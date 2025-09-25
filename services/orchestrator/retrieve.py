"""Hybrid retrieval coordination for the orchestrator service."""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional, Set, Tuple

from src_common.logging import get_logger
from src_common.config import get_environment_config
from src_common.orchestrator.classifier import Classification
from src_common.orchestrator.plan_models import QueryPlan
from src_common.orchestrator.query_planner import get_planner
from src_common.orchestrator.retriever import DocChunk, retrieve as core_retrieve

from .policy import PolicyManager
from .rerank import Reranker

logger = get_logger(__name__)


class HybridRetriever:
    """Executes hybrid retrieval using shared orchestration components."""

    def __init__(
        self,
        environment: str,
        policy_manager: PolicyManager,
        reranker: Optional[Reranker] = None,
    ) -> None:
        self.environment = environment
        self.policy_manager = policy_manager
        self.planner = get_planner(environment)
        self.reranker = reranker or Reranker(environment)
        self.allowed_sources = self._load_allowed_sources(environment)

    def retrieve(
        self,
        query: str,
        *,
        classification: Optional[Classification] = None,
        top_k: int = 8,
        lane: Optional[str] = None,
    ) -> Tuple[QueryPlan, Classification, List[DocChunk], float]:
        start_time = time.perf_counter()

        plan = self._resolve_plan(query)
        resolved_classification: Classification = classification or plan.classification  # type: ignore[assignment]

        # Ensure plan reflects up-to-date policy selections when classification supplied
        if classification is not None:
            overrides = self.policy_manager.resolve_plan(classification)
            plan.retrieval_strategy.update(overrides)

        top_k = max(1, min(top_k, plan.retrieval_strategy.get("vector_top_k", top_k)))

        lane_filter = None if not lane else lane.upper()
        chunks = core_retrieve(plan, query, self.environment, limit=top_k, lane=lane_filter)

        if not chunks:
            logger.warning("Hybrid retrieval returned no results; attempting vector-only fallback", extra={"query": query[:80]})
            vector_only_plan = plan.retrieval_strategy.copy()
            vector_only_plan["graph_depth"] = 0
            plan.retrieval_strategy.update(vector_only_plan)
            chunks = core_retrieve(plan, query, self.environment, limit=top_k, lane=lane_filter)

        if self.allowed_sources:
            filtered_chunks = [
                chunk
                for chunk in chunks
                if self._is_source_allowed(chunk)
            ]
            if len(filtered_chunks) != len(chunks):
                logger.info(
                    "Source gating filtered retrieval results",
                    extra={"requested": len(chunks), "allowed": len(filtered_chunks), "query": query[:80]},
                )
            chunks = filtered_chunks

        elapsed_ms = (time.perf_counter() - start_time) * 1000
        return plan, resolved_classification, chunks, elapsed_ms


    def _load_allowed_sources(self, environment: str) -> Set[str]:
        """Load and normalise allowed source prefixes from environment configuration."""

        env_config = get_environment_config()
        raw_sources = env_config.get("ALLOWED_SOURCES") or env_config.get("allowed_sources")
        if not raw_sources:
            logger.info(
                "No ALLOWED_SOURCES configured; retrieval operates without gating",
                extra={"env": environment},
            )
            return set()

        if isinstance(raw_sources, str):
            candidates = [item.strip() for item in raw_sources.split(",") if item.strip()]
        elif isinstance(raw_sources, (list, tuple, set)):
            candidates = [str(item).strip() for item in raw_sources if str(item).strip()]
        else:
            logger.warning(
                "ALLOWED_SOURCES config has unexpected type; ignoring gating",
                extra={"type": type(raw_sources).__name__},
            )
            return set()

        normalised: Set[str] = set()
        for value in candidates:
            lowered = value.lower()
            if not lowered:
                continue
            normalised.add(lowered)
            if lowered.endswith("/"):
                normalised.add(lowered.rstrip("/"))
        if normalised:
            logger.info(
                "Loaded allowed sources for retrieval gating",
                extra={"env": environment, "allowed": sorted(normalised)},
            )
        return normalised

    def _is_source_allowed(self, chunk: DocChunk) -> bool:
        """Determine whether a retrieved chunk originates from an allowed source."""

        if not self.allowed_sources:
            return True

        source_candidates = []
        source = (chunk.source or "").lower()
        if source:
            source_candidates.append(source)
            if "://" in source:
                source_candidates.append(source.split("://", 1)[1])
            if "/" in source:
                source_candidates.append(source.split("/", 1)[0])
        metadata = chunk.metadata or {}
        metadata_source = str(metadata.get("source", ""))
        if metadata_source:
            source_candidates.append(metadata_source.lower())
        metadata_source_id = str(metadata.get("source_id", ""))
        if metadata_source_id:
            source_candidates.append(metadata_source_id.lower())

        for candidate in source_candidates:
            for allowed in self.allowed_sources:
                if not allowed:
                    continue
                if candidate == allowed or candidate.startswith(f"{allowed}/") or candidate.startswith(allowed):
                    return True
        return False

    def _resolve_plan(self, query: str) -> QueryPlan:
        try:
            return self.planner.get_plan(query)
        except Exception as exc:  # pragma: no cover - defensive fallback
            logger.warning("Query planner failed; falling back to policy-only plan", extra={"error": str(exc)})
            fallback_classification: Classification = {  # type: ignore[assignment]
                "intent": "fact_lookup",
                "domain": "unknown",
                "complexity": "low",
                "needs_tools": True,
                "confidence": 0.25,
            }
            fallback_strategy = self.policy_manager.resolve_plan(fallback_classification)
            plan = QueryPlan.create_from_query(
                query=query,
                classification=fallback_classification,
                retrieval_strategy=fallback_strategy,
                model_config={},
            )
            return plan

