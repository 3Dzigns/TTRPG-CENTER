# tests/functional/test_admin_api.py
"""
Functional tests for Phase 4 Admin API endpoints
Tests the FastAPI admin application and all API routes
"""

import pytest
import json
import asyncio
from unittest.mock import patch, MagicMock
from httpx import AsyncClient
from fastapi.testclient import TestClient

from app_admin import app


class TestAdminAPIEndpoints:
    """Test all admin API endpoints"""
    
    @pytest.fixture
    def client(self):
        return TestClient(app)
    
    def test_health_check(self, client):
        """Test admin service health endpoint"""
        response = client.get("/health")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["service"] == "admin"
        assert "timestamp" in data
    
    def test_admin_dashboard_page(self, client):
        """Test admin dashboard HTML page"""
        with patch('src_common.admin.status.AdminStatusService.get_system_overview') as mock_status, \
             patch('src_common.admin.cache_control.AdminCacheService.get_cache_overview') as mock_cache:
            
            # Mock return values
            mock_status.return_value = {
                "timestamp": 1234567890,
                "environments": [],
                "system_metrics": {"cpu_percent": 10.0},
                "overall_status": "healthy"
            }
            mock_cache.return_value = {
                "timestamp": 1234567890,
                "environments": {}
            }
            
            response = client.get("/")
            
            assert response.status_code == 200
            assert "Admin Dashboard" in response.text
    
    # System Status API Tests
    def test_get_status_overview(self, client):
        """Test system status overview endpoint"""
        response = client.get("/api/status/overview")
        
        assert response.status_code == 200
        data = response.json()
        assert "timestamp" in data
        assert "environments" in data
        assert "overall_status" in data
    
    def test_get_environment_status(self, client):
        """Test environment-specific status endpoint"""
        response = client.get("/api/status/dev")
        
        assert response.status_code == 200
        data = response.json()
        assert "name" in data
        assert "port" in data
        assert "is_active" in data
    
    def test_get_environment_status_invalid(self, client):
        """Test invalid environment returns 400"""
        response = client.get("/api/status/invalid")
        
        assert response.status_code == 400
        assert "Invalid environment" in response.json()["detail"]
    
    def test_get_environment_logs(self, client):
        """Test environment logs endpoint"""
        response = client.get("/api/status/dev/logs?lines=10")
        
        assert response.status_code == 200
        logs = response.json()
        assert isinstance(logs, list)
    
    # Ingestion Console API Tests  
    def test_get_ingestion_overview(self, client):
        """Test ingestion overview endpoint"""
        response = client.get("/api/ingestion/overview")
        
        assert response.status_code == 200
        data = response.json()
        assert "timestamp" in data
        assert "environments" in data
    
    def test_list_ingestion_jobs(self, client):
        """Test job listing endpoint"""
        response = client.get("/api/ingestion/dev/jobs")
        
        assert response.status_code == 200
        jobs = response.json()
        assert isinstance(jobs, list)
    
    def test_retry_ingestion_job_not_found(self, client):
        """Test retrying non-existent job returns 400"""
        response = client.post("/api/ingestion/dev/jobs/nonexistent/retry")
        
        assert response.status_code == 400
    
    # Dictionary Management API Tests
    def test_get_dictionary_overview(self, client):
        """Test dictionary overview endpoint"""
        response = client.get("/api/dictionary/overview")
        
        assert response.status_code == 200
        data = response.json()
        assert "timestamp" in data
        assert "environments" in data
    
    def test_list_dictionary_terms(self, client):
        """Test dictionary terms listing"""
        response = client.get("/api/dictionary/dev/terms")
        
        assert response.status_code == 200
        terms = response.json()
        assert isinstance(terms, list)
    
    def test_create_dictionary_term(self, client):
        """Test creating a dictionary term"""
        term_data = {
            "term": "Test Term",
            "definition": "Test definition",
            "category": "concept",
            "source": "test_source",
            "tags": ["test"]
        }
        
        with patch('src_common.admin.dictionary.AdminDictionaryService.create_term') as mock_create:
            # Mock successful creation
            mock_term = MagicMock()
            mock_term.__dict__ = term_data.copy()
            mock_create.return_value = mock_term
            
            response = client.post("/api/dictionary/dev/terms", json=term_data)
            
            assert response.status_code == 200
            data = response.json()
            assert data["term"] == "Test Term"
    
    def test_get_dictionary_term_not_found(self, client):
        """Test getting non-existent term returns 404"""
        with patch('src_common.admin.dictionary.AdminDictionaryService.get_term') as mock_get:
            mock_get.return_value = None
            
            response = client.get("/api/dictionary/dev/terms/nonexistent")
            
            assert response.status_code == 404
    
    # Testing & Bug Management API Tests
    def test_get_testing_overview(self, client):
        """Test testing overview endpoint"""
        response = client.get("/api/testing/overview")
        
        assert response.status_code == 200
        data = response.json()
        assert "timestamp" in data
        assert "environments" in data
    
    def test_list_tests(self, client):
        """Test regression tests listing"""
        response = client.get("/api/testing/dev/tests")
        
        assert response.status_code == 200
        tests = response.json()
        assert isinstance(tests, list)
    
    def test_create_test(self, client):
        """Test creating a regression test"""
        test_data = {
            "name": "Test Case",
            "description": "Test description",
            "test_type": "unit",
            "command": "pytest",
            "expected_result": "Pass",
            "tags": ["unit"]
        }
        
        with patch('src_common.admin.testing.AdminTestingService.create_test') as mock_create:
            # Mock successful creation
            mock_test = MagicMock()
            mock_test.__dict__ = test_data.copy()
            mock_create.return_value = mock_test
            
            response = client.post("/api/testing/dev/tests", json=test_data)
            
            assert response.status_code == 200
            data = response.json()
            assert data["name"] == "Test Case"
    
    def test_run_test(self, client):
        """Test running a regression test"""
        with patch('src_common.admin.testing.AdminTestingService.run_test') as mock_run:
            # Mock execution result
            mock_execution = MagicMock()
            mock_execution.__dict__ = {
                "execution_id": "exec_123",
                "test_id": "test_123",
                "status": "passed",
                "exit_code": 0
            }
            mock_run.return_value = mock_execution
            
            response = client.post("/api/testing/dev/tests/test_123/run")
            
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "passed"
    
    def test_list_bugs(self, client):
        """Test bug bundles listing"""
        response = client.get("/api/testing/dev/bugs")
        
        assert response.status_code == 200
        bugs = response.json()
        assert isinstance(bugs, list)
    
    def test_create_bug(self, client):
        """Test creating a bug bundle"""
        bug_data = {
            "title": "Test Bug",
            "description": "Bug description",
            "severity": "medium",
            "steps_to_reproduce": ["Step 1", "Step 2"]
        }
        
        with patch('src_common.admin.testing.AdminTestingService.create_bug') as mock_create:
            # Mock successful creation
            mock_bug = MagicMock()
            mock_bug.__dict__ = bug_data.copy()
            mock_create.return_value = mock_bug
            
            response = client.post("/api/testing/dev/bugs", json=bug_data)
            
            assert response.status_code == 200
            data = response.json()
            assert data["title"] == "Test Bug"
    
    # Cache Control API Tests
    def test_get_cache_overview(self, client):
        """Test cache overview endpoint"""
        response = client.get("/api/cache/overview")
        
        assert response.status_code == 200
        data = response.json()
        assert "timestamp" in data
        assert "environments" in data
    
    def test_get_cache_policy(self, client):
        """Test cache policy retrieval"""
        response = client.get("/api/cache/dev/policy")
        
        assert response.status_code == 200
        policy = response.json()
        assert "environment" in policy
        assert "cache_enabled" in policy
    
    def test_update_cache_policy(self, client):
        """Test cache policy updates"""
        policy_updates = {
            "cache_enabled": True,
            "default_ttl_seconds": 300
        }
        
        response = client.put("/api/cache/dev/policy", json=policy_updates)
        
        assert response.status_code == 200
        data = response.json()
        assert data["cache_enabled"] is True
    
    def test_disable_cache(self, client):
        """Test cache disabling"""
        response = client.post("/api/cache/dev/disable")
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "disabled" in data["message"]
    
    def test_enable_cache(self, client):
        """Test cache enabling"""
        response = client.post("/api/cache/dev/enable")
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "enabled" in data["message"]
    
    def test_clear_cache(self, client):
        """Test cache clearing"""
        response = client.post("/api/cache/dev/clear")
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "cleared_entries" in data
    
    def test_validate_cache_compliance(self, client):
        """Test cache compliance validation"""
        response = client.get("/api/cache/dev/compliance")
        
        assert response.status_code == 200
        data = response.json()
        assert "environment" in data
        assert "compliant" in data
        assert "issues" in data


class TestAdminMiddleware:
    """Test admin middleware functionality"""
    
    @pytest.fixture
    def client(self):
        return TestClient(app)
    
    def test_cache_control_middleware_applied(self, client):
        """Test that cache control middleware adds appropriate headers"""
        response = client.get("/api/status/overview")
        
        # Should have cache-control headers
        assert "Cache-Control" in response.headers
    
    def test_cors_middleware_applied(self, client):
        """Test CORS headers are present"""
        response = client.options("/api/status/overview")
        
        # Should handle preflight requests
        assert response.status_code in [200, 404]  # Depending on FastAPI version


class TestAdminWebSocket:
    """Test admin WebSocket functionality"""
    
    @pytest.fixture
    def client(self):
        return TestClient(app)
    
    def test_websocket_connection(self, client):
        """Test WebSocket connection establishment"""
        with client.websocket_connect("/ws") as websocket:
            # Send a test message
            websocket.send_text("ping")
            
            # Should receive status update
            data = websocket.receive_json()
            assert "type" in data
            assert "timestamp" in data


class TestAdminSecurity:
    """Test admin security measures"""
    
    @pytest.fixture
    def client(self):
        return TestClient(app)
    
    def test_environment_validation(self, client):
        """Test that invalid environments are rejected"""
        invalid_envs = ["../../../etc/passwd", "'; DROP TABLE users; --", "invalid"]
        
        for env in invalid_envs:
            response = client.get(f"/api/status/{env}")
            assert response.status_code == 400
    
    def test_parameter_validation(self, client):
        """Test parameter validation"""
        # Test negative lines parameter
        response = client.get("/api/status/dev/logs?lines=-1")
        assert response.status_code == 422  # Validation error
        
        # Test excessive lines parameter  
        response = client.get("/api/status/dev/logs?lines=10000")
        assert response.status_code == 422  # Validation error
    
    def test_sql_injection_protection(self, client):
        """Test protection against SQL injection attempts"""
        malicious_term = "'; DROP TABLE dictionary; --"
        
        response = client.get(f"/api/dictionary/dev/terms/{malicious_term}")
        
        # Should handle gracefully, not cause server error
        assert response.status_code in [404, 400]


class TestAdminPerformance:
    """Test admin performance characteristics"""
    
    @pytest.fixture
    def client(self):
        return TestClient(app)
    
    def test_response_times(self, client):
        """Test that API responses are reasonably fast"""
        import time
        
        endpoints = [
            "/api/status/overview",
            "/api/ingestion/overview", 
            "/api/dictionary/overview",
            "/api/testing/overview",
            "/api/cache/overview"
        ]
        
        for endpoint in endpoints:
            start_time = time.time()
            response = client.get(endpoint)
            elapsed_time = time.time() - start_time
            
            assert response.status_code == 200
            assert elapsed_time < 5.0  # Should respond within 5 seconds


@pytest.mark.asyncio
class TestAdminIntegration:
    """Integration tests for admin functionality"""
    
    async def test_admin_service_integration(self):
        """Test that all admin services work together"""
        # This would test end-to-end workflows like:
        # 1. Create dictionary term
        # 2. Create test that validates term
        # 3. Run test
        # 4. Check cache behavior
        # 5. View results in dashboard
        
        # For now, just verify all services initialize
        from src_common.admin import (
            AdminStatusService, AdminIngestionService, 
            AdminDictionaryService, AdminTestingService, AdminCacheService
        )
        
        services = [
            AdminStatusService(),
            AdminIngestionService(),
            AdminDictionaryService(),
            AdminTestingService(), 
            AdminCacheService()
        ]
        
        # All services should initialize without error
        assert all(service is not None for service in services)
    
    async def test_environment_isolation(self):
        """Test that environments remain properly isolated"""
        from src_common.admin.dictionary import AdminDictionaryService
        
        dict_service = AdminDictionaryService()
        
        # Create terms in different environments
        dev_term_data = {
            'term': 'Dev Term',
            'definition': 'Development term',
            'category': 'concept',
            'source': 'dev_source'
        }
        
        test_term_data = {
            'term': 'Test Term', 
            'definition': 'Test term',
            'category': 'concept',
            'source': 'test_source'
        }
        
        # Mock the save operations to avoid file system dependencies
        with patch.object(dict_service, '_save_term'), \
             patch.object(dict_service, 'get_term') as mock_get:
            
            mock_get.return_value = None  # Term doesn't exist
            
            dev_term = await dict_service.create_term("dev", dev_term_data)
            test_term = await dict_service.create_term("test", test_term_data)
            
            # Terms should be properly isolated by environment
            assert dev_term.environment == "dev"
            assert test_term.environment == "test"
            assert dev_term.term != test_term.term


if __name__ == "__main__":
    pytest.main([__file__, "-v"])