"""
Health verifier worker for nightly checksum validation and refresh/removal flows.
"""

from __future__ import annotations

import logging
from functools import lru_cache
from pathlib import Path
from typing import Dict
from uuid import uuid4

from ingestion.config import Settings
from ingestion.core.db.cassandra_store import get_cassandra_store
from ingestion.core.db.dictionary import get_dictionary_store
from ingestion.core.job_registry import JobRecord, JobRegistry, JobState, new_record
from ingestion.core.tracing import send_task_with_tracing
from ingestion.core.task_utils import shared_task
from ingestion.workers.common.embeddings import compute_checksum

_LOG = logging.getLogger(__name__)
_settings = Settings()
_registry = JobRegistry.global_instance(settings=_settings)


@lru_cache(maxsize=1)
def _get_cassandra_store():
    """Lazy initialization of Cassandra store with caching."""
    return get_cassandra_store(_settings)


@lru_cache(maxsize=1)
def _get_dictionary_store():
    """Lazy initialization of dictionary store with caching."""
    return get_dictionary_store(_settings)


def _enqueue_refresh(job: JobRecord, checksum: str, row_count: int, app) -> None:
    refresh_job_id = f"{job.job_id}-refresh-{uuid4().hex[:8]}"
    record = new_record(
        job_id=refresh_job_id,
        source_path=job.source_path,
        state=JobState.QUEUED,
        refresh=True,
        stage="health_verifier",
        message="Refresh queued by health verifier",
    )
    _registry.upsert(record)

    if app is not None:
        send_task_with_tracing(app, "ingestion_engine.orchestrate", args=[refresh_job_id])
    else:
        _LOG.info("Simulated refresh enqueue", extra={"job_id": refresh_job_id})

    _registry.update_state(
        job.job_id,
        state=JobState.VERIFYING,
        stage="health_verifier",
        message="Checksum mismatch - refresh queued",
        expected_checksum=checksum,
        expected_count=row_count,
    )


def _enqueue_removal(job: JobRecord, app) -> None:
    removal_job_id = f"{job.job_id}-remove-{uuid4().hex[:8]}"
    record = new_record(
        job_id=removal_job_id,
        source_path=job.source_path,
        state=JobState.QUEUED,
        refresh=False,
        stage="health_verifier",
        message="Removal queued by health verifier",
    )
    _registry.upsert(record)

    if app is not None:
        send_task_with_tracing(app, "housekeeping.remove_source", args=[removal_job_id, job.source_path])
    else:
        _LOG.info("Simulated removal enqueue", extra={"job_id": removal_job_id})

    _registry.update_state(
        job.job_id,
        state=JobState.REMOVED,
        stage="health_verifier",
        message="Source missing - removal queued",
    )


@shared_task(bind=True, name="health_verifier.verify", queue="health_verifier")
def verify(self) -> Dict[str, int]:
    jobs = list(_registry.list())
    stats = {"verified": 0, "refresh": 0, "removal": 0}
    app = getattr(self, "app", None) if self is not None else None

    for job in jobs:
        if job.state not in {JobState.COMPLETED, JobState.CLEANUP}:
            continue

        source_path = Path(job.source_path)
        if not source_path.exists():
            _enqueue_removal(job, app)
            stats["removal"] += 1
            continue

        try:
            cassandra_store = _get_cassandra_store()
            embeddings = cassandra_store.fetch_source(job.job_id)
        except Exception as exc:  # pragma: no cover - best effort
            _LOG.warning("Failed to fetch Cassandra rows for %s: %s", job.job_id, exc)
            continue

        row_count = len(embeddings)
        if row_count == 0:
            _LOG.warning("No Cassandra rows found for job %s; skipping", job.job_id)
            continue

        checksum, _ = compute_checksum(job.job_id, embeddings)
        expected_checksum = job.expected_checksum or ""
        expected_count = job.expected_count if job.expected_count is not None else row_count
        try:
            dictionary_store = _get_dictionary_store()
            dictionary_count = dictionary_store.count_terms(job.job_id)
        except Exception as exc:  # pragma: no cover - best effort
            _LOG.debug("Dictionary count unavailable for %s: %s", job.job_id, exc)
            dictionary_count = None

        counts_match = expected_count == row_count
        if dictionary_count is not None:
            counts_match = counts_match and dictionary_count == expected_count

        if expected_checksum and expected_checksum == checksum and counts_match:
            _registry.update_state(
                job.job_id,
                state=JobState.COMPLETED,
                stage="health_verifier",
                message="Checksums verified against live stores",
                expected_checksum=checksum,
                expected_count=row_count,
            )
            stats["verified"] += 1
        else:
            _enqueue_refresh(job, checksum, row_count, app)
            stats["refresh"] += 1

    _LOG.info("Health verification complete", extra={"stats": stats})
    return stats
