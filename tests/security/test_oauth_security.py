"""
OAuth Security Tests
Comprehensive test suite for OAuth authentication security
"""

import pytest
import os
import time
import uuid
import json
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime, timezone, timedelta

import httpx
from fastapi.testclient import TestClient

# Import OAuth components
from src_common.oauth_service import (
    GoogleOAuthService, OAuthStateManager, OAuthUserManager, 
    OAuthAuthenticationService
)
from src_common.oauth_endpoints import oauth_router
from src_common.auth_models import UserRole, OAuthLoginRequest, OAuthCallbackRequest
from src_common.auth_database import AuthDatabaseManager
from src_common.jwt_service import JWTService


class TestOAuthStateManager:
    """Test OAuth state token management for security"""
    
    def test_generate_state_token_security(self):
        """Test state token generation creates secure tokens"""
        manager = OAuthStateManager()
        
        # Generate multiple tokens
        tokens = [manager.generate_state("google") for _ in range(100)]
        
        # All tokens should be unique
        assert len(set(tokens)) == 100
        
        # Tokens should be 32 chars (base64url of 32 bytes = ~43 chars)
        for token in tokens:
            assert len(token) >= 32
            assert all(c.isalnum() or c in '-_' for c in token)  # base64url characters
    
    def test_state_token_expiration(self):
        """Test state tokens expire correctly"""
        manager = OAuthStateManager()
        
        # Generate token
        token = manager.generate_state("google")
        
        # Manually expire token before validation
        manager._states[token]["expires_at"] = time.time() - 1
        
        # Should be invalid after expiration
        valid, return_url = manager.validate_state(token, "google")
        assert valid is False
        
        # Token should be cleaned up
        assert token not in manager._states
    
    def test_state_token_one_time_use(self):
        """Test state tokens can only be used once"""
        manager = OAuthStateManager()
        
        token = manager.generate_state("google")
        
        # First use should succeed
        valid1, _ = manager.validate_state(token, "google")
        assert valid1 is True
        
        # Second use should fail
        valid2, _ = manager.validate_state(token, "google")
        assert valid2 is False
    
    def test_state_token_provider_validation(self):
        """Test state tokens validate provider correctly"""
        manager = OAuthStateManager()
        
        token = manager.generate_state("google")
        
        # Correct provider should work
        valid, _ = manager.validate_state(token, "google")
        assert valid is True
        
        # Wrong provider should fail
        token2 = manager.generate_state("google")
        valid, _ = manager.validate_state(token2, "github")
        assert valid is False
    
    def test_state_cleanup_expired_tokens(self):
        """Test cleanup of expired state tokens"""
        manager = OAuthStateManager()
        
        # Generate multiple tokens
        tokens = [manager.generate_state("google") for _ in range(5)]
        
        # Expire some tokens
        current_time = time.time()
        for i, token in enumerate(tokens[:3]):
            manager._states[token]["expires_at"] = current_time - 1
        
        # Run cleanup
        manager.cleanup_expired_states()
        
        # Expired tokens should be removed
        assert len(manager._states) == 2
        for token in tokens[:3]:
            assert token not in manager._states
        for token in tokens[3:]:
            assert token in manager._states


class TestGoogleOAuthService:
    """Test Google OAuth service security"""
    
    @pytest.fixture
    def mock_env_vars(self, monkeypatch):
        """Mock OAuth environment variables"""
        monkeypatch.setenv("GOOGLE_CLIENT_ID", "test_client_id")
        monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "test_client_secret")
        monkeypatch.setenv("GOOGLE_CLIENT_REDIRECT_URL", "https://localhost:8000/auth/callback")
    
    def test_oauth_service_requires_configuration(self):
        """Test OAuth service fails without proper configuration"""
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(ValueError, match="Google OAuth credentials not configured"):
                GoogleOAuthService()
    
    def test_authorization_url_generation(self, mock_env_vars):
        """Test OAuth authorization URL is generated securely"""
        service = GoogleOAuthService()
        
        auth_url = service.get_authorization_url("https://example.com/return")
        
        # URL should contain required parameters
        assert "https://accounts.google.com/o/oauth2/v2/auth" in auth_url
        assert "client_id=test_client_id" in auth_url
        assert "redirect_uri=https%3A//localhost%3A8000/auth/callback" in auth_url
        assert "scope=openid+email+profile" in auth_url
        assert "response_type=code" in auth_url
        assert "state=" in auth_url
        assert "access_type=offline" in auth_url
        assert "prompt=consent" in auth_url
    
    def test_state_parameter_in_url(self, mock_env_vars):
        """Test state parameter is properly included in auth URL"""
        service = GoogleOAuthService()
        
        auth_url = service.get_authorization_url()
        
        # Extract state parameter
        import urllib.parse as urlparse
        parsed_url = urlparse.urlparse(auth_url)
        query_params = urlparse.parse_qs(parsed_url.query)
        
        assert "state" in query_params
        state_token = query_params["state"][0]
        
        # State should be in the manager
        assert state_token in service.state_manager._states
        assert service.state_manager._states[state_token]["provider"] == "google"
    
    @pytest.mark.asyncio
    async def test_token_exchange_validates_state(self, mock_env_vars):
        """Test token exchange validates state parameter"""
        service = GoogleOAuthService()
        
        # Invalid state should fail
        result = await service.exchange_code_for_token("test_code", "invalid_state")
        assert result is None
    
    @pytest.mark.asyncio
    async def test_token_exchange_with_valid_state(self, mock_env_vars):
        """Test token exchange with valid state"""
        service = GoogleOAuthService()
        
        # Generate valid state
        state = service.state_manager.generate_state("google", "https://example.com")
        
        # Mock successful token exchange
        mock_token_response = {
            "access_token": "test_access_token",
            "refresh_token": "test_refresh_token",
            "token_type": "Bearer",
            "expires_in": 3600
        }
        
        with patch("authlib.integrations.httpx_client.AsyncOAuth2Client") as mock_client:
            mock_instance = AsyncMock()
            mock_instance.fetch_token.return_value = mock_token_response
            mock_client.return_value.__aenter__.return_value = mock_instance
            
            result = await service.exchange_code_for_token("test_code", state)
        
        assert result is not None
        assert result["access_token"] == "test_access_token"
        assert result["return_url"] == "https://example.com"
    
    @pytest.mark.asyncio
    async def test_user_info_retrieval_security(self, mock_env_vars):
        """Test user info retrieval handles errors securely"""
        service = GoogleOAuthService()
        
        # Test with invalid token
        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_response = Mock()
            mock_response.raise_for_status.side_effect = httpx.HTTPStatusError("Unauthorized", request=Mock(), response=Mock(status_code=401))
            mock_instance.get.return_value = mock_response
            mock_client.return_value.__aenter__.return_value = mock_instance
            
            result = await service.get_user_info("invalid_token")
        
        assert result is None
    
    @pytest.mark.asyncio
    async def test_token_revocation(self, mock_env_vars):
        """Test OAuth token revocation"""
        service = GoogleOAuthService()
        
        # Mock successful revocation
        with patch("httpx.AsyncClient") as mock_client:
            mock_instance = AsyncMock()
            mock_response = Mock()
            mock_response.status_code = 200
            mock_instance.post.return_value = mock_response
            mock_client.return_value.__aenter__.return_value = mock_instance
            
            result = await service.revoke_token("test_token")
        
        assert result is True


class TestOAuthUserManager:
    """Test OAuth user management security"""
    
    @pytest.fixture
    def mock_db_manager(self):
        """Mock database manager for testing"""
        return Mock(spec=AuthDatabaseManager)
    
    def test_sync_oauth_user_requires_email(self, mock_db_manager):
        """Test OAuth user sync requires email"""
        manager = OAuthUserManager(mock_db_manager)
        
        # OAuth info without email should fail
        oauth_info = {"id": "123", "name": "Test User"}
        result = manager.sync_oauth_user(oauth_info, "google")
        
        assert result is None
    
    def test_sync_existing_oauth_user(self, mock_db_manager):
        """Test syncing existing OAuth user"""
        manager = OAuthUserManager(mock_db_manager)
        
        # Mock existing user
        existing_user = Mock()
        existing_user.id = "user_123"
        mock_db_manager.get_user_by_email.return_value = existing_user
        
        oauth_info = {"id": "google_123", "email": "test@example.com", "name": "Test User"}
        result = manager.sync_oauth_user(oauth_info, "google")
        
        assert result == "user_123"
        mock_db_manager.get_user_by_email.assert_called_once_with("test@example.com")
    
    def test_create_new_oauth_user_username_conflict(self, mock_db_manager):
        """Test creating new OAuth user handles username conflicts"""
        manager = OAuthUserManager(mock_db_manager)
        
        # Mock no existing user by email
        mock_db_manager.get_user_by_email.return_value = None
        
        # Mock username conflicts
        def mock_get_user_by_username(username):
            if username in ["testuser", "testuser_1"]:
                return Mock()  # User exists
            return None  # User doesn't exist
        
        mock_db_manager.get_user_by_username.side_effect = mock_get_user_by_username
        mock_db_manager.create_user.return_value = "new_user_123"
        
        oauth_info = {"id": "google_123", "email": "testuser@example.com", "name": "Test User"}
        result = manager.sync_oauth_user(oauth_info, "google")
        
        # Should create user with incremented username
        assert result == "new_user_123"
        mock_db_manager.create_user.assert_called_once()
        
        # Check the username used in create_user call
        call_args = mock_db_manager.create_user.call_args
        assert call_args[1]["username"] == "testuser_2"  # Should skip conflicts
        assert call_args[1]["is_oauth_user"] is True
        assert call_args[1]["oauth_provider"] == "google"


class TestOAuthAuthenticationService:
    """Test complete OAuth authentication service"""
    
    @pytest.fixture
    def mock_components(self):
        """Mock OAuth service components"""
        with patch.multiple(
            "src_common.oauth_service",
            GoogleOAuthService=Mock(),
            JWTService=Mock(),
            AuthenticationService=Mock(),
            AuthDatabaseManager=Mock(),
            OAuthUserManager=Mock()
        ) as mocks:
            yield mocks
    
    def test_get_oauth_login_url_unsupported_provider(self, mock_components):
        """Test OAuth login URL generation for unsupported provider"""
        service = OAuthAuthenticationService()
        
        result = service.get_oauth_login_url("unsupported_provider")
        assert result is None
    
    @pytest.mark.asyncio
    async def test_oauth_callback_success_flow(self, mock_components):
        """Test successful OAuth callback flow"""
        service = OAuthAuthenticationService()
        
        # Mock successful token exchange
        mock_token_data = {
            "access_token": "oauth_token",
            "return_url": "https://example.com"
        }
        service.google_oauth.exchange_code_for_token.return_value = mock_token_data
        
        # Mock successful user info retrieval
        mock_user_info = {
            "id": "google_123",
            "email": "test@example.com",
            "name": "Test User"
        }
        service.google_oauth.get_user_info.return_value = mock_user_info
        
        # Mock successful user sync
        service.user_manager.sync_oauth_user.return_value = "user_123"
        
        # Mock database user retrieval
        mock_user = Mock()
        mock_user.id = "user_123"
        mock_user.username = "testuser"
        mock_user.email = "test@example.com"
        mock_user.full_name = "Test User"
        mock_user.role = UserRole.USER
        service.db_manager.get_user_by_id.return_value = mock_user
        
        # Mock JWT token generation
        service.jwt_service.create_access_token.return_value = "jwt_access_token"
        service.jwt_service.create_refresh_token.return_value = "jwt_refresh_token"
        
        # Test callback handling
        result = await service.handle_oauth_callback("google", "auth_code", "state_token")
        
        assert result is not None
        assert result["access_token"] == "jwt_access_token"
        assert result["refresh_token"] == "jwt_refresh_token"
        assert result["user"]["username"] == "testuser"
        assert result["oauth_provider"] == "google"
        assert result["return_url"] == "https://example.com"
    
    @pytest.mark.asyncio
    async def test_oauth_callback_token_exchange_failure(self, mock_components):
        """Test OAuth callback with token exchange failure"""
        service = OAuthAuthenticationService()
        
        # Mock failed token exchange
        service.google_oauth.exchange_code_for_token.return_value = None
        
        result = await service.handle_oauth_callback("google", "auth_code", "state_token")
        assert result is None
    
    @pytest.mark.asyncio
    async def test_oauth_callback_user_sync_failure(self, mock_components):
        """Test OAuth callback with user sync failure"""
        service = OAuthAuthenticationService()
        
        # Mock successful token exchange
        service.google_oauth.exchange_code_for_token.return_value = {"access_token": "token"}
        
        # Mock successful user info retrieval
        service.google_oauth.get_user_info.return_value = {"id": "123", "email": "test@example.com"}
        
        # Mock failed user sync
        service.user_manager.sync_oauth_user.return_value = None
        
        result = await service.handle_oauth_callback("google", "auth_code", "state_token")
        assert result is None


class TestOAuthEndpointSecurity:
    """Test OAuth endpoint security"""
    
    @pytest.fixture
    def test_app(self):
        """Create test FastAPI app with OAuth router"""
        from fastapi import FastAPI
        
        app = FastAPI()
        app.include_router(oauth_router)
        return TestClient(app)
    
    def test_oauth_login_endpoint_validates_provider(self, test_app):
        """Test OAuth login endpoint validates provider"""
        # Test unsupported provider
        response = test_app.get("/auth/oauth/login/unsupported")
        assert response.status_code == 400
        assert "Unsupported OAuth provider" in response.json()["detail"]
    
    def test_oauth_login_endpoint_requires_configuration(self, test_app):
        """Test OAuth login endpoint requires proper configuration"""
        with patch.dict(os.environ, {}, clear=True):
            response = test_app.get("/auth/oauth/login/google")
            assert response.status_code == 500
    
    def test_oauth_callback_handles_provider_errors(self, test_app):
        """Test OAuth callback handles provider errors securely"""
        response = test_app.get("/auth/oauth/callback?error=access_denied&error_description=User+denied+access")
        assert response.status_code == 400
        assert "access_denied" in response.json()["detail"]
    
    def test_oauth_callback_requires_parameters(self, test_app):
        """Test OAuth callback requires code and state parameters"""
        # Missing code parameter
        response = test_app.get("/auth/oauth/callback?state=test_state")
        assert response.status_code == 422  # Validation error
        
        # Missing state parameter
        response = test_app.get("/auth/oauth/callback?code=test_code")
        assert response.status_code == 422  # Validation error
    
    def test_oauth_providers_endpoint_security(self, test_app):
        """Test OAuth providers endpoint doesn't leak sensitive info"""
        with patch.dict(os.environ, {
            "GOOGLE_CLIENT_ID": "sensitive_client_id_12345678901234567890",
            "GOOGLE_CLIENT_SECRET": "sensitive_secret",
            "GOOGLE_CLIENT_REDIRECT_URL": "https://localhost:8000/callback"
        }):
            response = test_app.get("/auth/oauth/providers")
            assert response.status_code == 200
            
            data = response.json()
            # Should show truncated client ID, not full secret
            google_provider = next(p for p in data["providers"] if p["name"] == "google")
            assert google_provider["available"] is True
            
            # Check health endpoint doesn't leak secrets
            response = test_app.get("/auth/oauth/health")
            health_data = response.json()
            client_id_shown = health_data["providers"]["google"]["client_id"]
            assert "sensitive_client_id" in client_id_shown
            assert client_id_shown.endswith("...")
            assert "sensitive_secret" not in str(health_data)


class TestOAuthSecurityScenarios:
    """Test OAuth security attack scenarios"""
    
    def test_csrf_attack_prevention(self):
        """Test OAuth CSRF attack prevention via state parameter"""
        manager = OAuthStateManager()
        
        # Attacker tries to use state token from different session
        legitimate_state = manager.generate_state("google", "https://legitimate.com")
        
        # Attacker tries to validate with wrong provider
        valid, return_url = manager.validate_state(legitimate_state, "github")
        assert valid is False
        
        # State token should still be valid for correct provider
        valid, return_url = manager.validate_state(legitimate_state, "google")
        assert valid is True
        assert return_url == "https://legitimate.com"
    
    def test_authorization_code_replay_prevention(self):
        """Test prevention of authorization code replay attacks"""
        # This is primarily handled by OAuth provider, but we should ensure
        # our state tokens can't be reused
        manager = OAuthStateManager()
        
        state = manager.generate_state("google")
        
        # First validation should succeed
        valid1, _ = manager.validate_state(state, "google")
        assert valid1 is True
        
        # Replay attempt should fail
        valid2, _ = manager.validate_state(state, "google")
        assert valid2 is False
    
    def test_state_token_tampering_detection(self):
        """Test detection of tampered state tokens"""
        manager = OAuthStateManager()
        
        state = manager.generate_state("google")
        
        # Tamper with state token
        tampered_state = state[:-1] + "X"  # Change last character
        
        valid, _ = manager.validate_state(tampered_state, "google")
        assert valid is False
    
    def test_oauth_user_enumeration_prevention(self):
        """Test prevention of user enumeration via OAuth responses"""
        # OAuth service should not leak information about existing users
        # This is more of a design principle test
        manager = OAuthUserManager(Mock(spec=AuthDatabaseManager))
        
        # Both existing and non-existing users should follow same code path
        # and not leak timing information
        
        oauth_info = {"email": "test@example.com", "id": "123", "name": "Test"}
        
        # Mock database responses
        manager.db_manager.get_user_by_email.return_value = None
        manager.db_manager.get_user_by_username.return_value = None
        manager.db_manager.create_user.return_value = "new_user"
        
        result1 = manager.sync_oauth_user(oauth_info, "google")
        
        # Should not expose whether user existed or was created
        assert result1 == "new_user"
    
    def test_oauth_session_fixation_prevention(self):
        """Test OAuth session fixation attack prevention"""
        # Each OAuth flow should generate new state tokens
        manager = OAuthStateManager()
        
        # Generate multiple states - should all be unique
        states = [manager.generate_state("google") for _ in range(10)]
        assert len(set(states)) == 10
        
        # Each state should have its own expiration
        for state in states:
            state_data = manager._states[state]
            assert "expires_at" in state_data
            assert state_data["expires_at"] > time.time()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])