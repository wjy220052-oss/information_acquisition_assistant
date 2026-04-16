#!/usr/bin/env python3
"""
Database initialization script
Creates all tables defined in the models
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import create_tables, check_connection
from app.core.logging import get_logger

logger = get_logger(__name__)


def init_database():
    """Initialize database tables"""
    logger.info("Checking database connection...")

    if not check_connection():
        logger.error("Database connection failed. Please check your .env configuration.")
        sys.exit(1)

    logger.info("Database connection successful. Creating tables...")

    try:
        create_tables()
        logger.info("Database tables created successfully!")
    except Exception as e:
        logger.error(f"Failed to create tables: {e}")
        sys.exit(1)


if __name__ == "__main__":
    init_database()
