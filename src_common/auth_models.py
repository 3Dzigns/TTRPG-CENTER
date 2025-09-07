# auth_models.py
"""
FR-SEC-401: JWT Authentication Models
Database models and Pydantic schemas for authentication system
"""

import uuid
from datetime import datetime, timezone
from typing import List, Optional
from enum import Enum

from pydantic import BaseModel, Field, EmailStr, validator
from sqlalchemy import Column, String, DateTime, Boolean, Integer, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func

Base = declarative_base()


class UserRole(str, Enum):
    """User role enumeration"""
    ADMIN = "admin"
    USER = "user"
    GUEST = "guest"


class AuthUser(Base):
    """User authentication table"""
    __tablename__ = "auth_users"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    username = Column(String(50), unique=True, nullable=False, index=True)
    email = Column(String(100), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=True)  # Nullable for OAuth users
    role = Column(SQLEnum(UserRole), default=UserRole.USER, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    last_login = Column(DateTime(timezone=True), nullable=True)
    failed_attempts = Column(Integer, default=0, nullable=False)
    locked_until = Column(DateTime(timezone=True), nullable=True)
    
    # OAuth fields
    full_name = Column(String(100), nullable=True)
    is_oauth_user = Column(Boolean, default=False, nullable=False)
    oauth_provider = Column(String(50), nullable=True, index=True)  # 'google', 'github', etc.
    oauth_id = Column(String(100), nullable=True, index=True)  # OAuth provider's user ID
    
    def __repr__(self):
        return f"<AuthUser(id={self.id}, username={self.username}, role={self.role})>"


class AuthTokenBlacklist(Base):
    """Token blacklist for logout functionality"""
    __tablename__ = "auth_token_blacklist"
    
    jti = Column(String(255), primary_key=True)  # JWT ID
    user_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    
    def __repr__(self):
        return f"<AuthTokenBlacklist(jti={self.jti}, user_id={self.user_id})>"


# Pydantic Models for API

class LoginRequest(BaseModel):
    """Login request model"""
    username: str = Field(min_length=3, max_length=50, description="Username")
    password: str = Field(min_length=8, description="Password")
    
    @validator('username')
    def username_alphanumeric(cls, v):
        if not v.replace('_', '').replace('-', '').isalnum():
            raise ValueError('Username must contain only alphanumeric characters, hyphens, and underscores')
        return v.lower()


class LoginResponse(BaseModel):
    """Login response model"""
    access_token: str = Field(description="JWT access token")
    refresh_token: str = Field(description="JWT refresh token")
    token_type: str = Field(default="bearer", description="Token type")
    expires_in: int = Field(description="Token expiration time in seconds")
    user_id: str = Field(description="User ID")
    username: str = Field(description="Username")
    role: UserRole = Field(description="User role")


class TokenRefreshRequest(BaseModel):
    """Token refresh request model"""
    refresh_token: str = Field(description="Refresh token")


class TokenRefreshResponse(BaseModel):
    """Token refresh response model"""
    access_token: str = Field(description="New JWT access token")
    token_type: str = Field(default="bearer", description="Token type")
    expires_in: int = Field(description="Token expiration time in seconds")


class LogoutRequest(BaseModel):
    """Logout request model"""
    refresh_token: Optional[str] = Field(default=None, description="Optional refresh token to blacklist")


class UserRegistrationRequest(BaseModel):
    """User registration request model"""
    username: str = Field(min_length=3, max_length=50, description="Username")
    email: EmailStr = Field(description="Email address")
    password: str = Field(min_length=8, description="Password")
    role: Optional[UserRole] = Field(default=UserRole.USER, description="User role")
    
    @validator('username')
    def username_alphanumeric(cls, v):
        if not v.replace('_', '').replace('-', '').isalnum():
            raise ValueError('Username must contain only alphanumeric characters, hyphens, and underscores')
        return v.lower()
    
    @validator('password')
    def validate_password_strength(cls, v):
        """Validate password meets security requirements"""
        if len(v) < 8:
            raise ValueError('Password must be at least 8 characters long')
        
        has_upper = any(c.isupper() for c in v)
        has_lower = any(c.islower() for c in v)
        has_digit = any(c.isdigit() for c in v)
        has_special = any(c in "!@#$%^&*()_+-=[]{}|;:,.<>?" for c in v)
        
        if not has_upper:
            raise ValueError('Password must contain at least one uppercase letter')
        if not has_lower:
            raise ValueError('Password must contain at least one lowercase letter')
        if not has_digit:
            raise ValueError('Password must contain at least one number')
        if not has_special:
            raise ValueError('Password must contain at least one special character')
        
        return v


class UserContext(BaseModel):
    """User context for authenticated requests"""
    user_id: str = Field(description="User ID")
    username: str = Field(description="Username")
    role: UserRole = Field(description="User role")
    permissions: List[str] = Field(default_factory=list, description="User permissions")
    is_active: bool = Field(default=True, description="User active status")
    
    @property
    def is_admin(self) -> bool:
        """Check if user has admin role"""
        return self.role == UserRole.ADMIN
    
    @property
    def is_user(self) -> bool:
        """Check if user has user role or higher"""
        return self.role in [UserRole.USER, UserRole.ADMIN]
    
    def has_permission(self, permission: str) -> bool:
        """Check if user has specific permission"""
        return permission in self.permissions or self.is_admin


class TokenClaims(BaseModel):
    """JWT token claims structure"""
    sub: str = Field(description="Subject (user ID)")
    username: str = Field(description="Username")
    role: UserRole = Field(description="User role")
    permissions: List[str] = Field(default_factory=list, description="User permissions")
    iss: str = Field(description="Issuer")
    aud: str = Field(description="Audience")
    exp: int = Field(description="Expiration time")
    iat: int = Field(description="Issued at time")
    jti: str = Field(description="JWT ID")
    token_type: str = Field(description="Token type (access/refresh)")


class AuthStatus(BaseModel):
    """Authentication status response"""
    authenticated: bool = Field(description="Authentication status")
    user: Optional[UserContext] = Field(default=None, description="User context if authenticated")
    message: Optional[str] = Field(default=None, description="Status message")


class PasswordChangeRequest(BaseModel):
    """Password change request model"""
    current_password: str = Field(description="Current password")
    new_password: str = Field(min_length=8, description="New password")
    
    @validator('new_password')
    def validate_new_password_strength(cls, v):
        """Validate new password meets security requirements"""
        if len(v) < 8:
            raise ValueError('Password must be at least 8 characters long')
        
        has_upper = any(c.isupper() for c in v)
        has_lower = any(c.islower() for c in v)
        has_digit = any(c.isdigit() for c in v)
        has_special = any(c in "!@#$%^&*()_+-=[]{}|;:,.<>?" for c in v)
        
        if not (has_upper and has_lower and has_digit and has_special):
            raise ValueError('Password must contain uppercase, lowercase, number, and special character')
        
        return v


class UserProfile(BaseModel):
    """User profile response model"""
    user_id: str = Field(description="User ID")
    username: str = Field(description="Username")
    email: str = Field(description="Email address")
    role: UserRole = Field(description="User role")
    is_active: bool = Field(description="User active status")
    created_at: Optional[datetime] = Field(default=None, description="Account creation date")
    last_login: Optional[datetime] = Field(default=None, description="Last login time")


class AuthError(BaseModel):
    """Authentication error response"""
    error: str = Field(description="Error code")
    message: str = Field(description="Error message")
    details: Optional[dict] = Field(default=None, description="Additional error details")


# OAuth Models

class OAuthLoginRequest(BaseModel):
    """OAuth login request"""
    provider: str = Field(description="OAuth provider name")
    return_url: Optional[str] = Field(default=None, description="URL to redirect after authentication")


class OAuthLoginResponse(BaseModel):
    """OAuth login response with authorization URL"""
    authorization_url: str = Field(description="OAuth authorization URL")
    state: str = Field(description="OAuth state token")


class OAuthCallbackRequest(BaseModel):
    """OAuth callback request"""
    code: str = Field(description="Authorization code")
    state: str = Field(description="State token")


class OAuthLoginResult(BaseModel):
    """OAuth authentication result"""
    access_token: str = Field(description="JWT access token")
    refresh_token: str = Field(description="JWT refresh token")
    token_type: str = Field(default="bearer", description="Token type")
    expires_in: int = Field(description="Token expiration time in seconds")
    user: "UserProfile" = Field(description="User profile information")
    oauth_provider: str = Field(description="OAuth provider name")
    return_url: Optional[str] = Field(default=None, description="URL to redirect to")


class OAuthUserInfo(BaseModel):
    """OAuth user information from provider"""
    id: str = Field(description="OAuth provider user ID")
    email: str = Field(description="User email")
    name: Optional[str] = Field(default=None, description="User full name")
    username: Optional[str] = Field(default=None, description="Username")
    picture: Optional[str] = Field(default=None, description="Profile picture URL")
    provider: str = Field(description="OAuth provider name")
