"""
Job polling helper for async unstructured processing.

This module polls job status until completion or timeout.
"""

import time
import logging
from pathlib import Path
from typing import Dict, Any

from submit_unstructured_job import read_job_status, get_job_dir


logger = logging.getLogger(__name__)


class JobTimeoutError(Exception):
    """Raised when job exceeds timeout waiting for completion."""
    pass


class JobFailedError(Exception):
    """Raised when job fails with errors."""
    pass


def wait_for_completion(
    job_id: str,
    timeout: int = 3600,
    poll_interval: int = 5,
    jobs_root: str = "/Transfer_Station/jobs/unstructured"
) -> Dict[str, Any]:
    """
    Poll job status until completion or timeout.

    Args:
        job_id: Job UUID to poll
        timeout: Maximum seconds to wait (default: 3600 = 1 hour)
        poll_interval: Seconds between status checks (default: 5)
        jobs_root: Root directory for job queue

    Returns:
        result: Job result dictionary with:
            - job_id: Job UUID
            - output_path: Path to output JSON file
            - statistics: Processing statistics (pages, elements, duration, etc.)
            - duration: Total processing time in seconds

    Raises:
        JobTimeoutError: If job doesn't complete within timeout
        JobFailedError: If job fails with errors
        FileNotFoundError: If job status file not found
    """
    start_time = time.time()
    last_state = None

    logger.info(f"Waiting for job {job_id} completion (timeout: {timeout}s, poll: {poll_interval}s)")

    while True:
        elapsed = time.time() - start_time

        # Check timeout
        if elapsed > timeout:
            raise JobTimeoutError(
                f"Job {job_id} exceeded timeout of {timeout}s (elapsed: {elapsed:.1f}s)"
            )

        # Read current status
        try:
            status = read_job_status(job_id, jobs_root)
        except FileNotFoundError as e:
            raise JobFailedError(f"Job {job_id} status file not found - job may have been deleted") from e

        state = status.get("state")
        worker = status.get("worker")
        progress = status.get("progress", {})

        # Log state changes
        if state != last_state:
            logger.info(f"Job {job_id} state: {state} (worker: {worker}, progress: {progress})")
            last_state = state

        # Check completion
        if state == "completed":
            result = {
                "job_id": job_id,
                "output_path": status.get("output_path"),
                "statistics": status.get("statistics", {}),
                "duration": elapsed
            }

            logger.info(
                f"Job {job_id} completed successfully in {elapsed:.1f}s "
                f"(output: {result['output_path']})"
            )

            return result

        # Check failure
        elif state == "failed":
            errors = status.get("errors", ["Unknown error"])
            error_msg = "; ".join(errors) if isinstance(errors, list) else str(errors)

            logger.error(f"Job {job_id} failed: {error_msg}")

            raise JobFailedError(
                f"Job {job_id} failed after {elapsed:.1f}s: {error_msg}"
            )

        # Sleep before next poll
        time.sleep(poll_interval)


def check_job_status(
    job_id: str,
    jobs_root: str = "/Transfer_Station/jobs/unstructured"
) -> Dict[str, Any]:
    """
    Check current job status without waiting.

    Args:
        job_id: Job UUID to check
        jobs_root: Root directory for job queue

    Returns:
        status: Current job status dictionary

    Raises:
        FileNotFoundError: If job status file not found
    """
    return read_job_status(job_id, jobs_root)


def is_job_complete(
    job_id: str,
    jobs_root: str = "/Transfer_Station/jobs/unstructured"
) -> bool:
    """
    Check if job is in completed state.

    Args:
        job_id: Job UUID to check
        jobs_root: Root directory for job queue

    Returns:
        True if job state is "completed", False otherwise
    """
    try:
        status = read_job_status(job_id, jobs_root)
        return status.get("state") == "completed"
    except FileNotFoundError:
        return False


def is_job_failed(
    job_id: str,
    jobs_root: str = "/Transfer_Station/jobs/unstructured"
) -> bool:
    """
    Check if job is in failed state.

    Args:
        job_id: Job UUID to check
        jobs_root: Root directory for job queue

    Returns:
        True if job state is "failed", False otherwise
    """
    try:
        status = read_job_status(job_id, jobs_root)
        return status.get("state") == "failed"
    except FileNotFoundError:
        return False
