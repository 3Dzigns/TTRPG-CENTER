from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from ..ttrpg_logging import get_logger
from ..vector_store.factory import make_vector_store

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



def _retrieve_from_store(query: str, env: str, top_k: int = 5) -> List[DocChunk]:
    try:
        store = make_vector_store(env)
    except Exception as exc:
        logger.warning("Vector store unavailable; falling back to local artifacts: %s", exc)
        return []

    filters: Dict[str, Any] = {
        "query_text": query,
        "scan_limit": 2000,
    }
    raw_results = store.query(vector=None, top_k=max(top_k * 2, 10), filters=filters)
    if not raw_results:
        return []

    chunks: List[DocChunk] = []
    for doc in raw_results:
        text = doc.get("content") or ""
        metadata = doc.get("metadata") or {}
        score = doc.get("score", 0.0)
        chunks.append(
            DocChunk(
                id=str(doc.get("chunk_id")),
                text=text,
                source=f"vector:{store.backend_name}:{metadata.get('source_file', 'unknown')}",
                score=score,
                metadata=metadata,
            )
        )
    chunks.sort(key=lambda c: c.score, reverse=True)
    return chunks[: max(1, top_k)]


def retrieve(plan: Union[Dict[str, Any], 'QueryPlan'], query: str, env: str, limit: int = 3) -> List[DocChunk]:
    """
    Graph-augmented hybrid retriever. Supports both legacy plan dictionaries and new QueryPlan objects
    with graph expansion capabilities. Performs lightweight lexical scoring over local artifacts
    to satisfy Phase 2 contract without external services. If AstraDB is configured and reachable,
    prefers AstraDB as the source of truth.
    """
    # Handle both legacy dict plans and new QueryPlan objects
    if hasattr(plan, 'retrieval_strategy'):
        # QueryPlan object
        plan_dict = plan.retrieval_strategy
        graph_expansion = getattr(plan, 'graph_expansion', None)
        expanded_query = _get_expanded_query(query, graph_expansion)
    else:
        # Legacy dict plan
        plan_dict = plan
        graph_expansion = None
        expanded_query = query

    top_k = int(plan_dict.get("vector_top_k", 5))

    # Prefer AstraDB when available (use expanded query for better results)
    astra_results = _retrieve_from_store(expanded_query, env, top_k)
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
            # Apply reranking if enabled
            results = _apply_reranking(results, plan, query, env)
            return results

    candidates = list(_iter_candidate_chunks(env))
    for i, ch in enumerate(candidates):
        # Use expanded query for better scoring when available
        base_score = _simple_score(expanded_query, ch.text)

        # Apply graph-aware boosting if we have expansion metadata
        if graph_expansion and graph_expansion.get("enabled"):
            base_score = _apply_graph_boost(base_score, ch, graph_expansion)

        candidates[i] = DocChunk(
            id=ch.id,
            text=ch.text,
            source=ch.source,
            score=base_score,
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

    # Apply reranking if enabled
    results = _apply_reranking(results, plan, query, env)

    return results


def _get_expanded_query(original_query: str, graph_expansion: Optional[Dict[str, Any]]) -> str:
    """
    Extract the expanded query from graph expansion metadata.

    Args:
        original_query: Original user query
        graph_expansion: Graph expansion metadata from QueryPlan

    Returns:
        Expanded query string or original if no expansion available
    """
    if not graph_expansion or not graph_expansion.get("enabled"):
        return original_query

    # Return expanded query if available, otherwise fall back to original
    expanded = graph_expansion.get("expanded_query")
    if expanded and expanded != original_query:
        logger.debug(f"Using expanded query: '{original_query}' -> '{expanded}'")
        return expanded

    return original_query


def _apply_graph_boost(base_score: float, chunk: DocChunk, graph_expansion: Dict[str, Any]) -> float:
    """
    Apply graph-aware boosting to the base similarity score.

    Args:
        base_score: Base similarity score
        chunk: Document chunk to score
        graph_expansion: Graph expansion metadata

    Returns:
        Boosted score incorporating graph relationships
    """
    if not graph_expansion.get("enabled") or not graph_expansion.get("expansion_terms"):
        return base_score

    boost_factor = 1.0
    text_lower = chunk.text.lower()

    # Check for mentions of expanded terms in the chunk
    for term_data in graph_expansion.get("expansion_terms", []):
        term = term_data.get("term", "").lower()
        confidence = term_data.get("confidence", 0.0)
        source = term_data.get("source", "")

        if term and term in text_lower:
            # Apply boost based on expansion source and confidence
            if source == "alias":
                boost_factor += confidence * 0.3  # Moderate boost for aliases
            elif source == "cross_ref":
                boost_factor += confidence * 0.4  # Higher boost for cross-references
            elif source == "graph_relation":
                boost_factor += confidence * 0.2  # Lower boost for graph relations

    # Cap the boost to prevent extreme scores
    boost_factor = min(boost_factor, 2.0)

    boosted_score = base_score * boost_factor

    if boost_factor > 1.0:
        logger.debug(f"Applied graph boost: {base_score:.3f} -> {boosted_score:.3f} "
                    f"(factor: {boost_factor:.2f})")

    return boosted_score


def _apply_reranking(
    results: List[DocChunk],
    plan: Union[Dict[str, Any], 'QueryPlan'],
    query: str,
    env: str
) -> List[DocChunk]:
    """
    Apply hybrid reranking to results if enabled in the plan.

    Args:
        results: Initial retrieval results
        plan: Query plan (dict or QueryPlan object)
        query: Original user query
        env: Environment

    Returns:
        Reranked results as DocChunk list
    """
    if not results:
        return results

    # Check if reranking is enabled
    reranking_config = None
    classification = None

    if hasattr(plan, 'reranking_config'):
        # QueryPlan object
        reranking_config = getattr(plan, 'reranking_config', None)
        classification = getattr(plan, 'classification', None)
        query_plan_dict = {
            'retrieval_strategy': plan.retrieval_strategy,
            'graph_expansion': getattr(plan, 'graph_expansion', None)
        }
    else:
        # Legacy dict plan - no reranking support
        return results

    if not reranking_config:
        return results

    try:
        # Import reranker components
        from .hybrid_reranker import HybridReranker, RerankingConfig, RerankingStrategy

        # Create reranker
        reranker = HybridReranker(environment=env)

        # Convert reranking config to RerankingConfig object
        strategy = RerankingStrategy(reranking_config.get("strategy", "hybrid_full"))
        weights = reranking_config.get("weights", {})

        config = RerankingConfig(
            strategy=strategy,
            max_results_to_rerank=reranking_config.get("max_results", 20),
            reranking_timeout_ms=reranking_config.get("timeout_ms", 100),
            enable_signal_caching=reranking_config.get("enable_caching", True)
        )

        # Apply custom weights if provided
        if weights:
            config.vector_weight = weights.get("vector", 0.3)
            config.graph_weight = weights.get("graph", 0.2)
            config.content_weight = weights.get("content", 0.2)
            config.domain_weight = weights.get("domain", 0.2)
            config.metadata_weight = weights.get("metadata", 0.1)

        # Convert DocChunk to dict format for reranker
        results_dicts = []
        for chunk in results:
            result_dict = {
                'id': chunk.id,
                'content': chunk.text,
                'score': chunk.score,
                'metadata': chunk.metadata.copy() if chunk.metadata else {},
                'source': chunk.source
            }
            results_dicts.append(result_dict)

        # Apply reranking
        reranked_results = reranker.rerank_results(
            query=query,
            results=results_dicts,
            config=config,
            query_plan=query_plan_dict,
            classification=classification
        )

        # Convert back to DocChunk format
        final_results = []
        for reranked in reranked_results:
            original = reranked.original_result

            doc_chunk = DocChunk(
                id=original['id'],
                text=original['content'],
                source=original['source'],
                score=reranked.final_score,
                metadata=original['metadata']
            )
            final_results.append(doc_chunk)

        logger.info(f"Applied reranking: {len(results)} -> {len(final_results)} results")

        return final_results

    except ImportError:
        logger.warning("Reranker components not available, skipping reranking")
        return results

    except Exception as e:
        logger.warning(f"Error during reranking: {e}, returning original results")
        return results
