from __future__ import annotations

import os
from typing import Any, Dict, Optional

try:
    import anthropic
except Exception:  # pragma: no cover - optional dependency
    anthropic = None  # type: ignore[assignment]

from .base import BaseLLMProvider, LLMProviderError, LLMResponse


class AnthropicProvider(BaseLLMProvider):
    """Adapter for Anthropic's Claude models."""

    name = "claude"

    def __init__(self) -> None:
        self._api_key = os.getenv("ANTHROPIC_API_KEY", "").strip()
        self._client: Optional[anthropic.Anthropic] = None  # type: ignore[type-arg]

    def is_configured(self) -> bool:
        return bool(self._api_key) and anthropic is not None

    def _get_client(self) -> "anthropic.Anthropic":
        if anthropic is None:  # pragma: no cover - guarded in tests
            raise LLMProviderError("Anthropic provider unavailable: install the anthropic package.")
        if not self._api_key:
            raise LLMProviderError("Anthropic provider unavailable: missing ANTHROPIC_API_KEY.")
        if self._client is None:
            self._client = anthropic.Anthropic(api_key=self._api_key)
        return self._client

    def generate(
        self,
        prompt: str,
        model: str,
        *,
        temperature: Optional[float] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> LLMResponse:
        client = self._get_client()
        max_tokens = 1024
        if metadata and isinstance(metadata.get("max_tokens"), int):
            max_tokens = metadata["max_tokens"]
        try:
            response = client.messages.create(
                model=model,
                max_tokens=max_tokens,
                messages=[{"role": "user", "content": prompt}],
                temperature=temperature,
            )
        except Exception as exc:
            name = exc.__class__.__name__
            raise LLMProviderError(f"Anthropic provider request failed ({name}).") from exc

        text = _extract_text(response.content)
        usage = _normalize_usage(getattr(response, "usage", None))

        return LLMResponse(
            text=text,
            model=getattr(response, "model", model) or model,
            finish_reason=getattr(response, "stop_reason", None),
            usage=usage,
            raw=response,
        )


def _extract_text(content: Any) -> str:
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text" and "text" in item:
                parts.append(str(item["text"]))
            elif hasattr(item, "text"):
                parts.append(str(getattr(item, "text")))
            else:
                parts.append(str(item))
        return "\n".join(part for part in parts if part).strip()
    return ""


def _normalize_usage(usage: Any) -> Optional[Dict[str, Any]]:
    if usage is None:
        return None
    if isinstance(usage, dict):
        return {k: usage[k] for k in usage if usage[k] is not None}
    if hasattr(usage, "model_dump"):
        data = usage.model_dump()
        return {k: data[k] for k in data if data[k] is not None}
    if hasattr(usage, "dict"):
        data = usage.dict()
        return {k: data[k] for k in data if data[k] is not None}
    return None


__all__ = ["AnthropicProvider"]
