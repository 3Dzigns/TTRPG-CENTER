# tests/unit/test_graph_store.py
"""
Unit tests for Graph Store - Phase 3
Tests node/edge operations, neighbors, and parameter queries
"""

import pytest
import tempfile
from pathlib import Path

from src_common.graph.store import GraphStore, GraphNode, GraphEdge, GraphStoreError

class TestGraphStore:
    """Test GraphStore CRUD operations and security features"""
    
    @pytest.fixture
    def temp_store(self):
        """Create temporary graph store for testing"""
        with tempfile.TemporaryDirectory() as temp_dir:
            storage_path = Path(temp_dir) / "test_graph"
            store = GraphStore(storage_path=storage_path)
            yield store
    
    def test_upsert_node_create(self, temp_store):
        """Test creating new node"""
        result = temp_store.upsert_node(
            "test:node:1", 
            "Concept", 
            {"name": "Test Concept", "description": "A test concept"}
        )
        
        assert result["id"] == "test:node:1"
        assert result["type"] == "Concept"
        assert result["properties"]["name"] == "Test Concept"
        assert result["version"] == 1
        
        # Verify node is stored
        retrieved = temp_store.get_node("test:node:1")
        assert retrieved is not None
        assert retrieved["id"] == "test:node:1"
    
    def test_upsert_node_update(self, temp_store):
        """Test updating existing node"""
        # Create initial node
        temp_store.upsert_node("test:node:1", "Concept", {"name": "Original", "value": 1})
        
        # Update node
        result = temp_store.upsert_node("test:node:1", "Concept", {"name": "Updated", "value": 2})
        
        assert result["version"] == 2
        assert result["properties"]["name"] == "Updated"
        assert result["properties"]["value"] == 2
    
    def test_upsert_edge_create(self, temp_store):
        """Test creating edge between nodes"""
        # Create nodes first
        temp_store.upsert_node("node:a", "Concept", {"name": "Node A"})
        temp_store.upsert_node("node:b", "Concept", {"name": "Node B"})
        
        # Create edge
        result = temp_store.upsert_edge("node:a", "depends_on", "node:b", {"strength": 0.8})
        
        assert result["source"] == "node:a"
        assert result["type"] == "depends_on"
        assert result["target"] == "node:b"
        assert result["properties"]["strength"] == 0.8
        assert result["version"] == 1
    
    def test_upsert_edge_invalid_nodes(self, temp_store):
        """Test edge creation with non-existent nodes"""
        with pytest.raises(GraphStoreError, match="Source node .* does not exist"):
            temp_store.upsert_edge("nonexistent", "depends_on", "also_nonexistent", {})
    
    def test_invalid_node_type(self, temp_store):
        """Test rejection of invalid node types"""
        with pytest.raises(GraphStoreError, match="Invalid node type"):
            temp_store.upsert_node("test:node", "InvalidType", {})
    
    def test_invalid_edge_type(self, temp_store):
        """Test rejection of invalid edge types"""
        temp_store.upsert_node("node:a", "Concept", {})
        temp_store.upsert_node("node:b", "Concept", {})
        
        with pytest.raises(GraphStoreError, match="Invalid edge type"):
            temp_store.upsert_edge("node:a", "invalid_edge", "node:b", {})
    
    def test_neighbors_depth_limit(self, temp_store):
        """Test neighbor search respects depth limits"""
        # Create chain: A -> B -> C -> D
        temp_store.upsert_node("node:a", "Concept", {"name": "A"})
        temp_store.upsert_node("node:b", "Concept", {"name": "B"})
        temp_store.upsert_node("node:c", "Concept", {"name": "C"})
        temp_store.upsert_node("node:d", "Concept", {"name": "D"})
        
        temp_store.upsert_edge("node:a", "depends_on", "node:b", {})
        temp_store.upsert_edge("node:b", "depends_on", "node:c", {})
        temp_store.upsert_edge("node:c", "depends_on", "node:d", {})
        
        # Test depth limits
        neighbors_1 = temp_store.neighbors("node:a", depth=1)
        neighbors_2 = temp_store.neighbors("node:a", depth=2)
        neighbors_3 = temp_store.neighbors("node:a", depth=3)
        
        assert len(neighbors_1) == 1  # Only B
        assert len(neighbors_2) == 2  # B and C
        assert len(neighbors_3) == 3  # B, C, and D
    
    def test_neighbors_edge_type_filter(self, temp_store):
        """Test neighbor search with edge type filtering"""
        temp_store.upsert_node("node:a", "Concept", {"name": "A"})
        temp_store.upsert_node("node:b", "Concept", {"name": "B"})
        temp_store.upsert_node("node:c", "Concept", {"name": "C"})
        
        temp_store.upsert_edge("node:a", "depends_on", "node:b", {})
        temp_store.upsert_edge("node:a", "part_of", "node:c", {})
        
        # Filter by edge type
        depends_neighbors = temp_store.neighbors("node:a", etypes=["depends_on"])
        part_neighbors = temp_store.neighbors("node:a", etypes=["part_of"])
        all_neighbors = temp_store.neighbors("node:a")
        
        assert len(depends_neighbors) == 1
        assert len(part_neighbors) == 1  
        assert len(all_neighbors) == 2
    
    def test_pii_sanitization(self, temp_store):
        """Test PII redaction in node properties"""
        result = temp_store.upsert_node(
            "test:node:pii",
            "Entity",
            {
                "name": "Test User",
                "email": "user@example.com",
                "password": "secret123",
                "description": "Regular description"
            }
        )
        
        assert result["properties"]["name"] == "Test User"
        assert result["properties"]["email"] == "***REDACTED***"
        assert result["properties"]["password"] == "***REDACTED***"
        assert result["properties"]["description"] == "Regular description"
    
    def test_query_basic_pattern(self, temp_store):
        """Test basic pattern matching queries"""
        # Create test nodes
        temp_store.upsert_node("proc:1", "Procedure", {"name": "Craft Potion", "type": "crafting"})
        temp_store.upsert_node("proc:2", "Procedure", {"name": "Cast Spell", "type": "magic"})
        temp_store.upsert_node("rule:1", "Rule", {"text": "DC 15 check required"})
        
        # Query for procedures
        procedures = temp_store.query("MATCH (n:Procedure) WHERE n.property = $param", {})
        
        assert len(procedures) == 2
        assert all(p["type"] == "Procedure" for p in procedures)
    
    def test_statistics(self, temp_store):
        """Test graph statistics reporting"""
        # Add various nodes and edges
        temp_store.upsert_node("n1", "Concept", {"name": "C1"})
        temp_store.upsert_node("n2", "Rule", {"text": "R1"})
        temp_store.upsert_node("n3", "Procedure", {"name": "P1"})
        
        temp_store.upsert_edge("n1", "depends_on", "n2", {})
        temp_store.upsert_edge("n3", "part_of", "n1", {})
        
        stats = temp_store.get_statistics()
        
        assert stats["total_nodes"] == 3
        assert stats["total_edges"] == 2
        assert stats["node_types"]["Concept"] == 1
        assert stats["node_types"]["Rule"] == 1
        assert stats["node_types"]["Procedure"] == 1
        assert stats["edge_types"]["depends_on"] == 1
        assert stats["edge_types"]["part_of"] == 1
    
    def test_persistence(self, temp_store):
        """Test data persistence and loading"""
        # Add data
        temp_store.upsert_node("persistent:1", "Concept", {"name": "Persistent"})
        temp_store.upsert_node("persistent:2", "Rule", {"text": "Test rule"})
        temp_store.upsert_edge("persistent:1", "cites", "persistent:2", {"confidence": 0.9})
        
        # Create new store with same storage path
        new_store = GraphStore(storage_path=temp_store.storage_path)
        
        # Verify data loaded
        assert new_store.get_node("persistent:1") is not None
        assert new_store.get_node("persistent:2") is not None
        assert len(new_store.edges) == 1
        
        stats = new_store.get_statistics()
        assert stats["total_nodes"] == 2
        assert stats["total_edges"] == 1