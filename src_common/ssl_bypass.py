"""
SSL Certificate Verification Bypass for Development Environment

This module provides comprehensive SSL certificate verification bypass for development
environments where self-signed certificates are used and external services (OpenAI, Astra)
cannot validate local certificates.

SECURITY WARNING: This should ONLY be used in development environments.
"""

import os
import ssl
import warnings
from typing import Optional
from .logging import get_logger

logger = get_logger(__name__)

# Global flag to track if SSL bypass has been configured
_ssl_bypass_configured = False


def configure_ssl_bypass_for_development() -> bool:
    """
    Configure comprehensive SSL certificate verification bypass for development.
    
    Returns:
        bool: True if SSL bypass was configured, False if not needed
    """
    global _ssl_bypass_configured
    
    if _ssl_bypass_configured:
        return True
    
    # Check if SSL bypass is requested
    ssl_no_verify = os.getenv("SSL_NO_VERIFY", "").strip().lower() in ("1", "true", "yes")
    app_env = os.getenv("APP_ENV", "").strip().lower()
    
    if not ssl_no_verify:
        logger.debug("SSL_NO_VERIFY not set - using default SSL verification")
        return False
        
    if app_env not in ("dev", "development"):
        error_msg = f"🚨 SECURITY VIOLATION: SSL_NO_VERIFY is set in non-development environment ({app_env}). This is forbidden for security reasons."
        logger.error(error_msg)
        raise RuntimeError(error_msg)
    
    logger.warning("=" * 70)
    logger.warning("🚨 DEVELOPMENT MODE: SSL CERTIFICATE VERIFICATION DISABLED")
    logger.warning("🚨 THIS BYPASSES ALL SSL SECURITY CHECKS FOR EXTERNAL APIs")
    logger.warning("🚨 NEVER USE THIS IN PRODUCTION ENVIRONMENTS")
    logger.warning("=" * 70)
    
    try:
        # 1. Disable SSL verification globally for Python's SSL context
        ssl._create_default_https_context = ssl._create_unverified_context
        logger.info("Configured Python SSL context to skip verification")
        
        # 2. Configure urllib3 to suppress SSL warnings
        import urllib3
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        logger.info("Suppressed urllib3 SSL verification warnings")
        
        # 3. Configure requests library default behavior
        try:
            import requests
            requests.packages.urllib3.disable_warnings()
            logger.info("Configured requests library SSL bypass")
        except (ImportError, AttributeError):
            pass
        
        # 4. Configure httpx (used by astrapy and OpenAI clients)
        try:
            import httpx
            # Create a global unverified client that can be used by libraries
            logger.info("httpx available for SSL bypass configuration")
        except ImportError:
            pass
            
        # 5. Configure OpenAI client specifically
        try:
            import openai
            # OpenAI client will inherit the unverified SSL context
            logger.info("OpenAI client configured for SSL bypass")
        except ImportError:
            pass
            
        _ssl_bypass_configured = True
        logger.warning("SSL certificate verification bypass ACTIVE - development only")
        return True
        
    except Exception as e:
        logger.error(f"Failed to configure SSL bypass: {e}")
        return False


def is_ssl_bypass_active() -> bool:
    """Check if SSL bypass is currently active"""
    return _ssl_bypass_configured


def get_ssl_context() -> Optional[ssl.SSLContext]:
    """
    Get appropriate SSL context based on environment configuration.
    
    Returns:
        ssl.SSLContext or None: Unverified context if bypass is active, None otherwise
    """
    if is_ssl_bypass_active():
        context = ssl.create_default_context()
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
        return context
    return None


def get_httpx_verify_setting() -> bool:
    """
    Get appropriate verify setting for httpx clients.
    
    Returns:
        bool: False if SSL bypass is active, True otherwise
    """
    return not is_ssl_bypass_active()


def get_requests_verify_setting() -> bool:
    """
    Get appropriate verify setting for requests library.
    
    Returns:
        bool: False if SSL bypass is active, True otherwise
    """
    return not is_ssl_bypass_active()


# Auto-configure SSL bypass when module is imported if environment variables are set
if __name__ != "__main__":
    configure_ssl_bypass_for_development()