"""
Pipeline orchestrator for managing full A→G pass execution.
"""

import asyncio
import uuid
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime
import logging

from .models import (
    PassType, JobStatus, JobRequest, JobResult, PassResult,
    TriggerMode, JobPriority, PipelineExecutionRequest
)
from .worker_pools import WorkerPoolManager
from .job_queue import PriorityJobQueue, JobTracker
from .pass_executor import PassExecutor
from .config import config

logger = logging.getLogger(__name__)


def setup_job_logger(job_id: str, env: str) -> tuple:
    """
    Create a dedicated file logger for a job and attach to ttrpg logger hierarchy.

    Args:
        job_id: Job ID for log filename
        env: Environment (dev/test/prod)

    Returns:
        Tuple of (job_logger, file_handler) for cleanup
    """
    # Create job-specific logger
    job_logger = logging.getLogger(f"pipeline_job_{job_id}")
    job_logger.setLevel(logging.DEBUG)
    job_logger.propagate = False  # Don't propagate to root logger

    # Remove any existing handlers
    job_logger.handlers.clear()

    # Create log directory if it doesn't exist
    log_dir = Path(config.base_path) / "env" / env / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)

    # Create log file path
    log_file = log_dir / f"{job_id}.log"

    # File handler for job-specific log
    file_handler = logging.FileHandler(log_file, encoding='utf-8')
    file_handler.setLevel(logging.DEBUG)

    # Console handler for stdout (so docker logs still work)
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)

    # Create formatter
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)

    # Add handlers to job logger
    job_logger.addHandler(file_handler)
    job_logger.addHandler(console_handler)

    # CRITICAL FIX: Add file handler to ttrpg logger hierarchy
    # This ensures all ttrpg.* loggers (including Pass A, B, C, etc.) write to job file
    ttrpg_logger = logging.getLogger("ttrpg")
    ttrpg_logger.addHandler(file_handler)

    return job_logger, file_handler


class PipelineOrchestrator:
    """Orchestrate full pipeline execution across worker pools."""

    def __init__(
        self,
        pool_manager: WorkerPoolManager,
        job_queue: PriorityJobQueue,
        job_tracker: JobTracker
    ):
        self.pool_manager = pool_manager
        self.job_queue = job_queue
        self.job_tracker = job_tracker
        self.executor = PassExecutor(config.target_env)
        self._active_pipelines: Dict[str, asyncio.Task] = {}

    async def trigger_pipeline(
        self,
        request: PipelineExecutionRequest
    ) -> JobResult:
        """
        Trigger full pipeline execution.

        Args:
            request: Pipeline execution request

        Returns:
            JobResult with execution details
        """
        job_id = request.job_id or self._generate_job_id(request.trigger_mode)

        logger.info(f"Pipeline triggered: job_id={job_id}, mode={request.trigger_mode}, files={len(request.source_files)}")

        # Create job request
        job_request = JobRequest(
            job_id=job_id,
            trigger_mode=request.trigger_mode,
            source_files=request.source_files,
            env=request.env,
            priority=request.priority,
            context=request.context or {}
        )

        # Add to queue
        queued = await self.job_queue.put(job_request)
        if not queued:
            logger.error(f"Failed to queue job {job_id}: queue full")
            return JobResult(
                job_id=job_id,
                status=JobStatus.FAILED,
                trigger_mode=request.trigger_mode,
                source_files=request.source_files,
                env=request.env,
                created_at=datetime.utcnow(),
                error="Job queue is full"
            )

        # Start pipeline task asynchronously (don't wait for completion)
        task = asyncio.create_task(
            self._run_pipeline(job_request, request.start_pass, request.end_pass)
        )
        self._active_pipelines[job_id] = task

        # Return immediately with job queued status
        return JobResult(
            job_id=job_id,
            status=JobStatus.QUEUED,
            trigger_mode=request.trigger_mode,
            source_files=request.source_files,
            env=request.env,
            created_at=job_request.created_at
        )

    async def _run_pipeline(
        self,
        job_request: JobRequest,
        start_pass: PassType,
        end_pass: PassType
    ) -> JobResult:
        """
        Run complete pipeline for job.

        Args:
            job_request: Job to execute
            start_pass: First pass to execute
            end_pass: Last pass to execute

        Returns:
            JobResult with execution details
        """
        job_id = job_request.job_id
        started_at = datetime.utcnow()

        # Setup job-specific logger
        job_logger, job_file_handler = setup_job_logger(job_id, job_request.env)

        await self.job_tracker.start_job(job_request)

        logger.info(f"Starting pipeline: job_id={job_id}, passes={start_pass.value}→{end_pass.value}")
        job_logger.info(f"Pipeline started: job_id={job_id}")
        job_logger.info(f"Trigger mode: {job_request.trigger_mode}")
        job_logger.info(f"Environment: {job_request.env}")
        job_logger.info(f"Pass range: {start_pass.value} → {end_pass.value}")
        job_logger.info(f"Source files: {len(job_request.source_files)}")
        for i, source_file in enumerate(job_request.source_files, 1):
            job_logger.info(f"  [{i}] {Path(source_file).name}")

        result = JobResult(
            job_id=job_id,
            status=JobStatus.RUNNING,
            trigger_mode=job_request.trigger_mode,
            source_files=job_request.source_files,
            env=job_request.env,
            created_at=job_request.created_at,
            started_at=started_at
        )

        # Define pass sequence
        pass_sequence = self._get_pass_sequence(start_pass, end_pass)

        try:
            # Execute each pass in sequence for all files
            for pass_type in pass_sequence:
                if not config.is_pass_enabled(pass_type.value):
                    logger.info(f"Pass {pass_type.value} disabled, skipping")
                    job_logger.warning(f"Pass {pass_type.value} is disabled in configuration, skipping")
                    continue

                logger.info(f"Job {job_id}: Executing {pass_type.value}")
                job_logger.info(f"\n{'='*60}")
                job_logger.info(f"Starting {pass_type.value}")
                job_logger.info(f"{'='*60}")

                # Execute pass for all source files
                pass_results = await self._execute_pass_for_sources(
                    pass_type,
                    job_id,
                    job_request.source_files,
                    job_request.env,
                    job_logger
                )

                result.pass_results.extend(pass_results)
                result.passes_completed.append(pass_type)

                # Log pass results
                success_count = len([r for r in pass_results if r.status == JobStatus.COMPLETED])
                failed_count = len([r for r in pass_results if r.status == JobStatus.FAILED])
                job_logger.info(f"{pass_type.value} completed: {success_count} succeeded, {failed_count} failed")

                # Check for failures
                failed_results = [r for r in pass_results if r.status == JobStatus.FAILED]
                if failed_results:
                    logger.error(f"Job {job_id}: {len(failed_results)} files failed in {pass_type.value}")
                    job_logger.error(f"PIPELINE FAILED: {len(failed_results)} files failed in {pass_type.value}")
                    for failed in failed_results:
                        job_logger.error(f"  - {Path(failed.source_file).name}: {failed.error}")
                    result.status = JobStatus.FAILED
                    result.error = f"{len(failed_results)} files failed in {pass_type.value}"
                    break

            # All passes completed successfully
            if result.status != JobStatus.FAILED:
                result.status = JobStatus.COMPLETED
                logger.info(f"Pipeline completed: job_id={job_id}")
                job_logger.info(f"\n{'='*60}")
                job_logger.info(f"PIPELINE COMPLETED SUCCESSFULLY")
                job_logger.info(f"Total passes completed: {len(result.passes_completed)}")
                job_logger.info(f"Total files processed: {len(job_request.source_files)}")
                job_logger.info(f"{'='*60}")

        except Exception as e:
            logger.error(f"Pipeline error for job {job_id}: {str(e)}")
            job_logger.error(f"\n{'='*60}")
            job_logger.error(f"PIPELINE ERROR: {str(e)}")
            job_logger.error(f"{'='*60}")
            result.status = JobStatus.FAILED
            result.error = str(e)

        finally:
            # Finalize result
            result.completed_at = datetime.utcnow()
            result.duration_seconds = (result.completed_at - started_at).total_seconds()

            job_logger.info(f"Pipeline duration: {result.duration_seconds:.2f} seconds")
            job_logger.info(f"Final status: {result.status}")

            # Close job logger handlers
            for handler in job_logger.handlers:
                handler.close()
                job_logger.removeHandler(handler)

            # Remove job file handler from ttrpg logger to prevent memory leak
            ttrpg_logger = logging.getLogger("ttrpg")
            if job_file_handler in ttrpg_logger.handlers:
                ttrpg_logger.removeHandler(job_file_handler)
                job_file_handler.close()

            await self.job_tracker.complete_job(job_id, result.status)

        return result

    async def _execute_pass_for_sources(
        self,
        pass_type: PassType,
        job_id: str,
        source_files: List[str],
        env: str,
        job_logger: logging.Logger
    ) -> List[PassResult]:
        """
        Execute a pass for all source files.

        Args:
            pass_type: Pass to execute
            job_id: Job ID
            source_files: List of source file paths
            env: Environment
            job_logger: Job-specific logger

        Returns:
            List of PassResult for each file
        """
        results = []

        # Execute pass for each file
        for i, source_file in enumerate(source_files, 1):
            job_logger.info(f"Processing file {i}/{len(source_files)}: {Path(source_file).name}")
            pass_result = await self._execute_single_pass(
                pass_type, job_id, source_file, env, job_logger
            )
            if pass_result.status == JobStatus.COMPLETED:
                job_logger.info(f"  ✓ Success ({pass_result.duration_seconds:.2f}s)")
            else:
                job_logger.error(f"  ✗ Failed: {pass_result.error}")
            results.append(pass_result)

        return results

    async def _execute_single_pass(
        self,
        pass_type: PassType,
        job_id: str,
        source_file: str,
        env: str,
        job_logger: logging.Logger
    ) -> PassResult:
        """
        Execute a single pass for one file.

        Args:
            pass_type: Pass to execute
            job_id: Job ID
            source_file: Source file path
            env: Environment
            job_logger: Job-specific logger

        Returns:
            PassResult with execution details
        """
        started_at = datetime.utcnow()

        logger.debug(f"Executing {pass_type.value} for {Path(source_file).name}")

        pass_result = PassResult(
            pass_type=pass_type,
            status=JobStatus.RUNNING,
            source_file=source_file,
            started_at=started_at
        )

        try:
            # Get executor function
            executor_map = self.executor.get_executor_map()
            executor_func = executor_map.get(pass_type)

            if not executor_func:
                raise ValueError(f"No executor for {pass_type.value}")

            # Create job path
            job_path = Path(config.get_artifacts_path(env, job_id))
            job_path.mkdir(parents=True, exist_ok=True)

            job_logger.debug(f"  Artifacts path: {job_path}")

            # Execute pass
            output = await executor_func(
                source_file=source_file,
                job_id=job_id,
                job_path=job_path,
                env=env
            )

            pass_result.status = JobStatus.COMPLETED if output.get("success", True) else JobStatus.FAILED
            pass_result.output = output
            pass_result.error = output.get("error_message")

            if pass_result.error:
                job_logger.error(f"  Pass returned error: {pass_result.error}")

        except Exception as e:
            logger.error(f"Pass {pass_type.value} failed for {source_file}: {str(e)}")
            job_logger.error(f"  Exception in pass execution: {str(e)}")
            pass_result.status = JobStatus.FAILED
            pass_result.error = str(e)

        finally:
            pass_result.completed_at = datetime.utcnow()
            pass_result.duration_seconds = (pass_result.completed_at - started_at).total_seconds()

        return pass_result

    def _get_pass_sequence(
        self,
        start_pass: PassType,
        end_pass: PassType
    ) -> List[PassType]:
        """
        Get ordered sequence of passes to execute.

        Args:
            start_pass: First pass
            end_pass: Last pass

        Returns:
            List of PassType in execution order
        """
        all_passes = [
            PassType.PASS_0,
            PassType.PASS_A,
            PassType.PASS_B,
            PassType.PASS_C,
            PassType.PASS_D,
            PassType.PASS_E,
            PassType.PASS_F,
            PassType.PASS_G
        ]

        start_idx = all_passes.index(start_pass)
        end_idx = all_passes.index(end_pass) + 1

        return all_passes[start_idx:end_idx]

    def _generate_job_id(self, trigger_mode: TriggerMode) -> str:
        """Generate unique job ID."""
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        short_uuid = str(uuid.uuid4())[:8]
        return f"{trigger_mode.value}_{timestamp}_{short_uuid}"

    async def get_job_status(self, job_id: str) -> Optional[JobResult]:
        """Get status of a job."""
        # Check if job is active
        job = await self.job_tracker.get_active_job(job_id)
        if job:
            return JobResult(
                job_id=job_id,
                status=JobStatus.RUNNING,
                trigger_mode=job.trigger_mode,
                source_files=job.source_files,
                env=job.env,
                created_at=job.created_at
            )

        # Check if job is queued
        job = await self.job_queue.get_job(job_id)
        if job:
            return JobResult(
                job_id=job_id,
                status=JobStatus.QUEUED,
                trigger_mode=job.trigger_mode,
                source_files=job.source_files,
                env=job.env,
                created_at=job.created_at
            )

        return None

    async def cancel_job(self, job_id: str) -> bool:
        """
        Cancel a job.

        Returns:
            True if cancelled, False if not found or already completed
        """
        # Remove from queue if queued
        removed = await self.job_queue.remove(job_id)
        if removed:
            logger.info(f"Cancelled queued job {job_id}")
            return True

        # Cancel active pipeline task
        task = self._active_pipelines.get(job_id)
        if task and not task.done():
            task.cancel()
            logger.info(f"Cancelled active job {job_id}")
            return True

        return False