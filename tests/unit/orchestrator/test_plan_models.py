"""
Unit tests for query plan data structures and models.
"""
import pytest
import time
from unittest.mock import patch

from src_common.orchestrator.plan_models import (
    QueryPlan, PlanMetrics, PlanGenerationContext
)
from src_common.orchestrator.classifier import Classification


class TestQueryPlan:
    """Test QueryPlan data structure and methods."""

    def test_create_from_query(self):
        """Test creating a QueryPlan from query components."""
        query = "What spells can a 5th level wizard cast?"
        classification: Classification = {
            "intent": "fact_lookup",
            "domain": "ttrpg_rules",
            "complexity": "medium",
            "needs_tools": True,
            "confidence": 0.85
        }
        retrieval_strategy = {"vector_top_k": 8, "rerank": "sbert"}
        model_config = {"model": "gpt-4", "max_tokens": 2000}

        plan = QueryPlan.create_from_query(
            query=query,
            classification=classification,
            retrieval_strategy=retrieval_strategy,
            model_config=model_config
        )

        assert plan.original_query == query
        assert plan.classification == classification
        assert plan.retrieval_strategy == retrieval_strategy
        assert plan.model_config == model_config
        assert plan.cache_ttl == 3600  # default
        assert plan.hit_count == 0
        assert len(plan.query_hash) == 64  # SHA-256 hash length

    def test_hash_query_consistency(self):
        """Test that query hashing is consistent."""
        query1 = "What is a fireball spell?"
        query2 = "What is a fireball spell?"  # identical
        query3 = " What is a fireball spell? "  # with whitespace

        hash1 = QueryPlan._hash_query(query1)
        hash2 = QueryPlan._hash_query(query2)
        hash3 = QueryPlan._hash_query(query3)

        assert hash1 == hash2  # identical queries have same hash
        assert hash1 == hash3  # whitespace is stripped

    def test_is_expired(self):
        """Test TTL expiration logic."""
        query = "test query"
        classification: Classification = {
            "intent": "fact_lookup",
            "domain": "ttrpg_rules",
            "complexity": "low",
            "needs_tools": True,
            "confidence": 0.8
        }

        # Create plan with 1 second TTL
        plan = QueryPlan.create_from_query(
            query=query,
            classification=classification,
            retrieval_strategy={},
            model_config={},
            cache_ttl=1
        )

        assert not plan.is_expired()  # Should not be expired immediately

        # Mock time to simulate passage of time
        with patch('time.time', return_value=plan.created_at + 2):
            assert plan.is_expired()  # Should be expired after TTL

    def test_increment_hit_count(self):
        """Test hit count tracking."""
        plan = QueryPlan.create_from_query(
            query="test",
            classification={"intent": "fact_lookup", "domain": "unknown",
                          "complexity": "low", "needs_tools": False, "confidence": 0.5},
            retrieval_strategy={},
            model_config={}
        )

        assert plan.hit_count == 0

        plan.increment_hit_count()
        assert plan.hit_count == 1

        plan.increment_hit_count()
        assert plan.hit_count == 2

    def test_serialization(self):
        """Test dictionary serialization and deserialization."""
        original_plan = QueryPlan.create_from_query(
            query="test query",
            classification={"intent": "fact_lookup", "domain": "ttrpg_rules",
                          "complexity": "medium", "needs_tools": True, "confidence": 0.9},
            retrieval_strategy={"vector_top_k": 5},
            model_config={"model": "gpt-4"},
            performance_hints={"cache_intermediate": True}
        )

        # Serialize to dict
        plan_dict = original_plan.to_dict()
        assert isinstance(plan_dict, dict)
        assert plan_dict["original_query"] == "test query"
        assert plan_dict["retrieval_strategy"]["vector_top_k"] == 5

        # Deserialize from dict
        restored_plan = QueryPlan.from_dict(plan_dict)
        assert restored_plan.original_query == original_plan.original_query
        assert restored_plan.query_hash == original_plan.query_hash
        assert restored_plan.classification == original_plan.classification
        assert restored_plan.retrieval_strategy == original_plan.retrieval_strategy
        assert restored_plan.model_config == original_plan.model_config


class TestPlanMetrics:
    """Test PlanMetrics data structure."""

    def test_metrics_creation(self):
        """Test creating metrics with all fields."""
        metrics = PlanMetrics(
            cache_hit_rate=0.75,
            cache_miss_rate=0.25,
            total_queries=100,
            cache_size=50,
            avg_plan_generation_time_ms=45.5,
            avg_execution_time_savings_ms=125.0,
            successful_plans=75,
            failed_plans=5,
            fallback_used=10,
            recorded_at=time.time()
        )

        assert metrics.cache_hit_rate == 0.75
        assert metrics.total_queries == 100
        assert metrics.successful_plans == 75

    def test_metrics_serialization(self):
        """Test metrics dictionary conversion."""
        metrics = PlanMetrics(
            cache_hit_rate=0.8,
            cache_miss_rate=0.2,
            total_queries=50,
            cache_size=25,
            avg_plan_generation_time_ms=30.0,
            avg_execution_time_savings_ms=100.0,
            successful_plans=40,
            failed_plans=2,
            fallback_used=3,
            recorded_at=1234567890.0
        )

        metrics_dict = metrics.to_dict()
        assert isinstance(metrics_dict, dict)
        assert metrics_dict["cache_hit_rate"] == 0.8
        assert metrics_dict["total_queries"] == 50


class TestPlanGenerationContext:
    """Test PlanGenerationContext configuration."""

    def test_default_initialization(self):
        """Test context with default values."""
        context = PlanGenerationContext(environment="dev")

        assert context.environment == "dev"
        assert context.max_vector_k == 50
        assert context.max_graph_depth == 3
        assert context.enable_reranking is True
        assert context.enable_graph_retrieval is True

        # Check default complexity multipliers
        assert context.complexity_multiplier["low"] == 1.0
        assert context.complexity_multiplier["medium"] == 1.5
        assert context.complexity_multiplier["high"] == 2.0

        # Check default intent preferences
        assert "fact_lookup" in context.intent_preferences
        assert context.intent_preferences["fact_lookup"]["prefer_vector"] is True

    def test_custom_initialization(self):
        """Test context with custom values."""
        custom_multipliers = {"low": 0.8, "medium": 1.2, "high": 1.8}
        custom_preferences = {"fact_lookup": {"prefer_vector": False, "graph_depth": 1}}

        context = PlanGenerationContext(
            environment="test",
            max_vector_k=25,
            complexity_multiplier=custom_multipliers,
            intent_preferences=custom_preferences
        )

        assert context.environment == "test"
        assert context.max_vector_k == 25
        assert context.complexity_multiplier == custom_multipliers
        assert context.intent_preferences == custom_preferences


@pytest.fixture
def sample_classification():
    """Fixture providing a sample classification."""
    return Classification({
        "intent": "fact_lookup",
        "domain": "ttrpg_rules",
        "complexity": "medium",
        "needs_tools": True,
        "confidence": 0.85
    })


@pytest.fixture
def sample_query_plan(sample_classification):
    """Fixture providing a sample query plan."""
    return QueryPlan.create_from_query(
        query="What are the damage dice for a longsword?",
        classification=sample_classification,
        retrieval_strategy={"vector_top_k": 5, "rerank": "sbert"},
        model_config={"model": "gpt-4", "max_tokens": 1500},
        performance_hints={"enable_early_termination": True}
    )