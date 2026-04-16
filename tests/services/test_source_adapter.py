"""
Tests for Source Adapter base class
"""

import pytest
from datetime import datetime, timezone

from app.models.schemas.source import (
    SourceType,
    SourceItem,
    FetchResult,
    FetchError,
)
from app.services.sources.base import SourceAdapter


class MockAdapter(SourceAdapter):
    """Mock adapter for testing"""

    source_name = "test_source"
    source_type = SourceType.API
    base_url = "https://example.com"

    def fetch_items(self, limit: int = 10) -> FetchResult:
        """Mock fetch implementation"""
        result = FetchResult(
            source_name=self.source_name,
            success=True,
            items_fetched=1,
            started_at=datetime.now(timezone.utc),
        )
        # Store items for retrieval (simplified for testing)
        result.items = [
            SourceItem(
                source_id=self.source_name,
                source_item_id="test-123",
                title="Test Article",
                url="https://example.com/test",
                summary="Test summary",
                author_name="Test Author",
            )
        ]
        return result

    def fetch_full_content(self, item: SourceItem) -> str:
        """Mock full content fetch"""
        return f"Full content for: {item.title}"


class TestSourceAdapter:
    """Test SourceAdapter base class"""

    def test_adapter_metadata_validation(self):
        """Test that adapter validates required metadata"""
        adapter = MockAdapter()
        assert adapter.source_name == "test_source"
        assert adapter.source_type == SourceType.API
        assert adapter.base_url == "https://example.com"

    def test_adapter_without_name_raises_error(self):
        """Test that adapter without source_name raises error"""

        class InvalidAdapter(SourceAdapter):
            source_type = SourceType.API
            base_url = "https://example.com"

            def fetch_items(self):
                return FetchResult("test", True, 0)
            def fetch_full_content(self, item):
                return ""

        with pytest.raises(ValueError, match="must define source_name"):
            InvalidAdapter()

    def test_adapter_without_type_raises_error(self):
        """Test that adapter without source_type raises error"""

        class InvalidAdapter(SourceAdapter):
            source_name = "test"
            base_url = "https://example.com"

            def fetch_items(self):
                return FetchResult("test", True, 0)
            def fetch_full_content(self, item):
                return ""

        with pytest.raises(ValueError, match="must define source_type"):
            InvalidAdapter()

    def test_adapter_without_base_url_raises_error(self):
        """Test that adapter without base_url raises error"""

        class InvalidAdapter(SourceAdapter):
            source_name = "test"
            source_type = SourceType.API

            def fetch_items(self):
                return FetchResult("test", True, 0)
            def fetch_full_content(self, item):
                return ""

        with pytest.raises(ValueError, match="must define base_url"):
            InvalidAdapter()

    def test_parse_item_with_valid_dict(self):
        """Test parsing a valid dict to SourceItem"""
        adapter = MockAdapter()
        raw_data = {
            'source_id': 'test',
            'source_item_id': '123',
            'title': 'Test',
            'url': 'https://example.com',
            'summary': 'Summary',
            'author_name': 'Author',
        }

        item = adapter.parse_item(raw_data)
        assert item.source_id == 'test'
        assert item.source_item_id == '123'
        assert item.title == 'Test'
        assert item.url == 'https://example.com'
        assert item.summary == 'Summary'
        assert item.author_name == 'Author'

    def test_parse_item_missing_required_field(self):
        """Test parsing dict with missing required field raises error"""
        adapter = MockAdapter()
        raw_data = {
            'source_id': 'test',
            'source_item_id': '123',
            'title': 'Test',
            # Missing 'url' - required
        }

        with pytest.raises(ValueError, match="Missing required field: url"):
            adapter.parse_item(raw_data)

    def test_parse_item_with_invalid_type(self):
        """Test parsing non-dict raises error"""
        adapter = MockAdapter()

        with pytest.raises(ValueError, match="Expected dict"):
            adapter.parse_item("not a dict")

    def test_handle_error(self):
        """Test error handling"""
        adapter = MockAdapter()
        exception = ValueError("Test error")

        error = adapter.handle_error(exception, item_id="test-123")

        assert error.source_name == "test_source"
        assert error.error_type == "ValueError"
        assert error.message == "Test error"
        assert error.item_id == "test-123"
        assert error.exception == exception

    def test_handle_error_without_item_id(self):
        """Test error handling without item ID"""
        adapter = MockAdapter()
        exception = ValueError("Test error")

        error = adapter.handle_error(exception)

        assert error.source_name == "test_source"
        assert error.error_type == "ValueError"
        assert error.message == "Test error"
        assert error.item_id is None


class TestSourceItem:
    """Test SourceItem dataclass"""

    def test_source_item_creation(self):
        """Test creating a SourceItem"""
        item = SourceItem(
            source_id="test",
            source_item_id="123",
            title="Test",
            url="https://example.com",
        )

        assert item.source_id == "test"
        assert item.source_item_id == "123"
        assert item.title == "Test"
        assert item.url == "https://example.com"
        assert item.summary is None
        assert item.author_name is None
        assert item.tags == []

    def test_source_item_with_invalid_url(self):
        """Test that invalid URL raises error"""
        with pytest.raises(ValueError, match="Invalid URL"):
            SourceItem(
                source_id="test",
                source_item_id="123",
                title="Test",
                url="not-a-url",
            )

    def test_source_item_normalized_url(self):
        """Test URL normalization"""
        item = SourceItem(
            source_id="test",
            source_item_id="123",
            title="Test",
            url="HTTPS://EXAMPLE.COM/Path?query=1#fragment",
        )

        normalized = item.normalized_url
        assert normalized == "https://example.com/path?query=1"
        assert "fragment" not in normalized  # Fragment removed
        assert normalized.islower()  # Lowercased


class TestFetchResult:
    """Test FetchResult dataclass"""

    def test_fetch_result_creation(self):
        """Test creating a FetchResult"""
        result = FetchResult(
            source_name="test",
            success=True,
        )

        assert result.source_name == "test"
        assert result.success is True
        assert result.items_fetched == 0
        assert result.items_new == 0
        assert result.items_updated == 0
        assert result.items_failed == 0
        assert result.errors == []
        assert result.duration_seconds == 0.0

    def test_fetch_result_add_error(self):
        """Test adding errors to FetchResult"""
        result = FetchResult(
            source_name="test",
            success=True,
        )

        result.add_error("Error 1")
        result.add_error("Error 2")

        assert len(result.errors) == 2
        assert result.items_failed == 2
        assert "Error 1" in result.errors
        assert "Error 2" in result.errors


class TestFetchError:
    """Test FetchError dataclass"""

    def test_fetch_error_creation(self):
        """Test creating a FetchError"""
        error = FetchError(
            source_name="test",
            error_type="ValueError",
            message="Test error",
            item_id="123",
        )

        assert error.source_name == "test"
        assert error.error_type == "ValueError"
        assert error.message == "Test error"
        assert error.item_id == "123"
        assert error.exception is None

    def test_fetch_error_to_dict(self):
        """Test converting FetchError to dict"""
        error = FetchError(
            source_name="test",
            error_type="ValueError",
            message="Test error",
        )

        error_dict = error.to_dict()

        assert error_dict["source_name"] == "test"
        assert error_dict["error_type"] == "ValueError"
        assert error_dict["message"] == "Test error"
        assert "timestamp" in error_dict
        assert error_dict["item_id"] is None
        assert error_dict["exception"] is None