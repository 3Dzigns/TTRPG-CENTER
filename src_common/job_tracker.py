"""
Redis-backed job state tracker for persistent job monitoring and control.

This module provides Redis persistence for ingestion job state, enabling:
- Job state persistence across service restarts
- Distributed job tracking across multiple services
- Real-time job metrics and progress monitoring
- Job cancellation with proper state cleanup
"""

import json
import time
import logging
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, asdict
import redis
from redis.asyncio import Redis as AsyncRedis

logger = logging.getLogger(__name__)


@dataclass
class PhaseProgress:
    """Progress tracking for a single ingestion phase"""
    phase: str
    status: str  # started, progress, completed, failed, cancelled
    start_time: float
    current_time: float
    total_items: int = 0
    completed_items: int = 0
    failed_items: int = 0
    current_item: Optional[str] = None
    error_message: Optional[str] = None
    processing_rate: float = 0.0

    @property
    def duration_seconds(self) -> float:
        return self.current_time - self.start_time

    @property
    def progress_percent(self) -> float:
        if self.total_items == 0:
            return 0.0
        return (self.completed_items / self.total_items) * 100


class RedisJobTracker:
    """
    Redis-backed job state persistence and tracking.

    Stores job state in Redis with the following key structure:
    - job:{job_id}:meta - Job metadata (environment, sources, options)
    - job:{job_id}:phases - Phase progress data
    - job:{job_id}:status - Current job status
    - jobs:active - Set of active job IDs
    - jobs:{environment}:active - Set of active jobs per environment
    """

    def __init__(self, redis_url: str = "redis://redis-dev:6379/0"):
        """
        Initialize Redis job tracker.

        Args:
            redis_url: Redis connection URL
        """
        self.redis_url = redis_url
        self._sync_redis: Optional[redis.Redis] = None
        self._async_redis: Optional[AsyncRedis] = None
        self._ttl_seconds = 86400 * 7  # Keep job data for 7 days

    @property
    def sync_redis(self) -> redis.Redis:
        """Get synchronous Redis connection (lazy initialization)"""
        if self._sync_redis is None:
            self._sync_redis = redis.from_url(self.redis_url, decode_responses=True)
        return self._sync_redis

    async def get_async_redis(self) -> AsyncRedis:
        """Get async Redis connection (lazy initialization)"""
        if self._async_redis is None:
            self._async_redis = AsyncRedis.from_url(self.redis_url, decode_responses=True)
        return self._async_redis

    def _job_meta_key(self, job_id: str) -> str:
        return f"job:{job_id}:meta"

    def _job_phases_key(self, job_id: str) -> str:
        return f"job:{job_id}:phases"

    def _job_status_key(self, job_id: str) -> str:
        return f"job:{job_id}:status"

    def _active_jobs_key(self, environment: Optional[str] = None) -> str:
        if environment:
            return f"jobs:{environment}:active"
        return "jobs:active"

    async def create_job(self, job_id: str, environment: str, sources: List[str],
                        options: Optional[Dict[str, Any]] = None) -> None:
        """
        Create a new job in Redis with initial state.

        Args:
            job_id: Unique job identifier
            environment: Environment name (dev, test, prod)
            sources: List of source files to process
            options: Additional job options
        """
        redis = await self.get_async_redis()

        meta = {
            "job_id": job_id,
            "environment": environment,
            "sources": sources,
            "options": options or {},
            "created_at": time.time(),
            "started_at": None,
            "completed_at": None,
        }

        # Store job metadata
        await redis.set(
            self._job_meta_key(job_id),
            json.dumps(meta),
            ex=self._ttl_seconds
        )

        # Set initial status
        await redis.set(
            self._job_status_key(job_id),
            "created",
            ex=self._ttl_seconds
        )

        # Initialize empty phases
        await redis.set(
            self._job_phases_key(job_id),
            json.dumps({}),
            ex=self._ttl_seconds
        )

        # Add to active jobs sets
        await redis.sadd(self._active_jobs_key(), job_id)
        await redis.sadd(self._active_jobs_key(environment), job_id)

        logger.info(f"Created job {job_id} in Redis for environment {environment}")

    async def start_job(self, job_id: str) -> None:
        """Mark job as started"""
        redis = await self.get_async_redis()

        # Update metadata with start time
        meta_key = self._job_meta_key(job_id)
        meta_json = await redis.get(meta_key)
        if meta_json:
            meta = json.loads(meta_json)
            meta["started_at"] = time.time()
            await redis.set(meta_key, json.dumps(meta), ex=self._ttl_seconds)

        # Update status
        await redis.set(
            self._job_status_key(job_id),
            "running",
            ex=self._ttl_seconds
        )

        logger.info(f"Started job {job_id}")

    async def update_phase(self, job_id: str, phase_progress: PhaseProgress) -> None:
        """
        Update phase progress for a job.

        Args:
            job_id: Job identifier
            phase_progress: Phase progress data to update
        """
        redis = await self.get_async_redis()

        # Get current phases
        phases_json = await redis.get(self._job_phases_key(job_id))
        phases = json.loads(phases_json) if phases_json else {}

        # Update phase data with computed metrics
        phase_data = asdict(phase_progress)
        phase_data['progress_percent'] = phase_progress.progress_percent
        phase_data['duration_seconds'] = phase_progress.duration_seconds
        phase_data['updated_at'] = time.time()
        phases[phase_progress.phase] = phase_data

        # Save back to Redis
        await redis.set(
            self._job_phases_key(job_id),
            json.dumps(phases),
            ex=self._ttl_seconds
        )

    async def get_job_state(self, job_id: str) -> Optional[Dict[str, Any]]:
        """
        Get complete job state from Redis.

        Args:
            job_id: Job identifier

        Returns:
            Job state dictionary or None if not found
        """
        redis = await self.get_async_redis()

        # Get all job data
        meta_json = await redis.get(self._job_meta_key(job_id))
        phases_json = await redis.get(self._job_phases_key(job_id))
        status = await redis.get(self._job_status_key(job_id))

        if not meta_json:
            return None

        meta = json.loads(meta_json)
        phases = json.loads(phases_json) if phases_json else {}

        return {
            "job_id": job_id,
            "meta": meta,
            "status": status or "unknown",
            "phases": phases,
        }

    async def get_job_metrics(self, job_id: str) -> Dict[str, Any]:
        """
        Get job metrics for real-time monitoring.

        Args:
            job_id: Job identifier

        Returns:
            Metrics dictionary compatible with WebSocket endpoint
        """
        state = await self.get_job_state(job_id)

        if not state:
            return {
                "job_id": job_id,
                "status": "not_found",
                "message": "Job not found"
            }

        phases = state.get("phases", {})
        status = state.get("status", "unknown")
        meta = state.get("meta", {})

        # Aggregate metrics across all phases
        total_items = sum(p.get("total_items", 0) for p in phases.values())
        completed_items = sum(p.get("completed_items", 0) for p in phases.values())
        failed_items = sum(p.get("failed_items", 0) for p in phases.values())

        # Find current active phase
        current_phase = None
        for phase_name, phase_data in phases.items():
            if phase_data.get("status") in ["started", "progress"]:
                current_phase = phase_name
                break

        # Calculate overall processing rate
        overall_rate = 0.0
        if phases:
            total_duration = max(p.get("duration_seconds", 0) for p in phases.values())
            if total_duration > 0:
                overall_rate = completed_items / total_duration

        return {
            "job_id": job_id,
            "status": status,
            "environment": meta.get("environment"),
            "sources": meta.get("sources", []),
            "current_phase": current_phase,
            "phase": current_phase,  # Alias for UI compatibility
            "processed_sources": completed_items,
            "total_sources": len(meta.get("sources", [])),
            "overall_progress": {
                "total_items": total_items,
                "completed_items": completed_items,
                "failed_items": failed_items,
                "success_rate": (completed_items / total_items * 100) if total_items > 0 else 0,
                "processing_rate": overall_rate
            },
            "phases": {
                name: {
                    "status": phase.get("status"),
                    "progress_percent": phase.get("progress_percent", 0),
                    "duration_seconds": phase.get("duration_seconds", 0),
                    "processing_rate": phase.get("processing_rate", 0),
                    "current_item": phase.get("current_item")
                }
                for name, phase in phases.items()
            },
            "timestamp": time.time()
        }

    async def cancel_job(self, job_id: str) -> bool:
        """
        Cancel a job and mark it as cancelled.

        Args:
            job_id: Job identifier

        Returns:
            True if job was cancelled, False if not found
        """
        redis = await self.get_async_redis()

        # Check if job exists
        status_key = self._job_status_key(job_id)
        current_status = await redis.get(status_key)

        if not current_status:
            logger.warning(f"Cannot cancel job {job_id}: not found")
            return False

        if current_status in ["completed", "failed", "cancelled"]:
            logger.info(f"Job {job_id} already in terminal state: {current_status}")
            return False

        # Update status to cancelled
        await redis.set(status_key, "cancelled", ex=self._ttl_seconds)

        # Get metadata and update completion time
        meta_key = self._job_meta_key(job_id)
        meta_json = await redis.get(meta_key)
        if meta_json:
            meta = json.loads(meta_json)
            meta["completed_at"] = time.time()
            meta["cancelled_at"] = time.time()
            await redis.set(meta_key, json.dumps(meta), ex=self._ttl_seconds)

        # Remove from active jobs
        meta = json.loads(meta_json) if meta_json else {}
        environment = meta.get("environment")

        await redis.srem(self._active_jobs_key(), job_id)
        if environment:
            await redis.srem(self._active_jobs_key(environment), job_id)

        logger.info(f"Cancelled job {job_id}")
        return True

    async def complete_job(self, job_id: str, status: str = "completed") -> None:
        """
        Mark job as completed or failed.

        Args:
            job_id: Job identifier
            status: Final status (completed, failed)
        """
        redis = await self.get_async_redis()

        # Update status
        await redis.set(
            self._job_status_key(job_id),
            status,
            ex=self._ttl_seconds
        )

        # Update metadata with completion time
        meta_key = self._job_meta_key(job_id)
        meta_json = await redis.get(meta_key)
        if meta_json:
            meta = json.loads(meta_json)
            meta["completed_at"] = time.time()
            await redis.set(meta_key, json.dumps(meta), ex=self._ttl_seconds)

        # Remove from active jobs
        meta = json.loads(meta_json) if meta_json else {}
        environment = meta.get("environment")

        await redis.srem(self._active_jobs_key(), job_id)
        if environment:
            await redis.srem(self._active_jobs_key(environment), job_id)

        logger.info(f"Completed job {job_id} with status {status}")

    async def list_active_jobs(self, environment: Optional[str] = None) -> List[str]:
        """
        List all active job IDs.

        Args:
            environment: Filter by environment (optional)

        Returns:
            List of active job IDs
        """
        redis = await self.get_async_redis()
        key = self._active_jobs_key(environment)
        job_ids = await redis.smembers(key)
        return list(job_ids)

    async def cleanup_stale_jobs(self, max_age_hours: int = 48) -> int:
        """
        Clean up jobs that have been running for too long.

        Args:
            max_age_hours: Maximum job age in hours

        Returns:
            Number of jobs cleaned up
        """
        redis = await self.get_async_redis()

        active_jobs = await self.list_active_jobs()
        cleanup_count = 0
        max_age_seconds = max_age_hours * 3600
        current_time = time.time()

        for job_id in active_jobs:
            state = await self.get_job_state(job_id)
            if not state:
                continue

            meta = state.get("meta", {})
            started_at = meta.get("started_at")

            if started_at and (current_time - started_at) > max_age_seconds:
                logger.warning(f"Cleaning up stale job {job_id} (age: {(current_time - started_at) / 3600:.1f} hours)")
                await self.complete_job(job_id, status="failed")
                cleanup_count += 1

        return cleanup_count

    async def close(self) -> None:
        """Close Redis connections"""
        if self._async_redis:
            await self._async_redis.close()
        if self._sync_redis:
            self._sync_redis.close()
