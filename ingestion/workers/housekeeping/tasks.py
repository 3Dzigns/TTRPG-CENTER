"""
Housekeeping worker tasks.
"""

from __future__ import annotations

import json
import logging
import os
import re
import shutil
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import List

import psycopg

from ingestion.config import Settings
from ingestion.core.db.cassandra_store import get_cassandra_store
from ingestion.core.db.dictionary import get_dictionary_store
from ingestion.core.db.graph_store import get_graph_store
from ingestion.core.idempotency import fingerprint_payload, mark_stage_completed, stage_completed
from ingestion.core.job_registry import JobRegistry, JobState
from ingestion.core.task_utils import shared_task
from ingestion.core.tracing import start_span
from ingestion.workers.housekeeping.retention import enforce_retention, _prune_job_directory

_LOG = logging.getLogger(__name__)
_settings = Settings()
_registry = JobRegistry.global_instance(settings=_settings)


@lru_cache(maxsize=1)
def _get_dictionary_store():
    """Lazy initialization of dictionary store with caching."""
    return get_dictionary_store(_settings)


@lru_cache(maxsize=1)
def _get_cassandra_store():
    """Lazy initialization of Cassandra store with caching."""
    return get_cassandra_store(_settings)


@lru_cache(maxsize=1)
def _get_graph_store():
    """Lazy initialization of graph store with caching."""
    return get_graph_store(_settings)


def _finalized_marker_path(job_id: str):
    return _settings.artifacts_dir / job_id / "finalized.marker"


def _sync_source_to_auth_db(source_path: str) -> bool:
    """
    Sync a source from the ingestion pipeline to the ttrpg_auth.sources table.

    Extracts source name from the file path and categorizes based on keywords.
    Uses INSERT ... ON CONFLICT DO NOTHING for idempotency.

    Returns True if successful, False otherwise.
    """
    auth_db_url = os.getenv("AUTH_DATABASE_URL")
    if not auth_db_url:
        _LOG.warning("AUTH_DATABASE_URL not set - skipping source sync")
        return False

    # Extract filename without extension
    source_name = Path(source_path).stem

    # Clean up common patterns in filenames
    source_name = re.sub(r'\s*-\s*CP\d+', '', source_name)  # Remove CP4110 patterns
    source_name = re.sub(r'\s+\(\d+(st|nd|rd|th)\s+Printing\)', '', source_name)  # Remove printing info
    source_name = source_name.strip()

    # Categorize based on keywords in the filename
    category = "ruleset"  # Default
    name_lower = source_name.lower()

    if any(word in name_lower for word in ["adventure", "path", "quest", "curse", "tomb", "mines"]):
        category = "campaign"
    elif any(word in name_lower for word in ["guide", "companion", "supplement"]):
        category = "expansion"
    elif any(word in name_lower for word in ["core", "rulebook", "rules", "handbook"]):
        category = "ruleset"
    elif any(word in name_lower for word in ["magic", "spells", "items"]):
        category = "expansion"

    try:
        with psycopg2.connect(auth_db_url) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO sources (name, category)
                    VALUES (%s, %s)
                    ON CONFLICT (name) DO NOTHING
                    RETURNING id
                    """,
                    (source_name, category)
                )
                result = cur.fetchone()
                if result:
                    _LOG.info(
                        "Source synced to auth database",
                        extra={"source_name": source_name, "category": category, "source_id": result[0]}
                    )
                else:
                    _LOG.info(
                        "Source already exists in auth database",
                        extra={"source_name": source_name}
                    )
                conn.commit()
                return True
    except Exception as exc:
        _LOG.error(
            "Failed to sync source to auth database",
            extra={"source_path": source_path, "source_name": source_name, "error": str(exc)}
        )
        return False


def _validate_data_integrity(job_id: str) -> dict:
    """
    Validate data integrity across all 3 databases before cleanup.

    Returns dict with:
        - valid: bool - True if all data is intact
        - cassandra_valid: bool
        - graph_valid: bool
        - cassandra_count: int
        - cassandra_expected: int
        - graph_count: int
        - graph_expected: int
        - errors: list of error messages
    """
    result = {
        "valid": False,
        "cassandra_valid": False,
        "graph_valid": False,
        "cassandra_count": 0,
        "cassandra_expected": 0,
        "graph_count": 0,
        "graph_expected": 0,
        "errors": [],
    }

    artifacts_dir = _settings.artifacts_dir / job_id

    # Validate Cassandra data
    cassandra_ready = artifacts_dir / "embeddings" / "ready.marker"
    if cassandra_ready.exists():
        try:
            cassandra_data = json.loads(cassandra_ready.read_text(encoding="utf-8"))
            expected_count = cassandra_data.get("rows", 0)
            result["cassandra_expected"] = expected_count

            cassandra_store = _get_cassandra_store()
            actual_rows = cassandra_store.fetch_source(job_id)
            actual_count = len(actual_rows)
            result["cassandra_count"] = actual_count

            if actual_count == expected_count:
                result["cassandra_valid"] = True
            else:
                result["errors"].append(
                    f"Cassandra count mismatch: expected {expected_count}, found {actual_count}"
                )
        except Exception as exc:
            result["errors"].append(f"Cassandra validation failed: {exc}")
    else:
        result["errors"].append("Cassandra ready.marker not found")

    # Validate Neo4J graph data
    graph_ready = artifacts_dir / "graph" / "ready.marker"
    if graph_ready.exists():
        try:
            graph_data = json.loads(graph_ready.read_text(encoding="utf-8"))
            expected_count = graph_data.get("chunks", 0)
            result["graph_expected"] = expected_count

            graph_store = _get_graph_store()
            # Query actual chunk count from Neo4J
            query_result = graph_store._driver.execute_query(
                "MATCH (c:Chunk {source_id: $source_id}) RETURN count(c) as count",
                source_id=job_id,
            )
            actual_count = query_result.records[0]["count"] if query_result.records else 0
            result["graph_count"] = actual_count

            if actual_count == expected_count:
                result["graph_valid"] = True
            else:
                result["errors"].append(
                    f"Neo4J count mismatch: expected {expected_count}, found {actual_count}"
                )
        except Exception as exc:
            result["errors"].append(f"Neo4J validation failed: {exc}")
    else:
        result["errors"].append("Graph ready.marker not found")

    # Overall validation
    result["valid"] = result["cassandra_valid"] and result["graph_valid"]

    return result


@shared_task(bind=True, name="housekeeping.finalize", queue="housekeeping")
def finalize_job(self, job_id: str) -> str:
    record = _registry.get(job_id)
    if not record:
        _LOG.warning("Housekeeping missing job", extra={"job_id": job_id})
        return "job-missing"

    if not record.expected_checksum or record.expected_count is None:
        _registry.update_state(
            job_id,
            state=JobState.CLEANUP,
            stage="housekeeping",
            message="Awaiting checksum verification",
        )
        return "awaiting-checksum"

    finalized_at = datetime.now(tz=timezone.utc).isoformat()
    marker_path = _finalized_marker_path(job_id)
    try:
        marker_path.parent.mkdir(parents=True, exist_ok=True)
        marker_payload = {
            "job_id": job_id,
            "source_path": record.source_path,
            "finalized": True,
            "finalized_at": finalized_at,
            "expected_checksum": record.expected_checksum,
            "expected_count": record.expected_count,
        }
        marker_path.write_text(json.dumps(marker_payload, indent=2), encoding="utf-8")
    except Exception as exc:  # pragma: no cover - best effort marker
        _LOG.warning("Failed to write finalized marker for %s: %s", job_id, exc)

    # Sync source to auth database for WebUI dropdown
    if record.source_path:
        _sync_source_to_auth_db(record.source_path)

    _registry.update_state(
        job_id,
        state=JobState.COMPLETED,
        stage="housekeeping",
        message="Housekeeping completed",
    )
    _registry.append_history(
        job_id,
        stage="housekeeping.finalize",
        message="Job finalized; retention window started",
        expected_checksum=record.expected_checksum,
        expected_count=record.expected_count,
    )
    return "housekeeping-complete"


@shared_task(bind=True, name="housekeeping.remove_source", queue="housekeeping")
def remove_source(self, job_id: str, source_path: str) -> str:
    _LOG.info("Removing source", extra={"job_id": job_id, "source": source_path})

    stage_fingerprint = fingerprint_payload({"source_path": source_path})
    if stage_completed(_settings, job_id, "housekeeping.remove_source", fingerprint=stage_fingerprint):
        _LOG.info("Removal already completed", extra={"job_id": job_id})
        return "removal-complete"

    removal_record = _registry.get(job_id)
    if removal_record:
        _registry.update_state(
            job_id,
            state=JobState.CLEANUP,
            stage="housekeeping",
            message="Removing source data",
        )

    targets: List[str] = []
    for record in _registry.list():
        if record.source_path == source_path and record.job_id != job_id:
            targets.append(record.job_id)

    with start_span(
        "housekeeping.remove",
        attributes={
            "job_id": job_id,
            "source_id": source_path,
            "stage": "housekeeping",
            "target_count": len(targets),
        },
    ) as span:
        removed_terms = 0
        removed_embeddings = 0
        removed_graph_nodes = 0
        removed_graph_relationships = 0

        dictionary_store = _get_dictionary_store()
        cassandra_store = _get_cassandra_store()
        graph_store = _get_graph_store()

        for target_id in targets:
            try:
                removed_terms += dictionary_store.count_terms(target_id)
                dictionary_store.delete_source(target_id)
            except Exception as exc:  # pragma: no cover - best effort
                _LOG.warning("Dictionary cleanup failed for %s: %s", target_id, exc)

            try:
                embeddings = cassandra_store.fetch_source(target_id)
                removed_embeddings += len(embeddings)
                cassandra_store.delete_source(target_id)
            except Exception as exc:  # pragma: no cover - best effort
                _LOG.warning("Cassandra cleanup failed for %s: %s", target_id, exc)

            try:
                graph_result = graph_store.delete_document(target_id)
                removed_graph_nodes += graph_result.get("nodes_removed", 0)
                removed_graph_relationships += graph_result.get("relationships_removed", 0)
            except Exception as exc:  # pragma: no cover - best effort
                _LOG.warning("Graph cleanup failed for %s: %s", target_id, exc)

            # Validate data integrity before cleanup
            target_artifacts = _settings.artifacts_dir / target_id
            if target_artifacts.exists():
                validation = _validate_data_integrity(target_id)
                if validation["valid"]:
                    # Data is valid - perform selective cleanup (keep markers, delete large files)
                    try:
                        removed_files = _prune_job_directory(target_artifacts)
                        _LOG.info(
                            "Selective cleanup completed for target",
                            extra={
                                "target_id": target_id,
                                "files_removed": len(removed_files),
                                "cassandra_count": validation["cassandra_count"],
                                "graph_count": validation["graph_count"],
                            }
                        )
                    except Exception as exc:  # pragma: no cover
                        _LOG.warning("Failed to prune artifacts for %s: %s", target_id, exc)
                else:
                    # Data corruption detected - keep ALL artifacts for potential recovery
                    _LOG.warning(
                        "Data corruption detected - preserving artifacts for recovery",
                        extra={
                            "target_id": target_id,
                            "errors": validation["errors"],
                            "cassandra_count": validation["cassandra_count"],
                            "cassandra_expected": validation["cassandra_expected"],
                            "graph_count": validation["graph_count"],
                            "graph_expected": validation["graph_expected"],
                        }
                    )
                    _registry.append_history(
                        target_id,
                        stage="housekeeping",
                        message=f"Data corruption detected - artifacts preserved: {', '.join(validation['errors'])}",
                    )

            try:
                _registry.update_state(
                    target_id,
                    state=JobState.REMOVED,
                    stage="housekeeping",
                    message="Source removed by housekeeping",
                )
            except Exception:
                pass

        # Validate data integrity before cleanup for the main job
        artifacts_dir = _settings.artifacts_dir / job_id
        if artifacts_dir.exists():
            validation = _validate_data_integrity(job_id)
            if validation["valid"]:
                # Data is valid - perform selective cleanup (keep markers, delete large files)
                try:
                    removed_files = _prune_job_directory(artifacts_dir)
                    _LOG.info(
                        "Selective cleanup completed",
                        extra={
                            "job_id": job_id,
                            "files_removed": len(removed_files),
                            "cassandra_count": validation["cassandra_count"],
                            "graph_count": validation["graph_count"],
                        }
                    )
                    _registry.append_history(
                        job_id,
                        stage="housekeeping.remove_source",
                        message=f"Cleaned up {len(removed_files)} artifacts while preserving integrity markers",
                    )
                except Exception as exc:  # pragma: no cover - best effort cleanup
                    _LOG.warning("Failed to prune artifacts for %s: %s", job_id, exc)
            else:
                # Data corruption detected - keep ALL artifacts for potential recovery
                _LOG.warning(
                    "Data corruption detected in main job - preserving artifacts for recovery",
                    extra={
                        "job_id": job_id,
                        "errors": validation["errors"],
                        "cassandra_count": validation["cassandra_count"],
                        "cassandra_expected": validation["cassandra_expected"],
                        "graph_count": validation["graph_count"],
                        "graph_expected": validation["graph_expected"],
                    }
                )
                _registry.append_history(
                    job_id,
                    stage="housekeeping.remove_source",
                    message=f"Data corruption detected - ALL artifacts preserved: {', '.join(validation['errors'])}",
                )

        span.set_attribute("removed_terms", removed_terms)
        span.set_attribute("removed_embeddings", removed_embeddings)
        span.set_attribute("graph_nodes_removed", removed_graph_nodes)
        span.set_attribute("graph_relationships_removed", removed_graph_relationships)

    _registry.update_state(
        job_id,
        state=JobState.REMOVED,
        stage="housekeeping",
        message=f"Removal completed (terms={removed_terms}, embeddings={removed_embeddings})",
    )
    mark_stage_completed(
        _settings,
        job_id,
        "housekeeping.remove_source",
        fingerprint=stage_fingerprint,
        details={
            "removed_terms": removed_terms,
            "removed_embeddings": removed_embeddings,
            "removed_graph_nodes": removed_graph_nodes,
            "removed_graph_relationships": removed_graph_relationships,
            "targets": targets,
        },
    )
    return "removal-complete"


@shared_task(bind=True, name="housekeeping.cleanup_old_artifacts", queue="housekeeping")
def cleanup_old_artifacts(self) -> dict:
    stats = enforce_retention(_settings, _registry)
    _LOG.info("Artifact retention sweep complete", extra={"stats": stats})
    return stats
