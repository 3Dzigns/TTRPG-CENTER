from __future__ import annotations

import json
import os
import re
import time
from array import array
from datetime import datetime
from typing import Any, Dict, Mapping, Optional, Sequence, List

try:
    from cassandra.auth import PlainTextAuthProvider  # type: ignore
    from cassandra.cluster import Cluster  # type: ignore
    from cassandra.io.asyncioreactor import AsyncioConnection  # type: ignore
    from cassandra.query import SimpleStatement  # type: ignore
except Exception as cassandra_import_error:  # pragma: no cover - environment specific
    PlainTextAuthProvider = None  # type: ignore[assignment]
    Cluster = None  # type: ignore[assignment]
    AsyncioConnection = None  # type: ignore[assignment]
    SimpleStatement = None  # type: ignore[assignment]
    _CASSANDRA_IMPORT_ERROR = cassandra_import_error
else:
    _CASSANDRA_IMPORT_ERROR = None

from ..ttrpg_logging import get_logger
from .base import VectorStore

logger = get_logger(__name__)


os.environ.setdefault('CASS_DRIVER_NO_EXTENSIONS', '1')


def _ensure_dependencies() -> None:
    if Cluster is None or AsyncioConnection is None or SimpleStatement is None or PlainTextAuthProvider is None:
        if '_CASSANDRA_IMPORT_ERROR' in globals() and _CASSANDRA_IMPORT_ERROR is not None:
            raise RuntimeError("Cassandra backend unavailable: cassandra-driver failed to import.") from _CASSANDRA_IMPORT_ERROR
        raise RuntimeError("Cassandra backend unavailable: cassandra-driver is not installed.")

class CassandraVectorStore(VectorStore):
    """Vector store backed by Apache Cassandra."""

    def __init__(self, env: str) -> None:
        super().__init__(env)
        _ensure_dependencies()
        self.contact_points = [cp.strip() for cp in os.getenv("CASSANDRA_CONTACT_POINTS", "127.0.0.1").split(",") if cp.strip()]
        self.port = int(os.getenv("CASSANDRA_PORT", "9042"))
        self.keyspace = os.getenv("CASSANDRA_KEYSPACE", "ttrpg")
        self.table = os.getenv("CASSANDRA_TABLE", "chunks")
        self.username = os.getenv("CASSANDRA_USERNAME", "").strip() or None
        self.password = os.getenv("CASSANDRA_PASSWORD", "").strip() or None
        self.consistency = os.getenv("CASSANDRA_CONSISTENCY", "LOCAL_ONE").upper()
        self.vector_scan_limit = int(os.getenv("CASSANDRA_VECTOR_SCAN_LIMIT", "2000"))

        auth_provider = None
        if self.username and self.password:
            auth_provider = PlainTextAuthProvider(username=self.username, password=self.password)

        self.cluster = Cluster(self.contact_points, port=self.port, auth_provider=auth_provider, connection_class=AsyncioConnection)
        self.session = self.cluster.connect()
        self._ensure_keyspace()
        self.session.set_keyspace(self.keyspace)
        self.ensure_schema()
        self._prepare_statements()

    @property
    def backend_name(self) -> str:
        return "cassandra"

    def ensure_schema(self) -> None:
        create_table = f"""
            CREATE TABLE IF NOT EXISTS {self.table} (
                chunk_id text PRIMARY KEY,
                environment text,
                stage text,
                content text,
                payload text,
                source_hash text,
                source_file text,
                embedding blob,
                embedding_model text,
                vector_id text,
                updated_at timestamp,
                loaded_at timestamp
            )
        """
        self.session.execute(create_table)
        self.session.execute(f"CREATE INDEX IF NOT EXISTS ON {self.table} (source_hash)")
        self.session.execute(f"CREATE INDEX IF NOT EXISTS ON {self.table} (environment)")
        self.session.execute(f"CREATE INDEX IF NOT EXISTS ON {self.table} (stage)")

    # ------------------------------------------------------------------
    # Public API implementations
    # ------------------------------------------------------------------
    def insert_documents(self, documents: Sequence[Mapping[str, Any]]) -> int:
        return self._write_documents(documents)

    def upsert_documents(self, documents: Sequence[Mapping[str, Any]]) -> int:
        return self._write_documents(documents)

    def delete_all(self) -> int:
        self.session.execute(f"TRUNCATE {self.table}")
        return 0

    def delete_by_source_hash(self, source_hash: str) -> int:
        chunk_ids = self._chunk_ids_for_source(source_hash)
        deleted = 0
        for chunk_id in chunk_ids:
            self.session.execute(self.delete_stmt, (chunk_id,))
            deleted += 1
        return deleted

    def count_documents(self) -> int:
        result = self.session.execute(f"SELECT COUNT(*) FROM {self.table}")
        row = result.one()
        return int(row[0]) if row else 0

    def count_documents_for_source(self, source_hash: str) -> int:
        return len(self._chunk_ids_for_source(source_hash))

    def get_sources_with_chunk_counts(self) -> Dict[str, Any]:
        statement = SimpleStatement(
            f"SELECT chunk_id, source_hash, source_file, updated_at, loaded_at FROM {self.table} WHERE environment = %s ALLOW FILTERING"
        )
        rows = self.session.execute(statement, (self.env,))
        totals: Dict[str, Dict[str, Any]] = {}
        for row in rows:
            source_hash = row.source_hash or "unknown"
            entry = totals.setdefault(
                source_hash,
                {
                    "source_hash": source_hash,
                    "source_file": row.source_file or "Unknown Source",
                    "chunk_count": 0,
                    "last_updated": self._coerce_timestamp(row.updated_at or row.loaded_at),
                },
            )
            entry["chunk_count"] += 1
            candidate_ts = self._coerce_timestamp(row.updated_at or row.loaded_at)
            if candidate_ts and candidate_ts > entry["last_updated"]:
                entry["last_updated"] = candidate_ts
        sources = sorted(totals.values(), key=lambda x: x["chunk_count"], reverse=True)
        total_chunks = sum(item["chunk_count"] for item in sources)
        return {
            "status": "ready",
            "environment": self.env,
            "collection_name": f"{self.keyspace}.{self.table}",
            "sources": sources,
            "total_sources": len(sources),
            "total_chunks": total_chunks,
        }

    def query(
        self,
        vector: Optional[Sequence[float]],
        top_k: int = 5,
        filters: Optional[Mapping[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        filters = filters or {}
        stage = filters.get("stage", "vectorized")
        metadata_filters = filters.get("metadata")
        query_text = filters.get("query_text")
        statement = SimpleStatement(
            f"SELECT chunk_id, content, payload, embedding, embedding_model FROM {self.table} "
            "WHERE environment = %s AND stage = %s ALLOW FILTERING"
        )
        rows = self.session.execute(statement, (self.env, stage))
        results: List[Dict[str, Any]] = []
        for idx, row in enumerate(rows):
            if idx >= self.vector_scan_limit:
                break
            payload = self._deserialize_payload(row.payload)
            metadata = payload.get("metadata") if isinstance(payload, dict) else {}
            if not self._metadata_matches(metadata, metadata_filters):
                continue
            if vector is None and query_text:
                score = self._lexical_score(query_text, row.content or payload.get("content") or "", metadata)
            else:
                embedding_list = self._blob_to_vector(row.embedding)
                score = self._similarity(vector, embedding_list)
            results.append(
                {
                    "chunk_id": row.chunk_id,
                    "content": row.content or payload.get("content") or "",
                    "metadata": metadata,
                    "score": score,
                }
            )
        results.sort(key=lambda item: item.get("score", 0.0), reverse=True)
        return results[: max(1, top_k)]
    def close(self) -> None:
        try:
            self.session.shutdown()
        finally:
            self.cluster.shutdown()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _ensure_keyspace(self) -> None:
        replication = os.getenv("CASSANDRA_REPLICATION", "{'class': 'SimpleStrategy', 'replication_factor': 1}")
        create_keyspace = (
            f"CREATE KEYSPACE IF NOT EXISTS {self.keyspace} WITH replication = {replication}"
        )
        self.session.execute(create_keyspace)

    def _prepare_statements(self) -> None:
        self.insert_stmt = self.session.prepare(
            f"""
            INSERT INTO {self.table} (
                chunk_id, environment, stage, content, payload, source_hash, source_file,
                embedding, embedding_model, vector_id, updated_at, loaded_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """
        )
        self.delete_stmt = self.session.prepare(
            f"DELETE FROM {self.table} WHERE chunk_id = ?"
        )

    def _write_documents(self, documents: Sequence[Mapping[str, Any]]) -> int:
        written = 0
        for doc in documents:
            params = self._normalise_document(doc)
            self.session.execute(self.insert_stmt, params)
            written += 1
        return written

    def _normalise_document(self, doc: Mapping[str, Any]) -> tuple[Any, ...]:
        chunk_id = str(doc.get("chunk_id") or doc.get("id") or doc.get("_id") or self._fallback_chunk_id())
        content = doc.get("content") or doc.get("text") or ""
        stage = doc.get("stage") or "raw"
        source_hash = (
            doc.get("source_hash")
            or doc.get("metadata", {}).get("source_hash")
            or doc.get("metadata", {}).get("source_id")
            or doc.get("source_id")
            or "unknown"
        )
        source_file = doc.get("source_file") or doc.get("metadata", {}).get("source_file")
        payload = json.dumps(dict(doc), ensure_ascii=False, default=self._json_default)
        embedding_list = self._ensure_vector(doc.get("embedding"))
        embedding_blob = self._vector_to_blob(embedding_list) if embedding_list else None
        embedding_model = doc.get("embedding_model")
        vector_id = doc.get("vector_id")
        updated_at = self._coerce_datetime(doc.get("updated_at"))
        loaded_at = self._coerce_datetime(doc.get("loaded_at"))
        return (
            chunk_id,
            self.env,
            stage,
            content,
            payload,
            source_hash,
            source_file,
            embedding_blob,
            embedding_model,
            vector_id,
            updated_at,
            loaded_at,
        )

    def _chunk_ids_for_source(self, source_hash: str) -> List[str]:
        statement = SimpleStatement(
            f"SELECT chunk_id FROM {self.table} WHERE source_hash = %s ALLOW FILTERING"
        )
        rows = self.session.execute(statement, (source_hash,))
        return [row.chunk_id for row in rows]

    @staticmethod
    def _vector_to_blob(values: Sequence[float]) -> bytes:
        arr = array("f", [float(v) for v in values])
        return arr.tobytes()

    @staticmethod
    def _blob_to_vector(blob: Optional[bytes]) -> List[float]:
        if blob is None:
            return []
        arr = array("f")
        arr.frombytes(blob)
        return list(arr)

    @staticmethod
    def _similarity(vector: Optional[Sequence[float]], other: Sequence[float]) -> float:
        if not vector or not other or len(vector) != len(other):
            return 0.0
        dot = sum(float(a) * float(b) for a, b in zip(vector, other))
        norm_a = sum(float(a) * float(a) for a in vector) ** 0.5
        norm_b = sum(float(b) * float(b) for b in other) ** 0.5
        if not norm_a or not norm_b:
            return 0.0
        return dot / (norm_a * norm_b)

    @staticmethod
    def _ensure_vector(value: Any) -> Optional[List[float]]:
        if value is None:
            return None
        if isinstance(value, list):
            return [float(v) for v in value]
        if isinstance(value, tuple):
            return [float(v) for v in value]
        try:
            import numpy as np  # type: ignore

            if isinstance(value, np.ndarray):  # pragma: no cover - optional dependency
                return [float(v) for v in value.tolist()]
        except Exception:
            pass
        return None

    @staticmethod
    def _deserialize_payload(payload: Optional[str]) -> Dict[str, Any]:
        if not payload:
            return {}
        try:
            return json.loads(payload)
        except Exception:
            return {}

    @staticmethod
    def _metadata_matches(metadata: Mapping[str, Any], required: Optional[Mapping[str, Any]]) -> bool:
        if not required:
            return True
        for key, value in required.items():
            meta_value = metadata.get(key)
            if isinstance(value, list):
                if meta_value not in value:
                    return False
            else:
                if meta_value != value:
                    return False
        return True


@staticmethod
def _lexical_score(query: str, text: str, metadata: Mapping[str, Any]) -> float:
    if not query or not text:
        return 0.0
    tokens_q = set(re.findall(r"\w+", query.lower()))
    tokens_t = set(re.findall(r"\w+", text.lower()))
    if not tokens_q or not tokens_t:
        return 0.0
    overlap = len(tokens_q & tokens_t) / max(1, len(tokens_q))
    boost = 0.0
    q_lower = query.lower()
    t_lower = text.lower()
    if "spells per day" in q_lower and "spells per day" in t_lower:
        boost += 2.0
    if "dodge" in q_lower and "dodge" in t_lower:
        boost += 1.5
    if "paladin" in q_lower and "paladin" in t_lower:
        boost += 1.0
    chunk_type = metadata.get("chunk_type") or metadata.get("type")
    if chunk_type and str(chunk_type).lower() in {"table", "list", "table_row"}:
        boost += 0.5
    return overlap + boost

    @staticmethod
    def _coerce_datetime(value: Any) -> Optional[datetime]:
        if value is None:
            return None
        if isinstance(value, datetime):
            return value
        if isinstance(value, (int, float)):
            return datetime.fromtimestamp(float(value))
        return None

    @staticmethod
    def _coerce_timestamp(value: Any) -> float:
        if value is None:
            return time.time()
        if isinstance(value, datetime):
            return value.timestamp()
        if isinstance(value, (int, float)):
            return float(value)
        return time.time()

    @staticmethod
    def _json_default(obj: Any) -> Any:
        if isinstance(obj, datetime):
            return obj.isoformat()
        return str(obj)

    @staticmethod
    def _fallback_chunk_id() -> str:
        return f"chunk_{int(time.time()*1000)}"
