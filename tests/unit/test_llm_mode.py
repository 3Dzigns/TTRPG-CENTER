import os

import pytest

from src_common.orchestrator.llm_runtime import generate_rag_answers
from src_common.providers import reset_provider_cache
from src_common.providers.base import LLMProviderError, LLMResponse
from src_common.providers.openai import OpenAIProvider


@pytest.fixture(autouse=True)
def reset_providers():
    reset_provider_cache()
    yield
    reset_provider_cache()


def test_llm_mode_stub_by_default_dev(monkeypatch):
    monkeypatch.delenv("LLM_MODE", raising=False)
    monkeypatch.setenv("APP_ENV", "dev")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    result = generate_rag_answers(
        prompt="Explain the rules",
        model_cfg={"model": "gpt-4o-mini"},
        stub_answers={"openai": "stub openai", "claude": "stub claude"},
    )

    assert result.used_stub_llm is True
    assert result.degraded is False
    assert result.selected in {"openai", "claude"}


def test_llm_mode_live_when_keys_present(monkeypatch):
    monkeypatch.setenv("LLM_MODE", "live")
    monkeypatch.setenv("APP_ENV", "dev")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")

    def fake_generate(self, prompt, model, **kwargs):
        return LLMResponse(text="live answer", model=model, finish_reason="stop")

    monkeypatch.setattr(OpenAIProvider, "generate", fake_generate)

    result = generate_rag_answers(
        prompt="Explain the rules",
        model_cfg={"model": "gpt-4o-mini"},
        stub_answers={"openai": "stub", "claude": "stub"},
    )

    assert result.used_stub_llm is False
    assert result.degraded is False
    assert result.selected == "openai"
    assert result.answers["openai"] == "live answer"


def test_fallback_sets_degraded_flag_on_error(monkeypatch):
    monkeypatch.setenv("LLM_MODE", "live")
    monkeypatch.setenv("APP_ENV", "dev")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")

    def failing_generate(self, *_, **__):
        raise LLMProviderError("OpenAI provider request failed (TimeoutError).")

    monkeypatch.setattr(OpenAIProvider, "generate", failing_generate)

    result = generate_rag_answers(
        prompt="Explain the rules",
        model_cfg={"model": "gpt-4o-mini"},
        stub_answers={"openai": "stub", "claude": "stub"},
    )

    assert result.used_stub_llm is True
    assert result.degraded is True
    assert result.degraded_reason == "OpenAI provider request failed (TimeoutError)."
