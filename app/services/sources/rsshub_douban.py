"""
RSSHub Douban Source Adapter

Fetches content from Douban books, movies, music, and reviews via RSSHub.
"""

import logging
from typing import Optional
from urllib.parse import urljoin

from app.models.schemas.source import SourceType
from app.services.sources.rss_base import RSSBaseAdapter

logger = logging.getLogger(__name__)


class RSSHubDoubanAdapter(RSSBaseAdapter):
    """
    RSSHub adapter for Douban content

    Supports:
    - Books (豆瓣读书)
    - Movies (豆瓣电影)
    - Music (豆瓣音乐)
    - Reviews (豆瓣影评/书评)
    """

    source_name = "rsshub_douban"
    source_type = SourceType.RSSHUB
    base_url = "https://rsshub.app/douban"

    def __init__(self, config: Optional[dict] = None):
        """Initialize Douban adapter"""
        super().__init__(config)

    def get_book_reviews_feed_url(self, book_id: Optional[str] = None) -> str:
        """
        Get RSS feed URL for Douban book reviews

        Args:
            book_id: Specific book ID (optional)

        Returns:
            RSS feed URL
        """
        if book_id:
            return urljoin(self.base_url + "/", f"book/reviews/{book_id}")
        return urljoin(self.base_url + "/", "book/reviews")

    def get_movie_reviews_feed_url(self, movie_id: Optional[str] = None) -> str:
        """
        Get RSS feed URL for Douban movie reviews

        Args:
            movie_id: Specific movie ID (optional)

        Returns:
            RSS feed URL
        """
        if movie_id:
            return urljoin(self.base_url + "/", f"movie/reviews/{movie_id}")
        return urljoin(self.base_url + "/", "movie/reviews")

    def get_music_reviews_feed_url(self) -> str:
        """
        Get RSS feed URL for Douban music reviews

        Returns:
            RSS feed URL
        """
        return urljoin(self.base_url + "/", "music/reviews")

    def fetch_items(self, limit: int = 10) -> "FetchResult":
        """
        Fetch items from Douban feed

        This method can be overridden to handle multiple feeds
        or dynamic feed selection.

        For now, it uses the base_url as configured.
        """
        return super().fetch_items(limit)

    def _parse_entry(self, entry: dict, feed_info: dict):
        """
        Parse Douban-specific entry data

        Args:
            entry: Single entry from parsed feed
            feed_info: Overall feed information

        Returns:
            Parsed SourceItem
        """
        # Use parent parsing for basic fields
        item = super()._parse_entry(entry, feed_info)

        # Add Douban-specific metadata if available
        if feed_info.get('title'):
            item.raw_data['feed_title'] = feed_info['title']

        # Priority for author: entry level > feed level
        # First check entry-level author details
        if entry.get('author_detail') and entry['author_detail'].get('name'):
            item.author_name = entry['author_detail']['name']
            if 'link' in entry['author_detail']:
                item.author_url = entry['author_detail']['link']
        elif entry.get('author'):
            item.author_name = entry['author']
        # Fallback to feed-level author info
        elif feed_info.get('author_detail'):
            author_detail = feed_info['author_detail']
            if 'name' in author_detail:
                item.author_name = author_detail['name']
            if 'link' in author_detail:
                item.author_url = author_detail['link']
        elif feed_info.get('author'):
            item.author_name = feed_info['author']

        # Add Douban-specific tags based on feed title
        feed_title = feed_info.get('title', '').lower()
        if '读书' in feed_title or 'book' in feed_title:
            item.tags.extend(['豆瓣读书', '书评'])
        elif '电影' in feed_title or 'movie' in feed_title:
            item.tags.extend(['豆瓣电影', '影评'])
        elif '音乐' in feed_title or 'music' in feed_title:
            item.tags.extend(['豆瓣音乐', '乐评'])

        # Extract rating if present in title or summary
        rating = self._extract_rating(entry.get('title', ''), entry.get('summary', ''))
        if rating:
            item.raw_data['rating'] = rating

        return item

    def _extract_rating(self, title: str, summary: str) -> Optional[str]:
        """
        Extract rating information from title or summary

        Args:
            title: Entry title
            summary: Entry summary

        Returns:
            Rating string if found (e.g., "8.5", "五星推荐")
        """
        text = f"{title} {summary}".lower()

        # Look for numeric ratings
        import re
        rating_match = re.search(r'(\d+\.?\d*)\s*分', text)
        if rating_match:
            return f"{rating_match.group(1)}分"

        # Look for star ratings
        star_patterns = [
            (r'(\d+)\s*星', r'\1星'),
            (r'(\d+)\s*颗星', r'\1星'),
            (r'五星', '5星'),
        ]
        for pattern, replacement in star_patterns:
            star_match = re.search(pattern, text)
            if star_match:
                if pattern == r'五星':
                    return '5星'
                return re.sub(pattern, replacement, star_match.group(0))

        # Look for recommendation levels
        if '推荐' in text:
            if '强烈' in text:
                return '强烈推荐'
            elif '不' in text and '推荐' in text:
                return '不推荐'
            else:
                return '推荐'

        return None