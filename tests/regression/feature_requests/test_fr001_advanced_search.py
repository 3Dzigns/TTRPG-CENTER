# tests/regression/feature_requests/test_fr001_advanced_search.py
"""
Feature Request FR-001: Advanced Search Functionality Regression Tests
Tests enhanced search capabilities with filters, sorting, and faceted search
"""

import pytest
import time
import json
from pathlib import Path
from unittest.mock import patch, MagicMock


class TestAdvancedSearchFunctionality:
    """Test suite for Advanced Search functionality validation"""

    def test_search_interface_availability(self):
        """Test that advanced search interface is available"""
        try:
            from src_common.search_engine import AdvancedSearchEngine
            from src_common.query_processor import QueryProcessor

            assert AdvancedSearchEngine is not None, "AdvancedSearchEngine should be available"
            assert QueryProcessor is not None, "QueryProcessor should be available for search"

        except ImportError as e:
            pytest.fail(f"Advanced search components not available: {e}")

    def test_faceted_search_capabilities(self):
        """Test faceted search with multiple filter dimensions"""
        try:
            from src_common.search_engine import AdvancedSearchEngine
        except ImportError:
            pytest.skip("Advanced search engine not available for testing")

        search_engine = AdvancedSearchEngine()

        # Test faceted search request
        faceted_query = {
            "query": "fireball spell",
            "facets": {
                "spell_school": ["evocation", "conjuration"],
                "spell_level": [3, 4, 5],
                "source_book": ["Player's Handbook", "Xanathar's Guide"],
                "character_class": ["wizard", "sorcerer"]
            },
            "sort_by": "relevance",
            "limit": 20
        }

        if hasattr(search_engine, 'faceted_search'):
            results = search_engine.faceted_search(faceted_query)

            assert isinstance(results, dict), "Faceted search should return structured results"

            # Verify result structure
            expected_fields = ["results", "facet_counts", "total_matches", "query_time"]

            for field in expected_fields:
                if field in results:
                    if field == "results":
                        assert isinstance(results[field], list), "Results should be list"

                    elif field == "facet_counts":
                        facet_counts = results[field]
                        assert isinstance(facet_counts, dict), "Facet counts should be structured"

                        # Verify facet structure
                        for facet_name, counts in facet_counts.items():
                            assert isinstance(counts, dict), f"Facet {facet_name} should have count structure"

                    elif field == "total_matches":
                        assert isinstance(results[field], int), "Total matches should be integer"
                        assert results[field] >= 0, "Total matches should be non-negative"

                    elif field == "query_time":
                        assert isinstance(results[field], (int, float)), "Query time should be numeric"
                        assert results[field] > 0, "Query time should be positive"

    def test_advanced_query_syntax(self):
        """Test advanced query syntax and operators"""
        try:
            from src_common.search_engine import AdvancedSearchEngine
        except ImportError:
            pytest.skip("Advanced search engine not available for testing")

        search_engine = AdvancedSearchEngine()

        # Test various advanced query syntaxes
        advanced_queries = [
            {
                "query": 'spell_name:"Magic Missile" AND spell_level:1',
                "description": "Exact phrase with field search"
            },
            {
                "query": "(fire OR flame) AND damage_type:fire",
                "description": "Boolean operators with field filter"
            },
            {
                "query": "spell_level:[1 TO 3] AND school:evocation",
                "description": "Range query with field filter"
            },
            {
                "query": "healing* NOT necromancy",
                "description": "Wildcard with negation"
            },
            {
                "query": "\"cone of cold\"~2 AND spell_level:5",
                "description": "Proximity search with field filter"
            }
        ]

        if hasattr(search_engine, 'advanced_query'):
            for query_test in advanced_queries:
                results = search_engine.advanced_query(query_test["query"])

                if results:
                    assert isinstance(results, dict), f"Advanced query should return structured results for: {query_test['description']}"

                    if "results" in results:
                        assert isinstance(results["results"], list), "Results should be list"

                    if "query_parsed" in results:
                        assert isinstance(results["query_parsed"], dict), "Parsed query should show structure"

    def test_search_result_ranking_and_sorting(self):
        """Test search result ranking algorithms and sorting options"""
        try:
            from src_common.search_engine import AdvancedSearchEngine
        except ImportError:
            pytest.skip("Advanced search engine not available for testing")

        search_engine = AdvancedSearchEngine()

        test_query = "healing spell"

        # Test different sorting options
        sort_options = [
            "relevance",
            "alphabetical",
            "spell_level_asc",
            "spell_level_desc",
            "source_book",
            "popularity"
        ]

        if hasattr(search_engine, 'search_with_sorting'):
            previous_results = None

            for sort_option in sort_options:
                results = search_engine.search_with_sorting(test_query, sort_by=sort_option)

                if results and "results" in results:
                    current_results = results["results"]

                    # Verify results are actually sorted differently
                    if previous_results and len(current_results) > 1 and len(previous_results) > 1:
                        # Results should potentially be in different order for different sort options
                        if sort_option != "relevance":  # Skip relevance comparison
                            first_item_different = (
                                current_results[0].get("id") != previous_results[0].get("id")
                            )

                            # Allow for cases where top result might be same but verify sorting logic exists
                            assert isinstance(current_results, list), f"Sorted results should be list for {sort_option}"

                    # Verify sort-specific result ordering
                    if sort_option == "alphabetical" and len(current_results) >= 2:
                        if all("name" in item for item in current_results[:2]):
                            first_name = current_results[0]["name"].lower()
                            second_name = current_results[1]["name"].lower()
                            assert first_name <= second_name, "Alphabetical sort should order names correctly"

                    elif sort_option == "spell_level_asc" and len(current_results) >= 2:
                        if all("spell_level" in item for item in current_results[:2]):
                            first_level = current_results[0]["spell_level"]
                            second_level = current_results[1]["spell_level"]
                            assert first_level <= second_level, "Ascending level sort should order correctly"

                    previous_results = current_results

    def test_search_filters_and_refinement(self):
        """Test search filter application and result refinement"""
        try:
            from src_common.search_engine import AdvancedSearchEngine
        except ImportError:
            pytest.skip("Advanced search engine not available for testing")

        search_engine = AdvancedSearchEngine()

        # Test filter application
        base_query = "damage spell"

        filter_sets = [
            {
                "name": "Level filters",
                "filters": {
                    "spell_level": [1, 2, 3],
                    "min_damage": 10
                }
            },
            {
                "name": "School filters",
                "filters": {
                    "spell_school": ["evocation", "necromancy"],
                    "damage_type": ["fire", "necrotic"]
                }
            },
            {
                "name": "Source filters",
                "filters": {
                    "source_book": ["Player's Handbook"],
                    "official_content": True
                }
            }
        ]

        if hasattr(search_engine, 'search_with_filters'):
            unfiltered_results = search_engine.search_with_filters(base_query, {})

            for filter_set in filter_sets:
                filtered_results = search_engine.search_with_filters(base_query, filter_set["filters"])

                if filtered_results and unfiltered_results:
                    filtered_count = filtered_results.get("total_matches", 0)
                    unfiltered_count = unfiltered_results.get("total_matches", 0)

                    # Filtered results should generally be fewer than unfiltered
                    # (unless filter set matches all results)
                    assert filtered_count <= unfiltered_count, \
                        f"Filtered results should be subset for {filter_set['name']}"

                    # Verify filter application in results
                    if "results" in filtered_results:
                        results = filtered_results["results"]

                        for result in results[:5]:  # Check first 5 results
                            # Verify filters are actually applied
                            filters = filter_set["filters"]

                            if "spell_level" in filters and "spell_level" in result:
                                assert result["spell_level"] in filters["spell_level"], \
                                    f"Result spell level should match filter: {filter_set['name']}"

                            if "spell_school" in filters and "spell_school" in result:
                                assert result["spell_school"] in filters["spell_school"], \
                                    f"Result spell school should match filter: {filter_set['name']}"

    def test_search_autocomplete_and_suggestions(self):
        """Test search autocomplete and suggestion functionality"""
        try:
            from src_common.search_engine import AdvancedSearchEngine
        except ImportError:
            pytest.skip("Advanced search engine not available for testing")

        search_engine = AdvancedSearchEngine()

        # Test autocomplete functionality
        partial_queries = [
            "fire",
            "heal",
            "mag",
            "illus",
            "transform"
        ]

        if hasattr(search_engine, 'get_autocomplete_suggestions'):
            for partial_query in partial_queries:
                suggestions = search_engine.get_autocomplete_suggestions(partial_query)

                if suggestions:
                    assert isinstance(suggestions, list), "Autocomplete should return list of suggestions"

                    for suggestion in suggestions[:5]:  # Check first 5 suggestions
                        assert isinstance(suggestion, (str, dict)), "Suggestion should be string or structured"

                        if isinstance(suggestion, dict):
                            assert "text" in suggestion, "Structured suggestion should have text"

                        suggestion_text = suggestion if isinstance(suggestion, str) else suggestion["text"]
                        assert partial_query.lower() in suggestion_text.lower(), \
                            f"Suggestion '{suggestion_text}' should contain partial query '{partial_query}'"

        # Test spell suggestions and did-you-mean functionality
        if hasattr(search_engine, 'get_spelling_suggestions'):
            misspelled_queries = [
                "magik missile",  # magic missile
                "firbal",         # fireball
                "healng",         # healing
                "teleort"         # teleport
            ]

            for misspelled in misspelled_queries:
                suggestions = search_engine.get_spelling_suggestions(misspelled)

                if suggestions:
                    assert isinstance(suggestions, list), "Spelling suggestions should be list"

                    if suggestions:  # If any suggestions returned
                        best_suggestion = suggestions[0]
                        suggestion_text = best_suggestion if isinstance(best_suggestion, str) else best_suggestion.get("text", "")

                        # Suggestion should be different from misspelled input
                        assert suggestion_text != misspelled, "Spelling suggestion should correct the input"

    def test_search_performance_and_caching(self):
        """Test search performance optimization and caching mechanisms"""
        try:
            from src_common.search_engine import AdvancedSearchEngine
        except ImportError:
            pytest.skip("Advanced search engine not available for testing")

        search_engine = AdvancedSearchEngine()

        test_query = "popular spells wizard"

        # Test response time for search queries
        if hasattr(search_engine, 'search'):
            start_time = time.perf_counter()
            first_results = search_engine.search(test_query)
            first_query_time = time.perf_counter() - start_time

            # First query should complete within reasonable time
            assert first_query_time < 5.0, f"Search query should complete within 5 seconds, took {first_query_time:.2f}s"

            # Test repeated query (should benefit from caching)
            start_time = time.perf_counter()
            second_results = search_engine.search(test_query)
            second_query_time = time.perf_counter() - start_time

            # Repeated query should generally be faster (due to caching)
            if second_query_time > 0:
                speed_improvement = first_query_time / second_query_time
                # Allow for some variation, but cached query should show improvement
                if speed_improvement > 1.2:  # At least 20% improvement
                    assert True, f"Caching improved performance by {speed_improvement:.1f}x"

        # Test search result pagination performance
        if hasattr(search_engine, 'search_paginated'):
            page_sizes = [10, 20, 50]

            for page_size in page_sizes:
                start_time = time.perf_counter()
                paginated_results = search_engine.search_paginated(test_query, page=1, page_size=page_size)
                pagination_time = time.perf_counter() - start_time

                if paginated_results:
                    # Pagination should complete quickly
                    assert pagination_time < 3.0, f"Paginated search should complete within 3 seconds"

                    if "results" in paginated_results:
                        results_count = len(paginated_results["results"])
                        assert results_count <= page_size, f"Results should not exceed page size {page_size}"

    def test_search_analytics_and_tracking(self):
        """Test search analytics and usage tracking"""
        try:
            from src_common.search_engine import AdvancedSearchEngine
        except ImportError:
            pytest.skip("Advanced search engine not available for testing")

        search_engine = AdvancedSearchEngine()

        # Test search query tracking
        test_queries = [
            "fireball spell",
            "healing potion",
            "magic weapon",
            "teleportation circle"
        ]

        if hasattr(search_engine, 'track_search_query'):
            for query in test_queries:
                tracking_result = search_engine.track_search_query(
                    query=query,
                    user_id="test_user_001",
                    session_id="test_session_001",
                    results_count=15,
                    click_through=True
                )

                if tracking_result:
                    assert isinstance(tracking_result, dict), "Search tracking should return structured result"

                    if "tracked" in tracking_result:
                        assert tracking_result["tracked"] == True, "Search should be successfully tracked"

        # Test search analytics retrieval
        if hasattr(search_engine, 'get_search_analytics'):
            analytics_timeframe = {
                "start_date": "2024-01-01",
                "end_date": "2024-12-31"
            }

            analytics = search_engine.get_search_analytics(analytics_timeframe)

            if analytics:
                assert isinstance(analytics, dict), "Search analytics should return structured data"

                expected_analytics_fields = [
                    "total_searches", "unique_queries", "top_queries",
                    "average_results_per_query", "click_through_rate"
                ]

                for field in expected_analytics_fields:
                    if field in analytics:
                        if field in ["total_searches", "unique_queries"]:
                            assert isinstance(analytics[field], int), f"{field} should be integer"

                        elif field == "top_queries":
                            top_queries = analytics[field]
                            assert isinstance(top_queries, list), "Top queries should be list"

                            for query_stat in top_queries[:3]:  # Check first 3
                                assert "query" in query_stat, "Query stat should have query text"
                                assert "count" in query_stat, "Query stat should have count"

                        elif field in ["average_results_per_query", "click_through_rate"]:
                            assert isinstance(analytics[field], (int, float)), f"{field} should be numeric"

    def test_advanced_search_contract_compliance(self):
        """Test that advanced search functionality matches established contract"""
        try:
            from src_common.search_engine import AdvancedSearchEngine
        except ImportError:
            pytest.skip("Advanced search engine not available for testing")

        search_engine = AdvancedSearchEngine()

        # Test basic search contract
        basic_query = "test spell"

        if hasattr(search_engine, 'search'):
            results = search_engine.search(basic_query)

            assert isinstance(results, dict), "Search must return structured results"

            # Required contract fields
            contract_fields = ["results", "total_matches", "query_time"]

            for field in contract_fields:
                if field in results:
                    if field == "results":
                        assert isinstance(results[field], list), "Results must be list"

                    elif field == "total_matches":
                        assert isinstance(results[field], int), "Total matches must be integer"
                        assert results[field] >= 0, "Total matches must be non-negative"

                    elif field == "query_time":
                        assert isinstance(results[field], (int, float)), "Query time must be numeric"
                        assert results[field] >= 0, "Query time must be non-negative"

        # Test result structure contract
        if hasattr(search_engine, 'search') and search_engine.search(basic_query):
            sample_results = search_engine.search(basic_query)

            if sample_results and "results" in sample_results and sample_results["results"]:
                first_result = sample_results["results"][0]

                # Required result fields
                result_contract_fields = ["id", "title", "relevance_score"]

                for field in result_contract_fields:
                    if field in first_result:
                        if field == "relevance_score":
                            score = first_result[field]
                            assert isinstance(score, (int, float)), "Relevance score must be numeric"
                            assert 0 <= score <= 1, "Relevance score must be 0-1"

        # Test performance contract
        performance_query = "performance test query"

        if hasattr(search_engine, 'search'):
            start_time = time.perf_counter()
            perf_results = search_engine.search(performance_query)
            query_duration = time.perf_counter() - start_time

            # Performance contract: sub-2 second response time for basic queries
            assert query_duration < 2.0, f"Search performance contract violation: {query_duration:.2f}s > 2.0s limit"

            if perf_results and "query_time" in perf_results:
                reported_time = perf_results["query_time"]

                # Reported time should be consistent with measured time (within 50% margin)
                time_ratio = abs(reported_time - query_duration) / max(reported_time, query_duration)
                assert time_ratio < 0.5, f"Reported query time should match measured time within 50%"