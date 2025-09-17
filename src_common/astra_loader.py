# src_common/astra_loader.py
"""
Vector store loader facade used by ingestion pipelines.
Supports AstraDB and Cassandra via the vector_store factory.
"""

from __future__ import annotations

import json
import os
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from .vector_store.factory import make_vector_store
from .ttrpg_logging import get_logger

logger = get_logger(__name__)


@dataclass
class LoadResult:
    """Result of loading chunks into the vector store."""

    collection_name: str
    chunks_loaded: int
    chunks_failed: int
    loading_time_ms: int
    success: bool
    error_message: Optional[str] = None


class AstraLoader:
    """Backwards-compatible loader used throughout the ingestion pipeline."""

    def __init__(self, env: str = "dev") -> None:
        self.env = env

        # Ensure root .env is loaded for credential-based backends (Astra)
        project_root = Path(__file__).parent.parent
        root_env = project_root / ".env"
        if root_env.exists():
            logger.debug("Loading credentials from root .env: %s", root_env)
            from .ttrpg_secrets import _load_env_file  # type: ignore

            _load_env_file(root_env)

        self.strict_creds = os.getenv("ASTRA_REQUIRE_CREDS", "true").strip().lower() in {"1", "true", "yes"}
        self.store = make_vector_store(env)
        self.backend = self.store.backend_name
        self.collection_name = getattr(self.store, "collection_name", f"ttrpg_chunks_{env}")
        self.client = getattr(self.store, "client", None)
        logger.info("Vector store loader initialized backend=%s env=%s", self.backend, env)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def load_chunks_from_file(self, chunks_file: Path) -> LoadResult:
        logger.info("Loading chunks from %s into %s", chunks_file, self.collection_name)
        start = time.time()

        try:
            with open(chunks_file, "r", encoding="utf-8") as handle:
                data = json.load(handle)
        except Exception as exc:  # pragma: no cover - I/O failure
            logger.error("Failed to read chunks file %s: %s", chunks_file, exc)
            return LoadResult(self.collection_name, 0, 0, 0, False, str(exc))

        chunks = (
            data.get("chunks")
            or data.get("vectorized_chunks")
            or data.get("items")
            or []
        )
        result = self._load_chunks_to_collection(chunks)
        result.loading_time_ms = int((time.time() - start) * 1000)
        return result

    def empty_collection(self) -> bool:
        logger.info("Clearing vector store collection %s", self.collection_name)
        try:
            self.store.delete_all()
            return True
        except Exception as exc:  # pragma: no cover - backend failure
            logger.error("Failed to empty collection %s: %s", self.collection_name, exc)
            return False

    def get_collection_stats(self) -> Dict[str, Any]:
        try:
            count = self.store.count_documents()
            return {
                "collection_name": self.collection_name,
                "document_count": count,
                "environment": self.env,
                "status": "ready",
            }
        except Exception as exc:  # pragma: no cover - backend failure
            logger.error("Error getting collection stats: %s", exc)
            return {
                "collection_name": self.collection_name,
                "document_count": 0,
                "environment": self.env,
                "status": "error",
                "error": str(exc),
            }

    def get_sources_with_chunk_counts(self) -> Dict[str, Any]:
        try:
            return self.store.get_sources_with_chunk_counts()
        except Exception as exc:  # pragma: no cover - backend failure
            logger.error("Failed to fetch source chunk counts: %s", exc)
            return {
                "status": "error",
                "environment": self.env,
                "sources": [],
                "total_sources": 0,
                "total_chunks": 0,
                "error": str(exc),
            }

    def safe_upsert_chunks_for_source(
        self, chunks: List[Dict[str, Any]], source_hash: str
    ) -> LoadResult:
        logger.info("Upserting %s chunks for source %s", len(chunks), source_hash[:12])
        for chunk in chunks:
            metadata = chunk.setdefault("metadata", {})
            metadata.setdefault("source_hash", source_hash)
            chunk.setdefault("source_hash", source_hash)
        self.store.delete_by_source_hash(source_hash)
        return self._load_chunks_to_collection(chunks)

    def validate_chunk_integrity(self, source_hash: str, expected_count: int) -> Dict[str, Any]:
        actual = self.store.count_documents_for_source(source_hash)
        integrity_valid = actual == expected_count
        status = "validated" if integrity_valid else "mismatch"
        if integrity_valid:
            logger.info("Chunk integrity valid for %s (%s)", source_hash[:12], actual)
        else:
            logger.warning(
                "Chunk integrity mismatch for %s: expected=%s actual=%s",
                source_hash[:12],
                expected_count,
                actual,
            )
        return {
            "source_hash": source_hash,
            "expected_count": expected_count,
            "actual_count": actual,
            "integrity_valid": integrity_valid,
            "status": status,
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _load_chunks_to_collection(self, chunks: List[Dict[str, Any]]) -> LoadResult:
        if not chunks:
            return LoadResult(self.collection_name, 0, 0, 0, True)

        documents: List[Dict[str, Any]] = []
        max_bytes = 7000  # BUG-017 guardrail
        target_chars = 400
        now = time.time()
        for chunk in chunks:
            content = chunk.get("content") or chunk.get("text") or ""
            metadata = dict(chunk.get("metadata") or {})
            metadata.setdefault("environment", self.env)
            chunk_id = chunk.get("chunk_id") or chunk.get("id") or str(uuid.uuid4())

            for part_index, part in enumerate(
                self._enforce_chunk_size_limits(content, target_chars, max_bytes), start=1
            ):
                doc_id = chunk_id if part_index == 1 else f"{chunk_id}-part{part_index}"
                documents.append(
                    {
                        "chunk_id": doc_id,
                        "content": part,
                        "metadata": metadata,
                        "environment": self.env,
                        "stage": chunk.get("stage") or metadata.get("stage") or "raw",
                        "source_hash": metadata.get("source_hash") or chunk.get("source_hash"),
                        "source_file": metadata.get("source_file") or chunk.get("source_file"),
                        "embedding": chunk.get("embedding"),
                        "embedding_model": chunk.get("embedding_model"),
                        "vector_id": chunk.get("vector_id"),
                        "updated_at": chunk.get("updated_at") or now,
                        "loaded_at": now,
                        "payload": chunk,
                    }
                )

        try:
            inserted = self.store.upsert_documents(documents)
            failed = len(documents) - inserted
            if failed:
                logger.warning("Partial upsert detected: %s/%s failed", failed, len(documents))
            else:
                logger.info("Upserted %s documents into %s", inserted, self.collection_name)
            return LoadResult(
                collection_name=self.collection_name,
                chunks_loaded=inserted,
                chunks_failed=max(0, failed),
                loading_time_ms=0,
                success=failed == 0,
                error_message=None if failed == 0 else "partial upsert",
            )
        except Exception as exc:
            logger.error("Error inserting chunks into %s: %s", self.collection_name, exc)
            if self.backend == "astra" and self.strict_creds:
                raise RuntimeError("Vector store upsert failed") from exc
            return LoadResult(
                collection_name=self.collection_name,
                chunks_loaded=0,
                chunks_failed=len(documents),
                loading_time_ms=0,
                success=False,
                error_message=str(exc),
            )

    @staticmethod
    def _enforce_chunk_size_limits(content: str, target_chars: int, max_bytes: int) -> List[str]:
        if not content:
            return [""]
        encoded = content.encode("utf-8")
        if len(encoded) <= max_bytes:
            return [content]

        segments: List[str] = []
        start = 0
        while start < len(content):
            end = start + target_chars
            segments.append(content[start:end])
            start = end
        safe_segments: List[str] = []
        for segment in segments:
            part = segment.strip()
            if not part:
                continue
            if len(part.encode("utf-8")) > max_bytes:
                midpoint = len(part) // 2
                safe_segments.extend([part[:midpoint], part[midpoint:]])
            else:
                safe_segments.append(part)
        return safe_segments or [content[:target_chars]]


def load_chunks_to_astra(chunks_file: Path, env: str = "dev") -> LoadResult:
    loader = AstraLoader(env=env)
    return loader.load_chunks_from_file(chunks_file)


def empty_collection(env: str = "dev") -> bool:
    loader = AstraLoader(env=env)
    return loader.empty_collection()
