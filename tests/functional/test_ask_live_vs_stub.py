import pytest
from fastapi.testclient import TestClient

from src_common.app import TTRPGApp
from src_common.providers import reset_provider_cache
from src_common.providers.base import LLMProviderError, LLMResponse
from src_common.providers.openai import OpenAIProvider
from src_common.vector_store import factory


@pytest.fixture
def rag_client(monkeypatch):
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("VECTOR_STORE_BACKEND", "memory")
    monkeypatch.setenv("PERSONA_TESTING_ENABLED", "false")
    monkeypatch.setenv("AEHRL_ENABLED", "false")

    reset_provider_cache()
    factory._CACHE.clear()

    app = TTRPGApp().app
    with TestClient(app) as client:
        yield client

    reset_provider_cache()
    factory._CACHE.clear()


def test_stub_mode_returns_stub_answer(monkeypatch, rag_client):
    monkeypatch.delenv("LLM_MODE", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    response = rag_client.post("/rag/ask", json={"query": "What is a focus spell?"})
    data = response.json()

    assert response.status_code == 200
    assert data["used_stub_llm"] is True
    assert data["degraded"] is False
    assert data["answers"]["selected"] in {"openai", "claude"}
    assert data["answer"]
    assert isinstance(data["sources"], list)
    assert data["lane"] == "A"


def test_live_mode_returns_live_answer(monkeypatch, rag_client):
    monkeypatch.setenv("LLM_MODE", "live")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")

    def fake_generate(self, prompt, model, **kwargs):
        return LLMResponse(text="real answer", model=model, finish_reason="stop")

    monkeypatch.setattr(OpenAIProvider, "generate", fake_generate)

    response = rag_client.post("/rag/ask", json={"query": "How many actions to cast?"})
    data = response.json()

    assert response.status_code == 200
    assert data["used_stub_llm"] is False
    assert data["degraded"] is False
    assert data["answers"]["selected"] == "openai"
    assert data["answer"] == "real answer"
    assert data["model"].get("provider") == "openai"
    assert data["lane"] == "A"


def test_live_mode_fallback_sets_degraded(monkeypatch, rag_client):
    monkeypatch.setenv("LLM_MODE", "live")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")

    def failing_generate(self, *_, **__):
        raise LLMProviderError("OpenAI provider request failed (RateLimitError).")

    monkeypatch.setattr(OpenAIProvider, "generate", failing_generate)

    response = rag_client.post("/rag/ask", json={"query": "Describe recall knowledge."})
    data = response.json()

    assert response.status_code == 200
    assert data["used_stub_llm"] is True
    assert data["degraded"] is True
    assert "RateLimitError" in data["degraded_reason"]
    assert "sk-test" not in data["degraded_reason"]


def test_lane_override_in_response(rag_client):
    response = rag_client.post("/rag/ask", json={"query": "Describe a paladin", "lane": "B"})
    data = response.json()

    assert response.status_code == 200
    assert data["lane"] == "B"
