"""
少数派 Source Adapter

Fetches content from SSPAI (https://sspai.com/)
"""

import logging
from datetime import datetime, timezone
from typing import List, Optional, Any
from urllib.parse import urljoin

from app.models.schemas.source import SourceType, SourceItem, FetchResult
from app.services.sources.base import SourceAdapter

logger = logging.getLogger(__name__)


class SspaiAdapter(SourceAdapter):
    """
    SSPAI Adapter for fetching articles from SSPAI
    """

    source_name = "sspai"
    source_type = SourceType.API
    base_url = "https://sspai.com/"

    def __init__(self, config: Optional[dict] = None):
        """Initialize SSPAI adapter"""
        super().__init__(config)
        self.page = config.get("page", 1) if config else 1
        self.per_page = config.get("per_page", 10) if config else 10

    def fetch_items(self, limit: int = 10) -> FetchResult:
        """
        Fetch articles from SSPAI

        Args:
            limit: Maximum number of articles to fetch

        Returns:
            FetchResult containing the articles
        """
        import requests

        try:
            # API endpoint
            url = urljoin(self.base_url, "/api/v1/article/index/page/get")
            params = {
                "page": self.page,
                "per_page": min(limit, self.per_page)  # Respect both limits
            }

            logger.info(f"Fetching articles from SSPAI: {url}, params={params}")

            response = requests.get(url, params=params, timeout=30)
            response.raise_for_status()

            raw_data = response.json()

            # Check API response
            if raw_data.get("error") != 0:
                error_msg = raw_data.get("msg", "Unknown error")
                return FetchResult(
                    source_name=self.source_name,
                    success=False,
                    errors=[f"API error: {error_msg}"],
                    started_at=datetime.now(timezone.utc),
                )

            articles = raw_data.get("data", [])[:limit]  # Respect limit
            result = FetchResult(
                source_name=self.source_name,
                success=True,
                items_fetched=len(articles),
                items_new=0,  # Will be updated during storage
                items_updated=0,  # Will be updated during storage
                started_at=datetime.now(timezone.utc),
            )

            # Parse articles into SourceItems
            items = []
            for article in articles:
                try:
                    item = self._parse_article(article)
                    items.append(item)
                except Exception as e:
                    logger.error(f"Failed to parse article {article.get('id')}: {e}")
                    result.add_error(f"Article parse error: {e}")
                    continue

            # Store items for testing and downstream processing
            self._last_items = items
            result.items = items
            return result

        except requests.RequestException as e:
            logger.error(f"Failed to fetch from SSPAI: {e}")
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
            logger.exception(f"Unexpected error fetching from SSPAI")
            return FetchResult(
                source_name=self.source_name,
                success=False,
                errors=[f"Unexpected error: {str(e)}"],
                started_at=datetime.now(timezone.utc),
            )

    def fetch_full_content(self, item: SourceItem) -> str:
        """
        Fetch full content for an article

        For MVP, we return summary from the original API response
        since the list API doesn't include full content.

        Args:
            item: SourceItem representing a SSPAI article

        Returns:
            Article content or summary as string
        """
        # For MVP, use summary as content since we don't have full content in list API
        if item.raw_data:
            # Prefer body_extend.body if available
            if "body_extend" in item.raw_data and item.raw_data["body_extend"]:
                body = item.raw_data["body_extend"].get("body", "")
                if body:
                    return body

            # Fall back to summary
            summary = item.raw_data.get("summary", "")
            if summary:
                return summary

        # If no content available, return clear message
        return "No additional content available in list API"

    def _parse_article(self, article_data: dict) -> SourceItem:
        """
        Parse a SSPAI article dict into a SourceItem

        Args:
            article_data: Raw article data from SSPAI API

        Returns:
            Parsed SourceItem
        """
        # Validate required fields
        required_fields = ["id", "title"]
        for field in required_fields:
            if field not in article_data:
                raise ValueError(f"Missing required field: {field}")

        # Convert ID to string
        article_id = str(article_data["id"])

        # Parse time field - try released_time first, then created_time
        publish_time = None
        for time_field in ["released_time", "created_time"]:
            if time_field in article_data and article_data[time_field]:
                try:
                    publish_time = self._parse_sspai_time(article_data[time_field])
                    break
                except (ValueError, TypeError):
                    continue

        # Handle author information
        author_name = None
        author_url = None
        if "author" in article_data and article_data["author"]:
            author = article_data["author"]
            author_name = author.get("nickname")
            if author.get("slug"):
                author_url = self._normalize_url(f"/u/{author['slug']}")

        # Create tags from corner and tags
        tags = []
        if "corner" in article_data and article_data["corner"]:
            corner = article_data["corner"]
            if corner.get("name"):
                tags.append(corner["name"])

        if "tags" in article_data and article_data["tags"]:
            for tag in article_data["tags"]:
                if tag.get("title"):
                    tags.append(tag["title"])

        # Use URL directly or construct from ID
        article_url = article_data.get("url")
        if not article_url:
            article_url = f"/articles/{article_id}"

        return SourceItem(
            source_id=self.source_name,
            source_item_id=article_id,
            title=article_data["title"],
            url=self._normalize_url(article_url),
            summary=article_data.get("summary"),
            author_name=author_name,
            author_url=author_url,
            publish_time=publish_time,
            tags=tags,
            raw_data=article_data,  # Store complete original JSON
        )

    def _parse_sspai_time(self, time_value) -> Optional[datetime]:
        """
        Parse SSPAI time value to timezone-aware datetime

        Args:
            time_value: Time value from SSPAI API (Unix timestamp or other format)

        Returns:
            timezone-aware datetime or None if parsing fails
        """
        if not time_value:
            return None

        # Handle Unix timestamp (integer)
        if isinstance(time_value, int):
            try:
                # SSPAI uses seconds, not milliseconds
                dt = datetime.fromtimestamp(time_value, tz=timezone.utc)
                return dt
            except (ValueError, OSError):
                return None

        # Handle string format
        if isinstance(time_value, str):
            try:
                # Try to parse as Unix timestamp string
                timestamp = int(time_value)
                dt = datetime.fromtimestamp(timestamp, tz=timezone.utc)
                return dt
            except ValueError:
                # Try ISO format if timestamp fails
                try:
                    dt = datetime.fromisoformat(time_value.replace("Z", "+00:00"))
                    if dt.tzinfo is None:
                        dt = dt.replace(tzinfo=timezone.utc)
                    else:
                        dt = dt.astimezone(timezone.utc)
                    return dt
                except ValueError:
                    return None

        return None

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