"""
Unit tests for query planner implementation.
"""
import pytest
from unittest.mock import patch, MagicMock

from src_common.orchestrator.query_planner import QueryPlanner, get_planner
from src_common.orchestrator.plan_models import QueryPlan, PlanGenerationContext
from src_common.orchestrator.classifier import Classification


class TestQueryPlanner:
    """Test QueryPlanner core functionality."""

    @pytest.fixture
    def mock_cache(self):
        """Mock cache for testing."""
        cache = MagicMock()
        cache.get.return_value = None  # Default to cache miss
        return cache

    @pytest.fixture
    def planner_with_mock_cache(self, mock_cache):
        """Create planner with mocked cache."""
        with patch('src_common.orchestrator.query_planner.get_cache', return_value=mock_cache):
            planner = QueryPlanner("test")
            return planner

    def test_planner_initialization(self):
        """Test planner initialization with environment setup."""
        with patch.dict('os.environ', {'APP_ENV': 'dev'}):
            planner = QueryPlanner()
            assert planner.environment == "dev"
            assert isinstance(planner.context, PlanGenerationContext)

    def test_get_plan_cache_hit(self, planner_with_mock_cache, mock_cache):
        """Test plan retrieval when cache hit occurs."""
        planner = planner_with_mock_cache
        query = "What is a fireball spell?"

        # Mock cache hit
        cached_plan = QueryPlan.create_from_query(
            query=query,
            classification={
                "intent": "fact_lookup",
                "domain": "ttrpg_rules",
                "complexity": "low",
                "needs_tools": True,
                "confidence": 0.8
            },
            retrieval_strategy={"vector_top_k": 5},
            model_config={"model": "gpt-4"}
        )
        mock_cache.get.return_value = cached_plan

        result = planner.get_plan(query)

        assert result is cached_plan
        mock_cache.get.assert_called_once_with(query)
        mock_cache.put.assert_not_called()  # Should not cache again

    def test_get_plan_cache_miss(self, planner_with_mock_cache, mock_cache):
        """Test plan generation when cache miss occurs."""
        planner = planner_with_mock_cache
        query = "How do I cast a spell?"

        # Mock cache miss
        mock_cache.get.return_value = None

        # Mock dependencies
        with patch('src_common.orchestrator.query_planner.classify_query') as mock_classify, \
             patch('src_common.orchestrator.query_planner.load_policies') as mock_policies, \
             patch('src_common.orchestrator.query_planner.choose_plan') as mock_choose, \
             patch('src_common.orchestrator.query_planner.pick_model') as mock_model:

            mock_classify.return_value = {
                "intent": "procedural_howto",
                "domain": "ttrpg_rules",
                "complexity": "medium",
                "needs_tools": True,
                "confidence": 0.9
            }
            mock_policies.return_value = {}
            mock_choose.return_value = {"vector_top_k": 8, "rerank": "sbert"}
            mock_model.return_value = {"model": "gpt-4", "max_tokens": 2000}

            result = planner.get_plan(query)

            assert isinstance(result, QueryPlan)
            assert result.original_query == query
            mock_cache.put.assert_called_once()  # Should cache the new plan

    def test_generate_retrieval_strategy_fact_lookup(self, planner_with_mock_cache):
        """Test retrieval strategy generation for fact lookup queries."""
        planner = planner_with_mock_cache

        classification: Classification = {
            "intent": "fact_lookup",
            "domain": "ttrpg_rules",
            "complexity": "low",
            "needs_tools": True,
            "confidence": 0.8
        }

        with patch('src_common.orchestrator.query_planner.load_policies') as mock_policies, \
             patch('src_common.orchestrator.query_planner.choose_plan') as mock_choose:

            mock_policies.return_value = {}
            mock_choose.return_value = {"vector_top_k": 5}

            strategy = planner._generate_retrieval_strategy(classification, "What is a spell?")

            # Fact lookup should optimize for precise vector search
            assert strategy["graph_depth"] == 0  # No graph for low complexity
            assert "vector_top_k" in strategy
            assert strategy.get("filters", {}).get("system") == "PF2E"

    def test_generate_retrieval_strategy_multi_hop(self, planner_with_mock_cache):
        """Test retrieval strategy generation for multi-hop reasoning."""
        planner = planner_with_mock_cache

        classification: Classification = {
            "intent": "multi_hop_reasoning",
            "domain": "ttrpg_rules",
            "complexity": "high",
            "needs_tools": True,
            "confidence": 0.85
        }

        with patch('src_common.orchestrator.query_planner.load_policies') as mock_policies, \
             patch('src_common.orchestrator.query_planner.choose_plan') as mock_choose:

            mock_policies.return_value = {}
            mock_choose.return_value = {"vector_top_k": 8, "graph_depth": 1}

            strategy = planner._generate_retrieval_strategy(classification, "Complex reasoning query")

            # Multi-hop should use graph traversal
            assert strategy["graph_depth"] >= 1
            assert strategy["rerank"] == "sbert"

    def test_generate_retrieval_strategy_creative_write(self, planner_with_mock_cache):
        """Test retrieval strategy generation for creative writing."""
        planner = planner_with_mock_cache

        classification: Classification = {
            "intent": "creative_write",
            "domain": "ttrpg_lore",
            "complexity": "medium",
            "needs_tools": True,
            "confidence": 0.7
        }

        with patch('src_common.orchestrator.query_planner.load_policies') as mock_policies, \
             patch('src_common.orchestrator.query_planner.choose_plan') as mock_choose:

            mock_policies.return_value = {}
            mock_choose.return_value = {"vector_top_k": 6}

            strategy = planner._generate_retrieval_strategy(classification, "Write a story")

            # Creative writing should use MMR for diversity
            assert strategy["rerank"] == "mmr"
            assert strategy["vector_top_k"] >= 6  # Increased for diversity

    def test_has_multiple_entities_detection(self, planner_with_mock_cache):
        """Test detection of multi-entity queries."""
        planner = planner_with_mock_cache

        # Queries with multiple entities
        multi_entity_queries = [
            "Compare wizards and sorcerers",
            "Difference between fireballs and lightning bolts",
            "Spells that work with metamagic",
            "Classes including ranger and paladin"
        ]

        # Single entity queries
        single_entity_queries = [
            "What is a wizard?",
            "How do fireballs work?",
            "Spell description for magic missile"
        ]

        for query in multi_entity_queries:
            assert planner._has_multiple_entities(query), f"Should detect multiple entities in: {query}"

        for query in single_entity_queries:
            assert not planner._has_multiple_entities(query), f"Should detect single entity in: {query}"

    def test_time_sensitive_query_detection(self, planner_with_mock_cache):
        """Test detection of time-sensitive queries."""
        planner = planner_with_mock_cache

        urgent_queries = [
            "I need this quickly",
            "Urgent spell help",
            "Fast answer needed",
            "Emergency combat rules"
        ]

        normal_queries = [
            "What is a spell?",
            "How do I create a character?",
            "Best strategies for combat"
        ]

        for query in urgent_queries:
            assert planner._is_time_sensitive_query(query), f"Should detect urgency in: {query}"

        for query in normal_queries:
            assert not planner._is_time_sensitive_query(query), f"Should not detect urgency in: {query}"

    def test_cache_ttl_calculation(self, planner_with_mock_cache):
        """Test TTL calculation based on query characteristics."""
        planner = planner_with_mock_cache

        # Rules queries should have longer TTL
        rules_classification: Classification = {
            "intent": "fact_lookup",
            "domain": "ttrpg_rules",
            "complexity": "low",
            "needs_tools": True,
            "confidence": 0.8
        }
        rules_ttl = planner._calculate_cache_ttl(rules_classification)
        assert rules_ttl == 3600 * 4  # 4 hours

        # Creative queries should have shorter TTL
        creative_classification: Classification = {
            "intent": "creative_write",
            "domain": "ttrpg_lore",
            "complexity": "high",
            "needs_tools": True,
            "confidence": 0.7
        }
        creative_ttl = planner._calculate_cache_ttl(creative_classification)
        assert creative_ttl == 3600 // 2  # 30 minutes

    def test_model_config_generation(self, planner_with_mock_cache):
        """Test model configuration generation with plan awareness."""
        planner = planner_with_mock_cache

        classification: Classification = {
            "intent": "fact_lookup",
            "domain": "ttrpg_rules",
            "complexity": "medium",
            "needs_tools": True,
            "confidence": 0.8
        }

        # Simple retrieval strategy
        simple_strategy = {"vector_top_k": 5, "graph_depth": 0}

        # Complex retrieval strategy
        complex_strategy = {"vector_top_k": 20, "graph_depth": 2}

        with patch('src_common.orchestrator.query_planner.pick_model') as mock_model:
            mock_model.return_value = {"model": "gpt-3.5-turbo", "max_tokens": 2000}

            # Simple strategy should use base model
            simple_config = planner._generate_model_config(classification, simple_strategy)
            assert simple_config["model"] == "gpt-3.5-turbo"

            # Complex strategy should upgrade model
            complex_config = planner._generate_model_config(classification, complex_strategy)
            assert complex_config["model"] == "gpt-4"

    def test_performance_hints_generation(self, planner_with_mock_cache):
        """Test performance hints generation."""
        planner = planner_with_mock_cache

        # Simple fact lookup
        simple_classification: Classification = {
            "intent": "fact_lookup",
            "domain": "ttrpg_rules",
            "complexity": "low",
            "needs_tools": True,
            "confidence": 0.8
        }

        simple_hints = planner._generate_performance_hints(simple_classification, "What is a spell?")
        assert simple_hints["enable_early_termination"] is True
        assert simple_hints["parallelizable_retrieval"] is True

        # Complex multi-hop
        complex_classification: Classification = {
            "intent": "multi_hop_reasoning",
            "domain": "ttrpg_rules",
            "complexity": "high",
            "needs_tools": True,
            "confidence": 0.9
        }

        complex_hints = planner._generate_performance_hints(complex_classification, "Complex reasoning")
        assert complex_hints["cache_intermediate_results"] is True

        # Time-sensitive query
        urgent_hints = planner._generate_performance_hints(simple_classification, "I need this quickly")
        assert urgent_hints["priority"] == "high"
        assert urgent_hints["timeout_ms"] == 30000

    def test_cache_management_methods(self, planner_with_mock_cache, mock_cache):
        """Test cache management functionality."""
        planner = planner_with_mock_cache

        # Test metrics
        mock_cache.get_metrics.return_value = MagicMock()
        metrics = planner.get_cache_metrics()
        mock_cache.get_metrics.assert_called_once()

        # Test clear cache
        mock_cache.clear.return_value = 5
        cleared = planner.clear_cache()
        assert cleared == 5
        mock_cache.clear.assert_called_once()

        # Test cleanup
        mock_cache.cleanup_expired.return_value = 3
        cleaned = planner.cleanup_expired_plans()
        assert cleaned == 3
        mock_cache.cleanup_expired.assert_called_once()


class TestGlobalPlannerManagement:
    """Test global planner instance management."""

    def test_get_planner_singleton(self):
        """Test that get_planner returns singleton instances per environment."""
        with patch.dict('os.environ', {'APP_ENV': 'test'}):
            planner1 = get_planner("dev")
            planner2 = get_planner("dev")
            planner3 = get_planner("prod")

            # Same environment should return same instance
            assert planner1 is planner2

            # Different environment should return different instance
            assert planner1 is not planner3

    def test_get_planner_default_environment(self):
        """Test planner creation with default environment."""
        with patch.dict('os.environ', {'APP_ENV': 'production'}):
            planner = get_planner()
            assert planner.environment == "production"