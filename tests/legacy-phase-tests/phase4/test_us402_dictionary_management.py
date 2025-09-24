# tests/regression/phase4/test_us402_dictionary_management.py
"""
Phase 4 - US-402: Admin Dictionary Management Regression Tests
Tests admin interface for managing TTRPG terminology dictionary and term definitions
"""

import pytest
import time
import json
from pathlib import Path
from unittest.mock import patch, MagicMock


class TestAdminDictionaryManagement:
    """Test suite for Admin Dictionary Management validation"""

    def test_dictionary_management_interface_availability(self):
        """Test that dictionary management interface is accessible"""
        try:
            from src_common.admin_routes import app
            from src_common.admin.dictionary import DictionaryManager

            assert app is not None, "Admin Flask app should be available"
            assert DictionaryManager is not None, "DictionaryManager class should be available"

        except ImportError as e:
            pytest.fail(f"Dictionary management interface not available: {e}")

    def test_dictionary_term_listing_endpoint(self):
        """Test admin endpoint for listing dictionary terms"""
        try:
            from src_common.admin_routes import app
        except ImportError:
            pytest.skip("Admin routes module not available for testing")

        with app.test_client() as client:
            # Test dictionary listing endpoint
            response = client.get('/admin/dictionary/terms')

            assert response.status_code == 200, f"Dictionary listing should succeed, got {response.status_code}"

            response_data = response.get_json()

            # Verify response structure
            assert isinstance(response_data, dict), "Response should be a dictionary"
            assert "terms" in response_data, "Response should include terms list"

            terms = response_data["terms"]
            assert isinstance(terms, list), "Terms should be a list"

            # Verify term structure
            for term in terms:
                required_fields = ["term", "definition", "category", "sources"]
                for field in required_fields:
                    assert field in term, f"Term missing required field: {field}"

                # Verify field types
                assert isinstance(term["term"], str), "Term should be string"
                assert isinstance(term["definition"], str), "Definition should be string"
                assert isinstance(term["sources"], list), "Sources should be list"

                # Verify sources structure
                for source in term["sources"]:
                    source_fields = ["page", "section"]
                    for field in source_fields:
                        if field in source:
                            if field == "page":
                                assert isinstance(source[field], int), "Page should be integer"

    def test_dictionary_term_search_endpoint(self):
        """Test admin endpoint for searching dictionary terms"""
        try:
            from src_common.admin_routes import app
        except ImportError:
            pytest.skip("Admin routes module not available for testing")

        with app.test_client() as client:
            # Test term search
            search_queries = ["spell", "damage", "fireball", "ac"]

            for query in search_queries:
                response = client.get(f'/admin/dictionary/search?q={query}')

                if response.status_code == 200:
                    search_results = response.get_json()

                    assert "results" in search_results, "Search response should include results"
                    assert "query" in search_results, "Search response should include query"
                    assert search_results["query"] == query, "Query should match request"

                    results = search_results["results"]
                    assert isinstance(results, list), "Search results should be list"

                    # Verify search relevance
                    for result in results:
                        term_text = result.get("term", "").lower()
                        definition_text = result.get("definition", "").lower()

                        # Should find query in term or definition
                        assert query.lower() in term_text or query.lower() in definition_text, f"Search result should contain query '{query}'"

            # Test search filters
            category_response = client.get('/admin/dictionary/search?category=spell')

            if category_response.status_code == 200:
                category_results = category_response.get_json()["results"]

                for result in category_results:
                    assert result.get("category", "").lower() == "spell", "Category filter should work"

    def test_dictionary_term_creation_endpoint(self):
        """Test admin endpoint for creating new dictionary terms"""
        try:
            from src_common.admin_routes import app
        except ImportError:
            pytest.skip("Admin routes module not available for testing")

        with app.test_client() as client:
            # Test term creation
            new_term_data = {
                "term": "Test Spell",
                "definition": "A magical effect created for testing purposes",
                "category": "spell",
                "sources": [
                    {"page": 123, "section": "Test Spells", "document": "Test Manual"}
                ],
                "metadata": {
                    "level": 1,
                    "school": "test",
                    "created_by": "admin_test"
                }
            }

            response = client.post('/admin/dictionary/terms', json=new_term_data)

            assert response.status_code in [200, 201], f"Term creation should succeed, got {response.status_code}"

            if response.status_code in [200, 201]:
                response_data = response.get_json()

                assert "term_id" in response_data, "Response should include term ID"
                assert "status" in response_data, "Response should include status"

                # Verify term was created
                term_id = response_data["term_id"]
                get_response = client.get(f'/admin/dictionary/terms/{term_id}')

                if get_response.status_code == 200:
                    created_term = get_response.get_json()
                    assert created_term["term"] == "Test Spell", "Created term should match input"
                    assert created_term["definition"] == new_term_data["definition"], "Definition should match input"

    def test_dictionary_term_editing_endpoint(self):
        """Test admin endpoint for editing existing dictionary terms"""
        try:
            from src_common.admin_routes import app
        except ImportError:
            pytest.skip("Admin routes module not available for testing")

        with app.test_client() as client:
            # First create a term to edit
            original_term = {
                "term": "Editable Spell",
                "definition": "Original definition",
                "category": "spell",
                "sources": [{"page": 100}]
            }

            create_response = client.post('/admin/dictionary/terms', json=original_term)

            if create_response.status_code in [200, 201]:
                term_id = create_response.get_json()["term_id"]

                # Test term editing
                updated_data = {
                    "definition": "Updated definition with more details",
                    "category": "spell",
                    "sources": [
                        {"page": 100, "section": "Updated Section"},
                        {"page": 101, "section": "Additional Reference"}
                    ]
                }

                edit_response = client.put(f'/admin/dictionary/terms/{term_id}', json=updated_data)

                assert edit_response.status_code == 200, f"Term editing should succeed, got {edit_response.status_code}"

                # Verify changes were applied
                get_response = client.get(f'/admin/dictionary/terms/{term_id}')

                if get_response.status_code == 200:
                    updated_term = get_response.get_json()
                    assert updated_term["definition"] == updated_data["definition"], "Definition should be updated"
                    assert len(updated_term["sources"]) == 2, "Sources should be updated"

    def test_dictionary_bulk_operations_endpoint(self):
        """Test admin endpoint for bulk dictionary operations"""
        try:
            from src_common.admin_routes import app
        except ImportError:
            pytest.skip("Admin routes module not available for testing")

        with app.test_client() as client:
            # Test bulk import
            bulk_terms = [
                {
                    "term": "Bulk Term 1",
                    "definition": "First bulk imported term",
                    "category": "test",
                    "sources": [{"page": 1}]
                },
                {
                    "term": "Bulk Term 2",
                    "definition": "Second bulk imported term",
                    "category": "test",
                    "sources": [{"page": 2}]
                },
                {
                    "term": "Bulk Term 3",
                    "definition": "Third bulk imported term",
                    "category": "test",
                    "sources": [{"page": 3}]
                }
            ]

            bulk_data = {"terms": bulk_terms}

            response = client.post('/admin/dictionary/bulk-import', json=bulk_data)

            if response.status_code in [200, 202]:
                bulk_response = response.get_json()

                assert "imported_count" in bulk_response, "Bulk response should include imported count"
                assert "failed_count" in bulk_response, "Bulk response should include failed count"

                imported_count = bulk_response["imported_count"]
                assert imported_count > 0, "Should import at least some terms"

                # Test bulk export
                export_response = client.get('/admin/dictionary/export?category=test')

                if export_response.status_code == 200:
                    export_data = export_response.get_json()

                    assert "terms" in export_data, "Export should include terms"
                    assert len(export_data["terms"]) >= imported_count, "Export should include imported terms"

    def test_dictionary_validation_rules(self):
        """Test dictionary term validation and constraint enforcement"""
        try:
            from src_common.admin_routes import app
        except ImportError:
            pytest.skip("Admin routes module not available for testing")

        with app.test_client() as client:
            # Test invalid term creation
            invalid_terms = [
                # Missing required fields
                {"term": "Invalid 1"},
                # Empty definition
                {"term": "Invalid 2", "definition": "", "category": "test"},
                # Invalid category
                {"term": "Invalid 3", "definition": "Test", "category": "invalid_category"},
                # Invalid source structure
                {"term": "Invalid 4", "definition": "Test", "category": "spell", "sources": ["invalid_source"]}
            ]

            for invalid_term in invalid_terms:
                response = client.post('/admin/dictionary/terms', json=invalid_term)

                # Should reject invalid terms
                assert response.status_code >= 400, f"Invalid term should be rejected: {invalid_term}"

                if response.status_code >= 400:
                    error_data = response.get_json()
                    assert "error" in error_data or "message" in error_data, "Error response should include message"

            # Test duplicate term handling
            valid_term = {
                "term": "Duplicate Test",
                "definition": "First definition",
                "category": "test",
                "sources": [{"page": 1}]
            }

            # Create first instance
            first_response = client.post('/admin/dictionary/terms', json=valid_term)

            if first_response.status_code in [200, 201]:
                # Try to create duplicate
                duplicate_response = client.post('/admin/dictionary/terms', json=valid_term)

                # Should handle duplicates appropriately (reject or merge)
                if duplicate_response.status_code >= 400:
                    error_data = duplicate_response.get_json()
                    assert "duplicate" in str(error_data).lower() or "exists" in str(error_data).lower()

    def test_dictionary_category_management(self):
        """Test management of dictionary term categories"""
        try:
            from src_common.admin_routes import app
        except ImportError:
            pytest.skip("Admin routes module not available for testing")

        with app.test_client() as client:
            # Test category listing
            response = client.get('/admin/dictionary/categories')

            if response.status_code == 200:
                category_data = response.get_json()

                assert "categories" in category_data, "Response should include categories list"

                categories = category_data["categories"]
                assert isinstance(categories, list), "Categories should be list"

                # Verify category structure
                for category in categories:
                    if isinstance(category, dict):
                        assert "name" in category, "Category should have name"
                        assert "count" in category, "Category should have term count"
                        assert isinstance(category["count"], int), "Count should be integer"

            # Test category statistics
            stats_response = client.get('/admin/dictionary/categories/statistics')

            if stats_response.status_code == 200:
                stats_data = stats_response.get_json()

                expected_stats = ["total_categories", "total_terms", "top_categories"]
                for stat in expected_stats:
                    if stat in stats_data:
                        if stat in ["total_categories", "total_terms"]:
                            assert isinstance(stats_data[stat], int), f"{stat} should be integer"

    def test_dictionary_source_management(self):
        """Test management of dictionary term sources and references"""
        try:
            from src_common.admin_routes import app
        except ImportError:
            pytest.skip("Admin routes module not available for testing")

        with app.test_client() as client:
            # Test source listing
            response = client.get('/admin/dictionary/sources')

            if response.status_code == 200:
                source_data = response.get_json()

                assert "sources" in source_data, "Response should include sources list"

                sources = source_data["sources"]
                assert isinstance(sources, list), "Sources should be list"

                # Verify source structure
                for source in sources:
                    if isinstance(source, dict):
                        source_fields = ["document", "pages_referenced", "terms_count"]
                        for field in source_fields:
                            if field in source:
                                if field in ["pages_referenced", "terms_count"]:
                                    assert isinstance(source[field], (int, list)), f"{field} should be integer or list"

            # Test source validation
            source_validation_response = client.get('/admin/dictionary/sources/validate')

            if source_validation_response.status_code == 200:
                validation_data = source_validation_response.get_json()

                assert "validation_results" in validation_data, "Should include validation results"

                results = validation_data["validation_results"]
                for result in results:
                    if isinstance(result, dict):
                        assert "source" in result, "Validation result should identify source"
                        assert "status" in result, "Validation result should include status"

    def test_dictionary_version_control(self):
        """Test version control and change tracking for dictionary terms"""
        try:
            from src_common.admin_routes import app
        except ImportError:
            pytest.skip("Admin routes module not available for testing")

        with app.test_client() as client:
            # Create a term to track changes
            term_data = {
                "term": "Version Test Spell",
                "definition": "Original definition for version testing",
                "category": "spell",
                "sources": [{"page": 200}]
            }

            create_response = client.post('/admin/dictionary/terms', json=term_data)

            if create_response.status_code in [200, 201]:
                term_id = create_response.get_json()["term_id"]

                # Make changes to track versions
                updated_definition = "Updated definition for version testing"
                update_data = {"definition": updated_definition}

                edit_response = client.put(f'/admin/dictionary/terms/{term_id}', json=update_data)

                if edit_response.status_code == 200:
                    # Test version history endpoint
                    history_response = client.get(f'/admin/dictionary/terms/{term_id}/history')

                    if history_response.status_code == 200:
                        history_data = history_response.get_json()

                        assert "versions" in history_data, "History should include versions"

                        versions = history_data["versions"]
                        assert isinstance(versions, list), "Versions should be list"
                        assert len(versions) >= 1, "Should have at least one version"

                        # Verify version structure
                        for version in versions:
                            version_fields = ["version_id", "timestamp", "changes", "modified_by"]
                            for field in version_fields:
                                if field in version:
                                    if field == "timestamp":
                                        assert isinstance(version[field], (str, int, float)), "Timestamp should be temporal"

    def test_dictionary_search_performance(self):
        """Test performance of dictionary search operations"""
        try:
            from src_common.admin_routes import app
        except ImportError:
            pytest.skip("Admin routes module not available for testing")

        with app.test_client() as client:
            # Test search performance with various query types
            search_queries = [
                "spell",           # Common term
                "fireball",        # Specific term
                "damage",          # Broad term
                "ac",             # Abbreviation
                "nonexistent"     # No results
            ]

            search_times = []

            for query in search_queries:
                start_time = time.perf_counter()
                response = client.get(f'/admin/dictionary/search?q={query}')
                end_time = time.perf_counter()

                search_time = (end_time - start_time) * 1000
                search_times.append(search_time)

                if response.status_code == 200:
                    # Individual search should be fast
                    assert search_time < 200, f"Search for '{query}' took {search_time:.1f}ms, should be < 200ms"

            # Average search time should be reasonable
            avg_search_time = sum(search_times) / len(search_times)
            assert avg_search_time < 100, f"Average search time {avg_search_time:.1f}ms should be < 100ms"

    def test_dictionary_admin_ui_responsiveness(self):
        """Test dictionary admin UI responsiveness and performance"""
        try:
            from src_common.admin_routes import app
        except ImportError:
            pytest.skip("Admin routes module not available for testing")

        with app.test_client() as client:
            # Test main dictionary interface load time
            start_time = time.perf_counter()
            response = client.get('/admin/dictionary')
            end_time = time.perf_counter()

            load_time = (end_time - start_time) * 1000

            assert response.status_code == 200, "Dictionary interface should load successfully"
            assert load_time < 1000, f"Dictionary interface load time {load_time:.1f}ms should be < 1000ms"

            # Test pagination performance
            pagination_response = client.get('/admin/dictionary/terms?page=1&per_page=50')

            if pagination_response.status_code == 200:
                start_time = time.perf_counter()
                page2_response = client.get('/admin/dictionary/terms?page=2&per_page=50')
                end_time = time.perf_counter()

                pagination_time = (end_time - start_time) * 1000

                if page2_response.status_code == 200:
                    assert pagination_time < 300, f"Pagination response time {pagination_time:.1f}ms should be < 300ms"

    def test_dictionary_contract_compliance(self):
        """Test that dictionary management interface matches established contract"""
        try:
            from src_common.admin_routes import app
        except ImportError:
            pytest.skip("Admin routes module not available for testing")

        with app.test_client() as client:
            # Test term listing contract
            response = client.get('/admin/dictionary/terms')

            if response.status_code == 200:
                response_data = response.get_json()

                # Required response structure
                assert "terms" in response_data, "Response must include terms array"
                assert isinstance(response_data["terms"], list), "Terms must be array"

                # Term contract
                for term in response_data["terms"]:
                    required_fields = ["term", "definition", "category"]
                    for field in required_fields:
                        assert field in term, f"Term missing required field: {field}"

                    # Field types
                    assert isinstance(term["term"], str), "Term must be string"
                    assert isinstance(term["definition"], str), "Definition must be string"
                    assert isinstance(term["category"], str), "Category must be string"

                    # Sources contract
                    if "sources" in term:
                        assert isinstance(term["sources"], list), "Sources must be array"

                        for source in term["sources"]:
                            if isinstance(source, dict):
                                if "page" in source:
                                    assert isinstance(source["page"], int), "Page must be integer"

            # Test search contract
            search_response = client.get('/admin/dictionary/search?q=test')

            if search_response.status_code == 200:
                search_data = search_response.get_json()

                required_search_fields = ["results", "query"]
                for field in required_search_fields:
                    assert field in search_data, f"Search response missing field: {field}"

                assert isinstance(search_data["results"], list), "Search results must be array"
                assert isinstance(search_data["query"], str), "Search query must be string"

            # Test creation contract
            valid_term = {
                "term": "Contract Test",
                "definition": "Test term for contract validation",
                "category": "test",
                "sources": [{"page": 1}]
            }

            create_response = client.post('/admin/dictionary/terms', json=valid_term)

            if create_response.status_code in [200, 201]:
                create_data = create_response.get_json()

                required_create_fields = ["term_id", "status"]
                for field in required_create_fields:
                    assert field in create_data, f"Creation response missing field: {field}"

                assert isinstance(create_data["term_id"], str), "Term ID must be string"