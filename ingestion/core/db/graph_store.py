"""
Graph storage helpers with Neo4j backend and in-memory fallback.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, Iterable, MutableMapping, Optional, Sequence, TypedDict

from ingestion.config import Settings

try:  # pragma: no cover - optional dependency
    from neo4j import GraphDatabase, basic_auth
    from neo4j.exceptions import Neo4jError  # type: ignore
except Exception:  # pragma: no cover - fallback when neo4j driver missing
    GraphDatabase = None  # type: ignore[assignment]
    Neo4jError = Exception  # type: ignore[assignment]

_LOG = logging.getLogger(__name__)


class DocumentNode(TypedDict, total=False):
    document_id: str
    source_path: str
    chunk_count: int
    title: str | None
    refresh: bool
    checksum: str | None
    updated_at: str


class ChunkNode(TypedDict, total=False):
    chunk_id: str
    chunk_index: int
    text: str
    page_number: int | None
    section_title: str | None
    text_hash: str
    metadata_hash: str
    vector_hash: str
    facets: dict | None
    source_id: str
    updated_at: str


class GraphWriteResult(TypedDict, total=False):
    nodes_created: int
    relationships_created: int
    document_id: str


class GraphRemovalResult(TypedDict, total=False):
    document_id: str
    nodes_removed: int
    relationships_removed: int


class DocumentGraph(TypedDict, total=False):
    document: DocumentNode
    chunks: Sequence[ChunkNode]


class _BaseGraphStore:
    """Common interface for graph storage backends."""

    def upsert_document_graph(
        self,
        document: DocumentNode,
        chunks: Iterable[ChunkNode],
        *,
        refresh: bool,
    ) -> GraphWriteResult:
        raise NotImplementedError

    def fetch_document(self, document_id: str) -> Optional[DocumentGraph]:  # pragma: no cover - optional
        return None

    def delete_document(self, document_id: str) -> GraphRemovalResult:
        raise NotImplementedError

    def close(self) -> None:  # pragma: no cover - optional override
        pass


class _InMemoryGraphStore(_BaseGraphStore):
    def __init__(self) -> None:
        self._documents: MutableMapping[str, DocumentGraph] = {}

    def upsert_document_graph(
        self,
        document: DocumentNode,
        chunks: Iterable[ChunkNode],
        *,
        refresh: bool,
    ) -> GraphWriteResult:
        document_id = document["document_id"]
        existing = self._documents.get(document_id)
        chunk_list = list(chunks)
        nodes_created = 0
        if refresh or existing is None:
            nodes_created = len(chunk_list) + 1 if chunk_list else 1
        else:
            previous_chunk_ids = {chunk["chunk_id"] for chunk in existing.get("chunks", [])}
            new_chunks = [chunk for chunk in chunk_list if chunk["chunk_id"] not in previous_chunk_ids]
            nodes_created = len(new_chunks)
        self._documents[document_id] = DocumentGraph(document=document, chunks=chunk_list)
        return GraphWriteResult(
            nodes_created=nodes_created,
            relationships_created=len(chunk_list),
            document_id=document_id,
        )

    def fetch_document(self, document_id: str) -> Optional[DocumentGraph]:
        return self._documents.get(document_id)

    def delete_document(self, document_id: str) -> GraphRemovalResult:
        graph = self._documents.pop(document_id, None)
        if not graph:
            return GraphRemovalResult(document_id=document_id, nodes_removed=0, relationships_removed=0)
        node_count = 1 + len(graph.get("chunks", []))
        return GraphRemovalResult(
            document_id=document_id,
            nodes_removed=node_count,
            relationships_removed=0,
        )

    def close(self) -> None:
        self._documents.clear()


@dataclass(slots=True)
class _Neo4jGraphStore(_BaseGraphStore):
    settings: Settings

    def __post_init__(self) -> None:
        if GraphDatabase is None:
            raise RuntimeError("neo4j driver is not installed.")
        self._driver = GraphDatabase.driver(
            self.settings.neo4j_uri,
            auth=basic_auth(self.settings.neo4j_user, self.settings.neo4j_password),
        )
        self._database = getattr(self.settings, "neo4j_database", "neo4j") or "neo4j"
        self._constraints_ready = False

    def _run_write(self, session, func, **kwargs):
        try:  # neo4j >= 5
            return session.execute_write(func, **kwargs)
        except AttributeError:  # pragma: no cover - neo4j < 5 fallback
            return session.write_transaction(func, **kwargs)

    @staticmethod
    def _ensure_constraints_tx(tx) -> None:
        tx.run(
            "CREATE CONSTRAINT document_document_id IF NOT EXISTS "
            "FOR (d:Document) REQUIRE d.document_id IS UNIQUE"
        )
        tx.run(
            "CREATE CONSTRAINT chunk_chunk_id IF NOT EXISTS "
            "FOR (c:Chunk) REQUIRE c.chunk_id IS UNIQUE"
        )
        tx.run(
            "CREATE CONSTRAINT chunk_text_hash IF NOT EXISTS "
            "FOR (c:Chunk) REQUIRE c.text_hash IS NOT NULL"
        )
        tx.run(
            "CREATE CONSTRAINT chunk_metadata_hash IF NOT EXISTS "
            "FOR (c:Chunk) REQUIRE c.metadata_hash IS NOT NULL"
        )
        tx.run(
            "CREATE INDEX chunk_section_title IF NOT EXISTS "
            "FOR (c:Chunk) ON (c.section_title)"
        )
        tx.run(
            "CREATE INDEX chunk_page_number IF NOT EXISTS "
            "FOR (c:Chunk) ON (c.page_number)"
        )
        tx.run(
            "CREATE INDEX chunk_source_id IF NOT EXISTS "
            "FOR (c:Chunk) ON (c.source_id)"
        )
        tx.run(
            "CREATE CONSTRAINT contains_order IF NOT EXISTS "
            "FOR ()-[r:CONTAINS]-() REQUIRE r.order IS NOT NULL"
        )

    @staticmethod
    def _delete_document_tx(tx, *, document_id: str) -> None:
        result = tx.run(
            """
            MATCH (d:Document {document_id: $document_id})
            DETACH DELETE d
            """,
            document_id=document_id,
        )
        return result.consume().counters

    @staticmethod
    def _upsert_document_tx(tx, *, document: DocumentNode):
        result = tx.run(
            """
            MERGE (d:Document {document_id: $document_id})
            SET d += $props
            RETURN d.document_id AS document_id
            """,
            document_id=document["document_id"],
            props=document,
        )
        return result.consume().counters

    @staticmethod
    def _upsert_chunks_tx(tx, *, chunks: Sequence[ChunkNode]):
        if not chunks:
            return tx.run("RETURN 0 AS skipped").consume().counters
        result = tx.run(
            """
            UNWIND $chunks AS chunk
            MERGE (c:Chunk {chunk_id: chunk.chunk_id})
            SET c += chunk
            RETURN count(c) AS total
            """,
            chunks=chunks,
        )
        return result.consume().counters

    @staticmethod
    def _upsert_contains_tx(tx, *, document_id: str, chunks: Sequence[ChunkNode]):
        if not chunks:
            return tx.run("RETURN 0 AS skipped").consume().counters
        result = tx.run(
            """
            MATCH (d:Document {document_id: $document_id})
            UNWIND $chunks AS chunk
            MATCH (c:Chunk {chunk_id: chunk.chunk_id})
            MERGE (d)-[r:CONTAINS]->(c)
            SET r.order = chunk.chunk_index,
                r.page_number = chunk.page_number
            RETURN count(r) AS total
            """,
            document_id=document_id,
            chunks=chunks,
        )
        return result.consume().counters

    def upsert_document_graph(
        self,
        document: DocumentNode,
        chunks: Iterable[ChunkNode],
        *,
        refresh: bool,
    ) -> GraphWriteResult:
        chunk_list = list(chunks)
        document_id = document["document_id"]
        with self._driver.session(database=self._database) as session:
            if not self._constraints_ready:
                self._run_write(session, self._ensure_constraints_tx)
                self._constraints_ready = True
            if refresh:
                self._run_write(session, self._delete_document_tx, document_id=document_id)

            doc_counters = self._run_write(session, self._upsert_document_tx, document=document)
            chunk_counters = self._run_write(session, self._upsert_chunks_tx, chunks=chunk_list)
            rel_counters = self._run_write(
                session,
                self._upsert_contains_tx,
                document_id=document_id,
                chunks=chunk_list,
            )

        nodes_created = int(doc_counters.nodes_created + chunk_counters.nodes_created)
        relationships_created = int(rel_counters.relationships_created)

        return GraphWriteResult(
            nodes_created=nodes_created,
            relationships_created=relationships_created,
            document_id=document_id,
        )

    def delete_document(self, document_id: str) -> GraphRemovalResult:
        with self._driver.session(database=self._database) as session:
            counters = self._run_write(session, self._delete_document_tx, document_id=document_id)
        nodes_removed = int(getattr(counters, "nodes_deleted", 0))
        relationships_removed = int(getattr(counters, "relationships_deleted", 0))
        return GraphRemovalResult(
            document_id=document_id,
            nodes_removed=nodes_removed,
            relationships_removed=relationships_removed,
        )

    def close(self) -> None:
        try:
            self._driver.close()
        except Neo4jError:  # pragma: no cover - passive shutdown
            pass


_GLOBAL_STORE: _BaseGraphStore | None = None


def get_graph_store(settings: Settings) -> _BaseGraphStore:
    """Return the configured graph store backend."""

    global _GLOBAL_STORE

    if _GLOBAL_STORE is not None:
        return _GLOBAL_STORE

    backend = getattr(settings, "neo4j_backend", "neo4j").lower()
    if backend == "memory":
        _GLOBAL_STORE = _InMemoryGraphStore()
    elif backend in {"neo4j", "bolt"}:
        try:
            _GLOBAL_STORE = _Neo4jGraphStore(settings=settings)
        except Exception as exc:  # pragma: no cover - fallback if driver missing
            _LOG.warning("Neo4j backend unavailable (%s); falling back to memory store", exc)
            _GLOBAL_STORE = _InMemoryGraphStore()
    else:
        _LOG.warning("Unknown graph backend '%s', defaulting to memory", backend)
        _GLOBAL_STORE = _InMemoryGraphStore()
    return _GLOBAL_STORE


def reset_graph_store() -> None:
    """Reset the cached graph store (used by tests)."""

    global _GLOBAL_STORE
    if _GLOBAL_STORE is not None:
        _GLOBAL_STORE.close()
    _GLOBAL_STORE = None


__all__ = [
    "ChunkNode",
    "DocumentGraph",
    "DocumentNode",
    "GraphWriteResult",
    "GraphRemovalResult",
    "get_graph_store",
    "reset_graph_store",
]
