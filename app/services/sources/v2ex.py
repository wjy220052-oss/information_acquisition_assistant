"""
V2EX Source Adapter

Fetches content from V2EX (https://www.v2ex.com/)
"""

import logging
from datetime import datetime, timezone
from typing import List, Optional, Any
from urllib.parse import urljoin

from app.models.schemas.source import SourceType, SourceItem, FetchResult
from app.services.sources.base import SourceAdapter

logger = logging.getLogger(__name__)


class V2EXAdapter(SourceAdapter):
    """
    V2EX Adapter for fetching topics from V2EX community
    """

    source_name = "v2ex"
    source_type = SourceType.API
    base_url = "https://www.v2ex.com/"

    def __init__(self, config: Optional[dict] = None):
        """Initialize V2EX adapter"""
        super().__init__(config)
        self.mode = config.get("mode", "latest") if config else "latest"
        self._last_items = []  # For testing

        if self.mode not in ["latest", "hot"]:
            raise ValueError("Mode must be either 'latest' or 'hot'")

    def fetch_items(self, limit: int = 10) -> FetchResult:
        """
        Fetch topics from V2EX

        Args:
            limit: Maximum number of topics to fetch

        Returns:
            FetchResult containing the topics
        """
        import requests

        try:
            # Determine API endpoint based on mode
            endpoint = "/api/topics/hot.json" if self.mode == "hot" else "/api/topics/latest.json"
            url = urljoin(self.base_url, endpoint)

            logger.info(f"Fetching {self.mode} topics from {url}, limit={limit}")

            response = requests.get(url, timeout=30)
            response.raise_for_status()

            raw_topics = response.json()
            topics = raw_topics[:limit]  # Respect limit

            result = FetchResult(
                source_name=self.source_name,
                success=True,
                items_fetched=len(topics),
                items_new=0,  # Will be updated during storage
                items_updated=0,  # Will be updated during storage
                started_at=datetime.now(timezone.utc),
            )

            # Parse topics into SourceItems
            items = []
            for topic in topics:
                try:
                    item = self._parse_topic(topic)
                    items.append(item)
                except Exception as e:
                    logger.error(f"Failed to parse topic {topic.get('id')}: {e}")
                    result.add_error(f"Topic parse error: {e}")
                    continue

            # Store items for testing and downstream processing
            self._last_items = items
            result.items = items
            return result

        except requests.RequestException as e:
            logger.error(f"Failed to fetch from V2EX: {e}")
            error_msg = f"Network error: {str(e)}"
            if e.response:
                error_msg += f" (Status: {e.response.status_code})"

            return FetchResult(
                source_name=self.source_name,
                success=False,
                errors=[error_msg],
                started_at=datetime.now(timezone.utc),
            )
        except Exception as e:
            logger.exception(f"Unexpected error fetching from V2EX")
            return FetchResult(
                source_name=self.source_name,
                success=False,
                errors=[f"Unexpected error: {str(e)}"],
                started_at=datetime.now(timezone.utc),
            )

    def fetch_full_content(self, item: SourceItem) -> str:
        """
        Fetch full content for a topic (currently uses API content)

        Args:
            item: SourceItem representing a V2EX topic

        Returns:
            Topic content as string
        """
        # For MVP, we return the content from the original API response
        # stored in raw_data. This avoids making additional HTTP requests.
        if item.raw_data and "content" in item.raw_data:
            return item.raw_data["content"]

        # Fallback - this shouldn't happen if items are properly parsed
        logger.warning(f"No content found for topic {item.source_item_id}")
        return ""

    def _parse_topic(self, topic_data: dict) -> SourceItem:
        """
        Parse a V2EX topic dict into a SourceItem

        Args:
            topic_data: Raw topic data from V2EX API

        Returns:
            Parsed SourceItem
        """
        # Validate required fields
        required_fields = ["id", "title", "url", "created", "member"]
        for field in required_fields:
            if field not in topic_data:
                raise ValueError(f"Missing required field: {field}")

        # Convert created time to timezone-aware datetime
        created_time = self._parse_v2ex_time(topic_data["created"])

        # Handle author information
        member = topic_data["member"]
        author_name = member.get("username") if member else None
        author_url = member.get("url") if member else None

        # Normalize author URL
        if author_url:
            author_url = self._normalize_url(author_url)

        # Create tags from node
        tags = []
        if "node" in topic_data and topic_data["node"]:
            tags.append(topic_data["node"]["title"])

        return SourceItem(
            source_id=self.source_name,
            source_item_id=str(topic_data["id"]),  # Convert to string
            title=topic_data["title"],
            url=self._normalize_url(topic_data["url"]),
            summary=topic_data.get("content", "")[:200] + "..." if topic_data.get("content") else None,
            author_name=author_name,
            author_url=author_url,
            publish_time=created_time,
            tags=tags,
            raw_data=topic_data,  # Store complete original JSON
        )

    def _parse_v2ex_time(self, v2ex_time) -> datetime:
        """
        Parse V2EX time to timezone-aware datetime

        Args:
            v2ex_time: Time string or timestamp from V2EX API

        Returns:
            timezone-aware datetime
        """
        # Handle both string and timestamp formats
        if isinstance(v2ex_time, (int, float)):
            # Unix timestamp
            dt = datetime.fromtimestamp(v2ex_time, tz=timezone.utc)
        else:
            # V2EX time format: ISO 8601 with timezone
            dt = datetime.fromisoformat(str(v2ex_time).replace("Z", "+00:00"))

            # Ensure timezone-aware
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            else:
                # Convert to UTC if timezone is not UTC
                dt = dt.astimezone(timezone.utc)

        return dt

    def _normalize_url(self, url: str) -> str:
        """
        Normalize URL to ensure it's a complete, valid URL

        Args:
            url: URL string, may be relative or incomplete

        Returns:
            Complete, normalized URL
        """
        if not url:
            return None

        # Ensure it starts with http/https
        if not url.startswith(("http://", "https://")):
            # If it starts with /, it's relative to base_url
            if url.startswith("/"):
                url = urljoin(self.base_url, url)
            else:
                # Otherwise, assume it's a path relative to base_url
                url = urljoin(self.base_url, f"/{url.lstrip('/')}")

        return url