# tests/performance/test_fr015_dictionary_performance.py
"""
Performance tests for FR-015 MongoDB Dictionary Backend
Validates AC2: Performance: initial search ≤1.5s on 10k records (indexed)
"""

import asyncio
import time
import pytest
from typing import List

from src_common.admin.dictionary import AdminDictionaryService, DictionaryTerm
from src_common.mongo_dictionary_service import MongoDictionaryService, DictEntry


class TestFR015DictionaryPerformance:
    """Performance tests for MongoDB dictionary backend"""

    @pytest.fixture
    def mongo_service(self):
        """Create MongoDB service for testing"""
        return MongoDictionaryService(env="test")

    @pytest.fixture
    def admin_service(self):
        """Create AdminDictionaryService with MongoDB enabled"""
        return AdminDictionaryService(use_mongodb=True)

    @pytest.fixture
    async def sample_data_10k(self, mongo_service):
        """Create 10k sample dictionary entries for performance testing"""
        entries = []

        # Generate test data with variety to ensure realistic search scenarios
        categories = ["rule", "concept", "procedure", "entity", "spell", "item", "location", "character"]
        sources = ["Player Handbook", "Dungeon Master Guide", "Monster Manual", "Homebrew"]

        for i in range(10000):
            category = categories[i % len(categories)]
            source = sources[i % len(sources)]

            entry = DictEntry(
                term=f"test_term_{i:05d}",
                definition=f"This is a test definition for term {i}. It contains searchable content about {category} mechanics and various gameplay elements.",
                category=category,
                sources=[{
                    "system": source,
                    "page_reference": f"p.{(i % 300) + 1}",
                    "confidence": 0.9 + (i % 10) * 0.01,
                    "extraction_method": "test_data_generation"
                }]
            )
            entries.append(entry)

        # Insert test data
        result = mongo_service.upsert_entries(entries)
        assert result == 10000, "Failed to insert all test data"

        # Wait for indexes to be built
        await asyncio.sleep(2)

        yield entries

        # Cleanup: Remove test data
        for entry in entries:
            mongo_service.delete_entry(entry.term)

    @pytest.mark.asyncio
    async def test_search_performance_10k_records(self, admin_service, sample_data_10k):
        """
        Test AC2: Performance: initial search ≤1.5s on 10k records (indexed)
        """
        # Test various search scenarios
        search_scenarios = [
            "rule",  # Category match
            "test",  # Common term
            "mechanics",  # Definition content
            "Player",  # Source content
            "test_term_05000",  # Exact term match
            "gameplay elements"  # Multi-word phrase
        ]

        for search_query in search_scenarios:
            start_time = time.time()

            results = await admin_service.search_terms(
                environment="test",
                query=search_query
            )

            search_time = time.time() - start_time

            # AC2 requirement: ≤1.5s
            assert search_time <= 1.5, (
                f"Search for '{search_query}' took {search_time:.3f}s, "
                f"exceeding 1.5s requirement (AC2)"
            )

            # Ensure we got meaningful results
            assert len(results) > 0, f"No results found for '{search_query}'"

            print(f"Search '{search_query}': {search_time:.3f}s, {len(results)} results")

    @pytest.mark.asyncio
    async def test_list_performance_large_dataset(self, admin_service, sample_data_10k):
        """Test list operations performance with large dataset"""
        start_time = time.time()

        terms = await admin_service.list_terms(
            environment="test",
            limit=100
        )

        list_time = time.time() - start_time

        # Should be much faster than search
        assert list_time <= 0.5, f"List operation took {list_time:.3f}s, should be ≤0.5s"
        assert len(terms) == 100, "Should return exactly 100 terms"

        print(f"List 100 terms: {list_time:.3f}s")

    @pytest.mark.asyncio
    async def test_category_filter_performance(self, admin_service, sample_data_10k):
        """Test category filtering performance"""
        start_time = time.time()

        terms = await admin_service.list_terms(
            environment="test",
            category="rule",
            limit=500
        )

        filter_time = time.time() - start_time

        assert filter_time <= 1.0, f"Category filter took {filter_time:.3f}s, should be ≤1.0s"

        # Verify all results match category
        for term in terms:
            assert term.category == "rule", "All results should match category filter"

        print(f"Category filter 'rule': {filter_time:.3f}s, {len(terms)} results")

    @pytest.mark.asyncio
    async def test_get_term_performance(self, admin_service, sample_data_10k):
        """Test individual term lookup performance"""
        # Test several lookups
        test_terms = ["test_term_00001", "test_term_05000", "test_term_09999"]

        for term_name in test_terms:
            start_time = time.time()

            term = await admin_service.get_term("test", term_name)

            lookup_time = time.time() - start_time

            assert lookup_time <= 0.1, f"Term lookup took {lookup_time:.3f}s, should be ≤0.1s"
            assert term is not None, f"Term '{term_name}' should exist"
            assert term.term == term_name, "Returned term should match requested term"

            print(f"Lookup '{term_name}': {lookup_time:.3f}s")

    @pytest.mark.asyncio
    async def test_stats_calculation_performance(self, admin_service, sample_data_10k):
        """Test statistics calculation performance on large dataset"""
        start_time = time.time()

        stats = await admin_service.get_environment_stats("test")

        stats_time = time.time() - start_time

        assert stats_time <= 2.0, f"Stats calculation took {stats_time:.3f}s, should be ≤2.0s"
        assert stats.total_terms >= 10000, "Should count all test terms"
        assert len(stats.categories) > 0, "Should have category breakdown"

        print(f"Stats calculation: {stats_time:.3f}s, {stats.total_terms} terms")

    @pytest.mark.asyncio
    async def test_concurrent_search_performance(self, admin_service, sample_data_10k):
        """Test performance under concurrent load"""
        async def search_task(query: str) -> float:
            start_time = time.time()
            await admin_service.search_terms("test", query)
            return time.time() - start_time

        # Run 10 concurrent searches
        tasks = [
            search_task(f"test_term_{i:05d}")
            for i in range(0, 10000, 1000)  # Search for terms at 1000 intervals
        ]

        start_time = time.time()
        search_times = await asyncio.gather(*tasks)
        total_time = time.time() - start_time

        # All individual searches should still meet performance requirement
        for i, search_time in enumerate(search_times):
            assert search_time <= 1.5, (
                f"Concurrent search {i} took {search_time:.3f}s, "
                f"exceeding 1.5s requirement"
            )

        # Total time for all concurrent searches should be reasonable
        assert total_time <= 3.0, f"10 concurrent searches took {total_time:.3f}s, should be ≤3.0s"

        print(f"10 concurrent searches: {total_time:.3f}s total, "
              f"avg {sum(search_times)/len(search_times):.3f}s per search")

    @pytest.mark.performance
    def test_mongodb_index_efficiency(self, mongo_service):
        """Test that MongoDB indexes are properly configured for performance"""
        # Verify text search index exists
        indexes = list(mongo_service.collection.list_indexes())

        index_names = [idx['name'] for idx in indexes]

        # Check for required indexes
        required_indexes = [
            'text_search',          # Full-text search
            'category_index',       # Category filtering
            'category_term_index'   # Compound category+term index
        ]

        for required_index in required_indexes:
            assert required_index in index_names, f"Missing required index: {required_index}"

        print(f"MongoDB indexes verified: {index_names}")

    @pytest.mark.asyncio
    async def test_memory_usage_large_dataset(self, admin_service, sample_data_10k):
        """Test memory efficiency with large dataset operations"""
        import psutil
        import os

        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB

        # Perform multiple operations
        await admin_service.list_terms("test", limit=1000)
        await admin_service.search_terms("test", "mechanics")
        await admin_service.get_environment_stats("test")

        final_memory = process.memory_info().rss / 1024 / 1024  # MB
        memory_increase = final_memory - initial_memory

        # Memory increase should be reasonable (less than 100MB for these operations)
        assert memory_increase < 100, (
            f"Memory usage increased by {memory_increase:.1f}MB, "
            f"should be less than 100MB"
        )

        print(f"Memory usage: {initial_memory:.1f}MB → {final_memory:.1f}MB "
              f"(+{memory_increase:.1f}MB)")


if __name__ == "__main__":
    # Run specific performance tests
    pytest.main([
        __file__,
        "-v",
        "-m", "performance",
        "--tb=short"
    ])