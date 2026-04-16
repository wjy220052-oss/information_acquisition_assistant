"""
Tests for configuration module
"""

import os
from typing import Generator

import pytest
from pydantic import ValidationError

from app.core.config import Settings, get_settings


@pytest.fixture(autouse=True)
def reset_settings() -> Generator[None, None, None]:
    """Reset global settings before each test"""
    import app.core.config
    app.core.config._settings = None
    yield
    app.core.config._settings = None


def test_settings_defaults() -> None:
    """Test that settings have proper defaults"""
    settings = Settings()

    assert settings.APP_NAME == "Information Acquisition Assistant"
    assert settings.APP_VERSION == "0.1.0"
    assert settings.DEBUG is False
    assert settings.HOST == "0.0.0.0"
    assert settings.PORT == 8000


def test_settings_from_env() -> None:
    """Test loading settings from environment variables"""
    os.environ["DEBUG"] = "true"
    os.environ["PORT"] = "9000"

    settings = Settings()

    assert settings.DEBUG is True
    assert settings.PORT == 9000

    # Cleanup
    del os.environ["DEBUG"]
    del os.environ["PORT"]


def test_get_database_url() -> None:
    """Test database URL construction"""
    settings = Settings(
        DATABASE_URL=None,  # Explicitly set to None
        DATABASE_HOST="dbhost",
        DATABASE_PORT=5433,
        DATABASE_USER="testuser",
        DATABASE_PASSWORD="testpass",
        DATABASE_NAME="testdb"
    )

    url = settings.get_database_url()
    assert url == "postgresql://testuser:testpass@dbhost:5433/testdb"


def test_get_database_url_with_connection_string() -> None:
    """Test that explicit DATABASE_URL takes precedence"""
    settings = Settings(
        DATABASE_URL="postgresql://custom:pass@host:5432/customdb",
        DATABASE_HOST="dbhost"
    )

    url = settings.get_database_url()
    assert url == "postgresql://custom:pass@host:5432/customdb"


def test_get_redis_url() -> None:
    """Test Redis URL construction"""
    settings = Settings(
        REDIS_HOST="redishost",
        REDIS_PORT=6380,
        REDIS_DB=1
    )

    url = settings.get_redis_url()
    assert url == "redis://redishost:6380/1"


def test_get_redis_url_with_connection_string() -> None:
    """Test that explicit REDIS_URL takes precedence"""
    settings = Settings(
        REDIS_URL="redis://custom:6380/1",
        REDIS_HOST="localhost"
    )

    url = settings.get_redis_url()
    assert url == "redis://custom:6380/1"


def test_get_settings_singleton() -> None:
    """Test that get_settings returns singleton instance"""
    settings1 = get_settings()
    settings2 = get_settings()

    assert settings1 is settings2


def test_exploration_ratio_validation() -> None:
    """Test that exploration ratio is properly set"""
    settings = Settings(EXPLORATION_RATIO=0.3)

    assert settings.EXPLORATION_RATIO == 0.3


def test_recommendation_limit_validation() -> None:
    """Test that recommendation limit is properly set"""
    settings = Settings(DEFAULT_RECOMMENDATION_LIMIT=10)

    assert settings.DEFAULT_RECOMMENDATION_LIMIT == 10
