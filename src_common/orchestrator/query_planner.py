"""
Query Planner Implementation
Generates optimized execution plans for queries using static heuristics.
"""
from __future__ import annotations

import os
import time
from typing import Dict, Any, Optional

from ..ttrpg_logging import get_logger
from .classifier import Classification, classify_query
from .plan_models import QueryPlan, PlanGenerationContext
from .plan_cache import get_cache
from .policies import load_policies, choose_plan
from .router import pick_model

logger = get_logger(__name__)


class QueryPlanner:
    """
    Intelligent query planner that generates optimized execution plans.

    Uses static heuristics to determine the best retrieval strategy,
    model configuration, and performance optimizations for each query.
    """

    def __init__(self, environment: str = None):
        self.environment = environment or os.getenv("APP_ENV", "dev")
        self.cache = get_cache(self.environment)
        self.context = PlanGenerationContext(environment=self.environment)

        logger.info(f"QueryPlanner initialized for environment: {self.environment}")

    def get_plan(self, query: str) -> QueryPlan:
        """
        Get or generate an optimized execution plan for a query.

        Args:
            query: The user query string

        Returns:
            QueryPlan with optimized retrieval and model configuration
        """
        start_time = time.time()

        # Try cache first (exact match)
        cached_plan = self.cache.get(query)
        if cached_plan:
            generation_time_ms = (time.time() - start_time) * 1000
            logger.debug(f"Plan retrieved from cache in {generation_time_ms:.2f}ms")
            return cached_plan

        # Generate new plan
        plan = self._generate_plan(query)

        # Cache the plan
        self.cache.put(query, plan)

        generation_time_ms = (time.time() - start_time) * 1000
        logger.info(f"Plan generated and cached in {generation_time_ms:.2f}ms")

        return plan

    def _generate_plan(self, query: str) -> QueryPlan:
        """
        Generate a new execution plan using static heuristics.

        Args:
            query: The user query string

        Returns:
            Newly generated QueryPlan
        """
        # 1. Classify the query using existing classifier
        classification = classify_query(query)

        # 2. Generate enhanced retrieval strategy
        retrieval_strategy = self._generate_retrieval_strategy(classification, query)

        # 3. Generate model configuration
        model_config = self._generate_model_config(classification, retrieval_strategy)

        # 4. Generate performance hints
        performance_hints = self._generate_performance_hints(classification, query)

        # 5. Create the plan
        plan = QueryPlan.create_from_query(
            query=query,
            classification=classification,
            retrieval_strategy=retrieval_strategy,
            model_config=model_config,
            performance_hints=performance_hints,
            cache_ttl=self._calculate_cache_ttl(classification)
        )

        return plan

    def _generate_retrieval_strategy(self, classification: Classification, query: str) -> Dict[str, Any]:
        """
        Generate optimized retrieval strategy based on classification and static heuristics.
        """
        # Start with existing policy-based plan
        policies = load_policies()
        base_plan = choose_plan(policies, classification)

        # Apply static heuristics for optimization
        enhanced_plan = base_plan.copy()

        intent = classification["intent"]
        complexity = classification["complexity"]
        domain = classification["domain"]

        # Intent-based optimizations
        if intent == "fact_lookup":
            # Fact lookups benefit from precise vector search
            enhanced_plan["vector_top_k"] = min(
                enhanced_plan.get("vector_top_k", 5) * self.context.complexity_multiplier[complexity],
                self.context.max_vector_k
            )
            # Disable graph search for simple facts unless complexity is high
            if complexity == "low":
                enhanced_plan["graph_depth"] = 0

        elif intent == "multi_hop_reasoning":
            # Multi-hop queries need graph traversal
            enhanced_plan["graph_depth"] = min(
                enhanced_plan.get("graph_depth", 1) + (1 if complexity == "high" else 0),
                self.context.max_graph_depth
            )
            enhanced_plan["rerank"] = "sbert"  # Better semantic understanding

        elif intent == "procedural_howto":
            # Procedural queries need ordered, relevant results
            enhanced_plan["rerank"] = "sbert"
            enhanced_plan["vector_top_k"] = min(
                enhanced_plan.get("vector_top_k", 8) * 1.5,
                self.context.max_vector_k
            )

        elif intent == "creative_write":
            # Creative queries need diverse, inspirational content
            enhanced_plan["vector_top_k"] = min(
                enhanced_plan.get("vector_top_k", 6) * 2,
                self.context.max_vector_k
            )
            enhanced_plan["rerank"] = "mmr"  # Maximize marginal relevance for diversity

        elif intent == "summarize":
            # Summarization needs comprehensive coverage
            enhanced_plan["vector_top_k"] = min(
                enhanced_plan.get("vector_top_k", 10) * 1.5,
                self.context.max_vector_k
            )

        # Domain-specific optimizations
        if domain == "ttrpg_rules":
            # Rules queries need precise, authoritative sources
            enhanced_plan["filters"] = enhanced_plan.get("filters", {})
            enhanced_plan["filters"]["system"] = "PF2E"  # Default to Pathfinder 2E
            enhanced_plan["rerank"] = "sbert"  # Precise semantic matching

        elif domain == "ttrpg_lore":
            # Lore queries can benefit from broader search
            enhanced_plan["expand"] = enhanced_plan.get("expand", [])
            if "lore_connections" not in enhanced_plan["expand"]:
                enhanced_plan["expand"].append("lore_connections")

        # Query length and complexity heuristics
        query_length = len(query.split())
        if query_length > 20:
            # Long queries may need more comprehensive search
            enhanced_plan["vector_top_k"] = min(
                enhanced_plan.get("vector_top_k", 8) * 1.3,
                self.context.max_vector_k
            )

        # Entity detection heuristics
        if self._has_multiple_entities(query):
            # Multi-entity queries benefit from graph traversal
            enhanced_plan["graph_depth"] = min(
                enhanced_plan.get("graph_depth", 0) + 1,
                self.context.max_graph_depth
            )

        return enhanced_plan

    def _generate_model_config(self, classification: Classification, retrieval_strategy: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate model configuration using existing router with plan awareness.
        """
        # Use existing model routing as base
        base_config = pick_model(classification, retrieval_strategy)

        # Apply plan-aware enhancements
        enhanced_config = base_config.copy()

        # Adjust model selection based on retrieval complexity
        graph_depth = retrieval_strategy.get("graph_depth", 0)
        vector_top_k = retrieval_strategy.get("vector_top_k", 5)

        if graph_depth > 1 or vector_top_k > 15:
            # Complex retrieval may need more capable model
            if enhanced_config.get("model") == "gpt-3.5-turbo":
                enhanced_config["model"] = "gpt-4"

        # Adjust context window based on expected content volume
        expected_tokens = self._estimate_content_tokens(retrieval_strategy)
        if expected_tokens > 8000:
            enhanced_config["max_tokens"] = min(enhanced_config.get("max_tokens", 2000) * 1.5, 4000)

        return enhanced_config

    def _generate_performance_hints(self, classification: Classification, query: str) -> Dict[str, Any]:
        """
        Generate performance optimization hints for query execution.
        """
        hints = {
            "parallelizable_retrieval": True,
            "cache_intermediate_results": False,
            "enable_early_termination": False,
            "prefetch_related": False
        }

        intent = classification["intent"]
        complexity = classification["complexity"]

        # Enable caching for expensive operations
        if complexity == "high" or intent == "multi_hop_reasoning":
            hints["cache_intermediate_results"] = True

        # Enable early termination for simple fact lookups
        if intent == "fact_lookup" and complexity == "low":
            hints["enable_early_termination"] = True

        # Enable prefetching for known patterns
        if intent == "procedural_howto":
            hints["prefetch_related"] = True

        # Query-specific hints
        if self._is_time_sensitive_query(query):
            hints["priority"] = "high"
            hints["timeout_ms"] = 30000  # 30 seconds max
        else:
            hints["timeout_ms"] = 60000  # 60 seconds default

        return hints

    def _calculate_cache_ttl(self, classification: Classification) -> int:
        """
        Calculate appropriate cache TTL based on query characteristics.
        """
        base_ttl = 3600  # 1 hour default

        # Stable content (rules) can be cached longer
        if classification["domain"] == "ttrpg_rules":
            return base_ttl * 4  # 4 hours

        # Simple fact lookups are stable
        if classification["intent"] == "fact_lookup" and classification["complexity"] == "low":
            return base_ttl * 2  # 2 hours

        # Creative and complex queries may change more often
        if classification["intent"] == "creative_write" or classification["complexity"] == "high":
            return base_ttl // 2  # 30 minutes

        return base_ttl

    def _has_multiple_entities(self, query: str) -> bool:
        """
        Heuristic to detect queries that reference multiple entities.
        """
        entity_indicators = [
            " and ", " with ", " vs ", " versus ", " compared to ",
            " between ", " among ", " including "
        ]
        return any(indicator in query.lower() for indicator in entity_indicators)

    def _is_time_sensitive_query(self, query: str) -> bool:
        """
        Detect queries that might be time-sensitive.
        """
        time_indicators = [
            "urgent", "quickly", "fast", "now", "immediate",
            "asap", "emergency", "critical"
        ]
        return any(indicator in query.lower() for indicator in time_indicators)

    def _estimate_content_tokens(self, retrieval_strategy: Dict[str, Any]) -> int:
        """
        Estimate total content tokens based on retrieval strategy.
        """
        # Rough estimation: 100 tokens per chunk average
        vector_tokens = retrieval_strategy.get("vector_top_k", 5) * 100
        graph_depth = retrieval_strategy.get("graph_depth", 0)
        graph_tokens = graph_depth * 200  # Graph traversal adds more content

        return vector_tokens + graph_tokens

    def get_cache_metrics(self):
        """Get current cache performance metrics."""
        return self.cache.get_metrics()

    def clear_cache(self) -> int:
        """Clear the query plan cache."""
        return self.cache.clear()

    def cleanup_expired_plans(self) -> int:
        """Remove expired plans from cache."""
        return self.cache.cleanup_expired()


# Global planner instance per environment
_planner_instances: Dict[str, QueryPlanner] = {}


def get_planner(environment: str = None) -> QueryPlanner:
    """
    Get or create a query planner instance for the specified environment.

    Args:
        environment: Environment name (dev/test/prod)

    Returns:
        QueryPlanner instance for the environment
    """
    env = environment or os.getenv("APP_ENV", "dev")

    if env not in _planner_instances:
        _planner_instances[env] = QueryPlanner(env)
    return _planner_instances[env]