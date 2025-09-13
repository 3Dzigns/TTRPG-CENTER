# neo4j_graph_service.py
"""
FR-006: Neo4j Graph Service
Provides Neo4j integration for LlamaIndex graph workflows and cross-references
"""

import os
import time
from typing import Any, Dict, List, Optional, Set, Tuple, Union
from dataclasses import dataclass, asdict
from neo4j import GraphDatabase, Driver, Session
from neo4j.exceptions import ServiceUnavailable, AuthError, ConfigurationError
import logging

from .logging import get_logger

logger = get_logger(__name__)


@dataclass
class GraphNode:
    """Graph node data structure"""
    id: str
    labels: List[str]
    properties: Dict[str, Any]
    
    def to_cypher_params(self) -> Dict[str, Any]:
        """Convert to parameters for Cypher query"""
        return {
            "node_id": self.id,
            "labels": self.labels,
            "properties": self.properties
        }


@dataclass
class GraphRelationship:
    """Graph relationship data structure"""
    source_id: str
    target_id: str
    relationship_type: str
    properties: Dict[str, Any]
    
    def to_cypher_params(self) -> Dict[str, Any]:
        """Convert to parameters for Cypher query"""
        return {
            "source_id": self.source_id,
            "target_id": self.target_id,
            "rel_type": self.relationship_type,
            "properties": self.properties
        }


class Neo4jGraphService:
    """Neo4j-based graph service for document structure and cross-references"""
    
    def __init__(self, env: str = "dev"):
        self.env = env
        self.driver: Optional[Driver] = None
        
        # Initialize connection
        self._connect()
        
        # Ensure constraints and indexes
        if self.driver:
            self._ensure_constraints_and_indexes()
    
    def _connect(self) -> None:
        """Establish Neo4j connection"""
        try:
            neo4j_uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
            neo4j_user = os.getenv("NEO4J_USER", "neo4j")
            neo4j_password = os.getenv("NEO4J_PASSWORD", "password")
            
            if not neo4j_uri or not neo4j_user or not neo4j_password:
                logger.warning("Neo4j credentials not configured, graph service disabled")
                return
            
            # Create Neo4j driver
            self.driver = GraphDatabase.driver(
                neo4j_uri,
                auth=(neo4j_user, neo4j_password),
                max_connection_lifetime=3600,  # 1 hour
                max_connection_pool_size=50,
                connection_acquisition_timeout=60
            )
            
            # Test connection
            with self.driver.session() as session:
                result = session.run("RETURN 1 AS test")
                test_value = result.single()["test"]
                if test_value != 1:
                    raise Exception("Connection test failed")
            
            logger.info(f"Neo4j graph service connected: {neo4j_uri}")
            
        except (ServiceUnavailable, AuthError, ConfigurationError) as e:
            logger.error(f"Failed to connect to Neo4j: {e}")
            self.driver = None
        except Exception as e:
            logger.error(f"Unexpected error connecting to Neo4j: {e}")
            self.driver = None
    
    def _ensure_constraints_and_indexes(self) -> None:
        """Create necessary constraints and indexes"""
        if not self.driver:
            return
        
        constraints_and_indexes = [
            # Unique constraints for node IDs
            "CREATE CONSTRAINT document_id_unique IF NOT EXISTS FOR (d:Document) REQUIRE d.id IS UNIQUE",
            "CREATE CONSTRAINT section_id_unique IF NOT EXISTS FOR (s:Section) REQUIRE s.id IS UNIQUE", 
            "CREATE CONSTRAINT chunk_id_unique IF NOT EXISTS FOR (c:Chunk) REQUIRE c.id IS UNIQUE",
            "CREATE CONSTRAINT term_id_unique IF NOT EXISTS FOR (t:Term) REQUIRE t.id IS UNIQUE",
            
            # Indexes for common queries
            "CREATE INDEX document_title_index IF NOT EXISTS FOR (d:Document) ON (d.title)",
            "CREATE INDEX section_title_index IF NOT EXISTS FOR (s:Section) ON (s.title)",
            "CREATE INDEX chunk_content_index IF NOT EXISTS FOR (c:Chunk) ON (c.text)",
            "CREATE INDEX term_name_index IF NOT EXISTS FOR (t:Term) ON (t.name)",
            
            # Full-text indexes for search
            "CREATE FULLTEXT INDEX document_fulltext IF NOT EXISTS FOR (d:Document) ON EACH [d.title, d.content]",
            "CREATE FULLTEXT INDEX chunk_fulltext IF NOT EXISTS FOR (c:Chunk) ON EACH [c.text]"
        ]
        
        try:
            with self.driver.session() as session:
                for query in constraints_and_indexes:
                    try:
                        session.run(query)
                    except Exception as e:
                        # Some constraints/indexes might already exist, which is okay
                        logger.debug(f"Constraint/index creation note: {e}")
                
            logger.info("Neo4j constraints and indexes ensured")
            
        except Exception as e:
            logger.error(f"Failed to create Neo4j constraints and indexes: {e}")
    
    def upsert_node(self, node: GraphNode) -> bool:
        """
        Insert or update a graph node
        
        Args:
            node: GraphNode to upsert
            
        Returns:
            True if successful, False otherwise
        """
        if not self.driver:
            return False
        
        try:
            # Build labels string for Cypher
            labels_str = ":".join(node.labels)
            
            # Cypher query to merge node
            query = f"""
            MERGE (n:{labels_str} {{id: $node_id}})
            SET n += $properties
            SET n.updated_at = timestamp()
            RETURN n.id AS id
            """
            
            with self.driver.session() as session:
                result = session.run(query, node.to_cypher_params())
                record = result.single()
                success = record is not None
                
                if success:
                    logger.debug(f"Upserted node: {node.id}")
                
                return success
                
        except Exception as e:
            logger.error(f"Failed to upsert node '{node.id}': {e}")
            return False
    
    def upsert_relationship(self, relationship: GraphRelationship) -> bool:
        """
        Insert or update a graph relationship
        
        Args:
            relationship: GraphRelationship to upsert
            
        Returns:
            True if successful, False otherwise
        """
        if not self.driver:
            return False
        
        try:
            # Cypher query to merge relationship
            query = f"""
            MATCH (source {{id: $source_id}})
            MATCH (target {{id: $target_id}})
            MERGE (source)-[r:{relationship.relationship_type}]->(target)
            SET r += $properties
            SET r.updated_at = timestamp()
            RETURN r
            """
            
            with self.driver.session() as session:
                result = session.run(query, relationship.to_cypher_params())
                record = result.single()
                success = record is not None
                
                if success:
                    logger.debug(f"Upserted relationship: {relationship.source_id} -> {relationship.target_id}")
                
                return success
                
        except Exception as e:
            logger.error(f"Failed to upsert relationship '{relationship.source_id}' -> '{relationship.target_id}': {e}")
            return False
    
    def create_document_graph(
        self, 
        document_id: str, 
        sections: List[Dict[str, Any]], 
        chunks: List[Dict[str, Any]]
    ) -> bool:
        """
        Create complete document graph structure
        
        Args:
            document_id: Document identifier
            sections: List of section data
            chunks: List of chunk data
            
        Returns:
            True if successful, False otherwise
        """
        if not self.driver:
            return False
        
        try:
            with self.driver.session() as session:
                # Start transaction
                tx = session.begin_transaction()
                
                try:
                    # Create document node
                    doc_query = """
                    MERGE (d:Document {id: $doc_id})
                    SET d.created_at = COALESCE(d.created_at, timestamp())
                    SET d.updated_at = timestamp()
                    RETURN d.id
                    """
                    tx.run(doc_query, {"doc_id": document_id})
                    
                    # Create section nodes and relationships
                    for section in sections:
                        section_id = section.get("id", f"{document_id}#{section.get('title', 'unknown')}")
                        
                        section_query = """
                        MERGE (s:Section {id: $section_id})
                        SET s += $properties
                        SET s.updated_at = timestamp()
                        WITH s
                        MATCH (d:Document {id: $doc_id})
                        MERGE (d)-[:HAS_SECTION]->(s)
                        """
                        
                        tx.run(section_query, {
                            "section_id": section_id,
                            "doc_id": document_id,
                            "properties": {
                                "title": section.get("title", ""),
                                "level": section.get("level", 1),
                                "page": section.get("page", 0)
                            }
                        })
                        
                        # Create parent-child relationships between sections
                        parent_id = section.get("parent_id")
                        if parent_id:
                            parent_query = """
                            MATCH (parent:Section {id: $parent_id})
                            MATCH (child:Section {id: $section_id})
                            MERGE (parent)-[:HAS_SUBSECTION]->(child)
                            """
                            tx.run(parent_query, {
                                "parent_id": parent_id,
                                "section_id": section_id
                            })
                    
                    # Create chunk nodes and relationships
                    for chunk in chunks:
                        chunk_id = chunk.get("id", f"{document_id}#chunk_{chunk.get('index', 0)}")
                        section_id = chunk.get("section_id")
                        
                        chunk_query = """
                        MERGE (c:Chunk {id: $chunk_id})
                        SET c += $properties
                        SET c.updated_at = timestamp()
                        """
                        
                        tx.run(chunk_query, {
                            "chunk_id": chunk_id,
                            "properties": {
                                "text": chunk.get("text", ""),
                                "page": chunk.get("page", 0),
                                "index": chunk.get("index", 0),
                                "tokens": chunk.get("tokens", 0)
                            }
                        })
                        
                        # Link chunk to document
                        doc_chunk_query = """
                        MATCH (d:Document {id: $doc_id})
                        MATCH (c:Chunk {id: $chunk_id})
                        MERGE (d)-[:HAS_CHUNK]->(c)
                        """
                        tx.run(doc_chunk_query, {
                            "doc_id": document_id,
                            "chunk_id": chunk_id
                        })
                        
                        # Link chunk to section if available
                        if section_id:
                            section_chunk_query = """
                            MATCH (s:Section {id: $section_id})
                            MATCH (c:Chunk {id: $chunk_id})
                            MERGE (s)-[:HAS_CHUNK]->(c)
                            """
                            tx.run(section_chunk_query, {
                                "section_id": section_id,
                                "chunk_id": chunk_id
                            })
                    
                    # Commit transaction
                    tx.commit()
                    logger.info(f"Created document graph for: {document_id}")
                    return True
                    
                except Exception as e:
                    tx.rollback()
                    raise e
                    
        except Exception as e:
            logger.error(f"Failed to create document graph for '{document_id}': {e}")
            return False
    
    def find_related_nodes(
        self, 
        node_id: str, 
        relationship_types: Optional[List[str]] = None, 
        max_depth: int = 2
    ) -> List[Dict[str, Any]]:
        """
        Find nodes related to a given node
        
        Args:
            node_id: Starting node ID
            relationship_types: Optional list of relationship types to follow
            max_depth: Maximum traversal depth
            
        Returns:
            List of related node data
        """
        if not self.driver:
            return []
        
        try:
            # Build relationship filter
            rel_filter = ""
            if relationship_types:
                rel_types = "|".join(relationship_types)
                rel_filter = f":{rel_types}"
            
            # Cypher query for related nodes
            query = f"""
            MATCH (start {{id: $node_id}})
            MATCH (start)-[r{rel_filter}*1..{max_depth}]-(related)
            RETURN DISTINCT related, labels(related) as labels
            LIMIT 100
            """
            
            with self.driver.session() as session:
                result = session.run(query, {"node_id": node_id})
                
                related_nodes = []
                for record in result:
                    node = record["related"]
                    labels = record["labels"]
                    
                    node_data = dict(node)
                    node_data["labels"] = labels
                    related_nodes.append(node_data)
                
                return related_nodes
                
        except Exception as e:
            logger.error(f"Failed to find related nodes for '{node_id}': {e}")
            return []
    
    def search_nodes(
        self, 
        query: str, 
        node_labels: Optional[List[str]] = None, 
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """
        Search nodes using full-text search
        
        Args:
            query: Search query
            node_labels: Optional list of node labels to filter
            limit: Maximum number of results
            
        Returns:
            List of matching nodes
        """
        if not self.driver:
            return []
        
        try:
            # Build label filter
            label_filter = ""
            if node_labels:
                labels = "|".join(node_labels)
                label_filter = f":{labels}"
            
            # Use full-text search if available, otherwise use CONTAINS
            search_query = f"""
            CALL db.index.fulltext.queryNodes('document_fulltext', $query)
            YIELD node, score
            WHERE node{label_filter}
            RETURN node, score, labels(node) as labels
            ORDER BY score DESC
            LIMIT {limit}
            """
            
            with self.driver.session() as session:
                try:
                    result = session.run(search_query, {"query": query})
                except Exception:
                    # Fallback to CONTAINS search
                    fallback_query = f"""
                    MATCH (n{label_filter})
                    WHERE n.title CONTAINS $query OR n.text CONTAINS $query OR n.content CONTAINS $query
                    RETURN n as node, 1.0 as score, labels(n) as labels
                    LIMIT {limit}
                    """
                    result = session.run(fallback_query, {"query": query})
                
                nodes = []
                for record in result:
                    node = record["node"]
                    score = record["score"]
                    labels = record["labels"]
                    
                    node_data = dict(node)
                    node_data["labels"] = labels
                    node_data["search_score"] = score
                    nodes.append(node_data)
                
                return nodes
                
        except Exception as e:
            logger.error(f"Failed to search nodes with query '{query}': {e}")
            return []
    
    def get_graph_stats(self) -> Dict[str, Any]:
        """
        Get graph database statistics
        
        Returns:
            Dictionary with graph statistics
        """
        if not self.driver:
            return {"error": "Neo4j not connected"}
        
        try:
            with self.driver.session() as session:
                # Count nodes by label
                node_counts = {}
                labels_result = session.run("CALL db.labels()")
                for record in labels_result:
                    label = record[0]
                    count_result = session.run(f"MATCH (n:{label}) RETURN count(n) as count")
                    count = count_result.single()["count"]
                    node_counts[label] = count
                
                # Count relationships by type
                rel_counts = {}
                rel_types_result = session.run("CALL db.relationshipTypes()")
                for record in rel_types_result:
                    rel_type = record[0]
                    count_result = session.run(f"MATCH ()-[r:{rel_type}]-() RETURN count(r) as count")
                    count = count_result.single()["count"]
                    rel_counts[rel_type] = count
                
                # Total counts
                total_nodes_result = session.run("MATCH (n) RETURN count(n) as count")
                total_nodes = total_nodes_result.single()["count"]
                
                total_rels_result = session.run("MATCH ()-[r]-() RETURN count(r) as count")
                total_relationships = total_rels_result.single()["count"]
                
                return {
                    "total_nodes": total_nodes,
                    "total_relationships": total_relationships,
                    "node_counts_by_label": node_counts,
                    "relationship_counts_by_type": rel_counts
                }
                
        except Exception as e:
            logger.error(f"Failed to get graph stats: {e}")
            return {"error": str(e)}
    
    def health_check(self) -> Dict[str, Any]:
        """
        Check Neo4j connection health
        
        Returns:
            Health status information
        """
        try:
            if not self.driver:
                return {"status": "disconnected", "error": "No Neo4j driver"}
            
            with self.driver.session() as session:
                result = session.run("RETURN 1 AS test")
                test_value = result.single()["test"]
                
                if test_value == 1:
                    # Get basic stats
                    stats = self.get_graph_stats()
                    return {
                        "status": "healthy",
                        "total_nodes": stats.get("total_nodes", 0),
                        "total_relationships": stats.get("total_relationships", 0)
                    }
                else:
                    return {"status": "error", "error": "Connection test failed"}
                    
        except Exception as e:
            return {"status": "error", "error": str(e)}
    
    def close(self) -> None:
        """Close Neo4j connection"""
        if self.driver:
            self.driver.close()
            self.driver = None
            logger.info("Neo4j graph service connection closed")


# Global instance for compatibility with existing code
_neo4j_graph_service: Optional[Neo4jGraphService] = None


def get_graph_service() -> Neo4jGraphService:
    """Get or create the global Neo4j graph service instance"""
    global _neo4j_graph_service
    if _neo4j_graph_service is None:
        env = os.getenv("APP_ENV", "dev")
        _neo4j_graph_service = Neo4jGraphService(env)
    return _neo4j_graph_service


def close_graph_service():
    """Close the global graph service connection"""
    global _neo4j_graph_service
    if _neo4j_graph_service:
        _neo4j_graph_service.close()
        _neo4j_graph_service = None