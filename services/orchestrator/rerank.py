"""Wrapper utilities for hybrid reranking within the orchestrator service."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from src_common.orchestrator.hybrid_reranker import HybridReranker, RerankedResult, RerankingConfig
from src_common.orchestrator.plan_models import QueryPlan
from src_common.orchestrator.classifier import Classification


class Reranker:
    """Thin wrapper around the shared HybridReranker implementation."""

    def __init__(self, environment: str) -> None:
        self._impl = HybridReranker(environment=environment)

    def rerank(
        self,
        query: str,
        results: List[Dict[str, Any]],
        *,
        plan: Optional[QueryPlan] = None,
        classification: Optional[Classification] = None,
        config: Optional[RerankingConfig] = None,
    ) -> List[RerankedResult]:
        return self._impl.rerank_results(
            query=query,
            results=results,
            config=config,
            query_plan=plan.retrieval_strategy if plan else None,
            classification=classification,
        )
