"""
Job submission helper for async unstructured processing.

This module creates job directories in Transfer_Station for the unstructured_job_worker
running in the unstructured container to claim and process.
"""

import json
import uuid
from pathlib import Path
from typing import Dict, Any, Optional, List

from time_utils import utc_now_isoformat


def create_job(
    document_path: str,
    output_dir: str,
    strategy: str = "hi_res",
    ocr_languages: Optional[List[str]] = None,
    max_pages: Optional[int] = None,
    jobs_root: str = "/Transfer_Station/jobs/unstructured"
) -> str:
    """
    Create async job for unstructured processing.

    The unstructured_job_worker.py running in the unstructured container will
    poll the jobs directory, claim this job, and process it locally (no HTTP).

    Args:
        document_path: Full path to document to process
        output_dir: Directory for output JSON files
        strategy: Unstructured partitioning strategy (hi_res, fast, ocr_only)
        ocr_languages: List of OCR language codes (default: ["eng"])
        max_pages: Maximum pages to process (None = all pages)
        jobs_root: Root directory for job queue

    Returns:
        job_id: UUID for tracking job status

    Creates:
        /Transfer_Station/jobs/unstructured/job_{uuid}/
          ├── manifest.json   # Job specification
          ├── status.json     # Current state
          └── queued.marker   # Signal for worker to claim
    """
    jobs_root = Path(jobs_root)
    job_id = f"job_{uuid.uuid4().hex[:12]}"
    job_dir = jobs_root / job_id

    # Create job directory
    job_dir.mkdir(parents=True, exist_ok=True)

    # Write manifest with job specification
    now_iso = utc_now_isoformat(with_z=True)

    manifest = {
        "job_id": job_id,
        "created_at": now_iso,
        "document_path": str(document_path),
        "output_dir": str(output_dir),
        "strategy": strategy,
        "ocr_languages": ocr_languages or ["eng"],
        "max_pages": max_pages,
        "stage": "pass_a"  # Initial stage for pipeline
    }

    manifest_path = job_dir / "manifest.json"
    with open(manifest_path, 'w', encoding='utf-8') as f:
        json.dump(manifest, f, indent=2)

    # Write initial status
    status = {
        "job_id": job_id,
        "state": "queued",
        "created_at": now_iso,
        "worker": None,
        "progress": {},
        "errors": [],
        "output_path": None,
        "statistics": {}
    }

    status_path = job_dir / "status.json"
    with open(status_path, 'w', encoding='utf-8') as f:
        json.dump(status, f, indent=2)

    # Create queued marker (atomic signal for worker)
    marker_path = job_dir / "queued.marker"
    marker_path.touch()

    return job_id


def get_job_dir(job_id: str, jobs_root: str = "/Transfer_Station/jobs/unstructured") -> Path:
    """Get path to job directory."""
    return Path(jobs_root) / job_id


def read_job_status(job_id: str, jobs_root: str = "/Transfer_Station/jobs/unstructured") -> Dict[str, Any]:
    """Read current job status from status.json."""
    job_dir = get_job_dir(job_id, jobs_root)
    status_path = job_dir / "status.json"

    if not status_path.exists():
        raise FileNotFoundError(f"Job {job_id} status file not found")

    with open(status_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def read_job_manifest(job_id: str, jobs_root: str = "/Transfer_Station/jobs/unstructured") -> Dict[str, Any]:
    """Read job manifest from manifest.json."""
    job_dir = get_job_dir(job_id, jobs_root)
    manifest_path = job_dir / "manifest.json"

    if not manifest_path.exists():
        raise FileNotFoundError(f"Job {job_id} manifest file not found")

    with open(manifest_path, 'r', encoding='utf-8') as f:
        return json.load(f)
