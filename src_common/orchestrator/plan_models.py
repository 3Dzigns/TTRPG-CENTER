"""
Query Plan Data Structures and Models
Defines the core data structures for query planning and caching.
"""
from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass, asdict
from typing import Dict, Any, Optional

from .classifier import Classification


@dataclass
class QueryPlan:
    """
    Represents an optimized execution plan for a query.

    This plan includes the retrieval strategy, model configuration,
    and performance hints to optimize query execution.
    """

    # Cache and identification
    query_hash: str  # SHA-256 hash for exact matching
    original_query: str  # For debugging and logging

    # Classification from existing classifier
    classification: Classification

    # Enhanced retrieval strategy (extends existing policies)
    retrieval_strategy: Dict[str, Any]

    # Model routing configuration
    model_config: Dict[str, Any]

    # Performance optimization hints
    performance_hints: Dict[str, Any]

    # Graph expansion metadata
    graph_expansion: Optional[Dict[str, Any]] = None

    # Reranking configuration metadata
    reranking_config: Optional[Dict[str, Any]] = None

    # Provenance tracking configuration
    provenance_config: Optional[Dict[str, Any]] = None

    # Evaluation gate configuration
    eval_config: Optional[Dict[str, Any]] = None

    # Cache metadata
    cache_ttl: int = 3600  # Time-to-live in seconds
    created_at: float = 0.0  # Unix timestamp
    hit_count: int = 0  # Number of times this plan was reused

    @classmethod
    def create_from_query(
        cls,
        query: str,
        classification: Classification,
        retrieval_strategy: Dict[str, Any],
        model_config: Dict[str, Any],
        performance_hints: Optional[Dict[str, Any]] = None,
        graph_expansion: Optional[Dict[str, Any]] = None,
        reranking_config: Optional[Dict[str, Any]] = None,
        provenance_config: Optional[Dict[str, Any]] = None,
        eval_config: Optional[Dict[str, Any]] = None,
        cache_ttl: int = 3600
    ) -> QueryPlan:
        """Create a new QueryPlan from query components."""
        query_hash = cls._hash_query(query)

        return cls(
            query_hash=query_hash,
            original_query=query,
            classification=classification,
            retrieval_strategy=retrieval_strategy,
            model_config=model_config,
            performance_hints=performance_hints or {},
            graph_expansion=graph_expansion,
            reranking_config=reranking_config,
            provenance_config=provenance_config,
            eval_config=eval_config,
            cache_ttl=cache_ttl,
            created_at=time.time(),
            hit_count=0
        )

    @staticmethod
    def _hash_query(query: str) -> str:
        """Generate a SHA-256 hash for exact query matching."""
        return hashlib.sha256(query.strip().encode('utf-8')).hexdigest()

    def is_expired(self) -> bool:
        """Check if this plan has exceeded its TTL."""
        return (time.time() - self.created_at) > self.cache_ttl

    def increment_hit_count(self) -> None:
        """Increment the hit count when plan is reused."""
        self.hit_count += 1

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> QueryPlan:
        """Create QueryPlan from dictionary (for cache loading)."""
        return cls(**data)


@dataclass
class PlanMetrics:
    """
    Metrics for tracking query plan performance and cache efficiency.
    """

    # Cache metrics
    cache_hit_rate: float
    cache_miss_rate: float
    total_queries: int
    cache_size: int

    # Performance metrics
    avg_plan_generation_time_ms: float
    avg_execution_time_savings_ms: float

    # Plan effectiveness
    successful_plans: int
    failed_plans: int
    fallback_used: int

    # Timestamp
    recorded_at: float

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for logging."""
        return asdict(self)


@dataclass
class PlanGenerationContext:
    """
    Context information for plan generation, including environment
    and configuration settings.
    """

    environment: str  # dev, test, prod
    max_vector_k: int = 50
    max_graph_depth: int = 3
    enable_reranking: bool = True
    enable_graph_retrieval: bool = True

    # Graph expansion settings
    enable_graph_expansion: bool = True
    graph_expansion_strategy: str = "hybrid"  # alias, graph, cross_ref, hybrid
    max_graph_expansions: int = 10
    min_expansion_confidence: float = 0.3

    # Reranking settings
    enable_hybrid_reranking: bool = True
    reranking_strategy: str = "hybrid_full"  # vector_only, graph_enhanced, domain_aware, hybrid_full
    max_results_to_rerank: int = 20
    reranking_timeout_ms: int = 100

    # Provenance tracking settings
    enable_provenance_tracking: bool = True
    track_query_processing: bool = True
    track_retrieval: bool = True
    track_reranking: bool = True
    track_answer_generation: bool = True
    provenance_detail_level: str = "full"  # minimal, standard, full
    max_provenance_time_ms: int = 50

    # Evaluation gate settings
    enable_evaluation_gate: bool = True
    evaluation_strategy: str = "comprehensive"  # fast, comprehensive, domain_focused, accuracy_first
    minimum_overall_quality: float = 0.6
    minimum_accuracy_score: float = 0.7
    max_evaluation_time_ms: int = 50
    enable_evaluation_caching: bool = True

    # Static heuristic weights
    complexity_multiplier: Dict[str, float] = None
    intent_preferences: Dict[str, Dict[str, Any]] = None

    def __post_init__(self):
        if self.complexity_multiplier is None:
            self.complexity_multiplier = {
                "low": 1.0,
                "medium": 1.5,
                "high": 2.0
            }

        if self.intent_preferences is None:
            self.intent_preferences = {
                "fact_lookup": {"prefer_vector": True, "graph_depth": 0},
                "multi_hop_reasoning": {"prefer_graph": True, "graph_depth": 2},
                "procedural_howto": {"prefer_vector": True, "rerank": True},
                "creative_write": {"prefer_vector": False, "graph_depth": 1},
                "summarize": {"prefer_vector": True, "top_k_boost": 1.5}
            }