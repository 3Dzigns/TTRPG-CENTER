"""Pass E graph builder integrating with LlamaIndex, Neo4j persistence, and fallback logic."""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from src_common.config import ConfigManager
from src_common.logging import get_logger
from src_common.job_logging import log_to_job, log_pass_start, log_pass_complete
from src_common.neo4j_graph_service import GraphNode, GraphRelationship, Neo4jGraphService

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
    neo4j_used: bool = False
    nodes_persisted: int = 0
    relationships_persisted: int = 0
    verification_count: int = 0


@dataclass
class SourceMetadata:
    """Metadata describing the source document for a job."""

    source_hash: str
    source_file: str
    environment: str
    job_id: str


class GraphBuilder:
    """Builds graph artifacts from vector data and persists to Neo4j."""

    def __init__(self, job_id: str, env: str, job_log_file: Optional[Path] = None) -> None:
        self.job_id = job_id
        self.env = env
        self.job_log_file = job_log_file
        self.config = ConfigManager()
        self._neo4j_enabled = self._should_use_neo4j()
        self._graph_service: Optional[Neo4jGraphService] = None

    def process(self, job_dir: Path) -> PassEResult:
        started_at = time.perf_counter()

        log_pass_start("E", "Graph Building & Cross-References (LlamaIndex/Neo4j)", self.job_log_file)

        pass_dir = job_dir / "pass_e"
        pass_dir.mkdir(parents=True, exist_ok=True)

        vector_path = job_dir / "pass_d" / f"{self.job_id}_pass_d_vectors.jsonl"
        if not vector_path.exists():
            raise FileNotFoundError(f"Pass D vectors not found: {vector_path}")

        logger.info("Pass E: Loading vectors from %s", vector_path.name)
        vector_records = list(self._load_vectors(vector_path))
        logger.info("Pass E: Loaded %s vectors for graph building", len(vector_records))

        chunk_texts = self._load_chunk_texts(job_dir)
        dictionary_terms = self._load_dictionary_entries(job_dir)
        source_meta = self._load_source_metadata(job_dir)

        llama_used = False
        fallback_used = False

        if vector_records and LLAMA_AVAILABLE:
            try:
                logger.info("Pass E: Starting LlamaIndex graph compilation for %s vectors", len(vector_records))
                log_to_job(
                    f"Starting LlamaIndex graph compilation for {len(vector_records)} vectors (20-60s operation)",
                    self.job_log_file,
                    "info",
                    "E",
                )
                graph_started = time.perf_counter()
                nodes, edges = self._build_with_llama(vector_records)
                llama_used = True
                graph_duration = time.perf_counter() - graph_started
                logger.info(
                    "Pass E: LlamaIndex graph compiled in %.1fs (%s nodes, %s edges)",
                    graph_duration,
                    len(nodes),
                    len(edges),
                )
                log_to_job(
                    f"Graph compiled in {graph_duration:.1f}s ({len(nodes)} nodes, {len(edges)} edges)",
                    self.job_log_file,
                    "info",
                    "E",
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "pass_e.llama_failure",
                    extra={"job_id": self.job_id, "reason": str(exc)},
                )
                logger.info("Pass E: Falling back to simple graph generation")
                nodes, edges = self._build_fallback(vector_records)
                fallback_used = True
        else:
            logger.info(
                "Pass E: LlamaIndex not available or no vectors, using fallback graph generation for %s vectors",
                len(vector_records),
            )
            nodes, edges = self._build_fallback(vector_records)
            fallback_used = True

        # Augment nodes/edges with dictionary term relationships
        term_nodes, mention_edges, neo4j_nodes, neo4j_relationships = self._build_term_relationships(
            dictionary_terms,
            chunk_texts,
            source_meta,
        )
        nodes.extend(term_nodes)
        edges.extend(mention_edges)

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
                    "neo4j_used": bool(neo4j_relationships),
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
                        "terms": len(term_nodes),
                        "mentions": len(mention_edges),
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

        nodes_persisted = 0
        relationships_persisted = 0
        verification_count = 0

        if self._neo4j_enabled and neo4j_nodes:
            nodes_persisted, relationships_persisted = self._persist_to_neo4j(neo4j_nodes, neo4j_relationships)
            if relationships_persisted > 0:
                verification_count = self._verify_neo4j(source_meta)
                if verification_count <= 0:
                    raise RuntimeError(
                        f"Pass E: Neo4j verification failed for job {self.job_id} (source {source_meta.source_hash})"
                    )
                log_to_job(
                    f"Neo4j write verified with {verification_count} relationships",
                    self.job_log_file,
                    "info",
                    "E",
                )
            else:
                log_to_job(
                    "Neo4j configured but no term relationships were generated; skipping verification",
                    self.job_log_file,
                    "warning",
                    "E",
                )
        elif self._neo4j_enabled:
            log_to_job("Neo4j configured but no graph nodes were generated", self.job_log_file, "warning", "E")

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
                "neo4j_used": self._neo4j_enabled,
                "nodes_persisted": nodes_persisted,
                "relationships_persisted": relationships_persisted,
                "verification_count": verification_count,
                "duration_ms": processing_time_ms,
            },
        )

        stats = {
            "nodes_created": len(nodes),
            "edges_created": len(edges),
            "llama_used": llama_used,
            "fallback_used": fallback_used,
            "neo4j_nodes": nodes_persisted,
            "neo4j_edges": relationships_persisted,
            "neo4j_verified": verification_count,
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
            neo4j_used=self._neo4j_enabled and relationships_persisted > 0,
            nodes_persisted=nodes_persisted,
            relationships_persisted=relationships_persisted,
            verification_count=verification_count,
        )

    def _load_vectors(self, vector_path: Path) -> Iterable[Dict[str, Any]]:
        with vector_path.open("r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                yield json.loads(line)

    def _load_chunk_texts(self, job_dir: Path) -> Dict[str, Dict[str, Any]]:
        chunks_file = job_dir / "pass_c" / f"{self.job_id}_pass_c_chunks.jsonl"
        chunk_texts: Dict[str, Dict[str, Any]] = {}
        if not chunks_file.exists():
            return chunk_texts
        with chunks_file.open("r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                data = json.loads(line)
                chunk_id = data.get("chunk_id")
                if not chunk_id:
                    continue
                chunk_texts[str(chunk_id)] = {
                    "text": data.get("text", ""),
                    "page_number": data.get("page_number") or data.get("page"),
                    "metadata": data,
                }
        return chunk_texts

    def _load_dictionary_entries(self, job_dir: Path) -> List[Dict[str, Any]]:
        artifact_path = job_dir / f"{self.job_id}_pass_a_dict.json"
        if not artifact_path.exists():
            logger.info("Pass E: Dictionary artifact not found at %s", artifact_path)
            return []
        try:
            with artifact_path.open("r", encoding="utf-8") as handle:
                payload = json.load(handle)
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("Pass E: Unable to parse Pass A dictionary artifact: %s", exc)
            return []
        entries = payload.get("dictionary_entries") or []
        normalized_entries: List[Dict[str, Any]] = []
        for entry in entries:
            term = (entry or {}).get("term")
            if not term:
                continue
            normalized_entries.append(self._normalize_dictionary_entry(entry))
        logger.info("Pass E: Loaded %s dictionary terms", len(normalized_entries))
        return normalized_entries

    def _normalize_dictionary_entry(self, entry: Dict[str, Any]) -> Dict[str, Any]:
        term = str(entry.get("term", "")).strip()
        definition = entry.get("definition")
        category = entry.get("category")
        sources = entry.get("sources") or []
        source_hash = None
        source_file = None
        for source in sources:
            if not isinstance(source, dict):
                continue
            if not source_hash and source.get("source_hash"):
                source_hash = str(source.get("source_hash"))
            if not source_file and source.get("source_file"):
                source_file = str(source.get("source_file"))
        normalized_term = self._normalize_term(term)
        term_id = self._build_term_id(normalized_term, source_hash)
        return {
            "term": term,
            "term_normalized": normalized_term,
            "definition": definition,
            "category": category,
            "sources": sources,
            "term_id": term_id,
            "source_hash": source_hash,
            "source_file": source_file,
        }

    def _build_term_relationships(
        self,
        dictionary_terms: List[Dict[str, Any]],
        chunk_texts: Dict[str, Dict[str, Any]],
        source_meta: SourceMetadata,
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], Dict[str, GraphNode], List[GraphRelationship]]:
        term_nodes_for_artifact: List[Dict[str, Any]] = []
        mention_edges_for_artifact: List[Dict[str, Any]] = []
        neo4j_nodes: Dict[str, GraphNode] = {}
        neo4j_relationships: List[GraphRelationship] = []

        chunk_nodes = self._build_chunk_nodes(chunk_texts, source_meta)
        neo4j_nodes.update(chunk_nodes)

        if not dictionary_terms:
            return term_nodes_for_artifact, mention_edges_for_artifact, neo4j_nodes, neo4j_relationships

        for term_entry in dictionary_terms:
            term_id = term_entry["term_id"]
            chunk_ids = self._resolve_term_chunk_ids(term_entry, chunk_texts)
            if not chunk_ids:
                # Fall back to linking first chunk if available to avoid dangling nodes
                first_chunk_id = next(iter(chunk_texts.keys()), None)
                if first_chunk_id:
                    chunk_ids = [first_chunk_id]
                    logger.debug(
                        "Pass E: Falling back to first chunk for term '%s' due to missing direct match",
                        term_entry["term"],
                    )
            if not chunk_ids:
                continue

            term_nodes_for_artifact.append(
                {
                    "id": term_id,
                    "type": "term",
                    "term": term_entry["term"],
                    "category": term_entry.get("category"),
                    "sources": term_entry.get("sources"),
                }
            )

            term_node = GraphNode(
                id=term_id,
                labels=["Term"],
                properties={
                    "term": term_entry["term"],
                    "term_normalized": term_entry["term_normalized"],
                    "category": term_entry.get("category"),
                    "definition": term_entry.get("definition"),
                    "job_id": self.job_id,
                    "environment": self.env,
                    "source_hash": term_entry.get("source_hash") or source_meta.source_hash,
                    "source_file": term_entry.get("source_file") or source_meta.source_file,
                    "sources_json": json.dumps(term_entry.get("sources") or []),
                    "created_at": iso_timestamp(),
                },
            )
            neo4j_nodes[term_node.id] = term_node

            for chunk_id in chunk_ids:
                mention_edges_for_artifact.append(
                    {
                        "source": term_id,
                        "target": chunk_id,
                        "predicate": "MENTIONS",
                    }
                )
                relationship = GraphRelationship(
                    source_id=term_id,
                    target_id=chunk_id,
                    relationship_type="MENTIONS",
                    properties={
                        "job_id": self.job_id,
                        "environment": self.env,
                        "source_hash": term_entry.get("source_hash") or source_meta.source_hash,
                        "term": term_entry["term"],
                        "created_at": iso_timestamp(),
                    },
                )
                neo4j_relationships.append(relationship)

        return term_nodes_for_artifact, mention_edges_for_artifact, neo4j_nodes, neo4j_relationships

    def _build_chunk_nodes(self, chunk_texts: Dict[str, Dict[str, Any]], source_meta: SourceMetadata) -> Dict[str, GraphNode]:
        chunk_nodes: Dict[str, GraphNode] = {}
        for chunk_id, data in chunk_texts.items():
            metadata = data.get("metadata", {})
            chunk_nodes[chunk_id] = GraphNode(
                id=chunk_id,
                labels=["Chunk"],
                properties={
                    "chunk_id": chunk_id,
                    "job_id": self.job_id,
                    "environment": self.env,
                    "source_hash": source_meta.source_hash,
                    "source_file": source_meta.source_file,
                    "doc_id": metadata.get("doc_id"),
                    "part_id": metadata.get("part_id"),
                    "section_id": metadata.get("section_id"),
                    "page_number": data.get("page_number"),
                    "content_preview": self._content_preview(data.get("text", "")),
                    "created_at": iso_timestamp(),
                },
            )
        return chunk_nodes

    def _resolve_term_chunk_ids(
        self,
        term_entry: Dict[str, Any],
        chunk_texts: Dict[str, Dict[str, Any]],
    ) -> List[str]:
        candidates: List[str] = []
        seen: set[str] = set()
        sources = term_entry.get("sources") or []
        for source in sources:
            if not isinstance(source, dict):
                continue
            chunk_id = source.get("chunk_id")
            if chunk_id and chunk_id in chunk_texts and chunk_id not in seen:
                candidates.append(chunk_id)
                seen.add(chunk_id)
                continue
            page = source.get("page") or source.get("page_number")
            if page is not None:
                for cid, payload in chunk_texts.items():
                    if str(page) == str(payload.get("page_number")) and cid not in seen:
                        candidates.append(cid)
                        seen.add(cid)
        if candidates:
            return candidates
        term = term_entry.get("term", "")
        if term:
            term_lower = term.lower()
            for cid, payload in chunk_texts.items():
                text = payload.get("text", "").lower()
                if term_lower and term_lower in text and cid not in seen:
                    candidates.append(cid)
                    seen.add(cid)
                    if len(candidates) >= 3:
                        break
        return candidates

    def _persist_to_neo4j(
        self,
        nodes: Dict[str, GraphNode],
        relationships: List[GraphRelationship],
    ) -> Tuple[int, int]:
        service = self._get_graph_service()
        nodes_persisted = 0
        relationships_persisted = 0

        for node in nodes.values():
            ok = service.upsert_node(node)
            if not ok:
                raise RuntimeError(f"Pass E: Failed to upsert Neo4j node {node.id}")
            nodes_persisted += 1

        for relationship in relationships:
            ok = service.upsert_relationship(relationship)
            if not ok:
                raise RuntimeError(
                    f"Pass E: Failed to upsert Neo4j relationship {relationship.source_id}->{relationship.target_id}"
                )
            relationships_persisted += 1

        logger.info(
            "pass_e.neo4j.persisted",
            extra={
                "job_id": self.job_id,
                "nodes": nodes_persisted,
                "relationships": relationships_persisted,
            },
        )
        return nodes_persisted, relationships_persisted

    def _verify_neo4j(self, source_meta: SourceMetadata) -> int:
        service = self._get_graph_service()
        with service._session() as session:  # type: ignore[attr-defined]
            result = session.run(
                (
                    "MATCH (t:Term {job_id:$job_id, environment:$env})-"
                    "[r:MENTIONS]->(c:Chunk {job_id:$job_id, environment:$env}) "
                    "WHERE r.source_hash = $source_hash RETURN count(r) AS count"
                ),
                {
                    "job_id": self.job_id,
                    "env": self.env,
                    "source_hash": source_meta.source_hash,
                },
            )
            record = result.single()
            count = int(record["count"]) if record else 0
            logger.info(
                "pass_e.neo4j.verified",
                extra={
                    "job_id": self.job_id,
                    "relationships": count,
                },
            )
            return count

    def _get_graph_service(self) -> Neo4jGraphService:
        if self._graph_service is None:
            self._graph_service = Neo4jGraphService(self.env)
            if self._graph_service.driver is None:
                raise RuntimeError("Pass E: Neo4j service failed to initialize")
        return self._graph_service

    def _should_use_neo4j(self) -> bool:
        uri = self.config.get_config("NEO4J_URI")
        user = self.config.get_config("NEO4J_USER") or self.config.get_config("NEO4J_USERNAME")
        password = self.config.get_config("NEO4J_PASSWORD") or self.config.get_config("NEO4J_PASS")
        if not (uri and user and password):
            logger.info("Pass E: Neo4j configuration incomplete; persistence disabled")
            return False
        return True

    def _build_with_llama(self, records: List[Dict[str, Any]]):
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

    def _build_fallback(self, records: List[Dict[str, Any]]):
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

    def _proposed_actions(self, nodes: List[Dict[str, Any]], edges: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        actions: List[Dict[str, Any]] = []
        if not nodes:
            actions.append({"action": "review_ingestion", "reason": "no_nodes"})
        elif not edges:
            actions.append({"action": "enrich_relationships", "reason": "no_edges"})
        else:
            actions.append({"action": "noop", "reason": "graph_ok"})
        return actions

    def _load_source_metadata(self, job_dir: Path) -> SourceMetadata:
        manifest_candidates = [
            job_dir / "manifest.json",
            job_dir / "pass_a" / f"{self.job_id}_pass_a_manifest.json",
        ]
        for candidate in manifest_candidates:
            if not candidate.exists():
                continue
            try:
                with candidate.open("r", encoding="utf-8") as handle:
                    manifest = json.load(handle)
            except Exception as exc:
                logger.debug("Pass E: unable to parse manifest %s: %s", candidate, exc)
                continue

            source_hash = (
                manifest.get("source_info", {}).get("source_hash")
                or manifest.get("pass_0_result", {}).get("source_hash")
                or manifest.get("source_hash")
            )
            source_file = (
                manifest.get("source_file")
                or manifest.get("source")
                or manifest.get("source_path")
                or manifest.get("pdf_path")
            )
            environment = manifest.get("environment") or self.env

            if isinstance(source_file, list) and source_file:
                source_file = source_file[0]

            if source_hash and source_file:
                return SourceMetadata(
                    source_hash=str(source_hash),
                    source_file=str(source_file),
                    environment=str(environment or self.env),
                    job_id=self.job_id,
                )

        raise RuntimeError("Pass E: Unable to determine source metadata for Neo4j persistence")

    @staticmethod
    def _normalize_term(term: str) -> str:
        normalized = term.strip().lower()
        normalized = re.sub(r"[^a-z0-9]+", "_", normalized)
        normalized = re.sub(r"_+", "_", normalized)
        return normalized.strip("_")

    @staticmethod
    def _build_term_id(normalized_term: str, source_hash: Optional[str]) -> str:
        if source_hash:
            normalized_hash = GraphBuilder._normalize_term(str(source_hash))
            if normalized_hash:
                return f"{normalized_term}::{normalized_hash}"
        return normalized_term or "term_undefined"

    @staticmethod
    def _content_preview(text: str, limit: int = 256) -> str:
        preview = text.strip()
        if len(preview) > limit:
            preview = preview[: limit - 3] + "..."
        return preview


def process_pass_e(job_dir: Path, job_id: str, env: str, job_log_file: Optional[Path] = None) -> PassEResult:
    builder = GraphBuilder(job_id=job_id, env=env, job_log_file=job_log_file)
    return builder.process(job_dir)


def iso_timestamp() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
