from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

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
            from .secrets import get_all_config, validate_database_config

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
        if self.client is None:
            logger.info(f"SIMULATION: would upsert {len(entries)} dictionary entries into {self.collection_name}")
            return len(entries)
        try:
            col = self.client.get_collection(self.collection_name)
            docs = []
            for e in entries:
                doc_id = e.term.strip().lower().replace(' ', '_')
                docs.append({
                    "_id": doc_id,
                    "term": e.term,
                    "definition": e.definition,
                    "category": e.category,
                    "sources": e.sources,
                    "updated_at": time.time(),
                })
            # Upsert via insert_many with ordered=False; duplicates overwrite via replace
            # Data API lacks upsert-many; do individual upserts
            upserted = 0
            for d in docs:
                try:
                    col.find_one_and_replace({"_id": d["_id"]}, d, upsert=True)
                    upserted += 1
                except Exception as e:
                    logger.warning(f"Dictionary upsert failed for {d['_id']}: {e}")
            return upserted
        except Exception as e:
            logger.error(f"Dictionary upsert error: {e}")
            return 0

