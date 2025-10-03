from __future__ import annotations

import os
import time
from dataclasses import dataclass, field
import re
from typing import Any, Dict, List, Optional
from collections import defaultdict

from .ttrpg_logging import get_logger
from .ssl_bypass import configure_ssl_bypass_for_development, get_httpx_verify_setting

logger = get_logger(__name__)


@dataclass
class DictEntry:
    term: str
    definition: str
    category: str
    sources: List[Dict[str, Any]] = field(default_factory=list)
    job_id: Optional[str] = None
    source_hash: Optional[str] = None
    environment: Optional[str] = None
    source_file: Optional[str] = None
    source_page: Optional[int] = None
    document_id: Optional[str] = None
    confidence: Optional[float] = None

    def to_mongo_doc(self) -> Dict[str, Any]:
        """Convert to MongoDB document format (compatible with mongo_dictionary_service)."""
        normalized_term = self._normalize_component(self.term)
        doc = {
            'term': self.term,
            'term_original': self.term,
            'term_normalized': normalized_term,
            'definition': self.definition,
            'category': self.category,
            'sources': self.sources,
            'job_id': self.job_id,
            'source_hash': self.source_hash,
            'environment': self.environment,
            'source_file': self.source_file,
            'source_page': self.source_page,
            'document_id': self.document_id,
            'confidence': self.confidence,
            'created_at': time.time(),
            'updated_at': time.time(),
        }
        doc['_id'] = self._build_document_id(normalized_term, self.source_hash)
        return doc

    @staticmethod
    def _normalize_component(value: Optional[str]) -> str:
        if not value:
            return ''
        normalized = value.strip().lower()
        normalized = normalized.replace('	', ' ')
        normalized = re.sub(r"[^a-z0-9]+", "_", normalized)
        normalized = re.sub(r"_+", "_", normalized)
        return normalized.strip('_')

    @classmethod
    def _build_document_id(cls, normalized_term: str, source_hash: Optional[str]) -> str:
        if source_hash:
            normalized_hash = cls._normalize_component(source_hash)
            if normalized_hash:
                return f"{normalized_term}::{normalized_hash}"
        return normalized_term


class DictionaryLoader:
    def __init__(self, env: str = "dev"):
        self.env = env
        self.collection_name = f"ttrpg_dictionary_{env}"
        self._astra_insecure_configured = False

        # Backend selection: prefer Mongo for FR-006 when available
        self.backend = os.getenv("DICTIONARY_BACKEND", "mongo").strip().lower()
        self.client = None           # Astra client
        self.mongo_client = None     # pymongo.MongoClient
        self.mongo_collection = None # pymongo Collection

        if self.backend == "mongo":
            self._init_mongo()
        else:
            self._init_astra()

        self.last_verification_count: Optional[int] = None

    def _init_mongo(self) -> None:
        uri = os.getenv("MONGO_URI", "").strip()
        if not uri:
            logger.error("MONGO_URI not set; cannot initialize Mongo dictionary backend")
            return
        try:
            from pymongo import MongoClient  # type: ignore
            self.mongo_client = MongoClient(uri)
            db = self.mongo_client.get_database()
            self.mongo_collection = db[self.collection_name]
            logger.info(f"Mongo dictionary backend initialized: {db.name}.{self.collection_name}")
        except Exception as e:
            logger.error(f"Failed to initialize Mongo dictionary backend: {e}")
            self.mongo_client = None
            self.mongo_collection = None

    def _init_astra(self) -> None:
        try:
            from astrapy import DataAPIClient  # type: ignore
            from .ttrpg_secrets import validate_database_config

            cfg = validate_database_config()
            if not all([cfg.get('ASTRA_DB_API_ENDPOINT'), cfg.get('ASTRA_DB_APPLICATION_TOKEN'), cfg.get('ASTRA_DB_ID')]):
                logger.warning("Astra config incomplete for dictionary loader; running in simulation mode")
                self.client = None
                return
            # Attempt secure client first
            self._maybe_configure_astra_httpx_secure()
            client = DataAPIClient(cfg['ASTRA_DB_APPLICATION_TOKEN'])
            self.client = client.get_database_by_api_endpoint(cfg['ASTRA_DB_API_ENDPOINT'])
            logger.info("Astra dictionary backend initialized")
        except Exception as e:
            logger.warning(f"DictionaryLoader Astra init failed: {e}")
            self.client = None

    def upsert_entries(
        self,
        entries: List[DictEntry],
        *,
        job_id: Optional[str] = None,
        source_hash: Optional[str] = None,
        source_file: Optional[str] = None,
        environment: Optional[str] = None,
    ) -> tuple[int, List[Dict[str, Any]]]:
        if not entries:
            self.last_verification_count = None
            return 0, []

        environment = environment or self.env
        deduped_entries = self._deduplicate_entries(entries, source_hash)
        original_count = len(entries)
        deduped_count = len(deduped_entries)

        if original_count > deduped_count:
            logger.info(
                "Deduplicated %s entries to %s (%s duplicates removed)",
                original_count,
                deduped_count,
                original_count - deduped_count,
            )

        if self.backend == "mongo" and self.mongo_collection is not None:
            return self._upsert_entries_mongo(
                deduped_entries,
                job_id=job_id,
                source_hash=source_hash,
                source_file=source_file,
                environment=environment,
            )

        if self.client is None:
            logger.info(
                "SIMULATION: would upsert %s dictionary entries into %s",
                deduped_count,
                self.collection_name,
            )
            simulated_results = [
                {
                    "term": entry.term,
                    "category": entry.category,
                    "status": "inserted",
                    "error_message": None,
                }
                for entry in deduped_entries
            ]
            self.last_verification_count = None
            return deduped_count, simulated_results

        try:
            col = self.client.get_collection(self.collection_name)
            docs = []
            for entry in deduped_entries:
                context = self._derive_entry_context(
                    entry,
                    source_hash=source_hash,
                    source_file=source_file,
                    job_id=job_id,
                    environment=environment,
                )
                docs.append(
                    {
                        "_id": self._normalize_term_id(entry.term, context["source_hash"]),
                        "term": entry.term,
                        "definition": entry.definition,
                        "category": entry.category,
                        "sources": context["sources"],
                        "updated_at": time.time(),
                    }
                )

            batch_size = 20
            upserted = 0
            for index in range(0, len(docs), batch_size):
                batch = docs[index:index + batch_size]
                upserted += self._upsert_batch(col, batch)
                if index + batch_size < len(docs):
                    time.sleep(0.1)

            logger.info(
                "Dictionary upsert completed: %s/%s entries processed (Astra backend)",
                upserted,
                deduped_count,
            )
            astra_results = [
                {
                    "term": entry.term,
                    "category": entry.category,
                    "status": "inserted",
                    "error_message": None,
                }
                for entry in deduped_entries
            ]
            self.last_verification_count = None
            return upserted, astra_results
        except Exception as exc:
            logger.error("Astra dictionary upsert error: %s", exc)
            raise

    def _upsert_entries_mongo(
        self,
        entries: List[DictEntry],
        *,
        job_id: Optional[str],
        source_hash: Optional[str],
        source_file: Optional[str],
        environment: str,
    ) -> tuple[int, List[Dict[str, Any]]]:
        assert self.mongo_collection is not None

        upserted = 0
        term_results: List[Dict[str, Any]] = []
        verification_hash: Optional[str] = None
        verification_job = job_id

        for entry in entries:
            try:
                context = self._derive_entry_context(
                    entry,
                    source_hash=source_hash,
                    source_file=source_file,
                    job_id=job_id,
                    environment=environment,
                )
                verification_hash = context["source_hash"]
                verification_job = context["job_id"]
                doc_id = self._normalize_term_id(entry.term, context["source_hash"])
                now = time.time()

                update_filter = {"_id": doc_id}
                update_body = {
                    "$setOnInsert": {
                        "created_at": now,
                        "sources": [],
                    },
                    "$set": {
                        "term": entry.term,
                        "term_original": entry.term,
                        "term_normalized": DictEntry._normalize_component(entry.term),
                        "definition": entry.definition,
                        "category": entry.category,
                        "job_id": context["job_id"],
                        "source_hash": context["source_hash"],
                        "source_file": context["source_file"],
                        "environment": context["environment"],
                        "updated_at": now,
                    },
                }
                result = self.mongo_collection.update_one(update_filter, update_body, upsert=True)

                if context["sources"]:
                    self.mongo_collection.update_one(
                        update_filter,
                        {"$addToSet": {"sources": {"$each": context["sources"]}}},
                    )

                upserted += 1
                status = "inserted" if result.upserted_id else ("updated" if result.modified_count > 0 else "unchanged")
                term_results.append(
                    {
                        "term": entry.term,
                        "category": entry.category,
                        "status": status,
                        "error_message": None,
                    }
                )
            except Exception as exc:
                term_results.append(
                    {
                        "term": entry.term,
                        "category": entry.category,
                        "status": "failed",
                        "error_message": str(exc),
                    }
                )
                logger.error(
                    "Mongo dictionary upsert error for term %s: %s",
                    entry.term,
                    exc,
                )
                raise

        verification_count = None
        if verification_hash:
            verification_count = self._verify_mongo_entries(
                verification_job,
                verification_hash,
                environment,
            )
            logger.info(
                "pass_a.mongo.terms_written",
                extra={
                    "job_id": verification_job,
                    "source_hash": verification_hash,
                    "environment": environment,
                    "rows_written": upserted,
                    "verified_count": verification_count,
                },
            )
        self.last_verification_count = verification_count
        return upserted, term_results

    def _derive_entry_context(
        self,
        entry: DictEntry,
        *,
        source_hash: Optional[str],
        source_file: Optional[str],
        job_id: Optional[str],
        environment: str,
    ) -> Dict[str, Any]:
        context_hash = entry.source_hash or source_hash
        if not context_hash:
            for source in entry.sources:
                candidate = source.get("source_hash")
                if candidate:
                    context_hash = str(candidate)
                    break
        if not context_hash:
            raise ValueError(f"Dictionary entry '{entry.term}' is missing source_hash metadata")

        context_file = entry.source_file or source_file
        if not context_file:
            for source in entry.sources:
                candidate = source.get("source_file") or source.get("system")
                if candidate:
                    context_file = str(candidate)
                    break
        context_job = entry.job_id or job_id

        enriched_sources: List[Dict[str, Any]] = []
        for source in entry.sources or []:
            enriched = dict(source)
            enriched.setdefault("source_hash", context_hash)
            enriched.setdefault("environment", environment)
            if context_job:
                enriched.setdefault("job_id", context_job)
            enriched_sources.append(enriched)
        if not enriched_sources:
            enriched_sources.append(
                {
                    "source_hash": context_hash,
                    "environment": environment,
                    "job_id": context_job,
                }
            )

        entry.source_hash = context_hash
        entry.source_file = context_file
        entry.job_id = context_job
        entry.environment = environment
        entry.sources = enriched_sources

        return {
            "source_hash": context_hash,
            "source_file": context_file,
            "job_id": context_job,
            "environment": environment,
            "sources": enriched_sources,
        }

    def _verify_mongo_entries(self, job_id: Optional[str], source_hash: str, environment: str) -> int:
        if self.mongo_collection is None:
            return 0

        query: Dict[str, Any] = {
            "source_hash": source_hash,
            "environment": environment,
        }
        if job_id:
            query["job_id"] = job_id

        count = self.mongo_collection.count_documents(query)
        if count <= 0:
            raise RuntimeError(
                f"Mongo dictionary verification failed for source {source_hash} (job {job_id})"
            )
        return count    def _deduplicate_entries(self, entries: List[DictEntry], source_hash: Optional[str] = None) -> List[DictEntry]:
        """Deduplicate entries by normalized term (and source), keeping the last occurrence."""
        term_map: Dict[str, DictEntry] = {}

        for entry in entries:
            normalized_term = self._normalize_term_id(entry.term, entry.source_hash or source_hash)
            term_map[normalized_term] = entry

        return list(term_map.values())

    def _normalize_term_id(self, term: str, source_hash: Optional[str] = None) -> str:
        normalized_term = DictEntry._normalize_component(term)
        if source_hash:
            normalized_hash = DictEntry._normalize_component(source_hash)
            if normalized_hash:
                return f"{normalized_term}::{normalized_hash}"
        return normalized_term

    
    def _upsert_batch(self, collection, batch_docs: List[Dict[str, Any]]) -> int:
        """Upsert a batch of documents using two-step pattern for AstraDB compatibility (BUG-013 fix)."""
        upserted = 0

        for doc in batch_docs:
            try:
                # Step 1: Ensure document exists with base fields
                collection.update_one(
                    {"_id": doc["_id"]}, 
                    {
                        "$setOnInsert": {
                            "_id": doc["_id"],
                            "created_at": doc["updated_at"],
                            "sources": []
                        },
                        "$set": {
                            "term": doc["term"],
                            "definition": doc["definition"],
                            "category": doc["category"],
                            "updated_at": doc["updated_at"]
                        }
                    },
                    upsert=True
                )
                
                # Step 2: Add sources using separate operation
                if doc["sources"]:
                    collection.update_one(
                        {"_id": doc["_id"]},
                        {
                            "$addToSet": {
                                "sources": {"$each": doc["sources"]}
                            }
                        }
                    )
                
                upserted += 1
                
                # Log audit trail for dictionary changes
                logger.debug(f"Dictionary term upserted: {doc['term']} with {len(doc['sources'])} sources")
                
            except Exception as e:
                msg = str(e)
                # TLS fallback: if certificate verification fails, reconfigure astrapy client to no-TLS verify and retry once
                if any(tok in msg for tok in ["CERTIFICATE_VERIFY_FAILED", "certificate verify failed", "SSLError"]) and not self._astra_insecure_configured:
                    try:
                        self._configure_astra_httpx_insecure()
                        # retry once after switching to insecure client
                        try:
                            collection.update_one(
                                {"_id": doc["_id"]}, 
                                {
                                    "$setOnInsert": {
                                        "_id": doc["_id"],
                                        "created_at": doc["updated_at"],
                                        "sources": []
                                    },
                                    "$set": {
                                        "term": doc["term"],
                                        "definition": doc["definition"],
                                        "category": doc["category"],
                                        "updated_at": doc["updated_at"]
                                    }
                                },
                                upsert=True
                            )
                            if doc["sources"]:
                                collection.update_one(
                                    {"_id": doc["_id"]},
                                    {"$addToSet": {"sources": {"$each": doc["sources"]}}}
                                )
                            upserted += 1
                            logger.warning("Retried dictionary upsert without TLS verification: success")
                            continue
                        except Exception as e2:
                            logger.warning(f"Retry after disabling TLS verification failed for {doc['_id']}: {e2}")
                    except Exception as cfg_e:
                        logger.warning(f"Failed to reconfigure Astra client for no-TLS verify: {cfg_e}")
                # Final failure path
                logger.warning(f"Dictionary upsert failed for {doc['_id']}: {e}")

        return upserted

    def _maybe_configure_astra_httpx_secure(self) -> None:
        """Ensure astrapy uses an httpx client with default verification unless dev bypass is active."""
        try:
            # Honor global dev SSL bypass, but default to verify=True
            ssl_bypass_active = configure_ssl_bypass_for_development()
            import httpx  # type: ignore
            from astrapy.utils import api_commander as _ac  # type: ignore
            verify_setting = get_httpx_verify_setting() if ssl_bypass_active else True
            _ac.APICommander.client = httpx.Client(verify=verify_setting)
            self._astra_insecure_configured = not verify_setting
            if not verify_setting:
                logger.warning("DictionaryLoader: SSL verification bypass enabled for Astra (development only)")
        except Exception as e:
            # Non-fatal; will proceed with astrapy defaults
            logger.debug(f"DictionaryLoader: could not configure Astra httpx client: {e}")

    def _configure_astra_httpx_insecure(self) -> None:
        """Force astrapy httpx client to verify=False (dev fallback)."""
        import httpx  # type: ignore
        from astrapy.utils import api_commander as _ac  # type: ignore
        _ac.APICommander.client = httpx.Client(verify=False)
        self._astra_insecure_configured = True
        logger.warning("DictionaryLoader: switched Astra client to no TLS verification due to certificate errors")

    def get_term_count(self) -> int:
        """Get total count of dictionary terms."""
        try:
            if self.backend == "mongo" and self.mongo_collection is not None:
                return self.mongo_collection.estimated_document_count()
            if self.client is not None:
                collection = self.client.get_collection(self.collection_name)
                return collection.estimated_document_count()
            return 0
        except Exception as e:
            logger.warning(f"Failed to get term count: {e}")
            return 0
    
    def get_term_details(self, term: str) -> Optional[Dict[str, Any]]:
        """Get detailed information about a specific term."""
        normalized_id = self._normalize_term_id(term)
        try:
            if self.backend == "mongo" and self.mongo_collection is not None:
                return self.mongo_collection.find_one({"_id": normalized_id})
            if self.client is not None:
                collection = self.client.get_collection(self.collection_name)
                return collection.find_one({"_id": normalized_id})
            return None
        except Exception as e:
            logger.warning(f"Failed to get term details for {term}: {e}")
            return None

