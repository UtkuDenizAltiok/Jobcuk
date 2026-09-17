"""The AI providers Jobcu can use, listed alphabetically. Jobcu recommends none of them."""

from dataclasses import dataclass

from jobcu.ai.anthropic_adapter import AnthropicAdapter
from jobcu.ai.base import ProviderAdapter
from jobcu.ai.compatible_adapter import CompatibleAdapter
from jobcu.ai.gemini_adapter import GeminiAdapter
from jobcu.ai.openai_adapter import OpenAIAdapter


@dataclass(frozen=True)
class ProviderInfo:
    id: str
    name: str
    adapter: type[ProviderAdapter]
    key_page: str  # where users create a key
    needs_base_url: bool = False
    key_optional: bool = False

    @property
    def key_name(self) -> str:
        return f"ai_{self.id}"


PROVIDERS: dict[str, ProviderInfo] = {
    info.id: info
    for info in (
        ProviderInfo(
            "anthropic", "Anthropic (Claude)", AnthropicAdapter,
            key_page="https://platform.claude.com/settings/keys",
        ),
        ProviderInfo(
            "gemini", "Google (Gemini)", GeminiAdapter,
            key_page="https://aistudio.google.com/apikey",
        ),
        ProviderInfo(
            "openai", "OpenAI", OpenAIAdapter,
            key_page="https://platform.openai.com/api-keys",
        ),
        ProviderInfo(
            "openai_compatible", "Other (OpenAI-compatible)", CompatibleAdapter,
            key_page="", needs_base_url=True, key_optional=True,
        ),
    )
}
