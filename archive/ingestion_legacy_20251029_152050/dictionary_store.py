#!/usr/bin/env python3
"""
dictionary_store.py - Postgres-backed dictionary persistence helpers
====================================================================

Provides a thin abstraction over the Postgres `dictionary_documents`
table so pipeline stages can store and retrieve Pass A/C dictionary
artifacts without touching MongoDB. The module is intentionally small
and synchronous so it can be imported both by workers and standalone
scripts.
"""

from __future__ import annotations

import os
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any, Dict, Iterator, List, Optional

import psycopg2
from psycopg2.extras import Json


DEFAULT_TABLE = "dictionary_documents"


class DictionaryStoreError(RuntimeError):
    """Raised when dictionary persistence fails."""


def _env(name: str, default: Optional[str] = None) -> str:
    value = os.getenv(name, default)
    if value is None:
        raise DictionaryStoreError(f"Environment variable '{name}' is required for dictionary storage")
    return value


def _pg_connect_kwargs(
    *,
    host: Optional[str] = None,
    port: Optional[int] = None,
    database: Optional[str] = None,
    user: Optional[str] = None,
    password: Optional[str] = None,
) -> Dict[str, Any]:
    """Build keyword arguments for psycopg2.connect using env fallbacks."""

    def _int(value: Optional[str], default: int) -> int:
        try:
            return int(value) if value is not None else default
        except ValueError as exc:  # pragma: no cover - defensive
            raise DictionaryStoreError(f"Invalid integer for Postgres port '{value}'") from exc

    return {
        "host": host or os.getenv("POSTGRES_HOST", "postgres"),
        "port": _int(str(port) if port is not None else os.getenv("POSTGRES_PORT"), 5432),
        "dbname": database or os.getenv("POSTGRES_DB", "ttrpg"),
        "user": user or _env("POSTGRES_USER", "postgres"),
        "password": password or _env("POSTGRES_PASSWORD", "postgres"),
    }


@dataclass
class UpsertSummary:
    document_id: str
    stage: str
    term_count: int
    category_count: int
    toc_count: int


class DictionaryStore:
    """Lightweight Postgres helper for dictionary persistence."""

    def __init__(
        self,
        *,
        host: Optional[str] = None,
        port: Optional[int] = None,
        database: Optional[str] = None,
        user: Optional[str] = None,
        password: Optional[str] = None,
        table_name: str = DEFAULT_TABLE,
        autocommit: bool = True,
    ) -> None:
        self.table_name = table_name
        self.conn = psycopg2.connect(**_pg_connect_kwargs(
            host=host,
            port=port,
            database=database,
            user=user,
            password=password,
        ))
        if autocommit:
            self.conn.autocommit = True
        self._ensure_schema()

    @contextmanager
    def cursor(self) -> Iterator["psycopg2.extensions.cursor"]:
        cur = self.conn.cursor()
        try:
            yield cur
        finally:
            cur.close()

    def close(self) -> None:
        if self.conn:
            self.conn.close()

    # ------------------------------------------------------------------ #
    # Schema + CRUD helpers
    # ------------------------------------------------------------------ #
    def _ensure_schema(self) -> None:
        """Create dictionary table if it does not exist."""
        ddl = f"""
        CREATE TABLE IF NOT EXISTS {self.table_name} (
            document_id TEXT PRIMARY KEY,
            stage TEXT NOT NULL,
            source_path TEXT,
            sha256 TEXT,
            file_size_bytes BIGINT,
            computed_at TIMESTAMPTZ,
            gate_metadata JSONB,
            metadata JSONB,
            elements JSONB,
            toc JSONB,
            categories JSONB,
            terms JSONB,
            statistics JSONB,
            warnings JSONB,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW()
        );
        CREATE INDEX IF NOT EXISTS {self.table_name}_stage_idx ON {self.table_name}(stage);
        """
        with self.cursor() as cur:
            cur.execute(ddl)

    def upsert_document(
        self,
        *,
        document_id: str,
        stage: str,
        metadata: Dict[str, Any],
        elements: Optional[List[Dict[str, Any]]] = None,
        toc: Optional[List[Dict[str, Any]]] = None,
        categories: Optional[Dict[str, Any]] = None,
        terms: Optional[List[Dict[str, Any]]] = None,
        statistics: Optional[Dict[str, Any]] = None,
        warnings: Optional[List[Dict[str, Any]]] = None,
        gate_metadata: Optional[Dict[str, Any]] = None,
        source_path: Optional[str] = None,
        sha256: Optional[str] = None,
        file_size_bytes: Optional[int] = None,
        computed_at: Optional[str] = None,
    ) -> UpsertSummary:
        """Insert or update a dictionary document row."""
        with self.cursor() as cur:
            cur.execute(
                f"""
                INSERT INTO {self.table_name} (
                    document_id, stage, source_path, sha256, file_size_bytes, computed_at,
                    gate_metadata, metadata, elements, toc, categories, terms, statistics, warnings,
                    created_at, updated_at
                ) VALUES (
                    %(document_id)s, %(stage)s, %(source_path)s, %(sha256)s, %(file_size_bytes)s, %(computed_at)s,
                    %(gate_metadata)s, %(metadata)s, %(elements)s, %(toc)s, %(categories)s, %(terms)s,
                    %(statistics)s, %(warnings)s,
                    NOW(), NOW()
                )
                ON CONFLICT (document_id) DO UPDATE SET
                    stage = EXCLUDED.stage,
                    source_path = EXCLUDED.source_path,
                    sha256 = EXCLUDED.sha256,
                    file_size_bytes = EXCLUDED.file_size_bytes,
                    computed_at = EXCLUDED.computed_at,
                    gate_metadata = EXCLUDED.gate_metadata,
                    metadata = EXCLUDED.metadata,
                    elements = EXCLUDED.elements,
                    toc = EXCLUDED.toc,
                    categories = EXCLUDED.categories,
                    terms = EXCLUDED.terms,
                    statistics = EXCLUDED.statistics,
                    warnings = EXCLUDED.warnings,
                    updated_at = NOW();
                """,
                {
                    "document_id": document_id,
                    "stage": stage,
                    "source_path": source_path,
                    "sha256": sha256,
                    "file_size_bytes": file_size_bytes,
                    "computed_at": computed_at,
                    "gate_metadata": Json(gate_metadata) if gate_metadata is not None else None,
                    "metadata": Json(metadata) if metadata is not None else None,
                    "elements": Json(elements) if elements is not None else None,
                    "toc": Json(toc) if toc is not None else None,
                    "categories": Json(categories) if categories is not None else None,
                    "terms": Json(terms) if terms is not None else None,
                    "statistics": Json(statistics) if statistics is not None else None,
                    "warnings": Json(warnings) if warnings is not None else None,
                },
            )

        return UpsertSummary(
            document_id=document_id,
            stage=stage,
            term_count=len(terms or []),
            category_count=len((categories or {}).get("by_system", []) if isinstance(categories, dict) else []),
            toc_count=len(toc or []),
        )

    def delete_document(self, document_id: str) -> int:
        """Delete a dictionary document. Returns rows removed."""
        with self.cursor() as cur:
            cur.execute(f"DELETE FROM {self.table_name} WHERE document_id = %s;", (document_id,))
            return cur.rowcount

    def fetch_document(self, document_id: str) -> Optional[Dict[str, Any]]:
        with self.cursor() as cur:
            cur.execute(
                f"""
                SELECT document_id, stage, metadata, toc, categories, terms, statistics, gate_metadata,
                       source_path, sha256, file_size_bytes, computed_at
                FROM {self.table_name}
                WHERE document_id = %s;
                """,
                (document_id,),
            )
            row = cur.fetchone()
            if not row:
                return None

            keys = [
                "document_id",
                "stage",
                "metadata",
                "toc",
                "categories",
                "terms",
                "statistics",
                "gate_metadata",
                "source_path",
                "sha256",
                "file_size_bytes",
                "computed_at",
            ]
            return dict(zip(keys, row))

    def fetch_terms(self, document_id: str) -> List[Dict[str, Any]]:
        """Return the stored terms array (empty list if missing)."""
        doc = self.fetch_document(document_id)
        terms = doc.get("terms") if doc else None
        return terms or []

    def summarize(self) -> Dict[str, Any]:
        """Return a lightweight summary for ops tooling."""
        with self.cursor() as cur:
            cur.execute(
                f"""
                SELECT
                    COUNT(*) as total,
                    COUNT(*) FILTER (WHERE stage = 'pass_a') AS pass_a_docs,
                    COUNT(*) FILTER (WHERE stage = 'pass_c') AS pass_c_docs
                FROM {self.table_name};
                """
            )
            total, pass_a_docs, pass_c_docs = cur.fetchone()
        return {
            "total_documents": total,
            "pass_a_documents": pass_a_docs,
            "pass_c_documents": pass_c_docs,
        }


@contextmanager
def dictionary_store(**kwargs: Any) -> Iterator[DictionaryStore]:
    store = DictionaryStore(**kwargs)
    try:
        yield store
    finally:
        store.close()
