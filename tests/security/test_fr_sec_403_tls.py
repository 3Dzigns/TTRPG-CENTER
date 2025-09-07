# test_fr_sec_403_tls.py
"""
FR-SEC-403: HTTPS/TLS Implementation Tests
Unit and integration tests for TLS certificate management and HTTPS enforcement
"""

import pytest
import os
import ssl
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock, AsyncMock
from datetime import datetime, timedelta
from fastapi import FastAPI
from fastapi.testclient import TestClient
import cryptography.x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography import x509

from src_common.tls_security import (
    TLSCertificateManager,
    CertificateStatus,
    HTTPSRedirectMiddleware,
    SecurityHeadersMiddleware,
    create_app_with_tls,
    validate_tls_startup,
    get_tls_health_status,
    TLS_CONFIG,
    SECURITY_HEADERS
)


class TestTLSCertificateManager:
    """Test TLS certificate management functionality"""
    
    @pytest.fixture
    def temp_cert_dir(self):
        """Create temporary directory for certificate testing"""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield Path(temp_dir)
    
    @pytest.fixture
    def mock_tls_config(self, temp_cert_dir):
        """Mock TLS configuration for testing"""
        return {
            "test": {
                "mode": "self_signed",
                "cert_path": str(temp_cert_dir / "cert.pem"),
                "key_path": str(temp_cert_dir / "key.pem"),
                "domains": ["localhost", "127.0.0.1"],
                "redirect_http": True
            },
            "prod": {
                "mode": "custom",
                "cert_path": str(temp_cert_dir / "prod_cert.pem"),
                "key_path": str(temp_cert_dir / "prod_key.pem"),
                "hsts_max_age": 31536000
            }
        }
    
    def test_self_signed_certificate_generation(self, mock_tls_config, temp_cert_dir):
        """Test self-signed certificate generation"""
        with patch.dict('src_common.tls_security.TLS_CONFIG', mock_tls_config):
            manager = TLSCertificateManager(mock_tls_config, "test")
            
            # Generate certificate
            import asyncio
            cert_path, key_path = asyncio.run(manager._generate_self_signed())
            
            # Check files were created
            assert Path(cert_path).exists()
            assert Path(key_path).exists()
            
            # Validate certificate
            status = manager.validate_certificate_file(cert_path)
            assert status.is_valid
            assert status.days_until_expiry > 300  # Should be valid for ~1 year
    
    def test_custom_certificate_loading(self, mock_tls_config, temp_cert_dir):
        """Test loading custom certificates from file system"""
        # Create a dummy certificate file
        cert_path = temp_cert_dir / "prod_cert.pem"
        key_path = temp_cert_dir / "prod_key.pem"
        
        # Generate test certificate
        with patch.dict('src_common.tls_security.TLS_CONFIG', mock_tls_config):
            test_manager = TLSCertificateManager(mock_tls_config, "test")
            import asyncio
            test_cert, test_key = asyncio.run(test_manager._generate_self_signed())
            
            # Copy to prod paths
            import shutil
            shutil.copy2(test_cert, cert_path)
            shutil.copy2(test_key, key_path)
            
            # Test custom loading
            prod_manager = TLSCertificateManager(mock_tls_config, "prod")
            loaded_cert, loaded_key = prod_manager._load_custom_certificate()
            
            assert loaded_cert == str(cert_path)
            assert loaded_key == str(key_path)
    
    def test_certificate_validation(self, mock_tls_config, temp_cert_dir):
        """Test certificate validation functionality"""
        with patch.dict('src_common.tls_security.TLS_CONFIG', mock_tls_config):
            manager = TLSCertificateManager(mock_tls_config, "test")
            
            # Generate certificate
            import asyncio
            cert_path, key_path = asyncio.run(manager._generate_self_signed())
            
            # Validate certificate
            status = manager.validate_certificate_file(cert_path)
            
            assert isinstance(status, CertificateStatus)
            assert status.is_valid
            assert isinstance(status.expires_at, datetime)
            assert status.days_until_expiry > 0
            assert status.error is None
    
    def test_expired_certificate_detection(self, mock_tls_config, temp_cert_dir):
        """Test detection of expired certificates"""
        # Generate expired certificate
        private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048,
        )
        
        subject = issuer = x509.Name([
            x509.NameAttribute(x509.NameOID.COMMON_NAME, "localhost"),
        ])
        
        # Create expired certificate (expired yesterday)
        cert = x509.CertificateBuilder().subject_name(
            subject
        ).issuer_name(
            issuer
        ).public_key(
            private_key.public_key()
        ).serial_number(
            x509.random_serial_number()
        ).not_valid_before(
            datetime.utcnow() - timedelta(days=2)
        ).not_valid_after(
            datetime.utcnow() - timedelta(days=1)  # Expired yesterday
        ).sign(private_key, hashes.SHA256())
        
        # Write expired certificate
        cert_path = temp_cert_dir / "expired_cert.pem"
        with open(cert_path, "wb") as f:
            f.write(cert.public_bytes(serialization.Encoding.PEM))
        
        # Test validation
        with patch.dict('src_common.tls_security.TLS_CONFIG', mock_tls_config):
            manager = TLSCertificateManager(mock_tls_config, "test")
            status = manager.validate_certificate_file(str(cert_path))
            
            assert not status.is_valid
            assert "expired" in status.error.lower()
            assert status.days_until_expiry == 0
    
    def test_invalid_certificate_file(self, mock_tls_config):
        """Test handling of invalid certificate files"""
        with patch.dict('src_common.tls_security.TLS_CONFIG', mock_tls_config):
            manager = TLSCertificateManager(mock_tls_config, "test")
            
            # Test non-existent file
            status = manager.validate_certificate_file("/nonexistent/cert.pem")
            assert not status.is_valid
            assert status.error is not None
    
    def test_missing_certificate_files_raise_error(self, mock_tls_config):
        """Test custom certificate loading with missing files raises appropriate errors"""
        with patch.dict('src_common.tls_security.TLS_CONFIG', mock_tls_config):
            manager = TLSCertificateManager(mock_tls_config, "prod")
            
            with pytest.raises(FileNotFoundError):
                manager._load_custom_certificate()


class TestHTTPSRedirectMiddleware:
    """Test HTTPS redirect middleware functionality"""
    
    @pytest.fixture
    def test_app(self):
        """Test FastAPI application"""
        app = FastAPI()
        
        @app.get("/test")
        async def test_endpoint():
            return {"message": "test"}
        
        return app
    
    def test_http_requests_redirect_to_https(self, test_app):
        """Test HTTP requests are redirected to HTTPS"""
        test_app.add_middleware(HTTPSRedirectMiddleware, force_https=True)
        
        # Use TestClient with custom base_url to simulate HTTP
        client = TestClient(test_app, base_url="http://testserver")
        
        response = client.get("/test", follow_redirects=False)
        
        assert response.status_code == 301
        assert "location" in response.headers
        assert response.headers["location"].startswith("https://")
    
    def test_https_requests_pass_through(self, test_app):
        """Test HTTPS requests pass through without redirection"""
        test_app.add_middleware(HTTPSRedirectMiddleware, force_https=True)
        
        # Use TestClient with HTTPS base_url
        client = TestClient(test_app, base_url="https://testserver")
        
        response = client.get("/test")
        
        assert response.status_code == 200
        assert response.json() == {"message": "test"}
    
    def test_query_parameters_preserved_in_redirect(self, test_app):
        """Test query parameters are preserved during HTTP->HTTPS redirect"""
        test_app.add_middleware(HTTPSRedirectMiddleware, force_https=True)
        
        client = TestClient(test_app, base_url="http://testserver")
        
        response = client.get("/test?param=value&other=test", follow_redirects=False)
        
        assert response.status_code == 301
        location = response.headers["location"]
        assert "param=value" in location
        assert "other=test" in location
    
    def test_redirect_disabled_allows_http(self, test_app):
        """Test HTTP requests pass through when redirect is disabled"""
        test_app.add_middleware(HTTPSRedirectMiddleware, force_https=False)
        
        client = TestClient(test_app, base_url="http://testserver")
        
        response = client.get("/test")
        
        assert response.status_code == 200
        assert response.json() == {"message": "test"}


class TestSecurityHeadersMiddleware:
    """Test security headers middleware"""
    
    @pytest.fixture
    def test_app(self):
        """Test FastAPI application"""
        app = FastAPI()
        
        @app.get("/test")
        async def test_endpoint():
            return {"message": "test"}
        
        return app
    
    def test_security_headers_added_to_responses(self, test_app):
        """Test security headers are added to all responses"""
        test_app.add_middleware(SecurityHeadersMiddleware, environment="dev")
        
        client = TestClient(test_app)
        response = client.get("/test")
        
        # Check standard security headers
        assert response.headers.get("X-Content-Type-Options") == "nosniff"
        assert response.headers.get("X-Frame-Options") == "DENY"
        assert response.headers.get("X-XSS-Protection") == "1; mode=block"
        assert "Content-Security-Policy" in response.headers
    
    def test_hsts_header_added_in_production(self, test_app):
        """Test HSTS header is added in production environments"""
        test_app.add_middleware(SecurityHeadersMiddleware, environment="prod")
        
        client = TestClient(test_app)
        response = client.get("/test")
        
        assert "Strict-Transport-Security" in response.headers
        hsts_header = response.headers["Strict-Transport-Security"]
        assert "max-age=" in hsts_header
    
    def test_hsts_header_not_added_in_development(self, test_app):
        """Test HSTS header is not added in development environment"""
        test_app.add_middleware(SecurityHeadersMiddleware, environment="dev")
        
        client = TestClient(test_app)
        response = client.get("/test")
        
        # HSTS should not be present in dev
        assert "Strict-Transport-Security" not in response.headers


class TestTLSIntegration:
    """Integration tests for TLS configuration"""
    
    @pytest.fixture
    def test_app(self):
        """Test FastAPI application"""
        app = FastAPI()
        
        @app.get("/health")
        async def health_check():
            return {"status": "ok"}
        
        return app
    
    @pytest.mark.asyncio
    async def test_create_app_with_tls_dev_environment(self, test_app):
        """Test TLS app creation for development environment"""
        with patch('src_common.tls_security.TLSCertificateManager.load_certificate') as mock_load:
            mock_load.return_value = ("cert.pem", "key.pem")
            
            app, cert_path, key_path = await create_app_with_tls(test_app, "dev")
            
            assert app is not None
            assert cert_path == "cert.pem"
            assert key_path == "key.pem"
            
            # Check middlewares were added
            middleware_classes = [m.cls.__name__ for m in app.user_middleware]
            assert "SecurityHeadersMiddleware" in middleware_classes
            assert "HTTPSRedirectMiddleware" in middleware_classes
    
    @pytest.mark.asyncio
    async def test_create_app_with_tls_handles_certificate_errors(self, test_app):
        """Test TLS app creation handles certificate loading errors gracefully"""
        with patch('src_common.tls_security.TLSCertificateManager.load_certificate') as mock_load:
            mock_load.side_effect = Exception("Certificate loading failed")
            
            # Should not raise in development
            app, cert_path, key_path = await create_app_with_tls(test_app, "dev")
            
            assert app is not None
            assert cert_path is None
            assert key_path is None
    
    @pytest.mark.asyncio
    async def test_create_app_with_tls_fails_hard_in_production(self, test_app):
        """Test TLS app creation fails hard in production with certificate errors"""
        with patch('src_common.tls_security.TLSCertificateManager.load_certificate') as mock_load:
            mock_load.side_effect = Exception("Certificate loading failed")
            
            # Should raise in production
            with pytest.raises(Exception, match="Certificate loading failed"):
                await create_app_with_tls(test_app, "prod")


class TestTLSValidation:
    """Test TLS configuration validation"""
    
    def test_startup_validation_passes_with_valid_config(self):
        """Test startup validation passes with valid configuration"""
        assert validate_tls_startup("dev") is True
    
    def test_startup_validation_fails_with_invalid_environment(self):
        """Test startup validation fails with invalid environment"""
        with pytest.raises(ValueError):
            validate_tls_startup("invalid")
    
    def test_production_validation_requires_certificate_paths(self):
        """Test production environment validation requires certificate paths"""
        # Mock configuration without certificate paths
        mock_config = {
            "prod": {
                "mode": "custom",
                "redirect_http": True
            }
        }
        
        with patch.dict('src_common.tls_security.TLS_CONFIG', mock_config):
            with pytest.raises(ValueError, match="requires certificate and key paths"):
                validate_tls_startup("prod")


class TestTLSHealthStatus:
    """Test TLS health status reporting"""
    
    def test_healthy_tls_status(self):
        """Test health status for valid TLS configuration"""
        status = get_tls_health_status("dev")
        
        assert status["status"] == "healthy"
        assert status["environment"] == "dev"
        assert status["mode"] == "self_signed"
        assert isinstance(status["redirect_http"], bool)
        assert "timestamp" in status
    
    def test_unhealthy_tls_status_invalid_env(self):
        """Test health status for invalid environment"""
        status = get_tls_health_status("invalid")
        
        assert status["status"] == "unhealthy"
        assert status["environment"] == "invalid"
        assert "error" in status


class TestTLSSecurityScenarios:
    """Security-focused test scenarios for TLS"""
    
    @pytest.fixture
    def secured_app(self):
        """FastAPI app with TLS security features"""
        app = FastAPI()
        app.add_middleware(SecurityHeadersMiddleware, environment="prod")
        app.add_middleware(HTTPSRedirectMiddleware, force_https=True)
        
        @app.get("/api/sensitive")
        async def sensitive_endpoint():
            return {"sensitive": "data"}
        
        return app
    
    def test_mixed_content_warnings_eliminated(self, secured_app):
        """Test security headers prevent mixed content warnings"""
        client = TestClient(secured_app, base_url="https://testserver")
        
        response = client.get("/api/sensitive")
        
        # CSP header should prevent mixed content
        csp = response.headers.get("Content-Security-Policy")
        assert csp is not None
        assert "default-src 'self'" in csp
    
    def test_clickjacking_protection(self, secured_app):
        """Test X-Frame-Options prevents clickjacking"""
        client = TestClient(secured_app, base_url="https://testserver")
        
        response = client.get("/api/sensitive")
        
        assert response.headers.get("X-Frame-Options") == "DENY"
    
    def test_content_type_sniffing_prevented(self, secured_app):
        """Test X-Content-Type-Options prevents MIME sniffing"""
        client = TestClient(secured_app, base_url="https://testserver")
        
        response = client.get("/api/sensitive")
        
        assert response.headers.get("X-Content-Type-Options") == "nosniff"
    
    def test_xss_protection_enabled(self, secured_app):
        """Test XSS protection is enabled"""
        client = TestClient(secured_app, base_url="https://testserver")
        
        response = client.get("/api/sensitive")
        
        xss_protection = response.headers.get("X-XSS-Protection")
        assert xss_protection == "1; mode=block"


class TestCertificateLifecycle:
    """Test certificate lifecycle management"""
    
    @pytest.fixture
    def temp_cert_dir(self):
        """Create temporary directory for certificate testing"""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield Path(temp_dir)
    
    def test_certificate_near_expiry_detection(self, temp_cert_dir):
        """Test detection of certificates nearing expiry"""
        # Generate certificate expiring soon
        private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048,
        )
        
        subject = issuer = x509.Name([
            x509.NameAttribute(x509.NameOID.COMMON_NAME, "localhost"),
        ])
        
        # Create certificate expiring in 15 days
        cert = x509.CertificateBuilder().subject_name(
            subject
        ).issuer_name(
            issuer
        ).public_key(
            private_key.public_key()
        ).serial_number(
            x509.random_serial_number()
        ).not_valid_before(
            datetime.utcnow()
        ).not_valid_after(
            datetime.utcnow() + timedelta(days=15)  # Expires in 15 days
        ).sign(private_key, hashes.SHA256())
        
        # Write certificate
        cert_path = temp_cert_dir / "expiring_cert.pem"
        with open(cert_path, "wb") as f:
            f.write(cert.public_bytes(serialization.Encoding.PEM))
        
        # Test validation
        mock_config = {"test": {"mode": "custom"}}
        with patch.dict('src_common.tls_security.TLS_CONFIG', mock_config):
            manager = TLSCertificateManager(mock_config, "test")
            status = manager.validate_certificate_file(str(cert_path))
            
            assert status.is_valid
            assert status.days_until_expiry == 15
            
            # Certificate should trigger renewal alerts (< 30 days)
            assert status.days_until_expiry < 30
    
    def test_certificate_renewal_stub(self):
        """Test certificate renewal functionality (stub implementation)"""
        mock_config = {"dev": {"mode": "self_signed"}}
        with patch.dict('src_common.tls_security.TLS_CONFIG', mock_config):
            manager = TLSCertificateManager(mock_config, "dev")
            
            import asyncio
            # Renewal should return False (not implemented)
            result = asyncio.run(manager.renew_certificate())
            assert result is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])