from __future__ import annotations

import threading
from collections import defaultdict
from copy import deepcopy
from typing import Any, Dict, List, Mapping, Optional, Sequence

from .base import VectorStore

_lock = threading.RLock()
_store: Dict[str, List[Dict[str, Any]]] = defaultdict(list)


def _tokenize(text: str) -> List[str]:
    return [token.lower() for token in (text or "").split() if token]


def _lexical_score(query: str, content: str) -> float:
    if not query or not content:
        return 0.0
    q = set(_tokenize(query))
    c = set(_tokenize(content))
    if not q or not c:
        return 0.0
    return len(q & c) / max(len(q), 1)


class MemoryVectorStore(VectorStore):
    """In-process vector store used for local development and tests."""

    backend_name = "memory"

    def _bucket(self) -> List[Dict[str, Any]]:
        with _lock:
            return _store[self.env]

    def ensure_schema(self) -> None:  # pragma: no cover - schema-less backend
        return None

    def insert_documents(self, documents: Sequence[Mapping[str, Any]]) -> int:
        inserted = 0
        with _lock:
            bucket = self._bucket()
            for doc in documents:
                fallback_id = len(bucket) + inserted
                bucket.append(self._normalize(doc, fallback_id=fallback_id))
                inserted += 1
        return inserted

    def upsert_documents(self, documents: Sequence[Mapping[str, Any]]) -> int:
        updated = 0
        with _lock:
            bucket = self._bucket()
            by_id = {doc["chunk_id"]: idx for idx, doc in enumerate(bucket) if "chunk_id" in doc}
            for doc in documents:
                fallback_id = len(bucket)
                normalized = self._normalize(doc, fallback_id=fallback_id)
                chunk_id = normalized["chunk_id"]
                if chunk_id in by_id:
                    bucket[by_id[chunk_id]] = normalized
                else:
                    bucket.append(normalized)
                updated += 1
        return updated

    def delete_all(self) -> int:
        with _lock:
            bucket = self._bucket()
            count = len(bucket)
            bucket.clear()
            return count

    def delete_by_source_hash(self, source_hash: str) -> int:
        if not source_hash:
            return 0
        removed = 0
        with _lock:
            bucket = self._bucket()
            keep = []
            for doc in bucket:
                metadata = doc.get("metadata") or {}
                if metadata.get("source_hash") == source_hash:
                    removed += 1
                else:
                    keep.append(doc)
            bucket[:] = keep
        return removed

    def count_documents(self) -> int:
        with _lock:
            return len(self._bucket())

    def count_documents_for_source(self, source_hash: str) -> int:
        if not source_hash:
            return 0
        with _lock:
            return sum(1 for doc in self._bucket() if (doc.get("metadata") or {}).get("source_hash") == source_hash)

    def get_sources_with_chunk_counts(self) -> Dict[str, Any]:
        with _lock:
            counts: Dict[str, int] = defaultdict(int)
            for doc in self._bucket():
                metadata = doc.get("metadata") or {}
                source = metadata.get("source_file") or metadata.get("source_hash") or "unknown"
                counts[source] += 1
            return dict(counts)

    def query(
        self,
        vector: Optional[Sequence[float]],
        top_k: int = 5,
        filters: Optional[Mapping[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        filters = filters or {}
        query_text = str(filters.get("query_text", ""))
        results: List[Dict[str, Any]] = []
        with _lock:
            for doc in self._bucket():
                content = doc.get("content") or ""
                metadata = doc.get("metadata") or {}
                score = _lexical_score(query_text, content)
                if score <= 0:
                    continue
                results.append(
                    {
                        "chunk_id": doc.get("chunk_id"),
                        "content": content,
                        "metadata": deepcopy(metadata),
                        "score": score,
                        "source_file": metadata.get("source_file"),
                    }
                )
        results.sort(key=lambda item: item.get("score", 0.0), reverse=True)
        return results[: max(1, top_k)]

    def close(self) -> None:  # pragma: no cover - no resources to release
        return None

    def _normalize(self, doc: Mapping[str, Any], *, fallback_id: int) -> Dict[str, Any]:
        chunk_id = str(doc.get("chunk_id") or doc.get("id") or doc.get("uuid") or fallback_id)
        content = doc.get("content") or doc.get("text") or ""
        metadata = doc.get("metadata") or {}
        if not isinstance(metadata, dict):
            metadata = dict(metadata)
        return {
            "chunk_id": chunk_id,
            "content": str(content),
            "metadata": deepcopy(metadata),
        }


__all__ = ["MemoryVectorStore"]
