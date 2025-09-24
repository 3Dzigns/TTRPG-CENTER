"""
Pass 0 — Preflight & De-dup

Compute file_sha, page count; short-circuit if identical to prior ingestion.
MVP v2 requirement: Pass 0→G pipeline with preflight checks.
"""

from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, Tuple

from .logging import get_logger
from .environment_isolation import get_environment_validator

logger = get_logger(__name__)


class PreflightResult:
    """Result of preflight checks."""

    def __init__(self, should_skip: bool, reason: str = "", file_sha: str = "",
                 page_count: int = 0, existing_job_id: str = ""):
        self.should_skip = should_skip
        self.reason = reason
        self.file_sha = file_sha
        self.page_count = page_count
        self.existing_job_id = existing_job_id


def compute_file_sha(file_path: Path) -> str:
    """
    Compute SHA-256 hash of file.

    Args:
        file_path: Path to file to hash

    Returns:
        Hex string of SHA-256 hash

    Raises:
        OSError: If file cannot be read
    """
    logger.info(f"Computing SHA-256 for {file_path}")

    sha256_hash = hashlib.sha256()

    with open(file_path, "rb") as f:
        # Read file in chunks to handle large files
        for chunk in iter(lambda: f.read(8192), b""):
            sha256_hash.update(chunk)

    file_sha = sha256_hash.hexdigest()
    logger.debug(f"File SHA-256: {file_sha}")

    return file_sha


def get_pdf_page_count(file_path: Path) -> int:
    """
    Get page count from PDF file.

    Args:
        file_path: Path to PDF file

    Returns:
        Number of pages in PDF

    Raises:
        ValueError: If file is not a valid PDF or cannot be read
    """
    try:
        # Try to use PyPDF2/PyPDF4 for page count
        try:
            import PyPDF2
            with open(file_path, "rb") as f:
                reader = PyPDF2.PdfReader(f)
                page_count = len(reader.pages)
                logger.debug(f"PDF page count (PyPDF2): {page_count}")
                return page_count
        except ImportError:
            logger.debug("PyPDF2 not available, trying alternative method")

        # Alternative: count pages using basic PDF parsing
        with open(file_path, "rb") as f:
            content = f.read()

        # Count occurrences of /Type /Page
        page_count = content.count(b"/Type /Page")
        if page_count == 0:
            # Fallback: count page objects
            page_count = content.count(b"obj") // 10  # Rough estimate

        logger.debug(f"PDF page count (fallback): {page_count}")
        return max(1, page_count)  # At least 1 page

    except Exception as e:
        logger.error(f"Failed to get page count for {file_path}: {str(e)}")
        raise ValueError(f"Cannot determine page count: {str(e)}")


def check_existing_ingestion(file_sha: str, page_count: int, env_root: Path) -> Optional[str]:
    """
    Check if file has already been ingested with same SHA and page count.

    Args:
        file_sha: SHA-256 hash of file
        page_count: Number of pages in PDF
        env_root: Environment root directory

    Returns:
        Existing job_id if found, None otherwise
    """
    artifacts_dir = env_root / "artifacts"

    if not artifacts_dir.exists():
        logger.debug("No artifacts directory found, no prior ingestion")
        return None

    logger.info(f"Checking for existing ingestion: sha={file_sha[:12]}..., pages={page_count}")

    # Look through all job directories
    for job_dir in artifacts_dir.iterdir():
        if not job_dir.is_dir():
            continue

        manifest_path = job_dir / "manifest.json"
        if not manifest_path.exists():
            continue

        try:
            with open(manifest_path, "r") as f:
                manifest = json.load(f)

            # Check if SHA and page count match
            if (manifest.get("source_file_sha") == file_sha and
                manifest.get("source_page_count") == page_count):

                job_id = manifest.get("job_id", job_dir.name)
                logger.info(f"Found matching ingestion: job_id={job_id}")
                return job_id

        except (json.JSONDecodeError, OSError) as e:
            logger.warning(f"Failed to read manifest in {job_dir}: {str(e)}")
            continue

    logger.info("No matching ingestion found")
    return None


def create_noop_job_record(file_path: Path, existing_job_id: str,
                          file_sha: str, page_count: int, env_root: Path) -> str:
    """
    Create a no-op job record for skipped ingestion.

    Args:
        file_path: Original file path
        existing_job_id: ID of existing job with same content
        file_sha: SHA-256 hash of file
        page_count: Page count
        env_root: Environment root directory

    Returns:
        New job_id for the no-op record
    """
    import uuid
    from datetime import datetime

    noop_job_id = f"noop-{uuid.uuid4().hex[:8]}"
    noop_job_dir = env_root / "artifacts" / noop_job_id
    noop_job_dir.mkdir(parents=True, exist_ok=True)

    noop_record = {
        "job_id": noop_job_id,
        "status": "skipped",
        "reason": "duplicate_content",
        "source_file": str(file_path),
        "source_file_sha": file_sha,
        "source_page_count": page_count,
        "existing_job_id": existing_job_id,
        "created_at": datetime.utcnow().isoformat(),
        "pass_0_preflight": {
            "duplicate_detected": True,
            "original_job": existing_job_id,
            "skip_reason": "Identical content already processed"
        }
    }

    # Write no-op manifest
    manifest_path = noop_job_dir / "manifest.json"
    with open(manifest_path, "w") as f:
        json.dump(noop_record, f, indent=2)

    logger.info(f"Created no-op job record: {noop_job_id}")
    return noop_job_id


def run_preflight_checks(file_path: Path) -> PreflightResult:
    """
    Run Pass 0 preflight checks for a file.

    Args:
        file_path: Path to file to check

    Returns:
        PreflightResult with skip decision and metadata

    Raises:
        OSError: If file cannot be accessed
        ValueError: If file is not valid
    """
    logger.info(f"Starting Pass 0 preflight checks for {file_path}")

    # Validate file exists and is readable
    if not file_path.exists():
        raise OSError(f"File does not exist: {file_path}")

    if not file_path.is_file():
        raise OSError(f"Path is not a file: {file_path}")

    # Get environment root for artifact checking
    env_validator = get_environment_validator()
    env_root = Path(env_validator.get_environment_root())

    try:
        # Compute file SHA
        file_sha = compute_file_sha(file_path)

        # Get page count (assuming PDF for now)
        if file_path.suffix.lower() == '.pdf':
            page_count = get_pdf_page_count(file_path)
        else:
            logger.warning(f"Non-PDF file: {file_path}, using page count = 1")
            page_count = 1

        # Check for existing ingestion
        existing_job_id = check_existing_ingestion(file_sha, page_count, env_root)

        if existing_job_id:
            # Create no-op record and skip
            noop_job_id = create_noop_job_record(
                file_path, existing_job_id, file_sha, page_count, env_root
            )

            return PreflightResult(
                should_skip=True,
                reason=f"Duplicate content (existing job: {existing_job_id})",
                file_sha=file_sha,
                page_count=page_count,
                existing_job_id=existing_job_id
            )

        else:
            # New content, proceed with ingestion
            logger.info(f"New content detected, proceeding with ingestion")
            return PreflightResult(
                should_skip=False,
                reason="New content",
                file_sha=file_sha,
                page_count=page_count
            )

    except Exception as e:
        logger.error(f"Preflight checks failed for {file_path}: {str(e)}")
        raise


def create_preflight_manifest(job_id: str, file_path: Path,
                             preflight_result: PreflightResult, env_root: Path) -> Dict[str, Any]:
    """
    Create initial manifest with preflight results.

    Args:
        job_id: Job identifier
        file_path: Source file path
        preflight_result: Results from preflight checks
        env_root: Environment root directory

    Returns:
        Initial manifest dictionary
    """
    manifest = {
        "job_id": job_id,
        "source_file": str(file_path),
        "source_file_sha": preflight_result.file_sha,
        "source_page_count": preflight_result.page_count,
        "created_at": datetime.utcnow().isoformat(),
        "status": "preflight_complete",
        "pass_0_preflight": {
            "file_sha": preflight_result.file_sha,
            "page_count": preflight_result.page_count,
            "duplicate_check": "passed" if not preflight_result.should_skip else "duplicate",
            "reason": preflight_result.reason,
            "completed_at": datetime.utcnow().isoformat()
        }
    }

    return manifest


if __name__ == "__main__":
    # Test with a sample file
    import sys
    if len(sys.argv) > 1:
        test_file = Path(sys.argv[1])
        result = run_preflight_checks(test_file)
        print(f"Preflight result: skip={result.should_skip}, reason={result.reason}")
        print(f"SHA: {result.file_sha}")
        print(f"Pages: {result.page_count}")