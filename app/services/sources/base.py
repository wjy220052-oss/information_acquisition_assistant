"""
Source Adapter Base Class

Provides a unified interface for fetching content from various sources.
All source adapters must inherit from this base class.
"""

import logging
from abc import ABC, abstractmethod
from typing import List, Optional, Any
from datetime import datetime

from app.models.schemas.source import (
    SourceType,
    SourceItem,
    FetchResult,
    FetchError,
)

logger = logging.getLogger(__name__)


class SourceAdapter(ABC):
    """
    Abstract base class for content source adapters

    Each source (V2EX, 少数派, RSSHub, etc.) should implement this interface.
    """

    # Subclasses must define these metadata attributes
    source_name: str  # e.g., "v2ex", "sspai"
    source_type: SourceType  # e.g., SourceType.API, SourceType.RSSHUB
    base_url: str

    def __init__(self, config: Optional[dict] = None):
        """
        Initialize the adapter with optional configuration

        Args:
            config: Dictionary containing adapter-specific configuration
        """
        self.config = config or {}
        self._validate_metadata()

    def _validate_metadata(self):
        """Validate that required metadata is defined"""
        if not hasattr(self, 'source_name') or not self.source_name:
            raise ValueError(f"{self.__class__.__name__} must define source_name")
        if not hasattr(self, 'source_type'):
            raise ValueError(f"{self.__class__.__name__} must define source_type")
        if not hasattr(self, 'base_url') or not self.base_url:
            raise ValueError(f"{self.__class__.__name__} must define base_url")

    @abstractmethod
    def fetch_items(self, limit: int = 10) -> FetchResult:
        """
        Fetch a list of content items from the source

        Args:
            limit: Maximum number of items to fetch

        Returns:
            FetchResult containing the items and metadata
        """
        pass

    @abstractmethod
    def fetch_full_content(self, item: SourceItem) -> str:
        """
        Fetch the full content of a specific item

        Args:
            item: The SourceItem to fetch full content for

        Returns:
            The full content as a string
        """
        pass

    def parse_item(self, raw_data: Any) -> SourceItem:
        """
        Parse raw data into a SourceItem

        This method can be overridden by subclasses that need custom parsing.
        Default implementation assumes raw_data is already a dict with required fields.

        Args:
            raw_data: Raw data from the source (format depends on source type)

        Returns:
            Parsed SourceItem

        Raises:
            ValueError: If required fields are missing
        """
        if not isinstance(raw_data, dict):
            raise ValueError(f"Expected dict, got {type(raw_data)}")

        required_fields = ['source_id', 'source_item_id', 'title', 'url']
        for field in required_fields:
            if field not in raw_data:
                raise ValueError(f"Missing required field: {field}")

        return SourceItem(
            source_id=raw_data['source_id'],
            source_item_id=raw_data['source_item_id'],
            title=raw_data['title'],
            url=raw_data['url'],
            summary=raw_data.get('summary'),
            author_name=raw_data.get('author_name'),
            author_url=raw_data.get('author_url'),
            publish_time=raw_data.get('publish_time'),
            tags=raw_data.get('tags', []),
            raw_data=raw_data.get('raw_data'),
        )

    def handle_error(self, error: Exception, item_id: Optional[str] = None) -> FetchError:
        """
        Handle and format an error

        Args:
            error: The exception that occurred
            item_id: Optional item ID for context

        Returns:
            Formatted FetchError
        """
        return FetchError(
            source_name=self.source_name,
            error_type=type(error).__name__,
            message=str(error),
            item_id=item_id,
            exception=error,
        )

    def log_error(self, error: FetchError):
        """Log a FetchError"""
        logger.error(
            f"Source {error.source_name} error: {error.error_type} - {error.message}"
        )
        if error.item_id:
            logger.debug(f"  Item ID: {error.item_id}")
