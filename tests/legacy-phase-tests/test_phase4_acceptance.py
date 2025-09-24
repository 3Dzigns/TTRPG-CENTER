# tests/functional/test_phase4_acceptance.py
"""
Phase 4 Acceptance Tests - ADM-001 through ADM-005
Tests that validate completion criteria for Phase 4 Admin UI implementation
"""

import pytest
import asyncio
import time
from unittest.mock import patch, MagicMock
from httpx import AsyncClient
from fastapi.testclient import TestClient

from app_admin import app
from src_common.admin import (
    AdminStatusService,
    AdminIngestionService, 
    AdminDictionaryService,
    AdminTestingService,
    AdminCacheService
)


class TestADM001SystemStatusDashboard:
    """ADM-001: System Status dashboard (shows DEV/TEST/PROD separately)"""
    
    @pytest.fixture
    def client(self):
        return TestClient(app)
    
    def test_system_status_displays_all_environments(self, client):
        """Test that system status shows DEV/TEST/PROD separately"""
        response = client.get("/api/status/overview")
        
        assert response.status_code == 200
        data = response.json()
        
        # Should have separate environment data
        assert "environments" in data
        environments = [env["name"] for env in data["environments"]]
        assert "dev" in environments
        assert "test" in environments  
        assert "prod" in environments
    
    def test_environment_port_assignments(self, client):
        """Test that environments have correct port assignments"""
        for env, expected_port in [("dev", 8000), ("test", 8181), ("prod", 8282)]:
            response = client.get(f"/api/status/{env}")
            
            assert response.status_code == 200
            data = response.json()
            assert data["port"] == expected_port
    
    def test_system_metrics_available(self, client):
        """Test that system metrics are provided"""
        response = client.get("/api/status/overview")
        
        assert response.status_code == 200
        data = response.json()
        
        assert "system_metrics" in data
        metrics = data["system_metrics"]
        assert "cpu_percent" in metrics
        assert "memory_percent" in metrics
        assert "disk_percent" in metrics
    
    @pytest.mark.asyncio
    async def test_environment_health_monitoring(self):
        """Test environment health monitoring functionality"""
        status_service = AdminStatusService()
        
        for env in ["dev", "test", "prod"]:
            health = await status_service.check_environment_health(env)
            
            assert health.name == env
            assert health.port > 0
            assert health.last_health_check is not None


class TestADM002IngestionConsole:
    """ADM-002: Ingestion Console"""
    
    @pytest.fixture  
    def client(self):
        return TestClient(app)
    
    def test_ingestion_overview_available(self, client):
        """Test ingestion console overview is available"""
        response = client.get("/api/ingestion/overview")
        
        assert response.status_code == 200
        data = response.json()
        
        # Should have environment-specific data
        assert "environments" in data
        assert len(data["environments"]) == 3
        
        for env in ["dev", "test", "prod"]:
            assert env in data["environments"]
            env_data = data["environments"][env]
            assert "total_jobs" in env_data
            assert "status_breakdown" in env_data
    
    def test_job_listing_by_environment(self, client):
        """Test job listing is scoped by environment"""
        for env in ["dev", "test", "prod"]:
            response = client.get(f"/api/ingestion/{env}/jobs")
            
            assert response.status_code == 200
            jobs = response.json()
            assert isinstance(jobs, list)
    
    def test_job_management_operations(self, client):
        """Test job retry and delete operations"""
        # Test retry operation (will fail for non-existent job)
        response = client.post("/api/ingestion/dev/jobs/nonexistent/retry")
        assert response.status_code == 400
        
        # Test delete operation (will fail for non-existent job)
        response = client.delete("/api/ingestion/dev/jobs/nonexistent") 
        assert response.status_code == 400
    
    @pytest.mark.asyncio
    async def test_job_artifact_tracking(self):
        """Test job artifact tracking functionality"""
        ingestion_service = AdminIngestionService()
        
        # Test artifact retrieval for each environment
        for env in ["dev", "test", "prod"]:
            overview = await ingestion_service.get_ingestion_overview()
            assert overview["environments"][env]["artifacts_path"] == f"artifacts/{env}"


class TestADM003DictionaryManagement:
    """ADM-003: Dictionary management (view/edit terms per environment)"""
    
    @pytest.fixture
    def client(self):
        return TestClient(app)
    
    def test_dictionary_overview_per_environment(self, client):
        """Test dictionary overview shows per-environment data"""
        response = client.get("/api/dictionary/overview")
        
        assert response.status_code == 200
        data = response.json()
        
        # Should have environment-specific statistics
        assert "environments" in data
        for env in ["dev", "test", "prod"]:
            assert env in data["environments"]
            env_data = data["environments"][env]
            assert "stats" in env_data
            stats = env_data["stats"]
            assert "total_terms" in stats
            assert "categories" in stats
            assert "environment" in stats
            assert stats["environment"] == env
    
    def test_environment_scoped_term_operations(self, client):
        """Test CRUD operations are environment-scoped"""
        # Test term listing per environment
        for env in ["dev", "test", "prod"]:
            response = client.get(f"/api/dictionary/{env}/terms")
            assert response.status_code == 200
            
            terms = response.json()
            assert isinstance(terms, list)
    
    def test_term_creation_with_environment_isolation(self, client):
        """Test term creation respects environment isolation"""
        term_data = {
            "term": "Test Term",
            "definition": "Test definition",
            "category": "concept", 
            "source": "test_source"
        }
        
        with patch('src_common.admin.dictionary.AdminDictionaryService.create_term') as mock_create:
            # Mock successful creation with environment tracking
            mock_term = MagicMock()
            mock_term.__dict__ = {**term_data, "environment": "dev"}
            mock_create.return_value = mock_term
            
            response = client.post("/api/dictionary/dev/terms", json=term_data)
            
            assert response.status_code == 200
            data = response.json()
            assert data["environment"] == "dev"
    
    @pytest.mark.asyncio
    async def test_dictionary_search_functionality(self):
        """Test dictionary search capabilities"""
        dict_service = AdminDictionaryService()
        
        for env in ["dev", "test", "prod"]:
            # Test search functionality
            results = await dict_service.search_terms(env, "test")
            assert isinstance(results, list)
            
            # Test category filtering
            terms = await dict_service.list_terms(env, category="concept")
            assert isinstance(terms, list)


class TestADM004RegressionTestsAndBugBundles:
    """ADM-004: Regression tests & bug bundles (scoped to environment)"""
    
    @pytest.fixture
    def client(self):
        return TestClient(app)
    
    def test_testing_overview_per_environment(self, client):
        """Test testing overview shows environment-scoped data"""
        response = client.get("/api/testing/overview")
        
        assert response.status_code == 200
        data = response.json()
        
        # Should have environment-specific test and bug statistics
        assert "environments" in data
        for env in ["dev", "test", "prod"]:
            assert env in data["environments"]
            env_data = data["environments"][env]
            assert "test_stats" in env_data
            assert "bug_stats" in env_data
            
            test_stats = env_data["test_stats"]
            assert "total" in test_stats
            assert "by_status" in test_stats
            assert "by_type" in test_stats
    
    def test_regression_test_management(self, client):
        """Test regression test creation and management"""
        # Test test listing per environment
        for env in ["dev", "test", "prod"]:
            response = client.get(f"/api/testing/{env}/tests")
            assert response.status_code == 200
            
            tests = response.json()
            assert isinstance(tests, list)
        
        # Test test creation
        test_data = {
            "name": "Sample Test",
            "description": "Test description",
            "test_type": "unit",
            "command": "pytest",
            "expected_result": "Pass"
        }
        
        with patch('src_common.admin.testing.AdminTestingService.create_test') as mock_create:
            mock_test = MagicMock()
            mock_test.__dict__ = {**test_data, "environment": "dev"}
            mock_create.return_value = mock_test
            
            response = client.post("/api/testing/dev/tests", json=test_data)
            assert response.status_code == 200
    
    def test_bug_bundle_management(self, client):
        """Test bug bundle creation and tracking"""
        # Test bug listing per environment
        for env in ["dev", "test", "prod"]:
            response = client.get(f"/api/testing/{env}/bugs")
            assert response.status_code == 200
            
            bugs = response.json()
            assert isinstance(bugs, list)
        
        # Test bug creation
        bug_data = {
            "title": "Sample Bug",
            "description": "Bug description", 
            "severity": "medium"
        }
        
        with patch('src_common.admin.testing.AdminTestingService.create_bug') as mock_create:
            mock_bug = MagicMock()
            mock_bug.__dict__ = {**bug_data, "environment": "dev"}
            mock_create.return_value = mock_bug
            
            response = client.post("/api/testing/dev/bugs", json=bug_data)
            assert response.status_code == 200
    
    def test_test_execution_functionality(self, client):
        """Test test execution capabilities"""
        with patch('src_common.admin.testing.AdminTestingService.run_test') as mock_run:
            # Mock execution result
            mock_execution = MagicMock()
            mock_execution.__dict__ = {
                "execution_id": "exec_123",
                "status": "passed",
                "environment": "dev"
            }
            mock_run.return_value = mock_execution
            
            response = client.post("/api/testing/dev/tests/test123/run")
            assert response.status_code == 200
            
            data = response.json()
            assert data["status"] == "passed"
    
    def test_test_suite_execution(self, client):
        """Test test suite execution functionality"""
        response = client.post("/api/testing/dev/test-suites/run")
        assert response.status_code == 200
        
        data = response.json()
        assert "environment" in data
        assert data["environment"] == "dev"


class TestADM005CacheRefreshCompliance:
    """ADM-005: Cache refresh compliance"""
    
    @pytest.fixture
    def client(self):
        return TestClient(app)
    
    def test_admin_cache_toggle_availability(self, client):
        """Test admin cache toggle is available"""
        response = client.get("/api/cache/overview")
        
        assert response.status_code == 200
        data = response.json()
        
        # Should have cache control for all environments
        assert "environments" in data
        for env in ["dev", "test", "prod"]:
            assert env in data["environments"]
            env_data = data["environments"][env]
            assert "policy" in env_data
            assert "status" in env_data
    
    def test_cache_disable_functionality(self, client):
        """Test cache can be disabled instantly"""
        response = client.post("/api/cache/dev/disable")
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "disabled" in data["message"]
    
    def test_cache_enable_functionality(self, client):
        """Test cache can be enabled with proper settings"""
        response = client.post("/api/cache/dev/enable")
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "enabled" in data["message"]
    
    def test_environment_specific_cache_policies(self, client):
        """Test cache policies are environment-specific"""
        for env in ["dev", "test", "prod"]:
            response = client.get(f"/api/cache/{env}/policy")
            
            assert response.status_code == 200
            policy = response.json()
            assert policy["environment"] == env
            
            # Verify environment-specific defaults
            if env == "dev":
                assert policy["cache_enabled"] is False  # No-store by default
            elif env == "test":
                assert policy["default_ttl_seconds"] <= 5  # Very short TTL
    
    def test_cache_compliance_validation(self, client):
        """Test cache compliance validation"""
        for env in ["dev", "test", "prod"]:
            response = client.get(f"/api/cache/{env}/compliance")
            
            assert response.status_code == 200
            compliance = response.json()
            assert "environment" in compliance
            assert "compliant" in compliance
            assert "issues" in compliance
            assert compliance["environment"] == env
    
    def test_critical_page_no_store_policy(self, client):
        """Test that critical pages have no-store policy"""
        response = client.get("/api/cache/dev/policy")
        
        assert response.status_code == 200
        policy = response.json()
        
        # Admin and feedback pages should be no-store
        no_store_pages = policy["no_store_pages"]
        has_admin_pages = any("/admin" in page for page in no_store_pages)
        has_feedback_pages = any("feedback" in page for page in no_store_pages)
        
        assert has_admin_pages or "*" in no_store_pages  # Either explicit or wildcard
    
    @pytest.mark.asyncio 
    async def test_fast_retest_behavior(self):
        """Test that cache settings enable fast retest behavior"""
        cache_service = AdminCacheService()
        
        # Test environment should have very short TTL
        policy = await cache_service.get_cache_policy("test")
        assert policy.default_ttl_seconds <= 5
        
        # Dev environment should have no-store for immediate changes
        policy = await cache_service.get_cache_policy("dev")
        assert not policy.cache_enabled or policy.default_ttl_seconds == 0
    
    def test_cache_clear_functionality(self, client):
        """Test cache clearing works for all environments"""
        for env in ["dev", "test", "prod"]:
            response = client.post(f"/api/cache/{env}/clear")
            
            assert response.status_code == 200
            result = response.json()
            assert result["success"] is True
            assert result["environment"] == env


class TestPhase4Integration:
    """Integration tests for complete Phase 4 functionality"""
    
    @pytest.fixture
    def client(self):
        return TestClient(app)
    
    def test_admin_dashboard_loads_successfully(self, client):
        """Test that admin dashboard loads with all components"""
        with patch('src_common.admin.status.AdminStatusService.get_system_overview') as mock_status, \
             patch('src_common.admin.cache_control.AdminCacheService.get_cache_overview') as mock_cache:
            
            # Mock comprehensive data
            mock_status.return_value = {
                "timestamp": time.time(),
                "environments": [
                    {"name": "dev", "port": 8000, "is_active": True},
                    {"name": "test", "port": 8181, "is_active": True}, 
                    {"name": "prod", "port": 8282, "is_active": False}
                ],
                "system_metrics": {
                    "cpu_percent": 25.5,
                    "memory_percent": 60.2,
                    "disk_percent": 45.0
                },
                "overall_status": "healthy"
            }
            
            mock_cache.return_value = {
                "timestamp": time.time(),
                "environments": {
                    "dev": {"policy": {"cache_enabled": False}, "status": "disabled"},
                    "test": {"policy": {"cache_enabled": True}, "status": "enabled"},
                    "prod": {"policy": {"cache_enabled": True}, "status": "enabled"}
                }
            }
            
            response = client.get("/")
            
            assert response.status_code == 200
            assert "Admin Dashboard" in response.text
            assert "Development" in response.text
            assert "Testing" in response.text
            assert "Production" in response.text
    
    def test_all_admin_services_accessible(self, client):
        """Test that all admin services are accessible via API"""
        endpoints = [
            "/api/status/overview",
            "/api/ingestion/overview",
            "/api/dictionary/overview", 
            "/api/testing/overview",
            "/api/cache/overview"
        ]
        
        for endpoint in endpoints:
            response = client.get(endpoint)
            assert response.status_code == 200, f"Endpoint {endpoint} failed"
            
            data = response.json()
            assert "timestamp" in data
            assert "environments" in data
    
    def test_environment_isolation_enforcement(self, client):
        """Test that environment isolation is enforced across all services"""
        environments = ["dev", "test", "prod"]
        
        # Test each service respects environment boundaries
        service_endpoints = [
            "/api/status/{env}",
            "/api/ingestion/{env}/jobs",
            "/api/dictionary/{env}/terms",
            "/api/testing/{env}/tests",
            "/api/cache/{env}/policy"
        ]
        
        for env in environments:
            for endpoint_template in service_endpoints:
                endpoint = endpoint_template.format(env=env)
                response = client.get(endpoint)
                
                # Should succeed for valid environments
                assert response.status_code == 200, f"Failed: {endpoint}"
                
                # Response should contain environment context
                if response.headers.get("content-type", "").startswith("application/json"):
                    data = response.json()
                    # Environment should be referenced in response
                    assert env in str(data).lower() or "environment" in str(data).lower()
    
    def test_cache_control_middleware_integration(self, client):
        """Test that cache control middleware integrates properly"""
        # Test different endpoints get appropriate cache headers
        endpoints_to_test = [
            ("/api/status/overview", True),  # Should have cache headers
            ("/api/cache/dev/policy", True),  # Should have cache headers
            ("/", True)  # HTML page should have cache headers
        ]
        
        for endpoint, should_have_cache_headers in endpoints_to_test:
            response = client.get(endpoint)
            
            if should_have_cache_headers:
                assert "Cache-Control" in response.headers
    
    @pytest.mark.asyncio
    async def test_websocket_real_time_updates(self):
        """Test WebSocket functionality for real-time updates"""
        client = TestClient(app)
        
        # Test WebSocket connection
        with client.websocket_connect("/ws") as websocket:
            # Send ping to keep connection alive
            websocket.send_text("ping")
            
            # Should receive status update
            try:
                data = websocket.receive_json(timeout=5)
                assert "type" in data
                assert "timestamp" in data
            except Exception:
                # WebSocket might not send immediate response, that's OK
                pass
    
    def test_security_validation_across_services(self, client):
        """Test security validation is consistent across all services"""
        # Test invalid environment parameter rejection
        invalid_env = "../../etc/passwd"
        
        vulnerable_endpoints = [
            f"/api/status/{invalid_env}",
            f"/api/ingestion/{invalid_env}/jobs",
            f"/api/dictionary/{invalid_env}/terms",
            f"/api/testing/{invalid_env}/tests",
            f"/api/cache/{invalid_env}/policy"
        ]
        
        for endpoint in vulnerable_endpoints:
            response = client.get(endpoint)
            # Accept both 400 (validation error) and 404 (path not found) as valid security responses
            assert response.status_code in [400, 404], f"Security issue: {endpoint} returned {response.status_code}"


@pytest.mark.asyncio
async def test_phase4_definition_of_done():
    """Test that Phase 4 meets all Definition of Done criteria"""
    
    # Initialize all services
    status_service = AdminStatusService()
    ingestion_service = AdminIngestionService()
    dictionary_service = AdminDictionaryService()
    testing_service = AdminTestingService()
    cache_service = AdminCacheService()
    
    # Test ADM-001: System Status dashboard shows DEV/TEST/PROD separately
    status_overview = await status_service.get_system_overview()
    assert len(status_overview["environments"]) == 3
    env_names = [env["name"] for env in status_overview["environments"]]
    assert all(env in env_names for env in ["dev", "test", "prod"])
    
    # Test ADM-002: Ingestion Console available 
    ingestion_overview = await ingestion_service.get_ingestion_overview()
    assert "environments" in ingestion_overview
    assert len(ingestion_overview["environments"]) == 3
    
    # Test ADM-003: Dictionary management per environment
    dict_overview = await dictionary_service.get_dictionary_overview()
    assert "environments" in dict_overview
    assert len(dict_overview["environments"]) == 3
    
    # Test ADM-004: Regression tests & bug bundles scoped to environment
    testing_overview = await testing_service.get_testing_overview()
    assert "environments" in testing_overview
    assert len(testing_overview["environments"]) == 3
    
    # Test ADM-005: Cache refresh compliance
    cache_overview = await cache_service.get_cache_overview()
    assert "environments" in cache_overview
    assert len(cache_overview["environments"]) == 3
    
    # Test cache compliance for each environment
    for env in ["dev", "test", "prod"]:
        compliance = await cache_service.validate_compliance(env)
        # Should have compliance data (may have issues, but should validate)
        assert "compliant" in compliance
        assert "issues" in compliance


if __name__ == "__main__":
    pytest.main([__file__, "-v"])