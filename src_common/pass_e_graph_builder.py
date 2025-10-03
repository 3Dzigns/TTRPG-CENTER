"""Pass E graph builder integrating with LlamaIndex and fallback logic."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional

from src_common.config import ConfigManager
from src_common.logging import get_logger
from src_common.job_logging import log_to_job, log_pass_start, log_pass_complete

try:
    from llama_index.graph_stores.simple import SimpleGraphStore  # type: ignore
    from llama_index.core import KnowledgeGraphIndex  # type: ignore
    from llama_index.core import Document as LlamaDocument  # type: ignore
    LLAMA_AVAILABLE = True
except Exception:  # pragma: no cover - optional dependency guard
    SimpleGraphStore = None
    KnowledgeGraphIndex = None
    LlamaDocument = None
    LLAMA_AVAILABLE = False

logger = get_logger(__name__)


@dataclass
class PassEResult:
    """Structured Pass E result."""

    job_id: str
    nodes_created: int
    edges_created: int
    llama_used: bool
    fallback_used: bool
    processing_time_ms: int
    artifacts: List[str]
    success: bool = True
    error_message: Optional[str] = None


class GraphBuilder:
    """Builds graph artifacts from vector data."""

    def __init__(self, job_id: str, env: str, job_log_file: Optional[Path] = None) -> None:
        self.job_id = job_id
        self.env = env
        self.job_log_file = job_log_file
        self.config = ConfigManager()

    def process(self, job_dir: Path) -> PassEResult:
        started_at = time.perf_counter()

        # Pass start logging
        log_pass_start("E", "Graph Building & Cross-References (LlamaIndex)", self.job_log_file)

        pass_dir = job_dir / "pass_e"
        pass_dir.mkdir(parents=True, exist_ok=True)

        vector_path = job_dir / "pass_d" / f"{self.job_id}_pass_d_vectors.jsonl"
        if not vector_path.exists():
            raise FileNotFoundError(f"Pass D vectors not found: {vector_path}")

        logger.info(f"Pass E: Loading vectors from {vector_path.name}")
        vector_records = list(self._load_vectors(vector_path))
        logger.info(f"Pass E: Loaded {len(vector_records)} vectors for graph building")

        llama_used = False
        fallback_used = False

        if vector_records and LLAMA_AVAILABLE:
            try:
                logger.info(f"Pass E: Starting LlamaIndex graph compilation for {len(vector_records)} vectors (this may take 20-60s)")
                log_to_job(f"Starting LlamaIndex graph compilation for {len(vector_records)} vectors (20-60s operation)", self.job_log_file, "info", "E")
                graph_started = time.perf_counter()

                nodes, edges = self._build_with_llama(vector_records)
                llama_used = True

                graph_duration = time.perf_counter() - graph_started
                logger.info(f"Pass E: LlamaIndex graph compiled in {graph_duration:.1f}s ({len(nodes)} nodes, {len(edges)} edges)")
                log_to_job(f"Graph compiled in {graph_duration:.1f}s ({len(nodes)} nodes, {len(edges)} edges)", self.job_log_file, "info", "E")
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "pass_e_llama_failure",
                    extra={"job_id": self.job_id, "reason": str(exc)},
                )
                logger.info(f"Pass E: Falling back to simple graph generation")
                nodes, edges = self._build_fallback(vector_records)
                fallback_used = True
        else:
            logger.info(f"Pass E: LlamaIndex not available, using fallback graph generation for {len(vector_records)} vectors")
            nodes, edges = self._build_fallback(vector_records)
            fallback_used = True

        graph_path = pass_dir / "graph.json"
        with graph_path.open("w", encoding="utf-8") as handle:
            json.dump({"nodes": nodes, "edges": edges}, handle, indent=2)

        summary_path = pass_dir / "graph_summary.json"
        with summary_path.open("w", encoding="utf-8") as handle:
            json.dump(
                {
                    "job_id": self.job_id,
                    "env": self.env,
                    "nodes": len(nodes),
                    "edges": len(edges),
                    "llama_used": llama_used,
                    "fallback_used": fallback_used,
                    "generated_at": iso_timestamp(),
                },
                handle,
                indent=2,
            )

        delta_path = pass_dir / "dict_delta.passE.json"
        with delta_path.open("w", encoding="utf-8") as handle:
            json.dump(
                {
                    "job_id": self.job_id,
                    "graph_statistics": {
                        "nodes": len(nodes),
                        "edges": len(edges),
                    },
                    "suggested_actions": self._proposed_actions(nodes, edges),
                },
                handle,
                indent=2,
            )

        artifacts = [
            graph_path.relative_to(job_dir).as_posix(),
            summary_path.relative_to(job_dir).as_posix(),
            delta_path.relative_to(job_dir).as_posix(),
        ]

        processing_time_ms = int((time.perf_counter() - started_at) * 1000)
        duration_seconds = processing_time_ms / 1000

        logger.info(
            "pass_e_complete",
            extra={
                "job_id": self.job_id,
                "nodes": len(nodes),
                "edges": len(edges),
                "llama_used": llama_used,
                "fallback_used": fallback_used,
                "duration_ms": processing_time_ms,
            },
        )

        # Pass complete logging
        stats = {
            "nodes_created": len(nodes),
            "edges_created": len(edges),
            "llama_used": llama_used,
            "fallback_used": fallback_used
        }
        log_pass_complete("E", duration_seconds, stats, self.job_log_file)

        return PassEResult(
            job_id=self.job_id,
            nodes_created=len(nodes),
            edges_created=len(edges),
            llama_used=llama_used,
            fallback_used=fallback_used,
            processing_time_ms=processing_time_ms,
            artifacts=artifacts,
        )

    def _load_vectors(self, vector_path: Path) -> Iterable[Dict[str, object]]:
        with vector_path.open("r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                yield json.loads(line)

    def _build_with_llama(self, records: List[Dict[str, object]]):
        assert SimpleGraphStore is not None and KnowledgeGraphIndex is not None and LlamaDocument is not None
        graph_store = SimpleGraphStore()
        documents = [
            LlamaDocument(
                text=record.get("metadata", {}).get("chunk_id", ""),
                metadata={"doc_id": record.get("doc_id"), "chunk_id": record.get("chunk_id")},
            )
            for record in records
        ]
        index = KnowledgeGraphIndex.from_documents(documents, graph_store=graph_store)
        nodes = [
            {
                "id": node.node_id,
                "doc_id": node.metadata.get("doc_id"),
                "chunk_id": node.metadata.get("chunk_id"),
            }
            for node in index.index_struct.nodes
        ]
        edges = [
            {
                "source": edge.n1,
                "target": edge.n2,
                "predicate": edge.relationship,
            }
            for edge in index.index_struct.relationships
        ]
        return nodes, edges

    def _build_fallback(self, records: List[Dict[str, object]]):
        nodes = []
        edges = []
        for record in records:
            node_id = record.get("chunk_id") or record.get("metadata", {}).get("chunk_id")
            if not node_id:
                continue
            node = {
                "id": node_id,
                "doc_id": record.get("doc_id"),
                "part_id": record.get("part_id"),
                "section_id": record.get("section_id"),
            }
            nodes.append(node)
        for first, second in zip(nodes, nodes[1:], strict=False):
            edges.append(
                {
                    "source": first["id"],
                    "target": second["id"],
                    "predicate": "follows",
                }
            )
        return nodes, edges

    def _proposed_actions(self, nodes: List[Dict[str, object]], edges: List[Dict[str, object]]) -> List[Dict[str, object]]:
        actions: List[Dict[str, object]] = []
        if not nodes:
            actions.append({"action": "review_ingestion", "reason": "no_nodes"})
        elif not edges:
            actions.append({"action": "enrich_relationships", "reason": "no_edges"})
        else:
            actions.append({"action": "noop", "reason": "graph_ok"})
        return actions


def process_pass_e(job_dir: Path, job_id: str, env: str, job_log_file: Optional[Path] = None) -> PassEResult:
    builder = GraphBuilder(job_id=job_id, env=env, job_log_file=job_log_file)
    return builder.process(job_dir)


def iso_timestamp() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
