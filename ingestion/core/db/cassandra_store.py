"""
Cassandra storage helpers for embedding persistence.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from typing import Dict, Iterable, List, MutableMapping, Optional, Sequence, TypedDict

from ingestion.config import Settings

os.environ.setdefault("CASSANDRA_DRIVER_EVENT_LOOP", "asyncio")
os.environ.setdefault("CASSANDRA_DRIVER_NO_EXTENSIONS", "1")

try:  # pragma: no cover - optional dependency
    from cassandra import ConsistencyLevel
    from cassandra.auth import PlainTextAuthProvider
    from cassandra.cluster import Cluster, Session
    from cassandra.query import PreparedStatement, SimpleStatement
    from cassandra.io.asyncioreactor import AsyncioConnection
    from cassandra.policies import AddressTranslator
except Exception:  # pragma: no cover - fallback to in-memory implementation
    Cluster = None  # type: ignore[assignment]
    Session = None  # type: ignore[assignment]
    PreparedStatement = None  # type: ignore[assignment]
    ConsistencyLevel = None  # type: ignore[assignment]
    SimpleStatement = None  # type: ignore[assignment]
    AsyncioConnection = None  # type: ignore[assignment]
    AddressTranslator = None  # type: ignore[assignment]

_LOG = logging.getLogger(__name__)


class EmbeddingRow(TypedDict, total=False):
    document_id: str
    source_id: str
    element_id: str
    chunk_id: str
    chunk_index: int
    text: str
    system: Optional[str]
    source: Optional[str]
    section: Optional[str]
    tags: Optional[Sequence[str]]
    page_number: Optional[int]
    section_title: Optional[str]
    text_hash: str
    metadata_hash: str
    vector_hash: str
    embedding: Sequence[float]
    facets: Optional[dict]


class _BaseCassandraStore:
    """Common interface for Cassandra persistence backends."""

    def upsert_embeddings(
        self,
        document_id: str,
        rows: Iterable[EmbeddingRow],
        *,
        refresh: bool,
    ) -> int:
        raise NotImplementedError

    def delete_source(self, document_id: str) -> None:
        raise NotImplementedError

    def fetch_source(self, document_id: str) -> List[EmbeddingRow]:
        raise NotImplementedError

    def close(self) -> None:  # pragma: no cover - optional override
        pass


if AddressTranslator is not None:

    class _StaticAddressTranslator(AddressTranslator):
        def __init__(self, target: str) -> None:
            self._target = target

        def translate(self, addr):  # type: ignore[override]
            return self._target

else:  # pragma: no cover - dependency missing

    _StaticAddressTranslator = None  # type: ignore[assignment]


class _InMemoryCassandraStore(_BaseCassandraStore):
    def __init__(self) -> None:
        self._store: MutableMapping[str, Dict[str, EmbeddingRow]] = {}

    def upsert_embeddings(
        self,
        document_id: str,
        rows: Iterable[EmbeddingRow],
        *,
        refresh: bool,
    ) -> int:
        bucket = self._store.setdefault(document_id, {})
        if refresh:
            bucket.clear()
        count = 0
        for row in rows:
            element_id = row.get("element_id") or row.get("chunk_id")
            chunk_index = row.get("chunk_index", 0)
            key = f"{element_id}:{chunk_index}"
            bucket[key] = dict(row)
            count += 1
        return count

    def delete_source(self, document_id: str) -> None:
        self._store.pop(document_id, None)

    def fetch_source(self, document_id: str) -> List[EmbeddingRow]:
        bucket = self._store.get(document_id, {})
        return sorted(
            bucket.values(),
            key=lambda item: (item.get("element_id") or item.get("chunk_id"), item.get("chunk_index", 0)),
        )

    def close(self) -> None:
        self._store.clear()


def _resolve_consistency(level: str) -> int:
    if ConsistencyLevel is None:  # pragma: no cover - handled by fallback
        return 0
    name = level.upper()
    if not hasattr(ConsistencyLevel, name):
        _LOG.warning("Unknown Cassandra consistency '%s', defaulting to LOCAL_QUORUM", level)
        name = "LOCAL_QUORUM"
    return getattr(ConsistencyLevel, name)


@dataclass(slots=True)
class _CassandraStore(_BaseCassandraStore):
    settings: Settings

    def __post_init__(self) -> None:
        if Cluster is None or Session is None:
            raise RuntimeError("cassandra-driver is not installed.")

        auth_provider = None
        if self.settings.cassandra_username and self.settings.cassandra_password:
            auth_provider = PlainTextAuthProvider(
                username=self.settings.cassandra_username,
                password=self.settings.cassandra_password,
            )

        cluster_kwargs = {
            "port": self.settings.cassandra_port,
            "auth_provider": auth_provider,
        }
        # AsyncioConnection disabled for Celery worker compatibility
        # Standard blocking connection works reliably with multiprocessing/solo pools
        # if AsyncioConnection is not None:
        #     cluster_kwargs["connection_class"] = AsyncioConnection
        override_address = os.getenv("CASSANDRA_TRANSLATED_ADDRESS")
        if override_address and _StaticAddressTranslator is not None:
            cluster_kwargs["address_translator"] = _StaticAddressTranslator(override_address)
        self._cluster = Cluster(self.settings.cassandra_hosts, **cluster_kwargs)
        self._session: Session = self._cluster.connect()
        self._keyspace = self.settings.cassandra_keyspace
        self._dimension = self.settings.embedding_dimension
        self._consistency = _resolve_consistency(self.settings.cassandra_consistency)
        self._ensure_schema()
        self._session.set_keyspace(self._keyspace)
        self._insert_stmt: PreparedStatement = self._session.prepare(
            """
            INSERT INTO embeddings (
                document_id,
                element_id,
                chunk_index,
                text,
                system,
                source,
                section,
                tags,
                page_number,
                section_title,
                text_hash,
                metadata_hash,
                vector_hash,
                facets,
                embedding,
                created_at,
                updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, toTimestamp(now()), toTimestamp(now()))
            """
        )
        self._insert_stmt.consistency_level = self._consistency

        self._select_stmt: PreparedStatement = self._session.prepare(
            """
            SELECT element_id, chunk_index, text, system, source, section, tags,
                   page_number, section_title, text_hash, metadata_hash, vector_hash, facets, embedding
            FROM embeddings WHERE document_id = ?
            ORDER BY element_id ASC, chunk_index ASC
            """
        )
        self._select_stmt.consistency_level = self._consistency

        self._delete_stmt: PreparedStatement = self._session.prepare(
            "DELETE FROM embeddings WHERE document_id = ?"
        )
        self._delete_stmt.consistency_level = self._consistency

    def _ensure_schema(self) -> None:
        replication = "{'class': 'SimpleStrategy', 'replication_factor': 1}"
        self._session.execute(
            f"CREATE KEYSPACE IF NOT EXISTS {self._keyspace} WITH replication = {replication};"
        )
        self._session.set_keyspace(self._keyspace)
        self._session.execute(
            f"""
            CREATE TABLE IF NOT EXISTS embeddings (
                document_id TEXT,
                element_id TEXT,
                chunk_index INT,
                text TEXT,
                system TEXT,
                source TEXT,
                section TEXT,
                tags SET<TEXT>,
                page_number INT,
                section_title TEXT,
                text_hash TEXT,
                metadata_hash TEXT,
                vector_hash TEXT,
                facets TEXT,
                embedding vector<FLOAT, {self._dimension}>,
                created_at TIMESTAMP,
                updated_at TIMESTAMP,
                PRIMARY KEY ((document_id), element_id, chunk_index)
            ) WITH CLUSTERING ORDER BY (element_id ASC, chunk_index ASC);
            """
        )
        index_statements = [
            "CREATE CUSTOM INDEX IF NOT EXISTS embeddings_system_idx ON embeddings (system) USING 'StorageAttachedIndex';",
            "CREATE CUSTOM INDEX IF NOT EXISTS embeddings_source_idx ON embeddings (source) USING 'StorageAttachedIndex';",
            "CREATE CUSTOM INDEX IF NOT EXISTS embeddings_section_idx ON embeddings (section) USING 'StorageAttachedIndex';",
            "CREATE CUSTOM INDEX IF NOT EXISTS embeddings_tags_idx ON embeddings (values(tags)) USING 'StorageAttachedIndex';",
            "CREATE CUSTOM INDEX IF NOT EXISTS embeddings_vector_ann ON embeddings (vector) USING 'StorageAttachedIndex' WITH OPTIONS = {'similarity_function': 'cosine'};",
        ]
        for cql in index_statements:
            try:
                self._session.execute(cql)
            except Exception:  # pragma: no cover - index creation best effort
                _LOG.debug("Failed to create Cassandra index with statement: %s", cql, exc_info=True)

    def upsert_embeddings(
        self,
        document_id: str,
        rows: Iterable[EmbeddingRow],
        *,
        refresh: bool,
    ) -> int:
        if refresh:
            self._session.execute(self._delete_stmt, (document_id,))

        count = 0
        for row in rows:
            vector = list(row["embedding"])
            if len(vector) != self._dimension:
                raise ValueError(
                    f"Embedding dimension mismatch: expected {self._dimension}, got {len(vector)}"
                )

            facets_payload = json.dumps(row.get("facets") or {})
            tags = row.get("tags") or []
            tag_values = [str(tag) for tag in tags]

            self._session.execute(
                self._insert_stmt,
                (
                    document_id,
                    row.get("element_id") or row.get("chunk_id"),
                    row.get("chunk_index", 0),
                    row.get("text"),
                    row.get("system"),
                    row.get("source"),
                    row.get("section") or row.get("section_title"),
                    set(tag_values),
                    row.get("page_number"),
                    row.get("section_title"),
                    row.get("text_hash"),
                    row.get("metadata_hash"),
                    row.get("vector_hash"),
                    facets_payload,
                    vector,
                ),
            )
            count += 1
        return count

    def delete_source(self, document_id: str) -> None:
        self._session.execute(self._delete_stmt, (document_id,))

    def fetch_source(self, document_id: str) -> List[EmbeddingRow]:
        result = self._session.execute(self._select_stmt, (document_id,))
        rows: List[EmbeddingRow] = []
        for row in result:
            facets_payload = row.facets
            facets = json.loads(facets_payload) if facets_payload else None
            tags = list(row.tags) if hasattr(row, "tags") and row.tags is not None else []
            rows.append(
                EmbeddingRow(
                    document_id=document_id,
                    source_id=document_id,
                    element_id=row.element_id,
                    chunk_id=row.element_id,
                    chunk_index=row.chunk_index,
                    text=row.text,
                    system=row.system,
                    source=row.source,
                    section=row.section,
                    tags=tags,
                    page_number=row.page_number,
                    section_title=row.section_title,
                    text_hash=row.text_hash,
                    metadata_hash=row.metadata_hash,
                    vector_hash=row.vector_hash,
                    embedding=list(row.embedding),
                    facets=facets,
                )
            )
        return rows

    def close(self) -> None:
        try:
            self._session.shutdown()
        finally:
            self._cluster.shutdown()


_GLOBAL_STORE: _BaseCassandraStore | None = None


def get_cassandra_store(settings: Settings) -> _BaseCassandraStore:
    """Return the configured Cassandra store (singleton per process)."""

    global _GLOBAL_STORE

    backend = settings.cassandra_backend.lower()
    if _GLOBAL_STORE is not None:
        return _GLOBAL_STORE

    if backend == "memory" or Cluster is None:
        if Cluster is None and backend != "memory":
            _LOG.warning(
                "cassandra-driver not available; falling back to in-memory store for tests."
            )
        _GLOBAL_STORE = _InMemoryCassandraStore()
    else:
        _GLOBAL_STORE = _CassandraStore(settings=settings)

    return _GLOBAL_STORE


def reset_cassandra_store() -> None:
    """Reset the cached Cassandra store (used by tests)."""

    global _GLOBAL_STORE
    if _GLOBAL_STORE is not None:
        _GLOBAL_STORE.close()
    _GLOBAL_STORE = None


__all__ = [
    "EmbeddingRow",
    "get_cassandra_store",
    "reset_cassandra_store",
]
