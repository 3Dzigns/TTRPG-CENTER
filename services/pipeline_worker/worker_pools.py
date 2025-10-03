"""
Worker pool management for pipeline passes.
"""

import asyncio
import uuid
from typing import Dict, List, Optional, Callable, Awaitable
from datetime import datetime
from .models import PassType, WorkerStatus, WorkerPoolStatus, JobStatus
from .config import config
import logging

logger = logging.getLogger(__name__)


class Worker:
    """Individual worker for executing pass tasks."""

    def __init__(self, worker_id: str, pass_type: PassType):
        self.worker_id = worker_id
        self.pass_type = pass_type
        self.status = "idle"
        self.current_job_id: Optional[str] = None
        self.current_source: Optional[str] = None
        self.jobs_completed = 0
        self.jobs_failed = 0
        self._task: Optional[asyncio.Task] = None

    async def execute(
        self,
        job_id: str,
        source_file: str,
        executor_func: Callable,
        **kwargs
    ) -> tuple[JobStatus, Optional[str], Optional[dict]]:
        """
        Execute a pass task.

        Returns:
            (status, error_message, output_data)
        """
        self.status = "busy"
        self.current_job_id = job_id
        self.current_source = source_file

        try:
            logger.info(f"Worker {self.worker_id} executing {self.pass_type} for {source_file}")
            result = await executor_func(source_file=source_file, job_id=job_id, **kwargs)
            self.jobs_completed += 1
            return (JobStatus.COMPLETED, None, result)
        except Exception as e:
            logger.error(f"Worker {self.worker_id} failed: {str(e)}")
            self.jobs_failed += 1
            return (JobStatus.FAILED, str(e), None)
        finally:
            self.status = "idle"
            self.current_job_id = None
            self.current_source = None

    def get_status(self) -> WorkerStatus:
        """Get current worker status."""
        return WorkerStatus(
            worker_id=self.worker_id,
            pass_type=self.pass_type,
            status=self.status,
            current_job_id=self.current_job_id,
            current_source=self.current_source,
            jobs_completed=self.jobs_completed,
            jobs_failed=self.jobs_failed
        )


class WorkerPool:
    """Pool of workers for a specific pass."""

    def __init__(self, pass_type: PassType, pool_size: int):
        self.pass_type = pass_type
        self.pool_size = pool_size
        self.workers: List[Worker] = []
        self.queue: asyncio.Queue = asyncio.Queue()
        self.total_jobs_completed = 0
        self.total_jobs_failed = 0
        self._running = False
        self._worker_tasks: List[asyncio.Task] = []

        # Create workers
        for i in range(pool_size):
            worker_id = f"{pass_type.value}-worker-{i+1}"
            self.workers.append(Worker(worker_id, pass_type))

    async def start(self, executor_func: Callable):
        """Start all workers in the pool."""
        if self._running:
            return

        self._running = True
        logger.info(f"Starting worker pool for {self.pass_type} with {self.pool_size} workers")

        # Start worker tasks
        for worker in self.workers:
            task = asyncio.create_task(self._worker_loop(worker, executor_func))
            self._worker_tasks.append(task)

    async def stop(self):
        """Stop all workers in the pool."""
        if not self._running:
            return

        self._running = False
        logger.info(f"Stopping worker pool for {self.pass_type}")

        # Cancel all worker tasks
        for task in self._worker_tasks:
            task.cancel()

        # Wait for cancellation
        await asyncio.gather(*self._worker_tasks, return_exceptions=True)
        self._worker_tasks.clear()

    async def _worker_loop(self, worker: Worker, executor_func: Callable):
        """Main loop for a worker."""
        while self._running:
            try:
                # Wait for task with timeout
                task_data = await asyncio.wait_for(self.queue.get(), timeout=1.0)

                job_id = task_data["job_id"]
                source_file = task_data["source_file"]
                kwargs = task_data.get("kwargs", {})

                # Execute task
                status, error, output = await worker.execute(
                    job_id, source_file, executor_func, **kwargs
                )

                # Update pool stats
                if status == JobStatus.COMPLETED:
                    self.total_jobs_completed += 1
                else:
                    self.total_jobs_failed += 1

                # Store result for retrieval
                task_data["result"] = {
                    "status": status,
                    "error": error,
                    "output": output
                }

                self.queue.task_done()

            except asyncio.TimeoutError:
                # No tasks available, continue loop
                continue
            except asyncio.CancelledError:
                # Worker stopped
                break
            except Exception as e:
                logger.error(f"Worker loop error: {str(e)}")
                continue

    async def submit_task(self, job_id: str, source_file: str, **kwargs) -> bool:
        """
        Submit a task to the worker pool.

        Returns:
            True if submitted, False if queue full
        """
        if not self._running:
            return False

        try:
            task_data = {
                "job_id": job_id,
                "source_file": source_file,
                "kwargs": kwargs
            }
            await self.queue.put(task_data)
            return True
        except asyncio.QueueFull:
            return False

    def get_status(self) -> WorkerPoolStatus:
        """Get current pool status."""
        active_workers = sum(1 for w in self.workers if w.status == "busy")
        idle_workers = sum(1 for w in self.workers if w.status == "idle")

        return WorkerPoolStatus(
            pass_type=self.pass_type,
            pool_size=self.pool_size,
            active_workers=active_workers,
            idle_workers=idle_workers,
            workers=[w.get_status() for w in self.workers],
            queue_size=self.queue.qsize(),
            total_jobs_completed=self.total_jobs_completed,
            total_jobs_failed=self.total_jobs_failed
        )


class WorkerPoolManager:
    """Manage all worker pools for pipeline passes."""

    def __init__(self):
        self.pools: Dict[PassType, WorkerPool] = {}
        self._started = False

    async def initialize(self, executor_map: Dict[PassType, Callable]):
        """
        Initialize all worker pools with their executor functions.

        Args:
            executor_map: Map of PassType to executor function
        """
        logger.info("Initializing worker pool manager")

        # Create pools for each pass
        for pass_type in PassType:
            if not config.is_pass_enabled(pass_type.value):
                logger.info(f"Pass {pass_type.value} disabled, skipping pool creation")
                continue

            pool_size = config.get_pool_size(pass_type.value)
            pool = WorkerPool(pass_type, pool_size)
            self.pools[pass_type] = pool

            # Start pool with executor
            executor_func = executor_map.get(pass_type)
            if executor_func:
                await pool.start(executor_func)
            else:
                logger.warning(f"No executor function for {pass_type.value}")

        self._started = True
        logger.info(f"Worker pool manager initialized with {len(self.pools)} pools")

    async def shutdown(self):
        """Shutdown all worker pools."""
        if not self._started:
            return

        logger.info("Shutting down worker pool manager")

        # Stop all pools
        for pool in self.pools.values():
            await pool.stop()

        self._started = False

    async def submit_task(
        self,
        pass_type: PassType,
        job_id: str,
        source_file: str,
        **kwargs
    ) -> bool:
        """
        Submit a task to a specific pass pool.

        Returns:
            True if submitted, False if pool not found or queue full
        """
        pool = self.pools.get(pass_type)
        if not pool:
            logger.error(f"No pool found for {pass_type.value}")
            return False

        return await pool.submit_task(job_id, source_file, **kwargs)

    def get_pool_status(self, pass_type: PassType) -> Optional[WorkerPoolStatus]:
        """Get status of a specific pool."""
        pool = self.pools.get(pass_type)
        return pool.get_status() if pool else None

    def get_all_pool_status(self) -> List[WorkerPoolStatus]:
        """Get status of all pools."""
        return [pool.get_status() for pool in self.pools.values()]

    def is_ready(self) -> bool:
        """Check if manager is ready to accept tasks."""
        return self._started and len(self.pools) > 0