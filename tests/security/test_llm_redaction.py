from fastapi.testclient import TestClient

from src_common.app import TTRPGApp
from src_common.providers import reset_provider_cache
from src_common.providers.openai import OpenAIProvider
from src_common.vector_store import factory


def test_llm_redaction_masks_api_keys(monkeypatch):
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("VECTOR_STORE_BACKEND", "memory")
    monkeypatch.setenv("PERSONA_TESTING_ENABLED", "false")
    monkeypatch.setenv("AEHRL_ENABLED", "false")
    monkeypatch.setenv("LLM_MODE", "live")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-secret-123")

    def noisy_failure(self, *_, **__):
        raise RuntimeError("network error using key sk-secret-123")

    reset_provider_cache()
    factory._CACHE.clear()
    monkeypatch.setattr(OpenAIProvider, "generate", noisy_failure)

    app = TTRPGApp().app
    with TestClient(app) as client:
        response = client.post("/rag/ask", json={"query": "Show stealth rules"})
        data = response.json()

    assert response.status_code == 200
    assert data["degraded"] is True
    assert "sk-secret-123" not in data.get("degraded_reason", "")
    reset_provider_cache()
    factory._CACHE.clear()
