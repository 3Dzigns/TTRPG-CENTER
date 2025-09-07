#!/usr/bin/env python3
"""
Backfill dictionary and enrich categories from existing Astra chunks.

Usage:
  python scripts/dictionary_backfill.py --env dev --limit 5000

Effect:
  - Scans ttrpg_chunks_{ENV}
  - For each document, derives categories using Pass B heuristics and writes them into metadata.categories (non-destructive)
  - Extracts dictionary updates (including Feats) and upserts them into ttrpg_dictionary_{ENV}
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Any, Dict, List

from astrapy import DataAPIClient  # type: ignore

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src_common.pass_b_enricher import PassBEnricher, EnrichedChunk
from src_common.dictionary_loader import DictionaryLoader, DictEntry
from src_common.secrets import validate_database_config
from src_common.ttrpg_secrets import _load_env_file
from src_common.logging import get_logger, setup_logging


def main(argv: List[str]) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--env", default=os.getenv("APP_ENV", "dev"))
    ap.add_argument("--limit", type=int, default=5000)
    args = ap.parse_args(argv)

    setup_logging()
    logger = get_logger("dict_backfill")
    os.environ["APP_ENV"] = args.env

    # Load .env to ensure ASTRA_* present
    root_env = Path(__file__).resolve().parents[1] / ".env"
    if root_env.exists():
        _load_env_file(root_env)
    cfg = validate_database_config()
    client = DataAPIClient(cfg['ASTRA_DB_APPLICATION_TOKEN'])
    db = client.get_database_by_api_endpoint(cfg['ASTRA_DB_API_ENDPOINT'])
    col_name = f"ttrpg_chunks_{args.env}"
    col = db.get_collection(col_name)

    enricher = PassBEnricher("backfill_job")
    dict_loader = DictionaryLoader(args.env)

    # Pull documents in batches
    processed = 0
    upserted = 0
    updated = 0
    cursor = col.find({}, projection={"_id": 1, "chunk_id": 1, "content": 1, "metadata": 1}, limit=args.limit)
    for d in cursor:
        cid = d.get("chunk_id") or str(d.get("_id"))
        content = d.get("content") or ""
        meta = d.get("metadata") or {}

        # Derive categories and update chunk
        cats = enricher._categorize_content(content)
        # include feats if section says feats
        section = (meta.get("section") or "").lower()
        if "feat" in section and "feats" not in cats:
            cats.append("feats")
        try:
            col.update_one({"_id": d["_id"]}, {"$set": {"metadata.categories": cats}})
            updated += 1
        except Exception as e:
            logger.warning(f"Chunk update failed for {cid}: {e}")

        # Build minimal EnrichedChunk to pass to extractor
        e = EnrichedChunk(
            chunk_id=cid,
            original_content=content,
            enhanced_content=content,
            entities=enricher._extract_entities(content),
            categories=cats,
            complexity=enricher._assess_complexity(content, []),
            confidence=0.8,
        )
        updates = enricher._extract_dictionary_updates(e)
        if updates:
            entries = [DictEntry(u.term, u.definition, u.category, [{"chunk_id": cid, "section": meta.get("section"), "page": meta.get("page")}]) for u in updates]
            upserted += dict_loader.upsert_entries(entries)

        processed += 1
        if processed % 200 == 0:
            logger.info(f"Processed {processed} docs, updated {updated}, dict upserts {upserted}")

    logger.info(f"Backfill complete. Processed {processed}, updated {updated}, dict upserts {upserted}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
