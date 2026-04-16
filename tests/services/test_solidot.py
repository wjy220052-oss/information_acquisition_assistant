"""
Tests for Solidot Adapter

Covers:
- Adapter initialization
- RSS feed parsing
- Category/tag extraction from title
- Entry field mapping
"""

import pytest
from datetime import datetime, timezone
from unittest.mock import Mock, patch, MagicMock

from app.services.sources.solidot import SolidotAdapter
from app.models.schemas.source import SourceType, SourceItem, FetchResult


class TestSolidotAdapterBasics:
    """Tests for basic adapter functionality"""

    def test_adapter_metadata(self):
        """Adapter should have correct metadata"""
        adapter = SolidotAdapter()

        assert adapter.source_name == "solidot"
        assert adapter.source_type == SourceType.RSS
        assert adapter.base_url == "https://www.solidot.org/index.rss"

    def test_default_config(self):
        """Adapter should work with default config"""
        adapter = SolidotAdapter()
        assert adapter.timeout == 30
        assert "Mozilla" in adapter.user_agent

    def test_custom_config(self):
        """Adapter should accept custom config"""
        config = {
            'timeout': 60,
            'user_agent': 'CustomBot/1.0'
        }
        adapter = SolidotAdapter(config=config)

        assert adapter.timeout == 60
        assert adapter.user_agent == 'CustomBot/1.0'


class TestSolidotParseEntry:
    """Tests for entry parsing with Solidot-specific features"""

    def test_basic_entry_parsing(self):
        """Should parse basic entry fields correctly"""
        adapter = SolidotAdapter()

        entry = {
            'title': '[AI] OpenAI 发布 GPT-5',
            'link': 'https://www.solidot.org/story?sid=78901',
            'description': '<p>OpenAI 宣布...</p>',
            'author': 'solidot',
            'published': 'Mon, 15 Jan 2024 08:00:00 GMT',
        }
        feed_info = {'title': 'Solidot'}

        item = adapter._parse_entry(entry, feed_info)

        assert isinstance(item, SourceItem)
        assert item.source_id == "solidot"
        assert item.title == '[AI] OpenAI 发布 GPT-5'
        assert item.url == 'https://www.solidot.org/story?sid=78901'
        assert item.author_name == "solidot"

    def test_category_extraction_from_title(self):
        """Should extract category from title brackets"""
        adapter = SolidotAdapter()

        test_cases = [
            ('[AI] 人工智能新闻', 'AI'),
            ('[开源] Linux 更新', '开源'),
            ('[软件] 新发布', '软件'),
            ('[安全] 漏洞预警', '安全'),
        ]

        for title, expected_category in test_cases:
            entry = {
                'title': title,
                'link': 'https://example.com/test',
            }
            feed_info = {}

            item = adapter._parse_entry(entry, feed_info)

            assert expected_category in item.tags, f"Expected '{expected_category}' in tags for title '{title}', got {item.tags}"

    def test_tech_news_tag_added(self):
        """Should always add 科技资讯 tag"""
        adapter = SolidotAdapter()

        entry = {
            'title': '普通标题',
            'link': 'https://example.com/test',
        }
        feed_info = {}

        item = adapter._parse_entry(entry, feed_info)

        assert "科技资讯" in item.tags

    def test_category_mapping(self):
        """Should map categories to Chinese tags"""
        adapter = SolidotAdapter()

        entry = {
            'title': '[AI] 测试标题',
            'link': 'https://example.com/test',
        }
        feed_info = {}

        item = adapter._parse_entry(entry, feed_info)

        assert "AI" in item.tags
        assert "人工智能" in item.tags
        assert "科技资讯" in item.tags

    def test_no_duplicate_tags(self):
        """Should not create duplicate tags"""
        adapter = SolidotAdapter()

        entry = {
            'title': '[AI] 测试',
            'link': 'https://example.com/test',
            'category': 'AI',  # Same as title category
        }
        feed_info = {'category': '科技'}

        item = adapter._parse_entry(entry, feed_info)

        # Check no duplicates
        assert len(item.tags) == len(set(item.tags))

    def test_title_without_brackets(self):
        """Should handle title without category brackets"""
        adapter = SolidotAdapter()

        entry = {
            'title': '没有分类的普通标题',
            'link': 'https://example.com/test',
        }
        feed_info = {}

        item = adapter._parse_entry(entry, feed_info)

        # Should still have 科技资讯 tag
        assert "科技资讯" in item.tags
        # Should not have empty category tag
        assert "" not in item.tags


class TestSolidotFetchItems:
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
        mock_feed.feed = {'title': 'Solidot'}
        mock_feed.entries = [
            {
                'title': '[AI] 文章 1',
                'link': 'https://solidot.org/story?sid=1',
                'summary': 'Summary 1',
                'published': 'Mon, 15 Jan 2024 08:00:00 GMT',
            },
            {
                'title': '[开源] 文章 2',
                'link': 'https://solidot.org/story?sid=2',
                'summary': 'Summary 2',
                'published': 'Mon, 15 Jan 2024 09:00:00 GMT',
            },
        ]
        mock_parse.return_value = mock_feed

        adapter = SolidotAdapter()
        result = adapter.fetch_items(limit=10)

        assert result.success is True
        assert result.items_fetched == 2
        assert len(result.items) == 2
        assert result.items[0].title == '[AI] 文章 1'
        assert result.items[1].title == '[开源] 文章 2'

    @patch('app.services.sources.rss_base.requests.get')
    def test_fetch_failure(self, mock_get):
        """Should handle fetch failure gracefully"""
        from requests import RequestException
        mock_get.side_effect = RequestException("Network error")

        adapter = SolidotAdapter()
        result = adapter.fetch_items(limit=10)

        assert result.success is False
        assert len(result.errors) > 0

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
            {'title': f'[AI] 文章 {i}', 'link': f'https://solidot.org/{i}'}
            for i in range(20)
        ]
        mock_parse.return_value = mock_feed

        adapter = SolidotAdapter()
        result = adapter.fetch_items(limit=10)

        assert result.items_fetched == 10
        assert len(result.items) == 10


class TestSolidotFetchFullContent:
    """Tests for fetch_full_content method"""

    def test_returns_summary_from_raw_data(self):
        """Should return summary from raw_data if available"""
        adapter = SolidotAdapter()

        item = SourceItem(
            source_id="solidot",
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
        adapter = SolidotAdapter()

        item = SourceItem(
            source_id="solidot",
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
        adapter = SolidotAdapter()

        item = SourceItem(
            source_id="solidot",
            source_item_id="test-1",
            title="Test",
            url="https://example.com/test",
            summary=None,
            raw_data=None
        )

        content = adapter.fetch_full_content(item)
        assert "not available" in content.lower()
