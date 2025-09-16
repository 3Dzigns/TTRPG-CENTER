from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List

from ..ttrpg_logging import get_logger

logger = get_logger(__name__)


@dataclass
class DocChunk:
    id: str
    text: str
    source: str
    score: float
    metadata: Dict[str, Any]


def _tokenize(s: str) -> List[str]:
    return re.findall(r"\w+", (s or "").lower())


def _simple_score(query: str, text: str) -> float:
    q = set(_tokenize(query))
    t = set(_tokenize(text))
    if not q or not t:
        return 0.0
    return len(q & t) / max(1, len(q))


def _keyword_boost_score(query: str, text: str, metadata: Dict[str, Any]) -> float:
    base = _simple_score(query, text)
    ql = (query or "").lower()
    tx = (text or "").lower()
    boost = 0.0
    # Phrase boosts
    if "spells per day" in ql and "spells per day" in tx:
        boost += 2.0
    if "dodge" in ql and "dodge" in tx:
        boost += 1.5
    if "paladin" in ql and "paladin" in tx:
        boost += 1.0
    # Table preference if present
    mtype = metadata.get("chunk_type") or metadata.get("type")
    if mtype and str(mtype).lower() in {"table", "list", "table_row"}:
        boost += 0.5
    return base + boost


def _iter_candidate_chunks(env: str) -> List[DocChunk]:
    """
    Yield candidate chunks from env artifacts; fallback to bundled test artifacts.
    """
    roots = [Path(f"artifacts/ingest/{env}"), Path(f"artifacts/{env}")]
    # Only allow fallback test artifacts in test environment to preserve isolation contract
    if env == "test":
        roots.append(Path("src_common/artifacts/test"))
    for root in roots:
        if not root.exists():
            continue
        for path in sorted(root.rglob("*.json")):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                continue
            # detect pass A or pass B schema
            if isinstance(data, dict) and "chunks" in data and isinstance(data["chunks"], list):
                for ch in data["chunks"]:
                    text = ch.get("content") or ch.get("text") or ""
                    cid = ch.get("id") or ch.get("chunk_id") or str(path)
                    meta = ch.get("metadata") or {}
                    yield DocChunk(id=cid, text=text, source=str(path), score=0.0, metadata=meta)
            elif isinstance(data, dict) and "enriched_chunks" in data:
                for ch in data["enriched_chunks"]:
                    text = ch.get("enhanced_content") or ch.get("original_content") or ""
                    cid = ch.get("chunk_id") or str(path)
                    meta = {
                        "entities": ch.get("entities", []),
                        "categories": ch.get("categories", []),
                        "complexity": ch.get("complexity", "unknown"),
                    }
                    yield DocChunk(id=cid, text=text, source=str(path), score=0.0, metadata=meta)


def _astra_config() -> Dict[str, str]:
    return {
        "endpoint": os.getenv("ASTRA_DB_API_ENDPOINT", ""),
        "token": os.getenv("ASTRA_DB_APPLICATION_TOKEN", ""),
        "db_id": os.getenv("ASTRA_DB_ID", ""),
        "keyspace": os.getenv("ASTRA_DB_KEYSPACE", ""),
    }


def _retrieve_from_astra(query: str, env: str, top_k: int = 5) -> List[DocChunk]:
    cfg = _astra_config()
    if not (cfg["endpoint"] and cfg["token"]):
        return []
    try:
        from astrapy import DataAPIClient  # type: ignore

        client = DataAPIClient(cfg["token"])  # nosec
        db = client.get_database_by_api_endpoint(cfg["endpoint"])  # endpoint includes DB
        collection_name = f"ttrpg_chunks_{env}"
        col = db.get_collection(collection_name)

        # Page through a reasonable subset and score client-side (regex unsupported in JSON API)
        projection = {"content": 1, "metadata": 1, "chunk_id": 1}
        cursor = col.find({}, projection=projection, limit=2000)

        candidates: List[DocChunk] = []
        scanned = 0
        max_docs = 2000  # safety cap
        for d in cursor:
            text = (d.get("content") or "")
            cid = d.get("chunk_id") or str(d.get("_id"))
            meta = d.get("metadata") or {}
            score = _keyword_boost_score(query, text, meta)
            if score > 0:
                src = f"astra:{collection_name}:{cid}"
                candidates.append(DocChunk(id=str(cid), text=text, source=src, score=score, metadata=meta))
            scanned += 1
            if scanned >= max_docs:
                break

        if not candidates:
            return []
        candidates.sort(key=lambda c: c.score, reverse=True)
        # Deduplicate by signature
        seen = set()
        results: List[DocChunk] = []
        for c in candidates:
            sig = " ".join(_tokenize(c.text))[:200]
            if sig in seen:
                continue
            seen.add(sig)
            results.append(c)
            if len(results) >= max(1, top_k):
                break
        return results
    except Exception as e:
        logger.warning(f"Astra retrieval unavailable, falling back: {e}")
        return []


def retrieve(plan: Dict[str, Any], query: str, env: str, limit: int = 3) -> List[DocChunk]:
    """
    Hybrid retriever facade. For now, performs lightweight lexical scoring over local artifacts
    to satisfy Phase 2 contract without external services. If AstraDB is configured and reachable,
    prefers AstraDB as the source of truth.
    """
    top_k = int(plan.get("vector_top_k", 5))

    # Prefer AstraDB when available
    astra_results = _retrieve_from_astra(query, env, top_k)
    if astra_results:
        # Deduplicate similar content
        seen = set()
        results: List[DocChunk] = []
        for ch in astra_results:
            sig = " ".join(_tokenize(ch.text))[:200]
            if sig in seen:
                continue
            seen.add(sig)
            results.append(ch)
            if len(results) >= max(1, limit):
                break
        if results:
            return results

    candidates = list(_iter_candidate_chunks(env))
    for i, ch in enumerate(candidates):
        candidates[i] = DocChunk(
            id=ch.id,
            text=ch.text,
            source=ch.source,
            score=_simple_score(query, ch.text),
            metadata=ch.metadata,
        )
    # sort and dedup by content similarity (very naive)
    candidates.sort(key=lambda c: c.score, reverse=True)
    seen = []
    results: List[DocChunk] = []
    for ch in candidates:
        if len(results) >= max(limit, 1):
            break
        sig = " ".join(_tokenize(ch.text))[:200]
        if sig in seen:
            continue
        seen.append(sig)
        results.append(ch)
    return results
