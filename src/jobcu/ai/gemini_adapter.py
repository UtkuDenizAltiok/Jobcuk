"""Google (Gemini) through the official `google-genai` library."""

import re

import httpx
from google import genai
from google.genai import errors, types

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
    unique_sources,
)
from jobcu.settings import Effort

_REFUSAL_REASONS = {"SAFETY", "PROHIBITED_CONTENT", "BLOCKLIST", "SPII", "RECITATION"}


class GeminiAdapter(ProviderAdapter):
    can_search_the_web = True
    _genai_client: genai.Client | None = None

    def _client(self) -> genai.Client:
        # Kept for the adapter's lifetime: the library closes its connection when the
        # client object is discarded, which would break results that are still loading.
        if self._genai_client is None:
            self._genai_client = genai.Client(
                api_key=self.api_key,
                http_options=types.HttpOptions(timeout=int(self.timeout * 1000)),
            )
        return self._genai_client

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
        config = types.GenerateContentConfig(
            system_instruction=system,
            response_mime_type="application/json",
            response_json_schema=schema,
            max_output_tokens=max_output_tokens,
            thinking_config=types.ThinkingConfig(thinking_level=effort.upper()) if effort else None,
            # Jobcu gives the model no tools here, so the library's tool loop stays off.
            automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
        )
        try:
            response = self._client().models.generate_content(
                model=model, contents=prompt, config=config
            )
        except Exception as exc:
            raise _translate(exc) from exc

        feedback = response.prompt_feedback
        if feedback is not None and feedback.block_reason:
            raise AIRefused(MSG_REFUSED, str(feedback.block_reason))
        candidate = response.candidates[0] if response.candidates else None
        finish = _name(candidate.finish_reason) if candidate is not None else ""
        if finish == "MAX_TOKENS":
            raise AIOutputTruncated(MSG_TRUNCATED)
        if finish in _REFUSAL_REASONS:
            raise AIRefused(MSG_REFUSED, finish)
        meta = response.usage_metadata
        thoughts = (meta.thoughts_token_count or 0) if meta else 0
        return RawReply(
            text=response.text or "",
            usage=Usage(
                input_tokens=(meta.prompt_token_count or 0) if meta else 0,
                # Thinking tokens are charged as output.
                output_tokens=((meta.candidates_token_count or 0) + thoughts) if meta else 0,
                cached_input_tokens=(meta.cached_content_token_count or 0) if meta else 0,
                reasoning_tokens=thoughts,
            ),
        )

    def research(
        self, *, model: str, system: str, prompt: str, max_searches: int, max_output_tokens: int
    ) -> ResearchReply:
        config = types.GenerateContentConfig(
            system_instruction=system,
            max_output_tokens=max_output_tokens,
            tools=[types.Tool(google_search=types.GoogleSearch())],
            automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
        )
        try:
            response = self._client().models.generate_content(
                model=model, contents=prompt, config=config
            )
        except Exception as exc:
            raise _translate(exc) from exc
        feedback = response.prompt_feedback
        if feedback is not None and feedback.block_reason:
            raise AIRefused(MSG_REFUSED, str(feedback.block_reason))
        candidate = response.candidates[0] if response.candidates else None
        sources, searches = [], 0
        grounding = getattr(candidate, "grounding_metadata", None) if candidate else None
        if grounding is not None:
            searches = len(getattr(grounding, "web_search_queries", None) or [])
            for chunk in getattr(grounding, "grounding_chunks", None) or []:
                web = getattr(chunk, "web", None)
                if web is not None and getattr(web, "uri", None):
                    sources.append(Source(web.uri, getattr(web, "title", "") or ""))
        meta = response.usage_metadata
        thoughts = (meta.thoughts_token_count or 0) if meta else 0
        return ResearchReply(
            text=response.text or "",
            sources=unique_sources(sources),
            usage=Usage(
                input_tokens=(meta.prompt_token_count or 0) if meta else 0,
                output_tokens=((meta.candidates_token_count or 0) + thoughts) if meta else 0,
                cached_input_tokens=(meta.cached_content_token_count or 0) if meta else 0,
                reasoning_tokens=thoughts,
                web_searches=searches,
            ),
        )

    def list_models(self) -> list[str]:
        try:
            models = list(self._client().models.list())
        except Exception as exc:
            raise _translate(exc) from exc
        return sorted(
            (model.name or "").removeprefix("models/")
            for model in models
            if "generateContent" in (model.supported_actions or [])
        )


def _name(value) -> str:
    return getattr(value, "name", None) or str(value or "")


def _translate(exc: Exception) -> Exception:
    detail = str(exc)
    if isinstance(exc, errors.APIError):
        status = (exc.status or "").upper()
        text = f"{status} {exc.message or ''} {exc.details or ''}"
        if exc.code == 429 or status == "RESOURCE_EXHAUSTED":
            # Daily limits (e.g. "...PerDay...") won't reset by waiting a minute.
            if "perday" in text.lower().replace("_", "").replace(" ", ""):
                return AIQuotaExhausted(MSG_QUOTA, detail)
            return AIRateLimited(MSG_RATE_LIMITED, detail, _retry_delay(text))
        if "API_KEY_INVALID" in text or "API key not valid" in text or exc.code == 401:
            return AIAuthError(MSG_KEY_REJECTED, detail)
        if exc.code == 403:
            return AIAuthError(MSG_NO_PERMISSION, detail)
        if exc.code == 404:
            return AIModelNotFound(MSG_MODEL_NOT_FOUND, detail)
        if exc.code and exc.code >= 500:
            return AIUnavailable(MSG_UNAVAILABLE, detail)
        return AIBadRequest(MSG_BAD_REQUEST, detail)
    if isinstance(exc, httpx.HTTPError):
        return AIUnavailable(MSG_UNAVAILABLE, detail)
    if isinstance(exc, AIError):
        return exc
    return AIBadRequest(MSG_BAD_REQUEST, detail)


def _retry_delay(text: str) -> float | None:
    """Gemini suggests a wait like 'retryDelay': '31s'."""
    match = re.search(r"retryDelay['\"]?\s*[:=]\s*['\"]?(\d+(?:\.\d+)?)s", text)
    return float(match.group(1)) if match else None
