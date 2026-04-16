"""
阮一峰 weekly Source Adapter

Fetches content from 阮一峰的科技爱好者周刊
RSS Feed: https://github.com/ruanyf/weekly
"""

import logging
from typing import Optional

from app.models.schemas.source import SourceType
from app.services.sources.rss_base import RSSBaseAdapter

logger = logging.getLogger(__name__)


class RuanyfWeeklyAdapter(RSSBaseAdapter):
    """
    Adapter for 阮一峰的科技爱好者周刊

    每周五更新，内容涵盖：
    - 科技新闻与评论
    - 技术文章推荐
    - 工具与资源分享
    - 观点与思考

    RSS: https://feeds.feedburner.com/ruanyifeng
    """

    source_name = "ruanyf_weekly"
    source_type = SourceType.RSS
    base_url = "https://feeds.feedburner.com/ruanyifeng"

    def __init__(self, config: Optional[dict] = None):
        """Initialize Ruanyf weekly adapter"""
        super().__init__(config)

    def _parse_entry(self, entry: dict, feed_info: dict):
        """
        Parse weekly entry with enhanced metadata

        Args:
            entry: Single entry from parsed feed
            feed_info: Overall feed information

        Returns:
            Parsed SourceItem with weekly-specific tags
        """
        # Use parent parsing for basic fields
        item = super()._parse_entry(entry, feed_info)

        # Add weekly-specific tags
        item.tags.append("科技周刊")
        item.tags.append("阮一峰")

        # Extract issue number from title if present (e.g., "科技爱好者周刊（第 300 期）")
        title = entry.get('title', '')
        if '第' in title and '期' in title:
            item.tags.append("周刊")

        # Add category based on content analysis
        summary = item.summary or ''
        category_keywords = {
            '工具': ['工具', '软件', 'app', '推荐'],
            '教程': ['教程', '入门', '指南', 'how to'],
            '观点': ['观点', '思考', '评论', '看法'],
            '新闻': ['新闻', '发布', '更新', 'announcing'],
        }

        for category, keywords in category_keywords.items():
            if any(kw in summary.lower() or kw in title.lower() for kw in keywords):
                item.tags.append(category)
                break

        return item
