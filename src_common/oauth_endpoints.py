"""
OAuth Authentication Endpoints
FastAPI endpoints for OAuth authentication flows
"""

import os
from typing import Optional, Dict, Any
from urllib.parse import quote

from fastapi import APIRouter, HTTPException, Query, Depends, Request
from fastapi.responses import RedirectResponse, JSONResponse

from src_common.ttrpg_logging import get_logger
from src_common.oauth_service import OAuthAuthenticationService
from src_common.auth_models import (
    OAuthLoginRequest, OAuthLoginResponse, OAuthCallbackRequest, 
    OAuthLoginResult, AuthError, UserProfile
)
from src_common.auth_middleware import get_current_user, UserContext

logger = get_logger(__name__)

# OAuth service will be initialized lazily
oauth_service = None

def get_oauth_service() -> OAuthAuthenticationService:
    """Get OAuth service instance (lazy initialization)"""
    global oauth_service
    if oauth_service is None:
        oauth_service = OAuthAuthenticationService()
    return oauth_service

# Create router
oauth_router = APIRouter(prefix="/auth/oauth", tags=["OAuth Authentication"])


@oauth_router.get("/login/{provider}")
async def oauth_login(
    provider: str,
    return_url: Optional[str] = Query(None, description="URL to redirect after authentication"),
    request: Request = None
):
    """
    Initiate OAuth login flow for specified provider
    
    Args:
        provider: OAuth provider name (currently supports 'google')
        return_url: Optional URL to redirect after successful authentication
        
    Returns:
        Authorization URL for OAuth provider
    """
    try:
        # Validate provider
        if provider.lower() not in ["google"]:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported OAuth provider: {provider}"
            )
        
        # Get authorization URL
        auth_url = get_oauth_service().get_oauth_login_url(provider, return_url)
        
        if not auth_url:
            logger.error(f"Failed to generate OAuth URL for provider: {provider}")
            raise HTTPException(
                status_code=500,
                detail="Failed to generate OAuth authorization URL"
            )
        
        logger.info(f"Generated OAuth login URL for provider: {provider}")
        
        # Return a redirect response instead of JSON
        return RedirectResponse(url=auth_url, status_code=302)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in OAuth login endpoint: {e}")
        raise HTTPException(
            status_code=500,
            detail="Internal server error during OAuth initialization"
        )


@oauth_router.get("/login/{provider}/redirect")
async def oauth_login_redirect(
    provider: str,
    return_url: Optional[str] = Query(None, description="URL to redirect after authentication")
):
    """
    Direct redirect to OAuth provider (alternative to JSON response)
    
    Args:
        provider: OAuth provider name
        return_url: Optional URL to redirect after successful authentication
        
    Returns:
        HTTP redirect to OAuth provider
    """
    try:
        # Validate provider
        if provider.lower() not in ["google"]:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported OAuth provider: {provider}"
            )
        
        # Get authorization URL
        auth_url = get_oauth_service().get_oauth_login_url(provider, return_url)
        
        if not auth_url:
            logger.error(f"Failed to generate OAuth URL for provider: {provider}")
            raise HTTPException(
                status_code=500,
                detail="Failed to generate OAuth authorization URL"
            )
        
        logger.info(f"Redirecting to OAuth provider: {provider}")
        return RedirectResponse(url=auth_url)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in OAuth redirect endpoint: {e}")
        raise HTTPException(
            status_code=500,
            detail="Internal server error during OAuth redirect"
        )


@oauth_router.get("/callback", response_model=OAuthLoginResult)
async def oauth_callback(
    code: str = Query(..., description="Authorization code from OAuth provider"),
    state: str = Query(..., description="State parameter from OAuth provider"),
    error: Optional[str] = Query(None, description="Error from OAuth provider"),
    error_description: Optional[str] = Query(None, description="Error description from OAuth provider")
):
    """
    Handle OAuth callback from provider
    
    Args:
        code: Authorization code
        state: State parameter for security
        error: Error code if authorization failed
        error_description: Human-readable error description
        
    Returns:
        JWT tokens and user information
    """
    try:
        # Check for OAuth provider errors
        if error:
            logger.warning(f"OAuth provider returned error: {error} - {error_description}")
            raise HTTPException(
                status_code=400,
                detail=f"OAuth authorization failed: {error_description or error}"
            )
        
        # Extract provider from state or default to google
        # In a more robust implementation, we'd encode the provider in the state
        provider = "google"  # For now, only supporting Google
        
        # Handle OAuth callback
        auth_result = await get_oauth_service().handle_oauth_callback(provider, code, state)
        
        if not auth_result:
            logger.error("OAuth callback handling failed")
            raise HTTPException(
                status_code=400,
                detail="OAuth authentication failed"
            )
        
        logger.info(f"OAuth authentication successful for user: {auth_result['user']['username']}")
        
        # Create response with user profile
        user_profile = UserProfile(
            user_id=auth_result["user"]["id"],
            username=auth_result["user"]["username"],
            email=auth_result["user"]["email"],
            role=auth_result["user"]["role"],
            is_active=True,
            created_at=None,  # Would need to get from database
            last_login=None
        )
        
        return OAuthLoginResult(
            access_token=auth_result["access_token"],
            refresh_token=auth_result["refresh_token"],
            token_type=auth_result["token_type"],
            expires_in=3600,  # 1 hour
            user=user_profile,
            oauth_provider=auth_result["user"]["oauth_provider"],
            return_url=auth_result.get("return_url")
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in OAuth callback: {e}")
        raise HTTPException(
            status_code=500,
            detail="Internal server error during OAuth callback"
        )


@oauth_router.get("/callback/redirect")
async def oauth_callback_redirect(
    code: str = Query(..., description="Authorization code from OAuth provider"),
    state: str = Query(..., description="State parameter from OAuth provider"),
    error: Optional[str] = Query(None, description="Error from OAuth provider"),
    error_description: Optional[str] = Query(None, description="Error description from OAuth provider")
):
    """
    Handle OAuth callback with redirect (for web applications)
    
    This endpoint processes the OAuth callback and redirects to the frontend
    with tokens as URL parameters or error information.
    """
    try:
        # Check for OAuth provider errors
        if error:
            logger.warning(f"OAuth provider returned error: {error} - {error_description}")
            # Redirect to frontend with error
            error_url = f"/oauth/error?error={quote(error)}&description={quote(error_description or '')}"
            return RedirectResponse(url=error_url)
        
        # Handle OAuth callback
        provider = "google"  # For now, only supporting Google
        auth_result = await get_oauth_service().handle_oauth_callback(provider, code, state)
        
        if not auth_result:
            logger.error("OAuth callback handling failed")
            error_url = "/oauth/error?error=authentication_failed&description=OAuth authentication failed"
            return RedirectResponse(url=error_url)
        
        logger.info(f"OAuth authentication successful for user: {auth_result['user']['username']}")
        
        # Determine redirect URL
        return_url = auth_result.get("return_url", "/")
        
        # Add tokens as URL parameters (in production, consider using secure cookies or POST message)
        redirect_url = f"{return_url}?access_token={auth_result['access_token']}&refresh_token={auth_result['refresh_token']}&token_type={auth_result['token_type']}"
        
        return RedirectResponse(url=redirect_url)
        
    except Exception as e:
        logger.error(f"Error in OAuth callback redirect: {e}")
        error_url = f"/oauth/error?error=server_error&description={quote(str(e))}"
        return RedirectResponse(url=error_url)


@oauth_router.get("/user", response_model=UserProfile)
async def get_oauth_user_profile(current_user: UserContext = Depends(get_current_user)):
    """
    Get current OAuth user profile
    
    Args:
        current_user: Current authenticated user context
        
    Returns:
        User profile information
    """
    try:
        # This endpoint is protected by JWT authentication
        # The user context is provided by the auth middleware
        
        logger.info(f"Retrieved OAuth user profile for: {current_user.username}")
        
        return UserProfile(
            user_id=current_user.user_id,
            username=current_user.username,
            email="",  # Would need to get from database
            role=current_user.role,
            is_active=current_user.is_active,
            created_at=None,  # Would need to get from database
            last_login=None
        )
        
    except Exception as e:
        logger.error(f"Error getting OAuth user profile: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to retrieve user profile"
        )


@oauth_router.post("/logout")
async def oauth_logout(
    oauth_token: Optional[str] = Query(None, description="OAuth access token to revoke"),
    current_user: UserContext = Depends(get_current_user)
):
    """
    Logout OAuth user and revoke tokens
    
    Args:
        oauth_token: OAuth access token to revoke
        current_user: Current authenticated user context
        
    Returns:
        Logout confirmation
    """
    try:
        # Get JWT token from the request (would need to extract from Authorization header)
        # For now, we'll just blacklist based on user context
        jwt_token = ""  # Would extract from request headers
        
        # Determine OAuth provider (would get from user profile)
        provider = "google"  # Default to Google for now
        
        # Revoke OAuth session
        if oauth_token:
            success = await get_oauth_service().revoke_oauth_session(provider, oauth_token, jwt_token)
            if not success:
                logger.warning(f"Failed to fully revoke OAuth session for user: {current_user.username}")
        
        logger.info(f"OAuth logout completed for user: {current_user.username}")
        
        return {
            "message": "Logout successful",
            "user_id": current_user.user_id,
            "revoked": bool(oauth_token)
        }
        
    except Exception as e:
        logger.error(f"Error during OAuth logout: {e}")
        raise HTTPException(
            status_code=500,
            detail="Logout failed"
        )


@oauth_router.get("/providers")
async def get_oauth_providers():
    """
    Get available OAuth providers
    
    Returns:
        List of available OAuth providers and their configuration
    """
    try:
        providers = []
        
        # Check if Google OAuth is configured
        if all([
            os.getenv("GOOGLE_CLIENT_ID"),
            os.getenv("GOOGLE_CLIENT_SECRET"), 
            os.getenv("GOOGLE_CLIENT_REDIRECT_URL")
        ]):
            providers.append({
                "name": "google",
                "display_name": "Google",
                "available": True,
                "login_url": "/auth/oauth/login/google",
                "redirect_url": "/auth/oauth/login/google/redirect"
            })
        else:
            providers.append({
                "name": "google",
                "display_name": "Google", 
                "available": False,
                "reason": "OAuth credentials not configured"
            })
        
        return {
            "providers": providers,
            "environment": os.getenv("APP_ENV", "dev")
        }
        
    except Exception as e:
        logger.error(f"Error getting OAuth providers: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to retrieve OAuth providers"
        )


# Error handling endpoints for web redirects
@oauth_router.get("/error")
async def oauth_error(
    error: str = Query(..., description="Error code"),
    description: Optional[str] = Query(None, description="Error description")
):
    """
    OAuth error page (for web redirects)
    
    Returns:
        Error information for display
    """
    return {
        "error": error,
        "description": description,
        "message": "OAuth authentication failed",
        "retry_url": "/auth/oauth/providers"
    }


# Health check for OAuth service
@oauth_router.get("/health")
async def oauth_health():
    """
    OAuth service health check
    
    Returns:
        OAuth service status and configuration
    """
    try:
        # Check OAuth configuration
        google_configured = all([
            os.getenv("GOOGLE_CLIENT_ID"),
            os.getenv("GOOGLE_CLIENT_SECRET"),
            os.getenv("GOOGLE_CLIENT_REDIRECT_URL")
        ])
        
        # Clean up expired states
        get_oauth_service().cleanup_expired_states()
        
        return {
            "status": "healthy",
            "service": "oauth-authentication",
            "providers": {
                "google": {
                    "configured": google_configured,
                    "client_id": os.getenv("GOOGLE_CLIENT_ID", "not_set")[:20] + "..." if google_configured else None
                }
            },
            "environment": os.getenv("APP_ENV", "dev")
        }
        
    except Exception as e:
        logger.error(f"OAuth health check failed: {e}")
        return JSONResponse(
            status_code=500,
            content={
                "status": "unhealthy",
                "error": str(e),
                "service": "oauth-authentication"
            }
        )