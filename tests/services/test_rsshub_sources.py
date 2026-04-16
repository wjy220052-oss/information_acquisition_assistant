"""
Tests for RSSHub source adapters
"""

import pytest
from datetime import datetime, timezone
from unittest.mock import Mock, patch

from app.models.schemas.source import SourceType, FetchResult
from app.services.sources.rsshub_zhihu import RSSHubZhihuAdapter
from app.services.sources.rsshub_douban import RSSHubDoubanAdapter


class TestRSSHubZhihuAdapter:
    """Test RSSHub Zhihu adapter"""

    def test_metadata(self):
        """Test adapter metadata"""
        adapter = RSSHubZhihuAdapter()
        assert adapter.source_name == "rsshub_zhihu"
        assert adapter.source_type == SourceType.RSSHUB
        assert adapter.base_url == "https://rsshub.app/zhihu"

    def test_get_topic_feed_url(self):
        """Test topic feed URL generation"""
        adapter = RSSHubZhihuAdapter()
        url = adapter.get_topic_feed_url("tech")
        assert url == "https://rsshub.app/zhihu/topic/tech"

    def test_get_column_feed_url(self):
        """Test column feed URL generation"""
        adapter = RSSHubZhihuAdapter()
        url = adapter.get_column_feed_url("123456")
        assert url == "https://rsshub.app/zhihu/column/123456"

    def test_get_question_feed_url(self):
        """Test question feed URL generation"""
        adapter = RSSHubZhihuAdapter()
        url = adapter.get_question_feed_url("123456")
        assert url == "https://rsshub.app/zhihu/question/123456"

    @patch('app.services.sources.rss_base.RSSBaseAdapter._fetch_feed')
    @patch('app.services.sources.rss_base.RSSBaseAdapter._parse_feed')
    def test_fetch_items_success(self, mock_parse, mock_fetch):
        """Test successful item fetching"""
        adapter = RSSHubZhihuAdapter()

        # Mock successful response
        mock_response = Mock()
        mock_response.content = b'<rss></rss>'
        mock_fetch.return_value = mock_response

        # Mock parsed feed with entry
        mock_feed = Mock()
        mock_feed.bozo = False
        mock_feed.entries = [{
            'title': 'Test Title',
            'link': 'https://zhihu.com/test',
            'summary': 'Test summary',
            'author': 'Test Author',
            'published': '2024-01-01T00:00:00Z',
            'tags': ['tag1', 'tag2'],
        }]
        mock_feed.feed = {
            'title': '知乎专栏',
            'author': '专栏作者'
        }
        mock_parse.return_value = mock_feed

        result = adapter.fetch_items(limit=5)

        assert result.success is True
        assert result.items_fetched == 1
        assert result.items_new == 1
        assert len(result.items) == 1

        item = result.items[0]
        assert item.source_id == "rsshub_zhihu"
        assert item.source_item_id == "47d723880aad15f56e56e1ad9a4a095c"  # MD5 of "https://zhihu.com/test"
        assert item.title == "Test Title"
        assert item.url == "https://zhihu.com/test"
        assert item.summary == "Test summary"
        assert item.author_name == "Test Author"
        assert item.publish_time == datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
        assert "专栏" in item.tags

    @patch('app.services.sources.rss_base.RSSBaseAdapter._fetch_feed')
    def test_fetch_items_failure(self, mock_fetch):
        """Test fetch failure handling"""
        adapter = RSSHubZhihuAdapter()
        mock_fetch.return_value = None

        result = adapter.fetch_items()

        assert result.success is False
        assert result.items_fetched == 0
        assert "Failed to fetch feed" in result.errors[0]

    def test_parse_entry_with_zhihu_metadata(self):
        """Test parsing with Zhihu-specific metadata"""
        adapter = RSSHubZhihuAdapter()

        entry = {
            'title': 'Test Article',
            'link': 'https://zhihu.com/test',
            'summary': 'Test summary',
            'author': 'Test Author',
            'published': '2024-01-01T00:00:00Z',
        }

        feed_info = {
            'title': '知乎专栏',
            'author': '专栏作者'
        }

        with patch.object(adapter, '_extract_text') as mock_extract, \
             patch.object(adapter, '_extract_url') as mock_url, \
             patch.object(adapter, '_extract_id') as mock_id, \
             patch.object(adapter, '_extract_author') as mock_author, \
             patch.object(adapter, '_extract_publish_time') as mock_time, \
             patch.object(adapter, '_extract_tags') as mock_tags:

            # Mock the extraction methods
            mock_extract.return_value = "Test Article"
            mock_url.return_value = "https://zhihu.com/test"
            mock_id.return_value = "test-id"
            mock_author.return_value = "Test Author"
            mock_time.return_value = datetime(2024, 1, 1, tzinfo=timezone.utc)
            mock_tags.return_value = ["tag1"]

            item = adapter._parse_entry(entry, feed_info)

            assert item.raw_data['feed_title'] == '知乎专栏'
            assert "专栏" in item.tags


class TestRSSHubDoubanAdapter:
    """Test RSSHub Douban adapter"""

    def test_metadata(self):
        """Test adapter metadata"""
        adapter = RSSHubDoubanAdapter()
        assert adapter.source_name == "rsshub_douban"
        assert adapter.source_type == SourceType.RSSHUB
        assert adapter.base_url == "https://rsshub.app/douban"

    def test_get_book_reviews_feed_url(self):
        """Test book reviews feed URL generation"""
        adapter = RSSHubDoubanAdapter()
        url = adapter.get_book_reviews_feed_url("123456")
        assert url == "https://rsshub.app/douban/book/reviews/123456"

    def test_get_movie_reviews_feed_url(self):
        """Test movie reviews feed URL generation"""
        adapter = RSSHubDoubanAdapter()
        url = adapter.get_movie_reviews_feed_url("123456")
        assert url == "https://rsshub.app/douban/movie/reviews/123456"

    def test_get_music_reviews_feed_url(self):
        """Test music reviews feed URL generation"""
        adapter = RSSHubDoubanAdapter()
        url = adapter.get_music_reviews_feed_url()
        assert url == "https://rsshub.app/douban/music/reviews"

    def test_extract_rating(self):
        """Test rating extraction"""
        adapter = RSSHubDoubanAdapter()

        # Test numeric rating
        rating = adapter._extract_rating("《Python编程》", "这本书很不错，评分8.5分")
        assert rating == "8.5分"

        # Test star rating
        rating = adapter._extract_rating("《Python编程》", "五星推荐！")
        assert rating == "5星"

        # Test recommendation
        rating = adapter._extract_rating("《Python编程》", "强烈推荐")
        assert rating == "强烈推荐"

        # Test no rating
        rating = adapter._extract_rating("《Python编程》", "这是一本书")
        assert rating is None

    @patch('app.services.sources.rss_base.RSSBaseAdapter._fetch_feed')
    @patch('app.services.sources.rss_base.RSSBaseAdapter._parse_feed')
    def test_fetch_items_with_douban_metadata(self, mock_parse, mock_fetch):
        """Test fetching with Douban-specific metadata"""
        adapter = RSSHubDoubanAdapter()

        # Mock successful response
        mock_response = Mock()
        mock_response.content = b'<rss></rss>'
        mock_fetch.return_value = mock_response

        # Mock parsed feed with entry
        mock_feed = Mock()
        mock_feed.bozo = False
        mock_feed.entries = [{
            'title': '《Python编程》 - 8.5分',
            'link': 'https://book.douban.com/review/123456',
            'summary': '很好的Python入门书',
            'author_detail': {
                'name': '读者A',
                'link': 'https://www.douban.com/people/readerA'
            },
            'published': '2024-01-01T00:00:00Z',
        }]
        mock_feed.feed = {
            'title': '豆瓣读书',
            'author_detail': {
                'name': '豆瓣编辑',
                'link': 'https://www.douban.com/editor'
            }
        }
        mock_parse.return_value = mock_feed

        result = adapter.fetch_items()

        assert result.success is True
        assert len(result.items) == 1

        item = result.items[0]
        assert item.title == "《Python编程》 - 8.5分"
        assert item.author_name == "读者A"  # From entry, not feed
        assert item.author_url == "https://www.douban.com/people/readerA"
        assert "豆瓣读书" in item.tags
        assert "书评" in item.tags
        assert item.raw_data['rating'] == "8.5分"


class TestRSSBaseAdapterCommon:
    """Test common RSS adapter functionality"""

    def test_extract_id_various_formats(self):
        """Test ID extraction with various formats"""
        adapter = RSSHubZhihuAdapter()

        # Test with guid
        entry1 = {'guid': '12345', 'link': 'https://example.com'}
        assert adapter._extract_id(entry1, 'https://example.com') == '12345'

        # Test with id field
        entry2 = {'id': '12345', 'link': 'https://example.com'}
        assert adapter._extract_id(entry2, 'https://example.com') == '12345'

        # Test with post-id
        entry3 = {'post-id': '12345', 'link': 'https://example.com'}
        assert adapter._extract_id(entry3, 'https://example.com') == '12345'

        # Test fallback to URL hash
        entry4 = {'link': 'https://example.com/unique'}
        import hashlib
        expected = hashlib.md5('https://example.com/unique'.encode()).hexdigest()
        assert adapter._extract_id(entry4, 'https://example.com/unique') == expected

    def test_extract_publish_time_various_formats(self):
        """Test time extraction with various formats"""
        adapter = RSSHubZhihuAdapter()

        # Test RFC 3339 format
        dt1 = adapter._extract_publish_time({'published': '2024-01-01T00:00:00Z'})
        assert dt1 == datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc)

        # Test RFC 822 format
        dt2 = adapter._extract_publish_time({'pubDate': 'Tue, 01 Jan 2024 00:00:00 GMT'})
        assert dt2 == datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc)

        # Test no timezone
        dt3 = adapter._extract_publish_time({'published': '2024-01-01 00:00:00'})
        assert dt3 == datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc)

        # Test invalid time
        dt4 = adapter._extract_publish_time({'published': 'invalid-time'})
        assert dt4 is None

    def test_extract_tags_various_formats(self):
        """Test tag extraction with various formats"""
        adapter = RSSHubZhihuAdapter()

        # Test string tags
        tags1 = adapter._extract_tags({'tags': ['tag1', 'tag2']})
        assert tags1 == ['tag1', 'tag2']

        # Test dict tags
        tags2 = adapter._extract_tags({
            'tags': [{'term': 'tag1'}, {'term': 'tag2'}]
        })
        assert tags2 == ['tag1', 'tag2']

        # Test categories
        tags3 = adapter._extract_tags({
            'category': ['cat1', 'cat2']
        })
        assert tags3 == ['cat1', 'cat2']

        # Test empty tags
        tags4 = adapter._extract_tags({})
        assert tags4 == []

        # Test None tags
        tags5 = adapter._extract_tags({'tags': None})
        assert tags5 == []