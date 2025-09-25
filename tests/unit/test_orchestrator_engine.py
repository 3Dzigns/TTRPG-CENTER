import datetime
from typing import Any, Dict, List, Optional

import pytest
from fastapi.testclient import TestClient

from services.orchestrator import api as orchestrator_api
from services.orchestrator.engine import OrchestratorEngine
from services.orchestrator.types import (
    AnswerMetadata,
    AnswerResponseModel,
    ClassificationModel,
    RetrievedChunk,
)
from src_common.orchestrator.plan_models import QueryPlan
from src_common.orchestrator.retriever import DocChunk


class FakePolicyManager:
    """Minimal policy manager stub for engine testing."""

    def __init__(self) -> None:
        self.version = "test-policy"
        self.last_loaded = datetime.datetime.utcnow()
        self.hot_reload = False

    def resolve_plan(self, classification: Dict[str, Any]) -> Dict[str, Any]:
        return {"vector_top_k": classification.get("vector_top_k", 8)}

    def get_policy_settings(self) -> Dict[str, Any]:
        return {}

    def _load(self) -> None:  # pragma: no cover - stub hook
        return None


class FakePromptRegistry:
    """Simple prompt registry stub returning canned prompts."""

    def __init__(self) -> None:
        self.version = "test-prompts"
        self.last_loaded = datetime.datetime.utcnow()
        self.hot_reload = False

    def get_prompt_bundle(self, key: str) -> Dict[str, Any]:
        return {"systemPrompt": "system", "userTemplate": "Question: {question}\nContext: {context}"}

    def get_prompt(self, key: str) -> str:
        return "prompt"

    def _load(self) -> None:  # pragma: no cover - stub hook
        return None


class FakeAnswerComposer:
    """Tracks citation preference and returns deterministic payload."""

    def __init__(self) -> None:
        self.include_citations: Optional[bool] = None

    def compose(
        self,
        query: str,
        plan: QueryPlan,
        classification: Dict[str, Any],
        chunks: List[DocChunk],
        *,
        include_citations: bool = True,
    ) -> tuple[str, list[dict[str, str]], dict[str, str], float]:
        self.include_citations = include_citations
        citations = [
            {"source": chunk.source, "label": "[Source 1]", "passage": chunk.text[:50]}
            for chunk in chunks
        ] if include_citations else []
        metadata = {
            "model_used": plan.model_config.get("model", "stub"),
            "provider": "stub",
        }
        return "answer", citations, metadata, 12.5


class FakeHybridRetriever:
    """Captures classification payload sent to retrieval."""

    def __init__(self) -> None:
        self.last_classification: Dict[str, Any] | None = None

    def retrieve(
        self,
        query: str,
        *,
        classification: Dict[str, Any] | None = None,
        top_k: int = 8,
        lane: str | None = None,
    ) -> tuple[QueryPlan, Dict[str, Any], list[DocChunk], float]:
        self.last_classification = classification
        resolved = classification or {
            "intent": "fact_lookup",
            "domain": "ttrpg_rules",
            "complexity": "low",
            "needs_tools": True,
            "confidence": 0.75,
        }
        plan = QueryPlan.create_from_query(
            query=query,
            classification=resolved,
            retrieval_strategy={"vector_top_k": top_k},
            model_config={},
        )
        chunk = DocChunk(id="chunk-1", text="Example content", source="memory", score=0.92, metadata={})
        return plan, resolved, [chunk], 15.0


class FakeClassifier:
    def classify_query(self, query: str) -> Dict[str, Any]:
        return {
            "intent": "fact_lookup",
            "domain": "ttrpg_rules",
            "complexity": "low",
            "needs_tools": True,
            "confidence": 0.8,
        }


class DummyEngine:
    """Stub engine used for FastAPI endpoint tests."""

    def __init__(self) -> None:
        self.answer_calls: list[dict[str, Any]] = []
        self.orchestrate_calls: list[dict[str, Any]] = []

    def _build_response(self) -> AnswerResponseModel:
        chunk = RetrievedChunk(
            chunkId="c1",
            content="content",
            score=1.0,
            metadata={},
            source="source",
            rank=1,
        )
        metadata = AnswerMetadata(modelUsed="stub", confidence=1.0, latencyMs=1.0)
        return AnswerResponseModel(answer="ok", citations=[], retrievedChunks=[chunk], metadata=metadata)

    def answer(self, query: str, **kwargs: Any) -> AnswerResponseModel:
        self.answer_calls.append(kwargs)
        return self._build_response()

    def orchestrate(self, query: str, **kwargs: Any) -> AnswerResponseModel:
        self.orchestrate_calls.append(kwargs)
        return self._build_response()


@pytest.fixture()
def fresh_engine() -> OrchestratorEngine:
    engine = OrchestratorEngine.__new__(OrchestratorEngine)
    engine.environment = "dev"
    engine._flags = {}
    engine.policy_manager = FakePolicyManager()
    engine.prompt_registry = FakePromptRegistry()
    engine.llm_client = object()
    engine.retriever = FakeHybridRetriever()
    engine.answer_composer = FakeAnswerComposer()
    engine.classifier = FakeClassifier()
    engine._started_at = 0.0
    return engine


def test_engine_answer_normalises_classification(fresh_engine: OrchestratorEngine) -> None:
    classification = ClassificationModel(
        intent="fact_lookup",
        domain="ttrpg_rules",
        complexity="low",
        needsTools=True,
        confidence=0.9,
    )

    response = fresh_engine.answer(
        "What is a saving throw?",
        classification=classification,
        model="custom-model",
        include_citations=False,
    )

    retriever: FakeHybridRetriever = fresh_engine.retriever  # type: ignore[assignment]
    composer: FakeAnswerComposer = fresh_engine.answer_composer  # type: ignore[assignment]

    assert retriever.last_classification is not None
    assert retriever.last_classification.get("needs_tools") is True
    assert retriever.last_classification.get("needsTools") is True
    assert response.metadata.model_used == "custom-model"
    assert response.citations == []
    assert composer.include_citations is False


def test_answer_endpoint_passes_model_and_citations(monkeypatch: pytest.MonkeyPatch) -> None:
    dummy_engine = DummyEngine()
    monkeypatch.setattr(orchestrator_api, "engine", dummy_engine)

    client = TestClient(orchestrator_api.app)
    payload = {
        "query": "Test",
        "model": "gpt-custom",
        "citations": False,
    }

    response = client.post("/v2/answer", json=payload, headers={"Idempotency-Key": "abc"})

    assert response.status_code == 200
    assert dummy_engine.answer_calls, "engine.answer was not invoked"
    call_kwargs = dummy_engine.answer_calls[0]
    assert call_kwargs["model"] == "gpt-custom"
    assert call_kwargs["include_citations"] is False


def test_orchestrate_endpoint_invokes_engine(monkeypatch: pytest.MonkeyPatch) -> None:
    dummy_engine = DummyEngine()
    monkeypatch.setattr(orchestrator_api, "engine", dummy_engine)

    client = TestClient(orchestrator_api.app)
    payload = {
        "query": "Test orchestrate",
    }

    response = client.post("/v2/orchestrate", json=payload, headers={"Idempotency-Key": "xyz"})

    assert response.status_code == 200
    assert dummy_engine.orchestrate_calls, "engine.orchestrate was not invoked"
    call_kwargs = dummy_engine.orchestrate_calls[0]
    assert call_kwargs.get("idempotency_key") == "xyz"


def test_hybrid_retriever_source_gating(monkeypatch):
    from services.orchestrator.retrieve import HybridRetriever
    from src_common.orchestrator.retriever import DocChunk
    from src_common.orchestrator.plan_models import QueryPlan

    class StubPolicy:
        def resolve_plan(self, classification):
            return {}

    class StubPlanner:
        def get_plan(self, query):
            classification = {
                "intent": "fact_lookup",
                "domain": "ttrpg_rules",
                "complexity": "low",
                "needs_tools": True,
                "confidence": 0.75,
            }
            return QueryPlan.create_from_query(
                query=query,
                classification=classification,
                retrieval_strategy={},
                model_config={},
            )

    monkeypatch.setattr(
        "services.orchestrator.retrieve.get_environment_config",
        lambda: {"ALLOWED_SOURCES": "trusted-source"},
    )
    monkeypatch.setattr("services.orchestrator.retrieve.get_planner", lambda env: StubPlanner())

    def fake_core_retrieve(plan, query, environment, limit=8, lane=None):
        return [
            DocChunk(id="allowed", text="A", source="trusted-source/doc.json", score=0.9, metadata={}),
            DocChunk(id="blocked", text="B", source="untrusted/doc.json", score=0.5, metadata={}),
        ]

    monkeypatch.setattr("services.orchestrator.retrieve.core_retrieve", fake_core_retrieve)

    retriever = HybridRetriever("test", StubPolicy())
    plan, classification, chunks, _ = retriever.retrieve("show me spells")

    assert [chunk.id for chunk in chunks] == ["allowed"]
