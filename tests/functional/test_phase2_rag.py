# tests/functional/test_phase2_rag.py
"""
Functional tests for Phase 2 RAG retrieval endpoint.
"""

from fastapi.testclient import TestClient


def test_rag_ping(test_client: TestClient, mock_environment):
    r = test_client.get("/rag/ping")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "ok"
    assert data["component"] == "rag"


def test_rag_ask_basic_contract(test_client: TestClient, mock_environment):
    payload = {"query": "What is initiative in combat?"}
    r = test_client.post("/rag/ask", json=payload)
    assert r.status_code == 200
    data = r.json()

    # Top-level structure
    for key in ("classification", "plan", "model", "metrics", "retrieved", "answers"):
        assert key in data

    # Classification has required fields
    cls = data["classification"]
    for k in ("intent", "domain", "complexity", "needs_tools", "confidence"):
        assert k in cls

    # Metrics include timer, token count, and model badge
    m = data["metrics"]
    assert isinstance(m["timer_ms"], int)
    assert isinstance(m["token_count"], int)
    assert m["model_badge"]

    # Retrieved chunks with provenance
    chunks = data["retrieved"]
    assert isinstance(chunks, list)
    assert len(chunks) <= 3
    for c in chunks:
        for ck in ("id", "text", "source", "score", "metadata"):
            assert ck in c

    # Answers present and selector chosen
    ans = data["answers"]
    assert "openai" in ans and "claude" in ans and "selected" in ans

