"""
Integration tests for FetchTask with classification and quality scoring

These tests verify that FetchTask correctly integrates ContentClassifier
and ContentQualityScorer into the data flow.
"""

import pytest
from datetime import datetime, timezone
from unittest.mock import patch, MagicMock

from app.models.schemas.source import SourceType, SourceItem, FetchResult
from app.models.schemas.content import ContentType, QualityLevel
from app.services.sources.base import SourceAdapter
from app.tasks.fetch import FetchTask, run_fetch_task


class MockTechAdapter(SourceAdapter):
    """Test adapter that returns technology content"""

    source_name = "test_tech"
    source_type = SourceType.API
    base_url = "https://example.com"

    def fetch_items(self, limit: int = 10) -> FetchResult:
        """Mock fetch that returns tech items"""
        result = FetchResult(
            source_name=self.source_name,
            success=True,
            items_fetched=min(limit, 2),
            started_at=datetime.now(timezone.utc),
        )
        result.items = [
            SourceItem(
                source_id=self.source_name,
                source_item_id="tech-1",
                title="Python异步编程指南",
                url="https://example.com/python-async",
                summary="介绍Python中的async/await机制和使用场景",
                author_name="工程师张三",
                publish_time=datetime.now(timezone.utc),
                tags=["编程", "Python"],
            ),
            SourceItem(
                source_id=self.source_name,
                source_item_id="tech-2",
                title="深入理解机器学习算法",
                url="https://example.com/ml-algorithms",
                summary="系统讲解常见机器学习算法的原理和实现",
                author_name="AI研究员",
                publish_time=datetime.now(timezone.utc),
                tags=["AI", "机器学习"],
            ),
        ]
        return result

    def fetch_full_content(self, item: SourceItem) -> str:
        """Mock full content fetch"""
        return f"""
# {item.title}

这是一篇关于{item.summary}的技术文章。

## 核心概念

详细介绍各种技术概念和实现细节。

```python
def example():
    pass
```

## 实践应用

1. 第一步
2. 第二步
3. 第三步

## 总结

本文总结了关键技术点。

参考来源：https://docs.python.org
"""


class MockProductAdapter(SourceAdapter):
    """Test adapter that returns product content"""

    source_name = "test_product"
    source_type = SourceType.API
    base_url = "https://example.com"

    def fetch_items(self, limit: int = 10) -> FetchResult:
        result = FetchResult(
            source_name=self.source_name,
            success=True,
            items_fetched=1,
            started_at=datetime.now(timezone.utc),
        )
        result.items = [
            SourceItem(
                source_id=self.source_name,
                source_item_id="product-1",
                title="产品设计：打造优秀用户体验",
                url="https://example.com/product-design",
                summary="分享产品设计的关键原则和方法",
                author_name="产品经理",
                publish_time=datetime.now(timezone.utc),
            ),
        ]
        return result

    def fetch_full_content(self, item: SourceItem) -> str:
        return f"Full content for {item.source_item_id}"


class MockClickbaitAdapter(SourceAdapter):
    """Test adapter that returns low-quality clickbait content"""

    source_name = "test_clickbait"
    source_type = SourceType.API
    base_url = "https://example.com"

    def fetch_items(self, limit: int = 10) -> FetchResult:
        result = FetchResult(
            source_name=self.source_name,
            success=True,
            items_fetched=1,
            started_at=datetime.now(timezone.utc),
        )
        result.items = [
            SourceItem(
                source_id=self.source_name,
                source_item_id="clickbait-1",
                title="震惊！99%的人不知道的秘密！！！",
                url="https://example.com/clickbait",
                summary="",
                author_name="匿名用户",
                publish_time=datetime.now(timezone.utc) - __import__('datetime').timedelta(days=365),
            ),
        ]
        return result

    def fetch_full_content(self, item: SourceItem) -> str:
        return "这是一个很短的内容。没有结构。没有深度。"


class TestFetchTaskClassificationIntegration:
    """Test FetchTask integrates with ContentClassifier correctly"""

    @pytest.fixture(autouse=True)
    def skip_if_no_db(self, database_available):
        """These tests use mocks, so they don't need real database"""
        pass

    @patch('app.tasks.fetch.ArticleRepository')
    def test_fetch_task_classifies_tech_content(self, mock_repo):
        """Test that tech content is correctly classified"""
        adapter = MockTechAdapter()
        task = FetchTask(adapter)

        # Mock repository
        mock_instance = MagicMock()
        mock_instance.get_or_create_source.return_value = MagicMock(id="mock-source-id")
        mock_instance.get_or_create_author.return_value = None
        mock_instance.upsert_article.return_value = (MagicMock(id="mock-article-id"), True)
        mock_repo.return_value = mock_instance

        result = task.run(limit=1)

        assert result.success is True
        assert result.items_new >= 1  # Adapter may return up to limit items

        # Verify upsert_article was called with classification data
        call_args = mock_instance.upsert_article.call_args
        assert call_args is not None
        kwargs = call_args.kwargs or call_args[1]

        # Check classification was passed
        assert 'classification' in kwargs
        classification = kwargs['classification']
        assert classification is not None
        assert classification['content_type'] == ContentType.TECHNOLOGY.value
        assert classification['confidence'] > 0.0
        assert 'technology' in classification['tags']
        assert 'from_test_tech' in classification['tags']

    @patch('app.tasks.fetch.ArticleRepository')
    def test_fetch_task_classifies_product_content(self, mock_repo):
        """Test that product content is correctly classified"""
        adapter = MockProductAdapter()
        task = FetchTask(adapter)

        # Mock repository
        mock_instance = MagicMock()
        mock_instance.get_or_create_source.return_value = MagicMock(id="mock-source-id")
        mock_instance.get_or_create_author.return_value = None
        mock_instance.upsert_article.return_value = (MagicMock(id="mock-article-id"), True)
        mock_repo.return_value = mock_instance

        result = task.run(limit=1)

        assert result.success is True

        # Verify classification
        call_args = mock_instance.upsert_article.call_args
        kwargs = call_args.kwargs or call_args[1]
        classification = kwargs['classification']

        assert classification['content_type'] == ContentType.PRODUCT.value
        assert 'product' in classification['tags']

    @patch('app.tasks.fetch.ArticleRepository')
    def test_fetch_task_with_disabled_classification(self, mock_repo):
        """Test that classification can be disabled"""
        adapter = MockTechAdapter()
        task = FetchTask(adapter, enable_classification=False, enable_quality_scoring=False)

        # Mock repository
        mock_instance = MagicMock()
        mock_instance.get_or_create_source.return_value = MagicMock(id="mock-source-id")
        mock_instance.get_or_create_author.return_value = None
        mock_instance.upsert_article.return_value = (MagicMock(id="mock-article-id"), True)
        mock_repo.return_value = mock_instance

        result = task.run(limit=1)

        assert result.success is True

        # Verify classification and quality were NOT passed
        call_args = mock_instance.upsert_article.call_args
        kwargs = call_args.kwargs or call_args[1]

        assert kwargs.get('classification') is None
        assert kwargs.get('quality') is None


class TestFetchTaskQualityIntegration:
    """Test FetchTask integrates with ContentQualityScorer correctly"""

    @patch('app.tasks.fetch.ArticleRepository')
    def test_fetch_task_scores_high_quality_content(self, mock_repo):
        """Test that high quality content gets good scores"""
        adapter = MockTechAdapter()
        task = FetchTask(adapter)

        # Mock repository
        mock_instance = MagicMock()
        mock_instance.get_or_create_source.return_value = MagicMock(id="mock-source-id")
        mock_instance.get_or_create_author.return_value = None
        mock_instance.upsert_article.return_value = (MagicMock(id="mock-article-id"), True)
        mock_repo.return_value = mock_instance

        result = task.run(limit=1, fetch_full_content=True)

        assert result.success is True

        # Verify quality data was passed
        call_args = mock_instance.upsert_article.call_args
        kwargs = call_args.kwargs or call_args[1]

        assert 'quality' in kwargs
        quality = kwargs['quality']
        assert quality is not None

        # High quality content should have good scores
        assert quality['overall_score'] > 0.5
        assert quality['quality_level'] in [QualityLevel.HIGH.value, QualityLevel.MEDIUM.value]
        assert quality['completeness_score'] > 0.0
        assert quality['structure_score'] > 0.0
        assert quality['depth_score'] > 0.0
        assert quality['is_clickbait'] is False
        assert quality['is_original'] is True

    @patch('app.tasks.fetch.ArticleRepository')
    def test_fetch_task_scores_clickbait_content(self, mock_repo):
        """Test that clickbait content is detected"""
        adapter = MockClickbaitAdapter()
        task = FetchTask(adapter)

        # Mock repository
        mock_instance = MagicMock()
        mock_instance.get_or_create_source.return_value = MagicMock(id="mock-source-id")
        mock_instance.get_or_create_author.return_value = None
        mock_instance.upsert_article.return_value = (MagicMock(id="mock-article-id"), True)
        mock_repo.return_value = mock_instance

        result = task.run(limit=1)

        assert result.success is True

        # Verify quality data
        call_args = mock_instance.upsert_article.call_args
        kwargs = call_args.kwargs or call_args[1]

        quality = kwargs['quality']
        assert quality['is_clickbait'] is True
        # Low quality content should have lower scores
        assert quality['overall_score'] < 0.7

    @patch('app.tasks.fetch.ArticleRepository')
    def test_fetch_task_quality_score_components(self, mock_repo):
        """Test that all quality score components are present"""
        adapter = MockTechAdapter()
        task = FetchTask(adapter)

        # Mock repository
        mock_instance = MagicMock()
        mock_instance.get_or_create_source.return_value = MagicMock(id="mock-source-id")
        mock_instance.get_or_create_author.return_value = None
        mock_instance.upsert_article.return_value = (MagicMock(id="mock-article-id"), True)
        mock_repo.return_value = mock_instance

        result = task.run(limit=1)

        assert result.success is True

        # Verify all score components are present
        call_args = mock_instance.upsert_article.call_args
        kwargs = call_args.kwargs or call_args[1]

        quality = kwargs['quality']
        expected_keys = [
            'overall_score', 'quality_level',
            'completeness_score', 'structure_score', 'depth_score',
            'credibility_score', 'engagement_score',
            'is_original', 'has_citation', 'is_clickbait'
        ]
        for key in expected_keys:
            assert key in quality, f"Missing quality key: {key}"


class TestFetchTaskEndToEnd:
    """End-to-end tests for the complete fetch + classify + score flow"""

    @patch('app.tasks.fetch.ArticleRepository')
    def test_complete_data_flow(self, mock_repo):
        """Test the complete fetch -> classify -> score -> store flow"""
        adapter = MockTechAdapter()
        task = FetchTask(adapter)

        # Mock repository to track all calls
        mock_instance = MagicMock()
        mock_instance.get_or_create_source.return_value = MagicMock(id="mock-source-id")
        mock_instance.get_or_create_author.return_value = None
        mock_instance.upsert_article.return_value = (MagicMock(id="mock-article-id"), True)
        mock_repo.return_value = mock_instance

        result = task.run(limit=2)

        # Verify result
        assert result.success is True
        assert result.items_fetched == 2
        assert result.items_new == 2
        assert result.items_failed == 0

        # Verify upsert_article was called twice with correct data
        assert mock_instance.upsert_article.call_count == 2

        # Check first call
        first_call = mock_instance.upsert_article.call_args_list[0]
        kwargs = first_call.kwargs or first_call[1]

        assert 'classification' in kwargs
        assert 'quality' in kwargs
        assert kwargs['classification']['content_type'] == ContentType.TECHNOLOGY.value
        assert kwargs['quality']['overall_score'] > 0.0

    @patch('app.tasks.fetch.ArticleRepository')
    def test_run_fetch_task_convenience_function(self, mock_repo):
        """Test the convenience function with classification and quality"""
        adapter = MockTechAdapter()

        # Mock repository
        mock_instance = MagicMock()
        mock_instance.get_or_create_source.return_value = MagicMock(id="mock-source-id")
        mock_instance.get_or_create_author.return_value = None
        mock_instance.upsert_article.return_value = (MagicMock(id="mock-article-id"), True)
        mock_repo.return_value = mock_instance

        result = run_fetch_task(
            adapter,
            limit=1,
            enable_classification=True,
            enable_quality_scoring=True
        )

        assert result.success is True
        assert result.items_new >= 1  # Adapter may return up to limit items

        # Verify classification and quality were passed
        call_args = mock_instance.upsert_article.call_args
        kwargs = call_args.kwargs or call_args[1]

        assert kwargs['classification'] is not None
        assert kwargs['quality'] is not None
