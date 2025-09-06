# auth_endpoints.py
"""
FR-SEC-401: Authentication Endpoints
FastAPI endpoints for user authentication and token management
"""

from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, HTTPException, Depends, Request, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
# Rate limiting (optional - install slowapi for production)
try:
    from slowapi import Limiter, _rate_limit_exceeded_handler
    from slowapi.util import get_remote_address
    from slowapi.errors import RateLimitExceeded
    RATE_LIMITING_AVAILABLE = True
except ImportError:
    # Fallback for development/testing without slowapi
    RATE_LIMITING_AVAILABLE = False
    
    def get_remote_address(request):
        return getattr(request.client, 'host', 'unknown') if request.client else 'unknown'
    
    class RateLimitExceeded(Exception):
        def __init__(self, detail):
            self.detail = detail

from .auth_models import (
    LoginRequest, LoginResponse, TokenRefreshRequest, TokenRefreshResponse,
    LogoutRequest, UserRegistrationRequest, UserProfile, AuthStatus, 
    PasswordChangeRequest, UserRole
)
from .jwt_service import auth_service
from .auth_database import auth_db
from .logging import get_logger

logger = get_logger(__name__)

# Rate limiter setup (only if available)
if RATE_LIMITING_AVAILABLE:
    limiter = Limiter(key_func=get_remote_address)
else:
    # Mock limiter for development
    class MockLimiter:
        def limit(self, rate_limit):
            def decorator(func):
                return func
            return decorator
    limiter = MockLimiter()

# Security scheme for bearer token
security = HTTPBearer(auto_error=False)

# Create authentication router
auth_router = APIRouter(prefix="/auth", tags=["Authentication"])


@auth_router.post("/login", response_model=LoginResponse)
@limiter.limit("5/minute")  # Rate limit login attempts
async def login(request: Request, login_data: LoginRequest):
    """
    Authenticate user and return JWT tokens
    
    Args:
        request: FastAPI request object
        login_data: Login credentials
        
    Returns:
        JWT tokens and user information
    """
    client_ip = get_remote_address(request)
    
    try:
        # Check if user or IP is locked
        if auth_service.is_user_locked(login_data.username):
            logger.warning(f"Login attempt from locked user: {login_data.username} (IP: {client_ip})")
            raise HTTPException(
                status_code=status.HTTP_423_LOCKED,
                detail="Account temporarily locked due to failed login attempts"
            )
        
        if auth_service.is_user_locked(client_ip):
            logger.warning(f"Login attempt from locked IP: {client_ip}")
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many failed login attempts from this IP address"
            )
        
        # Authenticate user
        user = auth_db.authenticate_user(login_data.username, login_data.password)
        if not user:
            # Record failed attempt
            auth_service.record_failed_attempt(login_data.username)
            auth_service.record_failed_attempt(client_ip)
            
            logger.info(f"Failed login attempt: {login_data.username} (IP: {client_ip})")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid username or password"
            )
        
        # Clear failed attempts on successful login
        auth_service.clear_failed_attempts(login_data.username)
        auth_service.clear_failed_attempts(client_ip)
        
        # Get user permissions (would be from database in full implementation)
        permissions = []
        if user.role == UserRole.ADMIN:
            permissions = ["admin:read", "admin:write", "user:read", "user:write"]
        elif user.role == UserRole.USER:
            permissions = ["user:read", "user:write"]
        else:
            permissions = ["guest:read"]
        
        # Create tokens
        token_data = auth_service.create_tokens(
            str(user.id), user.username, user.role, permissions
        )
        
        logger.info(f"Successful login: {user.username} (role: {user.role.value})")
        
        return LoginResponse(**token_data)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Login error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Authentication service error"
        )


@auth_router.post("/refresh", response_model=TokenRefreshResponse)
@limiter.limit("10/minute")
async def refresh_token(request: Request, refresh_data: TokenRefreshRequest):
    """
    Refresh access token using refresh token
    
    Args:
        request: FastAPI request object
        refresh_data: Refresh token
        
    Returns:
        New access token
    """
    try:
        token_data = auth_service.refresh_access_token(refresh_data.refresh_token)
        
        logger.info("Token refreshed successfully")
        return TokenRefreshResponse(**token_data)
        
    except Exception as e:
        logger.warning(f"Token refresh failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token"
        )


@auth_router.post("/logout")
@limiter.limit("20/minute")
async def logout(request: Request, 
                logout_data: Optional[LogoutRequest] = None,
                credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)):
    """
    Logout user by blacklisting tokens
    
    Args:
        request: FastAPI request object
        logout_data: Optional logout request data
        credentials: Authorization header credentials
        
    Returns:
        Success message
    """
    try:
        access_token = credentials.credentials if credentials else None
        refresh_token = logout_data.refresh_token if logout_data else None
        
        # Blacklist tokens
        auth_service.logout_user(access_token, refresh_token)
        
        logger.info("User logged out successfully")
        return {"message": "Logged out successfully"}
        
    except Exception as e:
        logger.warning(f"Logout error: {e}")
        # Don't fail logout even if token blacklisting fails
        return {"message": "Logged out"}


@auth_router.post("/register", response_model=UserProfile)
@limiter.limit("3/minute")
async def register(request: Request, registration_data: UserRegistrationRequest):
    """
    Register new user account
    
    Args:
        request: FastAPI request object
        registration_data: User registration data
        
    Returns:
        User profile information
    """
    try:
        # Check if user already exists
        existing_user = auth_db.get_user_by_username(registration_data.username)
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Username already exists"
            )
        
        existing_email = auth_db.get_user_by_email(registration_data.email)
        if existing_email:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Email already registered"
            )
        
        # Create new user (non-admin by default)
        role = UserRole.USER if registration_data.role == UserRole.ADMIN else registration_data.role
        user = auth_db.create_user(
            registration_data.username,
            registration_data.email,
            registration_data.password,
            role
        )
        
        logger.info(f"New user registered: {user.username}")
        
        return UserProfile(
            user_id=str(user.id),
            username=user.username,
            email=user.email,
            role=user.role,
            is_active=user.is_active,
            created_at=user.created_at,
            last_login=user.last_login
        )
        
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Registration error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Registration service error"
        )


@auth_router.get("/me", response_model=UserProfile)
async def get_current_user_profile(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """
    Get current user profile
    
    Args:
        credentials: Authorization header credentials
        
    Returns:
        User profile information
    """
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required"
        )
    
    try:
        # Verify token and get user context
        user_context = auth_service.jwt_service.get_user_context(credentials.credentials)
        
        # Get user details from database
        user = auth_db.get_user_by_id(user_context.user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        return UserProfile(
            user_id=str(user.id),
            username=user.username,
            email=user.email,
            role=user.role,
            is_active=user.is_active,
            created_at=user.created_at,
            last_login=user.last_login
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.warning(f"Get profile error: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token"
        )


@auth_router.post("/change-password")
async def change_password(password_data: PasswordChangeRequest,
                         credentials: HTTPAuthorizationCredentials = Depends(security)):
    """
    Change user password
    
    Args:
        password_data: Password change request
        credentials: Authorization header credentials
        
    Returns:
        Success message
    """
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required"
        )
    
    try:
        # Verify token and get user context
        user_context = auth_service.jwt_service.get_user_context(credentials.credentials)
        
        # Change password
        success = auth_db.change_password(
            user_context.user_id,
            password_data.current_password,
            password_data.new_password
        )
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Current password is incorrect"
            )
        
        logger.info(f"Password changed for user: {user_context.username}")
        return {"message": "Password changed successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Password change error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Password change service error"
        )


@auth_router.get("/status", response_model=AuthStatus)
async def get_auth_status(credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)):
    """
    Get authentication status
    
    Args:
        credentials: Optional authorization header credentials
        
    Returns:
        Authentication status and user context if authenticated
    """
    if not credentials:
        return AuthStatus(
            authenticated=False,
            message="No authentication token provided"
        )
    
    try:
        # Verify token and get user context
        user_context = auth_service.jwt_service.get_user_context(credentials.credentials)
        
        return AuthStatus(
            authenticated=True,
            user=user_context,
            message="Successfully authenticated"
        )
        
    except Exception as e:
        logger.debug(f"Auth status check failed: {e}")
        return AuthStatus(
            authenticated=False,
            message="Invalid or expired token"
        )


# Admin-only endpoints
@auth_router.get("/admin/users")
async def list_users(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """
    List all users (admin only)
    
    Args:
        credentials: Authorization header credentials
        
    Returns:
        List of users
    """
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required"
        )
    
    try:
        # Verify admin token
        user_context = auth_service.jwt_service.get_user_context(credentials.credentials)
        
        if not user_context.is_admin:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Admin privileges required"
            )
        
        # Get user statistics
        stats = auth_db.get_user_stats()
        
        return {
            "message": "User list access granted",
            "stats": stats
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Admin users list error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Admin service error"
        )


@auth_router.post("/admin/cleanup")
async def cleanup_expired_tokens(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """
    Cleanup expired tokens from blacklist (admin only)
    
    Args:
        credentials: Authorization header credentials
        
    Returns:
        Cleanup results
    """
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required"
        )
    
    try:
        # Verify admin token
        user_context = auth_service.jwt_service.get_user_context(credentials.credentials)
        
        if not user_context.is_admin:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Admin privileges required"
            )
        
        # Cleanup expired tokens
        cleaned_count = auth_db.cleanup_expired_tokens()
        
        logger.info(f"Token cleanup completed by {user_context.username}: {cleaned_count} tokens removed")
        
        return {
            "message": "Token cleanup completed",
            "tokens_removed": cleaned_count
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Token cleanup error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Cleanup service error"
        )


# Rate limit error handler (only if available)
if RATE_LIMITING_AVAILABLE:
    @auth_router.exception_handler(RateLimitExceeded)
    async def rate_limit_handler(request: Request, exc: RateLimitExceeded):
        """Handle rate limit exceeded errors"""
        logger.warning(f"Rate limit exceeded for {get_remote_address(request)}: {exc.detail}")
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Rate limit exceeded: {exc.detail}"
        )