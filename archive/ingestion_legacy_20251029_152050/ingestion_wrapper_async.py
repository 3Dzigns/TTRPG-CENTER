#!/usr/bin/env python3
"""
ingestion_wrapper_async.py - Simplified async job queue wrapper
================================================================

Fire-and-forget wrapper that ONLY queues ingestion jobs.
Does NOT orchestrate, does NOT wait for completion.

Usage:
    python ingestion_wrapper_async.py --source /path/to/file.pdf
    python ingestion_wrapper_async.py --source /path/to/file.pdf --force-reprocess

Architecture:
    1. Validates source file exists
    2. Generates job_id from filename + timestamp
    3. Creates job directory in gate_0_hash queue
    4. Initializes status.json with job metadata
    5. Creates queued.marker to signal workers
    6. Exits immediately

Workers poll queues and process jobs asynchronously.
Monitor progress via job status files or pipeline_monitor.py.
"""

from __future__ import annotations

import argparse
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from async_job_utils import (
    create_job_directory,
    create_marker_file,
    ensure_directory,
    initialize_job_status,
    write_json_atomic,
    get_job_status_path,
)
from path_utils import resolve_transfer_path


def sanitize_job_id(filename: str) -> str:
    """
    Generate sanitized job ID from filename.

    Args:
        filename: Source filename (with or without extension)

    Returns:
        Sanitized job ID (lowercase, alphanumeric + underscores)
    """
    # Remove extension
    name_without_ext = Path(filename).stem

    # Convert to lowercase
    sanitized = name_without_ext.lower()

    # Replace spaces and special characters with underscores
    sanitized = re.sub(r'[^a-z0-9]+', '_', sanitized)

    # Remove leading/trailing underscores
    sanitized = sanitized.strip('_')

    # Collapse multiple underscores
    sanitized = re.sub(r'_+', '_', sanitized)

    # Limit length to 100 characters
    if len(sanitized) > 100:
        sanitized = sanitized[:100].rstrip('_')

    return sanitized


def generate_job_id(source_file: Path) -> str:
    """
    Generate deterministic job ID for a source file based on file path hash.

    This ensures:
    - Same source file always gets same job ID (no duplicates)
    - Different source files with same name get different IDs
    - Job can be tracked end-to-end across pipeline

    Args:
        source_file: Path to source file

    Returns:
        Job ID in format: {sanitized_filename}_{path_hash}
        Example: cyberpunk_v3_cp4110_core_rulebook_a3f2b1c4
    """
    import hashlib

    sanitized_name = sanitize_job_id(source_file.name)

    # Create deterministic hash from absolute file path
    path_str = str(source_file.absolute())
    path_hash = hashlib.sha256(path_str.encode('utf-8')).hexdigest()[:8]

    return f"{sanitized_name}_{path_hash}"


def queue_ingestion_job(
    source_file: Path,
    jobs_root: Path,
    force_reprocess: bool = False
) -> str:
    """
    Queue ingestion job by creating job directory and status.json.

    Args:
        source_file: Path to source file
        jobs_root: Root directory for job queues
        force_reprocess: If True, set rebuild_mode=True to force full reprocessing

    Returns:
        Job ID

    Raises:
        FileNotFoundError: If source file doesn't exist
        ValueError: If source file is not a regular file
    """
    # Validate source file
    if not source_file.exists():
        raise FileNotFoundError(f"Source file not found: {source_file}")

    if not source_file.is_file():
        raise ValueError(f"Source must be a regular file: {source_file}")

    # Generate deterministic job ID (same source = same ID)
    job_id = generate_job_id(source_file)

    # Check if job already exists in any queue
    if not force_reprocess:
        for queue_dir in jobs_root.iterdir():
            if queue_dir.is_dir():
                existing_job = queue_dir / job_id
                if existing_job.exists():
                    print(f"⚠️  Job already exists in {queue_dir.name} queue: {job_id}")
                    print(f"   Use --force-reprocess to requeue")
                    return job_id

    print(f"Queueing ingestion job: {job_id}")
    print(f"  Source: {source_file}")
    print(f"  Force reprocess: {force_reprocess}")

    # Create job directory in gate_0_hash queue (first stage)
    job_dir = create_job_directory(jobs_root, "gate_0_hash", job_id)

    # Initialize job status
    status = initialize_job_status(
        job_id=job_id,
        source_file=str(source_file.absolute()),
        current_stage="gate_0_hash",
        next_stage="gate_0_validate"
    )

    # Add force_reprocess flag if requested
    if force_reprocess:
        status["force_reprocess"] = True
        status["rebuild_mode"] = True
        status["rebuild_scope"] = {
            "mongodb": True,
            "cassandra": True,
            "neo4j": True
        }

    # Write status.json
    status_path = get_job_status_path(job_dir)
    write_json_atomic(status_path, status)

    # Create queued.marker to signal workers
    create_marker_file(job_dir, "queued.marker")

    print(f"  Job directory: {job_dir}")
    print(f"  Status file: {status_path}")
    print(f"✅ Job queued successfully")
    print(f"\nMonitor progress:")
    print(f"  - Job status: {status_path}")
    print(f"  - Worker logs: {resolve_transfer_path('Logs')}")
    print(f"\nWorkers will process job asynchronously.")

    return job_id


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Queue ingestion job for async processing",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Queue a new job
  python ingestion_wrapper_async.py --source /Transfer_Station/sources/manual.pdf

  # Force reprocess an existing document
  python ingestion_wrapper_async.py --source /Transfer_Station/sources/manual.pdf --force-reprocess

Monitor Progress:
  # Check job status
  cat /Transfer_Station/jobs/gate_0_hash/<job_id>/status.json

  # Monitor worker logs
  tail -f /Transfer_Station/Logs/gate_0_hash/worker.log
  tail -f /Transfer_Station/Logs/gate_0_validate/worker.log

Worker Execution:
  Workers must be running in their respective containers:
    docker exec ingestion_engine python gate_0_hash_worker.py &
    docker exec ingestion_engine python gate_0_validate_worker.py &
    docker exec ingestion_engine python doc_splitter_worker.py &
        """
    )

    parser.add_argument(
        "--source",
        type=Path,
        required=True,
        help="Path to source file to ingest (PDF, DOCX, TXT)"
    )

    parser.add_argument(
        "--force-reprocess",
        action="store_true",
        help="Force full reprocessing even if document already exists"
    )

    parser.add_argument(
        "--jobs-dir",
        type=Path,
        help="Root directory for job queues (default: /Transfer_Station/jobs)"
    )

    return parser.parse_args()


def main() -> int:
    """Main entry point."""
    try:
        args = parse_args()

        # Determine jobs root directory
        jobs_root = args.jobs_dir if args.jobs_dir else resolve_transfer_path("jobs")
        ensure_directory(jobs_root)

        # Queue the job
        job_id = queue_ingestion_job(
            source_file=args.source,
            jobs_root=jobs_root,
            force_reprocess=args.force_reprocess
        )

        print(f"\n🚀 Job {job_id} queued for async processing")
        return 0

    except FileNotFoundError as e:
        print(f"❌ Error: {e}", file=sys.stderr)
        return 1
    except ValueError as e:
        print(f"❌ Error: {e}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\n⚠️  Operation cancelled by user", file=sys.stderr)
        return 130
    except Exception as e:
        print(f"❌ Unexpected error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
