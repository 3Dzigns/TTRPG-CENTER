# src_common/graph/store.py
"""
Graph Store - Knowledge Graph (KG) and Workflow Graph (WG) storage and operations
US-301: Graph Schema & Store implementation
"""

import hashlib
import json
import time
import uuid
from typing import Dict, List, Literal, Optional, Any, Union
from dataclasses import dataclass, asdict
from pathlib import Path

from ..ttrpg_logging import get_logger

logger = get_logger(__name__)

# Phase 3 Graph Schema
NodeType = Literal["Rule", "Concept", "Procedure", "Step", "Entity", "SourceDoc", "Artifact", "Decision"]
EdgeType = Literal["depends_on", "part_of", "implements", "cites", "produces", "variant_of", "prereq"]

@dataclass
class GraphNode:
    """Graph node with versioning and metadata"""
    id: str
    type: NodeType
    properties: Dict[str, Any]
    created_at: float = None
    updated_at: float = None
    version: int = 1
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = time.time()
        if self.updated_at is None:
            self.updated_at = self.created_at

@dataclass
class GraphEdge:
    """Graph edge with properties and metadata"""
    id: str
    source: str
    type: EdgeType
    target: str
    properties: Dict[str, Any]
    created_at: float = None
    updated_at: float = None
    version: int = 1
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = time.time()
        if self.updated_at is None:
            self.updated_at = self.created_at
        # Generate deterministic ID if not provided
        if not self.id:
            content = f"{self.source}:{self.type}:{self.target}"
            self.id = f"edge:{hashlib.sha256(content.encode()).hexdigest()[:16]}"

class GraphStoreError(Exception):
    """Graph store operation errors"""
    pass

class GraphStore:
    """
    Phase 3 Graph Store for Knowledge Graph and Workflow Graph
    
    Provides CRUD operations with versioning, parameter queries,
    and write-ahead logging for Phase 3 graph-centered reasoning.
    """
    
    def __init__(self, client=None, storage_path: Optional[Path] = None):
        """
        Initialize graph store
        
        Args:
            client: External graph database client (Neo4j, AstraDB Graph, etc.)
            storage_path: Local storage path for development/testing
        """
        self.client = client
        self.storage_path = storage_path or Path("artifacts/graph")
        self.storage_path.mkdir(parents=True, exist_ok=True)
        
        # In-memory storage for development (will be replaced by real graph DB)
        self.nodes: Dict[str, GraphNode] = {}
        self.edges: Dict[str, GraphEdge] = {}
        self.write_ahead_log: List[Dict] = []
        
        # Security and performance limits
        self.MAX_DEPTH = 10
        self.MAX_NEIGHBORS = 1000
        
        # Load existing data if available
        self._load_from_storage()
        
        logger.info(f"Graph store initialized with {len(self.nodes)} nodes, {len(self.edges)} edges")
    
    def upsert_node(self, node_id: str, ntype: NodeType, properties: Dict[str, Any]) -> Dict[str, Any]:
        """
        Upsert a node with versioning and write-ahead logging
        
        Args:
            node_id: Unique node identifier
            ntype: Node type from NodeType enum
            properties: Node properties (sanitized for PII)
        
        Returns:
            Node data dictionary
        """
        try:
            # Validate node type
            if ntype not in ["Rule", "Concept", "Procedure", "Step", "Entity", "SourceDoc", "Artifact", "Decision"]:
                raise GraphStoreError(f"Invalid node type: {ntype}")
            
            # Sanitize properties for PII
            sanitized_props = self._sanitize_properties(properties)
            
            # Create or update node
            current_time = time.time()
            if node_id in self.nodes:
                # Update existing node
                existing = self.nodes[node_id]
                existing.properties.update(sanitized_props)
                existing.updated_at = current_time
                existing.version += 1
                node = existing
                logger.debug(f"Updated node {node_id} (version {node.version})")
            else:
                # Create new node
                node = GraphNode(
                    id=node_id,
                    type=ntype,
                    properties=sanitized_props,
                    created_at=current_time,
                    updated_at=current_time,
                    version=1
                )
                self.nodes[node_id] = node
                logger.debug(f"Created node {node_id}")
            
            # Write-ahead log entry
            self._log_operation("upsert_node", {
                "node_id": node_id,
                "type": ntype,
                "properties": sanitized_props,
                "timestamp": current_time
            })
            
            # Persist to storage
            self._save_to_storage()
            
            return asdict(node)
            
        except Exception as e:
            logger.error(f"Error upserting node {node_id}: {e}")
            raise GraphStoreError(f"Failed to upsert node: {e}")
    
    def upsert_edge(self, source: str, etype: EdgeType, target: str, properties: Dict[str, Any]) -> Dict[str, Any]:
        """
        Upsert an edge with versioning and write-ahead logging
        
        Args:
            source: Source node ID
            etype: Edge type from EdgeType enum  
            target: Target node ID
            properties: Edge properties
        
        Returns:
            Edge data dictionary
        """
        try:
            # Validate edge type
            if etype not in ["depends_on", "part_of", "implements", "cites", "produces", "variant_of", "prereq"]:
                raise GraphStoreError(f"Invalid edge type: {etype}")
            
            # Validate that nodes exist
            if source not in self.nodes:
                raise GraphStoreError(f"Source node {source} does not exist")
            if target not in self.nodes:
                raise GraphStoreError(f"Target node {target} does not exist")
            
            # Generate edge ID
            edge_content = f"{source}:{etype}:{target}"
            edge_id = f"edge:{hashlib.sha256(edge_content.encode()).hexdigest()[:16]}"
            
            # Sanitize properties
            sanitized_props = self._sanitize_properties(properties)
            
            # Create or update edge
            current_time = time.time()
            if edge_id in self.edges:
                # Update existing edge
                existing = self.edges[edge_id]
                existing.properties.update(sanitized_props)
                existing.updated_at = current_time
                existing.version += 1
                edge = existing
                logger.debug(f"Updated edge {edge_id} (version {edge.version})")
            else:
                # Create new edge
                edge = GraphEdge(
                    id=edge_id,
                    source=source,
                    type=etype,
                    target=target,
                    properties=sanitized_props,
                    created_at=current_time,
                    updated_at=current_time,
                    version=1
                )
                self.edges[edge_id] = edge
                logger.debug(f"Created edge {edge_id}")
            
            # Write-ahead log entry
            self._log_operation("upsert_edge", {
                "source": source,
                "type": etype,
                "target": target,
                "properties": sanitized_props,
                "timestamp": current_time
            })
            
            # Persist to storage
            self._save_to_storage()
            
            return asdict(edge)
            
        except Exception as e:
            logger.error(f"Error upserting edge {source}->{target}: {e}")
            raise GraphStoreError(f"Failed to upsert edge: {e}")
    
    def get_node(self, node_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve a node by ID
        
        Args:
            node_id: Node identifier
        
        Returns:
            Node dictionary or None if not found
        """
        node = self.nodes.get(node_id)
        return asdict(node) if node else None
    
    def neighbors(self, node_id: str, etypes: Optional[List[EdgeType]] = None, depth: int = 1) -> List[Dict[str, Any]]:
        """
        Find neighbors of a node with depth and type filtering
        
        Args:
            node_id: Starting node ID
            etypes: Optional list of edge types to filter by
            depth: Traversal depth (security limited)
        
        Returns:
            List of neighbor node dictionaries within the traversal horizon
        """
        try:
            # Security: limit depth
            depth = min(max(0, depth), self.MAX_DEPTH)

            if node_id not in self.nodes or depth == 0:
                return []

            visited = set()      # processed nodes
            discovered = set()   # neighbors discovered within depth
            current_level = {node_id}

            for _ in range(depth):
                next_level = set()

                for current_node in current_level:
                    if current_node in visited:
                        continue
                    visited.add(current_node)

                    # Explore incident edges
                    for edge in self.edges.values():
                        # Outgoing neighbor
                        if edge.source == current_node:
                            if etypes is None or edge.type in etypes:
                                if edge.target != node_id:
                                    discovered.add(edge.target)
                                next_level.add(edge.target)
                        # Incoming neighbor
                        elif edge.target == current_node:
                            if etypes is None or edge.type in etypes:
                                if edge.source != node_id:
                                    discovered.add(edge.source)
                                next_level.add(edge.source)

                current_level = next_level

                # Security: cap neighbor fan-out
                if len(discovered) >= self.MAX_NEIGHBORS:
                    logger.warning(f"Neighbor search truncated at {self.MAX_NEIGHBORS} nodes")
                    break

            # Materialize discovered neighbors
            neighbors: List[Dict[str, Any]] = []
            for neighbor_id in discovered:
                node = self.nodes.get(neighbor_id)
                if node:
                    neighbors.append(asdict(node))

            return neighbors

        except Exception as e:
            logger.error(f"Error finding neighbors for {node_id}: {e}")
            return []
    
    def query(self, pattern: str, params: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Parametrized query to prevent injection attacks
        
        Args:
            pattern: Query pattern with parameter placeholders
            params: Parameters for safe substitution
        
        Returns:
            List of result dictionaries
        """
        try:
            # Basic pattern matching for development
            # In production, this would use proper graph query language (Cypher, Gremlin, etc.)
            
            results = []
            
            # Simple pattern: "MATCH (n:NodeType) WHERE n.property = $param"
            if pattern.startswith("MATCH") and "WHERE" in pattern:
                # Extract node type and property filters
                # This is a simplified implementation - real graph DB would handle complex queries
                
                # Example: Find all Procedure nodes
                if "n:Procedure" in pattern:
                    for node in self.nodes.values():
                        if node.type == "Procedure":
                            # Apply parameter filters
                            match = True
                            for param_key, param_value in params.items():
                                if param_key in node.properties:
                                    if node.properties[param_key] != param_value:
                                        match = False
                                        break
                            
                            if match:
                                results.append(asdict(node))
            
            return results[:100]  # Limit results for security
            
        except Exception as e:
            logger.error(f"Error executing query: {e}")
            return []
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get graph statistics"""
        node_types = {}
        edge_types = {}
        
        for node in self.nodes.values():
            node_types[node.type] = node_types.get(node.type, 0) + 1
        
        for edge in self.edges.values():
            edge_types[edge.type] = edge_types.get(edge.type, 0) + 1
        
        return {
            "total_nodes": len(self.nodes),
            "total_edges": len(self.edges),
            "node_types": node_types,
            "edge_types": edge_types,
            "storage_path": str(self.storage_path),
            "write_ahead_log_entries": len(self.write_ahead_log)
        }
    
    def _sanitize_properties(self, properties: Dict[str, Any]) -> Dict[str, Any]:
        """Remove or redact PII from properties"""
        sanitized = {}
        
        # PII patterns to redact
        pii_patterns = ['email', 'phone', 'ssn', 'password', 'token', 'key']
        
        for key, value in properties.items():
            key_lower = key.lower()
            
            # Check if key indicates PII
            if any(pattern in key_lower for pattern in pii_patterns):
                sanitized[key] = "***REDACTED***"
            else:
                # Sanitize string values
                if isinstance(value, str) and len(value) > 1000:
                    # Truncate very long strings
                    sanitized[key] = value[:1000] + "..."
                else:
                    sanitized[key] = value
        
        return sanitized
    
    def _log_operation(self, operation: str, data: Dict[str, Any]):
        """Write-ahead logging for operations"""
        log_entry = {
            "id": str(uuid.uuid4()),
            "operation": operation,
            "data": data,
            "timestamp": time.time()
        }
        self.write_ahead_log.append(log_entry)
    
    def _save_to_storage(self):
        """Persist graph data to storage"""
        try:
            # Save nodes
            nodes_file = self.storage_path / "nodes.json"
            with open(nodes_file, 'w', encoding='utf-8') as f:
                nodes_data = {nid: asdict(node) for nid, node in self.nodes.items()}
                json.dump(nodes_data, f, indent=2)
            
            # Save edges
            edges_file = self.storage_path / "edges.json"
            with open(edges_file, 'w', encoding='utf-8') as f:
                edges_data = {eid: asdict(edge) for eid, edge in self.edges.items()}
                json.dump(edges_data, f, indent=2)
            
            # Save write-ahead log
            log_file = self.storage_path / "write_ahead_log.json"
            with open(log_file, 'w', encoding='utf-8') as f:
                json.dump(self.write_ahead_log, f, indent=2)
            
        except Exception as e:
            logger.error(f"Error saving graph data: {e}")
    
    def _load_from_storage(self):
        """Load graph data from storage"""
        try:
            # Load nodes
            nodes_file = self.storage_path / "nodes.json"
            if nodes_file.exists():
                with open(nodes_file, 'r', encoding='utf-8') as f:
                    nodes_data = json.load(f)
                    for nid, node_dict in nodes_data.items():
                        self.nodes[nid] = GraphNode(**node_dict)
            
            # Load edges
            edges_file = self.storage_path / "edges.json"
            if edges_file.exists():
                with open(edges_file, 'r', encoding='utf-8') as f:
                    edges_data = json.load(f)
                    for eid, edge_dict in edges_data.items():
                        self.edges[eid] = GraphEdge(**edge_dict)
            
            # Load write-ahead log
            log_file = self.storage_path / "write_ahead_log.json"
            if log_file.exists():
                with open(log_file, 'r', encoding='utf-8') as f:
                    self.write_ahead_log = json.load(f)
            
        except Exception as e:
            logger.warning(f"Could not load existing graph data: {e}")
