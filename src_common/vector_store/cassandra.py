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
    from cassandra.query import BatchStatement, ConsistencyLevel, SimpleStatement  # type: ignore
except Exception as cassandra_import_error:  # pragma: no cover - environment specific
    PlainTextAuthProvider = None  # type: ignore[assignment]
    Cluster = None  # type: ignore[assignment]
    BatchStatement = None  # type: ignore[assignment]
    ConsistencyLevel = None  # type: ignore[assignment]
    SimpleStatement = None  # type: ignore[assignment]
    _CASSANDRA_IMPORT_ERROR = cassandra_import_error
else:
    _CASSANDRA_IMPORT_ERROR = None

from ..ttrpg_logging import get_logger
from .base import VectorStore

logger = get_logger(__name__)


os.environ.setdefault('CASS_DRIVER_NO_EXTENSIONS', '1')


def _json_default_serializer(obj: Any) -> Any:
    """
    JSON serialization helper for datetime and other non-standard types.

    Used as the 'default' parameter for json.dumps() to handle
    datetime objects and other types that aren't natively JSON-serializable.

    Args:
        obj: Object to serialize

    Returns:
        JSON-serializable representation of obj
    """
    if isinstance(obj, datetime):
        return obj.isoformat()
    return str(obj)


def _ensure_dependencies() -> None:
    if (
        Cluster is None
        or SimpleStatement is None
        or BatchStatement is None
        or ConsistencyLevel is None
        or PlainTextAuthProvider is None
    ):
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
        default_keyspace = f"ttrpg_{env.lower()}" if env else "ttrpg_dev"
        self.keyspace = os.getenv("CASSANDRA_KEYSPACE", default_keyspace)
        self.table = os.getenv("CASSANDRA_TABLE", "chunks")
        self.username = os.getenv("CASSANDRA_USERNAME", "").strip() or None
        self.password = os.getenv("CASSANDRA_PASSWORD", "").strip() or None
        self.consistency = os.getenv("CASSANDRA_CONSISTENCY", "LOCAL_ONE").upper()
        self._consistency_level = self._resolve_consistency_level(self.consistency)
        self.write_batch_size = max(1, int(os.getenv("CASSANDRA_WRITE_BATCH_SIZE", "50")))
        self.write_retries = max(1, int(os.getenv("CASSANDRA_WRITE_RETRIES", "3")))
        self.write_retry_backoff = float(os.getenv("CASSANDRA_WRITE_RETRY_BACKOFF_SECONDS", "0.5"))
        self.write_timeout = float(os.getenv("CASSANDRA_WRITE_TIMEOUT_SECONDS", "15"))
        self.vector_scan_limit = int(os.getenv("CASSANDRA_VECTOR_SCAN_LIMIT", "2000"))

        auth_provider = None
        if self.username and self.password:
            auth_provider = PlainTextAuthProvider(username=self.username, password=self.password)

        self.cluster = Cluster(
            self.contact_points,
            port=self.port,
            auth_provider=auth_provider,
            connect_timeout=30,
            control_connection_timeout=30,
            idle_heartbeat_interval=30,
            idle_heartbeat_timeout=30
        )
        self.session = self.cluster.connect()
        self._enforce_environment_guard()
        self._ensure_keyspace()
        self.session.set_keyspace(self.keyspace)
        self.ensure_schema()
        self._prepare_statements()

    def _resolve_consistency_level(self, name: str) -> ConsistencyLevel:
        try:
            return getattr(ConsistencyLevel, name.upper())
        except AttributeError:
            logger.warning("Cassandra: unsupported consistency level '%s', defaulting to LOCAL_ONE", name)
            return ConsistencyLevel.LOCAL_ONE

    def _enforce_environment_guard(self) -> None:
        env_lower = (self.env or "").lower()
        keyspace_lower = (self.keyspace or "").lower()
        if env_lower and env_lower not in keyspace_lower:
            raise RuntimeError(
                f"Cassandra keyspace '{self.keyspace}' is not scoped for environment '{self.env}'"
            )

    @property
    def backend_name(self) -> str:
        return "cassandra"

    def ensure_schema(self) -> None:
        create_table = f"""
            CREATE TABLE IF NOT EXISTS {self.table} (
                source_hash text,
                environment text,
                chunk_id text,
                stage text,
                content text,
                payload text,
                source_file text,
                embedding blob,
                embedding_model text,
                vector_id text,
                updated_at timestamp,
                loaded_at timestamp,
                PRIMARY KEY ((source_hash, environment), chunk_id)
            ) WITH CLUSTERING ORDER BY (chunk_id ASC)
        """
        self.session.execute(create_table)
        self.session.execute(f"CREATE INDEX IF NOT EXISTS ON {self.table} (stage)")
        self.session.execute(f"CREATE INDEX IF NOT EXISTS ON {self.table} (source_file)")
        self._verify_table_schema()

    def _verify_table_schema(self) -> None:
        try:
            rows = self.session.execute(
                "SELECT column_name, kind FROM system_schema.columns WHERE keyspace_name=%s AND table_name=%s",
                (self.keyspace, self.table),
            )
            kinds = {row.column_name: row.kind for row in rows}
            expected = {"source_hash": "partition_key", "environment": "partition_key", "chunk_id": "clustering"}
            for column, expected_kind in expected.items():
                actual = kinds.get(column)
                if actual != expected_kind:
                    raise RuntimeError(
                        f"Cassandra table {self.keyspace}.{self.table} has unexpected primary key layout; column '{column}' is '{actual}', expected '{expected_kind}'"
                    )
        except RuntimeError:
            raise
        except Exception as exc:
            logger.warning("Cassandra: unable to verify schema for %s.%s: %s", self.keyspace, self.table, exc)

    # ------------------------------------------------------------------
    # Public API implementations
    # ------------------------------------------------------------------
    def insert_documents(self, documents: Sequence[Mapping[str, Any]]) -> int:
        logger.debug(f"Cassandra: Inserting {len(documents)} documents to keyspace={self.keyspace} table={self.table}")
        result = self._write_documents(documents)
        logger.info(f"Cassandra: Successfully inserted {result} documents")
        return result

    def upsert_documents(self, documents: Sequence[Mapping[str, Any]]) -> int:
        logger.debug(f"Cassandra: Upserting {len(documents)} documents to keyspace={self.keyspace} table={self.table}")
        result = self._write_documents(documents)
        logger.info(f"Cassandra: Successfully upserted {result} documents")
        return result

    def delete_all(self) -> int:
        self.session.execute(f"TRUNCATE {self.table}")
        return 0

    def delete_by_source_hash(self, source_hash: str) -> int:
        if not source_hash:
            return 0
        existing = self._chunk_ids_for_source(source_hash, self.env)
        if existing:
            self.session.execute(self.delete_partition_stmt, (source_hash, self.env))
        return len(existing)

    def count_documents(self) -> int:
        statement = SimpleStatement(
            f"SELECT COUNT(*) FROM {self.table} WHERE environment = %s ALLOW FILTERING"
        )
        row = self.session.execute(statement, (self.env,)).one()
        return int(row[0]) if row else 0

    def count_documents_for_source(self, source_hash: str, environment: Optional[str] = None) -> int:
        if not source_hash:
            return 0
        env = environment or self.env
        row = self.session.execute(self.count_stmt, (source_hash, env)).one()
        return int(row[0]) if row else 0

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

        # Convert JSON format to CQL format if needed
        if replication.startswith('{"'):
            import json
            replication_dict = json.loads(replication)
            replication_parts = [f"'{k}': {repr(v) if isinstance(v, str) else v}" for k, v in replication_dict.items()]
            replication = "{" + ", ".join(replication_parts) + "}"

        create_keyspace = (
            f"CREATE KEYSPACE IF NOT EXISTS {self.keyspace} WITH replication = {replication}"
        )
        self.session.execute(create_keyspace)

    def _prepare_statements(self) -> None:
        self.insert_stmt = self.session.prepare(
            f"""
            INSERT INTO {self.table} (
                source_hash, environment, chunk_id, stage, content, payload, source_file,
                embedding, embedding_model, vector_id, updated_at, loaded_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """
        )
        self.delete_stmt = self.session.prepare(
            f"DELETE FROM {self.table} WHERE source_hash = ? AND environment = ? AND chunk_id = ?"
        )
        self.delete_partition_stmt = self.session.prepare(
            f"DELETE FROM {self.table} WHERE source_hash = ? AND environment = ?"
        )
        self.count_stmt = self.session.prepare(
            f"SELECT COUNT(*) FROM {self.table} WHERE source_hash = ? AND environment = ?"
        )
        self.select_chunk_ids_stmt = self.session.prepare(
            f"SELECT chunk_id FROM {self.table} WHERE source_hash = ? AND environment = ?"
        )

    def _write_documents(self, documents: Sequence[Mapping[str, Any]]) -> int:
        if not documents:
            return 0

        params_list = [self._normalise_document(doc) for doc in documents]
        total_written = 0
        batches = [
            params_list[index:index + self.write_batch_size]
            for index in range(0, len(params_list), self.write_batch_size)
        ]

        for batch_index, batch_params in enumerate(batches, start=1):
            attempt = 0
            while attempt < self.write_retries:
                batch = BatchStatement(consistency_level=self._consistency_level)
                for params in batch_params:
                    batch.add(self.insert_stmt, params)

                try:
                    self.session.execute(batch, timeout=self.write_timeout)
                    total_written += len(batch_params)
                    logger.debug("Cassandra: Batch %s persisted %s rows", batch_index, len(batch_params))
                    break
                except Exception as exc:
                    attempt += 1
                    logger.warning(
                        "Cassandra: Batch %s failed on attempt %s/%s: %s",
                        batch_index,
                        attempt,
                        self.write_retries,
                        exc,
                    )
                    if attempt >= self.write_retries:
                        raise
                    time.sleep(self.write_retry_backoff * attempt)

        logger.info(
            "Cassandra: persisted %s rows across %s batch(es)",
            total_written,
            len(batches),
        )
        return total_written

    def _normalise_document(self, doc: Mapping[str, Any]) -> tuple[Any, ...]:
        chunk_id = str(doc.get("chunk_id") or doc.get("id") or doc.get("_id") or self._fallback_chunk_id())
        content = doc.get("content") or doc.get("text") or ""
        stage = doc.get("stage") or doc.get("metadata", {}).get("stage") or "vectorized"
        metadata = dict(doc.get("metadata") or {})

        doc_id = doc.get("doc_id") or metadata.get("doc_id") or doc.get("document_id")
        if not doc_id:
            raise ValueError("Vector document missing doc_id")

        source_hash = (
            doc.get("source_hash")
            or metadata.get("source_hash")
            or metadata.get("source_id")
            or doc.get("source_id")
        )
        if not source_hash:
            raise ValueError("Vector document missing source_hash")

        environment = doc.get("environment") or metadata.get("environment") or self.env
        if not environment:
            raise ValueError("Vector document missing environment")

        metadata.setdefault("doc_id", doc_id)
        metadata.setdefault("source_hash", source_hash)
        metadata.setdefault("environment", environment)
        if stage:
            metadata.setdefault("stage", stage)

        source_file = doc.get("source_file") or metadata.get("source_file")
        if source_file:
            metadata.setdefault("source_file", source_file)

        payload_body = dict(doc)
        payload_body.setdefault("doc_id", doc_id)
        payload_body["metadata"] = metadata
        payload = json.dumps(payload_body, ensure_ascii=False, default=_json_default_serializer)

        embedding_list = self._ensure_vector(doc.get("embedding"))
        embedding_blob = self._vector_to_blob(embedding_list) if embedding_list else None
        embedding_model = doc.get("embedding_model")
        vector_id = doc.get("vector_id") or chunk_id
        updated_at = self._coerce_datetime(doc.get("updated_at"))
        loaded_at = self._coerce_datetime(doc.get("loaded_at")) or updated_at or datetime.utcnow()

        return (
            source_hash,
            environment,
            chunk_id,
            stage,
            content,
            payload,
            source_file,
            embedding_blob,
            embedding_model,
            vector_id,
            updated_at,
            loaded_at,
        )

    def _chunk_ids_for_source(self, source_hash: str, environment: Optional[str] = None) -> List[str]:
        env = environment or self.env
        rows = self.session.execute(self.select_chunk_ids_stmt, (source_hash, env))
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
    def _fallback_chunk_id() -> str:
        return f"chunk_{int(time.time()*1000)}"
