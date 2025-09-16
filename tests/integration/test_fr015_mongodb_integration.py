# tests/integration/test_fr015_mongodb_integration.py
"""
Integration tests for FR-015 MongoDB Dictionary Backend
Validates AC1: All reads backed by MongoDB queries
"""

import pytest
import asyncio
import time
from typing import Dict, Any

from src_common.admin.dictionary import AdminDictionaryService
from src_common.mongo_dictionary_service import MongoDictionaryService, DictEntry


class TestFR015MongoDBIntegration:
    """Integration tests for MongoDB dictionary backend"""

    @pytest.fixture
    def mongo_service(self):
        """Create MongoDB service for testing"""
        service = MongoDictionaryService(env="test")
        # Verify MongoDB is available for integration tests
        health = service.health_check()
        if health.get("status") != "healthy":
            pytest.skip("MongoDB not available for integration testing")
        return service

    @pytest.fixture
    def admin_service(self):
        """Create AdminDictionaryService with MongoDB enabled"""
        return AdminDictionaryService(use_mongodb=True)

    @pytest.fixture
    async def sample_mongodb_data(self, mongo_service):
        """Create sample data directly in MongoDB for testing"""
        test_entries = [
            DictEntry(
                term="Fireball",
                definition="A bright streak flashes from your pointing finger to a point you choose within range and then blossoms with a low roar into an explosion of flame.",
                category="spell",
                sources=[{
                    "system": "Player Handbook",
                    "page_reference": "p.241",
                    "confidence": 0.95,
                    "extraction_method": "manual_entry"
                }]
            ),
            DictEntry(
                term="Armor Class",
                definition="Armor Class (AC) represents how well your character avoids being wounded in battle.",
                category="rule",
                sources=[{
                    "system": "Player Handbook",
                    "page_reference": "p.14",
                    "confidence": 0.98,
                    "extraction_method": "manual_entry"
                }]
            ),
            DictEntry(
                term="Dragon",
                definition="Large magical creatures known for their intelligence, power, and hoarding of treasure.",
                category="entity",
                sources=[{
                    "system": "Monster Manual",
                    "page_reference": "p.86",
                    "confidence": 0.92,
                    "extraction_method": "manual_entry"
                }]
            )
        ]

        # Insert test data
        result = mongo_service.upsert_entries(test_entries)
        assert result == 3, "Failed to insert test data"

        yield test_entries

        # Cleanup
        for entry in test_entries:
            mongo_service.delete_entry(entry.term)

    @pytest.mark.asyncio
    async def test_ac1_all_reads_from_mongodb(self, admin_service, sample_mongodb_data, mongo_service):
        """
        Test AC1: All reads backed by MongoDB queries
        Verify that read operations go through MongoDB when available
        """
        # Test 1: list_terms should query MongoDB
        start_time = time.time()
        terms = await admin_service.list_terms("test", limit=10)
        query_time = time.time() - start_time

        # Should find our test data
        term_names = [term.term for term in terms]
        assert "Fireball" in term_names, "Should find MongoDB data via list_terms"
        assert "Armor Class" in term_names, "Should find MongoDB data via list_terms"

        # Should be reasonably fast (MongoDB indexed query)
        assert query_time <= 1.0, f"MongoDB list query took {query_time:.3f}s, should be fast"

        # Test 2: get_term should query MongoDB
        fireball_term = await admin_service.get_term("test", "Fireball")
        assert fireball_term is not None, "Should retrieve term from MongoDB"
        assert fireball_term.term == "Fireball"
        assert "explosion of flame" in fireball_term.definition

        # Test 3: search_terms should query MongoDB
        search_results = await admin_service.search_terms("test", "flame")
        search_term_names = [term.term for term in search_results]
        assert "Fireball" in search_term_names, "Should find MongoDB data via search"

        # Test 4: get_environment_stats should query MongoDB
        stats = await admin_service.get_environment_stats("test")
        assert stats.total_terms >= 3, "Should count MongoDB entries in stats"
        assert "spell" in stats.categories, "Should include MongoDB categories"
        assert stats.categories["spell"] >= 1, "Should count spell category from MongoDB"

    @pytest.mark.asyncio
    async def test_mongodb_data_consistency(self, admin_service, sample_mongodb_data):
        """Test data consistency between MongoDB and AdminDictionaryService"""
        # Get term via AdminDictionaryService
        admin_term = await admin_service.get_term("test", "Dragon")
        assert admin_term is not None

        # Verify data matches MongoDB source
        assert admin_term.term == "Dragon"
        assert admin_term.category == "entity"
        assert "magical creatures" in admin_term.definition
        assert admin_term.source == "Monster Manual"

    @pytest.mark.asyncio
    async def test_mongodb_create_update_delete_cycle(self, admin_service, mongo_service):
        """Test full CRUD cycle through AdminDictionaryService using MongoDB"""
        term_data = {
            "term": "Test Integration Term",
            "definition": "A term created for integration testing",
            "category": "test",
            "source": "Integration Test Suite",
            "page_reference": "p.1",
            "tags": ["test", "integration"]
        }

        try:
            # Create term
            created_term = await admin_service.create_term("test", term_data)
            assert created_term.term == "Test Integration Term"

            # Verify it exists in MongoDB directly
            mongo_entry = mongo_service.get_entry("Test Integration Term")
            assert mongo_entry is not None
            assert mongo_entry.term == "Test Integration Term"

            # Update term
            updates = {"definition": "Updated definition for integration testing"}
            updated_term = await admin_service.update_term(
                "test", "Test Integration Term", updates
            )
            assert updated_term.definition == "Updated definition for integration testing"

            # Verify update in MongoDB
            mongo_entry_updated = mongo_service.get_entry("Test Integration Term")
            assert "Updated definition" in mongo_entry_updated.definition

            # Delete term
            success = await admin_service.delete_term("test", "Test Integration Term")
            assert success

            # Verify deletion in MongoDB
            mongo_entry_deleted = mongo_service.get_entry("Test Integration Term")
            assert mongo_entry_deleted is None

        finally:
            # Cleanup in case of test failure
            try:
                mongo_service.delete_entry("Test Integration Term")
            except:
                pass

    @pytest.mark.asyncio
    async def test_mongodb_search_indexing(self, admin_service, sample_mongodb_data):
        """Test MongoDB search indexing and full-text search capabilities"""
        # Test various search patterns
        search_tests = [
            ("flame", ["Fireball"]),  # Word in definition
            ("Armor", ["Armor Class"]),  # Word in term
            ("Class", ["Armor Class"]),  # Partial term match
            ("magical", ["Dragon"]),  # Word in definition
            ("spell", ["Fireball"]),  # Category-based search
            ("Player Handbook", ["Fireball", "Armor Class"])  # Source-based search
        ]

        for search_query, expected_terms in search_tests:
            start_time = time.time()
            results = await admin_service.search_terms("test", search_query)
            search_time = time.time() - start_time

            result_terms = [term.term for term in results]

            for expected_term in expected_terms:
                assert expected_term in result_terms, (
                    f"Search '{search_query}' should find '{expected_term}'. "
                    f"Found: {result_terms}"
                )

            # Performance check - should be fast with indexing
            assert search_time <= 1.5, (
                f"Search '{search_query}' took {search_time:.3f}s, "
                f"should be ≤1.5s (AC2)"
            )

    @pytest.mark.asyncio
    async def test_mongodb_category_filtering(self, admin_service, sample_mongodb_data):
        """Test MongoDB category filtering functionality"""
        # Test category filters
        category_tests = [
            ("spell", ["Fireball"]),
            ("rule", ["Armor Class"]),
            ("entity", ["Dragon"])
        ]

        for category, expected_terms in category_tests:
            terms = await admin_service.list_terms("test", category=category, limit=100)
            result_terms = [term.term for term in terms]

            for expected_term in expected_terms:
                assert expected_term in result_terms, (
                    f"Category '{category}' should include '{expected_term}'"
                )

            # Verify all results match the category
            for term in terms:
                assert term.category == category, (
                    f"All results should match category '{category}'"
                )

    @pytest.mark.asyncio
    async def test_mongodb_stats_calculation(self, admin_service, sample_mongodb_data):
        """Test MongoDB-based statistics calculation"""
        stats = await admin_service.get_environment_stats("test")

        # Should include our test data
        assert stats.total_terms >= 3
        assert stats.environment == "test"

        # Should have category breakdown
        expected_categories = {"spell": 1, "rule": 1, "entity": 1}
        for category, min_count in expected_categories.items():
            assert category in stats.categories, f"Should have category '{category}'"
            assert stats.categories[category] >= min_count, (
                f"Category '{category}' should have at least {min_count} terms"
            )

        # Should have source breakdown
        assert len(stats.sources) > 0, "Should have source information"

    @pytest.mark.asyncio
    async def test_mongodb_bulk_operations(self, admin_service, mongo_service):
        """Test bulk operations using MongoDB backend"""
        bulk_data = [
            {
                "term": f"Bulk Term {i}",
                "definition": f"Definition for bulk term {i}",
                "category": "test",
                "source": "Bulk Test"
            }
            for i in range(10)
        ]

        try:
            # Bulk import
            results = await admin_service.bulk_import("test", bulk_data)

            assert results["total"] == 10
            assert results["created"] == 10
            assert results["failed"] == 0

            # Verify in MongoDB
            for i in range(10):
                term_name = f"Bulk Term {i}"
                mongo_entry = mongo_service.get_entry(term_name)
                assert mongo_entry is not None, f"Bulk term {i} should exist in MongoDB"

            # Test bulk retrieval
            terms = await admin_service.list_terms("test", category="test", limit=20)
            bulk_terms = [term for term in terms if term.term.startswith("Bulk Term")]
            assert len(bulk_terms) == 10, "Should retrieve all bulk terms"

        finally:
            # Cleanup
            for i in range(10):
                try:
                    mongo_service.delete_entry(f"Bulk Term {i}")
                except:
                    pass

    @pytest.mark.asyncio
    async def test_mongodb_concurrent_operations(self, admin_service, mongo_service):
        """Test concurrent MongoDB operations"""
        async def create_and_search(index: int):
            term_data = {
                "term": f"Concurrent Term {index}",
                "definition": f"Definition for concurrent term {index}",
                "category": "concurrent_test",
                "source": "Concurrent Test"
            }

            # Create term
            await admin_service.create_term("test", term_data)

            # Search for it
            results = await admin_service.search_terms("test", f"Concurrent Term {index}")
            return len(results) > 0

        try:
            # Run 5 concurrent create/search operations
            tasks = [create_and_search(i) for i in range(5)]
            results = await asyncio.gather(*tasks)

            # All operations should succeed
            assert all(results), "All concurrent operations should succeed"

            # Verify all terms exist
            terms = await admin_service.list_terms("test", category="concurrent_test")
            concurrent_terms = [term for term in terms if term.term.startswith("Concurrent Term")]
            assert len(concurrent_terms) == 5, "Should have all concurrent terms"

        finally:
            # Cleanup
            for i in range(5):
                try:
                    mongo_service.delete_entry(f"Concurrent Term {i}")
                except:
                    pass

    def test_mongodb_connection_status(self, mongo_service):
        """Test MongoDB connection and health status"""
        health = mongo_service.health_check()

        assert health["status"] == "healthy", "MongoDB should be healthy for integration tests"
        assert "database" in health, "Health check should include database info"
        assert "collection" in health, "Health check should include collection info"

        # Test stats
        stats = mongo_service.get_stats()
        assert "total_entries" in stats, "Stats should include total entries"
        assert "database" in stats, "Stats should include database name"


if __name__ == "__main__":
    pytest.main([
        __file__,
        "-v",
        "--tb=short"
    ])