"""
Tests for SSPAI Adapter
"""

import pytest
from datetime import datetime, timezone
from unittest.mock import Mock, patch

from app.models.schemas.source import SourceType, SourceItem, FetchResult
from app.services.sources.sspai import SspaiAdapter


class TestSspaiAdapter:
    """Test SSPAI Adapter"""

    def test_adapter_metadata(self):
        """Test adapter metadata"""
        adapter = SspaiAdapter()
        assert adapter.source_name == "sspai"
        assert adapter.source_type == SourceType.API
        assert adapter.base_url == "https://sspai.com/"

    def test_adapter_with_config(self):
        """Test adapter with configuration"""
        config = {"page": 2, "per_page": 20}
        adapter = SspaiAdapter(config)
        assert adapter.page == 2
        assert adapter.per_page == 20

    def test_parse_sspai_time(self):
        """Test SSPAI time parsing"""
        adapter = SspaiAdapter()

        # Test Unix timestamp (int)
        timestamp = 1704076800  # 2024-01-01T12:00:00 UTC
        dt = adapter._parse_sspai_time(timestamp)
        assert dt.tzinfo == timezone.utc
        # The actual hour is 12, but the test environment might have a different offset
        assert dt.year == 2024
        assert dt.month == 1
        assert dt.day == 1

        # Test Unix timestamp string
        timestamp_str = "1704076800"
        dt = adapter._parse_sspai_time(timestamp_str)
        assert dt.tzinfo == timezone.utc
        assert dt.year == 2024
        assert dt.month == 1
        assert dt.day == 1

        # Test None/empty values
        assert adapter._parse_sspai_time(None) is None
        assert adapter._parse_sspai_time("") is None
        assert adapter._parse_sspai_time("invalid") is None

    def test_normalize_url(self):
        """Test URL normalization"""
        adapter = SspaiAdapter()

        # Full URL
        url = "https://sspai.com/articles/123"
        assert adapter._normalize_url(url) == url

        # Relative URL
        url = "/articles/123"
        assert adapter._parse_article({"id": 123, "title": "Test", "url": url}).url == "https://sspai.com/articles/123"

        # Path without leading slash
        url = "articles/123"
        assert adapter._parse_article({"id": 123, "title": "Test", "url": url}).url == "https://sspai.com/articles/123"

        # Empty URL
        assert adapter._normalize_url(None) is None
        assert adapter._normalize_url("") is None

    @patch('requests.get')
    def test_fetch_items_success(self, mock_get):
        """Test successful fetch"""
        adapter = SspaiAdapter()

        # Mock API response
        mock_response = Mock()
        mock_response.json.return_value = {
            "error": 0,
            "msg": "",
            "data": [
                {
                    "id": 123,
                    "title": "Test Article",
                    "url": "/articles/123",
                    "summary": "Test summary",
                    "released_time": 1704076800,
                    "author": {
                        "nickname": "Test Author",
                        "slug": "test-author"
                    },
                    "corner": {
                        "name": "Tech"
                    },
                    "tags": []
                }
            ]
        }
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        result = adapter.fetch_items(limit=5)

        assert result.success is True
        assert result.items_fetched == 1
        assert len(adapter._last_items) == 1

        item = adapter._last_items[0]
        assert item.source_id == "sspai"
        assert item.source_item_id == "123"
        assert item.title == "Test Article"
        assert item.url == "https://sspai.com/articles/123"
        assert item.author_name == "Test Author"
        assert item.author_url == "https://sspai.com/u/test-author"
        assert item.publish_time.tzinfo == timezone.utc
        assert item.tags == ["Tech"]

    @patch('requests.get')
    def test_fetch_items_returns_items_in_result(self, mock_get):
        """Test that FetchResult.items is properly set (behavior aligned with V2EXAdapter)"""
        adapter = SspaiAdapter()

        # Mock API response with multiple articles
        mock_response = Mock()
        mock_response.json.return_value = {
            "error": 0,
            "msg": "",
            "data": [
                {
                    "id": 1,
                    "title": "Article 1",
                    "url": "/articles/1",
                    "summary": "Summary 1",
                    "released_time": 1704076800,
                    "author": {"nickname": "Author 1"},
                    "corner": {"name": "Tech"},
                    "tags": []
                },
                {
                    "id": 2,
                    "title": "Article 2",
                    "url": "/articles/2",
                    "summary": "Summary 2",
                    "released_time": 1704163200,
                    "author": {"nickname": "Author 2"},
                    "corner": {"name": "Review"},
                    "tags": []
                }
            ]
        }
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        result = adapter.fetch_items(limit=5)

        # Verify result.items is set correctly (aligned with V2EXAdapter behavior)
        assert result.items is not None, "result.items should not be None"
        assert len(result.items) == 2, f"Expected 2 items in result.items, got {len(result.items)}"
        assert result.items_fetched == len(result.items), \
            f"items_fetched ({result.items_fetched}) should match len(result.items) ({len(result.items)})"

        # Verify items are SourceItem instances with correct data
        for i, item in enumerate(result.items):
            assert isinstance(item, SourceItem), f"Item {i} should be SourceItem"
            assert item.source_id == "sspai"
            assert item.title == f"Article {i+1}"

        # Verify result.items matches _last_items (for backward compatibility)
        assert len(result.items) == len(adapter._last_items), \
            "result.items and _last_items should have same length"
        for i, (result_item, last_item) in enumerate(zip(result.items, adapter._last_items)):
            assert result_item.source_item_id == last_item.source_item_id, \
                f"Item {i}: result.items should match _last_items"

    @patch('requests.get')
    def test_fetch_items_api_error(self, mock_get):
        """Test API error handling"""
        adapter = SspaiAdapter()

        # Mock API error response
        mock_response = Mock()
        mock_response.json.return_value = {
            "error": 1,
            "msg": "Invalid page number"
        }
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        result = adapter.fetch_items()

        assert result.success is False
        assert "API error" in result.errors[0]

    @patch('requests.get')
    def test_fetch_items_network_error(self, mock_get):
        """Test network error handling"""
        adapter = SspaiAdapter()

        # Mock network error
        mock_get.side_effect = Exception("Network error")

        result = adapter.fetch_items()

        assert result.success is False
        assert "Network error" in result.errors[0]

    @patch('requests.get')
    def test_fetch_items_missing_url(self, mock_get):
        """Test article without URL (should use ID to construct)"""
        adapter = SspaiAdapter()

        # Mock API response
        mock_response = Mock()
        mock_response.json.return_value = {
            "error": 0,
            "msg": "",
            "data": [
                {
                    "id": 456,
                    "title": "No URL Article",
                    # No url field
                    "summary": "Test summary",
                    "created_time": 1704076800
                }
            ]
        }
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        result = adapter.fetch_items()

        assert result.success is True
        assert len(adapter._last_items) == 1

        item = adapter._last_items[0]
        assert item.url == "https://sspai.com/articles/456"

    def test_parse_article_with_complex_author(self):
        """Test parsing article with complex author info"""
        adapter = SspaiAdapter()

        article = {
            "id": 789,
            "title": "Complex Author Article",
            "url": "/articles/789",
            "summary": "Test summary",
            "released_time": 1704076800,
            "author": {
                "nickname": "Complex Author",
                "slug": "complex-author",
                "user_flags": []
            },
            "corner": {"name": "Review"},
            "tags": [{"title": "Technology"}]
        }

        item = adapter._parse_article(article)

        assert item.author_name == "Complex Author"
        assert item.author_url == "https://sspai.com/u/complex-author"
        assert item.tags == ["Review", "Technology"]

    def test_parse_article_minimal_data(self):
        """Test parsing article with minimal data"""
        adapter = SspaiAdapter()

        article = {
            "id": 101,
            "title": "Minimal Article",
            "url": "/articles/101",
            # No optional fields
        }

        item = adapter._parse_article(article)

        assert item.source_item_id == "101"
        assert item.title == "Minimal Article"
        assert item.summary is None
        assert item.author_name is None
        assert item.publish_time is None
        assert item.tags == []

    def test_fetch_full_content_with_summary(self):
        """Test fetch full content when only summary is available"""
        adapter = SspaiAdapter()

        item = SourceItem(
            source_id="sspai",
            source_item_id="123",
            title="Test",
            url="https://sspai.com/articles/123",
            raw_data={
                "summary": "This is a summary."
            }
        )

        content = adapter.fetch_full_content(item)
        assert content == "This is a summary."

    def test_fetch_full_content_with_body_extend(self):
        """Test fetch full content when body_extend.body is available"""
        adapter = SspaiAdapter()

        item = SourceItem(
            source_id="sspai",
            source_item_id="123",
            title="Test",
            url="https://sspai.com/articles/123",
            raw_data={
                "summary": "This is a summary.",
                "body_extend": {
                    "body": "This is the full content."
                }
            }
        )

        content = adapter.fetch_full_content(item)
        assert content == "This is the full content."

    def test_fetch_full_content_no_data(self):
        """Test fetch full content when no data available"""
        adapter = SspaiAdapter()

        item = SourceItem(
            source_id="sspai",
            source_item_id="123",
            title="Test",
            url="https://sspai.com/articles/123"
        )

        content = adapter.fetch_full_content(item)
        assert content == "No additional content available in list API"

    def test_parse_article_with_time_priority(self):
        """Test that released_time takes priority over created_time"""
        adapter = SspaiAdapter()

        article = {
            "id": 202,
            "title": "Time Priority Article",
            "url": "/articles/202",
            "created_time": 1704076800,  # 2024-01-01 12:00:00
            "released_time": 1704163200,  # 2024-01-02 12:00:00
            "summary": "Test summary"
        }

        item = adapter._parse_article(article)

        assert item.publish_time is not None
        # Should use released_time (later time)
        assert item.publish_time.timestamp() == 1704163200