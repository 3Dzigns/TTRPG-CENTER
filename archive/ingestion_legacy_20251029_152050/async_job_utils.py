#!/usr/bin/env python3
"""
async_job_utils.py - Shared utilities for async pipeline job management
========================================================================

Provides common functionality for job queue operations, status management,
and inter-worker communication via the Transfer Station filesystem.
"""

from __future__ import annotations

import json
import socket
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
import fcntl


def utc_now() -> str:
    """Return current UTC timestamp in ISO 8601 format with 'Z' suffix."""
    return datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')


def load_json(path: Path) -> Dict[str, Any]:
    """Load JSON file with file locking for concurrent access safety."""
    with path.open("r", encoding="utf-8") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_SH)
        try:
            return json.load(handle)
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def write_json_atomic(path: Path, payload: Dict[str, Any]) -> None:
    """
    Atomically write JSON file with file locking.

    Uses temp file + rename for atomicity to prevent partial reads.
    """
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    with tmp_path.open("w", encoding="utf-8") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        try:
            json.dump(payload, handle, indent=2, ensure_ascii=False)
            handle.flush()
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
    tmp_path.replace(path)


def ensure_directory(path: Path) -> Path:
    """Create directory if it doesn't exist, return the path."""
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_worker_id() -> str:
    """Generate unique worker identifier: hostname:pid"""
    return f"{socket.gethostname()}:{os.getpid()}"


def create_job_directory(jobs_root: Path, stage_name: str, job_id: str) -> Path:
    """Create job directory for a specific stage."""
    job_dir = jobs_root / stage_name / job_id
    ensure_directory(job_dir)
    return job_dir


def get_job_status_path(job_dir: Path) -> Path:
    """Get path to status.json for a job."""
    return job_dir / "status.json"


def get_job_manifest_path(job_dir: Path) -> Path:
    """Get path to manifest.json for a job."""
    return job_dir / "manifest.json"


def create_marker_file(job_dir: Path, marker_name: str) -> Path:
    """Create empty marker file (e.g., 'queued.marker', 'claimed.marker')."""
    marker_path = job_dir / marker_name
    marker_path.touch()
    return marker_path


def remove_marker_file(job_dir: Path, marker_name: str) -> None:
    """Remove marker file if it exists."""
    marker_path = job_dir / marker_name
    if marker_path.exists():
        marker_path.unlink()


def has_marker(job_dir: Path, marker_name: str) -> bool:
    """Check if marker file exists."""
    return (job_dir / marker_name).exists()


def initialize_job_status(
    job_id: str,
    source_file: str,
    current_stage: str,
    next_stage: Optional[str] = None
) -> Dict[str, Any]:
    """
    Create initial job status structure.

    Args:
        job_id: Unique job identifier
        source_file: Path to source PDF file
        current_stage: Initial pipeline stage
        next_stage: Next stage to route to (if known)

    Returns:
        Job status dictionary
    """
    return {
        "job_id": job_id,
        "source_file": source_file,
        "current_stage": current_stage,
        "next_stage": next_stage,
        "status": "queued",
        "created_at": utc_now(),
        "updated_at": utc_now(),
        "started_at": None,
        "completed_at": None,
        "worker_id": None,
        "claimed_at": None,
        "stages_completed": [],
        "stage_history": {},
        "errors": [],
        "warnings": []
    }


def update_job_status(
    status: Dict[str, Any],
    updates: Dict[str, Any],
    add_to_history: bool = False
) -> Dict[str, Any]:
    """
    Update job status dict with new values.

    Args:
        status: Current status dict
        updates: Dict of fields to update
        add_to_history: If True, record current stage in stage_history

    Returns:
        Updated status dict
    """
    if add_to_history and status.get("current_stage"):
        stage_name = status["current_stage"]
        if stage_name not in status.get("stage_history", {}):
            status.setdefault("stage_history", {})[stage_name] = {
                "status": status.get("status", "unknown"),
                "started_at": status.get("started_at"),
                "completed_at": None,
                "duration_seconds": None,
                "worker": status.get("worker_id"),
                "errors": [],
                "warnings": []
            }

    status.update(updates)
    status["updated_at"] = utc_now()
    return status


def mark_stage_completed(
    status: Dict[str, Any],
    stage_name: str,
    duration_seconds: Optional[float] = None,
    metrics: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Mark a pipeline stage as completed in job status.

    Args:
        status: Job status dict
        stage_name: Name of completed stage
        duration_seconds: Time taken for stage
        metrics: Optional stage-specific metrics

    Returns:
        Updated status dict
    """
    if stage_name not in status.get("stages_completed", []):
        status.setdefault("stages_completed", []).append(stage_name)

    history_entry = status.setdefault("stage_history", {}).setdefault(stage_name, {})
    history_entry.update({
        "status": "completed",
        "completed_at": utc_now(),
        "duration_seconds": duration_seconds,
        "metrics": metrics or {}
    })

    return status


def add_error(status: Dict[str, Any], error_msg: str, stage: Optional[str] = None) -> Dict[str, Any]:
    """Add error message to job status."""
    error_entry = {
        "timestamp": utc_now(),
        "message": error_msg,
        "stage": stage or status.get("current_stage", "unknown")
    }
    status.setdefault("errors", []).append(error_entry)

    # Also add to stage history if stage is active
    if stage and stage in status.get("stage_history", {}):
        status["stage_history"][stage].setdefault("errors", []).append(error_msg)

    return status


def add_warning(status: Dict[str, Any], warning_msg: str, stage: Optional[str] = None) -> Dict[str, Any]:
    """Add warning message to job status."""
    warning_entry = {
        "timestamp": utc_now(),
        "message": warning_msg,
        "stage": stage or status.get("current_stage", "unknown")
    }
    status.setdefault("warnings", []).append(warning_entry)

    # Also add to stage history if stage is active
    if stage and stage in status.get("stage_history", {}):
        status["stage_history"][stage].setdefault("warnings", []).append(warning_msg)

    return status


def find_queued_jobs(stage_dir: Path) -> List[Path]:
    """
    Find all queued job directories for a stage.

    Returns list of job directories sorted by creation time (oldest first).
    """
    if not stage_dir.exists():
        return []

    queued_jobs = []
    for job_dir in stage_dir.iterdir():
        if not job_dir.is_dir():
            continue

        # Check for queued.marker
        if has_marker(job_dir, "queued.marker"):
            queued_jobs.append(job_dir)

    # Sort by directory creation time (oldest first)
    queued_jobs.sort(key=lambda p: p.stat().st_ctime)
    return queued_jobs


def claim_job(job_dir: Path, worker_id: str) -> bool:
    """
    Attempt to claim a queued job.

    Returns True if successfully claimed, False if already claimed.
    Uses marker files for atomic claiming.
    """
    queued_marker = job_dir / "queued.marker"
    claimed_marker = job_dir / "claimed.marker"

    if not queued_marker.exists():
        return False  # Not queued

    if claimed_marker.exists():
        return False  # Already claimed

    try:
        # Atomic claim: create claimed.marker and remove queued.marker
        claimed_marker.touch()
        queued_marker.unlink()

        # Update status.json
        status_path = get_job_status_path(job_dir)
        if status_path.exists():
            status = load_json(status_path)
            status = update_job_status(status, {
                "status": "claimed",
                "worker_id": worker_id,
                "claimed_at": utc_now()
            })
            write_json_atomic(status_path, status)

        return True
    except Exception:
        return False


def release_job(job_dir: Path) -> None:
    """
    Release a claimed job back to queued state.
    Used when worker fails to process job.
    """
    claimed_marker = job_dir / "claimed.marker"
    queued_marker = job_dir / "queued.marker"

    if claimed_marker.exists():
        claimed_marker.unlink()

    queued_marker.touch()

    # Update status
    status_path = get_job_status_path(job_dir)
    if status_path.exists():
        status = load_json(status_path)
        status = update_job_status(status, {
            "status": "queued",
            "worker_id": None,
            "claimed_at": None
        })
        write_json_atomic(status_path, status)


def complete_job_stage(job_dir: Path, next_stage: Optional[str] = None) -> None:
    """
    Mark current stage as complete and optionally move to next stage queue.

    If next_stage is None or "complete", marks job as fully completed.
    """
    claimed_marker = job_dir / "claimed.marker"

    # Remove claimed marker
    if claimed_marker.exists():
        claimed_marker.unlink()

    # Update status
    status_path = get_job_status_path(job_dir)
    if status_path.exists():
        status = load_json(status_path)

        current_stage = status.get("current_stage")
        if current_stage:
            # Calculate duration if started_at exists
            duration = None
            if status.get("started_at"):
                start_time = datetime.fromisoformat(status["started_at"].replace('Z', '+00:00'))
                duration = (datetime.now(timezone.utc) - start_time).total_seconds()

            status = mark_stage_completed(status, current_stage, duration_seconds=duration)

        if next_stage and next_stage != "complete":
            # Job continues to next stage
            status = update_job_status(status, {
                "current_stage": next_stage,
                "next_stage": next_stage,
                "status": "queued"
            })
        else:
            # Job is fully complete
            status = update_job_status(status, {
                "current_stage": "complete",
                "next_stage": None,
                "status": "completed",
                "completed_at": utc_now()
            })

        write_json_atomic(status_path, status)


import os  # For get_worker_id
