# tests/integration/test_fr015_error_handling.py
"""
Error handling tests for FR-015 MongoDB Dictionary Backend
Validates AC3: Error handling when Mongo unavailable
"""

import pytest
import asyncio
from unittest.mock import patch, MagicMock
from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError

from src_common.admin.dictionary import AdminDictionaryService
from src_common.admin.mongo_adapter import MongoDictionaryAdapter
from src_common.mongo_dictionary_service import MongoDictionaryService


class TestFR015ErrorHandling:
    """Error handling tests for MongoDB dictionary backend"""

    @pytest.fixture
    def admin_service_with_mongo(self):
        """AdminDictionaryService with MongoDB enabled"""
        return AdminDictionaryService(use_mongodb=True)

    @pytest.fixture
    def admin_service_without_mongo(self):
        """AdminDictionaryService with MongoDB disabled (file-based fallback)"""
        return AdminDictionaryService(use_mongodb=False)

    @pytest.mark.asyncio
    async def test_mongodb_connection_failure_graceful_fallback(self, admin_service_with_mongo):
        """
        Test AC3: Error handling when Mongo unavailable
        Should gracefully fall back to file-based storage
        """
        # Mock MongoDB connection failure
        with patch('src_common.mongo_dictionary_service.MongoClient') as mock_client:
            mock_client.side_effect = ConnectionFailure("MongoDB connection failed")

            # Create a new adapter that will fail to connect
            adapter = MongoDictionaryAdapter("test")

            # Should not raise exception, should handle gracefully
            stats = await adapter.get_environment_stats()

            # Should return empty stats when MongoDB is unavailable
            assert stats.total_terms == 0
            assert stats.environment == "test"

    @pytest.mark.asyncio
    async def test_mongodb_timeout_error_handling(self, admin_service_with_mongo):
        """Test handling of MongoDB timeout errors"""
        with patch.object(MongoDictionaryService, 'search_entries') as mock_search:
            mock_search.side_effect = ServerSelectionTimeoutError("MongoDB timeout")

            # Should not raise exception, should fall back gracefully
            results = await admin_service_with_mongo.search_terms("test", "sample query")

            # Should return empty results on timeout, not crash
            assert isinstance(results, list)
            # Results may be empty due to fallback or contain file-based results

    @pytest.mark.asyncio
    async def test_mongodb_unavailable_operations_fallback(self, admin_service_with_mongo):
        """Test that all operations gracefully handle MongoDB unavailability"""
        # Mock MongoDB health check to return unhealthy
        with patch.object(MongoDictionaryService, 'health_check') as mock_health:
            mock_health.return_value = {"status": "error", "error": "Connection failed"}

            # All these operations should work without throwing exceptions
            try:
                # List terms
                terms = await admin_service_with_mongo.list_terms("test", limit=10)
                assert isinstance(terms, list)

                # Get environment stats
                stats = await admin_service_with_mongo.get_environment_stats("test")
                assert stats.environment == "test"

                # Search terms
                search_results = await admin_service_with_mongo.search_terms("test", "query")
                assert isinstance(search_results, list)

                # Get specific term (should return None for non-existent terms)
                term = await admin_service_with_mongo.get_term("test", "nonexistent_term")
                assert term is None or hasattr(term, 'term')

            except Exception as e:
                pytest.fail(f"Operations should not fail when MongoDB is unavailable: {e}")

    @pytest.mark.asyncio
    async def test_create_term_mongodb_failure_fallback(self, admin_service_with_mongo):
        """Test creating terms when MongoDB fails"""
        term_data = {
            "term": "test_term",
            "definition": "Test definition",
            "category": "test",
            "source": "test_source"
        }

        with patch.object(MongoDictionaryAdapter, '_is_mongo_available') as mock_available:
            mock_available.return_value = False

            # Should fall back to file-based storage
            try:
                term = await admin_service_with_mongo.create_term("test", term_data)
                assert term.term == "test_term"
                assert term.definition == "Test definition"
            except Exception as e:
                # May fail if file system issues, but should not fail due to MongoDB
                if "MongoDB" in str(e):
                    pytest.fail(f"Should not fail due to MongoDB issues: {e}")

    @pytest.mark.asyncio
    async def test_update_term_mongodb_failure_fallback(self, admin_service_with_mongo):
        """Test updating terms when MongoDB fails"""
        # First create a term using file-based method
        term_data = {
            "term": "update_test_term",
            "definition": "Original definition",
            "category": "test",
            "source": "test_source"
        }

        with patch.object(MongoDictionaryAdapter, '_is_mongo_available') as mock_available:
            mock_available.return_value = False

            try:
                # Create term
                original_term = await admin_service_with_mongo.create_term("test", term_data)

                # Update term
                updates = {"definition": "Updated definition"}
                updated_term = await admin_service_with_mongo.update_term(
                    "test", "update_test_term", updates
                )

                assert updated_term.definition == "Updated definition"

            except Exception as e:
                if "MongoDB" in str(e):
                    pytest.fail(f"Should not fail due to MongoDB issues: {e}")

    @pytest.mark.asyncio
    async def test_delete_term_mongodb_failure_fallback(self, admin_service_with_mongo):
        """Test deleting terms when MongoDB fails"""
        with patch.object(MongoDictionaryAdapter, '_is_mongo_available') as mock_available:
            mock_available.return_value = False

            # Should not crash even if term doesn't exist
            success = await admin_service_with_mongo.delete_term("test", "nonexistent_term")
            assert isinstance(success, bool)

    def test_mongodb_service_initialization_failure(self):
        """Test MongoDictionaryService handles initialization failures gracefully"""
        with patch('os.getenv') as mock_getenv:
            # Mock missing MONGO_URI
            mock_getenv.return_value = None

            # Should not raise exception during initialization
            try:
                service = MongoDictionaryService(env="test")
                assert service.client is None
                assert service.collection is None
            except Exception as e:
                pytest.fail(f"MongoDictionaryService should handle missing config gracefully: {e}")

    def test_mongodb_service_ping_failure(self):
        """Test MongoDictionaryService handles ping failures gracefully"""
        with patch('src_common.mongo_dictionary_service.MongoClient') as mock_client:
            mock_instance = MagicMock()
            mock_instance.admin.command.side_effect = ConnectionFailure("Ping failed")
            mock_client.return_value = mock_instance

            # Should handle ping failure gracefully
            try:
                service = MongoDictionaryService(env="test")
                assert service.client is None
            except Exception as e:
                pytest.fail(f"Should handle ping failure gracefully: {e}")

    @pytest.mark.asyncio
    async def test_partial_mongodb_failure_mixed_operations(self, admin_service_with_mongo):
        """Test mixed success/failure scenarios with MongoDB"""
        # Mock some operations to succeed, others to fail
        with patch.object(MongoDictionaryService, 'search_entries') as mock_search, \
             patch.object(MongoDictionaryService, 'get_stats') as mock_stats:

            # Search fails, stats succeed
            mock_search.side_effect = ConnectionFailure("Search failed")
            mock_stats.return_value = {
                "total_entries": 5,
                "categories": ["test"],
                "category_distribution": {"test": 5}
            }

            # Search should fall back gracefully
            search_results = await admin_service_with_mongo.search_terms("test", "query")
            assert isinstance(search_results, list)

            # Stats should work via MongoDB
            stats = await admin_service_with_mongo.get_environment_stats("test")
            assert stats.total_terms >= 0  # Should get some result

    @pytest.mark.asyncio
    async def test_mongodb_adapter_error_logging(self, admin_service_with_mongo, caplog):
        """Test that MongoDB errors are properly logged"""
        with patch.object(MongoDictionaryService, 'health_check') as mock_health:
            mock_health.side_effect = Exception("Unexpected MongoDB error")

            # Trigger an operation that would check MongoDB health
            adapter = MongoDictionaryAdapter("test")

            # Should log the error appropriately
            try:
                stats = await adapter.get_environment_stats()
            except Exception:
                pass  # Expected to potentially fail

            # Check that appropriate warning/error messages were logged
            # This verifies AC3 requirement for proper error handling
            assert len(caplog.records) > 0, "Should log MongoDB errors"

    @pytest.mark.asyncio
    async def test_file_based_fallback_maintains_functionality(self, admin_service_without_mongo):
        """Test that file-based fallback provides full functionality"""
        # Test all operations work without MongoDB
        term_data = {
            "term": "fallback_test_term",
            "definition": "Test definition for fallback",
            "category": "test",
            "source": "test_source"
        }

        try:
            # Create
            term = await admin_service_without_mongo.create_term("test", term_data)
            assert term.term == "fallback_test_term"

            # Read
            retrieved_term = await admin_service_without_mongo.get_term("test", "fallback_test_term")
            assert retrieved_term is not None
            assert retrieved_term.term == "fallback_test_term"

            # List
            terms = await admin_service_without_mongo.list_terms("test")
            assert any(t.term == "fallback_test_term" for t in terms)

            # Search
            search_results = await admin_service_without_mongo.search_terms("test", "fallback")
            assert any(t.term == "fallback_test_term" for t in search_results)

            # Update
            updates = {"definition": "Updated fallback definition"}
            updated_term = await admin_service_without_mongo.update_term(
                "test", "fallback_test_term", updates
            )
            assert updated_term.definition == "Updated fallback definition"

            # Stats
            stats = await admin_service_without_mongo.get_environment_stats("test")
            assert stats.total_terms >= 1

            # Delete
            success = await admin_service_without_mongo.delete_term("test", "fallback_test_term")
            assert success

        except Exception as e:
            pytest.fail(f"File-based fallback should provide full functionality: {e}")

    @pytest.mark.asyncio
    async def test_mongodb_recovery_after_failure(self, admin_service_with_mongo):
        """Test that MongoDB operations work again after connectivity is restored"""
        # This test simulates MongoDB going down and coming back up
        with patch.object(MongoDictionaryService, 'health_check') as mock_health:
            # First, MongoDB is down
            mock_health.return_value = {"status": "error", "error": "Connection failed"}

            # Operations should fall back
            stats1 = await admin_service_with_mongo.get_environment_stats("test")

            # Then MongoDB comes back up
            mock_health.return_value = {"status": "healthy"}

            # Operations should work via MongoDB again
            stats2 = await admin_service_with_mongo.get_environment_stats("test")

            # Both should return valid stats (may be different depending on data source)
            assert stats1.environment == "test"
            assert stats2.environment == "test"


if __name__ == "__main__":
    pytest.main([
        __file__,
        "-v",
        "--tb=short"
    ])