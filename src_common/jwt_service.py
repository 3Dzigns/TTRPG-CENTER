# jwt_service.py
"""
FR-SEC-401: JWT Service Implementation
Secure JWT token generation, validation, and management
"""

import os
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, Optional, List
import jwt
from jwt.exceptions import InvalidTokenError, ExpiredSignatureError
from passlib.context import CryptContext
from passlib.hash import argon2
import logging

from .auth_models import UserRole, TokenClaims, UserContext
from .logging import get_logger

logger = get_logger(__name__)

# Password hashing context - try Argon2 first, fallback to bcrypt
try:
    # Test if Argon2 is available
    from passlib.hash import argon2
    argon2.hash("test")
    
    pwd_context = CryptContext(
        schemes=["argon2", "bcrypt"],
        deprecated="auto",
        argon2__memory_cost=65536,  # 64MB
        argon2__time_cost=3,        # 3 iterations
        argon2__parallelism=1       # Single thread
    )
    logger.info("Using Argon2 for password hashing")
    
except (ImportError, Exception):
    # Fallback to bcrypt if Argon2 is not available
    pwd_context = CryptContext(
        schemes=["bcrypt"],
        deprecated="auto",
        bcrypt__rounds=12  # Good security for bcrypt
    )
    logger.warning("Argon2 not available, using bcrypt for password hashing")

# Authentication configuration
AUTH_CONFIG = {
    "jwt": {
        "algorithm": "HS256",  # Use RS256 for production with key rotation
        "access_token_expire_minutes": 60,
        "refresh_token_expire_days": 30,
        "issuer": "ttrpg-center",
        "audience": "ttrpg-center-api"
    },
    "password": {
        "min_length": 8,
        "require_uppercase": True,
        "require_lowercase": True,
        "require_numbers": True,
        "require_special": True
    },
    "rate_limiting": {
        "login_attempts": 5,
        "lockout_duration_minutes": 15,
        "window_minutes": 1
    }
}


class JWTService:
    """JWT token service with secure generation and validation"""
    
    def __init__(self, secret_key: Optional[str] = None, algorithm: str = "HS256"):
        """
        Initialize JWT service
        
        Args:
            secret_key: JWT signing secret (from environment if not provided)
            algorithm: JWT algorithm (HS256 or RS256)
        """
        self.algorithm = algorithm
        self.secret_key = secret_key or self._get_secret_key()
        self.issuer = AUTH_CONFIG["jwt"]["issuer"]
        self.audience = AUTH_CONFIG["jwt"]["audience"]
        self.access_token_expire_minutes = AUTH_CONFIG["jwt"]["access_token_expire_minutes"]
        self.refresh_token_expire_days = AUTH_CONFIG["jwt"]["refresh_token_expire_days"]
        
        # Token blacklist (in production, use Redis or database)
        self._token_blacklist: set = set()
        
        logger.info(f"JWT service initialized with algorithm: {algorithm}")
    
    def _get_secret_key(self) -> str:
        """Get JWT secret key from environment or generate new one"""
        secret = os.getenv("JWT_SECRET_KEY")
        if not secret:
            if os.getenv("ENVIRONMENT", "dev") == "dev":
                # Generate a development secret
                secret = secrets.token_urlsafe(32)
                logger.warning("Using generated JWT secret - not suitable for production")
            else:
                raise ValueError("JWT_SECRET_KEY environment variable required for production")
        return secret
    
    def create_access_token(self, user_id: str, username: str, role: UserRole, 
                          permissions: List[str] = None) -> str:
        """
        Create JWT access token
        
        Args:
            user_id: User ID
            username: Username
            role: User role
            permissions: List of permissions
            
        Returns:
            JWT access token
        """
        now = datetime.now(timezone.utc)
        expire = now + timedelta(minutes=self.access_token_expire_minutes)
        
        claims = {
            "sub": user_id,
            "username": username,
            "role": role.value,
            "permissions": permissions or [],
            "iss": self.issuer,
            "aud": self.audience,
            "exp": int(expire.timestamp()),
            "iat": int(now.timestamp()),
            "jti": str(uuid.uuid4()),
            "token_type": "access"
        }
        
        try:
            token = jwt.encode(claims, self.secret_key, algorithm=self.algorithm)
            logger.debug(f"Created access token for user {username} (role: {role})")
            return token
            
        except Exception as e:
            logger.error(f"Failed to create access token: {e}")
            raise
    
    def create_refresh_token(self, user_id: str, username: str) -> str:
        """
        Create JWT refresh token
        
        Args:
            user_id: User ID
            username: Username
            
        Returns:
            JWT refresh token
        """
        now = datetime.now(timezone.utc)
        expire = now + timedelta(days=self.refresh_token_expire_days)
        
        claims = {
            "sub": user_id,
            "username": username,
            "iss": self.issuer,
            "aud": self.audience,
            "exp": int(expire.timestamp()),
            "iat": int(now.timestamp()),
            "jti": str(uuid.uuid4()),
            "token_type": "refresh"
        }
        
        try:
            token = jwt.encode(claims, self.secret_key, algorithm=self.algorithm)
            logger.debug(f"Created refresh token for user {username}")
            return token
            
        except Exception as e:
            logger.error(f"Failed to create refresh token: {e}")
            raise
    
    def verify_token(self, token: str, token_type: str = "access") -> TokenClaims:
        """
        Verify and decode JWT token
        
        Args:
            token: JWT token string
            token_type: Expected token type (access/refresh)
            
        Returns:
            Token claims
            
        Raises:
            InvalidTokenError: If token is invalid
            ExpiredSignatureError: If token is expired
        """
        try:
            # Check if token is blacklisted
            payload = jwt.decode(token, options={"verify_signature": False})
            jti = payload.get("jti")
            
            if jti and jti in self._token_blacklist:
                logger.warning(f"Attempt to use blacklisted token: {jti}")
                raise InvalidTokenError("Token has been invalidated")
            
            # Verify token signature and claims
            payload = jwt.decode(
                token,
                self.secret_key,
                algorithms=[self.algorithm],
                audience=self.audience,
                issuer=self.issuer
            )
            
            # Verify token type
            if payload.get("token_type") != token_type:
                raise InvalidTokenError(f"Invalid token type. Expected {token_type}")
            
            # Convert to TokenClaims model
            claims = TokenClaims(
                sub=payload["sub"],
                username=payload["username"],
                role=UserRole(payload.get("role", "user")),
                permissions=payload.get("permissions", []),
                iss=payload["iss"],
                aud=payload["aud"],
                exp=payload["exp"],
                iat=payload["iat"],
                jti=payload["jti"],
                token_type=payload["token_type"]
            )
            
            logger.debug(f"Successfully verified {token_type} token for user {claims.username}")
            return claims
            
        except ExpiredSignatureError:
            logger.info(f"Token expired for {token_type} token")
            raise
        except InvalidTokenError as e:
            logger.warning(f"Invalid {token_type} token: {e}")
            raise
        except Exception as e:
            logger.error(f"Token verification error: {e}")
            raise InvalidTokenError("Token verification failed")
    
    def blacklist_token(self, jti: str) -> None:
        """
        Add token to blacklist
        
        Args:
            jti: JWT ID to blacklist
        """
        self._token_blacklist.add(jti)
        logger.info(f"Token blacklisted: {jti}")
    
    def get_user_context(self, token: str) -> UserContext:
        """
        Get user context from valid access token
        
        Args:
            token: JWT access token
            
        Returns:
            User context
        """
        claims = self.verify_token(token, "access")
        
        return UserContext(
            user_id=claims.sub,
            username=claims.username,
            role=claims.role,
            permissions=claims.permissions,
            is_active=True  # Would be checked against database in production
        )


class PasswordService:
    """Secure password hashing and verification service"""
    
    @staticmethod
    def hash_password(password: str) -> str:
        """
        Hash password using Argon2
        
        Args:
            password: Plain text password
            
        Returns:
            Hashed password
        """
        try:
            hashed = pwd_context.hash(password)
            logger.debug("Password hashed successfully")
            return hashed
        except Exception as e:
            logger.error(f"Password hashing failed: {e}")
            raise
    
    @staticmethod
    def verify_password(password: str, hashed_password: str) -> bool:
        """
        Verify password against hash
        
        Args:
            password: Plain text password
            hashed_password: Hashed password
            
        Returns:
            True if password matches
        """
        try:
            is_valid = pwd_context.verify(password, hashed_password)
            logger.debug(f"Password verification: {'success' if is_valid else 'failed'}")
            return is_valid
        except Exception as e:
            logger.error(f"Password verification error: {e}")
            return False
    
    @staticmethod
    def is_password_strong(password: str) -> bool:
        """
        Check if password meets strength requirements
        
        Args:
            password: Password to check
            
        Returns:
            True if password is strong enough
        """
        config = AUTH_CONFIG["password"]
        
        if len(password) < config["min_length"]:
            return False
        
        if config["require_uppercase"] and not any(c.isupper() for c in password):
            return False
            
        if config["require_lowercase"] and not any(c.islower() for c in password):
            return False
            
        if config["require_numbers"] and not any(c.isdigit() for c in password):
            return False
            
        if config["require_special"] and not any(c in "!@#$%^&*()_+-=[]{}|;:,.<>?" for c in password):
            return False
        
        return True


class AuthenticationService:
    """Main authentication service coordinating JWT and password services"""
    
    def __init__(self):
        """Initialize authentication service"""
        self.jwt_service = JWTService()
        self.password_service = PasswordService()
        
        # Rate limiting storage (in production, use Redis)
        self._failed_attempts: Dict[str, List[datetime]] = {}
        self._locked_users: Dict[str, datetime] = {}
        
        logger.info("Authentication service initialized")
    
    def is_user_locked(self, identifier: str) -> bool:
        """
        Check if user is locked due to failed attempts
        
        Args:
            identifier: Username or IP address
            
        Returns:
            True if user is locked
        """
        if identifier in self._locked_users:
            lock_expires = self._locked_users[identifier]
            if datetime.now(timezone.utc) < lock_expires:
                return True
            else:
                # Lock expired, remove it
                del self._locked_users[identifier]
        
        return False
    
    def record_failed_attempt(self, identifier: str) -> None:
        """
        Record failed authentication attempt
        
        Args:
            identifier: Username or IP address
        """
        now = datetime.now(timezone.utc)
        window_start = now - timedelta(minutes=AUTH_CONFIG["rate_limiting"]["window_minutes"])
        
        # Clean old attempts
        if identifier in self._failed_attempts:
            self._failed_attempts[identifier] = [
                attempt for attempt in self._failed_attempts[identifier] 
                if attempt > window_start
            ]
        else:
            self._failed_attempts[identifier] = []
        
        # Add current attempt
        self._failed_attempts[identifier].append(now)
        
        # Check if should be locked
        max_attempts = AUTH_CONFIG["rate_limiting"]["login_attempts"]
        if len(self._failed_attempts[identifier]) >= max_attempts:
            lockout_duration = timedelta(minutes=AUTH_CONFIG["rate_limiting"]["lockout_duration_minutes"])
            self._locked_users[identifier] = now + lockout_duration
            
            logger.warning(f"User locked due to failed attempts: {identifier}")
    
    def clear_failed_attempts(self, identifier: str) -> None:
        """
        Clear failed attempts for successful login
        
        Args:
            identifier: Username or IP address
        """
        if identifier in self._failed_attempts:
            del self._failed_attempts[identifier]
        
        if identifier in self._locked_users:
            del self._locked_users[identifier]
    
    def create_tokens(self, user_id: str, username: str, role: UserRole, 
                     permissions: List[str] = None) -> Dict[str, Any]:
        """
        Create access and refresh tokens for user
        
        Args:
            user_id: User ID
            username: Username
            role: User role
            permissions: User permissions
            
        Returns:
            Token information
        """
        access_token = self.jwt_service.create_access_token(
            user_id, username, role, permissions
        )
        refresh_token = self.jwt_service.create_refresh_token(user_id, username)
        
        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
            "expires_in": self.jwt_service.access_token_expire_minutes * 60,
            "user_id": user_id,
            "username": username,
            "role": role.value
        }
    
    def refresh_access_token(self, refresh_token: str) -> Dict[str, Any]:
        """
        Create new access token from refresh token
        
        Args:
            refresh_token: Valid refresh token
            
        Returns:
            New access token information
        """
        # Verify refresh token
        claims = self.jwt_service.verify_token(refresh_token, "refresh")
        
        # Create new access token (would get permissions from database)
        access_token = self.jwt_service.create_access_token(
            claims.sub, claims.username, UserRole.USER  # Default role
        )
        
        return {
            "access_token": access_token,
            "token_type": "bearer",
            "expires_in": self.jwt_service.access_token_expire_minutes * 60
        }
    
    def logout_user(self, access_token: Optional[str] = None, 
                   refresh_token: Optional[str] = None) -> None:
        """
        Logout user by blacklisting tokens
        
        Args:
            access_token: Access token to blacklist
            refresh_token: Refresh token to blacklist
        """
        if access_token:
            try:
                claims = self.jwt_service.verify_token(access_token, "access")
                self.jwt_service.blacklist_token(claims.jti)
            except Exception as e:
                logger.warning(f"Could not blacklist access token: {e}")
        
        if refresh_token:
            try:
                claims = self.jwt_service.verify_token(refresh_token, "refresh")
                self.jwt_service.blacklist_token(claims.jti)
            except Exception as e:
                logger.warning(f"Could not blacklist refresh token: {e}")


# Global authentication service instance
auth_service = AuthenticationService()