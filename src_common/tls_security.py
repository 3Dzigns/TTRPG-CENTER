# tls_security.py
"""
FR-SEC-403: HTTPS/TLS Implementation
Certificate management, HTTPS enforcement, and security headers
"""

import os
import ssl
import asyncio
import logging
from pathlib import Path
from typing import Dict, Any, Tuple, Optional, List
from datetime import datetime, timedelta
import uvicorn
from fastapi import FastAPI, Request, Response
from fastapi.responses import RedirectResponse
from starlette.middleware.base import BaseHTTPMiddleware
import cryptography.x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography import x509

from .ttrpg_logging import get_logger

logger = get_logger(__name__)

# TLS configuration structure
TLS_CONFIG = {
    "dev": {
        "mode": "self_signed",
        "cert_path": "./certs/dev/cert.pem",
        "key_path": "./certs/dev/key.pem",
        "redirect_http": True,
        "domains": ["localhost", "127.0.0.1"]
    },
    "test": {
        "mode": "lets_encrypt",  # or custom
        "domain": "test.ttrpg-center.com",
        "email": "admin@ttrpg-center.com",
        "redirect_http": True,
        "hsts_max_age": 31536000,  # 1 year
        "cert_path": "/etc/ssl/certs/test-ttrpg-center.pem",
        "key_path": "/etc/ssl/private/test-ttrpg-center.key"
    },
    "prod": {
        "mode": "custom",  # or lets_encrypt
        "cert_path": "/etc/ssl/certs/ttrpg-center.pem",
        "key_path": "/etc/ssl/private/ttrpg-center.key",
        "ca_bundle_path": "/etc/ssl/certs/ca-bundle.pem",
        "redirect_http": True,
        "hsts_max_age": 63072000,  # 2 years
        "hsts_include_subdomains": True,
        "hsts_preload": True,
        "domains": ["ttrpg-center.com", "*.ttrpg-center.com"]
    }
}

# Security headers configuration
SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "X-XSS-Protection": "1; mode=block",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Content-Security-Policy": "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data: https:; connect-src 'self'",
    "Permissions-Policy": "geolocation=(), microphone=(), camera=()"
}


class CertificateStatus:
    """Certificate status information"""
    def __init__(self, is_valid: bool, expires_at: Optional[datetime] = None, 
                 days_until_expiry: Optional[int] = None, error: Optional[str] = None):
        self.is_valid = is_valid
        self.expires_at = expires_at
        self.days_until_expiry = days_until_expiry
        self.error = error


class TLSCertificateManager:
    """TLS certificate manager with support for different certificate types"""
    
    def __init__(self, config: Dict[str, Any], environment: Optional[str] = None):
        self.config = config
        self.environment = environment or os.getenv("ENVIRONMENT", "dev")
        self.env_config = config.get(self.environment)
        
        if not self.env_config:
            raise ValueError(f"No TLS config for environment: {self.environment}")
    
    async def load_certificate(self) -> Tuple[str, str]:
        """Load TLS certificate and private key"""
        if self.env_config["mode"] == "lets_encrypt":
            return await self._provision_lets_encrypt()
        elif self.env_config["mode"] == "custom":
            return self._load_custom_certificate()
        else:  # self_signed
            return await self._generate_self_signed()
    
    def _load_custom_certificate(self) -> Tuple[str, str]:
        """Load custom certificate from file system"""
        cert_path = self.env_config["cert_path"]
        key_path = self.env_config["key_path"]
        
        if not os.path.exists(cert_path):
            raise FileNotFoundError(f"Certificate file not found: {cert_path}")
        
        if not os.path.exists(key_path):
            raise FileNotFoundError(f"Private key file not found: {key_path}")
        
        # Validate certificate
        try:
            status = self.validate_certificate_file(cert_path)
            if not status.is_valid:
                raise ValueError(f"Invalid certificate: {status.error}")
        except Exception as e:
            logger.error(f"Certificate validation failed: {e}")
            raise
        
        logger.info(f"Loaded custom certificate from {cert_path}")
        return cert_path, key_path
    
    async def _provision_lets_encrypt(self) -> Tuple[str, str]:
        """Provision Let's Encrypt certificate (stub implementation)"""
        # NOTE: This is a stub implementation. In production, you would use
        # a proper ACME client like certbot or acme-python
        
        cert_path = self.env_config.get("cert_path", "/etc/letsencrypt/live/domain/fullchain.pem")
        key_path = self.env_config.get("key_path", "/etc/letsencrypt/live/domain/privkey.pem")
        
        # Check if certificates already exist
        if os.path.exists(cert_path) and os.path.exists(key_path):
            status = self.validate_certificate_file(cert_path)
            if status.is_valid and status.days_until_expiry > 30:
                logger.info("Using existing Let's Encrypt certificate")
                return cert_path, key_path
        
        # This would trigger certificate provisioning in production
        logger.warning("Let's Encrypt certificate provisioning not implemented - using fallback")
        return await self._generate_self_signed()
    
    async def _generate_self_signed(self) -> Tuple[str, str]:
        """Generate self-signed certificate for development"""
        cert_path = self.env_config["cert_path"]
        key_path = self.env_config["key_path"]
        
        # Create certificate directory
        cert_dir = Path(cert_path).parent
        cert_dir.mkdir(parents=True, exist_ok=True)
        
        # Check if certificates already exist and are valid
        if os.path.exists(cert_path) and os.path.exists(key_path):
            try:
                status = self.validate_certificate_file(cert_path)
                if status.is_valid and status.days_until_expiry > 30:
                    logger.info("Using existing self-signed certificate")
                    return cert_path, key_path
            except Exception:
                pass  # Generate new certificate
        
        # Generate private key
        private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048,
        )
        
        # Generate certificate
        subject = issuer = x509.Name([
            x509.NameAttribute(x509.NameOID.COUNTRY_NAME, "US"),
            x509.NameAttribute(x509.NameOID.STATE_OR_PROVINCE_NAME, "Development"),
            x509.NameAttribute(x509.NameOID.LOCALITY_NAME, "Localhost"),
            x509.NameAttribute(x509.NameOID.ORGANIZATION_NAME, "TTRPG Center Dev"),
            x509.NameAttribute(x509.NameOID.COMMON_NAME, "localhost"),
        ])
        
        # Add subject alternative names for development
        san_list = []
        for domain in self.env_config.get("domains", ["localhost"]):
            try:
                # Check if it's an IP address
                import ipaddress
                ip = ipaddress.ip_address(domain)
                san_list.append(x509.IPAddress(ip))
            except ValueError:
                # It's a domain name
                san_list.append(x509.DNSName(domain))
        
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
            datetime.utcnow() + timedelta(days=365)
        ).add_extension(
            x509.SubjectAlternativeName(san_list),
            critical=False,
        ).sign(private_key, hashes.SHA256())
        
        # Write private key
        with open(key_path, "wb") as f:
            f.write(private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.NoEncryption()
            ))
        
        # Write certificate
        with open(cert_path, "wb") as f:
            f.write(cert.public_bytes(serialization.Encoding.PEM))
        
        # Set appropriate permissions
        os.chmod(key_path, 0o600)
        os.chmod(cert_path, 0o644)
        
        logger.info(f"Generated self-signed certificate: {cert_path}")
        return cert_path, key_path
    
    def validate_certificate_file(self, cert_path: str) -> CertificateStatus:
        """Validate certificate file and return status"""
        try:
            with open(cert_path, "rb") as f:
                cert_data = f.read()
            
            cert = x509.load_pem_x509_certificate(cert_data)
            now = datetime.utcnow()
            
            if cert.not_valid_after < now:
                return CertificateStatus(False, cert.not_valid_after, 0, "Certificate expired")
            
            days_until_expiry = (cert.not_valid_after - now).days
            return CertificateStatus(True, cert.not_valid_after, days_until_expiry)
            
        except Exception as e:
            return CertificateStatus(False, error=str(e))
    
    async def renew_certificate(self) -> bool:
        """Renew certificate if needed"""
        # This would implement certificate renewal logic
        logger.info("Certificate renewal not implemented")
        return False


class HTTPSRedirectMiddleware(BaseHTTPMiddleware):
    """Middleware to redirect HTTP requests to HTTPS"""
    
    def __init__(self, app, force_https: bool = True):
        super().__init__(app)
        self.force_https = force_https
    
    async def dispatch(self, request: Request, call_next):
        if self.force_https and request.url.scheme == "http":
            # Build HTTPS URL
            https_url = request.url.replace(scheme="https")
            
            logger.info(
                f"Redirecting HTTP to HTTPS: {request.url} -> {https_url}",
                extra={
                    "client_ip": self._get_client_ip(request),
                    "user_agent": request.headers.get("user-agent", "")
                }
            )
            
            return RedirectResponse(url=str(https_url), status_code=301)
        
        return await call_next(request)
    
    def _get_client_ip(self, request: Request) -> str:
        """Extract client IP from request"""
        forwarded_for = request.headers.get("x-forwarded-for")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()
        
        if request.client:
            return request.client.host
        
        return "unknown"


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Middleware to add security headers to all responses"""
    
    def __init__(self, app, environment: str = "dev"):
        super().__init__(app)
        self.environment = environment
        self.headers = SECURITY_HEADERS.copy()
        
        # Add HSTS header for HTTPS environments
        if environment != "dev":
            env_config = TLS_CONFIG.get(environment, {})
            hsts_max_age = env_config.get("hsts_max_age", 31536000)
            hsts_parts = [f"max-age={hsts_max_age}"]
            
            if env_config.get("hsts_include_subdomains"):
                hsts_parts.append("includeSubDomains")
            
            if env_config.get("hsts_preload"):
                hsts_parts.append("preload")
            
            self.headers["Strict-Transport-Security"] = "; ".join(hsts_parts)
    
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        
        # Add security headers
        for header, value in self.headers.items():
            response.headers[header] = value
        
        return response


async def create_app_with_tls(app: FastAPI, environment: Optional[str] = None) -> Tuple[FastAPI, Optional[str], Optional[str]]:
    """
    Configure FastAPI application with TLS support
    
    Args:
        app: FastAPI application instance
        environment: Deployment environment (dev/test/prod)
    
    Returns:
        Tuple of (app, cert_path, key_path)
    """
    env = environment or os.getenv("ENVIRONMENT", "dev")
    
    try:
        # Load TLS configuration
        tls_manager = TLSCertificateManager(TLS_CONFIG, env)
        cert_path, key_path = await tls_manager.load_certificate()
        
        # Add security headers middleware
        app.add_middleware(SecurityHeadersMiddleware, environment=env)
        
        # Add HTTPS redirect middleware (except for health checks)
        if TLS_CONFIG[env].get("redirect_http", False):
            app.add_middleware(HTTPSRedirectMiddleware, force_https=True)
        
        logger.info(
            f"TLS configuration complete for environment: {env}",
            extra={
                "cert_path": cert_path,
                "mode": TLS_CONFIG[env]["mode"]
            }
        )
        
        return app, cert_path, key_path
        
    except Exception as e:
        logger.error(f"TLS configuration failed: {e}")
        if env == "prod":
            raise  # Fail hard in production
        else:
            logger.warning("Continuing without TLS in development")
            return app, None, None


def run_with_tls(app: FastAPI, cert_path: Optional[str], key_path: Optional[str], 
                port: int, host: str = "0.0.0.0"):
    """
    Run FastAPI application with TLS if certificates are available
    
    Args:
        app: FastAPI application
        cert_path: Path to certificate file
        key_path: Path to private key file
        port: Port to listen on
        host: Host to bind to
    """
    if cert_path and key_path:
        # Run with TLS
        uvicorn.run(
            app,
            host=host,
            port=port,
            ssl_keyfile=key_path,
            ssl_certfile=cert_path,
            ssl_version=ssl.PROTOCOL_TLS,
            ssl_cert_reqs=ssl.CERT_NONE,
            ssl_ciphers="ECDHE+AESGCM:ECDHE+CHACHA20:DHE+AESGCM:DHE+CHACHA20:!aNULL:!MD5:!DSS",
            access_log=True
        )
    else:
        # Run without TLS
        logger.warning("Running without TLS - certificates not available")
        uvicorn.run(app, host=host, port=port, access_log=True)


def validate_tls_startup(environment: Optional[str] = None) -> bool:
    """
    Validate TLS configuration on application startup
    
    Returns:
        bool: True if configuration is valid
    """
    env = environment or os.getenv("ENVIRONMENT", "dev")
    
    try:
        tls_manager = TLSCertificateManager(TLS_CONFIG, env)
        
        # Validate configuration exists
        if not tls_manager.env_config:
            raise ValueError(f"No TLS configuration for environment: {env}")
        
        # Production-specific validations
        if env == "prod":
            # Ensure certificate paths are configured
            if not tls_manager.env_config.get("cert_path") or not tls_manager.env_config.get("key_path"):
                raise ValueError("Production environment requires certificate and key paths")
            
            # Ensure HSTS is configured
            if not tls_manager.env_config.get("hsts_max_age"):
                logger.warning("HSTS not configured for production environment")
        
        logger.info(
            f"TLS configuration validation passed for environment: {env}",
            extra={
                "mode": tls_manager.env_config["mode"],
                "redirect_http": tls_manager.env_config.get("redirect_http", False)
            }
        )
        
        return True
        
    except Exception as e:
        logger.error(
            f"TLS configuration validation failed for environment: {env}",
            extra={"error": str(e)}
        )
        raise


def get_tls_health_status(environment: Optional[str] = None) -> Dict[str, Any]:
    """
    Get TLS configuration health status for monitoring
    
    Returns:
        Dict with TLS configuration status and metadata
    """
    env = environment or os.getenv("ENVIRONMENT", "dev")
    
    try:
        tls_manager = TLSCertificateManager(TLS_CONFIG, env)
        
        # Check certificate status if in custom/lets_encrypt mode
        cert_status = None
        if tls_manager.env_config["mode"] in ["custom", "lets_encrypt"]:
            cert_path = tls_manager.env_config.get("cert_path")
            if cert_path and os.path.exists(cert_path):
                cert_status = tls_manager.validate_certificate_file(cert_path)
        
        return {
            "status": "healthy",
            "environment": env,
            "mode": tls_manager.env_config["mode"],
            "redirect_http": tls_manager.env_config.get("redirect_http", False),
            "hsts_configured": "hsts_max_age" in tls_manager.env_config,
            "certificate_valid": cert_status.is_valid if cert_status else None,
            "certificate_expires": cert_status.expires_at.isoformat() if cert_status and cert_status.expires_at else None,
            "days_until_expiry": cert_status.days_until_expiry if cert_status else None,
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        return {
            "status": "unhealthy",
            "environment": env,
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }