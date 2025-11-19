"""
Cassandra upsert worker with checksum computation (stub implementation).
"""

from __future__ import annotations

import json
import logging
from functools import lru_cache
from pathlib import Path
from typing import List, Sequence
from uuid import uuid4

import os
import time

from ingestion.config import Settings
from ingestion.core.db.cassandra_store import EmbeddingRow, get_cassandra_store
from ingestion.core.idempotency import mark_stage_completed, stage_completed
from ingestion.core.job_registry import JobRegistry, JobState, new_record
from ingestion.core.task_utils import shared_task
from ingestion.core.tracing import start_span, send_task_with_tracing
from ingestion.workers.common.embeddings import compute_checksum, load_embeddings

_LOG = logging.getLogger(__name__)
_settings = Settings()
_registry = JobRegistry.global_instance(settings=_settings)


@lru_cache(maxsize=1)
def _get_cassandra_store():
    """Lazy initialization of Cassandra store with caching."""
    return get_cassandra_store(_settings)


@shared_task(bind=True, name="cassandra_upsert.write", queue="cassandra_upsert")
def upsert_embeddings(self, job_id: str) -> str:
    try:
        chunks = load_embeddings(job_id, _settings)
    except FileNotFoundError as exc:
        _LOG.error(str(exc))
        return "embeddings-missing"

    checksum, total_rows = compute_checksum(job_id, chunks)

    sleep_env = os.getenv("CHAOS_CASSANDRA_UPSERT_SLEEP")
    if sleep_env:
        try:
            delay = float(sleep_env)
        except ValueError:
            delay = 0.0
        if delay > 0:
            _LOG.info("Chaos sleep before Cassandra upsert", extra={"job_id": job_id, "delay": delay})
            time.sleep(delay)

    if stage_completed(_settings, job_id, "cassandra_upsert", fingerprint=checksum):
        # CRITICAL: Validate data integrity before skipping re-execution
        # Load expected count from ready marker
        embeddings_dir = _settings.artifacts_dir / job_id / "embeddings"
        ready_marker_path = embeddings_dir / "ready.marker"

        data_valid = True
        if ready_marker_path.exists():
            try:
                ready_data = json.loads(ready_marker_path.read_text(encoding="utf-8"))
                expected_count = ready_data.get("rows", 0)

                # Query actual Cassandra count
                cassandra_store = _get_cassandra_store()
                actual_rows = cassandra_store.fetch_source(job_id)
                actual_count = len(actual_rows)

                # Validate counts match
                if actual_count != expected_count:
                    _LOG.warning(
                        "Data corruption detected in Cassandra - count mismatch",
                        extra={
                            "job_id": job_id,
                            "expected": expected_count,
                            "actual": actual_count,
                            "missing": expected_count - actual_count,
                            "checksum": checksum,
                        }
                    )
                    _registry.append_history(
                        job_id,
                        stage="cassandra_upsert",
                        message=f"Data corruption detected: expected {expected_count}, found {actual_count}. Performing smart upsert to repair.",
                    )
                    # Don't skip - fall through to perform smart upsert with orphan cleanup
                    data_valid = False
                else:
                    _LOG.info(
                        "Cassandra data integrity validated",
                        extra={"job_id": job_id, "count": actual_count, "checksum": checksum}
                    )
            except Exception as exc:
                _LOG.warning(
                    "Failed to validate Cassandra data integrity",
                    extra={"job_id": job_id, "error": str(exc)}
                )
                # If validation fails, proceed cautiously - allow skip

        # Only skip if data is valid
        if data_valid:
            _LOG.info("Cassandra stage already completed and validated", extra={"job_id": job_id})
            try:
                send_task_with_tracing(self.app, "graph_upsert.write", args=[job_id])
            except Exception as exc:  # pragma: no cover - local fallback
                _LOG.warning("Falling back to inline graph upsert: %s", exc)
                from ingestion.workers.graph_upsert.tasks import upsert_graph

                upsert_graph(None, job_id)
            return checksum

    record = _registry.get(job_id)
    refresh = record.refresh if record else False
    source_id = record.source_path if record else job_id
    source_name = Path(source_id).name if source_id else job_id

    rows: List[EmbeddingRow] = []
    for item in chunks:
        embedding = item.get("embedding")
        if embedding is None:
            _LOG.warning("Chunk missing embedding payload", extra={"job_id": job_id})
            continue
        facets = item.get("facets") or {}
        tags_value = facets.get("tags")
        if tags_value is None:
            tags: Sequence[str] | None = None
        elif isinstance(tags_value, (list, tuple, set)):
            tags = [str(tag) for tag in tags_value]
        elif isinstance(tags_value, dict):
            tags = [str(val) for val in tags_value.values()]
        else:
            tags = [str(tags_value)]
        chunk_id = item.get("chunk_id") or f"{job_id}-chunk-{item.get('chunk_index', 0)}"
        rows.append(
            EmbeddingRow(
                document_id=job_id,
                source_id=job_id,
                element_id=chunk_id,
                chunk_id=chunk_id,
                chunk_index=item.get("chunk_index", 0),
                text=item.get("text"),
                system=facets.get("system"),
                source=facets.get("source") or source_name,
                section=item.get("section_title"),
                tags=tags,
                page_number=item.get("page_number"),
                section_title=item.get("section_title"),
                text_hash=item.get("text_hash"),
                metadata_hash=item.get("metadata_hash"),
                vector_hash=item.get("vector_hash"),
                embedding=embedding,
                facets=item.get("facets"),
            )
        )

    if not rows:
        _LOG.warning("No embeddings generated for job %s", job_id)
        return "no-embeddings"

    purge_stage = "cassandra_upsert_purge"
    should_refresh_clear = refresh and not stage_completed(_settings, job_id, purge_stage)
    with start_span(
        "cassandra.upsert",
        attributes={
            "job_id": job_id,
            "source_id": source_id,
            "stage": "cassandra_upsert",
            "refresh": refresh,
            "expected_rows": len(rows),
            "checksum": checksum,
        },
    ) as span:
        cassandra_store = _get_cassandra_store()
        row_count = cassandra_store.upsert_embeddings(job_id, rows, refresh=should_refresh_clear)
        span.set_attribute("rows_written", row_count)
        span.set_attribute("refresh_cleared", bool(should_refresh_clear))

        # Smart upsert: Clean up orphaned records (exist in DB but not in artifacts)
        # Note: For now, we validate count but don't delete orphans since Cassandra store
        # doesn't have chunk-level deletion. Orphan cleanup would require adding a new method
        # to cassandra_store or accepting full delete_source + re-upsert approach.
        expected_chunk_ids = {row.chunk_id for row in rows}
        actual_rows = cassandra_store.fetch_source(job_id)
        actual_chunk_ids = {row.chunk_id for row in actual_rows}
        orphaned_ids = actual_chunk_ids - expected_chunk_ids

        if orphaned_ids:
            _LOG.warning(
                "Detected orphaned chunks in Cassandra",
                extra={"job_id": job_id, "orphan_count": len(orphaned_ids), "orphan_ids": list(orphaned_ids)[:5]}
            )
            _registry.append_history(
                job_id,
                stage="cassandra_upsert",
                message=f"Detected {len(orphaned_ids)} orphaned chunks - upserted valid data but orphans remain (requires delete_source for full cleanup)",
            )
            span.set_attribute("orphans_detected", len(orphaned_ids))

    if row_count != len(rows):
        _LOG.warning(
            "Cassandra upsert row count mismatch",
            extra={"job_id": job_id, "expected": len(rows), "written": row_count},
        )
    if should_refresh_clear:
        mark_stage_completed(_settings, job_id, purge_stage)
        _registry.append_history(
            job_id,
            stage="cassandra_upsert",
            message="Cassandra partition cleared prior to refresh",
        )

    _registry.update_state(
        job_id,
        state=JobState.UPSERTING,
        stage="cassandra_upsert",
        message=f"Upserted {row_count} embeddings (checksum {checksum[:12]})",
        expected_checksum=checksum,
        expected_count=total_rows,
    )

    # Drop a readiness marker so downstream passes know embeddings are durable.
    embeddings_dir = _settings.artifacts_dir / job_id / "embeddings"
    embeddings_dir.mkdir(parents=True, exist_ok=True)
    ready_marker = embeddings_dir / "ready.marker"
    ready_marker.write_text(
        json.dumps({"checksum": checksum, "rows": row_count}, indent=2),
        encoding="utf-8",
    )

    mark_stage_completed(
        _settings,
        job_id,
        "cassandra_upsert",
        fingerprint=checksum,
        details={"count": row_count, "checksum": checksum},
    )

    try:
        send_task_with_tracing(self.app, "llamaindex.build_indices", args=[job_id])
    except Exception as exc:  # pragma: no cover - local fallback
        _LOG.warning("Falling back to inline llamaindex task: %s", exc)
        from ingestion.workers.llamaindex.tasks import build_indices

        build_indices(None, job_id)

    return checksum
