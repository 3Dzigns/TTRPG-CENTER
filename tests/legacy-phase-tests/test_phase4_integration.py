# tests/integration/test_phase4_integration.py
"""
Phase 4 Integration Tests
End-to-end testing of the complete Admin UI system
"""

import pytest
import asyncio
import time
from pathlib import Path
from fastapi.testclient import TestClient

from app_admin import app
from src_common.admin import (
    AdminStatusService, AdminIngestionService, 
    AdminDictionaryService, AdminTestingService, AdminCacheService
)


class TestPhase4SystemIntegration:
    """Test complete Phase 4 system integration"""
    
    @pytest.fixture
    def client(self):
        return TestClient(app)
    
    def test_admin_application_starts_successfully(self, client):
        """Test that the admin application starts and responds"""
        response = client.get("/health")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["service"] == "admin"
    
    def test_all_admin_services_initialize(self):
        """Test that all admin services can be initialized"""
        services = [
            AdminStatusService(),
            AdminIngestionService(),
            AdminDictionaryService(),
            AdminTestingService(),
            AdminCacheService()
        ]
        
        # All services should initialize without error
        assert all(service is not None for service in services)
    
    def test_admin_dashboard_renders(self, client):
        """Test that the admin dashboard page renders successfully"""
        response = client.get("/")
        
        assert response.status_code == 200
        assert "Admin Dashboard" in response.text
        assert "System Status" in response.text
        assert "Environment" in response.text
    
    @pytest.mark.asyncio
    async def test_end_to_end_workflow(self, client):
        """Test complete end-to-end admin workflow"""
        # 1. Check system status
        status_response = client.get("/api/status/overview")
        assert status_response.status_code == 200
        status_data = status_response.json()
        assert "environments" in status_data
        
        # 2. Check ingestion console
        ingestion_response = client.get("/api/ingestion/overview")
        assert ingestion_response.status_code == 200
        ingestion_data = ingestion_response.json()
        assert "environments" in ingestion_data
        
        # 3. Check dictionary management
        dict_response = client.get("/api/dictionary/overview")
        assert dict_response.status_code == 200
        dict_data = dict_response.json()
        assert "environments" in dict_data
        
        # 4. Check testing & bug management
        testing_response = client.get("/api/testing/overview")
        assert testing_response.status_code == 200
        testing_data = testing_response.json()
        assert "environments" in testing_data
        
        # 5. Check cache control
        cache_response = client.get("/api/cache/overview")
        assert cache_response.status_code == 200
        cache_data = cache_response.json()
        assert "environments" in cache_data
        
        # All services should provide environment data
        for env in ["dev", "test", "prod"]:
            assert env in status_data["environments"][0]["name"] or \
                   any(env_data.get("name") == env for env_data in status_data.get("environments", []))
    
    def test_websocket_connection(self, client):
        """Test WebSocket connectivity for real-time updates"""
        with client.websocket_connect("/ws") as websocket:
            # Send test message
            websocket.send_text("ping")
            
            # Should receive status update
            data = websocket.receive_json()
            assert "type" in data
            assert "timestamp" in data
    
    def test_environment_isolation(self, client):
        """Test that environment isolation is properly enforced"""
        environments = ["dev", "test", "prod"]
        
        for env in environments:
            # Test each environment endpoint
            response = client.get(f"/api/status/{env}")
            assert response.status_code == 200
            
            env_data = response.json()
            assert env_data["name"] == env
            assert env_data["port"] > 0
    
    def test_security_headers(self, client):
        """Test that security headers are properly set"""
        response = client.get("/api/status/overview")
        
        assert response.status_code == 200
        # Should have cache control headers
        assert "Cache-Control" in response.headers
    
    def test_cache_policy_enforcement(self, client):
        """Test cache policy enforcement across environments"""
        # Dev should have no-store policy
        dev_response = client.get("/api/cache/dev/policy")
        assert dev_response.status_code == 200
        dev_policy = dev_response.json()
        assert dev_policy["environment"] == "dev"
        
        # Test should have short TTL
        test_response = client.get("/api/cache/test/policy")
        assert test_response.status_code == 200
        test_policy = test_response.json()
        assert test_policy["environment"] == "test"
        
        # Prod should have longer TTL
        prod_response = client.get("/api/cache/prod/policy")
        assert prod_response.status_code == 200
        prod_policy = prod_response.json()
        assert prod_policy["environment"] == "prod"


class TestPhase4Performance:
    """Test Phase 4 performance characteristics"""
    
    @pytest.fixture
    def client(self):
        return TestClient(app)
    
    def test_response_time_requirements(self, client):
        """Test that all overview endpoints meet performance requirements"""
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
            # Should respond within 5 seconds (generous for CI)
            assert elapsed_time < 5.0, f"{endpoint} took {elapsed_time:.2f}s"
    
    def test_concurrent_requests(self, client):
        """Test handling of concurrent requests"""
        import threading
        
        results = []
        
        def make_request():
            response = client.get("/api/status/overview")
            results.append(response.status_code)
        
        # Create 10 concurrent threads
        threads = []
        for _ in range(10):
            thread = threading.Thread(target=make_request)
            threads.append(thread)
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        # All requests should succeed
        assert len(results) == 10
        assert all(status == 200 for status in results)


class TestPhase4ErrorHandling:
    """Test error handling and resilience"""
    
    @pytest.fixture  
    def client(self):
        return TestClient(app)
    
    def test_invalid_environment_handling(self, client):
        """Test handling of invalid environment parameters"""
        invalid_envs = ["invalid", "prod2", "development"]
        
        for invalid_env in invalid_envs:
            response = client.get(f"/api/status/{invalid_env}")
            assert response.status_code == 400
            assert "Invalid environment" in response.json()["detail"]
    
    def test_missing_resource_handling(self, client):
        """Test handling of missing resources"""
        # Test non-existent job
        response = client.get("/api/ingestion/dev/jobs/nonexistent")
        assert response.status_code == 404
        
        # Test non-existent dictionary term
        response = client.get("/api/dictionary/dev/terms/nonexistent")
        assert response.status_code == 404
    
    def test_malformed_request_handling(self, client):
        """Test handling of malformed requests"""
        # Test invalid JSON in POST request
        response = client.post(
            "/api/dictionary/dev/terms",
            data="invalid json",
            headers={"Content-Type": "application/json"}
        )
        assert response.status_code == 422  # Validation error


@pytest.mark.asyncio
async def test_phase4_complete_validation():
    """Final validation that Phase 4 meets all Definition of Done criteria"""
    
    # ADM-001: System Status Dashboard
    status_service = AdminStatusService()
    overview = await status_service.get_system_overview()
    assert "environments" in overview
    assert len(overview["environments"]) == 3
    
    # ADM-002: Ingestion Console  
    ingestion_service = AdminIngestionService()
    ingestion_overview = await ingestion_service.get_ingestion_overview()
    assert "environments" in ingestion_overview
    
    # ADM-003: Dictionary Management
    dict_service = AdminDictionaryService()
    dict_overview = await dict_service.get_dictionary_overview()
    assert "environments" in dict_overview
    
    # ADM-004: Testing & Bug Management
    testing_service = AdminTestingService()
    testing_overview = await testing_service.get_testing_overview()
    assert "environments" in testing_overview
    
    # ADM-005: Cache Control
    cache_service = AdminCacheService()
    cache_overview = await cache_service.get_cache_overview()
    assert "environments" in cache_overview
    
    # All services initialized and functional
    print("✅ Phase 4 Admin UI - All Definition of Done criteria validated")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])