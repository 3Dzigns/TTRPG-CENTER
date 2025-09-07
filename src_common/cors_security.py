# cors_security.py
"""
FR-SEC-402: CORS Security Configuration
Environment-specific, restrictive CORS policies with monitoring and validation
"""

import os
import logging
from typing import Dict, List, Any, Optional
from fastapi.middleware.cors import CORSMiddleware
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from .logging import get_logger

logger = get_logger(__name__)

# CORS configuration per environment
CORS_CONFIG = {
    "dev": {
        "allow_origins": [
            "http://localhost:3000",
            "http://localhost:8080", 
            "http://127.0.0.1:3000",
            "http://127.0.0.1:8080",
            "http://localhost:8000",  # Admin UI
            "http://localhost:8181",  # Test environment
            "http://localhost:8282"   # Prod environment local testing
        ],
        "allow_credentials": True,
        "max_age": 300  # 5 minutes for dev
    },
    "test": {
        "allow_origins": [
            "https://test.ttrpg-center.com",
            "https://test-admin.ttrpg-center.com",
            "https://test-feedback.ttrpg-center.com",
            "https://test-requirements.ttrpg-center.com"
        ],
        "allow_credentials": True,
        "max_age": 1800  # 30 minutes for test
    },
    "prod": {
        "allow_origins": [
            "https://ttrpg-center.com",
            "https://app.ttrpg-center.com",
            "https://admin.ttrpg-center.com",
            "https://feedback.ttrpg-center.com",
            "https://requirements.ttrpg-center.com"
        ],
        "allow_credentials": True,
        "max_age": 3600  # 1 hour for prod
    }
}

# Security headers configuration
SECURITY_HEADERS = {
    "allow_methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    "allow_headers": [
        "Authorization",
        "Content-Type", 
        "X-Requested-With",
        "X-CSRF-Token",
        "X-Admin-User",  # Temporary during auth transition
        "Cache-Control",
        "X-Trace-ID"
    ],
    "expose_headers": [
        "X-Total-Count",
        "X-Rate-Limit-Remaining",
        "X-Rate-Limit-Reset",
        "X-Trace-ID"
    ]
}


class CORSConfigLoader:
    """Environment-aware CORS configuration loader with security validation"""
    
    def __init__(self, environment: Optional[str] = None):
        self.environment = environment or os.getenv("ENVIRONMENT", "dev")
        self._validate_environment()
    
    def get_cors_config(self) -> Dict[str, Any]:
        """Load CORS configuration for current environment"""
        config = CORS_CONFIG.get(self.environment)
        if not config:
            raise ValueError(f"No CORS config for environment: {self.environment}")
        
        # Security validation
        self._validate_cors_config(config)
        return config
    
    def _validate_environment(self) -> None:
        """Validate environment parameter"""
        if self.environment not in CORS_CONFIG:
            raise ValueError(f"Invalid environment: {self.environment}. Must be one of: {list(CORS_CONFIG.keys())}")
    
    def _validate_cors_config(self, config: Dict[str, Any]) -> None:
        """Validate CORS configuration for security compliance"""
        # No wildcards allowed
        if "*" in config.get("allow_origins", []):
            raise ValueError("Wildcard origins not allowed - security vulnerability")
        
        # Production must use HTTPS
        if self.environment == "prod":
            for origin in config["allow_origins"]:
                if not origin.startswith("https://"):
                    raise ValueError(f"Production origin must use HTTPS: {origin}")
        
        # Test environment should also use HTTPS (except localhost)
        if self.environment == "test":
            for origin in config["allow_origins"]:
                if not origin.startswith("https://") and not origin.startswith("http://localhost"):
                    logger.warning(f"Test environment origin should use HTTPS: {origin}")


class CORSMonitoringMiddleware(BaseHTTPMiddleware):
    """CORS monitoring middleware for logging blocked requests and metrics"""
    
    def __init__(self, app, allowed_origins: List[str] = None):
        super().__init__(app)
        self.allowed_origins = set(allowed_origins or [])
        
    async def dispatch(self, request: Request, call_next):
        request_origin = request.headers.get("origin")
        
        # Log CORS requests for monitoring
        if request_origin:
            if request_origin not in self.allowed_origins:
                logger.warning(
                    "CORS request blocked",
                    extra={
                        "origin": request_origin,
                        "path": request.url.path,
                        "method": request.method,
                        "client_ip": self._get_client_ip(request),
                        "user_agent": request.headers.get("user-agent", ""),
                        "environment": os.getenv("ENVIRONMENT", "dev")
                    }
                )
                # TODO: Add metrics collection for blocked CORS requests
                # CORS_BLOCKED_COUNTER.inc(labels={"origin": request_origin})
        
        response = await call_next(request)
        return response
    
    def _get_client_ip(self, request: Request) -> str:
        """Extract client IP from request headers"""
        # Check for common proxy headers
        forwarded_for = request.headers.get("x-forwarded-for")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()
        
        real_ip = request.headers.get("x-real-ip")
        if real_ip:
            return real_ip
        
        # Fallback to direct client
        if request.client:
            return request.client.host
        
        return "unknown"


def setup_secure_cors(app, environment: Optional[str] = None) -> None:
    """
    Setup secure CORS configuration for FastAPI application
    
    Args:
        app: FastAPI application instance
        environment: Deployment environment (dev/test/prod)
    """
    config_loader = CORSConfigLoader(environment)
    cors_config = config_loader.get_cors_config()
    
    logger.info(
        f"Configuring CORS for environment: {config_loader.environment}",
        extra={
            "allowed_origins_count": len(cors_config["allow_origins"]),
            "allow_credentials": cors_config["allow_credentials"],
            "max_age": cors_config["max_age"]
        }
    )
    
    # Add CORS middleware with secure configuration
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_config["allow_origins"],
        allow_credentials=cors_config["allow_credentials"],
        allow_methods=SECURITY_HEADERS["allow_methods"],
        allow_headers=SECURITY_HEADERS["allow_headers"],
        expose_headers=SECURITY_HEADERS["expose_headers"],
        max_age=cors_config["max_age"]
    )
    
    # Add CORS monitoring middleware
    app.add_middleware(CORSMonitoringMiddleware, allowed_origins=cors_config["allow_origins"])
    
    logger.info(
        "CORS security configuration complete",
        extra={
            "environment": config_loader.environment,
            "origins": cors_config["allow_origins"],
            "security_validation": "passed"
        }
    )


def validate_cors_startup(environment: Optional[str] = None) -> bool:
    """
    Validate CORS configuration on application startup
    
    Returns:
        bool: True if configuration is valid, raises exception otherwise
    """
    try:
        config_loader = CORSConfigLoader(environment)
        cors_config = config_loader.get_cors_config()
        
        # Additional startup validations
        if not cors_config.get("allow_origins"):
            raise ValueError("CORS allowed origins cannot be empty")
        
        # Check for security anti-patterns
        for origin in cors_config["allow_origins"]:
            if origin.endswith("*"):
                raise ValueError(f"Wildcard subdomain not allowed: {origin}")
        
        logger.info(
            "CORS configuration validation passed",
            extra={
                "environment": config_loader.environment,
                "origins_count": len(cors_config["allow_origins"])
            }
        )
        
        return True
        
    except Exception as e:
        logger.error(
            "CORS configuration validation failed",
            extra={
                "environment": environment,
                "error": str(e)
            }
        )
        raise


# Health check function for CORS status
def get_cors_health_status(environment: Optional[str] = None) -> Dict[str, Any]:
    """
    Get CORS configuration health status for monitoring
    
    Returns:
        Dict with CORS configuration status and metadata
    """
    try:
        config_loader = CORSConfigLoader(environment)
        cors_config = config_loader.get_cors_config()
        
        return {
            "status": "healthy",
            "environment": config_loader.environment,
            "origins_configured": len(cors_config["allow_origins"]),
            "credentials_allowed": cors_config["allow_credentials"],
            "max_age": cors_config["max_age"],
            "validation": "passed",
            "timestamp": os.getenv("BUILD_TIMESTAMP", "unknown")
        }
        
    except Exception as e:
        return {
            "status": "unhealthy",
            "environment": environment or "unknown",
            "error": str(e),
            "validation": "failed",
            "timestamp": os.getenv("BUILD_TIMESTAMP", "unknown")
        }