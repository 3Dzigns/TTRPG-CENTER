from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional


class LLMProviderError(Exception):
    """Raised when a provider cannot return a response."""

    def __init__(self, message: str, *, retryable: bool = False) -> None:
        super().__init__(message)
        self.public_message = message
        self.retryable = retryable


@dataclass(slots=True)
class LLMResponse:
    """Normalized response object returned by provider adapters."""

    text: str
    model: str
    finish_reason: Optional[str] = None
    usage: Optional[Dict[str, Any]] = None
    raw: Optional[Any] = None


class BaseLLMProvider:
    """Interface for large language model providers."""

    name: str = "base"

    def is_configured(self) -> bool:
        """Return True when all configuration required to call the provider is available."""
        raise NotImplementedError

    def generate(
        self,
        prompt: str,
        model: str,
        *,
        temperature: Optional[float] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> LLMResponse:
        """Generate a response from the provider.

        Args:
            prompt: Rendered prompt text to send to the provider.
            model: Provider-specific model identifier.
            temperature: Optional sampling temperature override.
            metadata: Free-form metadata for logging/telemetry.
        """
        raise NotImplementedError


__all__ = ["BaseLLMProvider", "LLMProviderError", "LLMResponse"]
