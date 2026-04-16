"""
RSS/Atom/RSSHUB Base Adapter

Common functionality for RSS, Atom, and RSSHub-based sources.
"""

import logging
from datetime import datetime, timezone
from typing import List, Optional, Any, Dict, Union
import xml.etree.ElementTree as ET
from urllib.parse import urljoin, urlparse
import feedparser
import requests
from dateutil import parser as date_parser

from app.models.schemas.source import (
    SourceType,
    SourceItem,
    FetchResult,
    FetchError,
)
from app.services.sources.base import SourceAdapter

logger = logging.getLogger(__name__)


class RSSBaseAdapter(SourceAdapter):
    """
    Base adapter for RSS/Atom/RSSHUB sources

    Provides common functionality for parsing RSS/Atom feeds and
    implementing SourceAdapter interface.
    """

    def __init__(self, config: Optional[dict] = None):
        """Initialize RSS base adapter"""
        super().__init__(config)
        # Optional: feedparser can follow redirects with a timeout
        self.timeout = self.config.get('timeout', 30)
        # Optional: User-Agent header for some feeds that block default agents
        self.user_agent = self.config.get('user_agent',
            'Mozilla/5.0 (compatible; InformationAcquisitionAssistant/1.0; +https://github.com/user/repo)')

    def fetch_items(self, limit: int = 10) -> FetchResult:
        """
        Fetch items from RSS/Atom feed

        Args:
            limit: Maximum number of items to fetch

        Returns:
            FetchResult containing parsed items
        """
        result = FetchResult(
            source_name=self.source_name,
            success=False,
            started_at=datetime.now(timezone.utc),
        )

        try:
            # Fetch the feed
            response = self._fetch_feed()
            if not response:
                result.add_error("Failed to fetch feed")
                return result

            # Parse the feed
            parsed_feed = self._parse_feed(response.content)
            if not parsed_feed:
                result.add_error("Failed to parse feed")
                return result

            # Process entries
            entries = self._extract_entries(parsed_feed)
            result.items_fetched = min(len(entries), limit)

            # Parse entries to SourceItems
            parsed_items = []
            for i, entry in enumerate(entries[:limit]):
                try:
                    item = self._parse_entry(entry, parsed_feed.feed)
                    parsed_items.append(item)
                except Exception as e:
                    logger.warning(f"Failed to parse entry {i}: {e}")
                    result.add_error(f"Entry {i} parsing failed: {str(e)}")
                    continue

            result.items = parsed_items
            result.items_new = len(parsed_items)  # All are "new" for now
            result.success = True
            result.finished_at = datetime.now(timezone.utc)
            result.duration_seconds = (result.finished_at - result.started_at).total_seconds()

        except Exception as e:
            error_msg = f"Fetch failed: {str(e)}"
            result.add_error(error_msg)
            logger.error(error_msg, exc_info=True)

        return result

    def _fetch_feed(self) -> Optional[requests.Response]:
        """Fetch the feed content from URL"""
        headers = {'User-Agent': self.user_agent}

        try:
            response = requests.get(
                self.base_url,
                headers=headers,
                timeout=self.timeout,
                allow_redirects=True
            )
            response.raise_for_status()
            return response
        except requests.RequestException as e:
            logger.error(f"Failed to fetch feed from {self.base_url}: {e}")
            return None

    def _parse_feed(self, content: bytes) -> Optional[feedparser.FeedParserDict]:
        """Parse RSS/Atom feed content"""
        try:
            # feedparser can handle both bytes and strings
            parsed = feedparser.parse(content)

            # Check if feed is valid
            if parsed.bozo:
                logger.warning(f"Feed has parsing issues: {parsed.bozo_exception}")

            return parsed
        except Exception as e:
            logger.error(f"Failed to parse feed: {e}")
            return None

    def _extract_entries(self, parsed_feed: feedparser.FeedParserDict) -> List[dict]:
        """Extract entries from parsed feed"""
        # For RSS feeds, entries are in 'entries'
        # For Atom feeds, same structure
        # Handle both dict-style and object-style access (for testing with Mock)
        entries = []
        # First try attribute access (for real feedparser objects and Mocks with entries set)
        if hasattr(parsed_feed, 'entries'):
            entries = parsed_feed.entries
            # If entries is a Mock (not set), fall back to get method
            if hasattr(entries, '__class__') and entries.__class__.__name__ == 'Mock':
                if hasattr(parsed_feed, 'get'):
                    entries = parsed_feed.get('entries', []) or []
        elif hasattr(parsed_feed, 'get'):
            entries = parsed_feed.get('entries', []) or []
        # Ensure we return a list (not a Mock or other type)
        if not isinstance(entries, list):
            entries = list(entries) if hasattr(entries, '__iter__') else []
        return entries

    def _parse_entry(self, entry: dict, feed_info: dict) -> SourceItem:
        """
        Parse a single feed entry into SourceItem

        Args:
            entry: Single entry from parsed feed
            feed_info: Overall feed information

        Returns:
            Parsed SourceItem
        """
        # Extract required fields with fallbacks
        title = self._extract_text(entry, 'title')
        url = self._extract_url(entry, 'link')

        # Create unique ID within source
        source_item_id = self._extract_id(entry, url)

        # Extract optional fields with None defaults
        summary = self._extract_text(entry, 'summary')
        author_name = self._extract_author(entry)

        # Extract and parse publish time
        publish_time = self._extract_publish_time(entry)

        # Extract tags
        tags = self._extract_tags(entry)

        # Create raw data preserve
        raw_data = {
            'entry': entry,
            'feed_info': feed_info,
        }

        return SourceItem(
            source_id=self.source_name,
            source_item_id=str(source_item_id),  # Ensure string
            title=title,
            url=url,
            summary=summary,
            author_name=author_name,
            publish_time=publish_time,
            tags=tags,
            raw_data=raw_data,
        )

    def _extract_text(self, entry: dict, field: str) -> Optional[str]:
        """Extract text from field, handling different formats"""
        value = entry.get(field)
        if value is None:
            return None

        if isinstance(value, str):
            return value.strip()
        elif isinstance(value, dict):
            # Handle {'value': 'text', 'type': 'html'} format
            return value.get('value', '').strip()
        elif hasattr(value, 'string'):
            # Handle some XML parsing results
            return value.string.strip() if value.string else None

        return str(value).strip()

    def _extract_url(self, entry: dict, field: str) -> str:
        """Extract URL and validate it"""
        url = self._extract_text(entry, field)
        if not url:
            raise ValueError("URL field is required")

        # Ensure it's a full URL
        if not url.startswith(('http://', 'https://')):
            # Relative URL - resolve against base URL
            url = urljoin(self.base_url, url)

        return url

    def _extract_id(self, entry: dict, fallback_url: str) -> str:
        """Extract or create unique ID for the item"""
        # Try various ID fields
        id_fields = ['id', 'guid', 'post-id']
        for field in id_fields:
            if field in entry and entry[field]:
                return str(entry[field])

        # Fallback to URL hash if no ID found
        import hashlib
        return hashlib.md5(fallback_url.encode()).hexdigest()

    def _extract_author(self, entry: dict) -> Optional[str]:
        """Extract author information"""
        # Try various author fields
        author_fields = ['author', 'creator']
        for field in author_fields:
            if field in entry and entry[field]:
                return str(entry[field])

        # Try author dict
        if 'author_detail' in entry and entry['author_detail']:
            return entry['author_detail'].get('name')

        return None

    def _extract_publish_time(self, entry: dict) -> Optional[datetime]:
        """Extract and normalize publish time"""
        # Try various time fields
        time_fields = ['published', 'pubDate', 'updated', 'date']

        for field in time_fields:
            if field in entry and entry[field]:
                try:
                    # Use dateutil parser which is flexible with formats
                    dt = date_parser.parse(str(entry[field]))

                    # If no timezone info, assume UTC
                    if dt.tzinfo is None:
                        dt = dt.replace(tzinfo=timezone.utc)

                    return dt
                except (ValueError, TypeError) as e:
                    logger.debug(f"Failed to parse time from {field}: {e}")
                    continue

        return None

    def _extract_tags(self, entry: dict) -> List[str]:
        """Extract tags/categories"""
        tags = []

        # Try tags field
        if 'tags' in entry and entry['tags']:
            for tag in entry['tags']:
                if isinstance(tag, str):
                    tags.append(tag)
                elif isinstance(tag, dict):
                    tags.append(tag.get('term', ''))

        # Try categories field
        if 'category' in entry and entry['category']:
            categories = entry['category']
            if not isinstance(categories, list):
                categories = [categories]
            for cat in categories:
                if isinstance(cat, str):
                    tags.append(cat)
                elif isinstance(cat, dict):
                    tags.append(cat.get('term', ''))

        # Clean and filter empty tags
        return [tag.strip() for tag in tags if tag and tag.strip()]

    def fetch_full_content(self, item: SourceItem) -> str:
        """
        Fetch full content for an item

        First version: Return what we already have from the feed.
        Later versions can be enhanced to fetch full pages if needed.
        """
        if item.raw_data and 'entry' in item.raw_data:
            # Use the 'content' field if available
            if 'content' in item.raw_data['entry']:
                content = item.raw_data['entry']['content']
                if isinstance(content, str):
                    return content
                elif isinstance(content, list) and content:
                    # Handle list of content dicts
                    for c in content:
                        if isinstance(c, dict) and 'value' in c:
                            return c['value']
                    # Fallback to first content item
                    return str(content[0])

            # Fall back to summary if no content
            if item.summary:
                return item.summary

        # No additional content available
        return "[Full content not available in feed - implementation pending]"