"""
FR-002: Job Manager and Queue

Provides a minimal job lifecycle manager with persistence suitable for
scheduling integration tests. Includes Job dataclass and JobStatus enum.
"""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, asdict
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional


class JobStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class Job:
    id: str
    name: str
    job_type: str
    source_path: str
    environment: str
    priority: int
    created_at: datetime
    status: JobStatus = JobStatus.PENDING
    retry_count: int = 0
    error: Optional[str] = None


class JobQueue:
    """Simple in-memory priority queue for jobs (lowest priority value first)."""

    def __init__(self) -> None:
        self._queue: List[Job] = []

    def enqueue(self, job: Job) -> None:
        self._queue.append(job)
        self._queue.sort(key=lambda j: (j.priority, j.created_at))

    def dequeue(self) -> Optional[Job]:
        if not self._queue:
            return None
        return self._queue.pop(0)

    def size(self) -> int:
        return len(self._queue)


class JobManager:
    """Manage job lifecycle with optional persistence and pipeline execution hooks."""

    def __init__(self, config: Dict[str, Any], pipeline: Any, state_file: Optional[Path] = None) -> None:
        self.config = config
        self.pipeline = pipeline
        self.state_file = Path(state_file) if state_file else None
        self.jobs: Dict[str, Job] = {}
        self.on_status_change = None  # Optional callback(job_id, old, new)
        self._tasks: Dict[str, asyncio.Task] = {}
        self._counter = 0

    def _next_id(self) -> str:
        self._counter += 1
        return f"job_{self.config.get('environment', 'dev')}_{self._counter:06d}"

    def create_job(self, name: str, job_type: str, source_path: str, environment: str, priority: int = 1) -> str:
        job_id = self._next_id()
        job = Job(
            id=job_id,
            name=name,
            job_type=job_type,
            source_path=source_path,
            environment=environment,
            priority=priority,
            created_at=datetime.now(),
            status=JobStatus.PENDING,
        )
        self.jobs[job_id] = job
        self._emit(job_id, None, JobStatus.PENDING)
        return job_id

    def get_job(self, job_id: str) -> Optional[Job]:
        return self.jobs.get(job_id)

    async def start_job(self, job_id: str) -> None:
        job = self.jobs.get(job_id)
        if not job:
            return
        old = job.status
        job.status = JobStatus.RUNNING
        self._emit(job_id, old, job.status)
        # Launch background execution; do not await here to allow tests to proceed
        self._tasks[job_id] = asyncio.create_task(self._execute(job))

    async def _execute(self, job: Job) -> None:
        try:
            # Provide common kwargs
            kwargs: Dict[str, Any] = {
                "environment": job.environment,
                "source_path": job.source_path,
                "artifacts_dir": self.config.get("artifacts_base"),
            }
            await self._maybe_await(self.pipeline.process_source(**kwargs))
            # If no explicit completion, mark completed
            if self.jobs.get(job.id) and self.jobs[job.id].status == JobStatus.RUNNING:
                await self.complete_job(job.id, {"status": "completed"})
        except asyncio.CancelledError:
            # Cancellation handled by cancel_job
            pass
        except Exception as e:
            await self.fail_job(job.id, str(e))

    async def complete_job(self, job_id: str, result: Dict[str, Any]) -> None:
        job = self.jobs.get(job_id)
        if not job:
            return
        old = job.status
        job.status = JobStatus.COMPLETED
        self._emit(job_id, old, job.status)
        # Cleanup task if present
        t = self._tasks.pop(job_id, None)
        if t and not t.done():
            t.cancel()

    async def fail_job(self, job_id: str, error_message: str) -> None:
        job = self.jobs.get(job_id)
        if not job:
            return
        old = job.status
        job.status = JobStatus.FAILED
        job.error = error_message
        self._emit(job_id, old, job.status)

    async def cancel_job(self, job_id: str, reason: str = "") -> Dict[str, Any]:
        job = self.jobs.get(job_id)
        if not job:
            return {"status": "not_found"}
        # Cancel background task
        t = self._tasks.pop(job_id, None)
        if t and not t.done():
            t.cancel()
        old = job.status
        job.status = JobStatus.CANCELLED
        self._emit(job_id, old, job.status)
        return {"status": "cancelled", "reason": reason, "job_id": job_id}

    def save_state(self) -> None:
        if not self.state_file:
            return
        data = {
            "jobs": [self._job_to_json(j) for j in self.jobs.values()],
            "counter": self._counter,
        }
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        self.state_file.write_text(json.dumps(data, default=str, indent=2), encoding="utf-8")

    def load_state(self) -> None:
        if not self.state_file or not self.state_file.exists():
            return
        data = json.loads(self.state_file.read_text(encoding="utf-8"))
        self.jobs.clear()
        for jd in data.get("jobs", []):
            job = Job(
                id=jd["id"],
                name=jd["name"],
                job_type=jd["job_type"],
                source_path=jd["source_path"],
                environment=jd["environment"],
                priority=int(jd.get("priority", 1)),
                created_at=datetime.fromisoformat(jd["created_at"]),
                status=JobStatus(jd.get("status", "pending")),
                retry_count=int(jd.get("retry_count", 0)),
                error=jd.get("error"),
            )
            self.jobs[job.id] = job
        self._counter = int(data.get("counter", len(self.jobs)))

    async def recover_interrupted_jobs(self) -> List[str]:
        recovered: List[str] = []
        for job in self.jobs.values():
            if job.status == JobStatus.RUNNING:
                # Reset to PENDING so it can be re-run
                old = job.status
                job.status = JobStatus.PENDING
                self._emit(job.id, old, job.status)
                recovered.append(job.id)
        return recovered

    def _emit(self, job_id: str, old: Optional[JobStatus], new: JobStatus) -> None:
        if callable(self.on_status_change):
            try:
                self.on_status_change(job_id, old, new)
            except Exception:
                pass

    @staticmethod
    async def _maybe_await(v):
        if asyncio.iscoroutine(v):
            return await v
        return v

    @staticmethod
    def _job_to_json(job: Job) -> Dict[str, Any]:
        d = asdict(job)
        d["status"] = job.status.value
        d["created_at"] = job.created_at.isoformat()
        return d

