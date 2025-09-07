# test_fr_sec_402_cors.py
"""
FR-SEC-402: CORS Security Configuration Tests
Unit and integration tests for secure CORS implementation
"""

import pytest
import os
from unittest.mock import patch, MagicMock
from fastapi import FastAPI
from fastapi.testclient import TestClient
from fastapi.middleware.cors import CORSMiddleware

from src_common.cors_security import (
    CORSConfigLoader,
    CORSMonitoringMiddleware,
    setup_secure_cors,
    validate_cors_startup,
    get_cors_health_status,
    CORS_CONFIG,
    SECURITY_HEADERS
)


class TestCORSConfigLoader:
    """Test CORS configuration loading and validation"""
    
    def test_dev_environment_config_valid(self):
        """Test development environment CORS configuration"""
        loader = CORSConfigLoader("dev")
        config = loader.get_cors_config()
        
        assert "allow_origins" in config
        assert "allow_credentials" in config
        assert config["allow_credentials"] is True
        assert config["max_age"] == 300
        
        # Dev should allow localhost origins
        origins = config["allow_origins"]
        assert any("localhost" in origin for origin in origins)
        assert any("127.0.0.1" in origin for origin in origins)
    
    def test_prod_environment_requires_https(self):
        """Test production environment enforces HTTPS origins"""
        loader = CORSConfigLoader("prod")
        config = loader.get_cors_config()
        
        # All production origins must use HTTPS
        for origin in config["allow_origins"]:
            assert origin.startswith("https://"), f"Production origin must use HTTPS: {origin}"
    
    def test_wildcard_origins_rejected(self):
        """Test wildcard origins are rejected in security validation"""
        # Mock configuration with wildcard
        with patch.dict(CORS_CONFIG, {
            "test": {
                "allow_origins": ["*"],
                "allow_credentials": True,
                "max_age": 300
            }
        }):
            loader = CORSConfigLoader("test")
            
            with pytest.raises(ValueError, match="Wildcard origins not allowed"):
                loader.get_cors_config()
    
    def test_invalid_environment_raises_error(self):
        """Test invalid environment parameter raises appropriate error"""
        with pytest.raises(ValueError, match="Invalid environment"):
            CORSConfigLoader("invalid")
    
    def test_missing_config_raises_error(self):
        """Test missing configuration for environment raises error"""
        # Mock empty config
        with patch.dict(CORS_CONFIG, {}, clear=True):
            loader = CORSConfigLoader("dev")
            
            with pytest.raises(ValueError, match="No CORS config for environment"):
                loader.get_cors_config()


class TestCORSMonitoringMiddleware:
    """Test CORS monitoring and logging functionality"""
    
    @pytest.fixture
    def mock_logger(self):
        """Mock logger for testing"""
        with patch('src_common.cors_security.logger') as mock_log:
            yield mock_log
    
    @pytest.fixture
    def test_app(self):
        """Test FastAPI application"""
        app = FastAPI()
        
        @app.get("/test")
        async def test_endpoint():
            return {"message": "test"}
        
        return app
    
    def test_allowed_origin_passes_through(self, test_app, mock_logger):
        """Test requests from allowed origins pass through"""
        allowed_origins = ["https://example.com"]
        middleware = CORSMonitoringMiddleware(test_app, allowed_origins)
        
        # Add middleware to app for testing
        test_app.add_middleware(type(middleware), allowed_origins=allowed_origins)
        
        client = TestClient(test_app)
        response = client.get("/test", headers={"origin": "https://example.com"})
        
        assert response.status_code == 200
        # Should not log blocked request
        mock_logger.warning.assert_not_called()
    
    def test_blocked_origin_logged(self, test_app, mock_logger):
        """Test requests from blocked origins are logged"""
        allowed_origins = ["https://example.com"]
        middleware = CORSMonitoringMiddleware(test_app, allowed_origins)
        
        # Add middleware to app for testing
        test_app.add_middleware(type(middleware), allowed_origins=allowed_origins)
        
        client = TestClient(test_app)
        response = client.get("/test", headers={"origin": "https://evil.com"})
        
        # Request should still go through (CORS is handled by CORSMiddleware)
        # But should be logged as blocked
        mock_logger.warning.assert_called_once()
        
        # Check log call details
        call_args = mock_logger.warning.call_args
        assert "CORS request blocked" in call_args[0][0]
        assert "origin" in call_args[1]["extra"]
        assert call_args[1]["extra"]["origin"] == "https://evil.com"


class TestCORSIntegration:
    """Integration tests for CORS security setup"""
    
    @pytest.fixture
    def test_app(self):
        """Test FastAPI application"""
        app = FastAPI()
        
        @app.get("/api/test")
        async def test_endpoint():
            return {"message": "success"}
        
        return app
    
    def test_setup_secure_cors_dev_environment(self, test_app):
        """Test secure CORS setup for development environment"""
        with patch.dict(os.environ, {"ENVIRONMENT": "dev"}):
            setup_secure_cors(test_app, "dev")
            
            # Check that CORS middleware was added
            cors_middlewares = [
                m for m in test_app.user_middleware
                if m.cls == CORSMiddleware
            ]
            assert len(cors_middlewares) > 0
            
            client = TestClient(test_app)
            
            # Test preflight request
            response = client.options(
                "/api/test",
                headers={
                    "origin": "http://localhost:3000",
                    "access-control-request-method": "GET"
                }
            )
            
            assert response.status_code == 200
            assert "access-control-allow-origin" in response.headers
    
    def test_blocked_origin_request_fails(self, test_app):
        """Test requests from non-allowed origins are blocked"""
        setup_secure_cors(test_app, "dev")
        
        client = TestClient(test_app)
        
        # Test request from blocked origin
        response = client.get(
            "/api/test",
            headers={"origin": "https://evil.com"}
        )
        
        # Should not have CORS headers for blocked origin
        assert "access-control-allow-origin" not in response.headers
    
    def test_allowed_methods_restricted(self, test_app):
        """Test only allowed HTTP methods are permitted"""
        setup_secure_cors(test_app, "dev")
        
        client = TestClient(test_app)
        
        # Test preflight for allowed method
        response = client.options(
            "/api/test",
            headers={
                "origin": "http://localhost:3000",
                "access-control-request-method": "GET"
            }
        )
        
        assert response.status_code == 200
        assert "GET" in response.headers.get("access-control-allow-methods", "")
        
        # Trace method should not be allowed
        assert "TRACE" not in response.headers.get("access-control-allow-methods", "")
    
    def test_credentials_allowed_for_trusted_origins(self, test_app):
        """Test credentials are allowed for trusted origins"""
        setup_secure_cors(test_app, "dev")
        
        client = TestClient(test_app)
        
        response = client.options(
            "/api/test",
            headers={
                "origin": "http://localhost:3000",
                "access-control-request-method": "GET"
            }
        )
        
        assert response.headers.get("access-control-allow-credentials") == "true"


class TestCORSValidation:
    """Test CORS configuration validation"""
    
    def test_startup_validation_passes_with_valid_config(self):
        """Test startup validation passes with valid configuration"""
        with patch.dict(os.environ, {"ENVIRONMENT": "dev"}):
            assert validate_cors_startup("dev") is True
    
    def test_startup_validation_fails_with_wildcards(self):
        """Test startup validation fails with wildcard origins"""
        with patch.dict(CORS_CONFIG, {
            "test": {
                "allow_origins": ["*"],
                "allow_credentials": True,
                "max_age": 300
            }
        }):
            with pytest.raises(ValueError):
                validate_cors_startup("test")
    
    def test_prod_environment_requires_https(self):
        """Test production environment validation requires HTTPS"""
        # This should pass - prod config uses HTTPS
        assert validate_cors_startup("prod") is True


class TestCORSHealthStatus:
    """Test CORS health status reporting"""
    
    def test_healthy_cors_status(self):
        """Test health status for valid CORS configuration"""
        status = get_cors_health_status("dev")
        
        assert status["status"] == "healthy"
        assert status["environment"] == "dev"
        assert status["origins_configured"] > 0
        assert status["validation"] == "passed"
        assert "timestamp" in status
    
    def test_unhealthy_cors_status_invalid_env(self):
        """Test health status for invalid environment"""
        status = get_cors_health_status("invalid")
        
        assert status["status"] == "unhealthy"
        assert status["environment"] == "invalid"
        assert "error" in status
        assert status["validation"] == "failed"


class TestCORSSecurityScenarios:
    """Security-focused test scenarios"""
    
    @pytest.fixture
    def secured_app(self):
        """FastAPI app with secure CORS configuration"""
        app = FastAPI()
        setup_secure_cors(app, "dev")
        
        @app.get("/api/sensitive")
        async def sensitive_endpoint():
            return {"sensitive": "data"}
        
        return app
    
    def test_cross_site_request_forgery_prevention(self, secured_app):
        """Test CSRF protection through CORS policies"""
        client = TestClient(secured_app)
        
        # Attempt CSRF attack from malicious origin
        response = client.post(
            "/api/sensitive",
            headers={
                "origin": "https://malicious-site.com",
                "content-type": "application/json"
            },
            json={"malicious": "payload"}
        )
        
        # Should not have CORS headers allowing the malicious origin
        assert "access-control-allow-origin" not in response.headers or \
               response.headers.get("access-control-allow-origin") != "https://malicious-site.com"
    
    def test_data_exfiltration_attack_blocked(self, secured_app):
        """Test data exfiltration attempts are blocked by CORS"""
        client = TestClient(secured_app)
        
        # Attempt to read data from unauthorized origin
        response = client.get(
            "/api/sensitive",
            headers={"origin": "https://data-thief.com"}
        )
        
        # Should not provide CORS headers for unauthorized origin
        assert response.headers.get("access-control-allow-origin") != "https://data-thief.com"
    
    def test_origin_spoofing_attempts_blocked(self, secured_app):
        """Test origin spoofing attempts don't bypass CORS"""
        client = TestClient(secured_app)
        
        # Attempt to spoof allowed origin with typos/variations
        spoofed_origins = [
            "http://localhost.evil.com",  # Subdomain spoofing
            "https://localhost:3000",  # Protocol spoofing (dev allows http)
            "http://localhos:3000",  # Typo spoofing
        ]
        
        for spoofed_origin in spoofed_origins:
            response = client.get(
                "/api/sensitive",
                headers={"origin": spoofed_origin}
            )
            
            # Should not match exactly allowed origins
            assert response.headers.get("access-control-allow-origin") != spoofed_origin
    
    def test_cors_policy_bypasses_prevented(self, secured_app):
        """Test common CORS bypass techniques are prevented"""
        client = TestClient(secured_app)
        
        # Test null origin bypass attempt
        response = client.get(
            "/api/sensitive",
            headers={"origin": "null"}
        )
        assert response.headers.get("access-control-allow-origin") != "null"
        
        # Test wildcard with credentials bypass attempt
        response = client.options(
            "/api/sensitive",
            headers={
                "origin": "http://localhost:3000",
                "access-control-request-method": "GET"
            }
        )
        
        # Should have specific origin, not wildcard, when credentials are allowed
        allow_origin = response.headers.get("access-control-allow-origin")
        if allow_origin:
            assert allow_origin != "*"
            assert "localhost" in allow_origin


if __name__ == "__main__":
    pytest.main([__file__, "-v"])