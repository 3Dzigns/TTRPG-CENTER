"""
Priority job queue management for pipeline-worker.
"""

import asyncio
import heapq
from typing import Optional, Dict, List
from datetime import datetime
from .models import JobRequest, JobPriority, JobStatus


class PriorityJobQueue:
    """Priority queue for pipeline jobs."""

    def __init__(self, max_size: int = 100):
        self.max_size = max_size
        self._heap: List[tuple] = []
        self._counter = 0
        self._jobs: Dict[str, JobRequest] = {}
        self._lock = asyncio.Lock()

    async def put(self, job: JobRequest) -> bool:
        """
        Add job to queue with priority.

        Returns:
            True if job added, False if queue full
        """
        async with self._lock:
            if len(self._heap) >= self.max_size:
                return False

            # Use tuple for priority: (priority, counter, job_id)
            # Counter ensures FIFO for same priority
            priority_tuple = (job.priority.value, self._counter, job.job_id)
            heapq.heappush(self._heap, priority_tuple)
            self._jobs[job.job_id] = job
            self._counter += 1
            return True

    async def get(self) -> Optional[JobRequest]:
        """
        Get highest priority job from queue.

        Returns:
            JobRequest or None if queue empty
        """
        async with self._lock:
            if not self._heap:
                return None

            priority_tuple = heapq.heappop(self._heap)
            job_id = priority_tuple[2]
            job = self._jobs.pop(job_id, None)
            return job

    async def get_job(self, job_id: str) -> Optional[JobRequest]:
        """Get specific job by ID without removing from queue."""
        async with self._lock:
            return self._jobs.get(job_id)

    async def remove(self, job_id: str) -> bool:
        """
        Remove specific job from queue.

        Returns:
            True if removed, False if not found
        """
        async with self._lock:
            if job_id not in self._jobs:
                return False

            # Remove from jobs dict
            self._jobs.pop(job_id)

            # Rebuild heap without this job
            new_heap = [item for item in self._heap if item[2] != job_id]
            self._heap = new_heap
            heapq.heapify(self._heap)
            return True

    async def size(self) -> int:
        """Get current queue size."""
        async with self._lock:
            return len(self._heap)

    async def is_empty(self) -> bool:
        """Check if queue is empty."""
        return await self.size() == 0

    async def is_full(self) -> bool:
        """Check if queue is full."""
        return await self.size() >= self.max_size

    async def list_jobs(self) -> List[JobRequest]:
        """List all jobs in queue (sorted by priority)."""
        async with self._lock:
            # Return sorted list of jobs
            sorted_items = sorted(self._heap)
            return [self._jobs[item[2]] for item in sorted_items if item[2] in self._jobs]

    async def clear(self):
        """Clear all jobs from queue."""
        async with self._lock:
            self._heap.clear()
            self._jobs.clear()
            self._counter = 0


class JobTracker:
    """Track job execution status and history."""

    def __init__(self):
        self._active_jobs: Dict[str, JobRequest] = {}
        self._completed_jobs: Dict[str, JobRequest] = {}
        self._lock = asyncio.Lock()

    async def start_job(self, job: JobRequest):
        """Mark job as started."""
        async with self._lock:
            self._active_jobs[job.job_id] = job

    async def complete_job(self, job_id: str, status: JobStatus):
        """Mark job as completed."""
        async with self._lock:
            job = self._active_jobs.pop(job_id, None)
            if job:
                self._completed_jobs[job_id] = job

    async def get_active_job(self, job_id: str) -> Optional[JobRequest]:
        """Get active job by ID."""
        async with self._lock:
            return self._active_jobs.get(job_id)

    async def list_active_jobs(self) -> List[JobRequest]:
        """List all active jobs."""
        async with self._lock:
            return list(self._active_jobs.values())

    async def list_completed_jobs(self, limit: int = 100) -> List[JobRequest]:
        """List recently completed jobs."""
        async with self._lock:
            jobs = list(self._completed_jobs.values())
            # Sort by created_at descending
            jobs.sort(key=lambda j: j.created_at, reverse=True)
            return jobs[:limit]

    async def get_job_count(self) -> Dict[str, int]:
        """Get counts of active and completed jobs."""
        async with self._lock:
            return {
                "active": len(self._active_jobs),
                "completed": len(self._completed_jobs)
            }