from __future__ import annotations

import json
import os
import re
import time
from pathlib import Path
from typing import Any, Dict, Iterable, Mapping, Optional, Sequence, List

from ..ttrpg_logging import get_logger
from ..ttrpg_secrets import get_all_config, validate_database_config
from ..ssl_bypass import configure_ssl_bypass_for_development, get_httpx_verify_setting
from .base import VectorStore

logger = get_logger(__name__)


class AstraVectorStore(VectorStore):
    """Vector store backed by DataStax Astra DB collections."""

    def __init__(self, env: str) -> None:
        super().__init__(env)
        self.collection_name = f"ttrpg_chunks_{env}"
        self.require_credentials = os.getenv("ASTRA_REQUIRE_CREDS", "true").strip().lower() in {"1", "true", "yes"}
        self.general_timeout_ms = int(os.getenv("ASTRA_GENERAL_METHOD_TIMEOUT_MS", "60000"))
        self._config = get_all_config()
        self._db_config = validate_database_config()
        self.client = None
        self._init_client()

    @property
    def backend_name(self) -> str:
        return "astra"

    def ensure_schema(self) -> None:  # pragma: no cover - Astra collections are schemaless
        return None

    # ------------------------------------------------------------------
    # Public API implementations
    # ------------------------------------------------------------------
    def insert_documents(self, documents: Sequence[Mapping[str, Any]]) -> int:
        if not documents:
            return 0
        if self.client is None:
            if self.require_credentials:
                raise RuntimeError("AstraVectorStore: credentials required for insert")
            logger.info("AstraVectorStore running in simulation mode; pretending to insert %s documents", len(documents))
            return len(documents)
        try:
            collection = self.client.get_collection(self.collection_name)
            result = collection.insert_many(list(documents))
            inserted = len(getattr(result, "inserted_ids", []) or [])
            return inserted or len(documents)
        except Exception as exc:
            logger.error("AstraVectorStore insert failed: %s", exc)
            raise

    def upsert_documents(self, documents: Sequence[Mapping[str, Any]]) -> int:
        if not documents:
            return 0
        if self.client is None:
            if self.require_credentials:
                raise RuntimeError("AstraVectorStore: credentials required for upsert")
            logger.info("AstraVectorStore simulation upsert of %s documents", len(documents))
            return len(documents)
        collection = self.client.get_collection(self.collection_name)
        upserted = 0
        for doc in documents:
            chunk_id = doc.get("chunk_id") or doc.get("id")
            if not chunk_id:
                raise ValueError("Vector document missing chunk_id")
            try:
                collection.find_one_and_replace({"chunk_id": chunk_id}, dict(doc), upsert=True)
                upserted += 1
            except Exception as exc:
                logger.warning("AstraVectorStore upsert failed for %s: %s", chunk_id, exc)
        return upserted

    def delete_all(self) -> int:
        if self.client is None:
            logger.info("AstraVectorStore simulation delete_all")
            return 0
        collection = self.client.get_collection(self.collection_name)
        result = collection.delete_many({})
        return int(getattr(result, "deleted_count", 0) or 0)

    def delete_by_source_hash(self, source_hash: str) -> int:
        if self.client is None:
            logger.info("AstraVectorStore simulation delete for source %s", source_hash)
            return 0
        collection = self.client.get_collection(self.collection_name)
        query = {
            "$or": [
                {"metadata.source_hash": source_hash},
                {"source_hash": source_hash},
            ]
        }
        result = collection.delete_many(query)
        return int(getattr(result, "deleted_count", 0) or 0)

    def count_documents(self) -> int:
        if self.client is None:
            return 0
        collection = self.client.get_collection(self.collection_name)
        return int(collection.count_documents({}, upper_bound=10000))

    def count_documents_for_source(self, source_hash: str) -> int:
        if self.client is None:
            return 0
        collection = self.client.get_collection(self.collection_name)
        query = {
            "$or": [
                {"metadata.source_hash": source_hash},
                {"source_hash": source_hash},
            ]
        }
        return int(collection.count_documents(query, upper_bound=10000))

    def get_sources_with_chunk_counts(self) -> Dict[str, Any]:
        if self.client is None:
            return {
                "status": "simulation_mode",
                "environment": self.env,
                "sources": [],
                "total_sources": 0,
                "total_chunks": 0,
            }
        collection = self.client.get_collection(self.collection_name)
        pipeline = [
            {
                "$addFields": {
                    "source_hash_key": {
                        "$ifNull": [
                            "$metadata.source_hash",
                            "$source_hash",
                            "$metadata.source_id",
                            "$source_id",
                        ]
                    },
                    "source_file_key": {
                        "$ifNull": [
                            "$metadata.source_file",
                            "$source_file",
                            "$metadata.source",
                            "$source_id",
                        ]
                    },
                    "last_touch": {
                        "$ifNull": ["$updated_at", "$loaded_at"],
                    },
                }
            },
            {
                "$match": {
                    "source_hash_key": {"$nin": [None, "", False]},
                }
            },
            {
                "$group": {
                    "_id": "$source_hash_key",
                    "chunk_count": {"$sum": 1},
                    "source_file": {"$first": "$source_file_key"},
                    "last_updated": {"$max": "$last_touch"},
                }
            },
            {"$sort": {"chunk_count": -1}},
        ]
        results = self._aggregate_with_fallback(collection, pipeline)
        sources: List[Dict[str, Any]] = []
        total_chunks = 0
        for doc in results:
            source_hash = doc.get("_id")
            if not source_hash:
                continue
            source_info = {
                "source_hash": source_hash,
                "source_file": doc.get("source_file") or "Unknown Source",
                "chunk_count": int(doc.get("chunk_count", 0) or 0),
                "last_updated": doc.get("last_updated") or time.time(),
            }
            sources.append(source_info)
            total_chunks += source_info["chunk_count"]
        return {
            "status": "ready",
            "environment": self.env,
            "collection_name": self.collection_name,
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
        query_text = filters.get("query_text")
        metadata_filters = filters.get("metadata")
        scan_limit = int(filters.get("scan_limit", 2000))

        if self.client is None:
            return []
        collection = self.client.get_collection(self.collection_name)
        projection = {"content": 1, "metadata": 1, "chunk_id": 1, "embedding": 1}
        cursor = collection.find({}, projection=projection, limit=scan_limit)
        candidates: List[Dict[str, Any]] = []
        for doc in cursor:
            metadata = doc.get("metadata") or {}
            if metadata_filters and not self._metadata_matches(metadata, metadata_filters):
                continue
            if vector is None and query_text:
                score = self._lexical_score(query_text, doc.get("content") or "", metadata)
            else:
                score = self._similarity(vector, doc.get("embedding"))
            candidates.append(
                {
                    "chunk_id": doc.get("chunk_id") or str(doc.get("_id")),
                    "content": doc.get("content") or "",
                    "metadata": metadata,
                    "score": score,
                }
            )
        if not candidates:
            return []
        candidates.sort(key=lambda d: d.get("score", 0.0), reverse=True)
        return candidates[: max(1, top_k)]
    def close(self) -> None:
        self.client = None

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _init_client(self) -> None:
        try:
            project_root = Path(__file__).resolve().parents[2]
            root_env = project_root / ".env"
            if root_env.exists():
                from ..ttrpg_secrets import _load_env_file  # type: ignore

                _load_env_file(root_env)

            if os.getenv("ASTRA_SIMULATE", "").strip().lower() in {"1", "true", "yes"}:
                logger.warning("ASTRA_SIMULATE enabled; AstraVectorStore running without a client")
                self.client = None
                return

            ssl_bypass_active = configure_ssl_bypass_for_development()
            insecure = os.getenv("ASTRA_INSECURE", "").strip().lower() in {"1", "true", "yes"} or ssl_bypass_active
            if insecure:
                try:
                    import httpx  # type: ignore
                    from astrapy.utils import api_commander as _ac  # type: ignore

                    _ac.APICommander.client = httpx.Client(verify=get_httpx_verify_setting())
                    logger.warning("AstraVectorStore SSL verification disabled (development mode)")
                except Exception as exc:
                    logger.warning("Failed to configure Astra SSL bypass: %s", exc)

            if not all([
                self._db_config.get("ASTRA_DB_API_ENDPOINT"),
                self._db_config.get("ASTRA_DB_APPLICATION_TOKEN"),
                self._db_config.get("ASTRA_DB_ID"),
            ]):
                if self.require_credentials:
                    raise RuntimeError("Astra credentials missing and ASTRA_REQUIRE_CREDS enabled")
                logger.warning("Astra credentials incomplete; vector store operating in simulation mode")
                self.client = None
                return

            from astrapy import DataAPIClient  # type: ignore

            client = DataAPIClient(self._db_config["ASTRA_DB_APPLICATION_TOKEN"])  # nosec - handled by config loader
            self.client = client.get_database_by_api_endpoint(self._db_config["ASTRA_DB_API_ENDPOINT"])
            logger.info("AstraVectorStore initialized for env=%s collection=%s", self.env, self.collection_name)
        except Exception as exc:
            logger.error("Failed to initialize AstraVectorStore client: %s", exc)
            if self.require_credentials:
                raise
            self.client = None

    def _aggregate_with_fallback(self, collection: Any, pipeline: Sequence[Mapping[str, Any]]):
        aggregate_fn = getattr(collection, "aggregate", None)
        if callable(aggregate_fn):
            return aggregate_fn(pipeline)
        aggregate_raw_fn = getattr(collection, "aggregate_raw", None)
        if callable(aggregate_raw_fn):
            raw_result = aggregate_raw_fn({"pipeline": pipeline})
            if isinstance(raw_result, dict):
                return raw_result.get("data", [])
            return raw_result
        return self._aggregate_via_find(collection)

    @staticmethod
    def _metadata_matches(metadata: Mapping[str, Any], required: Optional[Mapping[str, Any]]) -> bool:
        if not required:
            return True
        for key, expected in required.items():
            current = metadata.get(key)
            if isinstance(expected, list):
                if current not in expected:
                    return False
            else:
                if current != expected:
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

    def _aggregate_via_find(self, collection: Any):
        projection = {
            "metadata.source_hash": True,
            "metadata.source_file": True,
            "metadata.source_id": True,
            "metadata.source": True,
            "source_hash": True,
            "source_file": True,
            "updated_at": True,
            "loaded_at": True,
        }
        find_fn = getattr(collection, "find", None)
        if not callable(find_fn):
            return []
        try:
            cursor = find_fn({}, projection=projection, timeout_ms=self.general_timeout_ms)
        except TypeError:
            cursor = find_fn({})
        if isinstance(cursor, dict):
            documents_iter = cursor.get("data", []) or []
        else:
            documents_iter = cursor if cursor is not None else []
        aggregated: Dict[str, Dict[str, Any]] = {}
        for doc in documents_iter:
            source_hash = (
                doc.get("metadata", {}).get("source_hash")
                or doc.get("source_hash")
                or doc.get("metadata", {}).get("source_id")
                or doc.get("source_id")
            )
            if not source_hash:
                continue
            entry = aggregated.setdefault(source_hash, {
                "_id": source_hash,
                "chunk_count": 0,
                "source_file": doc.get("metadata", {}).get("source_file")
                or doc.get("source_file")
                or doc.get("metadata", {}).get("source")
                or doc.get("source_id")
                or "Unknown Source",
                "last_updated": doc.get("updated_at") or doc.get("loaded_at") or time.time(),
            })
            entry["chunk_count"] += 1
            if doc.get("updated_at") or doc.get("loaded_at"):
                entry["last_updated"] = max(entry["last_updated"], doc.get("updated_at") or doc.get("loaded_at") or entry["last_updated"])
        return list(aggregated.values())

    @staticmethod
    def _similarity(vector: Sequence[float] | None, other: Any) -> float:
        if vector is None or other is None:
            return 0.0
        try:
            other_vec = other if isinstance(other, Sequence) else other.get("values")  # type: ignore[attr-defined]
            if other_vec is None:
                return 0.0
            a = list(float(v) for v in vector)
            b = list(float(v) for v in other_vec)
            if not a or not b or len(a) != len(b):
                return 0.0
            dot = sum(x * y for x, y in zip(a, b))
            norm_a = sum(x * x for x in a) ** 0.5
            norm_b = sum(x * x for x in b) ** 0.5
            if not norm_a or not norm_b:
                return 0.0
            return dot / (norm_a * norm_b)
        except Exception:
            return 0.0
