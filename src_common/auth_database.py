# auth_database.py
"""
FR-SEC-401: Authentication Database Management
Database operations for user authentication and token management
"""

import os
import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any
from sqlalchemy import create_engine, and_, or_
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.exc import IntegrityError
import logging

from .auth_models import Base, AuthUser, AuthTokenBlacklist, UserRole
from .jwt_service import PasswordService
from .logging import get_logger

logger = get_logger(__name__)


class AuthDatabaseManager:
    """Database manager for authentication system"""
    
    def __init__(self, database_url: Optional[str] = None):
        """
        Initialize database manager
        
        Args:
            database_url: Database connection URL (from environment if not provided)
        """
        self.database_url = database_url or self._get_database_url()
        self.engine = create_engine(
            self.database_url,
            pool_pre_ping=True,
            pool_recycle=300,
            echo=os.getenv("SQLALCHEMY_ECHO", "false").lower() == "true"
        )
        
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
        self.password_service = PasswordService()
        
        logger.info("Authentication database manager initialized")
    
    def _get_database_url(self) -> str:
        """Get database URL from environment or use SQLite for development"""
        db_url = os.getenv("AUTH_DATABASE_URL")
        if not db_url:
            if os.getenv("ENVIRONMENT", "dev") == "dev":
                # Use SQLite for development
                db_url = "sqlite:///./auth.db"
                logger.warning("Using SQLite for development - not suitable for production")
            else:
                raise ValueError("AUTH_DATABASE_URL environment variable required for production")
        return db_url
    
    def create_tables(self) -> None:
        """Create all authentication tables"""
        try:
            Base.metadata.create_all(bind=self.engine)
            logger.info("Authentication tables created successfully")
        except Exception as e:
            logger.error(f"Failed to create authentication tables: {e}")
            raise
    
    def get_session(self) -> Session:
        """Get database session"""
        return self.SessionLocal()
    
    def create_user(self, username: str, email: str, password: str = None, 
                   role: UserRole = UserRole.USER, full_name: str = None,
                   oauth_provider: str = None, oauth_id: str = None, 
                   is_oauth_user: bool = False) -> AuthUser:
        """
        Create new user
        
        Args:
            username: Username
            email: Email address
            password: Plain text password (None for OAuth users)
            role: User role
            full_name: Full name
            oauth_provider: OAuth provider name
            oauth_id: OAuth provider user ID
            is_oauth_user: Whether this is an OAuth user
            
        Returns:
            Created user object
            
        Raises:
            IntegrityError: If username or email already exists
        """
        with self.get_session() as db:
            try:
                # Hash password if provided (regular users)
                password_hash = None
                if password and not is_oauth_user:
                    password_hash = self.password_service.hash_password(password)
                
                # Create user
                user = AuthUser(
                    id=uuid.uuid4(),
                    username=username.lower(),
                    email=email.lower(),
                    password_hash=password_hash,
                    role=role,
                    is_active=True,
                    created_at=datetime.now(timezone.utc),
                    full_name=full_name,
                    oauth_provider=oauth_provider,
                    oauth_id=oauth_id,
                    is_oauth_user=is_oauth_user
                )
                
                db.add(user)
                db.commit()
                db.refresh(user)
                
                logger.info(f"Created user: {username} (role: {role.value})")
                return user
                
            except IntegrityError as e:
                db.rollback()
                logger.warning(f"User creation failed - duplicate username/email: {username}")
                raise ValueError("Username or email already exists")
            except Exception as e:
                db.rollback()
                logger.error(f"User creation failed: {e}")
                raise
    
    def get_user_by_username(self, username: str) -> Optional[AuthUser]:
        """
        Get user by username
        
        Args:
            username: Username to look up
            
        Returns:
            User object or None if not found
        """
        with self.get_session() as db:
            user = db.query(AuthUser).filter(
                AuthUser.username == username.lower()
            ).first()
            
            if user:
                logger.debug(f"Found user: {username}")
            else:
                logger.debug(f"User not found: {username}")
            
            return user
    
    def get_user_by_email(self, email: str) -> Optional[AuthUser]:
        """
        Get user by email
        
        Args:
            email: Email to look up
            
        Returns:
            User object or None if not found
        """
        with self.get_session() as db:
            user = db.query(AuthUser).filter(
                AuthUser.email == email.lower()
            ).first()
            
            if user:
                logger.debug(f"Found user by email: {email}")
            
            return user
    
    def get_user_by_id(self, user_id: str) -> Optional[AuthUser]:
        """
        Get user by ID
        
        Args:
            user_id: User ID to look up
            
        Returns:
            User object or None if not found
        """
        with self.get_session() as db:
            try:
                user = db.query(AuthUser).filter(
                    AuthUser.id == uuid.UUID(user_id)
                ).first()
                
                if user:
                    logger.debug(f"Found user by ID: {user_id}")
                
                return user
            except ValueError:
                logger.warning(f"Invalid user ID format: {user_id}")
                return None
    
    def get_user_by_oauth_id(self, oauth_provider: str, oauth_id: str) -> Optional[AuthUser]:
        """
        Get user by OAuth provider and ID
        
        Args:
            oauth_provider: OAuth provider name
            oauth_id: OAuth provider user ID
            
        Returns:
            User object or None if not found
        """
        with self.get_session() as db:
            user = db.query(AuthUser).filter(
                and_(
                    AuthUser.oauth_provider == oauth_provider,
                    AuthUser.oauth_id == oauth_id
                )
            ).first()
            
            if user:
                logger.debug(f"Found OAuth user: {oauth_provider}:{oauth_id}")
            else:
                logger.debug(f"OAuth user not found: {oauth_provider}:{oauth_id}")
            
            return user
    
    def authenticate_user(self, username: str, password: str) -> Optional[AuthUser]:
        """
        Authenticate user with username and password
        
        Args:
            username: Username
            password: Plain text password
            
        Returns:
            User object if authentication successful, None otherwise
        """
        user = self.get_user_by_username(username)
        if not user:
            logger.info(f"Authentication failed - user not found: {username}")
            return None
        
        if not user.is_active:
            logger.info(f"Authentication failed - user inactive: {username}")
            return None
        
        # Check if user is locked
        if user.locked_until and user.locked_until > datetime.now(timezone.utc):
            logger.info(f"Authentication failed - user locked: {username}")
            return None
        
        # Verify password
        if not self.password_service.verify_password(password, user.password_hash):
            # Increment failed attempts
            self.increment_failed_attempts(user.id)
            logger.info(f"Authentication failed - invalid password: {username}")
            return None
        
        # Authentication successful - clear failed attempts and update last login
        self.clear_failed_attempts(user.id)
        self.update_last_login(user.id)
        
        logger.info(f"Authentication successful: {username}")
        return user
    
    def increment_failed_attempts(self, user_id: uuid.UUID) -> None:
        """
        Increment failed login attempts for user
        
        Args:
            user_id: User ID
        """
        with self.get_session() as db:
            try:
                user = db.query(AuthUser).filter(AuthUser.id == user_id).first()
                if user:
                    user.failed_attempts += 1
                    
                    # Lock user after 5 failed attempts
                    if user.failed_attempts >= 5:
                        user.locked_until = datetime.now(timezone.utc) + timedelta(minutes=15)
                        logger.warning(f"User locked after failed attempts: {user.username}")
                    
                    db.commit()
                    logger.debug(f"Incremented failed attempts for user {user.username}: {user.failed_attempts}")
                    
            except Exception as e:
                db.rollback()
                logger.error(f"Failed to increment failed attempts: {e}")
    
    def clear_failed_attempts(self, user_id: uuid.UUID) -> None:
        """
        Clear failed login attempts for user
        
        Args:
            user_id: User ID
        """
        with self.get_session() as db:
            try:
                user = db.query(AuthUser).filter(AuthUser.id == user_id).first()
                if user:
                    user.failed_attempts = 0
                    user.locked_until = None
                    db.commit()
                    logger.debug(f"Cleared failed attempts for user {user.username}")
                    
            except Exception as e:
                db.rollback()
                logger.error(f"Failed to clear failed attempts: {e}")
    
    def update_last_login(self, user_id: uuid.UUID) -> None:
        """
        Update user's last login time
        
        Args:
            user_id: User ID
        """
        with self.get_session() as db:
            try:
                user = db.query(AuthUser).filter(AuthUser.id == user_id).first()
                if user:
                    user.last_login = datetime.now(timezone.utc)
                    db.commit()
                    logger.debug(f"Updated last login for user {user.username}")
                    
            except Exception as e:
                db.rollback()
                logger.error(f"Failed to update last login: {e}")
    
    def change_password(self, user_id: str, current_password: str, new_password: str) -> bool:
        """
        Change user password
        
        Args:
            user_id: User ID
            current_password: Current password
            new_password: New password
            
        Returns:
            True if password changed successfully
        """
        with self.get_session() as db:
            try:
                user = db.query(AuthUser).filter(AuthUser.id == uuid.UUID(user_id)).first()
                if not user:
                    logger.warning(f"Password change failed - user not found: {user_id}")
                    return False
                
                # Verify current password
                if not self.password_service.verify_password(current_password, user.password_hash):
                    logger.info(f"Password change failed - invalid current password: {user.username}")
                    return False
                
                # Hash new password
                new_password_hash = self.password_service.hash_password(new_password)
                user.password_hash = new_password_hash
                
                db.commit()
                logger.info(f"Password changed for user: {user.username}")
                return True
                
            except Exception as e:
                db.rollback()
                logger.error(f"Password change failed: {e}")
                return False
    
    def blacklist_token(self, jti: str, user_id: str, expires_at: datetime) -> None:
        """
        Add token to blacklist
        
        Args:
            jti: JWT ID
            user_id: User ID
            expires_at: Token expiration time
        """
        with self.get_session() as db:
            try:
                blacklisted_token = AuthTokenBlacklist(
                    jti=jti,
                    user_id=uuid.UUID(user_id),
                    expires_at=expires_at,
                    created_at=datetime.now(timezone.utc)
                )
                
                db.add(blacklisted_token)
                db.commit()
                
                logger.info(f"Token blacklisted: {jti}")
                
            except Exception as e:
                db.rollback()
                logger.error(f"Failed to blacklist token: {e}")
                raise
    
    def is_token_blacklisted(self, jti: str) -> bool:
        """
        Check if token is blacklisted
        
        Args:
            jti: JWT ID
            
        Returns:
            True if token is blacklisted
        """
        with self.get_session() as db:
            blacklisted = db.query(AuthTokenBlacklist).filter(
                AuthTokenBlacklist.jti == jti
            ).first()
            
            is_blacklisted = blacklisted is not None
            logger.debug(f"Token blacklist check for {jti}: {'blacklisted' if is_blacklisted else 'valid'}")
            
            return is_blacklisted
    
    def cleanup_expired_tokens(self) -> int:
        """
        Remove expired tokens from blacklist
        
        Returns:
            Number of tokens removed
        """
        with self.get_session() as db:
            try:
                now = datetime.now(timezone.utc)
                count = db.query(AuthTokenBlacklist).filter(
                    AuthTokenBlacklist.expires_at < now
                ).count()
                
                db.query(AuthTokenBlacklist).filter(
                    AuthTokenBlacklist.expires_at < now
                ).delete()
                
                db.commit()
                
                if count > 0:
                    logger.info(f"Cleaned up {count} expired blacklisted tokens")
                
                return count
                
            except Exception as e:
                db.rollback()
                logger.error(f"Failed to cleanup expired tokens: {e}")
                return 0
    
    def create_default_admin(self, username: str = "admin", 
                            email: str = "admin@ttrpg-center.com",
                            password: str = "Admin123!") -> Optional[AuthUser]:
        """
        Create default admin user for initial setup
        
        Args:
            username: Admin username
            email: Admin email
            password: Admin password
            
        Returns:
            Created admin user or None if already exists
        """
        try:
            # Check if admin already exists
            existing_admin = self.get_user_by_username(username)
            if existing_admin:
                logger.info(f"Admin user already exists: {username}")
                return existing_admin
            
            # Create admin user
            admin_user = self.create_user(username, email, password, UserRole.ADMIN)
            logger.info(f"Created default admin user: {username}")
            return admin_user
            
        except Exception as e:
            logger.error(f"Failed to create default admin: {e}")
            return None
    
    def get_user_stats(self) -> Dict[str, Any]:
        """
        Get user statistics
        
        Returns:
            Dictionary with user statistics
        """
        with self.get_session() as db:
            try:
                total_users = db.query(AuthUser).count()
                active_users = db.query(AuthUser).filter(AuthUser.is_active == True).count()
                admin_users = db.query(AuthUser).filter(AuthUser.role == UserRole.ADMIN).count()
                locked_users = db.query(AuthUser).filter(
                    and_(
                        AuthUser.locked_until.isnot(None),
                        AuthUser.locked_until > datetime.now(timezone.utc)
                    )
                ).count()
                
                recent_logins = db.query(AuthUser).filter(
                    AuthUser.last_login > datetime.now(timezone.utc) - timedelta(days=30)
                ).count()
                
                return {
                    "total_users": total_users,
                    "active_users": active_users,
                    "admin_users": admin_users,
                    "locked_users": locked_users,
                    "recent_logins": recent_logins
                }
                
            except Exception as e:
                logger.error(f"Failed to get user stats: {e}")
                return {}


# Global database manager instance
auth_db = AuthDatabaseManager()