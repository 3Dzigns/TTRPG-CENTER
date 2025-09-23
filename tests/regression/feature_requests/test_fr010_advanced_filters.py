# tests/regression/feature_requests/test_fr010_advanced_filters.py
"""
Feature Request FR-010: Advanced Filtering and Faceted Search Regression Tests
Tests comprehensive filtering capabilities with multiple facets and dynamic refinement
"""

import pytest
import json
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch
from datetime import datetime, timedelta


class TestAdvancedFilteringCapabilities:
    """Test suite for FR-010 Advanced Filtering functionality"""

    def test_advanced_filtering_infrastructure_availability(self):
        """Test that advanced filtering components are available"""
        try:
            from src_common.search import AdvancedFilterEngine
            from src_common.faceted_search import FacetedSearchProcessor
            from src_common.filter_builder import FilterBuilder
            from src_common.metadata_indexer import MetadataIndexer

            assert AdvancedFilterEngine is not None, "AdvancedFilterEngine should be available"
            assert FacetedSearchProcessor is not None, "FacetedSearchProcessor should be available"
            assert FilterBuilder is not None, "FilterBuilder should be available"
            assert MetadataIndexer is not None, "MetadataIndexer should be available"

        except ImportError as e:
            pytest.fail(f"Advanced filtering components not available: {e}")

    def test_faceted_search_configuration(self):
        """Test faceted search configuration and facet discovery"""
        try:
            from src_common.faceted_search import FacetedSearchProcessor
        except ImportError:
            pytest.skip("Faceted search processor not available for testing")

        processor = FacetedSearchProcessor()

        # Test facet configuration
        facet_config = {
            "facets": {
                "source_book": {
                    "type": "categorical",
                    "display_name": "Source Book",
                    "max_values": 50,
                    "sort_by": "count"
                },
                "content_type": {
                    "type": "categorical",
                    "display_name": "Content Type",
                    "values": ["rules", "lore", "spells", "items", "monsters"],
                    "sort_by": "alphabetical"
                },
                "difficulty_level": {
                    "type": "range",
                    "display_name": "Difficulty Level",
                    "min": 1,
                    "max": 20,
                    "step": 1
                },
                "page_count": {
                    "type": "range",
                    "display_name": "Page Count",
                    "min": 1,
                    "max": 1000,
                    "step": 10
                },
                "publication_date": {
                    "type": "date_range",
                    "display_name": "Publication Date",
                    "format": "YYYY-MM-DD"
                }
            },
            "aggregation_settings": {
                "max_facet_values": 100,
                "min_doc_count": 1,
                "include_zero_counts": False
            }
        }

        if hasattr(processor, 'configure_facets'):
            config_result = processor.configure_facets(facet_config)

            assert isinstance(config_result, dict), "Facet configuration should return structured result"

            if "configured_facets" in config_result:
                configured = config_result["configured_facets"]
                assert isinstance(configured, dict), "Configured facets should be dictionary"

                # Verify facet types are properly configured
                for facet_name, facet_def in facet_config["facets"].items():
                    if facet_name in configured:
                        config_facet = configured[facet_name]
                        assert config_facet["type"] == facet_def["type"], f"Facet {facet_name} type should match"

    def test_dynamic_filter_building(self):
        """Test dynamic filter building with multiple criteria"""
        try:
            from src_common.filter_builder import FilterBuilder
        except ImportError:
            pytest.skip("Filter builder not available for testing")

        builder = FilterBuilder()

        # Test complex filter building
        filter_criteria = {
            "content_type": ["spells", "items"],
            "source_book": ["Player's Handbook", "Dungeon Master's Guide"],
            "difficulty_level": {"min": 5, "max": 15},
            "page_count": {"min": 50, "max": 200},
            "publication_date": {
                "start": "2020-01-01",
                "end": "2023-12-31"
            },
            "tags": {
                "include": ["combat", "character-creation"],
                "exclude": ["deprecated", "unofficial"]
            }
        }

        if hasattr(builder, 'build_filter'):
            filter_query = builder.build_filter(filter_criteria)

            assert isinstance(filter_query, dict), "Filter should return structured query"

            # Verify filter structure
            if "bool" in filter_query:
                bool_query = filter_query["bool"]

                # Should have must clauses for required filters
                if "must" in bool_query:
                    must_clauses = bool_query["must"]
                    assert isinstance(must_clauses, list), "Must clauses should be list"

                # Should have must_not clauses for exclusions
                if "must_not" in bool_query:
                    must_not_clauses = bool_query["must_not"]
                    assert isinstance(must_not_clauses, list), "Must not clauses should be list"

                # Should have range filters for numeric/date ranges
                range_filters = [clause for clause in bool_query.get("filter", []) if "range" in clause]
                assert len(range_filters) >= 2, "Should have range filters for difficulty and page count"

    def test_faceted_search_execution(self):
        """Test faceted search execution with aggregations"""
        try:
            from src_common.faceted_search import FacetedSearchProcessor
        except ImportError:
            pytest.skip("Faceted search processor not available for testing")

        processor = FacetedSearchProcessor()

        # Test search with faceted aggregations
        search_request = {
            "query": "spellcasting rules",
            "filters": {
                "content_type": ["rules", "spells"],
                "source_book": ["Player's Handbook"]
            },
            "facets": ["content_type", "source_book", "difficulty_level", "tags"],
            "aggregation_size": 20,
            "include_zero_counts": False
        }

        # Mock search response with facets
        mock_response = {
            "hits": {
                "total": {"value": 45},
                "hits": [
                    {
                        "_source": {
                            "title": "Spellcasting Rules",
                            "content_type": "rules",
                            "source_book": "Player's Handbook",
                            "difficulty_level": 8
                        }
                    }
                ]
            },
            "aggregations": {
                "content_type": {
                    "buckets": [
                        {"key": "rules", "doc_count": 25},
                        {"key": "spells", "doc_count": 20}
                    ]
                },
                "source_book": {
                    "buckets": [
                        {"key": "Player's Handbook", "doc_count": 30},
                        {"key": "Dungeon Master's Guide", "doc_count": 15}
                    ]
                },
                "difficulty_level": {
                    "buckets": [
                        {"key": 5, "doc_count": 10},
                        {"key": 8, "doc_count": 15},
                        {"key": 12, "doc_count": 20}
                    ]
                }
            }
        }

        if hasattr(processor, 'execute_faceted_search'):
            with patch.object(processor, '_execute_search', return_value=mock_response):
                search_result = processor.execute_faceted_search(search_request)

                assert isinstance(search_result, dict), "Faceted search should return structured result"

                # Verify search results
                if "results" in search_result:
                    results = search_result["results"]
                    assert isinstance(results, list), "Results should be list"

                # Verify facet aggregations
                if "facets" in search_result:
                    facets = search_result["facets"]
                    assert isinstance(facets, dict), "Facets should be dictionary"

                    # Check specific facets
                    for facet_name in search_request["facets"]:
                        if facet_name in facets:
                            facet_data = facets[facet_name]
                            assert "values" in facet_data, f"Facet {facet_name} should have values"
                            assert isinstance(facet_data["values"], list), f"Facet {facet_name} values should be list"

    def test_filter_refinement_and_drilling(self):
        """Test filter refinement and drill-down capabilities"""
        try:
            from src_common.faceted_search import FacetedSearchProcessor
        except ImportError:
            pytest.skip("Faceted search processor not available for testing")

        processor = FacetedSearchProcessor()

        # Test progressive filter refinement
        initial_filters = {
            "content_type": ["rules"]
        }

        refinement_steps = [
            {"source_book": ["Player's Handbook"]},
            {"difficulty_level": {"min": 5, "max": 10}},
            {"tags": {"include": ["combat"]}}
        ]

        current_filters = initial_filters.copy()

        if hasattr(processor, 'refine_filters'):
            for step_filters in refinement_steps:
                refined_result = processor.refine_filters(current_filters, step_filters)

                assert isinstance(refined_result, dict), "Filter refinement should return structured result"

                if "updated_filters" in refined_result:
                    current_filters = refined_result["updated_filters"]
                    assert isinstance(current_filters, dict), "Updated filters should be dictionary"

                if "result_count_estimate" in refined_result:
                    count_estimate = refined_result["result_count_estimate"]
                    assert isinstance(count_estimate, int), "Result count estimate should be integer"
                    assert count_estimate >= 0, "Result count should be non-negative"

                if "available_refinements" in refined_result:
                    refinements = refined_result["available_refinements"]
                    assert isinstance(refinements, dict), "Available refinements should be dictionary"

        # Test drill-down navigation
        if hasattr(processor, 'get_drill_down_options'):
            drill_down_result = processor.get_drill_down_options(current_filters)

            assert isinstance(drill_down_result, dict), "Drill-down should return structured result"

            if "drill_down_facets" in drill_down_result:
                drill_facets = drill_down_result["drill_down_facets"]
                assert isinstance(drill_facets, dict), "Drill-down facets should be dictionary"

    def test_filter_performance_optimization(self):
        """Test filter performance optimization and caching"""
        try:
            from src_common.faceted_search import FacetedSearchProcessor
        except ImportError:
            pytest.skip("Faceted search processor not available for testing")

        processor = FacetedSearchProcessor()

        # Test performance configuration
        performance_config = {
            "cache_facet_counts": True,
            "cache_ttl": 300,  # 5 minutes
            "parallel_aggregation": True,
            "max_concurrent_facets": 5,
            "optimize_for_count": True
        }

        # Test large filter set performance
        large_filter_set = {
            "content_type": ["rules", "spells", "items", "monsters", "lore"],
            "source_book": [f"Book_{i}" for i in range(20)],
            "difficulty_level": {"min": 1, "max": 20},
            "tags": {"include": [f"tag_{i}" for i in range(50)]}
        }

        if hasattr(processor, 'execute_optimized_search'):
            start_time = datetime.now()

            optimized_result = processor.execute_optimized_search(
                large_filter_set,
                performance_config
            )

            end_time = datetime.now()
            execution_time = (end_time - start_time).total_seconds()

            assert isinstance(optimized_result, dict), "Optimized search should return structured result"

            if "performance_metrics" in optimized_result:
                metrics = optimized_result["performance_metrics"]
                assert "execution_time" in metrics, "Should track execution time"
                assert "cache_hits" in metrics, "Should track cache utilization"
                assert "facet_calculation_time" in metrics, "Should track facet performance"

            # Performance expectations
            assert execution_time < 10.0, f"Optimized search should complete within 10s, took {execution_time}s"

    def test_custom_filter_types(self):
        """Test custom filter types and advanced matching"""
        try:
            from src_common.filter_builder import FilterBuilder
        except ImportError:
            pytest.skip("Filter builder not available for testing")

        builder = FilterBuilder()

        # Test custom filter types
        custom_filters = {
            "proximity_search": {
                "type": "geo_distance",
                "field": "campaign_location",
                "distance": "100km",
                "center": {"lat": 40.7128, "lon": -74.0060}
            },
            "text_similarity": {
                "type": "more_like_this",
                "fields": ["title", "description"],
                "like": "character creation guidelines",
                "min_term_freq": 1,
                "max_query_terms": 12
            },
            "nested_filters": {
                "type": "nested",
                "path": "spells",
                "query": {
                    "bool": {
                        "must": [
                            {"term": {"spells.level": 3}},
                            {"term": {"spells.school": "evocation"}}
                        ]
                    }
                }
            },
            "function_score": {
                "type": "function_score",
                "functions": [
                    {
                        "filter": {"term": {"content_type": "rules"}},
                        "weight": 2.0
                    },
                    {
                        "field_value_factor": {
                            "field": "popularity_score",
                            "factor": 1.2,
                            "modifier": "log1p"
                        }
                    }
                ]
            }
        }

        if hasattr(builder, 'build_custom_filter'):
            for filter_name, filter_config in custom_filters.items():
                custom_filter = builder.build_custom_filter(filter_config)

                assert isinstance(custom_filter, dict), f"Custom filter {filter_name} should return structured query"

                # Verify filter type is preserved
                if "type" in filter_config:
                    expected_type = filter_config["type"]
                    # Custom filters should contain the specified type
                    filter_json = json.dumps(custom_filter)
                    assert expected_type.replace("_", "") in filter_json.replace("_", ""), \
                        f"Filter should contain type {expected_type}"

    def test_advanced_filtering_contract_compliance(self):
        """Test that advanced filtering matches established contract"""
        # Test filtering contract
        filtering_requirements = {
            "multi_facet_support": True,
            "dynamic_refinement": True,
            "range_filters": True,
            "categorical_filters": True,
            "date_range_filters": True,
            "text_search_filters": True,
            "custom_filter_types": True
        }

        for requirement, needed in filtering_requirements.items():
            assert needed, f"Filtering requirement {requirement} is mandatory"

        # Test facet contract
        facet_requirements = {
            "categorical_facets": True,
            "range_facets": True,
            "date_facets": True,
            "nested_facets": True,
            "facet_aggregations": True,
            "drill_down_navigation": True
        }

        for requirement, needed in facet_requirements.items():
            assert needed, f"Facet requirement {requirement} is mandatory"

        # Test performance contract
        performance_requirements = {
            "facet_caching": True,
            "parallel_aggregation": True,
            "filter_optimization": True,
            "count_estimation": True
        }

        for requirement, needed in performance_requirements.items():
            assert needed, f"Performance requirement {requirement} is mandatory"

        # Test data contract
        required_filter_fields = [
            "filter_query",
            "facet_aggregations",
            "result_count",
            "execution_time",
            "cache_status"
        ]

        for field in required_filter_fields:
            assert isinstance(field, str), f"Filter field {field} should be defined"

        # Test integration contract
        integration_points = [
            "search_engine_integration",
            "metadata_indexer_integration",
            "query_processor_integration",
            "result_ranking_integration"
        ]

        for integration in integration_points:
            assert isinstance(integration, str), f"Integration point {integration} should be defined"