from fastapi.testclient import TestClient

from src_common.app import TTRPGApp
from src_common.vector_store import factory


def _make_client():
    factory._CACHE.clear()
    app = TTRPGApp().app
    return TestClient(app)


def test_answer_contract_structure(monkeypatch):
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("VECTOR_STORE_BACKEND", "memory")
    monkeypatch.setenv("PERSONA_TESTING_ENABLED", "false")
    monkeypatch.setenv("AEHRL_ENABLED", "false")
    monkeypatch.delenv("LLM_MODE", raising=False)

    with _make_client() as client:
        response = client.post("/rag/ask", json={"query": "Outline rage benefits"})
        data = response.json()

    assert response.status_code == 200
    assert set(data.keys()) >= {"query", "answer", "sources", "trace_id", "used_stub_llm", "answers"}
    assert isinstance(data["trace_id"], str)
    assert isinstance(data["sources"], list)
    assert "selected" in data["answers"]
    assert "model" in data
