"""
Utilities for writing human-readable job status snapshots.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional
from typing import TYPE_CHECKING

from ingestion.core.tracing import get_current_trace_ids

from ingestion.config import Settings
from ingestion.core.db.cassandra_store import get_cassandra_store
from ingestion.core.db.dictionary import get_dictionary_store

LOG = logging.getLogger(__name__)
if TYPE_CHECKING:
    from ingestion.core.job_registry import JobRecord


def _artifact_paths(settings: Settings, job_id: str) -> Dict[str, str]:
    base = settings.artifacts_dir / job_id
    return {
        "base": str(base),
        "unstructured": str(base / "unstructured"),
        "metadata": str(base / "metadata"),
        "embeddings": str(base / "embeddings"),
        "llamaindex": str(base / "llamaindex"),
        "graph": str(base / "graph"),
    }


def _counts(settings: Settings, job_id: str) -> Dict[str, Any]:
    counts: Dict[str, Any] = {
        "dictionary_terms": None,
        "embeddings_rows": None,
    }

    try:
        dictionary_store = get_dictionary_store(settings)
        counts["dictionary_terms"] = dictionary_store.count_terms(job_id)  # type: ignore[attr-defined]
    except Exception:  # pragma: no cover - best effort
        LOG.debug("Failed to fetch dictionary counts for %s", job_id, exc_info=True)

    try:
        cassandra_store = get_cassandra_store(settings)
        rows = cassandra_store.fetch_source(job_id)  # type: ignore[attr-defined]
        counts["embeddings_rows"] = len(rows)
    except Exception:  # pragma: no cover - best effort
        LOG.debug("Failed to fetch Cassandra counts for %s", job_id, exc_info=True)
        # Fallback to ready marker if available
        ready_marker = settings.artifacts_dir / job_id / "embeddings" / "ready.marker"
        if ready_marker.exists():
            try:
                payload = json.loads(ready_marker.read_text(encoding="utf-8"))
                counts["embeddings_rows"] = payload.get("rows")
            except Exception:
                pass

    return counts


def _load_existing(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:  # pragma: no cover - corrupt file
        return {}


def write_status_snapshot(
    job: JobRecord,
    settings: Settings,
    *,
    last_error: Optional[str] = None,
) -> Path:
    """
    Persist a status snapshot to /Transfer_Station/jobs/{job_id}.status.json.
    """

    settings.jobs_dir.mkdir(parents=True, exist_ok=True)
    status_path = settings.jobs_dir / f"{job.job_id}.status.json"
    existing = _load_existing(status_path)

    trace_id, span_id = get_current_trace_ids()
    snapshot = {
        "job_id": job.job_id,
        "source": job.source_path,
        "refresh": job.refresh,
        "state": job.state.value,
        "stage": job.stage,
        "message": job.message or "",
        "expected_checksum": job.expected_checksum,
        "expected_count": job.expected_count,
        "updated_at": job.updated_at.isoformat(),
        "generated_at": datetime.now(tz=timezone.utc).isoformat(),
        "artifacts": _artifact_paths(settings, job.job_id),
        "counts": _counts(settings, job.job_id),
        "trace_id": trace_id,
        "span_id": span_id,
        "last_error": last_error if last_error is not None else existing.get("last_error"),
    }

    status_path.write_text(json.dumps(snapshot, indent=2), encoding="utf-8")
    return status_path


__all__ = ["write_status_snapshot"]
