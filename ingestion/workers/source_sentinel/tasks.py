"""
Source Sentinel worker.

This worker scans the shared sources directory and enqueues ingestion jobs
based on metadata stored in the job registry. The implementation currently
produces log output to demonstrate flow; full queue integration arrives with
subsequent milestones.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Iterable

from ingestion.config import Settings
from ingestion.core.job_registry import JobRegistry, JobState, new_record
from ingestion.core.pipeline import deterministic_job_id
from ingestion.workers.ingestion_engine.tasks import orchestrate_passes
from ingestion.core.task_utils import shared_task

_LOG = logging.getLogger(__name__)
_settings = Settings()
_registry = JobRegistry.global_instance(settings=_settings)


def _iter_sources() -> Iterable[Path]:
    sources_dir = _settings.sources_dir
    sources_dir.mkdir(parents=True, exist_ok=True)
    for path in sources_dir.glob("**/*"):
        if path.is_file():
            yield path


@shared_task(bind=True, name="source_sentinel.scan", queue="source_sentinel")
def source_scan(self) -> int:
    """
    Discover new sources and create placeholder job registry entries.

    Returns the number of sources enqueued (placeholder behavior).
    """
    processed = 0
    for path in _iter_sources():
        job_id = deterministic_job_id(path)
        if _registry.exists_for_source(str(path)):
            continue

        record = new_record(
            job_id=job_id,
            source_path=str(path),
            state=JobState.QUEUED,
            refresh=False,
            stage="source_sentinel",
            message="Queued by Source Sentinel",
        )
        _registry.upsert(record)
        orchestrate_passes.delay(job_id)
        _LOG.info(
            "Queued source for ingestion",
            extra={"job_id": job_id, "source": str(path)},
        )
        processed += 1
    return processed
