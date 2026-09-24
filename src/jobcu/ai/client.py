"""The one place where Jobcu asks an AI anything.

Every AI request in Jobcu goes through `AIClient.generate`, which:
- picks the provider and model from the user's settings
- checks the user's monthly limit first
- waits and retries on rate limits and short outages, without losing progress
- drops reasoning settings a model doesn't support
- checks the answer against the expected format, and asks once more if it's wrong
- records the tokens used
"""

import logging
import random
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import ClassVar, TypeVar

from pydantic import BaseModel, ValidationError

from jobcu.ai.base import (
    MSG_NO_WEB_SEARCH,
    MSG_RATE_LIMITED,
    AIAuthError,
    AIBadRequest,
    AIError,
    AIInvalidOutput,
    AILimitReached,
    AIOutputTruncated,
    AIRateLimited,
    AIUnavailable,
    ProviderAdapter,
    ResearchReply,
)
from jobcu.ai.providers import PROVIDERS
from jobcu.ai.schema import extract_json, strict_json_schema
from jobcu.ai.usage import UsageLog, estimate_cost, total_tokens
from jobcu.keystore import KeyStore
from jobcu.settings import Effort, Settings

log = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)

MAX_RATE_LIMIT_WAITS = 10
MAX_OUTAGE_RETRIES = 4
MAX_WAIT_SECONDS = 300


# Thinking counts towards the output limit with every provider, but only what is used is paid
# for. Each request gets this room on top of its answer: without it, medium thinking cut off the
# answer of the step that sorts location conditions (2,000 tokens), and Jobcu fell back to
# looking everything up on the web (2026-09-24).
THINKING_ROOM = {"minimal": 1_000, "low": 4_000, "medium": 12_000, "high": 16_000}
MAX_OUTPUT_TOKENS = 32_000  # within every current provider's own limit


def with_thinking_room(max_output_tokens: int, effort: Effort | None) -> int:
    return min(max_output_tokens + THINKING_ROOM.get(effort or "", 0),
               max(max_output_tokens, MAX_OUTPUT_TOKENS))


class AIClient:
    # Models that rejected a reasoning setting, remembered while Jobcu runs.
    _effort_unsupported: ClassVar[set[tuple[str, str]]] = set()

    def __init__(
        self,
        settings: Settings,
        keys: KeyStore | None = None,
        *,
        usage_log: UsageLog | None = None,
        search_id: int | None = None,
        notify: Callable[[str], None] | None = None,
        patient: bool = True,
        sleep: Callable[[float], None] = time.sleep,
        adapter: ProviderAdapter | None = None,
    ) -> None:
        self.settings = settings
        self.keys = keys or KeyStore()
        self.usage_log = usage_log
        self.search_id = search_id
        self.notify = notify or (lambda message: None)
        self.patient = patient  # False for quick checks: report limits instead of waiting
        self.sleep = sleep
        self._adapter = adapter
        # Web look-ups used in this search, against the cap in Settings.
        self.web_searches_used = 0

    @property
    def provider_id(self) -> str:
        provider = self.settings.ai.provider
        if provider is None:
            raise AIAuthError("Please choose an AI provider in Settings first.")
        return provider

    def model_for(self, reasoning: bool) -> str:
        ai = self.settings.ai
        model = (ai.reasoning_model if reasoning and ai.reasoning_model else ai.model).strip()
        if not model:
            raise AIAuthError("Please choose an AI model in Settings first.")
        return model

    def adapter(self) -> ProviderAdapter:
        if self._adapter is None:
            info = PROVIDERS[self.provider_id]
            key = self.keys.get(info.key_name) or ""
            if not key and not info.key_optional:
                raise AIAuthError("Please enter your AI key in Settings first.")
            if info.needs_base_url and not self.settings.ai.base_url.strip():
                raise AIAuthError("Please enter the provider's address in Settings first.")
            self._adapter = info.adapter(key, base_url=self.settings.ai.base_url.strip())
        return self._adapter

    def generate(
        self,
        output: type[T],
        *,
        step: str,
        system: str,
        prompt: str,
        reasoning: bool = False,
        max_output_tokens: int = 4000,
    ) -> T:
        provider = self.provider_id
        model = self.model_for(reasoning)
        adapter = self.adapter()
        self._check_monthly_limit()

        effort = self.settings.ai.reasoning_effort if reasoning else self.settings.ai.scoring_effort
        if (provider, model) in self._effort_unsupported:
            effort = None
        schema = strict_json_schema(output)
        request_prompt = prompt
        rate_waits = outage_retries = 0
        effort_dropped = truncation_retried = repair_used = False

        while True:
            try:
                reply = adapter.complete_json(
                    model=model,
                    system=system,
                    prompt=request_prompt,
                    schema=schema,
                    schema_name=output.__name__,
                    effort=effort,
                    max_output_tokens=with_thinking_room(max_output_tokens, effort),
                )
            except AIRateLimited as exc:
                rate_waits += 1
                if not self.patient or rate_waits > MAX_RATE_LIMIT_WAITS:
                    raise
                self.notify(MSG_RATE_LIMITED)
                self._wait(exc.retry_after or min(10 * 2 ** (rate_waits - 1), 120), exc)
                continue
            except AIUnavailable as exc:
                outage_retries += 1
                if outage_retries > MAX_OUTAGE_RETRIES:
                    raise
                self._wait(min(5 * 2 ** (outage_retries - 1), 60), exc)
                continue
            except AIBadRequest:
                if effort is not None:
                    # Many models don't accept reasoning settings: try once without.
                    effort, effort_dropped = None, True
                    continue
                raise
            except AIOutputTruncated:
                if truncation_retried:
                    raise
                truncation_retried = True
                max_output_tokens *= 2
                continue

            if effort_dropped:
                self._effort_unsupported.add((provider, model))
            self._record(step, provider, model, reply.usage)
            try:
                return output.model_validate(extract_json(reply.text))
            except (ValueError, ValidationError) as exc:
                if repair_used:
                    raise AIInvalidOutput(
                        "The AI's answer wasn't in the format Jobcu needs, even after asking "
                        "again. A different model may work better.",
                        str(exc)[:500],
                    ) from exc
                repair_used = True
                request_prompt = (
                    f"{prompt}\n\nIMPORTANT: your previous answer did not follow the required "
                    "JSON format. Answer again with only valid JSON in exactly that format."
                )

    def research(
        self,
        *,
        step: str,
        system: str,
        prompt: str,
        max_searches: int = 4,
        max_output_tokens: int = 3000,
        effort: Effort | None = None,
    ) -> ResearchReply:
        """Ask the AI to look something up on the web and say which pages it used. The
        reasoning effort is the person's setting for reasoning steps unless `effort` says.

        Used for conditions Jobcu can only answer by checking current information (HANDOVER
        section 6 and 9.6). The user's own AI provider does the searching; Jobcu never contacts
        a search engine itself.
        """
        if not self.settings.use_web_search:
            raise AIError(
                "Looking things up on the web is switched off in Settings, so anything that "
                'needs checking is shown as "not checked".'
            )
        left = self.settings.limits.web_search_cap - self.web_searches_used
        if left <= 0:
            raise AILimitReached(
                "Jobcu has used this search's allowance of web look-ups. You can raise it in "
                "Settings."
            )
        provider = self.provider_id
        model = self.model_for(reasoning=True)
        adapter = self.adapter()
        if not adapter.can_search_the_web:
            raise AIError(MSG_NO_WEB_SEARCH)
        self._check_monthly_limit()
        effort = effort or self.settings.ai.reasoning_effort
        if (provider, model) in self._effort_unsupported:
            effort = None
        waits = outages = 0
        while True:
            try:
                reply = adapter.research(
                    model=model,
                    system=system,
                    prompt=prompt,
                    max_searches=min(max_searches, left),
                    max_output_tokens=with_thinking_room(max_output_tokens, effort),
                    effort=effort,
                )
                break
            except AIBadRequest:
                if effort is None:
                    raise
                # Many models don't accept reasoning settings: try once without.
                effort = None
                self._effort_unsupported.add((provider, model))
            except AIRateLimited as exc:
                waits += 1
                if not self.patient or waits > MAX_RATE_LIMIT_WAITS:
                    raise
                self.notify(MSG_RATE_LIMITED)
                self._wait(exc.retry_after or min(10 * 2 ** (waits - 1), 120), exc)
            except AIUnavailable as exc:
                outages += 1
                if outages > MAX_OUTAGE_RETRIES:
                    raise
                self._wait(min(5 * 2 ** (outages - 1), 60), exc)
        self.web_searches_used += max(1, reply.usage.web_searches)
        self._record(step, provider, model, reply.usage)
        return reply

    def _wait(self, seconds: float, reason: AIError) -> None:
        seconds = min(max(seconds, 1.0), MAX_WAIT_SECONDS) + random.uniform(0, 1)
        log.info("AI request waiting %.0fs: %s", seconds, reason.detail or reason.message)
        self.sleep(seconds)

    def _record(self, step: str, provider: str, model: str, usage) -> None:
        if self.usage_log is not None:
            self.usage_log.record(
                step=step, provider=provider, model=model, usage=usage, search_id=self.search_id
            )

    def _check_monthly_limit(self) -> None:
        if self.usage_log is None:
            return
        limits = self.settings.limits
        if limits.monthly_token_limit is None and limits.monthly_cost_limit is None:
            return
        month = self.usage_log.this_month()
        if limits.monthly_token_limit is not None and total_tokens(month) >= (
            limits.monthly_token_limit
        ):
            raise AILimitReached(
                "Your monthly AI limit in Jobcu's settings is reached, so Jobcu stopped using "
                "the AI. You can raise the limit in Settings."
            )
        if limits.monthly_cost_limit is not None:
            cost, _ = estimate_cost(month, self.settings.prices)
            if cost >= limits.monthly_cost_limit:
                raise AILimitReached(
                    "Your monthly AI spending limit in Jobcu's settings is reached, so Jobcu "
                    "stopped using the AI. You can raise the limit in Settings."
                )


# ---------------------------------------------------------------------------
# Setup check: does the key work, and does the model answer in Jobcu's format?
# ---------------------------------------------------------------------------


class _ConnectionProbe(BaseModel):
    ok: bool
    word: str


@dataclass
class CheckResult:
    ok: bool
    message: str


def check_setup(settings: Settings, keys: KeyStore | None = None, **client_args) -> CheckResult:
    client = AIClient(settings, keys, patient=False, **client_args)
    models = [client.model_for(False)] if settings.ai.model.strip() else []
    if settings.ai.reasoning_model.strip():
        models.append(client.model_for(True))
    if not models:
        return CheckResult(False, "Please choose an AI model first.")
    try:
        for reasoning in ([False, True] if len(models) == 2 else [False]):
            answer = client.generate(
                _ConnectionProbe,
                step="setup_check",
                system="You are a connection test for an app.",
                prompt='Reply with "ok" set to true and "word" set to "jobcu".',
                reasoning=reasoning,
                max_output_tokens=2000,
            )
            if not answer.ok or answer.word.strip().lower() != "jobcu":
                return CheckResult(
                    False,
                    "The model answered, but not correctly. A different model may work better.",
                )
    except AIRateLimited:
        return CheckResult(
            False,
            "The key works, but the AI provider says you've hit a short-term limit. "
            "Wait a minute and test again.",
        )
    except AIError as exc:
        log.warning("Setup check failed: %s", exc.detail or exc.message)
        return CheckResult(False, exc.message)
    if len(models) == 2:
        return CheckResult(True, "Connection works. Both models answer in the format Jobcu needs.")
    return CheckResult(True, "Connection works. The model answers in the format Jobcu needs.")
