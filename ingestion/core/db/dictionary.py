"""
Dictionary storage backends.

Provides a Postgres implementation with unique (source_id, normalized_term)
upserts and an in-memory fallback used for tests.
"""

from __future__ import annotations

import logging
from typing import Dict, Iterable, MutableMapping, Optional, TypedDict

from ingestion.config import Settings
from ingestion.core.db.postgres import PostgresPool

try:
    from psycopg.types.json import Json
except ImportError:  # pragma: no cover - optional dependency
    Json = None  # type: ignore[assignment]

_LOG = logging.getLogger(__name__)


class DictionaryEntry(TypedDict, total=False):
    source_id: str
    normalized_term: str
    raw_text: str
    page_number: Optional[int]
    section_title: Optional[str]
    facets: Optional[Dict]


class _BaseDictionaryStore:
    def upsert_terms(
        self,
        source_id: str,
        entries: Iterable[DictionaryEntry],
        *,
        refresh: bool,
    ) -> int:
        raise NotImplementedError

    def delete_source(self, source_id: str) -> None:
        raise NotImplementedError

    def count_terms(self, source_id: str) -> int:
        raise NotImplementedError

    def close(self) -> None:  # pragma: no cover - optional override
        pass


class _InMemoryDictionaryStore(_BaseDictionaryStore):
    def __init__(self) -> None:
        self._store: MutableMapping[str, Dict[str, DictionaryEntry]] = {}

    def upsert_terms(
        self,
        source_id: str,
        entries: Iterable[DictionaryEntry],
        *,
        refresh: bool,
    ) -> int:
        bucket = self._store.setdefault(source_id, {})
        if refresh:
            bucket.clear()
        count = 0
        for entry in entries:
            normalized = entry["normalized_term"]
            bucket[normalized] = entry
            count += 1
        _LOG.debug("In-memory dictionary updated", extra={"source_id": source_id, "count": count})
        return count

    def delete_source(self, source_id: str) -> None:
        self._store.pop(source_id, None)

    def count_terms(self, source_id: str) -> int:
        bucket = self._store.get(source_id, {})
        return len(bucket)


class _PostgresDictionaryStore(_BaseDictionaryStore):
    def __init__(self, settings: Settings) -> None:
        if Json is None:
            raise RuntimeError("psycopg extras not available")
        self._pool = PostgresPool(settings)
        self._ensure_schema()

    def _ensure_schema(self) -> None:
        with self._pool.connection() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS ingestion_dictionary (
                    source_id TEXT NOT NULL,
                    normalized_term TEXT NOT NULL,
                    raw_text TEXT NOT NULL,
                    page_number INTEGER,
                    section_title TEXT,
                    facets JSONB,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    CONSTRAINT ingestion_dictionary_pk PRIMARY KEY (source_id, normalized_term)
                );
                """
            )

    def upsert_terms(
        self,
        source_id: str,
        entries: Iterable[DictionaryEntry],
        *,
        refresh: bool,
    ) -> int:
        with self._pool.connection() as conn:
            if refresh:
                conn.execute("DELETE FROM ingestion_dictionary WHERE source_id = %s", (source_id,))
            count = 0
            for entry in entries:
                facets_payload = Json(entry["facets"]) if entry.get("facets") is not None else None
                conn.execute(
                    """
                    INSERT INTO ingestion_dictionary (source_id, normalized_term, raw_text, page_number, section_title, facets)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    ON CONFLICT (source_id, normalized_term)
                    DO UPDATE SET
                        raw_text = EXCLUDED.raw_text,
                        page_number = EXCLUDED.page_number,
                        section_title = EXCLUDED.section_title,
                        facets = EXCLUDED.facets,
                        updated_at = NOW();
                    """,
                    (
                        source_id,
                        entry["normalized_term"],
                        entry["raw_text"],
                        entry.get("page_number"),
                        entry.get("section_title"),
                        facets_payload,
                    ),
                )
                count += 1
        _LOG.info("Dictionary upserted", extra={"source_id": source_id, "count": count})
        return count

    def delete_source(self, source_id: str) -> None:
        with self._pool.connection() as conn:
            conn.execute("DELETE FROM ingestion_dictionary WHERE source_id = %s", (source_id,))
        _LOG.info("Dictionary terms removed", extra={"source_id": source_id})

    def count_terms(self, source_id: str) -> int:
        with self._pool.connection() as conn:
            result = conn.execute(
                "SELECT COUNT(*) FROM ingestion_dictionary WHERE source_id = %s",
                (source_id,),
            ).fetchone()
            return int(result[0]) if result else 0

    def close(self) -> None:
        self._pool.close()


_GLOBAL_STORE: _BaseDictionaryStore | None = None


def get_dictionary_store(settings: Settings) -> _BaseDictionaryStore:
    global _GLOBAL_STORE

    if _GLOBAL_STORE is not None:
        return _GLOBAL_STORE

    backend = settings.dictionary_backend.lower()
    if backend == "postgres":
        try:
            _GLOBAL_STORE = _PostgresDictionaryStore(settings)
        except Exception as exc:  # pragma: no cover - fallback for tests or missing deps
            _LOG.warning("Falling back to in-memory dictionary store: %s", exc)
            _GLOBAL_STORE = _InMemoryDictionaryStore()
    elif backend == "memory":
        _GLOBAL_STORE = _InMemoryDictionaryStore()
    else:
        _LOG.warning("Unknown dictionary backend '%s', defaulting to memory", backend)
        _GLOBAL_STORE = _InMemoryDictionaryStore()
    return _GLOBAL_STORE


def reset_dictionary_store() -> None:
    global _GLOBAL_STORE
    if _GLOBAL_STORE is not None:
        _GLOBAL_STORE.close()
    _GLOBAL_STORE = None


__all__ = [
    "DictionaryEntry",
    "get_dictionary_store",
    "reset_dictionary_store",
]
