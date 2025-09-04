# tests/functional/test_health_endpoint.py
"""
Functional tests for health check endpoint.
"""

import json
import time

import pytest
from fastapi.testclient import TestClient


def test_health_endpoint_returns_ok(test_client: TestClient, mock_environment):
    """Test that /healthz endpoint returns 200 with correct structure."""
    response = test_client.get("/healthz")
    
    assert response.status_code == 200
    
    data = response.json()
    assert data["status"] == "ok"
    assert data["environment"] == "test"
    assert data["port"] == "8181"
    assert data["version"] == "0.1.0"
    assert "timestamp" in data
    assert isinstance(data["timestamp"], (int, float))


def test_health_endpoint_includes_environment_info(test_client: TestClient, mock_environment):
    """Test that health endpoint includes correct environment information."""
    response = test_client.get("/healthz")
    
    assert response.status_code == 200
    
    data = response.json()
    
    # Should reflect the test environment setup
    assert data["environment"] == "test"
    assert data["port"] == "8181"
    
    # Timestamp should be recent (within last 10 seconds)
    current_time = time.time()
    assert abs(current_time - data["timestamp"]) < 10


def test_health_endpoint_response_time(test_client: TestClient, mock_environment, performance_monitor):
    """Test that health endpoint responds quickly."""
    performance_monitor.start("health_check")
    
    response = test_client.get("/healthz")
    
    duration = performance_monitor.end("health_check")
    
    assert response.status_code == 200
    
    # Health check should be very fast (< 100ms)
    performance_monitor.assert_under_threshold("health_check", 100.0)


def test_root_endpoint_returns_basic_info(test_client: TestClient, mock_environment):
    """Test that root endpoint returns basic API information."""
    response = test_client.get("/")
    
    assert response.status_code == 200
    
    data = response.json()
    assert data["message"] == "TTRPG Center API"
    assert data["environment"] == "test"
    assert data["version"] == "0.1.0"
    assert data["health_check"] == "/healthz"


def test_status_endpoint_returns_system_info(test_client: TestClient, mock_environment):
    """Test that /status endpoint returns detailed system information."""
    response = test_client.get("/status")
    
    assert response.status_code == 200
    
    data = response.json()
    
    # Basic info
    assert data["environment"] == "test"
    assert "timestamp" in data
    
    # Directory info
    assert "directories" in data
    directories = data["directories"]
    assert "artifacts" in directories
    assert "artifacts_exists" in directories
    assert "logs" in directories
    assert "logs_exists" in directories
    
    # WebSocket info
    assert "websockets" in data
    assert "active_connections" in data["websockets"]
    
    # Configuration info
    assert "configuration" in data
    config = data["configuration"]
    assert config["port"] == "8181"
    assert config["log_level"] == "INFO"
    assert config["cache_ttl"] == "5"


@pytest.mark.asyncio
async def test_health_endpoint_async(async_client):
    """Test health endpoint with async client."""
    response = await async_client.get("/healthz")
    
    assert response.status_code == 200
    
    data = response.json()
    assert data["status"] == "ok"
    assert "timestamp" in data


class TestHealthEndpointInDifferentEnvironments:
    """Test health endpoint behavior across different environments."""
    
    def test_health_endpoint_dev_environment(self, test_client: TestClient, monkeypatch):
        """Test health endpoint in dev environment."""
        monkeypatch.setenv("APP_ENV", "dev")
        monkeypatch.setenv("PORT", "8000")
        
        response = test_client.get("/healthz")
        data = response.json()
        
        assert data["environment"] == "dev"
        assert data["port"] == "8000"
    
    def test_health_endpoint_prod_environment(self, test_client: TestClient, monkeypatch):
        """Test health endpoint in production environment.""" 
        monkeypatch.setenv("APP_ENV", "prod")
        monkeypatch.setenv("PORT", "8282")
        
        response = test_client.get("/healthz")
        data = response.json()
        
        assert data["environment"] == "prod"
        assert data["port"] == "8282"
    
    def test_health_endpoint_unknown_environment(self, test_client: TestClient, monkeypatch):
        """Test health endpoint with unknown environment."""
        # Clear environment variables
        monkeypatch.delenv("APP_ENV", raising=False)
        monkeypatch.delenv("PORT", raising=False)
        
        response = test_client.get("/healthz")
        data = response.json()
        
        assert data["environment"] == "unknown"
        assert data["port"] == "unknown"


class TestHealthEndpointCaching:
    """Test caching behavior of health endpoint."""
    
    def test_health_endpoint_cache_headers_dev(self, test_client: TestClient, monkeypatch):
        """Test that dev environment uses no-cache headers."""
        monkeypatch.setenv("APP_ENV", "dev")
        monkeypatch.setenv("CACHE_TTL_SECONDS", "0")
        
        response = test_client.get("/healthz")
        
        # Should have cache control headers for dev
        assert response.status_code == 200
        
        # Note: FastAPI doesn't automatically add cache headers,
        # this test documents expected behavior for future implementation
    
    def test_health_endpoint_multiple_calls_show_different_timestamps(self, test_client: TestClient, mock_environment):
        """Test that multiple health checks show progression of time."""
        # First call
        response1 = test_client.get("/healthz")
        data1 = response1.json()
        
        # Small delay
        time.sleep(0.01)
        
        # Second call
        response2 = test_client.get("/healthz")
        data2 = response2.json()
        
        # Timestamps should be different
        assert data2["timestamp"] > data1["timestamp"]
        
        # Other fields should be the same
        assert data1["status"] == data2["status"]
        assert data1["environment"] == data2["environment"]


class TestHealthEndpointErrorHandling:
    """Test error handling in health endpoint."""
    
    def test_health_endpoint_survives_missing_env_vars(self, test_client: TestClient, monkeypatch):
        """Test that health endpoint works even with missing environment variables."""
        # Remove all environment variables that might affect health check
        for var in ["APP_ENV", "PORT", "LOG_LEVEL"]:
            monkeypatch.delenv(var, raising=False)
        
        response = test_client.get("/healthz")
        
        # Should still return 200 with default values
        assert response.status_code == 200
        
        data = response.json()
        assert data["status"] == "ok"
        assert "environment" in data  # May be "unknown"
        assert "port" in data  # May be "unknown"
    
    def test_health_endpoint_concurrent_requests(self, test_client: TestClient, mock_environment):
        """Test health endpoint under concurrent load."""
        import concurrent.futures
        import threading
        
        def make_health_request():
            return test_client.get("/healthz")
        
        # Make 10 concurrent requests
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(make_health_request) for _ in range(10)]
            responses = [future.result() for future in concurrent.futures.as_completed(futures)]
        
        # All should succeed
        for response in responses:
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "ok"