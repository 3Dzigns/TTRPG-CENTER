"""High-level orchestration engine wiring together classification, retrieval, and answering."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Union

import yaml

from src_common.config import get_environment_config
from src_common.logging import get_logger
from src_common.orchestrator.classifier import Classification
from src_common.orchestrator.retriever import DocChunk

from .answer import AnswerComposer
from .classifier import QueryClassifier
from .llm import LLMClient
from .policy import PolicyManager
from .prompt_registry import PromptRegistry
from .retrieve import HybridRetriever
from .types import (
    AnswerMetadata,
    AnswerResponseModel,
    Citation,
    ClassificationModel,
    RetrievalResponseModel,
    RetrievedChunk,
)

logger = get_logger(__name__)


class OrchestratorEngine:
    """Coordinates the orchestrator service lifecycle and operations."""

    def __init__(self) -> None:
        env_config = get_environment_config()
        self.environment = env_config.get("environment", "dev")
        self._flags = self._load_flags()
        hot_reload = bool(self._flags.get("development", {}).get("hot_reload", False))
        self.policy_manager = PolicyManager(self.environment, hot_reload=hot_reload)
        self.prompt_registry = PromptRegistry(self.environment, hot_reload=hot_reload)
        self.llm_client = LLMClient(self.environment)
        self.retriever = HybridRetriever(self.environment, self.policy_manager)
        self.answer_composer = AnswerComposer(self.environment, self.prompt_registry, self.llm_client)
        self.classifier = QueryClassifier()
        self._started_at = time.perf_counter()

    # ------------------------------------------------------------------
    # Public operations

    def classify(self, query: str) -> ClassificationModel:
        result = self.classifier.classify_query(query)
        return ClassificationModel.model_validate(result)

    def retrieve(
        self,
        query: str,
        *,
        classification: Optional[ClassificationModel] = None,
        top_k: int = 8,
        lane: Optional[str] = None,
    ) -> RetrievalResponseModel:
        payload_classification = self._normalise_classification(classification)
        plan, resolved_classification, chunks, elapsed_ms = self.retriever.retrieve(
            query,
            classification=payload_classification,
            top_k=top_k,
            lane=lane,
        )
        retrieval_strategy = plan.retrieval_strategy.copy()
        payload_chunks = self._convert_chunks(chunks)
        classification_model = ClassificationModel.model_validate(resolved_classification)
        return RetrievalResponseModel(
            query=query,
            classification=classification_model,
            strategyUsed=retrieval_strategy,
            chunks=payload_chunks,
            totalChunks=len(payload_chunks),
            processingTimeMs=elapsed_ms,
        )

    def answer(
        self,
        query: str,
        *,
        classification: Optional[ClassificationModel] = None,
        top_k: int = 8,
        lane: Optional[str] = None,
        model: Optional[str] = None,
        include_citations: bool = True,
        idempotency_key: Optional[str] = None,
    ) -> AnswerResponseModel:
        payload_classification = self._normalise_classification(classification)
        plan, resolved_classification, chunks, retrieval_ms = self.retriever.retrieve(
            query,
            classification=payload_classification,
            top_k=top_k,
            lane=lane,
        )

        if model:
            plan.model_config = {**(plan.model_config or {}), "model": model}

        answer_text, citations_raw, llm_metadata, llm_latency = self.answer_composer.compose(
            query,
            plan,
            resolved_classification,
            chunks,
            include_citations=include_citations,
        )

        retrieved_chunks = self._convert_chunks(chunks)
        citations = [Citation(**item) for item in citations_raw]
        classification_model = ClassificationModel.model_validate(resolved_classification)
        confidence = self._estimate_confidence(classification_model, chunks)

        metadata = AnswerMetadata(
            modelUsed=llm_metadata.get("model_used", "stub"),
            confidence=confidence,
            latencyMs=retrieval_ms + llm_latency,
            provider=llm_metadata.get("provider"),
            idempotencyKey=idempotency_key,
        )

        return AnswerResponseModel(
            answer=answer_text,
            citations=citations,
            retrievedChunks=retrieved_chunks,
            metadata=metadata,
        )

    def orchestrate(
        self,
        query: str,
        *,
        context: Optional[Dict[str, Any]] = None,
        classification: Optional[ClassificationModel] = None,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        lane: Optional[str] = None,
        top_k: int = 8,
        model: Optional[str] = None,
        include_citations: bool = True,
        idempotency_key: Optional[str] = None,
    ) -> AnswerResponseModel:
        del context, user_id, session_id  # Context is reserved for future use.
        resolved_classification = classification or self.classify(query)
        return self.answer(
            query,
            classification=resolved_classification,
            top_k=top_k,
            lane=lane,
            model=model,
            include_citations=include_citations,
            idempotency_key=idempotency_key,
        )

    def uptime_seconds(self) -> float:
        return time.perf_counter() - self._started_at

    def policy_snapshot(self) -> Dict[str, str]:
        return {
            "retrievalPolicyVersion": self.policy_manager.version,
            "promptRegistryVersion": self.prompt_registry.version,
            "lastLoadedAt": self.prompt_registry.last_loaded.isoformat(),
        }

    # ------------------------------------------------------------------
    # Helpers

    def _load_flags(self) -> Dict[str, Dict[str, object]]:
        env_override = Path(f"env/{self.environment}/config/flags.yaml")
        candidates = [env_override, Path("config/flags.yaml")]
        for path in candidates:
            if path.exists():
                try:
                    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}
                except Exception as exc:  # pragma: no cover - defensive guard
                    logger.warning("Failed to load flags", extra={"path": str(path), "error": str(exc)})
        return {}

    @staticmethod
    def _convert_chunks(chunks: List[DocChunk]) -> List[RetrievedChunk]:
        payload: List[RetrievedChunk] = []
        for rank, chunk in enumerate(chunks, start=1):
            payload.append(
                RetrievedChunk(
                    chunkId=chunk.id,
                    content=chunk.text,
                    score=float(chunk.score),
                    metadata=chunk.metadata or {},
                    source=chunk.source,
                    rank=rank,
                )
            )
        return payload

    @staticmethod
    def _estimate_confidence(classification: ClassificationModel, chunks: List[DocChunk]) -> float:
        base_conf = classification.confidence
        if not chunks:
            return round(max(0.1, base_conf * 0.6), 3)
        top_scores = [max(0.0, min(1.0, chunk.score)) for chunk in chunks[:3]]
        avg_score = sum(top_scores) / len(top_scores)
        combined = (base_conf * 0.5) + (avg_score * 0.5)
        return round(min(1.0, max(0.1, combined)), 3)

    @staticmethod
    def _normalise_classification(
        classification: Optional[Union[ClassificationModel, Mapping[str, Any]]]
    ) -> Optional[Classification]:
        if classification is None:
            return None
        if isinstance(classification, ClassificationModel):
            payload: Dict[str, Any] = classification.model_dump(by_alias=False)
        elif isinstance(classification, Mapping):
            payload = dict(classification)
        else:
            raise TypeError("Unsupported classification payload supplied to orchestrator")

        if "needsTools" in payload and "needs_tools" not in payload:
            payload["needs_tools"] = payload["needsTools"]
        if "needs_tools" in payload and "needsTools" not in payload:
            payload["needsTools"] = payload["needs_tools"]

        return Classification(**payload)  # type: ignore[arg-type]
