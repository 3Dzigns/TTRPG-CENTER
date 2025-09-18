"""
Graph Artifact Loader for Graph Augmented Retrieval

Loads and manages graph structures created by Pass E for enhanced query processing.
Provides efficient access to graph nodes, edges, cross-references, and alias mappings.
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Dict, Any, List, Optional, Set
from dataclasses import dataclass
from threading import Lock
import os

from ..ttrpg_logging import get_logger

logger = get_logger(__name__)


@dataclass
class GraphNode:
    """Graph node representing a document entity (section, chunk, concept)"""
    node_id: str
    node_type: str  # section, chunk, entity
    title: str
    content: Optional[str] = None
    parent_id: Optional[str] = None
    children: List[str] = None
    metadata: Optional[Dict[str, Any]] = None

    def __post_init__(self):
        if self.children is None:
            self.children = []


@dataclass
class GraphEdge:
    """Graph edge representing relationships between nodes"""
    edge_id: str
    source_id: str
    target_id: str
    edge_type: str  # contains, references, relates_to
    weight: float = 1.0
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class CrossReference:
    """Cross-reference between game elements with confidence scoring"""
    ref_id: str
    source_element: str
    target_element: str
    ref_type: str  # spell_to_class, feat_to_rule, etc.
    confidence: float
    context: str


@dataclass
class GraphSnapshot:
    """Complete graph structure loaded from Pass E artifacts"""
    job_id: str
    created_at: float
    nodes: Dict[str, GraphNode]
    edges: List[GraphEdge]
    cross_references: List[CrossReference]
    aliases: Dict[str, Set[str]]  # term -> set of aliases

    def get_node(self, node_id: str) -> Optional[GraphNode]:
        """Get node by ID"""
        return self.nodes.get(node_id)

    def get_children(self, node_id: str) -> List[GraphNode]:
        """Get child nodes for a given node"""
        node = self.get_node(node_id)
        if not node:
            return []
        return [self.nodes[child_id] for child_id in node.children if child_id in self.nodes]

    def get_related_nodes(self, node_id: str, max_depth: int = 2) -> List[GraphNode]:
        """Get related nodes via graph traversal (BFS)"""
        if node_id not in self.nodes:
            return []

        visited = set()
        queue = [(node_id, 0)]
        related = []

        while queue and len(related) < 50:  # Limit results
            current_id, depth = queue.pop(0)

            if current_id in visited or depth > max_depth:
                continue

            visited.add(current_id)
            current_node = self.nodes.get(current_id)

            if current_node and depth > 0:  # Don't include self
                related.append(current_node)

            # Add connected nodes to queue
            for edge in self.edges:
                if edge.source_id == current_id and edge.target_id not in visited:
                    queue.append((edge.target_id, depth + 1))
                elif edge.target_id == current_id and edge.source_id not in visited:
                    queue.append((edge.source_id, depth + 1))

        return related

    def find_cross_references(self, element: str) -> List[CrossReference]:
        """Find cross-references for a given element"""
        return [ref for ref in self.cross_references
                if element.lower() in ref.source_element.lower() or
                   element.lower() in ref.target_element.lower()]

    def expand_aliases(self, term: str) -> Set[str]:
        """Get aliases for a term"""
        term_lower = term.lower()
        aliases = set([term])  # Include original term

        # Direct aliases
        if term_lower in self.aliases:
            aliases.update(self.aliases[term_lower])

        # Reverse lookup - find terms that have this as an alias
        for key, alias_set in self.aliases.items():
            if term_lower in {alias.lower() for alias in alias_set}:
                aliases.add(key)
                aliases.update(alias_set)

        return aliases


class GraphLoader:
    """
    Loads and caches graph artifacts from Pass E ingestion jobs.

    Provides environment-specific loading and caching for optimal performance.
    """

    def __init__(self, environment: str = None):
        self.environment = environment or os.getenv("APP_ENV", "dev")
        self.cache_ttl = 3600  # 1 hour cache TTL
        self._cache: Dict[str, GraphSnapshot] = {}
        self._cache_timestamps: Dict[str, float] = {}
        self._lock = Lock()

        logger.info(f"GraphLoader initialized for environment: {self.environment}")

    def get_artifact_directory(self, job_id: str = None) -> Optional[Path]:
        """
        Get the artifact directory for the latest or specified job.

        Args:
            job_id: Specific job ID, or None for latest

        Returns:
            Path to artifact directory or None if not found
        """
        base_path = Path(f"artifacts/ingest/{self.environment}")

        if not base_path.exists():
            logger.warning(f"Artifacts directory not found: {base_path}")
            return None

        if job_id:
            # Specific job directory
            specific_path = base_path / job_id
            if specific_path.exists():
                return specific_path

            # Try job directories that contain the job_id
            for job_dir in base_path.iterdir():
                if job_dir.is_dir() and job_id in job_dir.name:
                    return job_dir

            logger.warning(f"Job directory not found for job_id: {job_id}")
            return None

        # Latest job - find most recent graph_snapshot.json
        latest_job = None
        latest_time = 0

        for job_dir in base_path.iterdir():
            if not job_dir.is_dir():
                continue

            graph_file = job_dir / "graph_snapshot.json"
            if graph_file.exists():
                try:
                    # Use file modification time
                    mtime = graph_file.stat().st_mtime
                    if mtime > latest_time:
                        latest_time = mtime
                        latest_job = job_dir
                except Exception as e:
                    logger.warning(f"Error checking {graph_file}: {e}")

        if latest_job:
            logger.debug(f"Using latest job directory: {latest_job}")
            return latest_job

        logger.warning(f"No valid job directories found in {base_path}")
        return None

    def load_graph_snapshot(self, job_id: str = None, force_reload: bool = False) -> Optional[GraphSnapshot]:
        """
        Load graph snapshot from artifacts.

        Args:
            job_id: Specific job ID, or None for latest
            force_reload: Force reload from disk, ignoring cache

        Returns:
            GraphSnapshot or None if not available
        """
        cache_key = job_id or "latest"

        with self._lock:
            # Check cache first
            if not force_reload and cache_key in self._cache:
                cached_time = self._cache_timestamps.get(cache_key, 0)
                if (time.time() - cached_time) < self.cache_ttl:
                    logger.debug(f"Returning cached graph for {cache_key}")
                    return self._cache[cache_key]

            # Load from disk
            artifact_dir = self.get_artifact_directory(job_id)
            if not artifact_dir:
                return None

            try:
                snapshot = self._load_snapshot_from_directory(artifact_dir)
                if snapshot:
                    # Cache the result
                    self._cache[cache_key] = snapshot
                    self._cache_timestamps[cache_key] = time.time()
                    logger.info(f"Loaded graph snapshot: {snapshot.job_id} "
                              f"({len(snapshot.nodes)} nodes, {len(snapshot.edges)} edges, "
                              f"{len(snapshot.cross_references)} cross-refs)")
                    return snapshot

            except Exception as e:
                logger.error(f"Failed to load graph snapshot from {artifact_dir}: {e}")
                return None

    def _load_snapshot_from_directory(self, artifact_dir: Path) -> Optional[GraphSnapshot]:
        """Load graph snapshot from artifact directory"""

        # Load graph snapshot
        graph_file = artifact_dir / "graph_snapshot.json"
        if not graph_file.exists():
            logger.warning(f"graph_snapshot.json not found in {artifact_dir}")
            return None

        with open(graph_file, 'r', encoding='utf-8') as f:
            graph_data = json.load(f)

        # Load alias map
        alias_file = artifact_dir / "alias_map.json"
        aliases = {}
        if alias_file.exists():
            with open(alias_file, 'r', encoding='utf-8') as f:
                alias_data = json.load(f)
                aliases = alias_data.get("aliases", {})

        # Convert to proper data structures
        nodes = {}
        for node_id, node_data in graph_data.get("nodes", {}).items():
            nodes[node_id] = GraphNode(
                node_id=node_id,
                node_type=node_data.get("node_type", "unknown"),
                title=node_data.get("title", ""),
                content=node_data.get("content"),
                parent_id=node_data.get("parent_id"),
                children=node_data.get("children", []),
                metadata=node_data.get("metadata", {})
            )

        edges = []
        for edge_data in graph_data.get("edges", []):
            edges.append(GraphEdge(
                edge_id=edge_data.get("edge_id", ""),
                source_id=edge_data.get("source_id", ""),
                target_id=edge_data.get("target_id", ""),
                edge_type=edge_data.get("edge_type", "unknown"),
                weight=edge_data.get("weight", 1.0),
                metadata=edge_data.get("metadata", {})
            ))

        cross_references = []
        for ref_data in graph_data.get("cross_references", []):
            cross_references.append(CrossReference(
                ref_id=ref_data.get("ref_id", ""),
                source_element=ref_data.get("source_element", ""),
                target_element=ref_data.get("target_element", ""),
                ref_type=ref_data.get("ref_type", "unknown"),
                confidence=ref_data.get("confidence", 0.0),
                context=ref_data.get("context", "")
            ))

        # Convert aliases to sets
        alias_dict = {}
        for term, alias_list in aliases.items():
            if isinstance(alias_list, list):
                alias_dict[term.lower()] = set(alias.lower() for alias in alias_list)
            else:
                alias_dict[term.lower()] = {str(alias_list).lower()}

        return GraphSnapshot(
            job_id=graph_data.get("job_id", "unknown"),
            created_at=graph_data.get("created_at", time.time()),
            nodes=nodes,
            edges=edges,
            cross_references=cross_references,
            aliases=alias_dict
        )

    def clear_cache(self) -> None:
        """Clear the graph cache"""
        with self._lock:
            self._cache.clear()
            self._cache_timestamps.clear()
            logger.info("Graph cache cleared")

    def get_cache_info(self) -> Dict[str, Any]:
        """Get cache information for debugging"""
        with self._lock:
            cache_info = {}
            for key, snapshot in self._cache.items():
                cache_time = self._cache_timestamps.get(key, 0)
                cache_info[key] = {
                    "job_id": snapshot.job_id,
                    "nodes": len(snapshot.nodes),
                    "edges": len(snapshot.edges),
                    "cross_references": len(snapshot.cross_references),
                    "aliases": len(snapshot.aliases),
                    "cached_at": cache_time,
                    "age_seconds": time.time() - cache_time
                }
            return cache_info


# Global loader instance per environment
_loader_instances: Dict[str, GraphLoader] = {}
_loader_lock = Lock()


def get_graph_loader(environment: str = None) -> GraphLoader:
    """
    Get or create a graph loader instance for the specified environment.

    Args:
        environment: Environment name (dev/test/prod)

    Returns:
        GraphLoader instance for the environment
    """
    env = environment or os.getenv("APP_ENV", "dev")

    with _loader_lock:
        if env not in _loader_instances:
            _loader_instances[env] = GraphLoader(env)
        return _loader_instances[env]