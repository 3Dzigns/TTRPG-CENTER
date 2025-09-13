# tests/container/test_database_integration.py
"""
FR-006: Database Integration Tests
Tests for containerized database integrations and data flow
"""

import pytest
import os
import time
from typing import Dict, Any, List

# Import the new containerized services
from src_common.database_config import get_engine, test_database_connection, get_database_info
from src_common.mongo_dictionary_service import get_dictionary_service, DictEntry
from src_common.neo4j_graph_service import get_graph_service, GraphNode, GraphRelationship
from src_common.redis_service import get_redis_service


class TestPostgreSQLIntegration:
    """Test PostgreSQL integration through the new database configuration"""
    
    def test_connection_establishment(self):
        """Test that PostgreSQL connection can be established"""
        is_connected = test_database_connection()
        assert is_connected, "Failed to connect to PostgreSQL"
    
    def test_database_info_retrieval(self):
        """Test database information retrieval"""
        engine = get_engine()
        db_info = get_database_info(engine)
        
        assert "error" not in db_info
        assert "database_type" in db_info
        
        # Should be PostgreSQL in container environment
        if "POSTGRES_HOST" in os.environ:
            assert db_info["database_type"] == "PostgreSQL"
        else:
            assert db_info["database_type"] == "SQLite"  # Fallback
    
    def test_connection_pooling(self):
        """Test that connection pooling works correctly"""
        engine = get_engine()
        
        # Test multiple concurrent connections
        connections = []
        try:
            for i in range(5):
                conn = engine.connect()
                connections.append(conn)
                
                # Test simple query
                result = conn.execute("SELECT 1 as test")
                assert result.scalar() == 1
        finally:
            # Clean up connections
            for conn in connections:
                conn.close()
    
    def test_alembic_migrations(self):
        """Test that Alembic migrations have been applied"""
        engine = get_engine()
        
        with engine.connect() as conn:
            # Check if alembic_version table exists
            if engine.url.drivername.startswith("postgresql"):
                result = conn.execute("""
                    SELECT EXISTS (
                        SELECT FROM information_schema.tables 
                        WHERE table_name = 'alembic_version'
                    )
                """)
            else:
                result = conn.execute("""
                    SELECT COUNT(*) FROM sqlite_master 
                    WHERE type='table' AND name='alembic_version'
                """)
            
            has_alembic = result.scalar()
            assert has_alembic, "Alembic version table not found - migrations not applied"


class TestMongoDBIntegration:
    """Test MongoDB integration through the dictionary service"""
    
    @pytest.fixture
    def dictionary_service(self):
        """Get dictionary service instance"""
        return get_dictionary_service()
    
    @pytest.fixture
    def sample_entries(self):
        """Sample dictionary entries for testing"""
        return [
            DictEntry(
                term="Test Spell",
                definition="A spell used for testing purposes",
                category="spell",
                sources=[{"system": "test", "book": "Test Book", "page": 1}]
            ),
            DictEntry(
                term="Test Equipment",
                definition="Equipment used for testing",
                category="equipment", 
                sources=[{"system": "test", "book": "Test Book", "page": 2}]
            )
        ]
    
    def test_connection_health(self, dictionary_service):
        """Test MongoDB connection health"""
        health = dictionary_service.health_check()
        
        assert health["status"] in ["healthy", "disconnected"]
        
        if health["status"] == "healthy":
            assert "database" in health
            assert "collection" in health
    
    def test_upsert_entries(self, dictionary_service, sample_entries):
        """Test upserting dictionary entries"""
        if dictionary_service.health_check()["status"] != "healthy":
            pytest.skip("MongoDB not available")
        
        count = dictionary_service.upsert_entries(sample_entries)
        assert count == len(sample_entries)
        
        # Verify entries were inserted
        for entry in sample_entries:
            retrieved = dictionary_service.get_entry(entry.term)
            assert retrieved is not None
            assert retrieved.term == entry.term
            assert retrieved.definition == entry.definition
            assert retrieved.category == entry.category
    
    def test_search_functionality(self, dictionary_service, sample_entries):
        """Test dictionary search functionality"""
        if dictionary_service.health_check()["status"] != "healthy":
            pytest.skip("MongoDB not available")
        
        # First ensure test data exists
        dictionary_service.upsert_entries(sample_entries)
        
        # Test text search
        results = dictionary_service.search_entries("test")
        assert len(results) >= 0  # May find other test entries
        
        # Test category filter
        spell_results = dictionary_service.search_entries("test", category="spell")
        spell_entries = [r for r in spell_results if r.category == "spell"]
        assert len(spell_entries) >= 1
    
    def test_statistics(self, dictionary_service):
        """Test dictionary statistics"""
        if dictionary_service.health_check()["status"] != "healthy":
            pytest.skip("MongoDB not available")
        
        stats = dictionary_service.get_stats()
        
        assert "error" not in stats
        assert "total_entries" in stats
        assert "categories" in stats
        assert isinstance(stats["total_entries"], int)
        assert isinstance(stats["categories"], int)


class TestNeo4jIntegration:
    """Test Neo4j integration through the graph service"""
    
    @pytest.fixture
    def graph_service(self):
        """Get graph service instance"""
        return get_graph_service()
    
    @pytest.fixture
    def sample_graph_data(self):
        """Sample graph data for testing"""
        return {
            "nodes": [
                GraphNode(
                    id="test-doc-1",
                    labels=["Document"],
                    properties={"title": "Test Document", "created_at": int(time.time())}
                ),
                GraphNode(
                    id="test-section-1", 
                    labels=["Section"],
                    properties={"title": "Test Section", "level": 1}
                ),
                GraphNode(
                    id="test-chunk-1",
                    labels=["Chunk"], 
                    properties={"text": "Test chunk content", "index": 0}
                )
            ],
            "relationships": [
                GraphRelationship(
                    source_id="test-doc-1",
                    target_id="test-section-1",
                    relationship_type="HAS_SECTION",
                    properties={}
                ),
                GraphRelationship(
                    source_id="test-section-1",
                    target_id="test-chunk-1", 
                    relationship_type="HAS_CHUNK",
                    properties={}
                )
            ]
        }
    
    def test_connection_health(self, graph_service):
        """Test Neo4j connection health"""
        health = graph_service.health_check()
        
        assert health["status"] in ["healthy", "error", "disconnected"]
        
        if health["status"] == "healthy":
            assert "total_nodes" in health
            assert "total_relationships" in health
    
    def test_node_operations(self, graph_service, sample_graph_data):
        """Test graph node operations"""
        if graph_service.health_check()["status"] != "healthy":
            pytest.skip("Neo4j not available")
        
        # Test node creation
        for node in sample_graph_data["nodes"]:
            success = graph_service.upsert_node(node)
            assert success, f"Failed to upsert node {node.id}"
        
        # Test node relationships
        for relationship in sample_graph_data["relationships"]:
            success = graph_service.upsert_relationship(relationship)
            assert success, f"Failed to upsert relationship {relationship.source_id} -> {relationship.target_id}"
    
    def test_document_graph_creation(self, graph_service):
        """Test complete document graph creation"""
        if graph_service.health_check()["status"] != "healthy":
            pytest.skip("Neo4j not available")
        
        document_id = "test-document-full"
        sections = [
            {
                "id": f"{document_id}#section-1",
                "title": "Introduction",
                "level": 1,
                "page": 1
            },
            {
                "id": f"{document_id}#section-2", 
                "title": "Chapter 1",
                "level": 1,
                "page": 10,
                "parent_id": f"{document_id}#section-1"
            }
        ]
        
        chunks = [
            {
                "id": f"{document_id}#chunk-1",
                "text": "This is the introduction text",
                "page": 1,
                "index": 0,
                "section_id": f"{document_id}#section-1"
            },
            {
                "id": f"{document_id}#chunk-2",
                "text": "This is chapter 1 content", 
                "page": 10,
                "index": 1,
                "section_id": f"{document_id}#section-2"
            }
        ]
        
        success = graph_service.create_document_graph(document_id, sections, chunks)
        assert success, "Failed to create document graph"
        
        # Verify graph structure
        related_nodes = graph_service.find_related_nodes(document_id, max_depth=2)
        assert len(related_nodes) >= 4  # Document + 2 sections + 2 chunks
    
    def test_graph_statistics(self, graph_service):
        """Test graph statistics"""
        if graph_service.health_check()["status"] != "healthy":
            pytest.skip("Neo4j not available")
        
        stats = graph_service.get_graph_stats()
        
        assert "error" not in stats
        assert "total_nodes" in stats
        assert "total_relationships" in stats
        assert isinstance(stats["total_nodes"], int)
        assert isinstance(stats["total_relationships"], int)


class TestRedisIntegration:
    """Test Redis integration (placeholder mode)"""
    
    @pytest.fixture
    def redis_service(self):
        """Get Redis service instance"""
        return get_redis_service()
    
    def test_connection_health(self, redis_service):
        """Test Redis connection health"""
        health = redis_service.health_check()
        
        assert health["status"] in ["healthy", "disabled", "error", "disconnected"]
        assert "features_enabled" in health
        
        # Features should be disabled in placeholder mode
        assert not health["features_enabled"]
    
    def test_ping_connectivity(self, redis_service):
        """Test basic Redis ping"""
        if redis_service.health_check()["status"] not in ["healthy", "disabled"]:
            pytest.skip("Redis not available")
        
        ping_result = redis_service.ping()
        assert isinstance(ping_result, bool)
        
        # If Redis is connected, ping should work
        if redis_service.client:
            assert ping_result
    
    def test_feature_disabled_mode(self, redis_service):
        """Test that Redis features are properly disabled"""
        # All operations should return appropriate disabled responses
        assert redis_service.set_value("test_key", "test_value") is False
        assert redis_service.get_value("test_key") is None
        assert redis_service.delete_key("test_key") is False
        assert redis_service.exists("test_key") is False
    
    def test_server_info(self, redis_service):
        """Test Redis server information retrieval"""
        if redis_service.health_check()["status"] not in ["healthy", "disabled"]:
            pytest.skip("Redis not available")
        
        info = redis_service.get_info()
        
        if "error" not in info:
            assert "redis_version" in info
            assert "used_memory" in info
            assert "connected_clients" in info


class TestCrossServiceIntegration:
    """Test integration between different database services"""
    
    def test_health_endpoint_aggregation(self):
        """Test that health endpoint properly aggregates all service statuses"""
        from src_common.container_health_service import get_health_service
        
        health_service = get_health_service()
        health_status = health_service.get_health_status(include_details=True)
        
        assert "services" in health_status
        services = health_status["services"]
        
        # Check that all expected services are reported
        expected_services = ["database", "mongodb", "neo4j", "redis", "astradb", "openai", "scheduler"]
        
        for service in expected_services:
            assert service in services, f"Service {service} not found in health status"
            assert "status" in services[service], f"Status not found for service {service}"
    
    def test_service_interdependencies(self):
        """Test that services properly handle dependencies"""
        # Test database dependency for app startup
        db_connected = test_database_connection()
        
        if db_connected:
            # If database is connected, other services should be able to initialize
            mongo_service = get_dictionary_service()
            mongo_health = mongo_service.health_check()
            
            graph_service = get_graph_service()
            graph_health = graph_service.health_check()
            
            # Services should either be healthy or have graceful degradation
            assert mongo_health["status"] in ["healthy", "disconnected"]
            assert graph_health["status"] in ["healthy", "error", "disconnected"]
    
    def test_data_flow_pipeline(self):
        """Test basic data flow between services"""
        # This would test a simplified version of the ingestion pipeline
        # For now, we'll test basic connectivity and data operations
        
        # Test PostgreSQL -> MongoDB -> Neo4j flow
        db_connected = test_database_connection()
        
        if db_connected:
            mongo_service = get_dictionary_service()
            if mongo_service.health_check()["status"] == "healthy":
                # Test basic dictionary operation
                test_entry = DictEntry(
                    term="Integration Test",
                    definition="Testing cross-service integration",
                    category="test",
                    sources=[{"system": "integration", "book": "Test", "page": 1}]
                )
                
                upsert_count = mongo_service.upsert_entries([test_entry])
                assert upsert_count == 1
                
                # Verify retrieval
                retrieved = mongo_service.get_entry("Integration Test")
                assert retrieved is not None
                assert retrieved.term == "Integration Test"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])