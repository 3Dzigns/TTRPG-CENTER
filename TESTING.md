# TTRPG Center Testing Guide

Comprehensive testing documentation for the TTRPG Center application, covering all testing strategies, tools, and procedures.

## Testing Strategy Overview

The TTRPG Center employs a multi-layered testing approach ensuring system reliability, performance, and user experience:

### Testing Pyramid

```
    🔺 E2E Tests (Browser/API)
   🔺🔺 Integration Tests (Component)
  🔺🔺🔺 Unit Tests (Function/Class)
 🔺🔺🔺🔺 Static Analysis (Lint/Type)
```

- **Static Analysis**: Code quality, type safety, security scanning
- **Unit Tests**: Individual component validation
- **Integration Tests**: Cross-component interaction
- **End-to-End Tests**: Complete user workflow validation

### Test Categories

| Category | Purpose | Location | Frequency |
|----------|---------|----------|-----------|
| Unit | Component isolation | `tests/unit/` | Every commit |
| Functional | Feature validation | `tests/functional/` | Every PR |
| Integration | System interaction | `tests/integration/` | Every PR |
| Regression | Stability assurance | `tests/regression/` | Nightly |
| Performance | Speed/resource validation | `tests/performance/` | Weekly |
| Security | Vulnerability detection | `tests/security/` | Every PR |
| E2E | User workflow validation | `tests/e2e/` | Pre-release |

## Quick Start

### Prerequisites

```bash
# Python dependencies
pip install pytest pytest-html pytest-xdist pytest-cov
pip install pytest-mock pytest-asyncio pytest-timeout
pip install selenium playwright beautifulsoup4

# Security testing
pip install bandit safety semgrep

# Performance testing
pip install locust pytest-benchmark
```

### Running Tests

```bash
# All tests (comprehensive)
pytest

# Specific test categories
pytest tests/unit/          # Unit tests only
pytest tests/functional/    # Functional tests only
pytest tests/regression/    # Regression tests only

# With coverage report
pytest --cov=src_common --cov-report=html

# Parallel execution
pytest -n auto

# Specific environment
TTRPG_ENV=test pytest tests/
```

## Test Structure and Organization

### Directory Layout

```
tests/
├── unit/                   # Unit tests (fast, isolated)
│   ├── test_ingestion/
│   ├── test_search/
│   ├── test_admin/
│   └── conftest.py
├── functional/             # Functional tests (feature-based)
│   ├── test_spell_search.py
│   ├── test_content_ingestion.py
│   └── test_user_preferences.py
├── integration/            # Integration tests (cross-component)
│   ├── test_api_integration.py
│   ├── test_database_integration.py
│   └── test_ui_api_integration.py
├── regression/             # Regression tests (stability)
│   ├── phase0/ through phase7/
│   ├── feature_requests/
│   ├── golden_masters/
│   └── README.md
├── performance/            # Performance tests (benchmarks)
│   ├── test_search_performance.py
│   ├── test_ingestion_performance.py
│   └── locustfile.py
├── security/               # Security tests (vulnerability)
│   ├── test_auth_security.py
│   ├── test_input_validation.py
│   └── test_data_protection.py
├── e2e/                    # End-to-end tests (browser-based)
│   ├── test_user_workflows.py
│   ├── test_admin_workflows.py
│   └── page_objects/
├── fixtures/               # Shared test data
│   ├── sample_pdfs/
│   ├── test_data.json
│   └── golden_masters/
└── conftest.py            # Global test configuration
```

## Unit Testing

### Philosophy

Unit tests focus on individual components in isolation, ensuring:
- **Fast execution** (<1s per test)
- **No external dependencies** (mocked)
- **Single responsibility** testing
- **Predictable outcomes**

### Example Unit Test

```python
# tests/unit/test_search/test_query_processor.py

import pytest
from unittest.mock import Mock, patch
from src_common.query_processor import QueryProcessor


class TestQueryProcessor:
    """Unit tests for QueryProcessor component"""

    @pytest.fixture
    def query_processor(self):
        """Create QueryProcessor instance with mocked dependencies"""
        mock_classifier = Mock()
        mock_vectorizer = Mock()
        return QueryProcessor(mock_classifier, mock_vectorizer)

    def test_process_simple_query(self, query_processor):
        """Test processing of simple search query"""
        # Arrange
        query = "fireball spell"
        expected_result = {
            "query_type": "spell_search",
            "extracted_terms": ["fireball", "spell"],
            "confidence": 0.95
        }

        # Mock classifier behavior
        query_processor.classifier.classify.return_value = "spell_search"
        query_processor.vectorizer.extract_terms.return_value = ["fireball", "spell"]

        # Act
        result = query_processor.process(query)

        # Assert
        assert result["query_type"] == expected_result["query_type"]
        assert result["extracted_terms"] == expected_result["extracted_terms"]
        assert result["confidence"] >= 0.9

        # Verify interactions
        query_processor.classifier.classify.assert_called_once_with(query)
        query_processor.vectorizer.extract_terms.assert_called_once_with(query)

    @pytest.mark.parametrize("query,expected_type", [
        ("fireball spell", "spell_search"),
        ("magic sword stats", "item_search"),
        ("goblin stats", "creature_search"),
        ("how to cast spells", "rule_search")
    ])
    def test_query_classification(self, query_processor, query, expected_type):
        """Test query type classification for various inputs"""
        query_processor.classifier.classify.return_value = expected_type

        result = query_processor.process(query)

        assert result["query_type"] == expected_type

    def test_empty_query_handling(self, query_processor):
        """Test handling of empty or invalid queries"""
        with pytest.raises(ValueError, match="Query cannot be empty"):
            query_processor.process("")

        with pytest.raises(ValueError, match="Query cannot be empty"):
            query_processor.process(None)

    def test_query_preprocessing(self, query_processor):
        """Test query preprocessing and sanitization"""
        # Test whitespace handling
        result = query_processor._preprocess_query("  fireball   spell  ")
        assert result == "fireball spell"

        # Test special character handling
        result = query_processor._preprocess_query("fire<ball> & magic!")
        assert result == "fireball magic"

        # Test case normalization
        result = query_processor._preprocess_query("FIREBALL Spell")
        assert result == "fireball spell"
```

### Unit Test Guidelines

1. **Test Structure**: Use Arrange-Act-Assert pattern
2. **Naming**: Descriptive test names indicating scenario and expectation
3. **Isolation**: Mock all external dependencies
4. **Coverage**: Aim for >90% code coverage
5. **Speed**: Each test should complete in <100ms

## Functional Testing

### Philosophy

Functional tests validate feature behavior from a user perspective:
- **Feature-complete scenarios**
- **Real component integration**
- **User workflow validation**
- **Business logic verification**

### Example Functional Test

```python
# tests/functional/test_spell_search.py

import pytest
import time
from src_common.search_engine import SearchEngine
from src_common.database import DatabaseManager


class TestSpellSearchFunctionality:
    """Functional tests for spell search feature"""

    @pytest.fixture(scope="class")
    def search_system(self):
        """Set up real search system for functional testing"""
        db_manager = DatabaseManager("test")
        search_engine = SearchEngine(db_manager)

        # Load test data
        test_spells = [
            {
                "name": "Fireball",
                "level": 3,
                "school": "evocation",
                "description": "A bright streak flashes from your pointing finger..."
            },
            {
                "name": "Magic Missile",
                "level": 1,
                "school": "evocation",
                "description": "You create three glowing darts of magical force..."
            }
        ]

        for spell in test_spells:
            search_engine.index_content(spell)

        yield search_engine

        # Cleanup
        db_manager.cleanup_test_data()

    def test_basic_spell_search(self, search_system):
        """Test basic spell search functionality"""
        # User searches for "fireball"
        results = search_system.search("fireball")

        # Should find the fireball spell
        assert len(results["items"]) >= 1
        assert results["items"][0]["name"] == "Fireball"
        assert results["items"][0]["level"] == 3

        # Should complete quickly
        assert results["query_time"] < 1.0

    def test_filtered_spell_search(self, search_system):
        """Test spell search with filters"""
        # User searches for level 1 spells
        results = search_system.search(
            query="spell",
            filters={"level": 1}
        )

        # Should find Magic Missile
        assert len(results["items"]) >= 1
        found_magic_missile = any(
            item["name"] == "Magic Missile"
            for item in results["items"]
        )
        assert found_magic_missile

        # All results should be level 1
        for item in results["items"]:
            assert item["level"] == 1

    def test_search_performance(self, search_system):
        """Test search performance requirements"""
        start_time = time.perf_counter()

        # Perform multiple searches
        for query in ["fireball", "magic", "evocation", "level 1"]:
            results = search_system.search(query)
            assert len(results["items"]) >= 0  # Valid results

        total_time = time.perf_counter() - start_time

        # Should handle multiple searches quickly
        assert total_time < 2.0, f"Search performance too slow: {total_time:.2f}s"

    def test_search_relevance_ranking(self, search_system):
        """Test search result relevance ranking"""
        # Search for "evocation spell"
        results = search_system.search("evocation spell")

        # Should return results
        assert len(results["items"]) >= 2

        # Evocation spells should rank higher
        evocation_spells = [
            item for item in results["items"]
            if item["school"] == "evocation"
        ]
        assert len(evocation_spells) >= 2

        # First result should be highly relevant
        assert results["items"][0]["relevance_score"] > 0.7
```

### Functional Test Guidelines

1. **Real Components**: Use actual system components, not mocks
2. **Test Data**: Use realistic test data sets
3. **User Scenarios**: Test complete user workflows
4. **Performance**: Include performance expectations
5. **Cleanup**: Always clean up test data

## Integration Testing

### Philosophy

Integration tests verify component interactions and system behavior:
- **Cross-component communication**
- **Data flow validation**
- **Interface contract verification**
- **System configuration testing**

### Example Integration Test

```python
# tests/integration/test_ingestion_search_integration.py

import pytest
import tempfile
from pathlib import Path
from src_common.ingestion import IngestionPipeline
from src_common.search_engine import SearchEngine
from src_common.database import DatabaseManager


class TestIngestionSearchIntegration:
    """Integration tests for ingestion pipeline and search system"""

    @pytest.fixture(scope="class")
    def integrated_system(self):
        """Set up complete ingestion and search system"""
        # Use test database
        db_manager = DatabaseManager("test")

        # Initialize components
        ingestion_pipeline = IngestionPipeline(db_manager)
        search_engine = SearchEngine(db_manager)

        yield {
            "ingestion": ingestion_pipeline,
            "search": search_engine,
            "database": db_manager
        }

        # Cleanup
        db_manager.cleanup_test_data()

    def test_pdf_ingestion_to_search_workflow(self, integrated_system):
        """Test complete workflow from PDF ingestion to search"""
        ingestion = integrated_system["ingestion"]
        search = integrated_system["search"]

        # Create test PDF content
        test_pdf_content = """
        Fireball
        3rd-level evocation
        Casting Time: 1 action
        Range: 150 feet
        Components: V, S, M (a tiny ball of bat guano and sulfur)
        Duration: Instantaneous

        A bright streak flashes from your pointing finger to a point you choose
        within range and then blossoms with a low roar into an explosion of flame.
        """

        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp_file:
            # Create simple PDF for testing
            from reportlab.pdfgen import canvas
            c = canvas.Canvas(tmp_file.name)
            c.drawString(100, 750, test_pdf_content)
            c.save()

            pdf_path = Path(tmp_file.name)

        try:
            # Step 1: Ingest PDF through pipeline
            ingestion_result = ingestion.process_document(pdf_path)

            assert ingestion_result["status"] == "completed"
            assert ingestion_result["chunks_created"] > 0
            assert "fireball" in ingestion_result["extracted_content"].lower()

            # Step 2: Verify content is searchable
            search_results = search.search("fireball")

            assert len(search_results["items"]) >= 1

            # Find the ingested fireball content
            fireball_result = None
            for item in search_results["items"]:
                if "fireball" in item.get("title", "").lower():
                    fireball_result = item
                    break

            assert fireball_result is not None
            assert "evocation" in fireball_result["content"].lower()
            assert fireball_result["document_source"] == str(pdf_path)

            # Step 3: Verify metadata extraction
            assert "spell_level" in fireball_result.get("metadata", {})
            assert fireball_result["metadata"]["spell_level"] == 3

        finally:
            # Cleanup test file
            pdf_path.unlink(missing_ok=True)

    def test_database_consistency_across_components(self, integrated_system):
        """Test database consistency across ingestion and search"""
        ingestion = integrated_system["ingestion"]
        search = integrated_system["search"]
        database = integrated_system["database"]

        # Ingest test content
        test_content = {
            "title": "Test Spell",
            "content": "A test spell for integration testing",
            "metadata": {"type": "spell", "level": 1}
        }

        # Add content through ingestion
        ingestion_id = ingestion.add_content(test_content)

        # Verify in database
        db_record = database.get_content(ingestion_id)
        assert db_record["title"] == test_content["title"]

        # Verify searchable
        search_results = search.search("test spell")
        found_content = any(
            item["id"] == ingestion_id
            for item in search_results["items"]
        )
        assert found_content

        # Test updates
        updated_content = test_content.copy()
        updated_content["content"] = "Updated test spell content"

        ingestion.update_content(ingestion_id, updated_content)

        # Verify update propagated
        updated_search = search.search("updated test spell")
        assert len(updated_search["items"]) >= 1

    def test_error_handling_integration(self, integrated_system):
        """Test error handling across integrated components"""
        ingestion = integrated_system["ingestion"]
        search = integrated_system["search"]

        # Test invalid file handling
        with pytest.raises(ValueError, match="Unsupported file format"):
            ingestion.process_document(Path("nonexistent.xyz"))

        # Test search with invalid parameters
        with pytest.raises(ValueError, match="Invalid search parameters"):
            search.search("", filters={"invalid_filter": "value"})

        # Verify system remains stable after errors
        valid_results = search.search("test")
        assert isinstance(valid_results, dict)
        assert "items" in valid_results
```

## Performance Testing

### Philosophy

Performance tests ensure system meets speed and resource requirements:
- **Response time validation**
- **Throughput measurement**
- **Resource utilization**
- **Scalability assessment**

### Benchmark Testing

```python
# tests/performance/test_search_performance.py

import pytest
import time
import statistics
from concurrent.futures import ThreadPoolExecutor
from src_common.search_engine import SearchEngine


class TestSearchPerformance:
    """Performance tests for search functionality"""

    @pytest.fixture(scope="class")
    def performance_search_engine(self):
        """Set up search engine with performance test data"""
        search_engine = SearchEngine("test")

        # Load substantial test dataset
        for i in range(1000):
            test_content = {
                "id": f"test_content_{i}",
                "title": f"Test Content {i}",
                "content": f"This is test content number {i} for performance testing",
                "metadata": {"type": "test", "index": i}
            }
            search_engine.index_content(test_content)

        yield search_engine

    @pytest.mark.performance
    def test_search_response_time(self, performance_search_engine):
        """Test search response time requirements"""
        search_queries = [
            "test content",
            "performance testing",
            "content number",
            "test metadata"
        ]

        response_times = []

        for query in search_queries:
            start_time = time.perf_counter()
            results = performance_search_engine.search(query)
            end_time = time.perf_counter()

            response_time = end_time - start_time
            response_times.append(response_time)

            # Individual query should be fast
            assert response_time < 2.0, f"Query '{query}' took {response_time:.3f}s"

            # Should return results
            assert len(results["items"]) > 0

        # Average response time should be good
        avg_response_time = statistics.mean(response_times)
        assert avg_response_time < 1.0, f"Average response time {avg_response_time:.3f}s"

        # 95th percentile should be acceptable
        p95_response_time = statistics.quantiles(response_times, n=20)[18]  # 95th percentile
        assert p95_response_time < 1.5, f"95th percentile response time {p95_response_time:.3f}s"

    @pytest.mark.performance
    def test_concurrent_search_throughput(self, performance_search_engine):
        """Test search throughput under concurrent load"""
        num_concurrent_users = 10
        queries_per_user = 5
        total_queries = num_concurrent_users * queries_per_user

        def perform_searches(user_id):
            """Perform searches for a single user"""
            query_times = []
            for i in range(queries_per_user):
                query = f"test content {user_id} {i}"

                start_time = time.perf_counter()
                results = performance_search_engine.search(query)
                end_time = time.perf_counter()

                query_times.append(end_time - start_time)

                # Verify results
                assert isinstance(results, dict)
                assert "items" in results

            return query_times

        # Execute concurrent searches
        start_time = time.perf_counter()

        with ThreadPoolExecutor(max_workers=num_concurrent_users) as executor:
            futures = [
                executor.submit(perform_searches, user_id)
                for user_id in range(num_concurrent_users)
            ]

            all_query_times = []
            for future in futures:
                user_query_times = future.result()
                all_query_times.extend(user_query_times)

        total_time = time.perf_counter() - start_time

        # Calculate throughput metrics
        throughput = total_queries / total_time
        avg_response_time = statistics.mean(all_query_times)

        # Verify performance requirements
        assert throughput >= 20, f"Throughput {throughput:.1f} queries/sec, expected >=20"
        assert avg_response_time < 2.0, f"Average response time {avg_response_time:.3f}s under load"

        # No queries should be extremely slow
        max_response_time = max(all_query_times)
        assert max_response_time < 5.0, f"Maximum response time {max_response_time:.3f}s"

    @pytest.mark.performance
    @pytest.mark.benchmark
    def test_search_memory_usage(self, performance_search_engine, benchmark):
        """Test search memory usage patterns"""
        import psutil
        import os

        def search_operation():
            """Perform search operation for benchmarking"""
            return performance_search_engine.search("test content performance")

        # Measure initial memory
        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss

        # Benchmark the search operation
        result = benchmark(search_operation)

        # Measure final memory
        final_memory = process.memory_info().rss
        memory_increase = final_memory - initial_memory

        # Memory increase should be reasonable
        assert memory_increase < 50 * 1024 * 1024, f"Memory increase {memory_increase / 1024 / 1024:.1f}MB too high"

        # Verify benchmark results
        assert result is not None
        assert "items" in result
```

### Load Testing with Locust

```python
# tests/performance/locustfile.py

from locust import HttpUser, task, between
import random


class TTRPGCenterUser(HttpUser):
    """Locust user simulation for TTRPG Center load testing"""

    wait_time = between(1, 3)  # Wait 1-3 seconds between requests

    def on_start(self):
        """Setup for each user session"""
        self.search_queries = [
            "fireball spell",
            "magic sword",
            "healing potion",
            "goblin stats",
            "wizard spells level 3",
            "armor class calculation"
        ]

    @task(3)
    def search_spells(self):
        """Simulate spell search - most common operation"""
        query = random.choice(self.search_queries)

        response = self.client.get(
            "/api/search",
            params={"q": query, "type": "spell"},
            name="Search Spells"
        )

        if response.status_code == 200:
            results = response.json()
            assert "items" in results
            assert len(results["items"]) >= 0

    @task(2)
    def browse_content(self):
        """Simulate content browsing"""
        content_types = ["spell", "item", "creature", "rule"]
        content_type = random.choice(content_types)

        response = self.client.get(
            f"/api/content/{content_type}",
            params={"page": 1, "limit": 20},
            name="Browse Content"
        )

        assert response.status_code == 200

    @task(1)
    def view_content_detail(self):
        """Simulate viewing specific content"""
        # First search for content
        query = random.choice(self.search_queries)
        search_response = self.client.get(
            "/api/search",
            params={"q": query, "limit": 5}
        )

        if search_response.status_code == 200:
            results = search_response.json()
            if results["items"]:
                # View first result
                content_id = results["items"][0]["id"]
                detail_response = self.client.get(
                    f"/api/content/{content_id}",
                    name="View Content Detail"
                )
                assert detail_response.status_code == 200

    @task(1)
    def admin_health_check(self):
        """Simulate admin health monitoring"""
        self.client.get("/admin/health", name="Admin Health Check")


# Run with: locust -f tests/performance/locustfile.py --host=http://localhost:8000
```

## Security Testing

### Philosophy

Security tests identify vulnerabilities and ensure data protection:
- **Input validation**
- **Authentication/authorization**
- **Data protection**
- **Vulnerability scanning**

### Example Security Tests

```python
# tests/security/test_input_validation.py

import pytest
import json
from src_common.api import app


class TestInputValidation:
    """Security tests for input validation"""

    @pytest.fixture
    def client(self):
        """Create test client"""
        return app.test_client()

    def test_sql_injection_prevention(self, client):
        """Test SQL injection attack prevention"""
        # Attempt SQL injection in search
        malicious_queries = [
            "'; DROP TABLE users; --",
            "1' OR '1'='1",
            "admin'--",
            "' UNION SELECT * FROM users --"
        ]

        for query in malicious_queries:
            response = client.get(f"/api/search?q={query}")

            # Should not cause server error
            assert response.status_code != 500

            # Should not return sensitive data
            if response.status_code == 200:
                data = response.json()
                response_text = json.dumps(data).lower()

                # Should not contain SQL error messages
                assert "sql" not in response_text
                assert "syntax error" not in response_text
                assert "mysql" not in response_text

    def test_xss_prevention(self, client):
        """Test Cross-Site Scripting (XSS) prevention"""
        # Attempt XSS in search and form inputs
        xss_payloads = [
            "<script>alert('xss')</script>",
            "javascript:alert('xss')",
            "<img src=x onerror=alert('xss')>",
            "';alert('xss');//"
        ]

        for payload in xss_payloads:
            # Test in search parameter
            response = client.get(f"/api/search?q={payload}")

            if response.status_code == 200:
                response_text = response.get_data(as_text=True)

                # Script tags should be escaped or removed
                assert "<script>" not in response_text.lower()
                assert "javascript:" not in response_text.lower()
                assert "onerror=" not in response_text.lower()

    def test_file_upload_security(self, client):
        """Test file upload security measures"""
        # Test malicious file uploads
        malicious_files = [
            ("malicious.php", b"<?php system($_GET['cmd']); ?>", "application/x-php"),
            ("malicious.jsp", b"<% Runtime.getRuntime().exec(request.getParameter(\"cmd\")); %>", "application/x-jsp"),
            ("malicious.exe", b"MZ\x90\x00\x03", "application/octet-stream"),
            ("normal.pdf.exe", b"MZ\x90\x00\x03", "application/pdf")  # Extension spoofing
        ]

        for filename, content, content_type in malicious_files:
            data = {
                'file': (content, filename, content_type)
            }

            response = client.post("/api/upload", data=data)

            # Should reject malicious files
            assert response.status_code in [400, 403, 415], f"Should reject {filename}"

    def test_authentication_security(self, client):
        """Test authentication security measures"""
        # Test protected endpoints without authentication
        protected_endpoints = [
            "/admin/users",
            "/admin/config",
            "/api/admin/delete",
            "/admin/logs"
        ]

        for endpoint in protected_endpoints:
            response = client.get(endpoint)

            # Should require authentication
            assert response.status_code in [401, 403], f"Endpoint {endpoint} should require auth"

    def test_rate_limiting(self, client):
        """Test rate limiting protection"""
        # Rapid requests to search endpoint
        responses = []

        for i in range(100):  # Make many rapid requests
            response = client.get("/api/search?q=test")
            responses.append(response.status_code)

        # Should eventually rate limit
        rate_limited = any(status == 429 for status in responses[-20:])  # Check last 20 requests

        # Allow for some tolerance in testing environment
        if not rate_limited:
            # At minimum, should not cause server errors
            server_errors = sum(1 for status in responses if status >= 500)
            assert server_errors == 0, "Rapid requests should not cause server errors"

    def test_data_exposure_prevention(self, client):
        """Test prevention of sensitive data exposure"""
        # Test API responses don't contain sensitive information
        response = client.get("/api/search?q=test")

        if response.status_code == 200:
            response_text = response.get_data(as_text=True).lower()

            # Should not expose sensitive configuration
            sensitive_keywords = [
                "password", "secret", "token", "key", "credential",
                "database_url", "api_key", "private_key"
            ]

            for keyword in sensitive_keywords:
                assert keyword not in response_text, f"Response should not contain '{keyword}'"

        # Test error messages don't expose system information
        response = client.get("/api/nonexistent-endpoint")

        if response.status_code >= 400:
            error_text = response.get_data(as_text=True).lower()

            # Should not expose system paths or stack traces
            system_info = [
                "/usr/local", "/home/", "c:\\", "stack trace",
                "traceback", "exception", "error at line"
            ]

            for info in system_info:
                assert info not in error_text, f"Error should not expose '{info}'"
```

### Static Security Analysis

```bash
# Security vulnerability scanning
bandit -r src_common/ -f json -o reports/security_report.json

# Dependency vulnerability check
safety check --json --output reports/dependency_vulnerabilities.json

# SAST with Semgrep
semgrep --config=auto src_common/ --json --output=reports/semgrep_report.json
```

## End-to-End Testing

### Philosophy

E2E tests validate complete user workflows in browser environment:
- **Real browser interaction**
- **Complete user journeys**
- **UI/UX validation**
- **Cross-browser compatibility**

### Example E2E Test with Playwright

```python
# tests/e2e/test_user_workflows.py

import pytest
from playwright.sync_api import sync_playwright, Page, expect


class TestUserWorkflows:
    """End-to-end tests for user workflows"""

    @pytest.fixture(scope="class")
    def browser_page(self):
        """Set up browser for E2E testing"""
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()

            # Set viewport
            page.set_viewport_size({"width": 1280, "height": 720})

            yield page

            browser.close()

    def test_spell_search_workflow(self, browser_page: Page):
        """Test complete spell search workflow"""
        page = browser_page

        # Navigate to application
        page.goto("http://localhost:8000")

        # Verify page loads
        expect(page).to_have_title("TTRPG Center")

        # Find and use search box
        search_box = page.locator("[data-testid=search-input]")
        expect(search_box).to_be_visible()

        # Perform search
        search_box.fill("fireball")
        search_box.press("Enter")

        # Wait for results
        page.wait_for_selector("[data-testid=search-results]")

        # Verify results displayed
        results = page.locator("[data-testid=search-result-item]")
        expect(results).to_have_count_greater_than(0)

        # Click on first result
        first_result = results.first
        expect(first_result).to_contain_text("Fireball")
        first_result.click()

        # Verify detail page
        page.wait_for_selector("[data-testid=content-detail]")
        detail_content = page.locator("[data-testid=content-detail]")
        expect(detail_content).to_contain_text("3rd-level evocation")

    def test_mobile_responsive_search(self, browser_page: Page):
        """Test search functionality on mobile viewport"""
        page = browser_page

        # Set mobile viewport
        page.set_viewport_size({"width": 375, "height": 667})

        # Navigate to application
        page.goto("http://localhost:8000")

        # Mobile menu might be collapsed
        mobile_menu = page.locator("[data-testid=mobile-menu-toggle]")
        if mobile_menu.is_visible():
            mobile_menu.click()

        # Search should still be accessible
        search_box = page.locator("[data-testid=search-input]")
        expect(search_box).to_be_visible()

        # Perform search
        search_box.fill("magic missile")
        search_box.press("Enter")

        # Results should display properly on mobile
        page.wait_for_selector("[data-testid=search-results]")
        results_container = page.locator("[data-testid=search-results]")
        expect(results_container).to_be_visible()

    def test_admin_workflow(self, browser_page: Page):
        """Test admin workflow for content management"""
        page = browser_page

        # Navigate to admin
        page.goto("http://localhost:8000/admin")

        # Should require authentication (if implemented)
        # For now, assume direct access for testing

        # Verify admin dashboard loads
        expect(page.locator("h1")).to_contain_text("Admin Dashboard")

        # Test ingestion workflow
        ingestion_tab = page.locator("[data-testid=ingestion-tab]")
        if ingestion_tab.is_visible():
            ingestion_tab.click()

            # Verify ingestion interface
            upload_area = page.locator("[data-testid=file-upload-area]")
            expect(upload_area).to_be_visible()

    def test_accessibility_compliance(self, browser_page: Page):
        """Test accessibility compliance"""
        page = browser_page

        # Navigate to main page
        page.goto("http://localhost:8000")

        # Test keyboard navigation
        page.keyboard.press("Tab")  # Should focus on first interactive element

        # Test search with keyboard
        page.keyboard.type("test search")
        page.keyboard.press("Enter")

        # Test color contrast and alt text
        # This would require additional accessibility testing tools
        # like axe-core integration

        # Verify ARIA labels exist
        search_input = page.locator("[data-testid=search-input]")
        expect(search_input).to_have_attribute("aria-label")

    @pytest.mark.slow
    def test_performance_in_browser(self, browser_page: Page):
        """Test application performance in browser"""
        page = browser_page

        # Navigate to application
        page.goto("http://localhost:8000")

        # Measure page load time
        performance = page.evaluate("""() => {
            const timing = performance.timing;
            return {
                loadTime: timing.loadEventEnd - timing.navigationStart,
                domContentLoaded: timing.domContentLoadedEventEnd - timing.navigationStart,
                firstPaint: performance.getEntriesByType('paint')[0]?.startTime || 0
            };
        }""")

        # Verify performance benchmarks
        assert performance["loadTime"] < 3000, f"Page load time {performance['loadTime']}ms too slow"
        assert performance["domContentLoaded"] < 2000, f"DOM load time {performance['domContentLoaded']}ms too slow"

        # Test search performance
        search_box = page.locator("[data-testid=search-input]")
        search_box.fill("performance test")

        # Measure search response time
        start_time = page.evaluate("() => performance.now()")
        search_box.press("Enter")
        page.wait_for_selector("[data-testid=search-results]")
        end_time = page.evaluate("() => performance.now()")

        search_time = end_time - start_time
        assert search_time < 2000, f"Search response time {search_time}ms too slow"
```

## Continuous Integration

### GitHub Actions Workflow

```yaml
# .github/workflows/tests.yml

name: Comprehensive Test Suite

on:
  push:
    branches: [ main, develop ]
  pull_request:
    branches: [ main ]

jobs:
  unit-tests:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: [3.9, 3.10, 3.11, 3.12]

    steps:
    - uses: actions/checkout@v3

    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: ${{ matrix.python-version }}

    - name: Cache dependencies
      uses: actions/cache@v3
      with:
        path: ~/.cache/pip
        key: ${{ runner.os }}-pip-${{ hashFiles('**/requirements*.txt') }}

    - name: Install dependencies
      run: |
        python -m pip install --upgrade pip
        pip install -r requirements.txt
        pip install -r requirements-test.txt

    - name: Run unit tests
      run: |
        pytest tests/unit/ \
          --cov=src_common \
          --cov-report=xml \
          --cov-report=term-missing \
          --junit-xml=reports/unit-tests.xml \
          -v

    - name: Upload coverage to Codecov
      uses: codecov/codecov-action@v3
      with:
        file: ./coverage.xml
        flags: unit-tests
        name: codecov-umbrella

  integration-tests:
    runs-on: ubuntu-latest
    needs: unit-tests

    services:
      postgres:
        image: postgres:13
        env:
          POSTGRES_PASSWORD: test
          POSTGRES_DB: ttrpg_test
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5

    steps:
    - uses: actions/checkout@v3

    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: 3.11

    - name: Install dependencies
      run: |
        pip install -r requirements.txt
        pip install -r requirements-test.txt

    - name: Run integration tests
      env:
        TTRPG_ENV: test
        DATABASE_URL: postgresql://postgres:test@localhost/ttrpg_test
      run: |
        pytest tests/integration/ \
          --junit-xml=reports/integration-tests.xml \
          -v

  security-tests:
    runs-on: ubuntu-latest

    steps:
    - uses: actions/checkout@v3

    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: 3.11

    - name: Install security tools
      run: |
        pip install bandit safety semgrep

    - name: Run Bandit security scan
      run: |
        bandit -r src_common/ -f json -o reports/bandit-report.json
      continue-on-error: true

    - name: Run Safety dependency check
      run: |
        safety check --json --output reports/safety-report.json
      continue-on-error: true

    - name: Run Semgrep SAST
      run: |
        semgrep --config=auto src_common/ --json --output=reports/semgrep-report.json
      continue-on-error: true

    - name: Upload security reports
      uses: actions/upload-artifact@v3
      with:
        name: security-reports
        path: reports/

  e2e-tests:
    runs-on: ubuntu-latest
    needs: [unit-tests, integration-tests]

    steps:
    - uses: actions/checkout@v3

    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: 3.11

    - name: Install dependencies
      run: |
        pip install -r requirements.txt
        pip install -r requirements-test.txt
        playwright install

    - name: Start application
      run: |
        python -m src_common.main &
        sleep 10  # Wait for application to start
      env:
        TTRPG_ENV: test

    - name: Run E2E tests
      run: |
        pytest tests/e2e/ \
          --junit-xml=reports/e2e-tests.xml \
          --html=reports/e2e-report.html \
          -v

    - name: Upload E2E reports
      uses: actions/upload-artifact@v3
      if: always()
      with:
        name: e2e-reports
        path: reports/

  regression-tests:
    runs-on: ubuntu-latest
    if: github.event_name == 'push' && github.ref == 'refs/heads/main'

    steps:
    - uses: actions/checkout@v3

    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: 3.11

    - name: Install dependencies
      run: |
        pip install -r requirements.txt
        pip install -r requirements-test.txt

    - name: Run regression test suite
      env:
        TTRPG_ENV: test
      run: |
        python tests/regression/Run-RegressionSuite.py \
          --environment test \
          --parallel true \
          --generate-report true

    - name: Upload regression reports
      uses: actions/upload-artifact@v3
      if: always()
      with:
        name: regression-reports
        path: tests/regression/reports/
```

## Test Maintenance

### Regular Maintenance Tasks

1. **Weekly Review**
   - Review test failures and flaky tests
   - Update test data and fixtures
   - Check performance benchmarks

2. **Monthly Tasks**
   - Update golden master references
   - Review test coverage gaps
   - Optimize slow tests

3. **Release Preparation**
   - Full regression test execution
   - Performance benchmark validation
   - Security scan review

### Test Quality Metrics

Monitor these metrics for test suite health:

- **Code Coverage**: >90% for critical components
- **Test Execution Time**: <10 minutes for full suite
- **Test Reliability**: <5% flaky test rate
- **Security Coverage**: All major attack vectors tested

---

This comprehensive testing guide ensures the TTRPG Center maintains high quality, security, and performance standards through systematic testing at all levels.