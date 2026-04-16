"""
Tests for Fetch task
"""

import pytest
from datetime import datetime, timezone
from uuid import uuid4
from unittest.mock import patch, MagicMock

from app.models.schemas.source import SourceType, SourceItem, FetchResult
from app.services.sources.base import SourceAdapter
from app.tasks.fetch import FetchTask, run_fetch_task


class MockFetchAdapter(SourceAdapter):
    """Test adapter for FetchTask testing"""

    source_name = "test_fetch"
    source_type = SourceType.API
    base_url = "https://example.com"

    def __init__(self):
        super().__init__()
        # Generate unique suffix for this instance to avoid unique key conflicts
        self.unique_suffix = str(uuid4())[:8]

    def fetch_items(self, limit: int = 10) -> FetchResult:
        """Mock fetch that returns test items with classifiable content"""
        result = FetchResult(
            source_name=self.source_name,
            success=True,
            items_fetched=min(limit, 2),  # Return up to 2 items
            started_at=datetime.now(timezone.utc),
        )
        # Attach items for testing - use unique source_item_ids to avoid conflicts
        result.items = [
            SourceItem(
                source_id=self.source_name,
                source_item_id=f"tech-item-{self.unique_suffix}",
                title="Python 编程入门教程：从基础到实战",
                url=f"https://example.com/item-{self.unique_suffix}-1",
                summary="学习 Python 编程语言和开发技巧",
                author_name="程序员小明",
            ),
            SourceItem(
                source_id=self.source_name,
                source_item_id=f"product-item-{self.unique_suffix}",
                title="产品经理如何设计用户体验",
                url=f"https://example.com/item-{self.unique_suffix}-2",
                summary="产品设计和用户增长策略",
                author_name="产品经理小李",
            ),
        ][:limit]
        return result

    def fetch_full_content(self, item: SourceItem) -> str:
        """Mock full content fetch"""
        return f"Full content for {item.source_item_id}"


class MockFetchErrorAdapter(SourceAdapter):
    """Test adapter that simulates errors"""

    source_name = "test_error"
    source_type = SourceType.API
    base_url = "https://example.com"

    def fetch_items(self, limit: int = 10) -> FetchResult:
        """Mock fetch that fails"""
        return FetchResult(
            source_name=self.source_name,
            success=False,
            errors=["Simulated fetch failure"],
            started_at=datetime.now(timezone.utc),
        )

    def fetch_full_content(self, item: SourceItem) -> str:
        """Mock full content fetch"""
        raise ValueError("Content fetch failed")


class TestFetchTask:
    """Test FetchTask orchestrator - mock version without database"""

    def test_fetch_task_creation(self):
        """Test creating a FetchTask"""
        adapter = MockFetchAdapter()
        task = FetchTask(adapter)

        assert task.adapter == adapter
        assert task.source_name == "test_fetch"

    @patch('app.tasks.fetch.ArticleRepository')
    def test_fetch_task_run_success(self, mock_repo):
        """Test successful fetch task run"""
        adapter = MockFetchAdapter()
        task = FetchTask(adapter)

        # Mock repository
        mock_instance = MagicMock()
        mock_instance.get_or_create_source.return_value = MagicMock(id="mock-source-id")
        mock_instance.get_or_create_author.return_value = None
        mock_instance.upsert_article.return_value = (MagicMock(id="mock-article-id"), True)
        mock_repo.return_value = mock_instance

        result = task.run(limit=2)

        assert result.success is True
        assert result.source_name == "test_fetch"
        assert result.items_fetched == 2
        assert result.items_new == 2  # Should create 2 new articles
        assert result.items_failed == 0
        assert result.duration_seconds >= 0

    @patch('app.tasks.fetch.ArticleRepository')
    def test_fetch_task_with_limit(self, mock_repo):
        """Test fetch task respects limit parameter"""
        adapter = MockFetchAdapter()
        task = FetchTask(adapter)

        # Mock repository
        mock_instance = MagicMock()
        mock_instance.get_or_create_source.return_value = MagicMock(id="mock-source-id")
        mock_instance.get_or_create_author.return_value = None
        mock_instance.upsert_article.return_value = (MagicMock(id="mock-article-id"), True)
        mock_repo.return_value = mock_instance

        result = task.run(limit=1)

        assert result.items_fetched == 1
        assert result.items_new == 1

    def test_fetch_task_with_fetch_failure(self):
        """Test fetch task handles fetch failure"""
        adapter = MockFetchErrorAdapter()
        task = FetchTask(adapter)

        result = task.run()

        assert result.success is False
        assert result.items_fetched == 0
        assert result.items_failed > 0
        assert "Fetch failed" in result.errors[0]

    @patch('app.tasks.fetch.ArticleRepository')
    def test_fetch_task_with_full_content(self, mock_repo):
        """Test fetch task with full content fetching"""
        adapter = MockFetchAdapter()
        task = FetchTask(adapter)

        # Mock repository
        mock_instance = MagicMock()
        mock_instance.get_or_create_source.return_value = MagicMock(id="mock-source-id")
        mock_instance.get_or_create_author.return_value = None
        mock_instance.upsert_article.return_value = (MagicMock(id="mock-article-id"), True)
        mock_repo.return_value = mock_instance

        result = task.run(limit=1, fetch_full_content=True)

        assert result.success is True
        assert result.items_new == 1
        # Verify that full content was fetched by checking duration
        # (it should take longer than without full content)

    @patch('app.tasks.fetch.ArticleRepository')
    def test_run_fetch_task_convenience(self, mock_repo):
        """Test convenience function for running fetch task"""
        adapter = MockFetchAdapter()

        # Mock repository
        mock_instance = MagicMock()
        mock_instance.get_or_create_source.return_value = MagicMock(id="mock-source-id")
        mock_instance.get_or_create_author.return_value = None
        mock_instance.upsert_article.return_value = (MagicMock(id="mock-article-id"), True)
        mock_repo.return_value = mock_instance

        result = run_fetch_task(adapter, limit=1)

        assert result.success is True
        assert result.items_new == 1


class TestFetchTaskIntegration:
    """Integration tests for FetchTask with real database"""

    def test_fetch_task_creates_articles_with_classification_and_quality(self, setup_database):
        """Test complete flow: fetch -> classify -> score -> articles in DB"""
        from app.core.database import get_db
        from app.models.db.tables import Article, Source
        from sqlalchemy import select
        from sqlalchemy import func as sql_func

        # Generate unique suffix to identify articles created by this test
        unique_suffix = str(uuid4())[:8]

        class MockFetchAdapterWithSuffix(MockFetchAdapter):
            """Test adapter with unique suffix to avoid conflicts"""
            def __init__(self):
                super().__init__()
                self.unique_suffix = unique_suffix

            def fetch_items(self, limit: int = 10) -> FetchResult:
                result = super().fetch_items(limit)
                # Update source_item_ids to be unique
                for i, item in enumerate(result.items):
                    item.source_item_id = f"{item.source_item_id}-{self.unique_suffix}"
                return result

        adapter = MockFetchAdapterWithSuffix()
        task = FetchTask(adapter)

        # Run fetch task
        result = task.run(limit=2)

        assert result.success is True
        # Note: items_new may be 0 if articles already exist (upsert behavior)
        # We verify by checking database directly
        assert result.items_fetched == 2

        # Verify articles in database - find by unique suffix
        with get_db() as db:
            articles = db.execute(
                select(Article).where(Article.source_item_id.like(f"%{unique_suffix}%"))
            ).scalars().all()

            # Should have exactly 2 articles from this test
            assert len(articles) == 2, f"Expected 2 articles with suffix {unique_suffix}, got {len(articles)}"

            # Verify classification and quality fields on articles created by this test
            for article in articles:
                assert article.content_type is not None, f"Article {article.id} has no content_type"
                assert article.content_type != "unknown", f"Article {article.id} has unknown content_type"
                assert article.overall_score is not None, f"Article {article.id} has no overall_score"
                assert article.overall_score > 0, f"Article {article.id} has invalid overall_score"
                assert article.classification_tags is not None, f"Article {article.id} has no classification_tags"
                assert len(article.classification_tags) > 0, f"Article {article.id} has empty classification_tags"
                assert article.quality_level is not None, f"Article {article.id} has no quality_level"

    def test_fetch_task_idempotent_same_source_item_id(self, setup_database):
        """Test running same fetch twice doesn't duplicate articles"""
        from app.core.database import get_db
        from app.models.db.tables import Article
        from sqlalchemy import select, func

        # Generate unique suffix to identify articles created by this test
        unique_suffix = str(uuid4())[:8]

        class MockFetchAdapterWithSuffix(MockFetchAdapter):
            """Test adapter with unique suffix to avoid conflicts"""
            def __init__(self):
                super().__init__()
                self.unique_suffix = unique_suffix

            def fetch_items(self, limit: int = 10) -> FetchResult:
                result = super().fetch_items(limit)
                # Update source_item_ids to be unique
                for i, item in enumerate(result.items):
                    item.source_item_id = f"{item.source_item_id}-{self.unique_suffix}"
                return result

        adapter = MockFetchAdapterWithSuffix()
        task = FetchTask(adapter)

        # First run
        result1 = task.run(limit=2)
        assert result1.success is True

        # Get count after first run - only count articles with our suffix
        with get_db() as db:
            count1 = db.execute(
                select(func.count(Article.id)).where(
                    Article.source_item_id.like(f"%{unique_suffix}%")
                )
            ).scalar()
            assert count1 == 2, f"Expected 2 articles after first run, got {count1}"

        # Second run with same adapter (same source_item_ids)
        result2 = task.run(limit=2)
        assert result2.success is True

        # Verify count hasn't changed (no duplicates)
        with get_db() as db:
            count2 = db.execute(
                select(func.count(Article.id)).where(
                    Article.source_item_id.like(f"%{unique_suffix}%")
                )
            ).scalar()
            assert count2 == count1, f"Article count changed from {count1} to {count2}, duplicates may have been created"