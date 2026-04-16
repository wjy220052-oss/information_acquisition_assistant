"""
Database connection and session management

Provides SQLAlchemy engine, session management, and database utilities.
"""

from contextlib import contextmanager
from typing import Generator

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session

from app.core.config import get_settings
from app.core.logging import get_logger
from app.models.db.base import Base

logger = get_logger(__name__)

# Global variables
_engine = None
_SessionLocal = None


def get_engine():
    """Get database engine (singleton pattern)"""
    global _engine
    if _engine is None:
        settings = get_settings()
        database_url = settings.get_database_url()

        # Create engine with connection pooling
        _engine = create_engine(
            database_url,
            pool_size=5,
            max_overflow=10,
            pool_pre_ping=True,
            pool_recycle=300,
            echo=settings.DEBUG,  # Log SQL queries in debug mode
        )

        logger.info(f"Database engine created: {database_url}")

    return _engine


def get_db_session():
    """Get database session"""
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(
            autocommit=False,
            autoflush=False,
            bind=get_engine(),
        )

    return _SessionLocal()


@contextmanager
def get_db() -> Generator[Session, None, None]:
    """
    Get database session with automatic cleanup

    Yields:
        Database session
    """
    db = get_db_session()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def get_db_dependency() -> Generator[Session, None, None]:
    """
    Get database session for FastAPI dependency injection

    Yields:
        Database session
    """
    db = get_db_session()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def create_tables():
    """Create all tables defined in the models"""
    engine = get_engine()
    Base.metadata.create_all(bind=engine)
    logger.info("All tables created successfully")


def drop_tables():
    """Drop all tables (use with caution!)"""
    engine = get_engine()
    Base.metadata.drop_all(bind=engine)
    logger.warning("All tables dropped successfully")


def check_connection() -> bool:
    """Check if database connection is working"""
    try:
        with get_db() as db:
            # Simple query to check connection
            result = db.execute(text("SELECT 1"))
            result.fetchone()
        return True
    except Exception as e:
        logger.error(f"Database connection failed: {e}")
        return False