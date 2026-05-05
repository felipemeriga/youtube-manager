"""Routing layer between thumbnail nodes and the underlying image-gen module.

Both providers expose the same async functions with identical signatures —
this module just selects which one to call based on the conversation's
`image_provider` field.
"""
from types import ModuleType
from typing import Literal

from services import nano_banana, openai_image

ProviderName = Literal["gemini", "openai"]

_PROVIDERS: dict[str, ModuleType] = {
    "gemini": nano_banana,
    "openai": openai_image,
}

DEFAULT_PROVIDER: ProviderName = "gemini"

# Per-provider default model — used when QUALITY_TIER's "model" doesn't apply
# (e.g. switching providers mid-feature without changing the tier config).
DEFAULT_MODEL_BY_PROVIDER: dict[str, str] = {
    "gemini": "gemini-3-pro-image-preview",
    "openai": "gpt-image-2",
}


def get_provider(name: str | None) -> ModuleType:
    """Return the image-gen module for `name`. Falls back to gemini for
    unknown / None values so existing conversations without the column keep
    working."""
    return _PROVIDERS.get(name or DEFAULT_PROVIDER, _PROVIDERS[DEFAULT_PROVIDER])


def model_for(provider_name: str | None, tier_model: str) -> str:
    """Pick the right model id for the active provider.

    QUALITY_TIER stores Gemini's model name. When the OpenAI provider is
    active that name is meaningless — use the OpenAI default instead.
    """
    name = provider_name or DEFAULT_PROVIDER
    if name == "gemini":
        return tier_model
    return DEFAULT_MODEL_BY_PROVIDER.get(name, tier_model)
