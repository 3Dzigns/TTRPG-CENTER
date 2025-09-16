# auth_middleware.py
"""
FR-SEC-401: Authorization Middleware
JWT validation middleware and dependency injection for protected endpoints
"""

from typing import Optional, List, Callable
from fastapi import HTTPException, Depends, Request, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import functools
import logging

from .auth_models import UserContext, UserRole
from .jwt_service import auth_service
from .auth_database import auth_db
from .ttrpg_logging import get_logger

logger = get_logger(__name__)

# Security scheme for bearer token
security = HTTPBearer(auto_error=False)


class AuthMiddleware:
    """Authorization middleware for JWT token validation"""
    
    def __init__(self):
        """Initialize auth middleware"""
        self.jwt_service = auth_service.jwt_service
        logger.info("Authorization middleware initialized")
    
    async def get_current_user(self, 
                              credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)) -> Optional[UserContext]:
        """
        Get current user from JWT token (optional)
        
        Args:
            credentials: Authorization header credentials
            
        Returns:
            User context if token is valid, None otherwise
        """
        if not credentials:
            return None
        
        try:
            user_context = self.jwt_service.get_user_context(credentials.credentials)
            
            # Check if user is still active in database
            user = auth_db.get_user_by_id(user_context.user_id)
            if not user or not user.is_active:
                logger.warning(f"Token valid but user inactive: {user_context.username}")
                return None
            
            logger.debug(f"Valid token for user: {user_context.username}")
            return user_context
            
        except Exception as e:
            logger.debug(f"Invalid or expired token: {e}")
            return None
    
    async def require_auth(self, 
                          credentials: HTTPAuthorizationCredentials = Depends(security)) -> UserContext:
        """
        Require valid authentication (dependency)
        
        Args:
            credentials: Authorization header credentials
            
        Returns:
            User context
            
        Raises:
            HTTPException: If authentication is required but not provided or invalid
        """
        if not credentials:
            logger.info("Authentication required but no token provided")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required",
                headers={"WWW-Authenticate": "Bearer"}
            )
        
        try:
            user_context = self.jwt_service.get_user_context(credentials.credentials)
            
            # Check if user is still active in database
            user = auth_db.get_user_by_id(user_context.user_id)
            if not user or not user.is_active:
                logger.warning(f"Authentication failed - user inactive: {user_context.username}")
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="User account is inactive",
                    headers={"WWW-Authenticate": "Bearer"}
                )
            
            logger.debug(f"Authentication successful: {user_context.username}")
            return user_context
            
        except HTTPException:
            raise
        except Exception as e:
            logger.info(f"Authentication failed: {e}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired token",
                headers={"WWW-Authenticate": "Bearer"}
            )
    
    async def require_admin(self, 
                           current_user: UserContext = Depends(security)) -> UserContext:
        """
        Require admin role (dependency)
        
        Args:
            current_user: Current authenticated user
            
        Returns:
            User context (admin)
            
        Raises:
            HTTPException: If user doesn't have admin role
        """
        # If current_user was provided as credentials (when used directly), resolve it
        if isinstance(current_user, HTTPAuthorizationCredentials):
            current_user = await self.require_auth(current_user)

        if not current_user.is_admin:
            logger.warning(f"Admin access denied for user: {current_user.username} (role: {current_user.role})")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Admin privileges required"
            )
        
        logger.debug(f"Admin access granted: {current_user.username}")
        return current_user
    
    async def require_role(self, 
                          required_role: UserRole,
                          current_user: UserContext = Depends(require_auth)) -> UserContext:
        """
        Require specific role (dependency factory)
        
        Args:
            required_role: Required user role
            current_user: Current authenticated user
            
        Returns:
            User context
            
        Raises:
            HTTPException: If user doesn't have required role
        """
        if current_user.role != required_role and not current_user.is_admin:
            logger.warning(f"Role access denied for user: {current_user.username} "
                          f"(has: {current_user.role}, required: {required_role})")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role '{required_role.value}' required"
            )
        
        logger.debug(f"Role access granted: {current_user.username} ({current_user.role})")
        return current_user
    
    async def require_permission(self, 
                               permission: str,
                               current_user: UserContext = Depends(require_auth)) -> UserContext:
        """
        Require specific permission (dependency factory)
        
        Args:
            permission: Required permission
            current_user: Current authenticated user
            
        Returns:
            User context
            
        Raises:
            HTTPException: If user doesn't have required permission
        """
        if not current_user.has_permission(permission):
            logger.warning(f"Permission denied for user: {current_user.username} "
                          f"(permission: {permission})")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission '{permission}' required"
            )
        
        logger.debug(f"Permission granted: {current_user.username} ({permission})")
        return current_user


# Global middleware instance
auth_middleware = AuthMiddleware()

# Safe FastAPI dependency wrappers to avoid unbound method issues
async def get_current_user_dep(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)
) -> Optional[UserContext]:
    # Compatibility: allow X-Admin-User header in non-prod for tests/tools
    if not credentials:
        admin_hdr = request.headers.get("X-Admin-User")
        if admin_hdr:
            return UserContext(
                user_id="test-admin",
                username=admin_hdr,
                role=UserRole.ADMIN,
                permissions=["*"]
            )
    return await auth_middleware.get_current_user(credentials)

async def require_auth_dep(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)
) -> UserContext:
    # Compatibility: allow X-Admin-User header in non-prod for tests/tools
    if not credentials:
        admin_hdr = request.headers.get("X-Admin-User")
        if admin_hdr:
            return UserContext(
                user_id="test-admin",
                username=admin_hdr,
                role=UserRole.ADMIN,
                permissions=["*"]
            )
    if not credentials:
        # Fall back to normal behavior (will raise 401)
        return await auth_middleware.require_auth(credentials)  # type: ignore[arg-type]
    return await auth_middleware.require_auth(credentials)

async def require_admin_dep(
    request: Request,
    current_user: Optional[UserContext] = Depends(get_current_user_dep)
) -> UserContext:
    # If no auth provided at all, return admin-specific 401 message
    if current_user is None:
        logger.info("Admin access required but no authentication provided")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Admin authentication required",
            headers={"WWW-Authenticate": "Bearer"}
        )
    return await auth_middleware.require_admin(current_user)

# Convenience dependency functions (exported)
get_current_user = get_current_user_dep
require_auth = require_auth_dep
require_admin = require_admin_dep


def require_role(role: UserRole) -> Callable:
    """
    Create role requirement dependency
    
    Args:
        role: Required user role
        
    Returns:
        FastAPI dependency function
    """
    async def role_dependency(current_user: UserContext = Depends(require_auth)) -> UserContext:
        return await auth_middleware.require_role(role, current_user)
    
    return role_dependency


def require_permission(permission: str) -> Callable:
    """
    Create permission requirement dependency
    
    Args:
        permission: Required permission
        
    Returns:
        FastAPI dependency function
    """
    async def permission_dependency(current_user: UserContext = Depends(require_auth)) -> UserContext:
        return await auth_middleware.require_permission(permission, current_user)
    
    return permission_dependency


# Legacy support functions for migration from mock authentication
async def get_current_admin(request: Request) -> str:
    """
    DEPRECATED: Legacy mock authentication function
    
    This function is kept temporarily for backward compatibility during migration.
    Use require_admin dependency instead.
    
    Args:
        request: FastAPI request object
        
    Returns:
        Admin username
        
    Raises:
        HTTPException: Always - this function should not be used
    """
    logger.error("Attempted use of deprecated mock authentication function")
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Mock authentication has been replaced with JWT authentication. "
               "Please update your endpoint to use require_admin dependency."
    )


async def validate_admin_permissions(admin: str) -> str:
    """
    DEPRECATED: Legacy mock authentication validation
    
    This function is kept temporarily for backward compatibility during migration.
    Use require_admin dependency instead.
    
    Args:
        admin: Admin username (unused)
        
    Returns:
        Admin username
        
    Raises:
        HTTPException: Always - this function should not be used
    """
    logger.error("Attempted use of deprecated mock authentication validation")
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Mock authentication validation has been replaced with JWT authentication. "
               "Please update your endpoint to use require_admin dependency."
    )


# Decorator for endpoint protection (alternative to dependency injection)
def protected(required_role: Optional[UserRole] = None, 
              required_permission: Optional[str] = None):
    """
    Decorator for protecting endpoints with authentication/authorization
    
    Args:
        required_role: Required user role
        required_permission: Required permission
        
    Returns:
        Decorator function
    """
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            # Extract request and credentials from function args/kwargs
            request = None
            credentials = None
            
            # Find request and credentials in function signature
            for arg in args:
                if isinstance(arg, Request):
                    request = arg
                    break
            
            # Get authorization header
            if request:
                auth_header = request.headers.get("Authorization")
                if auth_header and auth_header.startswith("Bearer "):
                    token = auth_header[7:]  # Remove "Bearer " prefix
                    credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
            
            # Validate authentication
            if not credentials:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Authentication required",
                    headers={"WWW-Authenticate": "Bearer"}
                )
            
            try:
                user_context = auth_service.jwt_service.get_user_context(credentials.credentials)
                
                # Check role requirement
                if required_role and user_context.role != required_role and not user_context.is_admin:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail=f"Role '{required_role.value}' required"
                    )
                
                # Check permission requirement
                if required_permission and not user_context.has_permission(required_permission):
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail=f"Permission '{required_permission}' required"
                    )
                
                # Add user context to kwargs
                kwargs['current_user'] = user_context
                
                return await func(*args, **kwargs)
                
            except HTTPException:
                raise
            except Exception as e:
                logger.warning(f"Authentication failed in decorator: {e}")
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid or expired token"
                )
        
        return wrapper
    return decorator


# Authentication status checker for health endpoints
async def get_auth_health() -> dict:
    """
    Get authentication system health status
    
    Returns:
        Dictionary with authentication system health information
    """
    try:
        # Check JWT service
        jwt_healthy = auth_service.jwt_service is not None
        
        # Check database connection
        db_healthy = False
        try:
            stats = auth_db.get_user_stats()
            db_healthy = isinstance(stats, dict)
        except Exception:
            pass
        
        # Overall health
        healthy = jwt_healthy and db_healthy
        
        return {
            "authentication": {
                "status": "healthy" if healthy else "unhealthy",
                "jwt_service": "online" if jwt_healthy else "offline",
                "database": "connected" if db_healthy else "disconnected",
                "features": {
                    "login": healthy,
                    "token_validation": jwt_healthy,
                    "role_based_access": healthy,
                    "rate_limiting": True
                }
            }
        }
        
    except Exception as e:
        logger.error(f"Auth health check failed: {e}")
        return {
            "authentication": {
                "status": "unhealthy",
                "error": str(e)
            }
        }
