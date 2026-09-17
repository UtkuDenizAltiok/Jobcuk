"""OpenAI through the official `openai` library (Responses API), plus shared helpers
for "Other (OpenAI-compatible)" providers."""

import openai

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

# Words in model names that mean the model can't write text answers
# (image, audio, embedding models and similar). Used only to tidy the model list.
_NON_TEXT_MODEL_WORDS = (
    "embedding",
    "tts",
    "whisper",
    "dall-e",
    "image",
    "audio",
    "realtime",
    "moderation",
    "transcribe",
    "speech",
    "sora",
    "video",
)


class OpenAIAdapter(ProviderAdapter):
    can_search_the_web = True
    _sdk_client: openai.OpenAI | None = None

    def _client(self) -> openai.OpenAI:
        if self._sdk_client is None:
            self._sdk_client = openai.OpenAI(
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
        extra: dict = {}
        if effort:
            extra["reasoning"] = {"effort": effort}
        try:
            response = self._client().responses.create(
                model=model,
                instructions=system,
                input=prompt,
                text={
                    "format": {
                        "type": "json_schema",
                        "name": schema_name,
                        "schema": schema,
                        "strict": True,
                    }
                },
                max_output_tokens=max_output_tokens,
                store=False,  # don't keep the user's data on OpenAI's side
                **extra,
            )
        except Exception as exc:
            raise translate_openai_error(exc) from exc

        if response.status == "incomplete":
            reason = getattr(response.incomplete_details, "reason", "")
            if reason == "content_filter":
                raise AIRefused(MSG_REFUSED)
            raise AIOutputTruncated(MSG_TRUNCATED)
        for item in response.output:
            for part in getattr(item, "content", None) or []:
                if getattr(part, "type", "") == "refusal":
                    raise AIRefused(MSG_REFUSED, getattr(part, "refusal", ""))
        usage = response.usage
        return RawReply(
            text=response.output_text,
            usage=Usage(
                input_tokens=usage.input_tokens,
                output_tokens=usage.output_tokens,
                cached_input_tokens=_attr(usage.input_tokens_details, "cached_tokens"),
                reasoning_tokens=_attr(usage.output_tokens_details, "reasoning_tokens"),
            ),
        )

    def research(
        self, *, model: str, system: str, prompt: str, max_searches: int, max_output_tokens: int
    ) -> ResearchReply:
        try:
            response = self._client().responses.create(
                model=model,
                instructions=system,
                input=prompt,
                tools=[{"type": "web_search"}],
                max_output_tokens=max_output_tokens,
                store=False,
            )
        except Exception as exc:
            raise translate_openai_error(exc) from exc
        sources, searches = [], 0
        for item in response.output:
            if getattr(item, "type", "") == "web_search_call":
                searches += 1
            for part in getattr(item, "content", None) or []:
                for annotation in getattr(part, "annotations", None) or []:
                    url = getattr(annotation, "url", None)
                    if url:
                        sources.append(Source(url, getattr(annotation, "title", "") or ""))
        usage = response.usage
        return ResearchReply(
            text=response.output_text,
            sources=unique_sources(sources),
            usage=Usage(
                input_tokens=usage.input_tokens,
                output_tokens=usage.output_tokens,
                cached_input_tokens=_attr(usage.input_tokens_details, "cached_tokens"),
                reasoning_tokens=_attr(usage.output_tokens_details, "reasoning_tokens"),
                web_searches=searches,
            ),
        )

    def list_models(self) -> list[str]:
        return list_openai_style_models(self._client())


def list_openai_style_models(client: openai.OpenAI) -> list[str]:
    try:
        names = [model.id for model in client.models.list()]
    except Exception as exc:
        raise translate_openai_error(exc) from exc
    return sorted(
        name for name in names if not any(word in name.lower() for word in _NON_TEXT_MODEL_WORDS)
    )


def translate_openai_error(exc: Exception) -> Exception:
    detail = str(exc)
    if isinstance(exc, openai.AuthenticationError):
        return AIAuthError(MSG_KEY_REJECTED, detail)
    if isinstance(exc, openai.PermissionDeniedError):
        return AIAuthError(MSG_NO_PERMISSION, detail)
    if isinstance(exc, openai.NotFoundError):
        return AIModelNotFound(MSG_MODEL_NOT_FOUND, detail)
    if isinstance(exc, openai.RateLimitError):
        if "insufficient_quota" in detail or getattr(exc, "code", None) == "insufficient_quota":
            return AIQuotaExhausted(MSG_QUOTA, detail)
        retry_after = parse_retry_after(exc.response.headers.get("retry-after"))
        return AIRateLimited(MSG_RATE_LIMITED, detail, retry_after)
    if isinstance(exc, openai.APIStatusError):
        if exc.status_code == 402:
            return AIQuotaExhausted(MSG_QUOTA, detail)
        if exc.status_code >= 500:
            return AIUnavailable(MSG_UNAVAILABLE, detail)
        return AIBadRequest(MSG_BAD_REQUEST, detail)
    if isinstance(exc, (openai.APIConnectionError, openai.APITimeoutError)):
        return AIUnavailable(MSG_UNAVAILABLE, detail)
    if isinstance(exc, AIError):
        return exc
    return AIBadRequest(MSG_BAD_REQUEST, detail)


def _attr(obj, name: str) -> int:
    return (getattr(obj, name, 0) or 0) if obj is not None else 0
