"""
LlamaIndex worker that builds lightweight retrieval artifacts from embeddings.
"""

from __future__ import annotations

import json
import logging
import math
from collections import Counter
from datetime import datetime, timezone
from heapq import nlargest
from pathlib import Path
from typing import Dict, Iterable, List, Sequence

from ingestion.config import Settings
from ingestion.artifacts import (
    write_llamaindex_manifest,
    write_llamaindex_nodes,
    write_llamaindex_ready_marker,
    write_llamaindex_similarity,
)
from ingestion.core.idempotency import mark_stage_completed, stage_completed
from ingestion.core.job_registry import JobRegistry, JobState
from ingestion.core.task_utils import shared_task
from ingestion.core.tracing import start_span, send_task_with_tracing
from ingestion.workers.common.embeddings import load_embeddings

_LOG = logging.getLogger(__name__)
_settings = Settings()
_registry = JobRegistry.global_instance(settings=_settings)

MAX_FULL_SIMILARITY = 200
SIMILARITY_TOP_K = 5


def _embeddings_marker(job_id: str) -> Path:
    return _settings.artifacts_dir / job_id / "embeddings" / "ready.marker"


def _llamaindex_dir(job_id: str) -> Path:
    return _settings.artifacts_dir / job_id / "llamaindex"


def _normalize(vector: Sequence[float]) -> List[float]:
    norm = math.sqrt(sum(float(value) * float(value) for value in vector))
    if norm == 0:
        return [0.0 for _ in vector]
    return [float(value) / norm for value in vector]


def _dot(a: Sequence[float], b: Sequence[float]) -> float:
    return sum(x * y for x, y in zip(a, b))


def _compute_similarity(
    chunk_ids: List[str],
    vectors: List[List[float]],
    *,
    top_k: int = SIMILARITY_TOP_K,
) -> Dict[str, List[Dict[str, float]]]:
    count = len(chunk_ids)
    entries: Dict[str, List[Dict[str, float]]] = {}
    if count == 0:
        return entries

    if count <= MAX_FULL_SIMILARITY:
        for i, chunk_id in enumerate(chunk_ids):
            sims: List[tuple[float, str]] = []
            for j in range(count):
                if i == j:
                    continue
                score = _dot(vectors[i], vectors[j])
                if score <= 0:
                    continue
                sims.append((score, chunk_ids[j]))
            top = nlargest(top_k, sims)
            entries[chunk_id] = [
                {"chunk_id": target, "score": round(score, 4)} for score, target in top
            ]
    else:
        window = 4
        for i, chunk_id in enumerate(chunk_ids):
            sims: List[tuple[float, str]] = []
            start = max(0, i - window)
            end = min(count, i + window + 1)
            for j in range(start, end):
                if i == j:
                    continue
                score = _dot(vectors[i], vectors[j])
                if score <= 0:
                    continue
                sims.append((score, chunk_ids[j]))
            top = nlargest(top_k, sims)
            entries[chunk_id] = [
                {"chunk_id": target, "score": round(score, 4)} for score, target in top
            ]
    return entries


@shared_task(bind=True, name="llamaindex.build_indices", queue="llamaindex")
def build_indices(self, job_id: str) -> str:
    marker_path = _embeddings_marker(job_id)
    if not marker_path.exists():
        _LOG.warning("Embeddings ready marker missing; skipping LlamaIndex", extra={"job_id": job_id})
        return "embeddings-not-ready"

    try:
        checksum_payload = json.loads(marker_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        _LOG.error("Embeddings ready marker malformed; skipping LlamaIndex", extra={"job_id": job_id})
        return "embeddings-marker-invalid"

    fingerprint = json.dumps(checksum_payload, sort_keys=True)
    output_dir = _llamaindex_dir(job_id)
    ready_marker = output_dir / "ready.marker"
    if stage_completed(_settings, job_id, "llamaindex", fingerprint=fingerprint) and ready_marker.exists():
        _LOG.info("LlamaIndex already processed", extra={"job_id": job_id})
    else:
        try:
            chunks = load_embeddings(job_id, _settings)
        except FileNotFoundError:
            _LOG.error("Embeddings payload missing for LlamaIndex", extra={"job_id": job_id})
            return "embeddings-missing"

        document_id = job_id
        chunk_ids = [str(chunk.get("chunk_id") or f"{document_id}-chunk-{idx}") for idx, chunk in enumerate(chunks)]
        normalized_vectors = [_normalize(chunk.get("embedding", [])) for chunk in chunks]
        section_counter: Counter[str] = Counter()
        nodes_payload = {
            "document_id": document_id,
            "nodes": [],
        }
        for chunk_id, chunk in zip(chunk_ids, chunks):
            section_title = chunk.get("section_title")
            if section_title:
                section_counter[str(section_title)] += 1
            nodes_payload["nodes"].append(
                {
                    "id": chunk_id,
                    "chunk_index": int(chunk.get("chunk_index", 0) or 0),
                    "text": chunk.get("text"),
                    "page_number": chunk.get("page_number"),
                    "section_title": section_title,
                    "facets": chunk.get("facets"),
                    "text_hash": chunk.get("text_hash"),
                    "metadata_hash": chunk.get("metadata_hash"),
                    "vector_hash": chunk.get("vector_hash"),
                }
            )

        similarity_index = {
            "document_id": document_id,
            "top_k": SIMILARITY_TOP_K,
            "entries": _compute_similarity(chunk_ids, normalized_vectors),
        }

        generated_at = datetime.now(tz=timezone.utc).isoformat()
        output_dir.mkdir(parents=True, exist_ok=True)
        nodes_path = output_dir / "nodes.json"
        similarity_path = output_dir / "similarity.json"
        manifest_path = output_dir / "manifest.json"

        write_llamaindex_nodes(nodes_path, nodes_payload)
        write_llamaindex_similarity(similarity_path, similarity_index)

        manifest = {
            "schema_version": "1",
            "job_id": job_id,
            "document_id": document_id,
            "chunk_count": len(chunks),
            "generated_at": generated_at,
            "embedding_checksum": checksum_payload.get("checksum"),
            "artifacts": {
                "nodes": nodes_path.name,
                "similarity": similarity_path.name,
            },
            "sections": [
                {"section_title": title, "chunks": count}
                for title, count in section_counter.most_common(10)
            ],
        }
        write_llamaindex_manifest(manifest_path, manifest)

        ready_payload = {
            "schema_version": "1",
            "job_id": job_id,
            "document_id": document_id,
            "generated_at": generated_at,
            "checksum": checksum_payload.get("checksum"),
            "chunks": len(chunks),
        }
        write_llamaindex_ready_marker(ready_marker, ready_payload)

        mark_stage_completed(
            _settings,
            job_id,
            "llamaindex",
            fingerprint=fingerprint,
            details={"chunks": len(chunks)},
        )
        _registry.update_state(
            job_id,
            state=JobState.VERIFYING,
            stage="llamaindex",
            message=f"LlamaIndex artifacts generated ({len(chunks)} chunks)",
        )

    try:
        send_task_with_tracing(self.app, "graph_upsert.write", args=[job_id])
    except Exception as exc:  # pragma: no cover - local fallback
        _LOG.warning("Falling back to inline graph upsert: %s", exc)
        from ingestion.workers.graph_upsert.tasks import upsert_graph

        upsert_graph(None, job_id)

    return "llamaindex-build-pending"
