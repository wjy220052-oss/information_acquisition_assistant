"""
Application configuration management

Configuration is loaded from environment variables with fallback to defaults.
Use .env file for local development.
"""

import os
from pathlib import Path
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables"""

    # Application
    APP_NAME: str = "Information Acquisition Assistant"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = False

    # Server
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    # Database (PostgreSQL)
    DATABASE_URL: Optional[str] = None
    DATABASE_HOST: str = "localhost"
    DATABASE_PORT: int = 5432
    DATABASE_USER: str = "postgres"
    DATABASE_PASSWORD: Optional[str] = None
    DATABASE_NAME: str = "reading_agent"

    # Redis
    REDIS_URL: Optional[str] = None
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0

    # Email
    SMTP_HOST: Optional[str] = None
    SMTP_PORT: int = 587
    SMTP_USER: Optional[str] = None
    SMTP_PASSWORD: Optional[str] = None
    SMTP_USE_SSL: bool = False  # True for SSL (port 465), False for STARTTLS (port 587)
    EMAIL_FROM: Optional[str] = None
    EMAIL_TO: Optional[str] = None

    # LLM / Embedding Services
    LLM_API_KEY: Optional[str] = None
    LLM_BASE_URL: Optional[str] = None
    EMBEDDING_API_KEY: Optional[str] = None
    EMBEDDING_BASE_URL: Optional[str] = None

    # RSS Sources
    RSSHUB_URL: str = "https://rsshub.app"

    # Recommendation
    DEFAULT_RECOMMENDATION_LIMIT: int = 10
    EXPLORATION_RATIO: float = 0.3

    # Reading Queue
    READING_QUEUE_DECAY_DAYS: list = [2, 5, 7]
    READING_QUEUE_MAX_DAYS: int = 14

    # Scheduler (APScheduler)
    SCHEDULER_ENABLED: bool = True
    SCHEDULER_TIMEZONE: str = "Asia/Shanghai"
    SCHEDULER_FETCH_TIME: str = "06:00"  # HH:MM format
    SCHEDULER_RECOMMEND_TIME: str = "06:30"  # HH:MM format
    SCHEDULER_EMAIL_TIME: str = "07:00"  # HH:MM format

    # Email Dashboard
    DASHBOARD_URL: str = "http://localhost:8000"

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": True,
        "extra": "forbid"
    }

    def get_database_url(self) -> str:
        """
        Construct database URL from individual components

        Returns:
            Database connection URL
        """
        if self.DATABASE_URL:
            return self.DATABASE_URL

        # Handle password - if None, don't include it in the URL
        if self.DATABASE_PASSWORD:
            return (
                f"postgresql://{self.DATABASE_USER}:{self.DATABASE_PASSWORD}"
                f"@{self.DATABASE_HOST}:{self.DATABASE_PORT}/{self.DATABASE_NAME}"
            )
        else:
            return (
                f"postgresql://{self.DATABASE_USER}"
                f"@{self.DATABASE_HOST}:{self.DATABASE_PORT}/{self.DATABASE_NAME}"
            )

    def get_redis_url(self) -> str:
        """
        Construct Redis URL from individual components

        Returns:
            Redis connection URL
        """
        if self.REDIS_URL:
            return self.REDIS_URL

        return f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"


# Global settings instance
_settings: Optional[Settings] = None


def get_settings() -> Settings:
    """
    Get global settings instance (singleton pattern)

    Returns:
        Application settings
    """
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
