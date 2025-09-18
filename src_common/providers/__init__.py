from __future__ import annotations

from typing import Dict, Iterable

from .anthropic import AnthropicProvider
from .base import BaseLLMProvider
from .openai import OpenAIProvider

_PROVIDER_FACTORIES: Dict[str, type[BaseLLMProvider]] = {
    "openai": OpenAIProvider,
    "anthropic": AnthropicProvider,
    "claude": AnthropicProvider,
}

_PROVIDER_CACHE: Dict[str, BaseLLMProvider] = {}


def get_provider(name: str) -> BaseLLMProvider:
    key = name.lower()
    if key not in _PROVIDER_FACTORIES:
        raise KeyError(f"Unknown LLM provider: {name}")
    if key not in _PROVIDER_CACHE:
        _PROVIDER_CACHE[key] = _PROVIDER_FACTORIES[key]()
    return _PROVIDER_CACHE[key]


def iter_providers(names: Iterable[str] | None = None) -> Iterable[BaseLLMProvider]:
    if names is None:
        keys = _PROVIDER_FACTORIES.keys()
    else:
        keys = (name.lower() for name in names)
    for key in keys:
        if key in _PROVIDER_FACTORIES:
            yield get_provider(key)


def any_provider_configured() -> bool:
    return any(provider.is_configured() for provider in iter_providers())


def reset_provider_cache() -> None:
    _PROVIDER_CACHE.clear()


__all__ = [
    "AnthropicProvider",
    "BaseLLMProvider",
    "OpenAIProvider",
    "any_provider_configured",
    "get_provider",
    "iter_providers",
    "reset_provider_cache",
]
