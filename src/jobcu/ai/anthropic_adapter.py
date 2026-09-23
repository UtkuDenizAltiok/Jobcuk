"""Anthropic (Claude) through the official `anthropic` library."""

import anthropic

from jobcu.ai.base import (
    MSG_BAD_REQUEST,
    MSG_KEY_REJECTED,
    MSG_MODEL_NOT_FOUND,
    MSG_NO_PERMISSION,
    MSG_QUOTA,
    MSG_RATE_LIMITED,
    MSG_REFUSED,
    MSG_TRUNCATED,
    MSG_UNAVAILABLE,
    AIAuthError,
    AIBadRequest,
    AIError,
    AIModelNotFound,
    AIOutputTruncated,
    AIQuotaExhausted,
    AIRateLimited,
    AIRefused,
    AIUnavailable,
    ProviderAdapter,
    RawReply,
    ResearchReply,
    Source,
    Usage,
    parse_retry_after,
    unique_sources,
)
from jobcu.settings import Effort


class AnthropicAdapter(ProviderAdapter):
    can_search_the_web = True
    _sdk_client: anthropic.Anthropic | None = None

    def _client(self) -> anthropic.Anthropic:
        if self._sdk_client is None:
            self._sdk_client = anthropic.Anthropic(
                api_key=self.api_key, max_retries=0, timeout=self.timeout
            )
        return self._sdk_client

    def complete_json(
        self,
        *,
        model: str,
        system: str,
        prompt: str,
        schema: dict,
        schema_name: str,
        effort: Effort | None,
        max_output_tokens: int,
    ) -> RawReply:
        output_config: dict = {"format": {"type": "json_schema", "schema": schema}}
        # The instructions are the same in every request of a step (scoring asks about several
        # batches of jobs), so Anthropic is asked to keep them ready and charge less for them.
        system_blocks = [{"type": "text", "text": system,
                          "cache_control": {"type": "ephemeral"}}]
        if effort:
            # Anthropic has no "minimal" level; "low" is its lowest.
            output_config["effort"] = "low" if effort == "minimal" else effort
        try:
            response = self._client().messages.create(
                model=model,
                max_tokens=max_output_tokens,
                system=system_blocks,
                messages=[{"role": "user", "content": prompt}],
                output_config=output_config,
            )
        except Exception as exc:
            raise _translate(exc) from exc

        if response.stop_reason == "refusal":
            raise AIRefused(MSG_REFUSED)
        if response.stop_reason == "max_tokens":
            raise AIOutputTruncated(MSG_TRUNCATED)
        text = "".join(block.text for block in response.content if block.type == "text")
        return RawReply(text=text, usage=_usage(response.usage))

    def research(
        self, *, model: str, system: str, prompt: str, max_searches: int, max_output_tokens: int,
        effort: Effort | None = None,
    ) -> ResearchReply:
        extra: dict = {}
        if effort:
            extra["output_config"] = {"effort": "low" if effort == "minimal" else effort}
        try:
            response = self._client().messages.create(
                model=model,
                max_tokens=max_output_tokens,
                system=system,
                messages=[{"role": "user", "content": prompt}],
                tools=[{"type": "web_search_20250305", "name": "web_search",
                        "max_uses": max_searches}],
                **extra,
            )
        except Exception as exc:
            raise _translate(exc) from exc
        text, sources = [], []
        for block in response.content:
            if block.type == "text":
                text.append(block.text)
                for citation in getattr(block, "citations", None) or []:
                    url = getattr(citation, "url", None)
                    if url:
                        sources.append(Source(url, getattr(citation, "title", "") or ""))
            elif block.type == "web_search_tool_result":
                for item in getattr(block, "content", None) or []:
                    url = getattr(item, "url", None)
                    if url:
                        sources.append(Source(url, getattr(item, "title", "") or ""))
        return ResearchReply("".join(text), unique_sources(sources), _usage(response.usage))

    def list_models(self) -> list[str]:
        try:
            return sorted(model.id for model in self._client().models.list())
        except Exception as exc:
            raise _translate(exc) from exc


def _usage(usage) -> Usage:
    cache_write = usage.cache_creation_input_tokens or 0
    cache_read = usage.cache_read_input_tokens or 0
    tool_use = usage.server_tool_use
    return Usage(
        # Anthropic reports cached and uncached input separately; Jobcu counts the total.
        input_tokens=usage.input_tokens + cache_write + cache_read,
        output_tokens=usage.output_tokens,
        cached_input_tokens=cache_read,
        web_searches=(tool_use.web_search_requests or 0) if tool_use else 0,
    )


def _translate(exc: Exception) -> Exception:
    detail = str(exc)
    if isinstance(exc, anthropic.AuthenticationError):
        return AIAuthError(MSG_KEY_REJECTED, detail)
    if isinstance(exc, anthropic.PermissionDeniedError):
        return AIAuthError(MSG_NO_PERMISSION, detail)
    if isinstance(exc, anthropic.NotFoundError):
        return AIModelNotFound(MSG_MODEL_NOT_FOUND, detail)
    if isinstance(exc, anthropic.RateLimitError):
        retry_after = parse_retry_after(exc.response.headers.get("retry-after"))
        return AIRateLimited(MSG_RATE_LIMITED, detail, retry_after)
    if isinstance(exc, anthropic.APIStatusError):
        if exc.status_code == 402 or "credit balance" in detail.lower():
            return AIQuotaExhausted(MSG_QUOTA, detail)
        if exc.status_code == 529 or exc.status_code >= 500:
            return AIUnavailable(MSG_UNAVAILABLE, detail)
        return AIBadRequest(MSG_BAD_REQUEST, detail)
    if isinstance(exc, (anthropic.APIConnectionError, anthropic.APITimeoutError)):
        return AIUnavailable(MSG_UNAVAILABLE, detail)
    if isinstance(exc, AIError):
        return exc
    return AIBadRequest(MSG_BAD_REQUEST, detail)
