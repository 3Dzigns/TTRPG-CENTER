# test_fr_sec_401_jwt_auth.py
"""
FR-SEC-401: JWT Authentication Implementation Tests
Comprehensive tests for JWT authentication system
"""

import pytest
import os
import uuid
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock
from fastapi import FastAPI, HTTPException, status
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import tempfile

from src_common.auth_models import AuthUser, UserRole, Base, LoginRequest, UserRegistrationRequest
from src_common.jwt_service import JWTService, PasswordService, AuthenticationService
from src_common.auth_database import AuthDatabaseManager
from src_common.auth_endpoints import auth_router
from src_common.auth_middleware import require_auth, require_admin, get_current_user


class TestJWTService:
    """Test JWT token service functionality"""
    
    @pytest.fixture
    def jwt_service(self):
        """Create JWT service for testing"""
        return JWTService(secret_key="test-secret-key-for-testing", algorithm="HS256")
    
    def test_create_access_token(self, jwt_service):
        """Test access token creation"""
        user_id = str(uuid.uuid4())
        username = "testuser"
        role = UserRole.USER
        permissions = ["user:read", "user:write"]
        
        token = jwt_service.create_access_token(user_id, username, role, permissions)
        
        assert isinstance(token, str)
        assert len(token) > 50  # JWT tokens are typically long
        
        # Verify token contents
        claims = jwt_service.verify_token(token, "access")
        assert claims.sub == user_id
        assert claims.username == username
        assert claims.role == role
        assert claims.permissions == permissions
        assert claims.token_type == "access"
    
    def test_create_refresh_token(self, jwt_service):
        """Test refresh token creation"""
        user_id = str(uuid.uuid4())
        username = "testuser"
        
        token = jwt_service.create_refresh_token(user_id, username)
        
        assert isinstance(token, str)
        
        # Verify token contents
        claims = jwt_service.verify_token(token, "refresh")
        assert claims.sub == user_id
        assert claims.username == username
        assert claims.token_type == "refresh"
    
    def test_verify_valid_token(self, jwt_service):
        """Test verification of valid tokens"""
        user_id = str(uuid.uuid4())
        username = "testuser"
        role = UserRole.ADMIN
        
        token = jwt_service.create_access_token(user_id, username, role)
        claims = jwt_service.verify_token(token, "access")
        
        assert claims.sub == user_id
        assert claims.username == username
        assert claims.role == role
        assert claims.token_type == "access"
    
    def test_verify_expired_token(self, jwt_service):
        """Test verification of expired tokens"""
        # Create JWT service with very short expiration
        short_jwt = JWTService(secret_key="test-secret", algorithm="HS256")
        short_jwt.access_token_expire_minutes = -1  # Already expired
        
        user_id = str(uuid.uuid4())
        token = short_jwt.create_access_token(user_id, "testuser", UserRole.USER)
        
        with pytest.raises(Exception):  # Should raise ExpiredSignatureError
            short_jwt.verify_token(token, "access")
    
    def test_verify_invalid_token(self, jwt_service):
        """Test verification of invalid tokens"""
        invalid_token = "invalid.jwt.token"
        
        with pytest.raises(Exception):  # Should raise InvalidTokenError
            jwt_service.verify_token(invalid_token, "access")
    
    def test_verify_wrong_token_type(self, jwt_service):
        """Test verification with wrong token type"""
        user_id = str(uuid.uuid4())
        access_token = jwt_service.create_access_token(user_id, "testuser", UserRole.USER)
        
        with pytest.raises(Exception):  # Should raise InvalidTokenError
            jwt_service.verify_token(access_token, "refresh")
    
    def test_blacklist_token(self, jwt_service):
        """Test token blacklisting"""
        user_id = str(uuid.uuid4())
        token = jwt_service.create_access_token(user_id, "testuser", UserRole.USER)
        claims = jwt_service.verify_token(token, "access")
        
        # Blacklist token
        jwt_service.blacklist_token(claims.jti)
        
        # Token should now be invalid
        with pytest.raises(Exception):
            jwt_service.verify_token(token, "access")
    
    def test_get_user_context(self, jwt_service):
        """Test user context extraction from token"""
        user_id = str(uuid.uuid4())
        username = "testuser"
        role = UserRole.ADMIN
        permissions = ["admin:read", "admin:write"]
        
        token = jwt_service.create_access_token(user_id, username, role, permissions)
        context = jwt_service.get_user_context(token)
        
        assert context.user_id == user_id
        assert context.username == username
        assert context.role == role
        assert context.permissions == permissions
        assert context.is_admin
        assert context.is_user


class TestPasswordService:
    """Test password hashing and verification"""
    
    def test_hash_password(self):
        """Test password hashing"""
        password = "TestPassword123!"
        hashed = PasswordService.hash_password(password)
        
        assert isinstance(hashed, str)
        assert len(hashed) > 50  # Hashed passwords are long
        assert hashed != password  # Should be different from original
    
    def test_verify_correct_password(self):
        """Test verification of correct password"""
        password = "TestPassword123!"
        hashed = PasswordService.hash_password(password)
        
        assert PasswordService.verify_password(password, hashed)
    
    def test_verify_incorrect_password(self):
        """Test verification of incorrect password"""
        password = "TestPassword123!"
        wrong_password = "WrongPassword456!"
        hashed = PasswordService.hash_password(password)
        
        assert not PasswordService.verify_password(wrong_password, hashed)
    
    def test_password_strength_validation(self):
        """Test password strength validation"""
        # Strong password
        assert PasswordService.is_password_strong("StrongPass123!")
        
        # Weak passwords
        assert not PasswordService.is_password_strong("short")  # Too short
        assert not PasswordService.is_password_strong("nouppercase123!")  # No uppercase
        assert not PasswordService.is_password_strong("NOLOWERCASE123!")  # No lowercase
        assert not PasswordService.is_password_strong("NoNumbers!")  # No numbers
        assert not PasswordService.is_password_strong("NoSpecialChars123")  # No special chars


class TestAuthDatabaseManager:
    """Test authentication database operations"""
    
    @pytest.fixture
    def temp_db(self):
        """Create temporary database for testing"""
        temp_file = tempfile.mktemp(suffix='.db')
        db_url = f"sqlite:///{temp_file}"
        
        db_manager = AuthDatabaseManager(db_url)
        db_manager.create_tables()
        
        yield db_manager
        
        # Cleanup
        if os.path.exists(temp_file):
            os.remove(temp_file)
    
    def test_create_user(self, temp_db):
        """Test user creation"""
        username = "testuser"
        email = "test@example.com"
        password = "TestPass123!"
        role = UserRole.USER
        
        user = temp_db.create_user(username, email, password, role)
        
        assert user.username == username.lower()
        assert user.email == email.lower()
        assert user.role == role
        assert user.is_active
        assert isinstance(user.id, uuid.UUID)
        
        # Verify password was hashed
        assert user.password_hash != password
        assert len(user.password_hash) > 50
    
    def test_create_duplicate_user(self, temp_db):
        """Test creating user with duplicate username/email"""
        username = "testuser"
        email = "test@example.com"
        password = "TestPass123!"
        
        # Create first user
        temp_db.create_user(username, email, password)
        
        # Attempt to create duplicate should fail
        with pytest.raises(ValueError, match="Username or email already exists"):
            temp_db.create_user(username, "different@example.com", password)
        
        with pytest.raises(ValueError, match="Username or email already exists"):
            temp_db.create_user("different_user", email, password)
    
    def test_get_user_by_username(self, temp_db):
        """Test retrieving user by username"""
        username = "testuser"
        email = "test@example.com"
        password = "TestPass123!"
        
        created_user = temp_db.create_user(username, email, password)
        retrieved_user = temp_db.get_user_by_username(username)
        
        assert retrieved_user is not None
        assert retrieved_user.id == created_user.id
        assert retrieved_user.username == username.lower()
    
    def test_get_nonexistent_user(self, temp_db):
        """Test retrieving nonexistent user"""
        user = temp_db.get_user_by_username("nonexistent")
        assert user is None
    
    def test_authenticate_user_success(self, temp_db):
        """Test successful user authentication"""
        username = "testuser"
        email = "test@example.com"
        password = "TestPass123!"
        
        temp_db.create_user(username, email, password)
        user = temp_db.authenticate_user(username, password)
        
        assert user is not None
        assert user.username == username.lower()
    
    def test_authenticate_user_wrong_password(self, temp_db):
        """Test authentication with wrong password"""
        username = "testuser"
        email = "test@example.com"
        password = "TestPass123!"
        
        temp_db.create_user(username, email, password)
        user = temp_db.authenticate_user(username, "WrongPassword")
        
        assert user is None
    
    def test_authenticate_nonexistent_user(self, temp_db):
        """Test authentication of nonexistent user"""
        user = temp_db.authenticate_user("nonexistent", "password")
        assert user is None
    
    def test_failed_attempts_lockout(self, temp_db):
        """Test user lockout after failed attempts"""
        username = "testuser"
        email = "test@example.com"
        password = "TestPass123!"
        
        user = temp_db.create_user(username, email, password)
        
        # Simulate 5 failed attempts
        for _ in range(5):
            temp_db.increment_failed_attempts(user.id)
        
        # User should now be locked
        refreshed_user = temp_db.get_user_by_id(str(user.id))
        assert refreshed_user.failed_attempts == 5
        assert refreshed_user.locked_until is not None
        assert refreshed_user.locked_until > datetime.now(timezone.utc)
        
        # Authentication should fail even with correct password
        locked_user = temp_db.authenticate_user(username, password)
        assert locked_user is None
    
    def test_change_password(self, temp_db):
        """Test password change functionality"""
        username = "testuser"
        email = "test@example.com"
        old_password = "OldPass123!"
        new_password = "NewPass456!"
        
        user = temp_db.create_user(username, email, old_password)
        old_hash = user.password_hash
        
        # Change password
        success = temp_db.change_password(str(user.id), old_password, new_password)
        assert success
        
        # Verify password changed
        updated_user = temp_db.get_user_by_id(str(user.id))
        assert updated_user.password_hash != old_hash
        
        # Verify new password works
        auth_user = temp_db.authenticate_user(username, new_password)
        assert auth_user is not None
        
        # Verify old password doesn't work
        old_auth = temp_db.authenticate_user(username, old_password)
        assert old_auth is None
    
    def test_create_default_admin(self, temp_db):
        """Test default admin user creation"""
        admin = temp_db.create_default_admin()
        
        assert admin is not None
        assert admin.username == "admin"
        assert admin.role == UserRole.ADMIN
        assert admin.is_active
        
        # Should not create duplicate
        admin2 = temp_db.create_default_admin()
        assert admin2.id == admin.id
    
    def test_get_user_stats(self, temp_db):
        """Test user statistics"""
        # Create test users
        temp_db.create_user("user1", "user1@test.com", "Pass123!", UserRole.USER)
        temp_db.create_user("admin1", "admin1@test.com", "Pass123!", UserRole.ADMIN)
        temp_db.create_default_admin()
        
        stats = temp_db.get_user_stats()
        
        assert stats["total_users"] == 3
        assert stats["active_users"] == 3
        assert stats["admin_users"] == 2  # admin1 + default admin
        assert stats["locked_users"] == 0


class TestAuthenticationEndpoints:
    """Test authentication API endpoints"""
    
    @pytest.fixture
    def test_app(self):
        """Create test FastAPI app with auth endpoints"""
        app = FastAPI()
        app.include_router(auth_router)
        return app
    
    @pytest.fixture
    def client(self, test_app):
        """Create test client"""
        return TestClient(test_app)
    
    @pytest.fixture
    def temp_db_for_endpoints(self):
        """Create temporary database and patch global auth_db"""
        temp_file = tempfile.mktemp(suffix='.db')
        db_url = f"sqlite:///{temp_file}"
        
        temp_db_manager = AuthDatabaseManager(db_url)
        temp_db_manager.create_tables()
        temp_db_manager.create_default_admin()
        
        with patch('src_common.auth_endpoints.auth_db', temp_db_manager):
            yield temp_db_manager
        
        # Cleanup
        if os.path.exists(temp_file):
            os.remove(temp_file)
    
    def test_login_success(self, client, temp_db_for_endpoints):
        """Test successful login"""
        # Use default admin credentials
        login_data = {
            "username": "admin",
            "password": "Admin123!"
        }
        
        response = client.post("/auth/login", json=login_data)
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"
        assert data["user_id"] is not None
        assert data["username"] == "admin"
        assert data["role"] == "admin"
    
    def test_login_invalid_credentials(self, client, temp_db_for_endpoints):
        """Test login with invalid credentials"""
        login_data = {
            "username": "admin",
            "password": "wrong_password"
        }
        
        response = client.post("/auth/login", json=login_data)
        
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert "Invalid username or password" in response.json()["detail"]
    
    def test_login_nonexistent_user(self, client, temp_db_for_endpoints):
        """Test login with nonexistent user"""
        login_data = {
            "username": "nonexistent",
            "password": "password"
        }
        
        response = client.post("/auth/login", json=login_data)
        
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
    
    def test_register_user(self, client, temp_db_for_endpoints):
        """Test user registration"""
        register_data = {
            "username": "newuser",
            "email": "newuser@example.com",
            "password": "NewPass123!",
            "role": "user"
        }
        
        response = client.post("/auth/register", json=register_data)
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        assert data["username"] == "newuser"
        assert data["email"] == "newuser@example.com"
        assert data["role"] == "user"
        assert data["is_active"]
    
    def test_register_duplicate_user(self, client, temp_db_for_endpoints):
        """Test registration with duplicate username"""
        register_data = {
            "username": "admin",  # Already exists
            "email": "admin2@example.com",
            "password": "NewPass123!"
        }
        
        response = client.post("/auth/register", json=register_data)
        
        assert response.status_code == status.HTTP_409_CONFLICT
        assert "Username already exists" in response.json()["detail"]
    
    def test_get_current_user_profile(self, client, temp_db_for_endpoints):
        """Test getting current user profile"""
        # Login first to get token
        login_response = client.post("/auth/login", json={
            "username": "admin",
            "password": "Admin123!"
        })
        token = login_response.json()["access_token"]
        
        # Get profile
        headers = {"Authorization": f"Bearer {token}"}
        response = client.get("/auth/me", headers=headers)
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        assert data["username"] == "admin"
        assert data["role"] == "admin"
        assert data["is_active"]
    
    def test_get_profile_without_token(self, client):
        """Test getting profile without authentication"""
        response = client.get("/auth/me")
        
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
    
    def test_logout(self, client, temp_db_for_endpoints):
        """Test user logout"""
        # Login first
        login_response = client.post("/auth/login", json={
            "username": "admin",
            "password": "Admin123!"
        })
        token = login_response.json()["access_token"]
        
        # Logout
        headers = {"Authorization": f"Bearer {token}"}
        response = client.post("/auth/logout", headers=headers)
        
        assert response.status_code == status.HTTP_200_OK
        assert "Logged out" in response.json()["message"]
    
    def test_auth_status_authenticated(self, client, temp_db_for_endpoints):
        """Test authentication status with valid token"""
        # Login first
        login_response = client.post("/auth/login", json={
            "username": "admin",
            "password": "Admin123!"
        })
        token = login_response.json()["access_token"]
        
        # Check status
        headers = {"Authorization": f"Bearer {token}"}
        response = client.get("/auth/status", headers=headers)
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        assert data["authenticated"] is True
        assert data["user"]["username"] == "admin"
        assert data["user"]["role"] == "admin"
    
    def test_auth_status_unauthenticated(self, client):
        """Test authentication status without token"""
        response = client.get("/auth/status")
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        
        assert data["authenticated"] is False
        assert data["user"] is None


class TestAuthorizationMiddleware:
    """Test authorization middleware and dependencies"""
    
    @pytest.fixture
    def test_app_with_auth(self):
        """Create test app with protected endpoints"""
        app = FastAPI()
        
        @app.get("/public")
        async def public_endpoint():
            return {"message": "public"}
        
        @app.get("/protected")
        async def protected_endpoint(current_user = Depends(require_auth)):
            return {"message": f"protected for {current_user.username}"}
        
        @app.get("/admin")
        async def admin_endpoint(current_user = Depends(require_admin)):
            return {"message": f"admin for {current_user.username}"}
        
        @app.get("/optional")
        async def optional_auth(current_user = Depends(get_current_user)):
            if current_user:
                return {"message": f"authenticated as {current_user.username}"}
            else:
                return {"message": "anonymous"}
        
        return app
    
    @pytest.fixture
    def auth_client(self, test_app_with_auth):
        """Create test client"""
        return TestClient(test_app_with_auth)
    
    def test_public_endpoint_access(self, auth_client):
        """Test access to public endpoint"""
        response = auth_client.get("/public")
        assert response.status_code == 200
        assert response.json()["message"] == "public"
    
    def test_protected_endpoint_without_token(self, auth_client):
        """Test protected endpoint without authentication"""
        response = auth_client.get("/protected")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
    
    @patch('src_common.auth_middleware.auth_service')
    @patch('src_common.auth_middleware.auth_db')
    def test_protected_endpoint_with_valid_token(self, mock_db, mock_auth, auth_client):
        """Test protected endpoint with valid token"""
        # Mock valid token and user
        mock_user_context = MagicMock()
        mock_user_context.user_id = "user123"
        mock_user_context.username = "testuser"
        mock_user_context.role = UserRole.USER
        mock_user_context.is_admin = False
        
        mock_user = MagicMock()
        mock_user.is_active = True
        
        mock_auth.jwt_service.get_user_context.return_value = mock_user_context
        mock_db.get_user_by_id.return_value = mock_user
        
        headers = {"Authorization": "Bearer valid_token"}
        response = auth_client.get("/protected", headers=headers)
        
        assert response.status_code == 200
        assert "testuser" in response.json()["message"]
    
    @patch('src_common.auth_middleware.auth_service')
    def test_protected_endpoint_with_invalid_token(self, mock_auth, auth_client):
        """Test protected endpoint with invalid token"""
        mock_auth.jwt_service.get_user_context.side_effect = Exception("Invalid token")
        
        headers = {"Authorization": "Bearer invalid_token"}
        response = auth_client.get("/protected", headers=headers)
        
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
    
    @patch('src_common.auth_middleware.auth_service')
    @patch('src_common.auth_middleware.auth_db')
    def test_admin_endpoint_with_admin_token(self, mock_db, mock_auth, auth_client):
        """Test admin endpoint with admin token"""
        # Mock admin user context
        mock_user_context = MagicMock()
        mock_user_context.user_id = "admin123"
        mock_user_context.username = "admin"
        mock_user_context.role = UserRole.ADMIN
        mock_user_context.is_admin = True
        
        mock_user = MagicMock()
        mock_user.is_active = True
        
        mock_auth.jwt_service.get_user_context.return_value = mock_user_context
        mock_db.get_user_by_id.return_value = mock_user
        
        headers = {"Authorization": "Bearer admin_token"}
        response = auth_client.get("/admin", headers=headers)
        
        assert response.status_code == 200
        assert "admin" in response.json()["message"]
    
    @patch('src_common.auth_middleware.auth_service')
    @patch('src_common.auth_middleware.auth_db')
    def test_admin_endpoint_with_user_token(self, mock_db, mock_auth, auth_client):
        """Test admin endpoint with regular user token"""
        # Mock regular user context
        mock_user_context = MagicMock()
        mock_user_context.user_id = "user123"
        mock_user_context.username = "testuser"
        mock_user_context.role = UserRole.USER
        mock_user_context.is_admin = False
        
        mock_user = MagicMock()
        mock_user.is_active = True
        
        mock_auth.jwt_service.get_user_context.return_value = mock_user_context
        mock_db.get_user_by_id.return_value = mock_user
        
        headers = {"Authorization": "Bearer user_token"}
        response = auth_client.get("/admin", headers=headers)
        
        assert response.status_code == status.HTTP_403_FORBIDDEN
    
    def test_optional_auth_without_token(self, auth_client):
        """Test optional authentication without token"""
        response = auth_client.get("/optional")
        assert response.status_code == 200
        assert response.json()["message"] == "anonymous"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])