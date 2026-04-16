"""
Source adapter schemas

Defines data structures for content items, fetch results, and errors.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional, List, Any
from urllib.parse import urlparse


class SourceType(str, Enum):
    """Source type enumeration"""
    RSSHUB = "rsshub"
    API = "api"
    RSS = "rss"
    SCRAPER = "scraper"


@dataclass
class SourceItem:
    """
    Single content item from a source

    Represents raw data fetched from a source before normalization.
    """
    # Source identifier
    source_id: str
    source_item_id: str  # Unique ID within the source

    # Basic content
    title: str
    url: str
    summary: Optional[str] = None

    # Author information
    author_name: Optional[str] = None
    author_url: Optional[str] = None

    # Metadata
    publish_time: Optional[datetime] = None
    tags: List[str] = field(default_factory=list)

    # Raw data for later processing
    raw_data: Optional[dict] = None

    def __post_init__(self):
        """Validate URL after initialization"""
        if self.url:
            try:
                parsed = urlparse(self.url)
                if not parsed.scheme or not parsed.netloc:
                    raise ValueError(f"Invalid URL: {self.url}")
            except Exception as e:
                raise ValueError(f"Invalid URL format: {e}")

    @property
    def normalized_url(self) -> str:
        """Get normalized URL (simplified version)"""
        # Basic normalization - remove fragments, lowercase scheme/netloc
        parsed = urlparse(self.url)
        normalized = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
        if parsed.query:
            normalized += f"?{parsed.query}"
        return normalized.lower()


@dataclass
class FetchResult:
    """
    Result of a fetch operation

    Contains statistics and metadata about the fetch process.
    """
    source_name: str
    success: bool
    items_fetched: int = 0
    items_new: int = 0
    items_updated: int = 0
    items_failed: int = 0
    errors: List[str] = field(default_factory=list)
    duration_seconds: float = 0.0
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    items: Optional[List[SourceItem]] = None  # Fetched items for downstream processing

    def add_error(self, error: str):
        """Add an error to the result"""
        self.errors.append(error)
        self.items_failed += 1


@dataclass
class FetchError:
    """
    Detailed error information for a failed fetch
    """
    source_name: str
    error_type: str
    message: str
    item_id: Optional[str] = None
    exception: Optional[Exception] = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict:
        """Convert to dictionary for logging/storage"""
        return {
            "source_name": self.source_name,
            "error_type": self.error_type,
            "message": self.message,
            "item_id": self.item_id,
            "exception": str(self.exception) if self.exception else None,
            "timestamp": self.timestamp.isoformat(),
        }
