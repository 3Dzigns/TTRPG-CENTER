"""
Embedding utility helpers for checksum calculations.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import List, Tuple

from ingestion.config import Settings
from ingestion.artifacts import load_embeddings_artifact
from ingestion.core.tracing import start_span


def load_embeddings(job_id: str, settings: Settings) -> List[dict]:
    path = settings.artifacts_dir / job_id / "embeddings" / "embeddings.json"
    if not path.exists():
        raise FileNotFoundError(f"Embeddings file missing for job {job_id}: {path}")
    with start_span(
        "embeddings.read_file",
        attributes={
            "job_id": job_id,
            "source_id": job_id,
            "stage": "cassandra_upsert",
            "path": str(path),
        },
    ) as span:
        try:
            span.set_attribute("bytes", path.stat().st_size)
        except OSError:  # pragma: no cover
            pass
        artifact = load_embeddings_artifact(path)
        chunks = []
        for chunk in artifact.chunks:
            if hasattr(chunk, "model_dump"):
                chunks.append(chunk.model_dump())  # type: ignore[attr-defined]
            elif hasattr(chunk, "dict"):
                chunks.append(chunk.dict())  # type: ignore[attr-defined]
            else:
                chunks.append(chunk)
        span.set_attribute("chunk_count", len(chunks))
        return chunks


def _hash_concat(parts: List[str]) -> str:
    digest = hashlib.sha256()
    for part in parts:
        digest.update(part.encode("utf-8"))
    return digest.hexdigest()


def compute_checksum(job_id: str, chunks: List[dict]) -> Tuple[str, int]:
    ordered: List[str] = []
    for chunk in chunks:
        ordered.append(
            "|".join(
                [
                    str(chunk.get("chunk_id", "")),
                    str(chunk.get("text_hash", "")),
                    str(chunk.get("metadata_hash", "")),
                    str(chunk.get("vector_hash", "")),
                ]
            )
        )
    checksum = _hash_concat(ordered) if ordered else _hash_concat([job_id])
    return checksum, len(ordered)
