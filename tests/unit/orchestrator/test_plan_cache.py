"""
Unit tests for query plan cache implementation.
"""
import pytest
import json
import time
import tempfile
import shutil
from pathlib import Path
from unittest.mock import patch, MagicMock

from src_common.orchestrator.plan_cache import QueryPlanCache, get_cache
from src_common.orchestrator.plan_models import QueryPlan


class TestQueryPlanCache:
    """Test QueryPlanCache behavior and functionality."""

    @pytest.fixture
    def temp_cache_dir(self):
        """Create a temporary directory for cache testing."""
        temp_dir = tempfile.mkdtemp()
        yield Path(temp_dir)
        shutil.rmtree(temp_dir)

    @pytest.fixture
    def cache_with_temp_dir(self, temp_cache_dir):
        """Create a cache instance with temporary directory."""
        with patch.object(QueryPlanCache, '__init__', lambda self, env: None):
            cache = QueryPlanCache.__new__(QueryPlanCache)
            cache.environment = "test"
            cache.cache_dir = temp_cache_dir / "query_plans"
            cache.cache_dir.mkdir(parents=True, exist_ok=True)
            cache._metrics = {"hits": 0, "misses": 0, "evictions": 0, "total_queries": 0}
            cache._lock = MagicMock()
            cache._lock.__enter__ = MagicMock(return_value=MagicMock())
            cache._lock.__exit__ = MagicMock(return_value=None)
            return cache

    @pytest.fixture
    def sample_plan(self):
        """Create a sample query plan for testing."""
        return QueryPlan.create_from_query(
            query="What spells can wizards cast?",
            classification={
                "intent": "fact_lookup",
                "domain": "ttrpg_rules",
                "complexity": "medium",
                "needs_tools": True,
                "confidence": 0.8
            },
            retrieval_strategy={"vector_top_k": 8, "rerank": "sbert"},
            model_config={"model": "gpt-4", "max_tokens": 2000}
        )

    def test_cache_initialization(self):
        """Test cache initialization with environment setup."""
        with patch.dict('os.environ', {'APP_ENV': 'test'}):
            cache = QueryPlanCache()
            assert cache.environment == "test"
            assert "test" in str(cache.cache_dir)

    def test_put_and_get_plan(self, cache_with_temp_dir, sample_plan):
        """Test storing and retrieving a plan from cache."""
        cache = cache_with_temp_dir
        query = "What spells can wizards cast?"

        # Initially no plan should exist
        result = cache.get(query)
        assert result is None
        assert cache._metrics["misses"] == 1

        # Store the plan
        cache.put(query, sample_plan)

        # Retrieve the plan
        result = cache.get(query)
        assert result is not None
        assert result.original_query == query
        assert result.hit_count == 1  # Should be incremented
        assert cache._metrics["hits"] == 1

    def test_exact_query_matching(self, cache_with_temp_dir, sample_plan):
        """Test that cache only matches exact query strings."""
        cache = cache_with_temp_dir
        original_query = "What spells can wizards cast?"
        similar_query = "What spells can a wizard cast?"  # slightly different

        # Store plan for original query
        cache.put(original_query, sample_plan)

        # Original query should hit
        result = cache.get(original_query)
        assert result is not None

        # Similar query should miss
        result = cache.get(similar_query)
        assert result is None

    def test_plan_expiration(self, cache_with_temp_dir):
        """Test TTL-based plan expiration."""
        cache = cache_with_temp_dir
        query = "test query"

        # Create plan with 1 second TTL
        plan = QueryPlan.create_from_query(
            query=query,
            classification={
                "intent": "fact_lookup",
                "domain": "unknown",
                "complexity": "low",
                "needs_tools": False,
                "confidence": 0.5
            },
            retrieval_strategy={},
            model_config={},
            cache_ttl=1
        )

        # Store the plan
        cache.put(query, plan)

        # Should be retrievable immediately
        result = cache.get(query)
        assert result is not None

        # Mock time to simulate expiration
        with patch('time.time', return_value=plan.created_at + 2):
            result = cache.get(query)
            assert result is None  # Should be expired and removed
            assert cache._metrics["evictions"] == 1

    def test_hit_count_tracking(self, cache_with_temp_dir, sample_plan):
        """Test that hit count is properly tracked and persisted."""
        cache = cache_with_temp_dir
        query = "test query"

        # Store plan
        cache.put(query, sample_plan)

        # Retrieve multiple times
        for i in range(3):
            result = cache.get(query)
            assert result.hit_count == i + 1

    def test_corrupted_cache_handling(self, cache_with_temp_dir):
        """Test handling of corrupted cache files."""
        cache = cache_with_temp_dir
        query = "test query"
        query_hash = QueryPlan._hash_query(query)

        # Create a corrupted cache file
        cache_file = cache.cache_dir / f"{query_hash}.json"
        cache_file.write_text("invalid json content", encoding='utf-8')

        # Should handle corruption gracefully
        result = cache.get(query)
        assert result is None
        assert not cache_file.exists()  # Should be removed

    def test_cleanup_expired(self, cache_with_temp_dir):
        """Test cleanup of expired cache entries."""
        cache = cache_with_temp_dir

        # Create mix of valid and expired plans
        current_time = time.time()

        # Valid plan (not expired)
        valid_plan_data = {
            "query_hash": "hash1",
            "original_query": "valid query",
            "created_at": current_time,
            "cache_ttl": 3600,
            "classification": {},
            "retrieval_strategy": {},
            "model_config": {},
            "performance_hints": {},
            "hit_count": 0
        }
        (cache.cache_dir / "hash1.json").write_text(
            json.dumps(valid_plan_data), encoding='utf-8'
        )

        # Expired plan
        expired_plan_data = {
            "query_hash": "hash2",
            "original_query": "expired query",
            "created_at": current_time - 7200,  # 2 hours ago
            "cache_ttl": 3600,  # 1 hour TTL
            "classification": {},
            "retrieval_strategy": {},
            "model_config": {},
            "performance_hints": {},
            "hit_count": 0
        }
        (cache.cache_dir / "hash2.json").write_text(
            json.dumps(expired_plan_data), encoding='utf-8'
        )

        # Run cleanup
        removed_count = cache.cleanup_expired()

        assert removed_count == 1  # Only expired plan should be removed
        assert (cache.cache_dir / "hash1.json").exists()  # Valid plan remains
        assert not (cache.cache_dir / "hash2.json").exists()  # Expired plan removed

    def test_clear_cache(self, cache_with_temp_dir, sample_plan):
        """Test clearing all cached plans."""
        cache = cache_with_temp_dir

        # Add multiple plans
        for i in range(3):
            query = f"test query {i}"
            cache.put(query, sample_plan)

        # Verify plans exist
        assert len(list(cache.cache_dir.glob("*.json"))) == 3

        # Clear cache
        removed_count = cache.clear()

        assert removed_count == 3
        assert len(list(cache.cache_dir.glob("*.json"))) == 0

    def test_get_metrics(self, cache_with_temp_dir, sample_plan):
        """Test metrics collection and calculation."""
        cache = cache_with_temp_dir

        # Add some activity
        cache.put("query1", sample_plan)
        cache.get("query1")  # hit
        cache.get("query2")  # miss

        metrics = cache.get_metrics()

        assert metrics.total_queries == 2
        assert metrics.cache_hit_rate == 0.5  # 1 hit out of 2 queries
        assert metrics.cache_miss_rate == 0.5  # 1 miss out of 2 queries
        assert metrics.successful_plans == 1
        assert metrics.cache_size >= 0

    def test_get_cache_info(self, cache_with_temp_dir, sample_plan):
        """Test detailed cache information retrieval."""
        cache = cache_with_temp_dir
        query = "test query for info"

        # Store a plan and retrieve it once
        cache.put(query, sample_plan)
        cache.get(query)

        cache_info = cache.get_cache_info()

        assert cache_info["environment"] == "test"
        assert cache_info["total_files"] == 1
        assert len(cache_info["files"]) == 1

        file_info = cache_info["files"][0]
        assert "test query" in file_info["query_preview"]
        assert file_info["hit_count"] == 1


class TestGlobalCacheManagement:
    """Test global cache instance management."""

    def test_get_cache_singleton(self):
        """Test that get_cache returns singleton instances per environment."""
        with patch.dict('os.environ', {'APP_ENV': 'test'}):
            cache1 = get_cache("dev")
            cache2 = get_cache("dev")
            cache3 = get_cache("prod")

            # Same environment should return same instance
            assert cache1 is cache2

            # Different environment should return different instance
            assert cache1 is not cache3

    def test_get_cache_default_environment(self):
        """Test cache creation with default environment."""
        with patch.dict('os.environ', {'APP_ENV': 'test'}):
            cache = get_cache()
            assert cache.environment == "test"