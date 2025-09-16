"""
BUG-002 Fix: HTTPS Canonical Redirect Middleware

Ensures all traffic uses the canonical scheme (HTTPS in prod/test, HTTP allowed in dev).
Provides 308 permanent redirects for non-canonical requests to maintain SEO and prevent
mixed content/session issues.
"""

import os
from typing import Optional
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import RedirectResponse

from .ttrpg_logging import get_logger

logger = get_logger(__name__)


class EnforceSchemeMiddleware(BaseHTTPMiddleware):
    """
    Middleware to enforce canonical scheme (HTTP/HTTPS) based on environment.
    
    Configuration:
    - CANONICAL_SCHEME env var: "http" or "https" (default: "https")
    - APP_ENV env var: "dev" allows HTTP, others enforce HTTPS
    """
    
    def __init__(self, app, canonical_scheme: Optional[str] = None):
        super().__init__(app)
        
        # Determine canonical scheme from config or environment
        if canonical_scheme:
            self.canonical_scheme = canonical_scheme
        else:
            env = os.getenv('APP_ENV', 'dev').lower()
            # Dev allows HTTP, all other environments default to HTTPS
            self.canonical_scheme = os.getenv('CANONICAL_SCHEME', 'http' if env == 'dev' else 'https')
        
        logger.info(f"EnforceSchemeMiddleware initialized with canonical scheme: {self.canonical_scheme}")
    
    async def dispatch(self, request: Request, call_next):
        """
        Check request scheme and redirect if not canonical.
        
        Priority order for scheme detection:
        1. X-Forwarded-Proto header (reverse proxy)
        2. X-Forwarded-Scheme header (alternative)
        3. Request URL scheme (direct connection)
        """
        
        # Get actual scheme from headers (proxy) or request
        actual_scheme = (
            request.headers.get("x-forwarded-proto") or 
            request.headers.get("x-forwarded-scheme") or 
            request.url.scheme
        )
        
        # Skip redirect if scheme is already canonical or if canonical is HTTP
        if self.canonical_scheme == "http" or actual_scheme == self.canonical_scheme:
            return await call_next(request)
        
        # Perform redirect to canonical scheme
        target_url = request.url.replace(scheme=self.canonical_scheme)
        
        logger.info(
            f"Redirecting {actual_scheme} request to canonical scheme: "
            f"{request.url} -> {target_url}"
        )
        
        # Use 308 (Permanent Redirect) to preserve request method and body
        return RedirectResponse(str(target_url), status_code=308)


def add_security_headers_middleware(app):
    """
    Add security headers based on environment and scheme.
    
    HSTS (Strict-Transport-Security) only added in production with HTTPS.
    """
    
    @app.middleware("http")
    async def security_headers(request: Request, call_next):
        response = await call_next(request)
        
        env = os.getenv('APP_ENV', 'dev').lower()
        canonical_scheme = os.getenv('CANONICAL_SCHEME', 'http' if env == 'dev' else 'https')
        
        # Add HSTS header in production with HTTPS
        if env in ['prod', 'production'] and canonical_scheme == 'https':
            # 1 year HSTS with subdomain inclusion and preload eligibility
            response.headers["Strict-Transport-Security"] = (
                "max-age=31536000; includeSubDomains; preload"
            )
            logger.debug("Added HSTS header for production HTTPS")
        
        # Add other security headers for all environments
        response.headers.update({
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": "DENY",
            "X-XSS-Protection": "1; mode=block",
            "Referrer-Policy": "strict-origin-when-cross-origin"
        })
        
        return response
    
    return app


def configure_canonical_redirect(app, canonical_scheme: Optional[str] = None):
    """
    Configure the application with canonical scheme redirection and security headers.
    
    Args:
        app: FastAPI application instance
        canonical_scheme: Override canonical scheme (optional)
        
    Returns:
        Configured app with middleware applied
    """
    
    # Add scheme enforcement middleware
    app.add_middleware(EnforceSchemeMiddleware, canonical_scheme=canonical_scheme)
    
    # Add security headers
    app = add_security_headers_middleware(app)
    
    logger.info("Canonical redirect and security headers configured")
    return app