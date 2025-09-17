"""
End-to-end functional tests for query planning integration.
Tests the complete flow from query input to response with planning enabled.
"""
import pytest
import json
import time
from pathlib import Path
from unittest.mock import patch, MagicMock

from src_common.orchestrator.service import rag_ask
from src_common.orchestrator.query_planner import get_planner
from src_common.orchestrator.plan_cache import get_cache


class TestQueryPlanningEndToEnd:
    """
    Test complete query planning integration with the RAG service.
    """

    @pytest.fixture
    def mock_dependencies(self):
        """Mock external dependencies for isolated testing."""
        mocks = {}

        # Mock retrieval to return consistent results
        mocks['retrieve'] = MagicMock()
        mocks['retrieve'].return_value = [
            MagicMock(
                id="chunk_1",
                text="A wizard is a spellcaster who learns magic through study and preparation.",
                source="pathfinder_core.pdf",
                score=0.95,
                metadata={"page": 42, "section": "Classes"}
            )
        ]

        # Mock AEHRL and Persona systems to avoid external dependencies
        mocks['aehrl_evaluator'] = MagicMock()
        mocks['persona_manager'] = MagicMock()

        return mocks

    @pytest.fixture
    def test_environment_setup(self):
        """Set up test environment variables."""
        env_vars = {
            'APP_ENV': 'test',
            'AEHRL_ENABLED': 'false',  # Disable for simpler testing
            'PERSONA_TESTING_ENABLED': 'false'  # Disable for simpler testing
        }
        return env_vars

    def test_query_planning_cache_miss_flow(self, mock_dependencies, test_environment_setup):
        """Test complete flow when query plan is not cached (first request)."""
        with patch.dict('os.environ', test_environment_setup), \
             patch('src_common.orchestrator.service.retrieve', mock_dependencies['retrieve']):

            # Clear any existing cache for clean test
            cache = get_cache("test")
            cache.clear()

            # Prepare test query
            query = "What is a wizard in Pathfinder?"
            payload = {"query": query, "top_k": 3}

            # Make the request
            start_time = time.time()
            response = rag_ask(payload)
            end_time = time.time()

            # Verify response structure
            assert response.status_code == 200
            response_data = json.loads(response.body)

            # Basic response validation
            assert response_data["query"] == query
            assert response_data["environment"] == "test"
            assert "classification" in response_data
            assert "plan" in response_data
            assert "model" in response_data

            # Query planning specific validation
            planning_info = response_data["query_planning"]
            assert planning_info["enabled"] is True
            assert planning_info["plan_cached"] is False  # First request should be cache miss
            assert planning_info["plan_hash"] is not None
            assert planning_info["cache_hit_count"] == 0

            # Verify plan was cached for future use
            planner = get_planner("test")
            cached_plan = planner.cache.get(query)
            assert cached_plan is not None
            assert cached_plan.original_query == query

            # Performance validation - plan generation should be reasonably fast
            execution_time_ms = (end_time - start_time) * 1000
            assert execution_time_ms < 1000  # Should complete within 1 second

    def test_query_planning_cache_hit_flow(self, mock_dependencies, test_environment_setup):
        """Test complete flow when query plan is cached (subsequent request)."""
        with patch.dict('os.environ', test_environment_setup), \
             patch('src_common.orchestrator.service.retrieve', mock_dependencies['retrieve']):

            query = "What spells can a 5th level wizard cast?"
            payload = {"query": query, "top_k": 5}

            # Make first request to populate cache
            first_response = rag_ask(payload)
            first_data = json.loads(first_response.body)

            # Verify first request was cache miss
            assert first_data["query_planning"]["plan_cached"] is False

            # Make second request (should hit cache)
            second_response = rag_ask(payload)
            second_data = json.loads(second_response.body)

            # Verify second request was cache hit
            planning_info = second_data["query_planning"]
            assert planning_info["enabled"] is True
            assert planning_info["plan_cached"] is True  # Should be cache hit
            assert planning_info["cache_hit_count"] == 1  # Hit count incremented

            # Verify same plan hash
            assert (first_data["query_planning"]["plan_hash"] ==
                   second_data["query_planning"]["plan_hash"])

    def test_different_query_types_optimization(self, mock_dependencies, test_environment_setup):
        """Test that different query types generate appropriately optimized plans."""
        with patch.dict('os.environ', test_environment_setup), \
             patch('src_common.orchestrator.service.retrieve', mock_dependencies['retrieve']):

            test_cases = [
                {
                    "query": "What is a fireball spell?",  # Simple fact lookup
                    "expected_intent": "fact_lookup",
                    "expected_complexity": "low"
                },
                {
                    "query": "How do I build an effective wizard character that can handle both combat and utility spells while maintaining good survivability?",  # Complex multi-hop
                    "expected_intent": "multi_hop_reasoning",
                    "expected_complexity": "high"
                },
                {
                    "query": "Write a dramatic scene where a wizard casts fireball",  # Creative
                    "expected_intent": "creative_write",
                    "expected_complexity": "medium"
                }
            ]

            for case in test_cases:
                payload = {"query": case["query"]}
                response = rag_ask(payload)
                response_data = json.loads(response.body)

                # Verify classification matches expectations
                classification = response_data["classification"]
                assert classification["intent"] == case["expected_intent"]
                assert classification["complexity"] == case["expected_complexity"]

                # Verify plan has appropriate optimizations
                plan = response_data["plan"]
                assert "vector_top_k" in plan
                assert isinstance(plan["vector_top_k"], (int, float))

                # Verify planning was used
                assert response_data["query_planning"]["enabled"] is True

    def test_plan_performance_optimization(self, mock_dependencies, test_environment_setup):
        """Test that plans include appropriate performance optimizations."""
        with patch.dict('os.environ', test_environment_setup), \
             patch('src_common.orchestrator.service.retrieve', mock_dependencies['retrieve']):

            # Test urgent query
            urgent_query = "I need help with combat rules quickly!"
            urgent_payload = {"query": urgent_query}

            urgent_response = rag_ask(urgent_payload)
            urgent_data = json.loads(urgent_response.body)

            # Verify performance hints are included
            hints = urgent_data["query_planning"]["performance_hints"]
            assert "priority" in hints
            assert hints["priority"] == "high"
            assert "timeout_ms" in hints

    def test_cache_efficiency_over_time(self, mock_dependencies, test_environment_setup):
        """Test cache efficiency improves with repeated queries."""
        with patch.dict('os.environ', test_environment_setup), \
             patch('src_common.orchestrator.service.retrieve', mock_dependencies['retrieve']):

            # Clear cache for clean test
            cache = get_cache("test")
            cache.clear()

            queries = [
                "What is a spell?",
                "How do I cast spells?",
                "What is a spell?",  # Repeat
                "What spells can wizards cast?",
                "How do I cast spells?",  # Repeat
                "What is a spell?"  # Repeat
            ]

            cache_hits = 0
            total_requests = 0

            for query in queries:
                payload = {"query": query}
                response = rag_ask(payload)
                response_data = json.loads(response.body)

                if response_data["query_planning"]["plan_cached"]:
                    cache_hits += 1
                total_requests += 1

            # Should have some cache hits from repeated queries
            cache_hit_rate = cache_hits / total_requests
            assert cache_hit_rate > 0.3  # At least 30% hit rate with repeated queries

    def test_fallback_behavior_on_planning_failure(self, mock_dependencies, test_environment_setup):
        """Test that system gracefully falls back when planning fails."""
        with patch.dict('os.environ', test_environment_setup), \
             patch('src_common.orchestrator.service.retrieve', mock_dependencies['retrieve']):

            # Mock planner to raise exception
            with patch('src_common.orchestrator.service.get_planner') as mock_get_planner:
                mock_planner = MagicMock()
                mock_planner.get_plan.side_effect = Exception("Planning failed")
                mock_get_planner.return_value = mock_planner

                query = "Test query for fallback"
                payload = {"query": query}

                # Should not crash, should fall back to legacy behavior
                response = rag_ask(payload)
                response_data = json.loads(response.body)

                # Should still return valid response
                assert response.status_code == 200
                assert response_data["query"] == query
                assert "plan" in response_data  # Fallback plan should exist

    def test_environment_isolation(self, mock_dependencies):
        """Test that different environments maintain separate caches."""
        with patch('src_common.orchestrator.service.retrieve', mock_dependencies['retrieve']):

            query = "Environment isolation test query"
            payload = {"query": query}

            # Test in dev environment
            with patch.dict('os.environ', {'APP_ENV': 'dev'}):
                dev_response = rag_ask(payload)
                dev_data = json.loads(dev_response.body)
                dev_hash = dev_data["query_planning"]["plan_hash"]

            # Test in test environment
            with patch.dict('os.environ', {'APP_ENV': 'test'}):
                test_response = rag_ask(payload)
                test_data = json.loads(test_response.body)
                test_hash = test_data["query_planning"]["plan_hash"]

            # Both should have same hash (same query) but separate cache instances
            assert dev_hash == test_hash  # Same query hash
            assert dev_data["environment"] == "dev"
            assert test_data["environment"] == "test"

    def test_metrics_collection(self, mock_dependencies, test_environment_setup):
        """Test that planning metrics are properly collected."""
        with patch.dict('os.environ', test_environment_setup), \
             patch('src_common.orchestrator.service.retrieve', mock_dependencies['retrieve']):

            # Make several requests to generate metrics
            queries = ["Query 1", "Query 2", "Query 1", "Query 3"]

            for query in queries:
                payload = {"query": query}
                rag_ask(payload)

            # Check that planner has metrics
            planner = get_planner("test")
            metrics = planner.get_cache_metrics()

            assert metrics.total_queries > 0
            assert metrics.cache_hit_rate >= 0.0
            assert metrics.cache_size >= 0