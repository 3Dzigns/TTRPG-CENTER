"""
FR-002: Scheduled Bulk Processor

Executes bulk ingestion jobs using a provided pipeline with concurrency
limits and retry logic.
"""

from __future__ import annotations

import asyncio
import time
from typing import Any, Dict, Optional
import os

from .ttrpg_logging import get_logger
from .job_status_store import get_job_store


class ScheduledBulkProcessor:
    def __init__(
        self,
        config: Dict[str, Any],
        pipeline: Any,
        max_concurrent_jobs: Optional[int] = None,
        max_retry_attempts: int = 3,
        retry_delay_seconds: float = 0.5,
    ) -> None:
        self.config = config
        self.pipeline = pipeline
        self.max_concurrent_jobs = max_concurrent_jobs or int(config.get("max_concurrent_jobs", 2))
        self.sem = asyncio.Semaphore(self.max_concurrent_jobs)
        self.max_retry_attempts = max_retry_attempts
        self.retry_delay_seconds = retry_delay_seconds
        self.logger = get_logger(__name__)
        self._active_jobs = 0

    async def execute_job(self, job) -> Dict[str, Any]:
        job_start_time = time.time()
        
        # P2.1: Create job status record
        self.logger.info(
            f"Initializing job status store (cwd={os.getcwd()}) for job {getattr(job, 'id', 'unknown')}"
        )
        job_store = await get_job_store()
        self.logger.info("Job status store ready; creating job record")
        job_store.create_job(
            job_id=job.id,
            source_path=getattr(job, 'source_path', 'unknown'),
            environment=getattr(job, 'environment', 'dev')
        )
        self.logger.info(f"Job status record created for {job.id}")
        
        # P0.1: Pre-semaphore logging - job waiting for execution slot
        waiting_start = time.time()
        current_active = self._active_jobs
        waiting_jobs = max(0, current_active - self.max_concurrent_jobs + 1)
        
        self.logger.info(
            f"Job {job.id} waiting for execution slot "
            f"(active: {current_active}/{self.max_concurrent_jobs}, "
            f"waiting: {waiting_jobs}, source: {getattr(job, 'source_path', 'unknown')})"
        )
        
        async with self.sem:
            # P0.1: Post-semaphore logging - job acquired slot and starting execution
            wait_time = time.time() - waiting_start
            self._active_jobs += 1
            
            self.logger.info(
                f"Job {job.id} acquired execution slot after {wait_time:.2f}s wait time, "
                f"starting 6-pass pipeline execution (slot {self._active_jobs}/{self.max_concurrent_jobs})"
            )
            
            try:
                attempt = 0
                while True:
                    attempt += 1
                    try:
                        # Execute the actual pipeline work
                        execution_start = time.time()
                        result = await self._maybe_await(
                            self.pipeline.process_source(
                                source_path=job.source_path,
                                environment=job.environment,
                                artifacts_dir=self.config.get("artifacts_base"),
                            )
                        )
                        
                        # P0.1: Execution completion logging
                        execution_time = time.time() - execution_start
                        total_time = time.time() - job_start_time
                        
                        self.logger.info(
                            f"Job {job.id} completed pipeline execution "
                            f"(execution: {execution_time:.2f}s, total: {total_time:.2f}s, "
                            f"status: {result.get('status', 'completed')})"
                        )
                        
                        # Normalize response
                        resp = {
                            "job_id": job.id,
                            "status": result.get("status", "completed"),
                            "processing_time": result.get("processing_time", execution_time),
                            "total_time": total_time,
                            "wait_time": wait_time,
                            "environment": result.get("environment", job.environment),
                            "artifacts_path": result.get("artifacts_path", self.config.get("artifacts_base")),
                            "thread_name": result.get("thread_name", "unknown"),
                            "error_message": result.get("error_message")
                        }
                        
                        # P2.1: Complete job in status store
                        job_store.complete_job(job.id, resp)
                        
                        return resp
                        
                    except Exception as e:
                        self.logger.warning(
                            f"Job {job.id} attempt {attempt} failed: {str(e)[:200]}"
                        )
                        
                        # Determine whether to retry
                        if attempt >= self.max_retry_attempts:
                            total_time = time.time() - job_start_time
                            self.logger.error(
                                f"Job {job.id} failed after {attempt} attempts "
                                f"(total time: {total_time:.2f}s): {str(e)}"
                            )
                            
                            failed_resp = {
                                "job_id": job.id,
                                "status": "failed",
                                "error_message": str(e),
                                "requires_retry": False,
                                "retry_count": attempt,
                                "total_time": total_time,
                                "wait_time": wait_time,
                                "thread_name": "failed",
                            }
                            
                            # P2.1: Complete failed job in status store
                            job_store.complete_job(job.id, failed_resp)
                            
                            return failed_resp
                        
                        # Backoff and retry
                        self.logger.info(f"Job {job.id} retrying in {self.retry_delay_seconds}s...")
                        await asyncio.sleep(self.retry_delay_seconds)
                        # Continue loop for retry
                        
            finally:
                # P0.1: Semaphore release logging  
                self._active_jobs -= 1
                total_time = time.time() - job_start_time
                
                self.logger.info(
                    f"Job {job.id} releasing execution slot "
                    f"(duration: {total_time:.2f}s, active slots now: {self._active_jobs}/{self.max_concurrent_jobs})"
                )

    @staticmethod
    async def _maybe_await(v):
        if asyncio.iscoroutine(v):
            return await v
        return v
