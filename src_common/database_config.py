# database_config.py
"""
FR-006: Enhanced Database Configuration
Support for PostgreSQL (containerized) and SQLite (fallback/testing)
"""

import os
from typing import Optional, Dict, Any
from urllib.parse import quote_plus
from sqlalchemy import create_engine, Engine, event, text
from sqlalchemy.orm import sessionmaker, Session
from sqlmodel import SQLModel
import logging

from .ttrpg_logging import get_logger

logger = get_logger(__name__)


class DatabaseConfig:
    """Database configuration factory supporting multiple database types"""
    
    @staticmethod
    def get_database_url() -> str:
        """
        Get database URL based on environment configuration
        
        Returns:
            Database URL string
        """
        # Check for PostgreSQL configuration first (containerized)
        postgres_host = os.getenv("POSTGRES_HOST")
        if postgres_host:
            postgres_user = os.getenv("POSTGRES_USER", "ttrpg_user")
            postgres_password = os.getenv("POSTGRES_PASSWORD", "ttrpg_dev_pass")
            postgres_db = os.getenv("POSTGRES_DB", "ttrpg_dev")
            postgres_port = os.getenv("POSTGRES_PORT", "5432")
            
            # URL encode password to handle special characters
            encoded_password = quote_plus(postgres_password)
            
            url = f"postgresql://{postgres_user}:{encoded_password}@{postgres_host}:{postgres_port}/{postgres_db}"
            logger.info(f"Using PostgreSQL database: {postgres_host}:{postgres_port}/{postgres_db}")
            return url
        
        # Fallback to SQLite (original configuration)
        database_path = os.getenv("APP_DB_PATH", "./data/app.db")
        url = f"sqlite:///{database_path}"
        logger.info(f"Using SQLite database: {database_path}")
        return url
    
    @staticmethod
    def get_engine_config() -> Dict[str, Any]:
        """
        Get engine configuration based on database type
        
        Returns:
            Dictionary of engine configuration parameters
        """
        database_url = DatabaseConfig.get_database_url()
        
        if database_url.startswith("postgresql://"):
            # PostgreSQL configuration
            return {
                "echo": os.getenv("SQLALCHEMY_ECHO", "false").lower() == "true",
                "pool_size": int(os.getenv("DB_POOL_SIZE", "10")),
                "max_overflow": int(os.getenv("DB_MAX_OVERFLOW", "20")),
                "pool_pre_ping": True,
                "pool_recycle": int(os.getenv("DB_POOL_RECYCLE", "3600")),
                "connect_args": {
                    "connect_timeout": int(os.getenv("DB_CONNECT_TIMEOUT", "10")),
                    "application_name": "ttrpg_center_dev",
                }
            }
        else:
            # SQLite configuration (original)
            return {
                "echo": os.getenv("SQLALCHEMY_ECHO", "false").lower() == "true",
                "connect_args": {
                    "check_same_thread": False,
                    "timeout": 20,
                },
                "pool_pre_ping": True,
                "pool_recycle": 3600,
            }


def create_db_engine(echo: bool = False) -> Engine:
    """
    Create database engine with optimized settings for PostgreSQL or SQLite
    
    Args:
        echo: Enable SQL query logging
        
    Returns:
        SQLAlchemy Engine configured for the target database
    """
    database_url = DatabaseConfig.get_database_url()
    engine_config = DatabaseConfig.get_engine_config()
    
    if echo:
        engine_config["echo"] = True
    
    # Create engine
    engine = create_engine(database_url, **engine_config)
    
    # Configure database-specific optimizations
    if database_url.startswith("postgresql://"):
        _configure_postgresql(engine)
    else:
        _configure_sqlite(engine)
    
    logger.info(f"Database engine created: {database_url.split('@')[-1] if '@' in database_url else database_url}")
    return engine


def _configure_postgresql(engine: Engine) -> None:
    """Configure PostgreSQL-specific optimizations"""
    
    @event.listens_for(engine, "connect")
    def set_postgresql_config(dbapi_connection, connection_record):
        """Configure PostgreSQL connection settings"""
        with dbapi_connection.cursor() as cursor:
            # Set timezone
            cursor.execute("SET timezone TO 'UTC'")
            
            # Set statement timeout (30 seconds)
            cursor.execute("SET statement_timeout TO '30s'")
            
            # Set search path
            cursor.execute("SET search_path TO public")
            
            # Commit the settings
            dbapi_connection.commit()


def _configure_sqlite(engine: Engine) -> None:
    """Configure SQLite-specific optimizations (original configuration)"""
    
    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        """Configure SQLite pragmas for optimal performance and safety"""
        cursor = dbapi_connection.cursor()
        
        # Enable Write-Ahead Logging (WAL) mode for better concurrency
        cursor.execute("PRAGMA journal_mode=WAL")
        
        # Enable foreign key constraints
        cursor.execute("PRAGMA foreign_keys=ON")
        
        # Optimize synchronization for development
        cursor.execute("PRAGMA synchronous=NORMAL")
        
        # Set cache size (64MB)
        cursor.execute("PRAGMA cache_size=-64000")
        
        # Set busy timeout for concurrent access
        cursor.execute("PRAGMA busy_timeout=30000")
        
        # Enable automatic index creation
        cursor.execute("PRAGMA automatic_index=ON")
        
        cursor.close()


def init_db(engine: Engine) -> None:
    """
    Initialize database by creating all tables
    
    Args:
        engine: SQLAlchemy engine
    """
    try:
        # Import all models to ensure they're registered
        from . import models
        
        # Create all tables
        SQLModel.metadata.create_all(engine)
        
        logger.info("Database tables created successfully")
        
        # Log database info
        _log_database_info(engine)
            
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        raise


def _log_database_info(engine: Engine) -> None:
    """Log database information after initialization"""
    try:
        with engine.connect() as conn:
            if engine.url.drivername.startswith("postgresql"):
                # PostgreSQL: Get table information
                result = conn.execute(text("""
                    SELECT table_name 
                    FROM information_schema.tables 
                    WHERE table_schema = 'public' 
                    AND table_type = 'BASE TABLE'
                """))
                tables = [row[0] for row in result]
                logger.info(f"PostgreSQL tables created: {', '.join(tables)}")
            else:
                # SQLite: Get table information
                result = conn.execute(text("SELECT name FROM sqlite_master WHERE type='table'"))
                tables = [row[0] for row in result]
                logger.info(f"SQLite tables created: {', '.join(tables)}")
                
    except Exception as e:
        logger.warning(f"Could not log database info: {e}")


def get_session_factory(engine: Engine) -> sessionmaker:
    """
    Create session factory for database operations
    
    Args:
        engine: SQLAlchemy engine
        
    Returns:
        SQLAlchemy session factory
    """
    return sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_database_info(engine: Engine) -> dict:
    """
    Get database information and statistics
    
    Args:
        engine: SQLAlchemy engine
        
    Returns:
        Dictionary with database information
    """
    try:
        with engine.connect() as conn:
            if engine.url.drivername.startswith("postgresql"):
                # PostgreSQL information
                result = conn.execute(text("SELECT version()"))
                version = result.scalar()
                
                result = conn.execute(text("""
                    SELECT COUNT(*) 
                    FROM information_schema.tables 
                    WHERE table_schema = 'public' 
                    AND table_type = 'BASE TABLE'
                """))
                table_count = result.scalar()
                
                return {
                    "database_type": "PostgreSQL",
                    "database_host": engine.url.host,
                    "database_name": engine.url.database,
                    "database_version": version.split(' ')[1] if version else "unknown",
                    "table_count": table_count,
                    "connection_pool_size": engine.pool.size(),
                }
            else:
                # SQLite information (original)
                from pathlib import Path
                db_path = engine.url.database
                db_size = Path(db_path).stat().st_size if Path(db_path).exists() else 0
                
                result = conn.execute(text("SELECT COUNT(*) FROM sqlite_master WHERE type='table'"))
                table_count = result.scalar()
                
                result = conn.execute(text("PRAGMA journal_mode"))
                journal_mode = result.scalar()
                
                result = conn.execute(text("PRAGMA foreign_keys"))
                foreign_keys = bool(result.scalar())
                
                return {
                    "database_type": "SQLite",
                    "database_path": db_path,
                    "database_size_bytes": db_size,
                    "database_size_mb": round(db_size / 1024 / 1024, 2),
                    "table_count": table_count,
                    "journal_mode": journal_mode,
                    "foreign_keys_enabled": foreign_keys,
                }
                
    except Exception as e:
        logger.error(f"Failed to get database info: {e}")
        return {"error": str(e)}


# Global database components (initialized on first use)
_engine: Optional[Engine] = None
_session_factory: Optional[sessionmaker] = None


def get_engine() -> Engine:
    """Get or create the global database engine"""
    global _engine
    if _engine is None:
        _engine = create_db_engine()
    return _engine


def get_session() -> Session:
    """Get a new database session"""
    global _session_factory
    if _session_factory is None:
        _session_factory = get_session_factory(get_engine())
    return _session_factory()


def close_db():
    """Close database connections (for testing/cleanup)"""
    global _engine, _session_factory
    if _engine:
        _engine.dispose()
        _engine = None
    _session_factory = None


def test_database_connection() -> bool:
    """
    Test database connection
    
    Returns:
        True if connection successful, False otherwise
    """
    try:
        engine = get_engine()
        with engine.connect() as conn:
            if engine.url.drivername.startswith("postgresql"):
                conn.execute(text("SELECT 1"))
            else:
                conn.execute(text("SELECT 1"))
        logger.info("Database connection test successful")
        return True
    except Exception as e:
        logger.error(f"Database connection test failed: {e}")
        return False