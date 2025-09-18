"""
Hybrid Reranker for TTRPG Content Retrieval

Implements multi-signal reranking to improve result relevance through:
- Vector similarity signals
- Graph relationship signals
- Content feature signals
- Domain-specific TTRPG signals

Integrates with QueryPlanner (FR-024) and Graph Augmented Retrieval (FR-025).
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Dict, List, Any, Optional, Union, Tuple
from enum import Enum

from ..ttrpg_logging import get_logger
from .classifier import Classification

logger = get_logger(__name__)


class RerankingStrategy(Enum):
    """Available reranking strategies based on query characteristics."""
    VECTOR_ONLY = "vector_only"
    GRAPH_ENHANCED = "graph_enhanced"
    CONTENT_FOCUSED = "content_focused"
    DOMAIN_AWARE = "domain_aware"
    HYBRID_FULL = "hybrid_full"


@dataclass
class RerankingSignals:
    """Container for all reranking signals computed for a result."""

    # Vector similarity signals
    vector_similarity: float = 0.0
    semantic_similarity: float = 0.0

    # Graph relationship signals
    graph_relevance: float = 0.0
    relationship_score: float = 0.0
    cross_reference_boost: float = 0.0

    # Content feature signals
    content_quality: float = 0.0
    readability_score: float = 0.0
    length_penalty: float = 0.0
    structure_score: float = 0.0

    # Domain-specific TTRPG signals
    entity_match_score: float = 0.0
    mechanics_relevance: float = 0.0
    rulebook_authority: float = 0.0

    # Metadata signals
    recency_boost: float = 0.0
    popularity_score: float = 0.0


@dataclass
class RerankedResult:
    """Container for a reranked result with detailed scoring."""

    # Original result data
    original_result: Dict[str, Any]
    original_rank: int
    original_score: float

    # Reranking data
    final_score: float
    final_rank: int
    signals: RerankingSignals

    # Performance metadata
    reranking_time_ms: float
    strategy_used: RerankingStrategy


@dataclass
class RerankingConfig:
    """Configuration for reranking strategies and signal weights."""

    strategy: RerankingStrategy = RerankingStrategy.HYBRID_FULL

    # Signal weights (sum should be 1.0)
    vector_weight: float = 0.3
    graph_weight: float = 0.2
    content_weight: float = 0.2
    domain_weight: float = 0.2
    metadata_weight: float = 0.1

    # Performance controls
    max_results_to_rerank: int = 20
    reranking_timeout_ms: int = 100
    enable_signal_caching: bool = True

    # Quality thresholds
    min_score_threshold: float = 0.1
    diversity_alpha: float = 0.7  # Balance between relevance and diversity


class HybridReranker:
    """
    Multi-signal hybrid reranker for TTRPG content.

    Combines vector similarity, graph relationships, content features,
    and domain-specific signals to improve result relevance.
    """

    def __init__(self, environment: str = "dev"):
        self.environment = environment
        self.signal_cache: Dict[str, RerankingSignals] = {}

        # Import signal extractors
        try:
            from .signal_extractors import (
                VectorSignalExtractor,
                GraphSignalExtractor,
                ContentSignalExtractor,
                DomainSignalExtractor
            )

            self.vector_extractor = VectorSignalExtractor(environment)
            self.graph_extractor = GraphSignalExtractor(environment)
            self.content_extractor = ContentSignalExtractor(environment)
            self.domain_extractor = DomainSignalExtractor(environment)

            logger.info(f"HybridReranker initialized for environment: {environment}")

        except ImportError as e:
            logger.warning(f"Signal extractors not available: {e}")
            self.vector_extractor = None
            self.graph_extractor = None
            self.content_extractor = None
            self.domain_extractor = None

    def rerank_results(
        self,
        query: str,
        results: List[Dict[str, Any]],
        config: Optional[RerankingConfig] = None,
        query_plan: Optional[Dict[str, Any]] = None,
        classification: Optional[Classification] = None
    ) -> List[RerankedResult]:
        """
        Rerank search results using multi-signal hybrid approach.

        Args:
            query: Original user query
            results: List of search results to rerank
            config: Reranking configuration (optional)
            query_plan: Query plan from QueryPlanner (optional)
            classification: Query classification (optional)

        Returns:
            List of reranked results with detailed scoring
        """
        start_time = time.perf_counter()

        if not results:
            return []

        config = config or self._get_default_config(classification)

        # Limit results to rerank for performance
        results_to_rerank = results[:config.max_results_to_rerank]

        logger.info(f"Reranking {len(results_to_rerank)} results with strategy: {config.strategy}")

        # Extract signals for all results
        reranked_results = []

        for i, result in enumerate(results_to_rerank):
            result_start_time = time.perf_counter()

            # Extract all signals
            signals = self._extract_signals(
                query, result, config, query_plan, classification
            )

            # Compute final score
            final_score = self._compute_final_score(signals, config)

            result_time_ms = (time.perf_counter() - result_start_time) * 1000

            reranked_result = RerankedResult(
                original_result=result,
                original_rank=i,
                original_score=result.get('score', 0.0),
                final_score=final_score,
                final_rank=0,  # Will be set after sorting
                signals=signals,
                reranking_time_ms=result_time_ms,
                strategy_used=config.strategy
            )

            reranked_results.append(reranked_result)

        # Sort by final score
        reranked_results.sort(key=lambda x: x.final_score, reverse=True)

        # Update final ranks
        for i, result in enumerate(reranked_results):
            result.final_rank = i

        total_time_ms = (time.perf_counter() - start_time) * 1000

        logger.info(
            f"Reranking completed in {total_time_ms:.2f}ms. "
            f"Average per result: {total_time_ms/len(results_to_rerank):.2f}ms"
        )

        return reranked_results

    def _extract_signals(
        self,
        query: str,
        result: Dict[str, Any],
        config: RerankingConfig,
        query_plan: Optional[Dict[str, Any]],
        classification: Optional[Classification]
    ) -> RerankingSignals:
        """Extract all reranking signals for a single result."""

        signals = RerankingSignals()

        # Check cache first
        result_id = result.get('id', str(hash(str(result))))
        cache_key = f"{query}:{result_id}:{config.strategy}"

        if config.enable_signal_caching and cache_key in self.signal_cache:
            return self.signal_cache[cache_key]

        try:
            # Vector similarity signals
            if self.vector_extractor and config.vector_weight > 0:
                vector_signals = self.vector_extractor.extract_signals(
                    query, result, classification
                )
                signals.vector_similarity = vector_signals.get('similarity', 0.0)
                signals.semantic_similarity = vector_signals.get('semantic', 0.0)

            # Graph relationship signals
            if self.graph_extractor and config.graph_weight > 0:
                graph_signals = self.graph_extractor.extract_signals(
                    query, result, query_plan
                )
                signals.graph_relevance = graph_signals.get('relevance', 0.0)
                signals.relationship_score = graph_signals.get('relationships', 0.0)
                signals.cross_reference_boost = graph_signals.get('cross_refs', 0.0)

            # Content feature signals
            if self.content_extractor and config.content_weight > 0:
                content_signals = self.content_extractor.extract_signals(
                    query, result, classification
                )
                signals.content_quality = content_signals.get('quality', 0.0)
                signals.readability_score = content_signals.get('readability', 0.0)
                signals.length_penalty = content_signals.get('length_penalty', 0.0)
                signals.structure_score = content_signals.get('structure', 0.0)

            # Domain-specific TTRPG signals
            if self.domain_extractor and config.domain_weight > 0:
                domain_signals = self.domain_extractor.extract_signals(
                    query, result, classification
                )
                signals.entity_match_score = domain_signals.get('entity_match', 0.0)
                signals.mechanics_relevance = domain_signals.get('mechanics', 0.0)
                signals.rulebook_authority = domain_signals.get('authority', 0.0)

            # Simple metadata signals (computed directly)
            signals.recency_boost = self._compute_recency_boost(result)
            signals.popularity_score = self._compute_popularity_score(result)

        except Exception as e:
            logger.warning(f"Error extracting signals: {e}")

        # Cache the signals
        if config.enable_signal_caching:
            self.signal_cache[cache_key] = signals

        return signals

    def _compute_final_score(
        self,
        signals: RerankingSignals,
        config: RerankingConfig
    ) -> float:
        """Compute final reranking score from all signals."""

        # Vector component
        vector_score = (
            signals.vector_similarity * 0.7 +
            signals.semantic_similarity * 0.3
        )

        # Graph component
        graph_score = (
            signals.graph_relevance * 0.5 +
            signals.relationship_score * 0.3 +
            signals.cross_reference_boost * 0.2
        )

        # Content component
        content_score = (
            signals.content_quality * 0.4 +
            signals.readability_score * 0.2 +
            signals.structure_score * 0.2 +
            max(0, 1.0 - signals.length_penalty) * 0.2
        )

        # Domain component
        domain_score = (
            signals.entity_match_score * 0.4 +
            signals.mechanics_relevance * 0.4 +
            signals.rulebook_authority * 0.2
        )

        # Metadata component
        metadata_score = (
            signals.recency_boost * 0.3 +
            signals.popularity_score * 0.7
        )

        # Weighted final score
        final_score = (
            vector_score * config.vector_weight +
            graph_score * config.graph_weight +
            content_score * config.content_weight +
            domain_score * config.domain_weight +
            metadata_score * config.metadata_weight
        )

        return max(0.0, min(1.0, final_score))

    def _compute_recency_boost(self, result: Dict[str, Any]) -> float:
        """Compute recency boost based on content age."""
        # Simple implementation - can be enhanced
        return 0.5  # Neutral boost for now

    def _compute_popularity_score(self, result: Dict[str, Any]) -> float:
        """Compute popularity score based on usage metrics."""
        # Simple implementation - can be enhanced
        return 0.5  # Neutral score for now

    def _get_default_config(self, classification: Optional[Classification]) -> RerankingConfig:
        """Get default reranking configuration based on query classification."""

        if not classification:
            return RerankingConfig()

        # Adapt weights based on query characteristics
        config = RerankingConfig()

        intent = getattr(classification, 'intent', 'unknown')
        domain = getattr(classification, 'domain', 'general')
        complexity = getattr(classification, 'complexity', 'medium')

        # Adjust strategy based on query type
        if intent == "fact_lookup":
            config.strategy = RerankingStrategy.VECTOR_ONLY
            config.vector_weight = 0.6
            config.content_weight = 0.3

        elif intent == "multi_hop_reasoning":
            config.strategy = RerankingStrategy.GRAPH_ENHANCED
            config.graph_weight = 0.4
            config.vector_weight = 0.3

        elif domain == "ttrpg_rules":
            config.strategy = RerankingStrategy.DOMAIN_AWARE
            config.domain_weight = 0.4
            config.content_weight = 0.3

        elif complexity == "high":
            config.strategy = RerankingStrategy.HYBRID_FULL
            # Use default balanced weights

        return config

    def get_reranking_metrics(self) -> Dict[str, Any]:
        """Get reranking performance metrics."""
        return {
            "cache_size": len(self.signal_cache),
            "environment": self.environment,
            "extractors_available": {
                "vector": self.vector_extractor is not None,
                "graph": self.graph_extractor is not None,
                "content": self.content_extractor is not None,
                "domain": self.domain_extractor is not None
            }
        }

    def clear_cache(self) -> int:
        """Clear signal cache and return number of entries cleared."""
        cache_size = len(self.signal_cache)
        self.signal_cache.clear()
        logger.info(f"Cleared {cache_size} cached signal entries")
        return cache_size