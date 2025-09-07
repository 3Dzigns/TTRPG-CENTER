# db.py
"""
FR-DB-001: Local AuthZ/AuthN Store Database Engine
SQLite database engine factory with WAL mode and FK constraints enabled
"""

import os
from pathlib import Path
from typing import Optional
from sqlalchemy import create_engine, Engine, event, text
from sqlalchemy.orm import sessionmaker, Session
from sqlmodel import SQLModel
import logging

from .logging import get_logger

logger = get_logger(__name__)


def create_db_engine(database_path: Optional[str] = None, echo: bool = False) -> Engine:
    """
    Create SQLite database engine with optimized settings
    
    Args:
        database_path: Path to SQLite database file (from APP_DB_PATH if not provided)
        echo: Enable SQL query logging
        
    Returns:
        SQLAlchemy Engine configured for SQLite with WAL mode and FK constraints
    """
    if not database_path:
        database_path = os.getenv("APP_DB_PATH", "./data/app.db")
    
    # Ensure database directory exists
    db_dir = Path(database_path).parent
    db_dir.mkdir(parents=True, exist_ok=True)
    
    # Create SQLite connection URL
    db_url = f"sqlite:///{database_path}"
    
    # Create engine with optimization settings
    engine = create_engine(
        db_url,
        echo=echo or os.getenv("SQLALCHEMY_ECHO", "false").lower() == "true",
        connect_args={
            "check_same_thread": False,  # Allow multi-threading
            "timeout": 20,  # Connection timeout in seconds
        },
        pool_pre_ping=True,  # Verify connections before use
        pool_recycle=3600,  # Recycle connections every hour
    )
    
    # Configure SQLite optimizations on connect
    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        """Configure SQLite pragmas for optimal performance and safety"""
        cursor = dbapi_connection.cursor()
        
        # Enable Write-Ahead Logging (WAL) mode for better concurrency
        cursor.execute("PRAGMA journal_mode=WAL")
        
        # Enable foreign key constraints
        cursor.execute("PRAGMA foreign_keys=ON")
        
        # Optimize synchronization for development (adjust for production)
        cursor.execute("PRAGMA synchronous=NORMAL")
        
        # Set cache size (negative value = KB, positive = pages)
        cursor.execute("PRAGMA cache_size=-64000")  # 64MB cache
        
        # Set busy timeout for concurrent access
        cursor.execute("PRAGMA busy_timeout=30000")  # 30 seconds
        
        # Enable automatic index creation
        cursor.execute("PRAGMA automatic_index=ON")
        
        cursor.close()
    
    logger.info(f"Database engine created: {database_path}")
    return engine


def init_db(engine: Engine) -> None:
    """
    Initialize database by creating all tables
    
    Args:
        engine: SQLAlchemy engine
    """
    try:
        # Import all models to ensure they're registered
        from . import models  # This will import all models
        
        # Create all tables
        SQLModel.metadata.create_all(engine)
        
        logger.info("Database tables created successfully")
        
        # Log database info
        with engine.connect() as conn:
            result = conn.execute(text("SELECT name FROM sqlite_master WHERE type='table'"))
            tables = [row[0] for row in result]
            logger.info(f"Created tables: {', '.join(tables)}")
            
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        raise


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
            # Get database file info
            db_path = engine.url.database
            db_size = Path(db_path).stat().st_size if Path(db_path).exists() else 0
            
            # Get table count
            result = conn.execute(text("SELECT COUNT(*) FROM sqlite_master WHERE type='table'"))
            table_count = result.scalar()
            
            # Get WAL mode status
            result = conn.execute(text("PRAGMA journal_mode"))
            journal_mode = result.scalar()
            
            # Get foreign key status
            result = conn.execute(text("PRAGMA foreign_keys"))
            foreign_keys = bool(result.scalar())
            
            return {
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