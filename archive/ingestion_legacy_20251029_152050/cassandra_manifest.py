#!/usr/bin/env python3
"""
cassandra_manifest.py - Helpers for embedding manifest metadata in Cassandra.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional, Tuple

try:
    from cassandra import ConsistencyLevel
    from cassandra.query import SimpleStatement
except ImportError:  # pragma: no cover - optional at runtime for tooling scripts
    ConsistencyLevel = None  # type: ignore
    SimpleStatement = None  # type: ignore

MANIFEST_TABLE = "embedding_manifests"


@dataclass
class ManifestRecord:
    document_id: str
    chunk_count: int
    vector_checksum: str
    chunk_index_min: Optional[int]
    chunk_index_max: Optional[int]
    embedding_model: str
    vector_dim: int
    updated_at: datetime
    updated_by: str


def ensure_manifest_table(session, keyspace: str) -> None:
    """Create the embedding manifest table if missing."""
    if SimpleStatement is None:
        raise RuntimeError("cassandra-driver not installed; unable to ensure manifest table")

    session.set_keyspace(keyspace)
    session.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {MANIFEST_TABLE} (
            document_id text PRIMARY KEY,
            chunk_count int,
            vector_checksum text,
            chunk_index_min int,
            chunk_index_max int,
            embedding_model text,
            vector_dim int,
            updated_at timestamp,
            updated_by text
        )
        """
    )


def compute_chunk_metrics(chunks: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Compute chunk metrics (count, range, checksum) from embedded chunks.

    Args:
        chunks: Iterable of chunk dictionaries containing chunk_index, sub_chunk, element_id, embedding, etc.

    Returns:
        Dictionary with chunk_count, chunk_index_min/max, vector_checksum.
    """
    fingerprints: List[Tuple[int, bytes]] = []
    chunk_index_min: Optional[int] = None
    chunk_index_max: Optional[int] = None

    for chunk in chunks:
        idx = int(chunk.get("chunk_index", 0))
        sub_chunk = int(chunk.get("sub_chunk") or 0)  # Defensive null-coalescing: handles None values
        element_id = str(chunk.get("element_id") or "")
        text_content = chunk.get("text") or chunk.get("text_content") or ""
        text_length = len(text_content)
        embedding_values = chunk.get("embedding") or []

        if chunk_index_min is None or idx < chunk_index_min:
            chunk_index_min = idx
        if chunk_index_max is None or idx > chunk_index_max:
            chunk_index_max = idx

        embed_sample = []
        if embedding_values:
            sample_head = embedding_values[:16]
            sample_tail = embedding_values[-16:] if len(embedding_values) > 16 else []
            embed_sample = sample_head + sample_tail

        embed_str = ",".join(f"{float(val):.6f}" for val in embed_sample)
        fingerprint_payload = f"{idx}|{sub_chunk}|{element_id}|{text_length}|{embed_str}".encode("utf-8", "ignore")
        chunk_hash = hashlib.sha256(fingerprint_payload).digest()
        fingerprints.append((idx, chunk_hash))

    hasher = hashlib.sha256()
    for _, fp in sorted(fingerprints, key=lambda item: item[0]):
        hasher.update(fp)

    return {
        "chunk_count": len(fingerprints),
        "chunk_index_min": chunk_index_min,
        "chunk_index_max": chunk_index_max,
        "vector_checksum": hasher.hexdigest(),
    }


def upsert_manifest(session, keyspace: str, record: ManifestRecord) -> None:
    """Insert or update the manifest row for a document."""
    if SimpleStatement is None:
        raise RuntimeError("cassandra-driver not installed; unable to upsert manifest")

    session.set_keyspace(keyspace)
    stmt = SimpleStatement(
        f"""
        INSERT INTO {MANIFEST_TABLE} (
            document_id,
            chunk_count,
            vector_checksum,
            chunk_index_min,
            chunk_index_max,
            embedding_model,
            vector_dim,
            updated_at,
            updated_by
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """,
        consistency_level=ConsistencyLevel.ONE,
    )
    session.execute(
        stmt,
        (
            record.document_id,
            record.chunk_count,
            record.vector_checksum,
            record.chunk_index_min,
            record.chunk_index_max,
            record.embedding_model,
            record.vector_dim,
            record.updated_at,
            record.updated_by,
        ),
    )


def fetch_manifest(session, keyspace: str, document_id: str) -> Optional[ManifestRecord]:
    """Fetch manifest row for the document."""
    if SimpleStatement is None:
        raise RuntimeError("cassandra-driver not installed; unable to fetch manifest")

    session.set_keyspace(keyspace)
    stmt = SimpleStatement(
        f"""
        SELECT document_id, chunk_count, vector_checksum,
               chunk_index_min, chunk_index_max,
               embedding_model, vector_dim, updated_at, updated_by
        FROM {MANIFEST_TABLE}
        WHERE document_id = %s
        """,
        consistency_level=ConsistencyLevel.ONE,
    )
    row = session.execute(stmt, (document_id,), timeout=10).one()
    if not row:
        return None

    return ManifestRecord(
        document_id=row.document_id,
        chunk_count=row.chunk_count or 0,
        vector_checksum=row.vector_checksum or "",
        chunk_index_min=row.chunk_index_min,
        chunk_index_max=row.chunk_index_max,
        embedding_model=row.embedding_model or "",
        vector_dim=row.vector_dim or 0,
        updated_at=row.updated_at,
        updated_by=row.updated_by or "",
    )
