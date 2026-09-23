"""Shared building blocks for Jobcu's AI layer.

Each provider adapter turns its provider's answers and errors into these common
types, so the rest of Jobcu never needs to know which provider is in use.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass

from jobcu.settings import Effort


@dataclass
class Usage:
    """Tokens used by one request. `output_tokens` includes any reasoning tokens."""

    input_tokens: int = 0
    output_tokens: int = 0
    cached_input_tokens: int = 0
    reasoning_tokens: int = 0
    web_searches: int = 0

    def __add__(self, other: "Usage") -> "Usage":
        return Usage(
            self.input_tokens + other.input_tokens,
            self.output_tokens + other.output_tokens,
            self.cached_input_tokens + other.cached_input_tokens,
            self.reasoning_tokens + other.reasoning_tokens,
            self.web_searches + other.web_searches,
        )


@dataclass
class RawReply:
    text: str
    usage: Usage


@dataclass
class Source:
    """A page the AI used, so the person can check it."""

    url: str
    title: str = ""


@dataclass
class ResearchReply:
    """An answer the AI looked up on the web, with the pages it used."""

    text: str
    sources: list[Source]
    usage: Usage


class AIError(Exception):
    """An AI problem, with a message that a non-technical user can understand.

    `detail` keeps the provider's own wording for the log file.
    """

    retryable = False

    def __init__(self, message: str, detail: str = "") -> None:
        super().__init__(message)
        self.message = message
        self.detail = detail


class AIAuthError(AIError):
    pass


class AIModelNotFound(AIError):
    pass


class AIRateLimited(AIError):
    retryable = True

    def __init__(self, message: str, detail: str = "", retry_after: float | None = None):
        super().__init__(message, detail)
        self.retry_after = retry_after


class AIQuotaExhausted(AIError):
    """A daily limit or the account's credit is used up. Waiting a minute won't help."""


class AIUnavailable(AIError):
    retryable = True


class AIBadRequest(AIError):
    pass


class AIRefused(AIError):
    pass


class AIOutputTruncated(AIError):
    pass


class AIInvalidOutput(AIError):
    pass


class AILimitReached(AIError):
    """The user's own monthly limit in Jobcu's settings is reached."""


# Plain messages shared by all adapters.
MSG_KEY_REJECTED = (
    "The AI provider didn't accept the key. Please check that you copied the whole key, "
    "and that it belongs to the provider you picked."
)
MSG_NO_PERMISSION = (
    "The AI provider says this key isn't allowed to do this. Check the key's permissions "
    "on the provider's website."
)
MSG_MODEL_NOT_FOUND = (
    "The AI provider doesn't know this model name, or your key can't use it. "
    "Please pick a model from the list."
)
MSG_RATE_LIMITED = "AI limit reached, continuing more slowly."
MSG_QUOTA = (
    "Your AI allowance is used up for now (a daily limit, or no credit left). "
    "Check your account on the provider's website, or try again later."
)
MSG_UNAVAILABLE = (
    "Jobcu couldn't reach the AI provider. Check your internet connection. If it keeps "
    "happening, the provider may be having problems."
)
MSG_BAD_REQUEST = "The AI provider couldn't handle Jobcu's request."
MSG_NO_WEB_SEARCH = (
    "This AI provider can't look things up on the web from Jobcu, so anything that needs "
    "checking on the web is shown as \"not checked\"."
)
MSG_REFUSED = "The AI declined to answer this request."
MSG_TRUNCATED = "The AI's answer was cut off because it was too long."


class ProviderAdapter(ABC):
    """Talks to one AI provider. Created with the user's key for each use."""

    # True when the provider can search the web itself during an answer.
    can_search_the_web = False

    def __init__(self, api_key: str, base_url: str = "", timeout: float = 180.0) -> None:
        self.api_key = api_key
        self.base_url = base_url
        self.timeout = timeout

    @abstractmethod
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
        """Ask for an answer that follows `schema` and return its raw text."""

    def research(
        self,
        *,
        model: str,
        system: str,
        prompt: str,
        max_searches: int,
        max_output_tokens: int,
        effort: Effort | None = None,
    ) -> ResearchReply:
        """Answer using live web search, naming the pages used. Providers that can't, say so."""
        raise AIError(MSG_NO_WEB_SEARCH)

    @abstractmethod
    def list_models(self) -> list[str]:
        """Model names this key can use, for the settings screen."""


def unique_sources(sources: list[Source]) -> list[Source]:
    """The same page is often cited several times; keep the first mention of each."""
    seen: dict[str, Source] = {}
    for source in sources:
        seen.setdefault(source.url, source)
    return list(seen.values())


def parse_retry_after(value: str | None) -> float | None:
    """Read a Retry-After value given in seconds."""
    if not value:
        return None
    try:
        return max(0.0, float(value))
    except ValueError:
        return None
