from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Dict, Mapping, Optional

from ..ttrpg_logging import get_logger
from ..providers import any_provider_configured, get_provider
from ..providers.base import LLMProviderError

logger = get_logger(__name__)


@dataclass(slots=True)
class LLMResult:
    """Outcome of the LLM generation step."""

    answers: Dict[str, str]
    selected: str
    used_stub_llm: bool
    degraded: bool
    degraded_reason: Optional[str]
    provider: Optional[str]
    provider_metadata: Dict[str, Any]


def resolve_llm_mode(env: Optional[str] = None) -> str:
    """Determine whether the orchestrator should call live LLMs or stay in stub mode."""
    explicit = os.getenv("LLM_MODE")
    if explicit:
        normalized = explicit.strip().lower()
        if normalized in {"live", "stub"}:
            return normalized
        if normalized == "auto":
            return "live" if any_provider_configured() else "stub"
    env_name = (env or os.getenv("APP_ENV", "dev")).strip().lower()
    if env_name in {"prod", "production", "staging", "test", "ci"} and any_provider_configured():
        return "live"
    return "stub"


def infer_provider_name(model_cfg: Optional[Mapping[str, Any]]) -> str:
    if not model_cfg:
        return "openai"
    provider = model_cfg.get("provider") if isinstance(model_cfg, Mapping) else None
    if isinstance(provider, str) and provider:
        return provider.lower()
    model_name = str(model_cfg.get("model", "")).lower()
    if model_name.startswith("gpt"):
        return "openai"
    if "claude" in model_name or model_name.startswith("anthropic"):
        return "claude"
    return "openai"


def generate_rag_answers(
    prompt: str,
    model_cfg: Optional[Mapping[str, Any]],
    stub_answers: Dict[str, str],
    *,
    llm_mode: Optional[str] = None,
) -> LLMResult:
    """Return responses for the RAG pipeline, honoring live/stub configuration."""
    answers = dict(stub_answers)
    selected = _select_stub_answer(answers)
    mode = (llm_mode or resolve_llm_mode()).strip().lower()
    provider_metadata: Dict[str, Any] = {}

    if mode != "live":
        return LLMResult(
            answers=answers,
            selected=selected,
            used_stub_llm=True,
            degraded=False,
            degraded_reason=None,
            provider=None,
            provider_metadata=provider_metadata,
        )

    provider_name = infer_provider_name(model_cfg)
    provider_metadata["requested_model"] = model_cfg.get("model") if model_cfg else None
    provider_metadata["requested_provider"] = provider_name

    try:
        provider = get_provider(provider_name)
    except KeyError:
        reason = f"Provider '{provider_name}' is not supported."
        logger.warning("LLM provider selection failed: %s", reason)
        return LLMResult(
            answers=answers,
            selected=selected,
            used_stub_llm=True,
            degraded=True,
            degraded_reason=reason,
            provider=None,
            provider_metadata=provider_metadata,
        )

    provider_metadata["provider"] = provider.name

    if not provider.is_configured():
        reason = f"{provider.name.title()} provider is not configured."
        logger.warning("LLM provider unavailable: %s", reason)
        return LLMResult(
            answers=answers,
            selected=selected,
            used_stub_llm=True,
            degraded=True,
            degraded_reason=reason,
            provider=provider.name,
            provider_metadata=provider_metadata,
        )

    model_name = str((model_cfg or {}).get("model") or "")
    temperature = None
    if model_cfg and isinstance(model_cfg.get("temperature"), (int, float)):
        temperature = float(model_cfg["temperature"])

    try:
        result = provider.generate(
            prompt=prompt,
            model=model_name,
            temperature=temperature,
            metadata=dict(model_cfg) if isinstance(model_cfg, Mapping) else None,
        )
    except LLMProviderError as err:
        reason = err.public_message
        logger.warning("LLM provider error (%s): %s", provider.name, reason)
        return LLMResult(
            answers=answers,
            selected=_select_stub_answer(answers),
            used_stub_llm=True,
            degraded=True,
            degraded_reason=reason,
            provider=provider.name,
            provider_metadata=provider_metadata,
        )
    except Exception as exc:  # pragma: no cover - defensive catch
        reason = f"{provider.name.title()} provider failed ({exc.__class__.__name__})."
        logger.warning("LLM provider unexpected error", exc_info=exc)
        return LLMResult(
            answers=answers,
            selected=_select_stub_answer(answers),
            used_stub_llm=True,
            degraded=True,
            degraded_reason=reason,
            provider=provider.name,
            provider_metadata=provider_metadata,
        )

    answer_key = provider.name
    answers[answer_key] = result.text
    selected = answer_key

    usage = result.usage or None
    provider_metadata.update(
        {
            "provider": provider.name,
            "model": result.model,
        }
    )
    if result.finish_reason:
        provider_metadata["finish_reason"] = result.finish_reason
    if usage:
        provider_metadata["usage"] = usage

    return LLMResult(
        answers=answers,
        selected=selected,
        used_stub_llm=False,
        degraded=False,
        degraded_reason=None,
        provider=provider.name,
        provider_metadata=provider_metadata,
    )


def _select_stub_answer(answers: Dict[str, str]) -> str:
    if not answers:
        return "openai"
    return max(answers, key=lambda key: len(str(answers.get(key, ""))))


__all__ = [
    "LLMResult",
    "generate_rag_answers",
    "infer_provider_name",
    "resolve_llm_mode",
]
