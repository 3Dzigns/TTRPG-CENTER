#!/usr/bin/env python3
"""
async_worker_base.py - Base class for all async pipeline workers
=================================================================

Provides common functionality for polling job queues, claiming jobs,
routing to next stages, and error handling.
"""

from __future__ import annotations

import argparse
import json
import logging
import signal
import sys
import time
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from async_job_utils import (
    add_error,
    add_warning,
    claim_job,
    complete_job_stage,
    ensure_directory,
    find_queued_jobs,
    get_job_status_path,
    get_worker_id,
    load_json,
    mark_stage_completed,
    release_job,
    update_job_status,
    utc_now,
    write_json_atomic,
)
from path_utils import resolve_transfer_path


class AsyncWorkerBase(ABC):
    """
    Base class for all async pipeline workers.

    Subclasses must implement:
        - _process_job(self, job_dir: Path, status: Dict) -> bool
        - stage_name (class attribute)
    """

    stage_name: str = None  # Override in subclass

    def __init__(
        self,
        jobs_root: Optional[Path] = None,
        log_dir: Optional[Path] = None,
        poll_interval: int = 5,
        log_level: str = "INFO",
        routing_config_path: Optional[Path] = None,
    ) -> None:
        """
        Initialize async worker.

        Args:
            jobs_root: Root directory for all job queues
            log_dir: Directory for worker logs
            poll_interval: Seconds between queue polls
            log_level: Logging level (DEBUG, INFO, WARNING, ERROR)
            routing_config_path: Path to pipeline_routes.json
        """
        if self.stage_name is None:
            raise ValueError("Subclass must define 'stage_name' attribute")

        self.jobs_root = jobs_root or resolve_transfer_path("jobs")
        self.stage_queue_dir = ensure_directory(self.jobs_root / self.stage_name)
        self.log_dir = ensure_directory(log_dir or resolve_transfer_path(f"Logs/{self.stage_name}"))
        self.poll_interval = poll_interval
        self.worker_id = get_worker_id()
        self.shutdown_requested = False

        # Load routing configuration
        self.routing_config_path = routing_config_path or Path(__file__).parent / "pipeline_routes.json"
        self.routing_config = self._load_routing_config()
        self.stage_config = self._get_stage_config()

        # Setup logging
        logging.basicConfig(
            level=getattr(logging, log_level.upper(), logging.INFO),
            format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
        )
        self.logger = logging.getLogger(f"{self.stage_name}_worker")

        # Setup signal handlers for graceful shutdown
        signal.signal(signal.SIGTERM, self._signal_handler)
        signal.signal(signal.SIGINT, self._signal_handler)

        self.logger.info(
            f"Worker starting (stage={self.stage_name}, queue={self.stage_queue_dir}, poll_interval={self.poll_interval}s, worker_id={self.worker_id})"
        )

        # Worker stats
        self.stats = {
            "jobs_processed": 0,
            "jobs_failed": 0,
            "started_at": utc_now(),
            "last_heartbeat": utc_now(),
        }

    def _signal_handler(self, signum, frame) -> None:
        """Handle shutdown signals gracefully."""
        self.logger.info(f"Received signal {signum}, initiating graceful shutdown...")
        self.shutdown_requested = True

    def _load_routing_config(self) -> Dict[str, Any]:
        """Load pipeline routing configuration from JSON."""
        if not self.routing_config_path.exists():
            raise FileNotFoundError(f"Routing config not found: {self.routing_config_path}")

        with self.routing_config_path.open("r", encoding="utf-8") as f:
            return json.load(f)

    def _get_stage_config(self) -> Dict[str, Any]:
        """Get configuration for this worker's stage from routing config."""
        for stage in self.routing_config.get("default_pipeline", []):
            if stage.get("stage") == self.stage_name:
                return stage

        raise ValueError(f"Stage '{self.stage_name}' not found in routing configuration")

    def _determine_next_stage(self, status: Dict[str, Any]) -> Optional[str]:
        """
        Determine next stage based on routing configuration.

        Args:
            status: Current job status dict

        Returns:
            Next stage name, "complete" if terminal, or None if failed
        """
        stage_cfg = self.stage_config

        # Check if this is a terminal stage
        if stage_cfg.get("terminal"):
            return "complete"

        # Check for routing rules (conditional routing)
        routing_rules = stage_cfg.get("routing_rules")
        if routing_rules:
            for rule in routing_rules:
                condition = rule.get("condition", {})
                # Simple condition matching: all key-value pairs must match
                if self._check_condition(status, condition):
                    next_stage = rule.get("next")
                    if rule.get("terminal"):
                        return "complete" if next_stage == "complete" else None
                    return next_stage

        # Default: use "next" field
        return stage_cfg.get("next")

    def _check_condition(self, status: Dict[str, Any], condition: Dict[str, Any]) -> bool:
        """
        Check if job status matches routing condition.

        Args:
            status: Job status dict
            condition: Condition dict from routing rules

        Returns:
            True if all conditions match
        """
        for key, expected_value in condition.items():
            actual_value = status.get(key)

            # Handle pipe-separated OR conditions (e.g., "valid|mismatch")
            if isinstance(expected_value, str) and "|" in expected_value:
                if actual_value not in expected_value.split("|"):
                    return False
            elif actual_value != expected_value:
                return False

        return True

    def _update_heartbeat(self) -> None:
        """Update worker heartbeat timestamp."""
        self.stats["last_heartbeat"] = utc_now()

        # Write heartbeat file for monitoring
        heartbeat_path = self.log_dir / "heartbeat.json"
        heartbeat_data = {
            "worker_id": self.worker_id,
            "stage_name": self.stage_name,
            "last_heartbeat": self.stats["last_heartbeat"],
            "jobs_processed": self.stats["jobs_processed"],
            "jobs_failed": self.stats["jobs_failed"],
            "started_at": self.stats["started_at"],
        }
        write_json_atomic(heartbeat_path, heartbeat_data)

    def _claim_next_job(self) -> Optional[Path]:
        """
        Find and claim the next available job in queue.

        Returns:
            Path to claimed job directory, or None if no jobs available
        """
        queued_jobs = find_queued_jobs(self.stage_queue_dir)

        for job_dir in queued_jobs:
            if claim_job(job_dir, self.worker_id):
                self.logger.info(f"Claimed job {job_dir.name}")
                return job_dir

        return None

    def _move_job_to_next_stage(self, job_dir: Path, status: Dict[str, Any], next_stage: str) -> bool:
        """
        Move job directory to next stage's queue.

        Args:
            job_dir: Current job directory
            status: Job status dict
            next_stage: Name of next stage

        Returns:
            True if successful
        """
        if next_stage == "complete":
            # Job is done, just mark as complete
            complete_job_stage(job_dir, next_stage="complete")
            self.logger.info(f"Job {job_dir.name} completed successfully")
            return True

        try:
            # Remove all marker files before moving to prevent stale markers
            claimed_marker = job_dir / "claimed.marker"
            queued_marker = job_dir / "queued.marker"
            if claimed_marker.exists():
                claimed_marker.unlink()
            if queued_marker.exists():
                queued_marker.unlink()

            # Create job directory in next stage queue
            next_stage_dir = ensure_directory(self.jobs_root / next_stage)
            next_job_dir = next_stage_dir / job_dir.name

            # Move entire job directory to next stage
            import shutil
            shutil.move(str(job_dir), str(next_job_dir))

            # Update status with new stage
            status_path = get_job_status_path(next_job_dir)
            status = update_job_status(status, {
                "current_stage": next_stage,
                "status": "queued",
                "worker_id": None,
                "claimed_at": None,
            })
            write_json_atomic(status_path, status)

            # Create queued marker in new location (after move, so only this marker exists)
            (next_job_dir / "queued.marker").touch()

            self.logger.info(f"Job {job_dir.name} moved to {next_stage} queue")
            return True

        except Exception as e:
            self.logger.error(f"Failed to move job to {next_stage}: {e}")
            return False

    @abstractmethod
    def _process_job(self, job_dir: Path, status: Dict[str, Any]) -> bool:
        """
        Process a single job. MUST be implemented by subclass.

        Args:
            job_dir: Path to job directory
            status: Current job status dict

        Returns:
            True if processing succeeded, False otherwise
        """
        raise NotImplementedError("Subclass must implement _process_job()")

    def _handle_job(self, job_dir: Path) -> bool:
        """
        Handle a claimed job: load status, process, route to next stage.

        Args:
            job_dir: Path to claimed job directory

        Returns:
            True if job was successfully processed and routed
        """
        try:
            # Load job status
            status_path = get_job_status_path(job_dir)
            if not status_path.exists():
                self.logger.error(f"Job {job_dir.name} has no status.json file")
                return False

            status = load_json(status_path)

            # Mark job as in progress
            status = update_job_status(status, {
                "status": "in_progress",
                "started_at": utc_now(),
            })
            write_json_atomic(status_path, status)

            # Process the job (subclass implementation)
            start_time = time.time()
            success = self._process_job(job_dir, status)
            duration = time.time() - start_time

            # Reload status in case _process_job modified it
            status = load_json(status_path)

            if success:
                # Mark stage as completed
                status = mark_stage_completed(status, self.stage_name, duration_seconds=duration)
                write_json_atomic(status_path, status)

                # Determine next stage
                next_stage = self._determine_next_stage(status)

                if next_stage:
                    # Move to next stage
                    success = self._move_job_to_next_stage(job_dir, status, next_stage)
                else:
                    # Job failed routing
                    self.logger.error(f"Job {job_dir.name} has no valid next stage")
                    status = add_error(status, f"Failed to determine next stage after {self.stage_name}")
                    status = update_job_status(status, {"status": "failed"})
                    write_json_atomic(status_path, status)
                    success = False

            if not success:
                self.logger.error(f"Job {job_dir.name} failed processing in {self.stage_name}")
                # Release job back to queue for retry
                release_job(job_dir)
                self.stats["jobs_failed"] += 1

            return success

        except Exception as e:
            self.logger.exception(f"Unexpected error handling job {job_dir.name}: {e}")
            # Try to release job back to queue
            try:
                release_job(job_dir)
            except Exception as release_error:
                self.logger.error(f"Failed to release job after error: {release_error}")
            return False

    def run(self, once: bool = False) -> None:
        """
        Run the worker loop.

        Args:
            once: If True, process one job and exit (for testing)
        """
        self.logger.info(f"Worker loop starting (stage={self.stage_name})")

        while not self.shutdown_requested:
            try:
                # Update heartbeat
                self._update_heartbeat()

                # Try to claim a job
                job_dir = self._claim_next_job()

                if job_dir is None:
                    if once:
                        self.logger.debug("No jobs available, exiting (--once mode)")
                        break

                    # No jobs available, sleep and continue
                    time.sleep(self.poll_interval)
                    continue

                # Process the job
                success = self._handle_job(job_dir)

                if success:
                    self.stats["jobs_processed"] += 1
                    self.logger.info(f"Job {job_dir.name} completed successfully (total: {self.stats['jobs_processed']})")
                else:
                    self.logger.warning(f"Job {job_dir.name} failed")

                if once:
                    self.logger.debug("Exiting after processing one job (--once mode)")
                    break

            except Exception as e:
                self.logger.exception(f"Unexpected error in worker loop: {e}")
                if once:
                    raise
                # Sleep briefly before retrying
                time.sleep(self.poll_interval)

        self.logger.info(f"Worker shutting down (processed={self.stats['jobs_processed']}, failed={self.stats['jobs_failed']})")

    @classmethod
    def main(cls) -> None:
        """Entry point for running worker from command line."""
        parser = argparse.ArgumentParser(
            description=f"{cls.stage_name} async worker for TTRPG ingestion pipeline"
        )
        parser.add_argument(
            "--jobs-dir",
            type=Path,
            help="Root directory for job queues (default: /Transfer_Station/jobs)",
        )
        parser.add_argument(
            "--log-dir",
            type=Path,
            help=f"Directory for worker logs (default: /Transfer_Station/Logs/{cls.stage_name})",
        )
        parser.add_argument(
            "--poll-interval",
            type=int,
            default=5,
            help="Seconds between queue polls (default: 5)",
        )
        parser.add_argument(
            "--log-level",
            choices=["DEBUG", "INFO", "WARNING", "ERROR"],
            default="INFO",
            help="Logging level (default: INFO)",
        )
        parser.add_argument(
            "--once",
            action="store_true",
            help="Process one job and exit (for testing)",
        )
        args = parser.parse_args()

        worker = cls(
            jobs_root=args.jobs_dir,
            log_dir=args.log_dir,
            poll_interval=args.poll_interval,
            log_level=args.log_level,
        )
        worker.run(once=args.once)


if __name__ == "__main__":
    # This should never be run directly, only subclasses
    raise RuntimeError("AsyncWorkerBase cannot be run directly, use a subclass worker")
