from __future__ import annotations

import os
import time
from dataclasses import dataclass
import re
from typing import Any, Dict, List, Optional
from collections import defaultdict

from .logging import get_logger
from .ssl_bypass import configure_ssl_bypass_for_development, get_httpx_verify_setting

logger = get_logger(__name__)


@dataclass
class DictEntry:
    term: str
    definition: str
    category: str
    sources: List[Dict[str, Any]]


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

    def upsert_entries(self, entries: List[DictEntry]) -> int:
        if not entries:
            return 0
            
        # Deduplicate entries by term (keep last occurrence)
        deduped_entries = self._deduplicate_entries(entries)
        original_count = len(entries)
        deduped_count = len(deduped_entries)
        
        if original_count > deduped_count:
            logger.info(f"Deduplicated {original_count} entries to {deduped_count} ({original_count - deduped_count} duplicates removed)")
        
        if self.backend == "mongo" and self.mongo_collection is not None:
            try:
                upserted = 0
                for e in deduped_entries:
                    _id = self._normalize_term_id(e.term)
                    now = time.time()
                    self.mongo_collection.update_one(
                        {"_id": _id},
                        {
                            "$setOnInsert": {"created_at": now, "sources": []},
                            "$set": {
                                "term": e.term,
                                "definition": e.definition,
                                "category": e.category,
                                "updated_at": now,
                            },
                        },
                        upsert=True,
                    )
                    if e.sources:
                        self.mongo_collection.update_one(
                            {"_id": _id}, {"$addToSet": {"sources": {"$each": e.sources}}}
                        )
                    upserted += 1
                logger.info(f"Mongo dictionary upsert completed: {upserted}/{deduped_count}")
                return upserted
            except Exception as e:
                logger.error(f"Mongo dictionary upsert error: {e}")
                return 0

        if self.client is None:
            logger.info(f"SIMULATION: would upsert {deduped_count} dictionary entries into {self.collection_name}")
            return deduped_count
            
        try:
            col = self.client.get_collection(self.collection_name)
            
            # Convert to documents with normalized IDs
            docs = []
            for e in deduped_entries:
                doc_id = self._normalize_term_id(e.term)
                docs.append({
                    "_id": doc_id,
                    "term": e.term,
                    "definition": e.definition,
                    "category": e.category,
                    "sources": e.sources,
                    "updated_at": time.time(),
                })
            
            # Process in batches to reduce individual API calls
            batch_size = 20  # Reasonable batch size for individual upserts
            upserted = 0
            
            for i in range(0, len(docs), batch_size):
                batch = docs[i:i + batch_size]
                batch_upserted = self._upsert_batch(col, batch)
                upserted += batch_upserted
                
                # Small delay between batches to avoid rate limiting
                if i + batch_size < len(docs):
                    time.sleep(0.1)
            
            logger.info(f"Dictionary upsert completed: {upserted}/{deduped_count} entries processed")
            return upserted
            
        except Exception as e:
            logger.error(f"Dictionary upsert error: {e}")
            return 0
    
    def _deduplicate_entries(self, entries: List[DictEntry]) -> List[DictEntry]:
        """Deduplicate entries by normalized term, keeping the last occurrence."""
        term_map = {}
        
        for entry in entries:
            normalized_term = self._normalize_term_id(entry.term)
            term_map[normalized_term] = entry
        
        return list(term_map.values())
    
    def _normalize_term_id(self, term: str) -> str:
        """Normalize a term to create a consistent, stable document ID.

        Rules:
        - Lowercase
        - Replace any non-alphanumeric character with underscore
        - Collapse repeated underscores
        - Trim leading/trailing underscores
        """
        t = term.strip().lower()
        # Normalize whitespace and punctuation
        t = t.replace('\t', ' ')
        t = re.sub(r"[^a-z0-9]+", "_", t)
        t = re.sub(r"_+", "_", t)
        t = t.strip('_')
        return t
    
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
