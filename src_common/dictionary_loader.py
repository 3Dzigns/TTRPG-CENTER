from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional
from collections import defaultdict

from .logging import get_logger

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
        self.client = None
        try:
            from astrapy import DataAPIClient  # type: ignore
            from .ttrpg_secrets import get_all_config, validate_database_config

            cfg = validate_database_config()
            if not all([cfg.get('ASTRA_DB_API_ENDPOINT'), cfg.get('ASTRA_DB_APPLICATION_TOKEN'), cfg.get('ASTRA_DB_ID')]):
                logger.warning("Astra config incomplete for dictionary loader; running in simulation mode")
                self.client = None
            else:
                client = DataAPIClient(cfg['ASTRA_DB_APPLICATION_TOKEN'])
                self.client = client.get_database_by_api_endpoint(cfg['ASTRA_DB_API_ENDPOINT'])
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
        """Normalize a term to create a consistent document ID."""
        return term.strip().lower().replace(' ', '_').replace('-', '_').replace("'", "")
    
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
                logger.warning(f"Dictionary upsert failed for {doc['_id']}: {e}")
        
        return upserted

    def get_term_count(self) -> int:
        """Get total count of dictionary terms."""
        if self.client is None:
            return 0
            
        try:
            collection = self.client.get_collection(self.collection_name)
            return collection.estimated_document_count()
        except Exception as e:
            logger.warning(f"Failed to get term count: {e}")
            return 0
    
    def get_term_details(self, term: str) -> Optional[Dict[str, Any]]:
        """Get detailed information about a specific term."""
        if self.client is None:
            return None
            
        try:
            collection = self.client.get_collection(self.collection_name)
            normalized_id = self._normalize_term_id(term)
            doc = collection.find_one({"_id": normalized_id})
            return doc
        except Exception as e:
            logger.warning(f"Failed to get term details for {term}: {e}")
            return None
