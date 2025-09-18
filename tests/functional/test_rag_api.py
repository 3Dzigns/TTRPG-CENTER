import pytest
from fastapi.testclient import TestClient
from types import SimpleNamespace

from src_common.app import TTRPGApp
from src_common.orchestrator import service
from src_common.orchestrator.retriever import DocChunk


@pytest.fixture
def rag_client(monkeypatch):
    monkeypatch.setenv("APP_ENV", "test")
    app = TTRPGApp().app
    with TestClient(app) as client:
        yield client


def test_rag_classify_endpoint_returns_classification(rag_client):
    response = rag_client.post("/rag/classify", json={"query": "Explain spell slots"})
    data = response.json()

    assert response.status_code == 200
    assert data["classification"]["intent"]
    assert data["environment"] == "test"


def test_rag_retrieve_endpoint_respects_lane(monkeypatch, rag_client):
    def fake_resolve(env, query):
        classification = {"intent": "fact_lookup", "domain": "ttrpg_rules", "complexity": "low"}
        plan = {"vector_top_k": 5}
        model_cfg = {"model": "gpt-4o-mini"}
        query_plan = SimpleNamespace(
            retrieval_strategy=plan,
            model_config=model_cfg,
            performance_hints={},
            query_hash=None,
            hit_count=0,
            graph_expansion=None,
        )
        return classification, query_plan, plan, model_cfg

    captured = {}

    def fake_retrieve(plan, query, env, limit=3, lane=None):
        captured["lane"] = lane
        return [
            DocChunk(
                id="chunk-1",
                text="Sample content",
                source="vector:test",
                score=0.95,
                metadata={"lane": lane or "A"},
            )
        ]

    monkeypatch.setattr(service, "_resolve_query_plan", fake_resolve)
    monkeypatch.setattr(service, "retrieve", fake_retrieve)

    response = rag_client.post("/rag/retrieve", json={"query": "Explain stealth", "lane": "C", "top_k": 2})
    data = response.json()

    assert response.status_code == 200
    assert captured["lane"] == "C"
    assert data["lane"] == "C"
    assert data["chunks"]
    assert data["chunks"][0]["metadata"]["lane"] == "C"
