"""
Tests for V2EX Adapter
"""

import pytest
from datetime import datetime, timezone
from unittest.mock import Mock, patch
import requests

from app.models.schemas.source import SourceType, SourceItem, FetchResult
from app.services.sources.v2ex import V2EXAdapter


class TestV2EXAdapter:
    """Test V2EX Adapter"""

    def test_adapter_metadata(self):
        """Test adapter metadata"""
        adapter = V2EXAdapter()
        assert adapter.source_name == "v2ex"
        assert adapter.source_type == SourceType.API
        assert adapter.base_url == "https://www.v2ex.com/"

    def test_adapter_with_config(self):
        """Test adapter with configuration"""
        config = {"mode": "hot"}
        adapter = V2EXAdapter(config)
        assert adapter.mode == "hot"

    def test_adapter_invalid_mode(self):
        """Test adapter with invalid mode raises error"""
        with pytest.raises(ValueError, match="Mode must be either 'latest' or 'hot'"):
            V2EXAdapter({"mode": "invalid"})

    def test_parse_v2ex_time(self):
        """Test V2EX time parsing"""
        adapter = V2EXAdapter()

        # Test timezone-aware time
        time_str = "2024-01-01T12:00:00+08:00"
        dt = adapter._parse_v2ex_time(time_str)
        assert dt.tzinfo == timezone.utc
        assert dt.hour == 4  # 12:00 UTC+8 = 04:00 UTC

        # Test UTC time
        time_str = "2024-01-01T12:00:00Z"
        dt = adapter._parse_v2ex_time(time_str)
        assert dt.tzinfo == timezone.utc
        assert dt.hour == 12

        # Test naive time (should be treated as UTC)
        time_str = "2024-01-01T12:00:00"
        dt = adapter._parse_v2ex_time(time_str)
        assert dt.tzinfo == timezone.utc
        assert dt.hour == 12

    def test_normalize_url(self):
        """Test URL normalization"""
        adapter = V2EXAdapter()

        # Full URL
        url = "https://www.v2ex.com/topics/123"
        assert adapter._normalize_url(url) == url

        # Relative URL
        url = "/topics/123"
        assert adapter._normalize_url(url) == "https://www.v2ex.com/topics/123"

        # Path without leading slash
        url = "topics/123"
        assert adapter._normalize_url(url) == "https://www.v2ex.com/topics/123"

        # Empty URL
        assert adapter._normalize_url(None) is None
        assert adapter._normalize_url("") is None

    @patch('requests.get')
    def test_fetch_items_latest(self, mock_get):
        """Test fetching latest items"""
        adapter = V2EXAdapter({"mode": "latest"})

        # Mock API response
        mock_response = Mock()
        mock_response.json.return_value = [
            {
                "id": 123,
                "title": "Test Topic",
                "url": "/t/123",
                "created": "2024-01-01T12:00:00+08:00",
                "member": {
                    "username": "testuser",
                    "url": "/member/testuser"
                },
                "node": {
                    "title": "tech"
                },
                "content": "# Test Content\nThis is a test."
            }
        ]
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        result = adapter.fetch_items(limit=5)

        assert result.success is True
        assert result.items_fetched == 1
        assert len(adapter._last_items) == 1

        item = adapter._last_items[0]
        assert item.source_id == "v2ex"
        assert item.source_item_id == "123"
        assert item.title == "Test Topic"
        assert item.url == "https://www.v2ex.com/t/123"
        assert item.author_name == "testuser"
        assert item.author_url == "https://www.v2ex.com/member/testuser"
        assert item.publish_time.tzinfo == timezone.utc
        assert item.publish_time.hour == 4  # 12:00 UTC+8
        assert item.tags == ["tech"]
        assert item.raw_data is not None

    @patch('requests.get')
    def test_fetch_items_hot(self, mock_get):
        """Test fetching hot items"""
        adapter = V2EXAdapter({"mode": "hot"})

        # Mock API response
        mock_response = Mock()
        mock_response.json.return_value = [
            {
                "id": 456,
                "title": "Hot Topic",
                "url": "/t/456",
                "created": "2024-01-01T12:00:00Z",
                "member": {
                    "username": "hotuser",
                },
                "node": {
                    "title": "share"
                }
            }
        ]
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        result = adapter.fetch_items()

        assert result.success is True
        assert result.items_fetched == 1
        assert len(adapter._last_items) == 1

        item = adapter._last_items[0]
        assert item.title == "Hot Topic"
        assert item.tags == ["share"]

    @patch('requests.get')
    def test_fetch_items_with_error(self, mock_get):
        """Test handling API errors"""
        adapter = V2EXAdapter()

        # Mock network error
        mock_get.side_effect = Exception("Network error")

        result = adapter.fetch_items()

        assert result.success is False
        assert "Network error" in result.errors[0]

    @patch('requests.get')
    def test_fetch_items_limit(self, mock_get):
        """Test fetch with limit"""
        adapter = V2EXAdapter()

        # Mock API response with more items than limit
        topics = []
        for i in range(15):
            topics.append({
                "id": i,
                "title": f"Topic {i}",
                "url": f"/t/{i}",
                "created": "2024-01-01T12:00:00Z",
                "member": {"username": f"user{i}"},
            })

        mock_response = Mock()
        mock_response.json.return_value = topics
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        result = adapter.fetch_items(limit=5)

        assert result.success is True
        assert result.items_fetched == 5

    def test_parse_topic_missing_required_field(self):
        """Test parsing topic with missing required field"""
        adapter = V2EXAdapter()

        with pytest.raises(ValueError, match="Missing required field: id"):
            adapter._parse_topic({
                "title": "Test",
                "url": "/t/1",
                "created": "2024-01-01T12:00:00Z",
                "member": {"username": "test"}
            })

    def test_fetch_full_content(self):
        """Test fetch full content"""
        adapter = V2EXAdapter()

        item = SourceItem(
            source_id="v2ex",
            source_item_id="123",
            title="Test",
            url="https://v2ex.com/t/123",
            raw_data={
                "content": "# Full Content\nThis is the full content."
            }
        )

        content = adapter.fetch_full_content(item)
        assert content == "# Full Content\nThis is the full content."

    def test_fetch_full_content_no_data(self):
        """Test fetch full content without raw data"""
        adapter = V2EXAdapter()

        item = SourceItem(
            source_id="v2ex",
            source_item_id="123",
            title="Test",
            url="https://v2ex.com/t/123"
        )

        content = adapter.fetch_full_content(item)
        assert content == ""

    def test_parse_topic_minimal_data(self):
        """Test parsing topic with minimal data"""
        adapter = V2EXAdapter()

        topic = {
            "id": 789,
            "title": "Minimal Topic",
            "url": "/t/789",
            "created": "2024-01-01T12:00:00+08:00",
            "member": {}  # Empty member
        }

        item = adapter._parse_topic(topic)

        assert item.source_item_id == "789"
        assert item.title == "Minimal Topic"
        assert item.author_name is None
        assert item.author_url is None
        assert item.tags == []  # No node
        assert item.publish_time.tzinfo == timezone.utc
        assert item.publish_time.hour == 4

    def test_parse_topic_with_incomplete_member(self):
        """Test parsing topic with incomplete member data"""
        adapter = V2EXAdapter()

        topic = {
            "id": 101,
            "title": "Incomplete Member",
            "url": "/t/101",
            "created": "2024-01-01T12:00:00Z",
            "member": {
                "username": "user"
                # No url field
            },
            "node": {
                "title": "test"
            }
        }

        item = adapter._parse_topic(topic)

        assert item.author_name == "user"
        assert item.author_url is None  # Should not raise error
        assert item.tags == ["test"]