"""Each provider's errors become the same plain Jobcu errors."""

import anthropic
import httpx
import httpx2
import openai
import pytest
from google.genai import errors as genai_errors

from jobcu.ai import anthropic_adapter, gemini_adapter, openai_adapter
from jobcu.ai.base import (
    AIAuthError,
    AIBadRequest,
    AIModelNotFound,
    AIQuotaExhausted,
    AIRateLimited,
    AIUnavailable,
)


def _response(status, headers=None):
    return httpx2.Response(status, headers=headers, request=httpx2.Request("POST", "https://x.test"))


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        (openai.AuthenticationError("bad key", response=_response(401), body=None), AIAuthError),
        (openai.NotFoundError("no model", response=_response(404), body=None), AIModelNotFound),
        (openai.BadRequestError("bad", response=_response(400), body=None), AIBadRequest),
        (openai.InternalServerError("oops", response=_response(500), body=None), AIUnavailable),
        (
            openai.RateLimitError(
                "insufficient_quota", response=_response(429), body={"code": "insufficient_quota"}
            ),
            AIQuotaExhausted,
        ),
    ],
)
def test_openai_errors(error, expected):
    assert isinstance(openai_adapter.translate_openai_error(error), expected)


def test_openai_rate_limit_keeps_retry_after():
    error = openai.RateLimitError(
        "slow down", response=_response(429, {"retry-after": "7"}), body=None
    )
    result = openai_adapter.translate_openai_error(error)
    assert isinstance(result, AIRateLimited) and result.retry_after == 7


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        (anthropic.AuthenticationError("bad", response=_response(401), body=None), AIAuthError),
        (anthropic.NotFoundError("no", response=_response(404), body=None), AIModelNotFound),
        (anthropic.APIStatusError("busy", response=_response(529), body=None), AIUnavailable),
        (
            anthropic.BadRequestError(
                "Your credit balance is too low", response=_response(400), body=None
            ),
            AIQuotaExhausted,
        ),
    ],
)
def test_anthropic_errors(error, expected):
    assert isinstance(anthropic_adapter._translate(error), expected)


def test_anthropic_rate_limit_keeps_retry_after():
    error = anthropic.RateLimitError(
        "slow down", response=_response(429, {"retry-after": "30"}), body=None
    )
    result = anthropic_adapter._translate(error)
    assert isinstance(result, AIRateLimited) and result.retry_after == 30


def _gemini_error(code, status, message, details=()):
    body = {"error": {"code": code, "status": status, "message": message, "details": list(details)}}
    return genai_errors.ClientError(code, body)


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        (
            _gemini_error(400, "INVALID_ARGUMENT", "API key not valid. Please pass a valid key."),
            AIAuthError,
        ),
        (_gemini_error(404, "NOT_FOUND", "models/x is not found"), AIModelNotFound),
        (_gemini_error(400, "INVALID_ARGUMENT", "thinking level not supported"), AIBadRequest),
        (
            _gemini_error(
                429,
                "RESOURCE_EXHAUSTED",
                "Quota exceeded",
                [{"violations": [{"quotaId": "GenerateRequestsPerDayPerProjectPerModel"}]}],
            ),
            AIQuotaExhausted,
        ),
        (genai_errors.ServerError(503, {"error": {"code": 503, "message": "busy"}}), AIUnavailable),
        (httpx.ConnectError("offline"), AIUnavailable),
    ],
)
def test_gemini_errors(error, expected):
    assert isinstance(gemini_adapter._translate(error), expected)


def test_gemini_per_minute_limit_keeps_suggested_wait():
    error = _gemini_error(
        429, "RESOURCE_EXHAUSTED", "Quota exceeded",
        [{"@type": "type.googleapis.com/google.rpc.RetryInfo", "retryDelay": "31s"}],
    )
    result = gemini_adapter._translate(error)
    assert isinstance(result, AIRateLimited) and result.retry_after == 31


def test_anthropic_asks_to_keep_the_instructions_ready():
    """Provider-side prompt caching: the same instructions cost less in later requests."""
    sent = {}

    class FakeMessages:
        def create(self, **request):
            sent.update(request)
            raise anthropic.APIStatusError("busy", response=_response(529), body=None)

    class FakeClient:
        messages = FakeMessages()
        models = None

    adapter = anthropic_adapter.AnthropicAdapter("fake-key")
    adapter._sdk_client = FakeClient()
    with pytest.raises(AIUnavailable):
        adapter.complete_json(model="m", system="Rules", prompt="Jobs", schema={}, schema_name="s",
                              effort=None, max_output_tokens=100)
    assert sent["system"] == [
        {"type": "text", "text": "Rules", "cache_control": {"type": "ephemeral"}}
    ]
