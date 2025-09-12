# models.py
"""
FR-DB-001: Local AuthZ/AuthN Store Database Models
Comprehensive database models using SQLModel for all entities
"""

import uuid
from datetime import datetime, timezone
from typing import List, Optional
from enum import Enum

from sqlmodel import SQLModel, Field, Relationship, Column, String, DateTime, Index
from sqlalchemy import UniqueConstraint, ForeignKey, text
from sqlalchemy.sql import func


# Enums

class UserRole(str, Enum):
    """User role enumeration"""
    ADMIN = "admin"
    GM = "gm"  # Game Master
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
    INCLUDED = "included"  # Full access included in subscription
    ALACARTE = "alacarte"  # Pay-per-use access
    TRIAL = "trial"        # Temporary trial access


# Core Models

class User(SQLModel, table=True):
    """User table - central identity management"""
    __tablename__ = "users"
    
    id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        primary_key=True,
        max_length=36
    )
    username: str = Field(max_length=50, unique=True, index=True, nullable=False)
    email: str = Field(max_length=100, unique=True, index=True, nullable=False)
    password_hash: Optional[str] = Field(max_length=255, nullable=True)  # Nullable for OAuth users
    full_name: Optional[str] = Field(max_length=100, nullable=True)
    is_active: bool = Field(default=True, nullable=False)
    failed_attempts: int = Field(default=0, nullable=False)
    locked_until: Optional[datetime] = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True)
    )
    last_login: Optional[datetime] = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True)
    )
    
    # OAuth fields
    is_oauth_user: bool = Field(default=False, nullable=False)
    oauth_provider: Optional[str] = Field(max_length=50, nullable=True, index=True)
    oauth_id: Optional[str] = Field(max_length=100, nullable=True, index=True)
    
    # Timestamps
    created_at: Optional[datetime] = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    )
    updated_at: Optional[datetime] = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    )
    
    # Relationships
    user_roles: List["UserRole_"] = Relationship(back_populates="user", cascade_delete=True)
    oauth_accounts: List["OAuthAccount"] = Relationship(back_populates="user", cascade_delete=True)
    created_games: List["Game"] = Relationship(back_populates="creator")
    game_memberships: List["GameMembership"] = Relationship(back_populates="user", cascade_delete=True)
    source_accesses: List["SourceAccess"] = Relationship(back_populates="user", cascade_delete=True)
    
    __table_args__ = (
        Index("idx_user_oauth", "oauth_provider", "oauth_id"),
    )


class Role(SQLModel, table=True):
    """Role table - define user roles and permissions"""
    __tablename__ = "roles"
    
    id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        primary_key=True,
        max_length=36
    )
    name: str = Field(max_length=50, unique=True, nullable=False)
    description: Optional[str] = Field(max_length=255, nullable=True)
    is_system: bool = Field(default=False, nullable=False)  # System-defined roles
    
    # Relationships
    user_roles: List["UserRole_"] = Relationship(back_populates="role", cascade_delete=True)
    role_permissions: List["RolePermission"] = Relationship(back_populates="role", cascade_delete=True)


class Permission(TimestampedModel, table=True):
    """Permission table - define granular permissions"""
    __tablename__ = "permissions"
    
    id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        primary_key=True,
        max_length=36
    )
    name: str = Field(max_length=50, unique=True, nullable=False)
    description: Optional[str] = Field(max_length=255, nullable=True)
    resource: str = Field(max_length=50, nullable=False)  # e.g., "users", "games", "sources"
    action: str = Field(max_length=50, nullable=False)    # e.g., "read", "write", "delete"
    
    # Relationships
    role_permissions: List["RolePermission"] = Relationship(back_populates="permission", cascade_delete=True)
    
    __table_args__ = (
        UniqueConstraint("resource", "action", name="uq_permission_resource_action"),
        Index("idx_permission_resource_action", "resource", "action"),
    )


class UserRole_(TimestampedModel, table=True):
    """User-Role many-to-many relationship"""
    __tablename__ = "user_roles"
    
    id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        primary_key=True,
        max_length=36
    )
    user_id: str = Field(foreign_key="users.id", nullable=False)
    role_id: str = Field(foreign_key="roles.id", nullable=False)
    granted_by: Optional[str] = Field(foreign_key="users.id", nullable=True)  # Who granted this role
    expires_at: Optional[datetime] = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True)
    )
    
    # Relationships
    user: User = Relationship(back_populates="user_roles", foreign_keys=[user_id])
    role: Role = Relationship(back_populates="user_roles")
    
    __table_args__ = (
        UniqueConstraint("user_id", "role_id", name="uq_user_role"),
        Index("idx_user_role_expires", "user_id", "expires_at"),
    )


class RolePermission(TimestampedModel, table=True):
    """Role-Permission many-to-many relationship"""
    __tablename__ = "role_permissions"
    
    id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        primary_key=True,
        max_length=36
    )
    role_id: str = Field(foreign_key="roles.id", nullable=False)
    permission_id: str = Field(foreign_key="permissions.id", nullable=False)
    
    # Relationships
    role: Role = Relationship(back_populates="role_permissions")
    permission: Permission = Relationship(back_populates="role_permissions")
    
    __table_args__ = (
        UniqueConstraint("role_id", "permission_id", name="uq_role_permission"),
    )


class OAuthAccount(TimestampedModel, table=True):
    """OAuth account linkage"""
    __tablename__ = "oauth_accounts"
    
    id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        primary_key=True,
        max_length=36
    )
    user_id: str = Field(foreign_key="users.id", nullable=False)
    provider: str = Field(max_length=50, nullable=False, index=True)  # "google", "github", etc.
    provider_user_id: str = Field(max_length=100, nullable=False, index=True)  # OAuth provider's user ID
    provider_username: Optional[str] = Field(max_length=100, nullable=True)
    provider_email: Optional[str] = Field(max_length=100, nullable=True)
    provider_name: Optional[str] = Field(max_length=100, nullable=True)
    provider_picture: Optional[str] = Field(max_length=500, nullable=True)
    access_token: Optional[str] = Field(max_length=1000, nullable=True)  # Encrypted
    refresh_token: Optional[str] = Field(max_length=1000, nullable=True)  # Encrypted
    expires_at: Optional[datetime] = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True)
    )
    is_primary: bool = Field(default=False, nullable=False)  # Primary OAuth account for user
    
    # Relationships
    user: User = Relationship(back_populates="oauth_accounts")
    
    __table_args__ = (
        UniqueConstraint("provider", "provider_user_id", name="uq_oauth_provider_user"),
        Index("idx_oauth_provider_email", "provider", "provider_email"),
    )


class Game(TimestampedModel, table=True):
    """Game table - TTRPG games/campaigns"""
    __tablename__ = "games"
    
    id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        primary_key=True,
        max_length=36
    )
    name: str = Field(max_length=100, nullable=False)
    description: Optional[str] = Field(max_length=1000, nullable=True)
    system: str = Field(max_length=50, nullable=False)  # "D&D 5e", "Pathfinder", etc.
    created_by_user_id: str = Field(foreign_key="users.id", nullable=False)
    is_active: bool = Field(default=True, nullable=False)
    max_players: int = Field(default=6, nullable=False)
    session_frequency: Optional[str] = Field(max_length=50, nullable=True)  # "weekly", "bi-weekly", etc.
    start_date: Optional[datetime] = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True)
    )
    end_date: Optional[datetime] = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True)
    )
    
    # Relationships
    creator: User = Relationship(back_populates="created_games")
    memberships: List["GameMembership"] = Relationship(back_populates="game", cascade_delete=True)
    
    __table_args__ = (
        Index("idx_game_system_active", "system", "is_active"),
        Index("idx_game_creator_active", "created_by_user_id", "is_active"),
    )


class GameMembership(TimestampedModel, table=True):
    """Game membership - users participating in games"""
    __tablename__ = "game_memberships"
    
    id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        primary_key=True,
        max_length=36
    )
    game_id: str = Field(foreign_key="games.id", nullable=False)
    user_id: str = Field(foreign_key="users.id", nullable=False)
    role_in_game: GameMembershipRole = Field(nullable=False)
    character_name: Optional[str] = Field(max_length=100, nullable=True)
    character_class: Optional[str] = Field(max_length=50, nullable=True)
    character_level: Optional[int] = Field(nullable=True)
    joined_at: Optional[datetime] = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    )
    left_at: Optional[datetime] = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True)
    )
    is_active: bool = Field(default=True, nullable=False)
    notes: Optional[str] = Field(max_length=1000, nullable=True)
    
    # Relationships
    game: Game = Relationship(back_populates="memberships")
    user: User = Relationship(back_populates="game_memberships")
    
    __table_args__ = (
        UniqueConstraint("game_id", "user_id", name="uq_game_user_membership"),
        Index("idx_membership_game_active", "game_id", "is_active"),
        Index("idx_membership_user_active", "user_id", "is_active"),
    )


class Source(TimestampedModel, table=True):
    """Source table - TTRPG content sources (books, modules, etc.)"""
    __tablename__ = "sources"
    
    id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        primary_key=True,
        max_length=36
    )
    name: str = Field(max_length=100, nullable=False, index=True)
    short_name: str = Field(max_length=20, nullable=False, unique=True)  # e.g., "PHB", "DMG"
    system: str = Field(max_length=50, nullable=False, index=True)  # "D&D 5e", "Pathfinder", etc.
    publisher: str = Field(max_length=100, nullable=False)
    version: Optional[str] = Field(max_length=20, nullable=True)
    isbn: Optional[str] = Field(max_length=20, nullable=True, unique=True)
    publication_date: Optional[datetime] = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True)
    )
    description: Optional[str] = Field(max_length=1000, nullable=True)
    is_available: bool = Field(default=True, nullable=False)
    is_core: bool = Field(default=False, nullable=False)  # Core rulebook vs. supplement
    price_cents: Optional[int] = Field(nullable=True)  # Price in cents for alacarte access
    file_path: Optional[str] = Field(max_length=500, nullable=True)  # Path to PDF file
    page_count: Optional[int] = Field(nullable=True)
    
    # Relationships
    access_grants: List["SourceAccess"] = Relationship(back_populates="source", cascade_delete=True)
    
    __table_args__ = (
        Index("idx_source_system_available", "system", "is_available"),
        Index("idx_source_name_system", "name", "system"),
    )


class SourceAccess(TimestampedModel, table=True):
    """Source access grants - user access to specific sources"""
    __tablename__ = "source_accesses"
    
    id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        primary_key=True,
        max_length=36
    )
    user_id: str = Field(foreign_key="users.id", nullable=False)
    source_id: str = Field(foreign_key="sources.id", nullable=False)
    access_type: SourceAccessType = Field(nullable=False)
    granted_by: Optional[str] = Field(foreign_key="users.id", nullable=True)  # Admin who granted access
    granted_at: Optional[datetime] = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    )
    expires_at: Optional[datetime] = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True)
    )
    is_active: bool = Field(default=True, nullable=False)
    usage_count: int = Field(default=0, nullable=False)  # For alacarte tracking
    last_accessed: Optional[datetime] = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True)
    )
    license_key: Optional[str] = Field(max_length=100, nullable=True)  # For future licensing
    notes: Optional[str] = Field(max_length=500, nullable=True)
    
    # Relationships
    user: User = Relationship(back_populates="source_accesses")
    source: Source = Relationship(back_populates="access_grants")
    
    __table_args__ = (
        UniqueConstraint("user_id", "source_id", name="uq_user_source_access"),
        Index("idx_access_user_active", "user_id", "is_active"),
        Index("idx_access_source_type", "source_id", "access_type"),
        Index("idx_access_expires", "expires_at"),
    )


class SourceIngestionHistory(TimestampedModel, table=True):
    """Track source processing history for SHA-based Pass C bypass"""
    __tablename__ = "source_ingestion_history"
    
    source_hash: str = Field(primary_key=True, max_length=64)  # SHA-256 hash
    source_path: str = Field(max_length=500, nullable=False, index=True)
    chunk_count: int = Field(nullable=False)
    last_processed_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    )
    environment: str = Field(max_length=10, nullable=False, index=True)  # dev/test/prod
    pass_c_artifacts_path: Optional[str] = Field(max_length=500, nullable=True)  # Path to Pass C artifacts
    
    __table_args__ = (
        Index("idx_ingestion_source_path", "source_path"),
        Index("idx_ingestion_environment", "environment"),
        Index("idx_ingestion_processed_at", "last_processed_at"),
    )


class AuthTokenBlacklist(TimestampedModel, table=True):
    """Token blacklist for logout functionality"""
    __tablename__ = "auth_token_blacklist"
    
    jti: str = Field(primary_key=True, max_length=255)  # JWT ID
    user_id: str = Field(foreign_key="users.id", nullable=False, index=True)
    expires_at: datetime = Field(
        sa_column=Column(DateTime(timezone=True), nullable=False)
    )
    token_type: str = Field(max_length=20, default="access", nullable=False)  # "access" or "refresh"
    
    __table_args__ = (
        Index("idx_blacklist_expires", "expires_at"),
        Index("idx_blacklist_user_expires", "user_id", "expires_at"),
    )


# Initialize all models
def create_all_tables(engine):
    """Create all tables"""
    SQLModel.metadata.create_all(engine)


# Model exports for easy importing
__all__ = [
    "User", "Role", "Permission", "UserRole_", "RolePermission",
    "OAuthAccount", "Game", "GameMembership", "Source", "SourceAccess",
    "SourceIngestionHistory", "AuthTokenBlacklist", "UserRole", "GameMembershipRole", "SourceAccessType",
    "TimestampedModel", "create_all_tables"
]