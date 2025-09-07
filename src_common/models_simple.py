# models_simple.py
"""
FR-DB-001: Simplified Database Models for Initial Migration
Starting with core models to avoid inheritance issues
"""

import uuid
from datetime import datetime, timezone
from typing import Optional
from enum import Enum

from sqlmodel import SQLModel, Field, Column, DateTime
from sqlalchemy.sql import func


# Enums

class UserRole(str, Enum):
    """User role enumeration"""
    ADMIN = "admin"
    GM = "gm"
    PLAYER = "player"
    USER = "user"
    GUEST = "guest"


class GameMembershipRole(str, Enum):
    """Game membership role enumeration"""
    GM = "gm"
    PLAYER = "player"
    OBSERVER = "observer"


class SourceAccessType(str, Enum):
    """Source access type enumeration"""
    INCLUDED = "included"
    ALACARTE = "alacarte"
    TRIAL = "trial"


# Core Models

class User(SQLModel, table=True):
    """User table - central identity management"""
    __tablename__ = "users"
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True, max_length=36)
    username: str = Field(max_length=50, unique=True, index=True, nullable=False)
    email: str = Field(max_length=100, unique=True, index=True, nullable=False)
    password_hash: Optional[str] = Field(max_length=255, nullable=True)
    full_name: Optional[str] = Field(max_length=100, nullable=True)
    is_active: bool = Field(default=True, nullable=False)
    failed_attempts: int = Field(default=0, nullable=False)
    locked_until: Optional[datetime] = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))
    last_login: Optional[datetime] = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))
    
    # OAuth fields
    is_oauth_user: bool = Field(default=False, nullable=False)
    oauth_provider: Optional[str] = Field(max_length=50, nullable=True, index=True)
    oauth_id: Optional[str] = Field(max_length=100, nullable=True, index=True)
    
    # Timestamps
    created_at: Optional[datetime] = Field(default=None, sa_column=Column(DateTime(timezone=True), server_default=func.now(), nullable=False))
    updated_at: Optional[datetime] = Field(default=None, sa_column=Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False))


class Role(SQLModel, table=True):
    """Role table - define user roles and permissions"""
    __tablename__ = "roles"
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True, max_length=36)
    name: str = Field(max_length=50, unique=True, nullable=False)
    description: Optional[str] = Field(max_length=255, nullable=True)
    is_system: bool = Field(default=False, nullable=False)
    
    # Timestamps
    created_at: Optional[datetime] = Field(default=None, sa_column=Column(DateTime(timezone=True), server_default=func.now(), nullable=False))
    updated_at: Optional[datetime] = Field(default=None, sa_column=Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False))


class Permission(SQLModel, table=True):
    """Permission table - define granular permissions"""
    __tablename__ = "permissions"
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True, max_length=36)
    name: str = Field(max_length=50, unique=True, nullable=False)
    description: Optional[str] = Field(max_length=255, nullable=True)
    resource: str = Field(max_length=50, nullable=False)
    action: str = Field(max_length=50, nullable=False)
    
    # Timestamps
    created_at: Optional[datetime] = Field(default=None, sa_column=Column(DateTime(timezone=True), server_default=func.now(), nullable=False))
    updated_at: Optional[datetime] = Field(default=None, sa_column=Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False))


class UserRole_(SQLModel, table=True):
    """User-Role many-to-many relationship"""
    __tablename__ = "user_roles"
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True, max_length=36)
    user_id: str = Field(foreign_key="users.id", nullable=False)
    role_id: str = Field(foreign_key="roles.id", nullable=False)
    granted_by: Optional[str] = Field(foreign_key="users.id", nullable=True)
    expires_at: Optional[datetime] = Field(default=None, sa_column=Column(DateTime(timezone=True), nullable=True))
    
    # Timestamps
    created_at: Optional[datetime] = Field(default=None, sa_column=Column(DateTime(timezone=True), server_default=func.now(), nullable=False))
    updated_at: Optional[datetime] = Field(default=None, sa_column=Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False))


class RolePermission(SQLModel, table=True):
    """Role-Permission many-to-many relationship"""
    __tablename__ = "role_permissions"
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True, max_length=36)
    role_id: str = Field(foreign_key="roles.id", nullable=False)
    permission_id: str = Field(foreign_key="permissions.id", nullable=False)
    
    # Timestamps
    created_at: Optional[datetime] = Field(default=None, sa_column=Column(DateTime(timezone=True), server_default=func.now(), nullable=False))
    updated_at: Optional[datetime] = Field(default=None, sa_column=Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False))


class AuthTokenBlacklist(SQLModel, table=True):
    """Token blacklist for logout functionality"""
    __tablename__ = "auth_token_blacklist"
    
    jti: str = Field(primary_key=True, max_length=255)
    user_id: str = Field(foreign_key="users.id", nullable=False, index=True)
    expires_at: datetime = Field(sa_column=Column(DateTime(timezone=True), nullable=False))
    token_type: str = Field(max_length=20, default="access", nullable=False)
    
    # Timestamps
    created_at: Optional[datetime] = Field(default=None, sa_column=Column(DateTime(timezone=True), server_default=func.now(), nullable=False))


# Model exports
__all__ = [
    "User", "Role", "Permission", "UserRole_", "RolePermission", "AuthTokenBlacklist",
    "UserRole", "GameMembershipRole", "SourceAccessType"
]