"""
Tests for Ruanyf Weekly Adapter

Covers:
- Adapter initialization
- RSS feed parsing
- Entry extraction
- Tag generation
"""

import pytest
from datetime import datetime, timezone
from unittest.mock import Mock, patch, MagicMock

from app.services.sources.ruanyf_weekly import RuanyfWeeklyAdapter
from app.models.schemas.source import SourceType, SourceItem, FetchResult


class TestRuanyfWeeklyAdapterBasics:
    """Tests for basic adapter functionality"""

    def test_adapter_metadata(self):
        """Adapter should have correct metadata"""
        adapter = RuanyfWeeklyAdapter()

        assert adapter.source_name == "ruanyf_weekly"
        assert adapter.source_type == SourceType.RSS
        assert adapter.base_url == "https://feeds.feedburner.com/ruanyifeng"

    def test_default_config(self):
        """Adapter should work with default config"""
        adapter = RuanyfWeeklyAdapter()
        assert adapter.timeout == 30
        assert "Mozilla" in adapter.user_agent

    def test_custom_config(self):
        """Adapter should accept custom config"""
        config = {
            'timeout': 60,
            'user_agent': 'CustomBot/1.0'
        }
        adapter = RuanyfWeeklyAdapter(config=config)

        assert adapter.timeout == 60
        assert adapter.user_agent == 'CustomBot/1.0'


class TestRuanyfWeeklyParseEntry:
    """Tests for entry parsing logic"""

    def test_basic_entry_parsing(self):
        """Should parse basic entry fields correctly"""
        adapter = RuanyfWeeklyAdapter()

        entry = {
            'title': '科技爱好者周刊（第 300 期）：测试标题',
            'link': 'https://www.ruanyifeng.com/blog/2024/01/weekly-issue-300.html',
            'summary': '本周介绍了一些新技术和工具...',
            'published': 'Mon, 15 Jan 2024 08:00:00 GMT',
            'author': '阮一峰',
        }
        feed_info = {'title': '阮一峰的网络日志'}

        item = adapter._parse_entry(entry, feed_info)

        assert isinstance(item, SourceItem)
        assert item.source_id == "ruanyf_weekly"
        assert "科技爱好者周刊" in item.title
        assert item.url.startswith('http')
        assert item.author_name == "阮一峰"

    def test_weekly_tags_added(self):
        """Should add weekly-specific tags"""
        adapter = RuanyfWeeklyAdapter()

        entry = {
            'title': '科技爱好者周刊（第 300 期）',
            'link': 'https://example.com/300',
        }
        feed_info = {}

        item = adapter._parse_entry(entry, feed_info)

        assert "科技周刊" in item.tags
        assert "阮一峰" in item.tags
        assert "周刊" in item.tags

    def test_category_tag_extraction(self):
        """Should extract category tags based on content"""
        adapter = RuanyfWeeklyAdapter()

        test_cases = [
            ({'title': '周刊', 'summary': '推荐一个好用工具'}, '工具'),
            ({'title': '教程：如何学习', 'summary': ''}, '教程'),
            ({'title': '我的观点', 'summary': '思考'}, '观点'),
            ({'title': '新闻', 'summary': 'announcement'}, '新闻'),
        ]

        for entry_data, expected_tag in test_cases:
            entry = {
                'title': entry_data['title'],
                'link': 'https://example.com/test',
                'summary': entry_data['summary'],
            }
            feed_info = {}

            item = adapter._parse_entry(entry, feed_info)

            assert expected_tag in item.tags, f"Expected tag '{expected_tag}' not found in {item.tags}"

    def test_no_duplicate_tags(self):
        """Should not create duplicate tags"""
        adapter = RuanyfWeeklyAdapter()

        entry = {
            'title': '科技爱好者周刊',
            'link': 'https://example.com/test',
        }
        feed_info = {}

        item = adapter._parse_entry(entry, feed_info)

        # Check no duplicates
        assert len(item.tags) == len(set(item.tags))


class TestRuanyfWeeklyFetchItems:
    """Tests for fetch_items with mocked HTTP"""

    @patch('app.services.sources.rss_base.requests.get')
    @patch('app.services.sources.rss_base.feedparser.parse')
    def test_successful_fetch(self, mock_parse, mock_get):
        """Should successfully fetch and parse RSS feed"""
        # Setup mock response
        mock_response = Mock()
        mock_response.content = b'<rss>...</rss>'
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        # Setup mock feedparser result
        mock_feed = Mock()
        mock_feed.bozo = False
        mock_feed.feed = {'title': '阮一峰的网络日志'}
        mock_feed.entries = [
            {
                'title': '周刊（第 1 期）',
                'link': 'https://example.com/1',
                'summary': 'Summary 1',
                'published': 'Mon, 15 Jan 2024 08:00:00 GMT',
            },
            {
                'title': '周刊（第 2 期）',
                'link': 'https://example.com/2',
                'summary': 'Summary 2',
                'published': 'Mon, 22 Jan 2024 08:00:00 GMT',
            },
        ]
        mock_parse.return_value = mock_feed

        adapter = RuanyfWeeklyAdapter()
        result = adapter.fetch_items(limit=10)

        assert result.success is True
        assert result.items_fetched == 2
        assert len(result.items) == 2
        assert result.items[0].title == '周刊（第 1 期）'

    @patch('app.services.sources.rss_base.requests.get')
    def test_fetch_failure(self, mock_get):
        """Should handle fetch failure gracefully"""
        from requests import RequestException
        mock_get.side_effect = RequestException("Network error")

        adapter = RuanyfWeeklyAdapter()
        result = adapter.fetch_items(limit=10)

        assert result.success is False
        assert len(result.errors) > 0
        assert 'Network error' in result.errors[0] or 'Failed to fetch' in result.errors[0]

    @patch('app.services.sources.rss_base.requests.get')
    @patch('app.services.sources.rss_base.feedparser.parse')
    def test_respects_limit(self, mock_parse, mock_get):
        """Should respect the limit parameter"""
        # Setup mocks
        mock_response = Mock()
        mock_response.content = b'<rss>...</rss>'
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        mock_feed = Mock()
        mock_feed.bozo = False
        mock_feed.feed = {}
        mock_feed.entries = [
            {'title': f'周刊（第 {i} 期）', 'link': f'https://example.com/{i}'}
            for i in range(20)
        ]
        mock_parse.return_value = mock_feed

        adapter = RuanyfWeeklyAdapter()
        result = adapter.fetch_items(limit=5)

        assert result.items_fetched == 5
        assert len(result.items) == 5


class TestRuanyfWeeklyFetchFullContent:
    """Tests for fetch_full_content method"""

    def test_returns_summary_from_raw_data(self):
        """Should return summary from raw_data if available"""
        adapter = RuanyfWeeklyAdapter()

        item = SourceItem(
            source_id="ruanyf_weekly",
            source_item_id="test-1",
            title="Test",
            url="https://example.com/test",
            summary="Test summary",
            raw_data={
                'entry': {
                    'content': 'Full content here'
                }
            }
        )

        content = adapter.fetch_full_content(item)
        assert content == "Full content here"

    def test_returns_item_summary_when_no_content(self):
        """Should return item.summary when no content in raw_data"""
        adapter = RuanyfWeeklyAdapter()

        item = SourceItem(
            source_id="ruanyf_weekly",
            source_item_id="test-1",
            title="Test",
            url="https://example.com/test",
            summary="Item summary",
            raw_data={'entry': {}}
        )

        content = adapter.fetch_full_content(item)
        assert content == "Item summary"

    def test_returns_not_available_message(self):
        """Should return not available message when no content"""
        adapter = RuanyfWeeklyAdapter()

        item = SourceItem(
            source_id="ruanyf_weekly",
            source_item_id="test-1",
            title="Test",
            url="https://example.com/test",
            summary=None,
            raw_data=None
        )

        content = adapter.fetch_full_content(item)
        assert "not available" in content.lower()
