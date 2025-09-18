from __future__ import annotations

import os
from typing import Any, Dict, Optional

try:
    from openai import OpenAI
except Exception:  # pragma: no cover - dependency optional at import time
    OpenAI = None  # type: ignore[assignment]

from .base import BaseLLMProvider, LLMProviderError, LLMResponse


class OpenAIProvider(BaseLLMProvider):
    """Thin adapter around the OpenAI SDK."""

    name = "openai"

    def __init__(self) -> None:
        self._api_key = os.getenv("OPENAI_API_KEY", "").strip()
        self._client: Optional[OpenAI] = None  # type: ignore[type-arg]

    def is_configured(self) -> bool:
        return bool(self._api_key) and OpenAI is not None

    def _get_client(self) -> OpenAI:
        if OpenAI is None:  # pragma: no cover - guarded by is_configured in tests
            raise LLMProviderError("OpenAI provider unavailable: install the openai package.")
        if not self._api_key:
            raise LLMProviderError("OpenAI provider unavailable: missing OPENAI_API_KEY.")
        if self._client is None:
            self._client = OpenAI(api_key=self._api_key)
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
        try:
            response = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                temperature=temperature,
            )
        except Exception as exc:  # Broad catch to normalize SDK-specific errors
            name = exc.__class__.__name__
            raise LLMProviderError(f"OpenAI provider request failed ({name}).") from exc

        choice = response.choices[0]
        text = _extract_text(choice.message)
        usage = _normalize_usage(getattr(response, "usage", None))

        return LLMResponse(
            text=text,
            model=getattr(response, "model", model) or model,
            finish_reason=getattr(choice, "finish_reason", None),
            usage=usage,
            raw=response,
        )


def _extract_text(message: Any) -> str:
    content = getattr(message, "content", None)
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, dict) and "text" in item:
                parts.append(str(item.get("text", "")))
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


__all__ = ["OpenAIProvider"]
