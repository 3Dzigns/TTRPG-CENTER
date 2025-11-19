"""
High-level pipeline orchestration helpers.

These helpers provide the single entry point used by tests or ad-hoc scripts to
kick off an ingestion job. They synchronously mirror the behaviour that the
asynchronous workers implement: create a registry record, stage the source in
`/Transfer_Station/artifacts`, then invoke the Unstructured worker to begin Pass
A. In production the same flow is triggered by the Source Sentinel, except
tasks are dispatched through Celery instead of being executed inline.
"""

from __future__ import annotations

import hashlib
import logging
import uuid
from pathlib import Path

from ingestion.core.job_registry import JobRegistry, JobState, new_record
from ingestion.workers.unstructured import process_document

_LOG = logging.getLogger(__name__)
_registry = JobRegistry.global_instance()


def deterministic_job_id(source_path: Path) -> str:
    stat = source_path.stat()
    payload = f"{source_path}:{stat.st_mtime}:{stat.st_size}".encode("utf-8")
    digest = hashlib.sha1(payload).hexdigest()
    return str(uuid.UUID(digest[:32]))


def kickoff_ingestion(source_path: Path, *, refresh: bool = False) -> str:
    """
    Create a job record and synchronously invoke the Unstructured worker stub.

    Real deployment will enqueue Celery tasks; synchronous invocation keeps the
    placeholder flow testable before we wire up the broker.
    """
    job_id = deterministic_job_id(source_path)
    _registry.upsert(
        new_record(
            job_id=job_id,
            source_path=str(source_path),
            state=JobState.QUEUED,
            refresh=refresh,
            stage="kickoff",
        )
    )
    _LOG.info("Kickoff ingestion", extra={"job_id": job_id, "source": str(source_path)})
    if hasattr(process_document, "run"):
        process_document.run(job_id, str(source_path))  # type: ignore[attr-defined]
    else:
        process_document(None, job_id, str(source_path))  # type: ignore[operator]
    return job_id
