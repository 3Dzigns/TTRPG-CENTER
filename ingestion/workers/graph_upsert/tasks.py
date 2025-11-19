"""
Graph upsert worker for persisting document graphs into Neo4j.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Iterable, List, Optional

from ingestion.config import Settings
from ingestion.core.db.graph_store import ChunkNode, DocumentNode, get_graph_store
from ingestion.core.idempotency import mark_stage_completed, stage_completed, fingerprint_payload
from ingestion.core.job_registry import JobRegistry, JobState
from ingestion.core.task_utils import shared_task
from ingestion.core.tracing import start_span
from ingestion.workers.common.embeddings import load_embeddings

_LOG = logging.getLogger(__name__)
_settings = Settings()
_registry = JobRegistry.global_instance(settings=_settings)


@lru_cache(maxsize=1)
def _get_graph_store():
    """Lazy initialization of graph store with caching."""
    return get_graph_store(_settings)


def _ready_marker(path: Path) -> Optional[dict]:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        _LOG.warning("Malformed ready marker: %s", path)
        return None


def _manifest_path(job_id: str) -> Path:
    graph_dir = _settings.artifacts_dir / job_id / "graph"
    graph_dir.mkdir(parents=True, exist_ok=True)
    return graph_dir / "graph_manifest.json"


def _graph_ready_path(job_id: str) -> Path:
    return _settings.artifacts_dir / job_id / "graph" / "ready.marker"


def _build_chunk_nodes(job_id: str, chunks: Iterable[dict], captured_at: str) -> List[ChunkNode]:
    nodes: List[ChunkNode] = []
    for payload in chunks:
        chunk_id = payload.get("chunk_id")
        if not chunk_id:
            continue
        index = payload.get("chunk_index")
        try:
            chunk_index = int(index) if index is not None else 0
        except (TypeError, ValueError):
            chunk_index = 0
        page_number = payload.get("page_number")
        try:
            page_number_val: Optional[int] = int(page_number) if page_number is not None else None
        except (TypeError, ValueError):
            page_number_val = None

        # Serialize facets to JSON string for Neo4J compatibility
        # Neo4J doesn't support MAP/dict property types, only primitives
        facets_value = payload.get("facets")
        facets_json = json.dumps(facets_value) if facets_value else None

        node: ChunkNode = {
            "chunk_id": chunk_id,
            "chunk_index": chunk_index,
            "text": payload.get("text"),
            "page_number": page_number_val,
            "section_title": payload.get("section_title"),
            "text_hash": payload.get("text_hash"),
            "metadata_hash": payload.get("metadata_hash"),
            "vector_hash": payload.get("vector_hash"),
            "facets": facets_json,
            "source_id": job_id,
            "updated_at": captured_at,
        }
        nodes.append(node)
    return nodes


def _write_manifest(job_id: str, manifest: dict) -> Path:
    path = _manifest_path(job_id)
    path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return path


def _load_existing_manifest(job_id: str) -> Optional[dict]:
    path = _manifest_path(job_id)
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


@shared_task(bind=True, name="graph_upsert.write", queue="graph_upsert")
def upsert_graph(self, job_id: str) -> str:
    record = _registry.get(job_id)
    source_path = record.source_path if record else job_id
    embeddings_marker_path = _settings.artifacts_dir / job_id / "embeddings" / "ready.marker"
    llamaindex_marker_path = _settings.artifacts_dir / job_id / "llamaindex" / "ready.marker"

    if not embeddings_marker_path.exists():
        _LOG.warning("Embeddings ready marker missing for graph upsert", extra={"job_id": job_id})
        return "embeddings-not-ready"
    if not llamaindex_marker_path.exists():
        _LOG.warning("LlamaIndex ready marker missing; deferring graph upsert", extra={"job_id": job_id})
        return "llamaindex-not-ready"

    embeddings_marker = _ready_marker(embeddings_marker_path)
    fingerprint = embeddings_marker.get("checksum") if embeddings_marker else None  # type: ignore[assignment]
    manifest_path = _manifest_path(job_id)
    existing_manifest = _load_existing_manifest(job_id)
    if fingerprint and stage_completed(_settings, job_id, "graph_upsert", fingerprint=fingerprint):
        if existing_manifest:
            _registry.update_state(
                job_id,
                state=JobState.VERIFYING,
                stage="graph_upsert",
                message="Graph upsert already completed",
                expected_checksum=fingerprint,
                expected_count=existing_manifest.get("chunks"),
            )
            _LOG.info("Graph upsert skipped (already completed)", extra={"job_id": job_id})
            return str(manifest_path)

    try:
        embedding_chunks = load_embeddings(job_id, _settings)
    except FileNotFoundError:
        _LOG.error("Embeddings payload missing for graph upsert", extra={"job_id": job_id})
        return "embeddings-missing"

    if not fingerprint:
        fingerprint = fingerprint_payload([chunk.get("vector_hash") for chunk in embedding_chunks])

    if stage_completed(_settings, job_id, "graph_upsert", fingerprint=fingerprint) and existing_manifest:
        _registry.update_state(
            job_id,
            state=JobState.VERIFYING,
            stage="graph_upsert",
            message="Graph upsert already completed",
            expected_checksum=fingerprint,
            expected_count=existing_manifest.get("chunks"),
        )
        _LOG.info("Graph upsert skipped (already completed)", extra={"job_id": job_id})
        return str(manifest_path)

    captured_at = datetime.now(tz=timezone.utc).isoformat()
    chunk_nodes = _build_chunk_nodes(job_id, embedding_chunks, captured_at)

    document_node: DocumentNode = {
        "document_id": job_id,
        "source_path": source_path,
        "chunk_count": len(chunk_nodes),
        "title": Path(source_path).name if source_path else job_id,
        "refresh": bool(record.refresh if record else False),
        "checksum": fingerprint,
        "updated_at": captured_at,
    }

    with start_span(
        "graph.upsert",
        attributes={
            "job_id": job_id,
            "source_id": source_path,
            "stage": "graph_upsert",
            "chunks": len(chunk_nodes),
            "refresh": bool(record.refresh if record else False),
        },
    ) as span:
        if record:
            _registry.update_state(
                job_id,
                state=JobState.UPSERTING,
                stage="graph_upsert",
                message="Upserting graph into Neo4j",
            )
        try:
            graph_store = _get_graph_store()
            result = graph_store.upsert_document_graph(
                document_node,
                chunk_nodes,
                refresh=bool(record.refresh if record else False),
            )
        except Exception as exc:  # pragma: no cover - surface failure
            _registry.update_state(
                job_id,
                state=JobState.FAILED,
                stage="graph_upsert",
                message=f"Graph upsert failed: {exc}",
            )
            span.set_attribute("error", str(exc))
            _LOG.exception("Graph upsert failed", extra={"job_id": job_id})
            raise

        nodes_created = int(result.get("nodes_created", 0))
        relationships_created = int(result.get("relationships_created", 0))
        span.set_attribute("nodes_written", nodes_created)
        span.set_attribute("edges_written", relationships_created)

    manifest_payload = {
        "job_id": job_id,
        "document_id": document_node["document_id"],
        "source_path": document_node["source_path"],
        "chunks": len(chunk_nodes),
        "checksum": fingerprint,
        "nodes_created": nodes_created,
        "relationships_created": relationships_created,
        "generated_at": captured_at,
    }
    _write_manifest(job_id, manifest_payload)
    _graph_ready_path(job_id).write_text(
        json.dumps(
            {
                "job_id": job_id,
                "document_id": document_node["document_id"],
                "ready": True,
                "generated_at": captured_at,
                "checksum": fingerprint,
                "chunks": len(chunk_nodes),
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    mark_stage_completed(
        _settings,
        job_id,
        "graph_upsert",
        fingerprint=fingerprint,
        details={"chunks": len(chunk_nodes), "nodes": nodes_created},
    )

    _registry.update_state(
        job_id,
        state=JobState.VERIFYING,
        stage="graph_upsert",
        message=f"Graph upsert complete ({len(chunk_nodes)} chunks)",
        expected_checksum=fingerprint,
        expected_count=len(chunk_nodes),
    )
    _LOG.info(
        "Graph upsert complete",
        extra={
            "job_id": job_id,
            "nodes_created": nodes_created,
            "relationships_created": relationships_created,
        },
    )
    return str(manifest_path)
