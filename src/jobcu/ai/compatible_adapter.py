"""'Other (OpenAI-compatible)' providers: any service that offers the Chat Completions
format at its own address, including models running on the user's own computer.

These services differ in what they support. Jobcu first asks for strict JSON that
follows the schema; if the service refuses, it asks for plain JSON; if that fails
too, it describes the format in the prompt. Every answer is checked afterwards.
"""

import json
from typing import ClassVar

import openai

from jobcu.ai.base import (
    MSG_REFUSED,
    MSG_TRUNCATED,
    AIBadRequest,
    AIOutputTruncated,
    AIRefused,
    ProviderAdapter,
    RawReply,
    Usage,
)
from jobcu.ai.openai_adapter import list_openai_style_models, translate_openai_error
from jobcu.settings import Effort

MODES = ("json_schema", "json_object", "prompt_only")


class CompatibleAdapter(ProviderAdapter):
    # Remembers which mode worked for each (address, model) while Jobcu runs.
    _mode_cache: ClassVar[dict[tuple[str, str], str]] = {}

    _sdk_client: openai.OpenAI | None = None

    def _client(self) -> openai.OpenAI:
        if self._sdk_client is None:
            self._sdk_client = openai.OpenAI(
                # Local services often need no key, but the library requires some value.
                api_key=self.api_key or "not-needed",
                base_url=self.base_url,
                max_retries=0,
                timeout=self.timeout,
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
        # Reasoning settings aren't sent: services name them differently or reject them.
        cache_key = (self.base_url, model)
        start = MODES.index(self._mode_cache.get(cache_key, MODES[0]))
        last_error: Exception | None = None
        for mode in MODES[start:]:
            try:
                reply = self._request(mode, model, system, prompt, schema, schema_name,
                                      max_output_tokens)
            except AIBadRequest as exc:
                last_error = exc
                continue
            self._mode_cache[cache_key] = mode
            return reply
        assert last_error is not None
        raise last_error

    def _request(self, mode, model, system, prompt, schema, schema_name, max_output_tokens):
        extra: dict = {}
        if mode == "json_schema":
            extra["response_format"] = {
                "type": "json_schema",
                "json_schema": {"name": schema_name, "schema": schema, "strict": True},
            }
        else:
            if mode == "json_object":
                extra["response_format"] = {"type": "json_object"}
            prompt = (
                f"{prompt}\n\nReply with only a JSON object that follows this JSON schema, "
                f"with no other text:\n{json.dumps(schema)}"
            )
        try:
            response = self._client().chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": prompt},
                ],
                max_tokens=max_output_tokens,
                **extra,
            )
        except Exception as exc:
            raise translate_openai_error(exc) from exc

        if not response.choices:
            raise AIBadRequest("The AI provider sent an empty answer.")
        choice = response.choices[0]
        if choice.finish_reason == "length":
            raise AIOutputTruncated(MSG_TRUNCATED)
        if choice.finish_reason == "content_filter" or getattr(choice.message, "refusal", None):
            raise AIRefused(MSG_REFUSED)
        usage = response.usage
        return RawReply(
            text=choice.message.content or "",
            usage=Usage(
                input_tokens=(usage.prompt_tokens or 0) if usage else 0,
                output_tokens=(usage.completion_tokens or 0) if usage else 0,
                cached_input_tokens=_detail(usage, "prompt_tokens_details", "cached_tokens"),
                reasoning_tokens=_detail(usage, "completion_tokens_details", "reasoning_tokens"),
            ),
        )

    def list_models(self) -> list[str]:
        return list_openai_style_models(self._client())


def _detail(usage, group: str, name: str) -> int:
    details = getattr(usage, group, None) if usage else None
    return (getattr(details, name, 0) or 0) if details else 0
