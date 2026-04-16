"""
Tests for database connection and models
"""

import pytest
from sqlalchemy import inspect

from app.core.database import check_connection, create_tables, drop_tables, get_engine
from app.models.db import tables


@pytest.fixture(scope="module", autouse=True)
def setup_database():
    """Setup test database"""
    drop_tables()
    create_tables()
    yield
    drop_tables()


def test_database_connection():
    """Test database connectivity"""
    assert check_connection(), "Database connection failed"


def test_all_tables_created():
    """Test all tables are created"""
    inspector = inspect(get_engine())
    tables_expected = {
        'sources', 'authors', 'articles',
        'recommendations', 'feedbacks', 'reading_queues'
    }
    tables_found = set(inspector.get_table_names())
    assert tables_expected.issubset(tables_found), f"Missing tables: {tables_expected - tables_found}"


def test_source_table_constraints():
    """Test Source table constraints"""
    from app.models.db.tables import Source
    inspector = inspect(get_engine())

    # Check unique constraints (sources table has source_key and slug as unique columns)
    constraints = inspector.get_unique_constraints('sources')
    constraint_names = {c['name'] for c in constraints}
    # SQLAlchemy auto-generates unique constraint names for unique=True columns
    # Just verify constraints exist
    assert len(constraints) >= 2, "Source table should have at least 2 unique constraints (source_key, slug)"


def test_article_table_constraints():
    """Test Article table constraints"""
    from app.models.db.tables import Article
    inspector = inspect(get_engine())

    # Check unique constraints
    constraints = inspector.get_unique_constraints('articles')
    constraint_names = {c['name'] for c in constraints}
    assert 'uq_source_source_item_id' in constraint_names


def test_recommendation_table_constraints():
    """Test Recommendation table constraints"""
    from app.models.db.tables import Recommendation
    inspector = inspect(get_engine())

    # Check unique constraints
    constraints = inspector.get_unique_constraints('recommendations')
    constraint_names = {c['name'] for c in constraints}
    assert 'uq_user_article_type_batch_date' in constraint_names


def test_reading_queue_table_constraints():
    """Test ReadingQueue table constraints"""
    from app.models.db.tables import ReadingQueue
    inspector = inspect(get_engine())

    # Check unique constraints
    constraints = inspector.get_unique_constraints('reading_queues')
    constraint_names = {c['name'] for c in constraints}
    assert 'uq_user_article_id' in constraint_names


def test_enum_values():
    """Test enum values are correctly defined"""
    from sqlalchemy import inspect as sql_inspect
    from app.models.db.tables import Article, Source

    # Note: content_type is now VARCHAR(50) to support multiple content types
    # from ContentClassifier (technology, product, life, culture, etc.)
    # Skip ENUM check for content_type

    # Test source type enum on Source table
    source_inspector = sql_inspect(Source)
    source_type_column = source_inspector.columns['type']
    source_type_enum = source_type_column.type
    source_type_values = source_type_enum.enums
    assert 'rsshub' in source_type_values
    assert 'api' in source_type_values
    assert 'rss' in source_type_values
    assert 'scraper' in source_type_values

    # Test status enum on Article table
    article_inspector = sql_inspect(Article)
    status_column = article_inspector.columns['status']
    status_enum = status_column.type
    status_values = status_enum.enums
    assert 'pending' in status_values
    assert 'processed' in status_values
    assert 'failed' in status_values

    # Test quality_level enum on Article table (for quality scoring)
    quality_level_column = article_inspector.columns['quality_level']
    quality_level_enum = quality_level_column.type
    quality_level_values = quality_level_enum.enums
    assert 'high' in quality_level_values
    assert 'medium' in quality_level_values
    assert 'low' in quality_level_values


def test_model_imports():
    """Test all models can be imported"""
    from app.models.db.tables import (
        Source, Author, Article,
        Recommendation, Feedback, ReadingQueue
    )
    # If imports succeed, models are properly defined


def test_base_model():
    """Test base model functionality"""
    from app.models.db.base import Base
    assert Base is not None


def test_create_tables_function():
    """Test create_tables function works"""
    # Drop tables first
    drop_tables()
    # Create tables
    create_tables()
    # Verify tables exist
    inspector = inspect(get_engine())
    tables_found = set(inspector.get_table_names())
    expected_tables = {
        'sources', 'authors', 'articles',
        'recommendations', 'feedbacks', 'reading_queues'
    }
    assert expected_tables.issubset(tables_found), "Not all tables were created"