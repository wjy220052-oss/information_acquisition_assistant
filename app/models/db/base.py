"""
Base model configuration

Provides common functionality for all models.
"""

from sqlalchemy.orm import DeclarativeBase

class Base(DeclarativeBase):
    """Base class for all models using SQLAlchemy 2.0 DeclarativeBase"""
    pass