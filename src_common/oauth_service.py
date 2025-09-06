"""
OAuth Authentication Service
Handles Google OAuth integration with JWT token generation
"""

import os
import json
import secrets
import time
from typing import Dict, Optional, Tuple, Any
from urllib.parse import urlencode
from datetime import datetime, timezone
from pathlib import Path

import httpx
from authlib.integrations.httpx_client import AsyncOAuth2Client
from authlib.common.errors import AuthlibBaseError

from src_common.ttrpg_logging import get_logger
from src_common.jwt_service import JWTService, AuthenticationService
from src_common.auth_database import AuthDatabaseManager
from src_common.auth_models import UserRole

# Load environment configuration
def load_env_config():
    """Load environment-specific configuration"""
    env = os.getenv("APP_ENV", os.getenv("ENVIRONMENT", "dev"))
    env_file = Path(f"env/{env}/config/.env")
    
    if env_file.exists():
        from dotenv import load_dotenv
        load_dotenv(env_file)
        
load_env_config()

logger = get_logger(__name__)


class OAuthConfig:
    """OAuth configuration for different providers"""
    
    GOOGLE = {
        "authorization_url": "https://accounts.google.com/o/oauth2/v2/auth",
        "token_url": "https://oauth2.googleapis.com/token",
        "userinfo_url": "https://www.googleapis.com/oauth2/v2/userinfo",
        "revoke_url": "https://oauth2.googleapis.com/revoke",
        "scopes": ["openid", "email", "profile"]
    }


class OAuthStateManager:
    """Manage OAuth state tokens for security"""
    
    def __init__(self):
        self._states: Dict[str, Dict[str, Any]] = {}
    
    def generate_state(self, provider: str, return_url: Optional[str] = None) -> str:
        """Generate secure state token for OAuth flow"""
        state_token = secrets.token_urlsafe(32)
        self._states[state_token] = {
            "provider": provider,
            "return_url": return_url,
            "created_at": time.time(),
            "expires_at": time.time() + 600  # 10 minutes
        }
        logger.debug(f"Generated OAuth state for {provider}: {state_token[:8]}...")
        return state_token
    
    def validate_state(self, state_token: str, provider: str) -> Tuple[bool, Optional[str]]:
        """Validate state token and return return_url if valid"""
        if state_token not in self._states:
            logger.warning(f"Invalid OAuth state token: {state_token[:8]}...")
            return False, None
        
        state_data = self._states[state_token]
        
        # Check expiration
        if time.time() > state_data["expires_at"]:
            logger.warning(f"Expired OAuth state token: {state_token[:8]}...")
            del self._states[state_token]
            return False, None
        
        # Check provider match
        if state_data["provider"] != provider:
            logger.warning(f"Provider mismatch for state token: expected {provider}, got {state_data['provider']}")
            return False, None
        
        return_url = state_data.get("return_url")
        del self._states[state_token]  # One-time use
        
        logger.debug(f"Validated OAuth state for {provider}")
        return True, return_url
    
    def cleanup_expired_states(self):
        """Clean up expired state tokens"""
        current_time = time.time()
        expired_tokens = [
            token for token, data in self._states.items()
            if current_time > data["expires_at"]
        ]
        
        for token in expired_tokens:
            del self._states[token]
        
        if expired_tokens:
            logger.debug(f"Cleaned up {len(expired_tokens)} expired OAuth state tokens")


class GoogleOAuthService:
    """Google OAuth 2.0 integration service"""
    
    def __init__(self):
        """Initialize Google OAuth service"""
        self.client_id = os.getenv("GOOGLE_CLIENT_ID")
        self.client_secret = os.getenv("GOOGLE_CLIENT_SECRET")
        self.redirect_url = os.getenv("GOOGLE_CLIENT_REDIRECT_URL")
        
        if not all([self.client_id, self.client_secret, self.redirect_url]):
            logger.error("Missing Google OAuth configuration")
            raise ValueError("Google OAuth credentials not configured")
        
        self.config = OAuthConfig.GOOGLE
        self.state_manager = OAuthStateManager()
        
        logger.info("Google OAuth service initialized")
    
    def get_authorization_url(self, return_url: Optional[str] = None) -> str:
        """
        Generate Google OAuth authorization URL
        
        Args:
            return_url: URL to redirect after successful authentication
            
        Returns:
            Authorization URL for user redirect
        """
        state_token = self.state_manager.generate_state("google", return_url)
        
        params = {
            "client_id": self.client_id,
            "redirect_uri": self.redirect_url,
            "scope": " ".join(self.config["scopes"]),
            "response_type": "code",
            "state": state_token,
            "access_type": "offline",  # Get refresh token
            "prompt": "consent"  # Force consent to get refresh token
        }
        
        auth_url = f"{self.config['authorization_url']}?{urlencode(params)}"
        logger.debug(f"Generated Google OAuth URL for state: {state_token[:8]}...")
        
        return auth_url
    
    async def exchange_code_for_token(self, code: str, state: str) -> Optional[Dict[str, Any]]:
        """
        Exchange authorization code for access token
        
        Args:
            code: Authorization code from callback
            state: State token for validation
            
        Returns:
            Token response or None if failed
        """
        # Validate state
        is_valid, return_url = self.state_manager.validate_state(state, "google")
        if not is_valid:
            logger.error("Invalid OAuth state in token exchange")
            return None
        
        try:
            async with AsyncOAuth2Client(
                client_id=self.client_id,
                client_secret=self.client_secret
            ) as client:
                token_response = await client.fetch_token(
                    self.config["token_url"],
                    authorization_response_url=f"{self.redirect_url}?code={code}&state={state}",
                    redirect_uri=self.redirect_url
                )
                
                logger.info("Successfully exchanged OAuth code for token")
                token_response["return_url"] = return_url
                return token_response
                
        except AuthlibBaseError as e:
            logger.error(f"OAuth token exchange failed: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error in token exchange: {e}")
            return None
    
    async def get_user_info(self, access_token: str) -> Optional[Dict[str, Any]]:
        """
        Get user information from Google
        
        Args:
            access_token: OAuth access token
            
        Returns:
            User information or None if failed
        """
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    self.config["userinfo_url"],
                    headers={"Authorization": f"Bearer {access_token}"}
                )
                response.raise_for_status()
                
                user_info = response.json()
                logger.info(f"Retrieved user info for: {user_info.get('email', 'unknown')}")
                
                return user_info
                
        except httpx.HTTPStatusError as e:
            logger.error(f"Failed to get user info: HTTP {e.response.status_code}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error getting user info: {e}")
            return None
    
    async def revoke_token(self, token: str) -> bool:
        """
        Revoke OAuth token
        
        Args:
            token: Access or refresh token to revoke
            
        Returns:
            True if successful
        """
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self.config["revoke_url"],
                    params={"token": token}
                )
                
                if response.status_code == 200:
                    logger.info("Successfully revoked OAuth token")
                    return True
                else:
                    logger.warning(f"Token revocation returned status: {response.status_code}")
                    return False
                    
        except Exception as e:
            logger.error(f"Error revoking token: {e}")
            return False


class OAuthUserManager:
    """Manage OAuth user accounts and synchronization"""
    
    def __init__(self, db_manager: AuthDatabaseManager):
        """Initialize OAuth user manager"""
        self.db_manager = db_manager
    
    def sync_oauth_user(self, oauth_info: Dict[str, Any], provider: str) -> Optional[str]:
        """
        Synchronize OAuth user with local database
        
        Args:
            oauth_info: User information from OAuth provider
            provider: OAuth provider name (e.g., 'google')
            
        Returns:
            User ID if successful, None if failed
        """
        try:
            email = oauth_info.get("email")
            if not email:
                logger.error("No email in OAuth user info")
                return None
            
            # Check if user exists by email
            existing_user = self.db_manager.get_user_by_email(email)
            
            if existing_user:
                # Update existing user's OAuth info
                self._update_oauth_info(existing_user.id, oauth_info, provider)
                logger.info(f"Updated OAuth info for existing user: {email}")
                return existing_user.id
            else:
                # Create new user from OAuth info
                user_id = self._create_oauth_user(oauth_info, provider)
                if user_id:
                    logger.info(f"Created new OAuth user: {email}")
                    return user_id
                else:
                    logger.error(f"Failed to create OAuth user: {email}")
                    return None
                
        except Exception as e:
            logger.error(f"Error syncing OAuth user: {e}")
            return None
    
    def _create_oauth_user(self, oauth_info: Dict[str, Any], provider: str) -> Optional[str]:
        """Create new user from OAuth information"""
        try:
            email = oauth_info["email"]
            name = oauth_info.get("name", email.split("@")[0])
            
            # Generate username from email
            username = email.split("@")[0]
            counter = 1
            original_username = username
            
            # Handle username conflicts
            while self.db_manager.get_user_by_username(username):
                username = f"{original_username}_{counter}"
                counter += 1
            
            # Create user (OAuth users don't have passwords)
            user_id = self.db_manager.create_user(
                username=username,
                email=email,
                password_hash="",  # No password for OAuth users
                role=UserRole.USER,
                full_name=name,
                oauth_provider=provider,
                oauth_id=oauth_info.get("id", oauth_info.get("sub")),
                is_oauth_user=True
            )
            
            return user_id
            
        except Exception as e:
            logger.error(f"Error creating OAuth user: {e}")
            return None
    
    def _update_oauth_info(self, user_id: str, oauth_info: Dict[str, Any], provider: str):
        """Update existing user's OAuth information"""
        try:
            # Update user's OAuth provider info
            # This would require extending the database schema
            # For now, just log the update
            logger.info(f"OAuth info updated for user {user_id} (provider: {provider})")
            
        except Exception as e:
            logger.error(f"Error updating OAuth info: {e}")


class OAuthAuthenticationService:
    """Complete OAuth authentication service"""
    
    def __init__(self):
        """Initialize OAuth authentication service"""
        self.google_oauth = GoogleOAuthService()
        self.jwt_service = JWTService()
        self.auth_service = AuthenticationService()
        
        # Initialize database manager
        db_url = os.getenv("AUTH_DATABASE_URL", "sqlite:///./auth.db")
        self.db_manager = AuthDatabaseManager(db_url)
        self.user_manager = OAuthUserManager(self.db_manager)
        
        logger.info("OAuth authentication service initialized")
    
    def get_oauth_login_url(self, provider: str, return_url: Optional[str] = None) -> Optional[str]:
        """
        Get OAuth login URL for provider
        
        Args:
            provider: OAuth provider name
            return_url: URL to redirect after authentication
            
        Returns:
            Authorization URL or None if provider not supported
        """
        if provider.lower() == "google":
            return self.google_oauth.get_authorization_url(return_url)
        else:
            logger.error(f"Unsupported OAuth provider: {provider}")
            return None
    
    async def handle_oauth_callback(self, provider: str, code: str, state: str) -> Optional[Dict[str, Any]]:
        """
        Handle OAuth callback and generate JWT tokens
        
        Args:
            provider: OAuth provider name
            code: Authorization code
            state: State token
            
        Returns:
            Authentication result with JWT tokens or None if failed
        """
        if provider.lower() != "google":
            logger.error(f"Unsupported OAuth provider: {provider}")
            return None
        
        try:
            # Exchange code for token
            token_data = await self.google_oauth.exchange_code_for_token(code, state)
            if not token_data:
                logger.error("Failed to exchange OAuth code for token")
                return None
            
            # Get user information
            user_info = await self.google_oauth.get_user_info(token_data["access_token"])
            if not user_info:
                logger.error("Failed to get OAuth user information")
                return None
            
            # Sync user with database
            user_id = self.user_manager.sync_oauth_user(user_info, provider)
            if not user_id:
                logger.error("Failed to sync OAuth user")
                return None
            
            # Get user from database
            user = self.db_manager.get_user_by_id(user_id)
            if not user:
                logger.error(f"User not found after sync: {user_id}")
                return None
            
            # Generate JWT tokens
            access_token = self.jwt_service.create_access_token(
                user_id=user.id,
                username=user.username,
                role=user.role
            )
            
            refresh_token = self.jwt_service.create_refresh_token(
                user_id=user.id,
                username=user.username
            )
            
            result = {
                "access_token": access_token,
                "refresh_token": refresh_token,
                "token_type": "bearer",
                "user": {
                    "id": user.id,
                    "username": user.username,
                    "email": user.email,
                    "full_name": user.full_name,
                    "role": user.role.value,
                    "oauth_provider": provider
                },
                "oauth_token": token_data["access_token"],
                "return_url": token_data.get("return_url")
            }
            
            logger.info(f"OAuth authentication successful for user: {user.username}")
            return result
            
        except Exception as e:
            logger.error(f"Error in OAuth callback handling: {e}")
            return None
    
    async def revoke_oauth_session(self, provider: str, oauth_token: str, jwt_token: str) -> bool:
        """
        Revoke OAuth session and JWT token
        
        Args:
            provider: OAuth provider name
            oauth_token: OAuth access token to revoke
            jwt_token: JWT token to blacklist
            
        Returns:
            True if successful
        """
        success = True
        
        try:
            # Revoke OAuth token
            if provider.lower() == "google":
                oauth_revoked = await self.google_oauth.revoke_token(oauth_token)
                if not oauth_revoked:
                    logger.warning("Failed to revoke OAuth token")
                    success = False
            
            # Blacklist JWT token
            jwt_revoked = self.jwt_service.blacklist_token(jwt_token)
            if not jwt_revoked:
                logger.warning("Failed to blacklist JWT token")
                success = False
            
            if success:
                logger.info(f"Successfully revoked OAuth session for provider: {provider}")
            
            return success
            
        except Exception as e:
            logger.error(f"Error revoking OAuth session: {e}")
            return False
    
    def cleanup_expired_states(self):
        """Clean up expired OAuth state tokens"""
        self.google_oauth.state_manager.cleanup_expired_states()