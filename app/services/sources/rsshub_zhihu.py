"""
RSSHub Zhihu Source Adapter

Fetches content from Zhihu topics, columns, and questions via RSSHub.
"""

import logging
from typing import Optional
from urllib.parse import urljoin

from app.models.schemas.source import SourceType
from app.services.sources.rss_base import RSSBaseAdapter

logger = logging.getLogger(__name__)


class RSSHubZhihuAdapter(RSSBaseAdapter):
    """
    RSSHub adapter for Zhihu content

    Supports:
    - Topics (知乎话题)
    - Columns (知乎专栏)
    - Questions (知乎问答)
    """

    source_name = "rsshub_zhihu"
    source_type = SourceType.RSSHUB
    base_url = "https://rsshub.app/zhihu"

    def __init__(self, config: Optional[dict] = None):
        """Initialize Zhihu adapter"""
        super().__init__(config)

    def get_topic_feed_url(self, topic_id: str) -> str:
        """
        Get RSS feed URL for a Zhihu topic

        Args:
            topic_id: Zhihu topic ID or slug

        Returns:
            RSS feed URL
        """
        return urljoin(self.base_url + "/", f"topic/{topic_id}")

    def get_column_feed_url(self, column_id: str) -> str:
        """
        Get RSS feed URL for a Zhihu column

        Args:
            column_id: Zhihu column ID or slug

        Returns:
            RSS feed URL
        """
        return urljoin(self.base_url + "/", f"column/{column_id}")

    def get_question_feed_url(self, question_id: str) -> str:
        """
        Get RSS feed URL for a Zhihu question

        Args:
            question_id: Zhihu question ID

        Returns:
            RSS feed URL
        """
        return urljoin(self.base_url + "/", f"question/{question_id}")

    def fetch_items(self, limit: int = 10) -> "FetchResult":
        """
        Fetch items from Zhihu feed

        This method can be overridden to handle multiple feeds
        or dynamic feed selection.

        For now, it uses the base_url as configured.
        """
        return super().fetch_items(limit)

    def _parse_entry(self, entry: dict, feed_info: dict):
        """
        Parse Zhihu-specific entry data

        Args:
            entry: Single entry from parsed feed
            feed_info: Overall feed information

        Returns:
            Parsed SourceItem
        """
        # Use parent parsing for basic fields
        item = super()._parse_entry(entry, feed_info)

        # Add Zhihu-specific metadata if available
        if feed_info.get('title'):
            # The feed title often contains the source type
            item.raw_data['feed_title'] = feed_info['title']

        # Zhihu entries often have author info in the title
        # Priority: entry.author > feed.author
        if not item.author_name:
            if feed_info.get('author'):
                item.author_name = feed_info['author']

        # Add Zhihu-specific tags based on feed title
        feed_title = feed_info.get('title', '')
        if '专栏' in feed_title:
            item.tags.append('专栏')
        elif '话题' in feed_title:
            item.tags.append('话题')
        elif '问答' in feed_title:
            item.tags.append('问答')

        return item