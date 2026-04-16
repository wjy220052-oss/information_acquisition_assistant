"""
Solidot Source Adapter

Fetches content from Solidot (奇客资讯)
RSS Feed: https://www.solidot.org/index.rss

Content focus:
- 科技新闻
- 开源动态
- AI/人工智能
- 软件资讯
- 安全资讯
"""

import logging
from typing import Optional

from app.models.schemas.source import SourceType
from app.services.sources.rss_base import RSSBaseAdapter

logger = logging.getLogger(__name__)


class SolidotAdapter(RSSBaseAdapter):
    """
    Adapter for Solidot (奇客资讯)

    A Chinese tech news site focusing on:
    - Open source
    - Science & Technology
    - AI/Machine Learning
    - Software & Security

    RSS: https://www.solidot.org/index.rss
    """

    source_name = "solidot"
    source_type = SourceType.RSS
    base_url = "https://www.solidot.org/index.rss"

    def __init__(self, config: Optional[dict] = None):
        """Initialize Solidot adapter"""
        super().__init__(config)

    def _parse_entry(self, entry: dict, feed_info: dict):
        """
        Parse Solidot-specific entry data

        Solidot RSS entries typically have:
        - title: Article title (may include category prefix like "[AI]")
        - link: Article URL
        - description: HTML summary
        - author: Author name
        - pubDate: Publish date
        - category: List of categories

        Args:
            entry: Single entry from parsed feed
            feed_info: Overall feed information

        Returns:
            Parsed SourceItem with Solidot-specific tags
        """
        # Use parent parsing for basic fields
        item = super()._parse_entry(entry, feed_info)

        # Add Solidot-specific metadata
        item.tags.append("科技资讯")

        # Extract category from title (e.g., "[AI] 标题内容")
        title = entry.get('title', '')
        if title.startswith('['):
            # Extract category from brackets
            end_bracket = title.find(']')
            if end_bracket > 0:
                category = title[1:end_bracket].strip()
                if category:
                    item.tags.append(category)
                    # Map common Solidot categories
                    category_mapping = {
                        'AI': '人工智能',
                        '开源': '开源',
                        '软件': '软件',
                        '安全': '安全',
                        '硬件': '硬件',
                        '科学': '科学',
                        '技术': '技术',
                        '互联网': '互联网',
                        '游戏': '游戏',
                        '企业': '企业',
                    }
                    if category in category_mapping:
                        item.tags.append(category_mapping[category])

        # Add feed-level category if available
        feed_category = feed_info.get('category')
        if feed_category and feed_category not in item.tags:
            item.tags.append(feed_category)

        # Clean up tags - remove duplicates and empty strings
        item.tags = list(dict.fromkeys([t.strip() for t in item.tags if t and t.strip()]))

        return item
