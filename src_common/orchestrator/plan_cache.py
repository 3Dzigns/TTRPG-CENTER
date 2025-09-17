"""
Query Plan Cache Implementation
Provides exact-match caching for query plans with environment isolation.
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Dict, Any, Optional, List
from threading import Lock

from ..ttrpg_logging import get_logger
from .plan_models import QueryPlan, PlanMetrics

logger = get_logger(__name__)


class QueryPlanCache:
    """
    File-based cache for query plans with exact string matching.

    Features:
    - Environment isolation (dev/test/prod)
    - TTL-based expiration
    - Thread-safe operations
    - Automatic cleanup of expired entries
    - Metrics tracking for cache performance
    """

    def __init__(self, environment: str = None):
        self.environment = environment or os.getenv("APP_ENV", "dev")
        self.cache_dir = Path(f"env/{self.environment}/cache/query_plans")
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        # Thread safety for concurrent access
        self._lock = Lock()

        # In-memory metrics tracking
        self._metrics = {
            "hits": 0,
            "misses": 0,
            "evictions": 0,
            "total_queries": 0
        }

        logger.info(f"QueryPlanCache initialized for environment: {self.environment}")

    def get(self, query: str) -> Optional[QueryPlan]:
        """
        Retrieve a cached plan for the exact query string.

        Args:
            query: The exact query string to match

        Returns:
            QueryPlan if found and not expired, None otherwise
        """
        with self._lock:
            self._metrics["total_queries"] += 1

            query_hash = QueryPlan._hash_query(query)
            cache_file = self.cache_dir / f"{query_hash}.json"

            if not cache_file.exists():
                self._metrics["misses"] += 1
                logger.debug(f"Cache miss for query hash: {query_hash}")
                return None

            try:
                with open(cache_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)

                plan = QueryPlan.from_dict(data)

                # Check if plan is expired
                if plan.is_expired():
                    # Remove expired plan
                    cache_file.unlink(missing_ok=True)
                    self._metrics["misses"] += 1
                    self._metrics["evictions"] += 1
                    logger.debug(f"Expired plan removed for query hash: {query_hash}")
                    return None

                # Increment hit count and update cache
                plan.increment_hit_count()
                self._update_cache_file(cache_file, plan)

                self._metrics["hits"] += 1
                logger.debug(f"Cache hit for query hash: {query_hash}, hit_count: {plan.hit_count}")
                return plan

            except Exception as e:
                logger.warning(f"Failed to load cached plan for {query_hash}: {e}")
                # Remove corrupted cache file
                cache_file.unlink(missing_ok=True)
                self._metrics["misses"] += 1
                return None

    def put(self, query: str, plan: QueryPlan) -> None:
        """
        Store a query plan in the cache.

        Args:
            query: The query string (used for hash generation)
            plan: The QueryPlan to cache
        """
        with self._lock:
            query_hash = QueryPlan._hash_query(query)
            cache_file = self.cache_dir / f"{query_hash}.json"

            try:
                self._update_cache_file(cache_file, plan)
                logger.debug(f"Cached plan for query hash: {query_hash}")

            except Exception as e:
                logger.warning(f"Failed to cache plan for {query_hash}: {e}")

    def _update_cache_file(self, cache_file: Path, plan: QueryPlan) -> None:
        """Update cache file with plan data."""
        with open(cache_file, 'w', encoding='utf-8') as f:
            json.dump(plan.to_dict(), f, indent=2)

    def cleanup_expired(self) -> int:
        """
        Remove all expired cache entries.

        Returns:
            Number of entries removed
        """
        with self._lock:
            removed_count = 0
            current_time = time.time()

            for cache_file in self.cache_dir.glob("*.json"):
                try:
                    with open(cache_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)

                    created_at = data.get('created_at', 0)
                    ttl = data.get('cache_ttl', 3600)

                    if (current_time - created_at) > ttl:
                        cache_file.unlink()
                        removed_count += 1

                except Exception as e:
                    logger.warning(f"Error checking cache file {cache_file}: {e}")
                    # Remove corrupted files
                    cache_file.unlink(missing_ok=True)
                    removed_count += 1

            if removed_count > 0:
                logger.info(f"Cleaned up {removed_count} expired cache entries")
                self._metrics["evictions"] += removed_count

            return removed_count

    def clear(self) -> int:
        """
        Clear all cached plans.

        Returns:
            Number of entries removed
        """
        with self._lock:
            removed_count = 0

            for cache_file in self.cache_dir.glob("*.json"):
                try:
                    cache_file.unlink()
                    removed_count += 1
                except Exception as e:
                    logger.warning(f"Error removing cache file {cache_file}: {e}")

            logger.info(f"Cleared {removed_count} cache entries")
            return removed_count

    def get_metrics(self) -> PlanMetrics:
        """
        Get current cache performance metrics.

        Returns:
            PlanMetrics with current performance data
        """
        with self._lock:
            total = self._metrics["total_queries"]
            hits = self._metrics["hits"]
            misses = self._metrics["misses"]

            cache_hit_rate = (hits / total) if total > 0 else 0.0
            cache_miss_rate = (misses / total) if total > 0 else 0.0

            # Count current cache size
            cache_size = len(list(self.cache_dir.glob("*.json")))

            return PlanMetrics(
                cache_hit_rate=cache_hit_rate,
                cache_miss_rate=cache_miss_rate,
                total_queries=total,
                cache_size=cache_size,
                avg_plan_generation_time_ms=0.0,  # Will be tracked separately
                avg_execution_time_savings_ms=0.0,  # Will be tracked separately
                successful_plans=hits,
                failed_plans=0,  # Will be tracked separately
                fallback_used=0,  # Will be tracked separately
                recorded_at=time.time()
            )

    def get_cache_info(self) -> Dict[str, Any]:
        """
        Get detailed cache information for debugging and monitoring.

        Returns:
            Dictionary with cache statistics and file information
        """
        with self._lock:
            cache_files = list(self.cache_dir.glob("*.json"))
            file_info = []

            for cache_file in cache_files:
                try:
                    stat = cache_file.stat()
                    with open(cache_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)

                    file_info.append({
                        "hash": cache_file.stem,
                        "query_preview": data.get('original_query', '')[:50] + "...",
                        "hit_count": data.get('hit_count', 0),
                        "created_at": data.get('created_at', 0),
                        "file_size_bytes": stat.st_size,
                        "ttl": data.get('cache_ttl', 3600)
                    })

                except Exception as e:
                    logger.warning(f"Error reading cache file {cache_file}: {e}")

            return {
                "environment": self.environment,
                "cache_directory": str(self.cache_dir),
                "total_files": len(cache_files),
                "metrics": self._metrics.copy(),
                "files": sorted(file_info, key=lambda x: x["hit_count"], reverse=True)
            }


# Global cache instance per environment
_cache_instances: Dict[str, QueryPlanCache] = {}
_cache_lock = Lock()


def get_cache(environment: str = None) -> QueryPlanCache:
    """
    Get or create a cache instance for the specified environment.

    Args:
        environment: Environment name (dev/test/prod)

    Returns:
        QueryPlanCache instance for the environment
    """
    env = environment or os.getenv("APP_ENV", "dev")

    with _cache_lock:
        if env not in _cache_instances:
            _cache_instances[env] = QueryPlanCache(env)
        return _cache_instances[env]