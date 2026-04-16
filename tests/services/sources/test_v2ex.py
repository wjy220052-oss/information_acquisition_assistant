"""
Tests for V2EX source adapter
"""

import pytest
from datetime import datetime, timezone
from unittest.mock import Mock, patch

from app.services.sources.v2ex import V2EXAdapter
from app.models.schemas.source import SourceType


@pytest.fixture
def v2ex_adapter():
    """Create V2EX adapter instance"""
    return V2EXAdapter(config={"mode": "latest"})


@pytest.fixture
def mock_v2ex_response():
    """Mock V2EX API response"""
    return [
        {
            "id": 123456,
            "title": "Test topic about Python programming",
            "url": "https://www.v2ex.com/t/123456",
            "content": "This is a test topic content about Python.",
            "created": int(datetime.now(timezone.utc).timestamp()),
            "member": {
                "id": 98765,
                "username": "testuser",
                "url": "https://www.v2ex.com/member/testuser"
            },
            "node": {
                "id": 1,
                "name": "python",
                "title": "Python"
            }
        },
        {
            "id": 123457,
            "title": "Another test topic",
            "url": "https://www.v2ex.com/t/123457",
            "content": "Discussion about software architecture.",
            "created": int(datetime.now(timezone.utc).timestamp()),
            "member": {
                "id": 98766,
                "username": "developer",
                "url": "https://www.v2ex.com/member/developer"
            },
            "node": {
                "id": 2,
                "name": "programmer",
                "title": "程序员"
            }
        }
    ]


class TestV2EXAdapter:
    """Tests for V2EXAdapter"""

    def test_adapter_metadata(self, v2ex_adapter):
        """Test adapter has correct metadata"""
        assert v2ex_adapter.source_name == "v2ex"
        assert v2ex_adapter.source_type == SourceType.API
        assert v2ex_adapter.base_url == "https://www.v2ex.com/"

    def test_fetch_items_success(self, v2ex_adapter, mock_v2ex_response):
        """Test successful fetch returns items in FetchResult"""
        with patch('requests.get') as mock_get:
            mock_response = Mock()
            mock_response.json.return_value = mock_v2ex_response
            mock_response.raise_for_status = Mock()
            mock_get.return_value = mock_response

            result = v2ex_adapter.fetch_items(limit=10)

            # Verify FetchResult structure
            assert result.success is True
            assert result.source_name == "v2ex"
            assert result.items_fetched == 2
            assert hasattr(result, 'items')
            assert result.items is not None
            assert len(result.items) == 2

            # Verify first item
            item1 = result.items[0]
            assert item1.source_id == "v2ex"
            assert item1.source_item_id == "123456"
            assert item1.title == "Test topic about Python programming"
            assert item1.url == "https://www.v2ex.com/t/123456"
            assert item1.author_name == "testuser"
            assert "Python" in item1.tags

    def test_fetch_items_with_limit(self, v2ex_adapter, mock_v2ex_response):
        """Test limit parameter is respected"""
        with patch('requests.get') as mock_get:
            mock_response = Mock()
            mock_response.json.return_value = mock_v2ex_response
            mock_response.raise_for_status = Mock()
            mock_get.return_value = mock_response

            result = v2ex_adapter.fetch_items(limit=1)

            assert result.success is True
            assert result.items_fetched == 1
            assert len(result.items) == 1

    def test_fetch_items_network_error(self, v2ex_adapter):
        """Test network error handling"""
        with patch('requests.get') as mock_get:
            from requests import RequestException
            mock_get.side_effect = RequestException("Network error")

            result = v2ex_adapter.fetch_items(limit=10)

            assert result.success is False
            assert len(result.errors) > 0
            assert "Network error" in result.errors[0]

    def test_fetch_items_empty_response(self, v2ex_adapter):
        """Test handling of empty API response"""
        with patch('requests.get') as mock_get:
            mock_response = Mock()
            mock_response.json.return_value = []
            mock_response.raise_for_status = Mock()
            mock_get.return_value = mock_response

            result = v2ex_adapter.fetch_items(limit=10)

            assert result.success is True
            assert result.items_fetched == 0
            assert result.items == []

    def test_parse_topic_missing_fields(self, v2ex_adapter):
        """Test parsing topic with missing required fields raises error"""
        incomplete_topic = {
            "id": 123,
            "title": "Test title"
            # Missing url, created, member
        }

        with pytest.raises(ValueError) as exc_info:
            v2ex_adapter._parse_topic(incomplete_topic)

        assert "Missing required field" in str(exc_info.value)

    def test_fetch_full_content(self, v2ex_adapter):
        """Test fetch_full_content returns content from raw_data"""
        from app.models.schemas.source import SourceItem

        item = SourceItem(
            source_id="v2ex",
            source_item_id="123",
            title="Test",
            url="https://v2ex.com/t/123",
            raw_data={"content": "Full content here"}
        )

        content = v2ex_adapter.fetch_full_content(item)
        assert content == "Full content here"

    def test_fetch_full_content_no_raw_data(self, v2ex_adapter):
        """Test fetch_full_content returns empty string when no raw_data"""
        from app.models.schemas.source import SourceItem

        item = SourceItem(
            source_id="v2ex",
            source_item_id="123",
            title="Test",
            url="https://v2ex.com/t/123",
            raw_data=None
        )

        content = v2ex_adapter.fetch_full_content(item)
        assert content == ""


class TestV2EXAdapterModes:
    """Tests for different V2EX adapter modes"""

    def test_latest_mode(self):
        """Test latest mode uses correct endpoint"""
        adapter = V2EXAdapter(config={"mode": "latest"})
        assert adapter.mode == "latest"

        with patch('requests.get') as mock_get:
            mock_response = Mock()
            mock_response.json.return_value = []
            mock_response.raise_for_status = Mock()
            mock_get.return_value = mock_response

            adapter.fetch_items(limit=10)

            # Verify correct endpoint was called
            call_args = mock_get.call_args
            assert "latest.json" in call_args[0][0]

    def test_hot_mode(self):
        """Test hot mode uses correct endpoint"""
        adapter = V2EXAdapter(config={"mode": "hot"})
        assert adapter.mode == "hot"

        with patch('requests.get') as mock_get:
            mock_response = Mock()
            mock_response.json.return_value = []
            mock_response.raise_for_status = Mock()
            mock_get.return_value = mock_response

            adapter.fetch_items(limit=10)

            # Verify correct endpoint was called
            call_args = mock_get.call_args
            assert "hot.json" in call_args[0][0]

    def test_invalid_mode(self):
        """Test invalid mode raises ValueError"""
        with pytest.raises(ValueError) as exc_info:
            V2EXAdapter(config={"mode": "invalid"})

        assert "Mode must be either 'latest' or 'hot'" in str(exc_info.value)
