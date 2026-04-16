"""
Tests for Content Classifier
"""

import pytest
from datetime import datetime, timezone

from app.models.schemas.source import SourceItem
from app.models.schemas.content import ContentType, QualityLevel
from app.services.intelligence.classifier import ContentClassifier


class TestContentClassifier:
    """Test Content Classifier"""

    def setup_method(self):
        """Setup test fixtures"""
        self.classifier = ContentClassifier()

    def test_classify_technology_content(self):
        """Test classification of technology content"""
        source_item = SourceItem(
            source_id="sspai",
            source_item_id="123",
            title="Python异步编程最佳实践",
            url="https://sspai.com/python-async",
            summary="介绍Python中的async/await机制和使用场景",
            author_name="工程师",
            publish_time=datetime(2024, 1, 1, tzinfo=timezone.utc),
            tags=["编程", "Python"],
        )

        classification = self.classifier.classify(source_item)

        assert classification.content_type == ContentType.TECHNOLOGY
        assert classification.confidence > 0.5
        assert "technology" in classification.tags
        assert "from_sspai" in classification.tags
        assert "python" in classification.subcategories

    def test_classify_product_content(self):
        """Test classification of product content"""
        source_item = SourceItem(
            source_id="sspai",
            source_item_id="456",
            title="产品设计：如何打造优秀的用户体验",
            url="https://sspai.com/product-design",
            summary="分享产品设计中的关键原则和方法",
            author_name="产品经理",
            publish_time=datetime(2024, 1, 2, tzinfo=timezone.utc),
        )

        classification = self.classifier.classify(source_item)

        assert classification.content_type == ContentType.PRODUCT
        assert classification.confidence > 0.5
        assert "product" in classification.tags

    def test_classify_culture_content(self):
        """Test classification of culture content"""
        source_item = SourceItem(
            source_id="douban",
            source_item_id="789",
            title="《人类简史》读书笔记",
            url="https://book.douban.com/review/123",
            summary="尤瓦尔·赫拉利的思考启发",
            author_name="读书爱好者",
            publish_time=datetime(2024, 1, 3, tzinfo=timezone.utc),
        )

        classification = self.classifier.classify(source_item)

        assert classification.content_type == ContentType.CULTURE
        assert classification.confidence > 0.5
        assert "culture" in classification.tags
        assert "books" in classification.subcategories

    def test_classify_discussion_content(self):
        """Test classification of discussion content"""
        source_item = SourceItem(
            source_id="v2ex",
            source_item_id="101",
            title="大家如何看待这个技术方案？",
            url="https://v2ex.com/topic/123",
            summary="想听听大家的意见",
            publish_time=datetime(2024, 1, 4, tzinfo=timezone.utc),
        )

        classification = self.classifier.classify(source_item)

        assert classification.content_type == ContentType.DISCUSSION
        assert classification.confidence > 0.5
        assert "discussion" in classification.tags

    def test_classify_with_content_text(self):
        """Test classification with full content text"""
        source_item = SourceItem(
            source_id="sspai",
            source_item_id="202",
            title="机器学习入门指南",
            url="https://sspai.com/ml-guide",
            summary="从零开始学习机器学习",
            publish_time=datetime(2024, 1, 5, tzinfo=timezone.utc),
        )

        content = """
        机器学习是人工智能的一个重要分支。本文将介绍：

        1. 什么是机器学习
        2. 监督学习与无监督学习
        3. 常见算法介绍
        4. 实践案例分析

        机器学习算法包括决策树、神经网络等。
        """

        classification = self.classifier.classify(source_item, content)

        assert classification.content_type == ContentType.TECHNOLOGY
        assert classification.confidence > 0.6  # Higher with content
        assert classification.metadata.paragraph_count == 6  # Should be extracted from content

    def test_classify_unknown_content(self):
        """Test classification of unknown content"""
        source_item = SourceItem(
            source_id="unknown",
            source_item_id="303",
            title="一些随机内容",
            url="https://example.com",
            summary="没有明显特征的内容",
            publish_time=datetime(2024, 1, 6, tzinfo=timezone.utc),
        )

        classification = self.classifier.classify(source_item)

        assert classification.content_type == ContentType.UNKNOWN
        assert classification.confidence == 0.0

    def test_source_specific_scoring(self):
        """Test source-specific classification bias"""
        # Same content from different sources
        tech_content = SourceItem(
            source_id="v2ex",
            source_item_id="404",
            title="Python编程问题",
            url="https://v2ex.com/python",
            summary="讨论Python开发技巧",
        )

        classification = self.classifier.classify(tech_content)

        # V2EX should have higher discussion bias
        assert classification.content_type in [ContentType.DISCUSSION, ContentType.TECHNOLOGY]

    def test_author_influence(self):
        """Test author influence on classification"""
        source_item = SourceItem(
            source_id="unknown",
            source_item_id="505",
            title="产品思考",
            url="https://example.com/product",
            summary="关于产品的一些想法",
            author_name="产品经理",
        )

        classification = self.classifier.classify(source_item)

        # Author should influence classification
        assert classification.content_type == ContentType.PRODUCT

    def test_extract_text_features(self):
        """Test text feature extraction"""
        text = "Python编程技术教程，如何实现机器学习算法？"
        features = self.classifier._extract_text_features(text)

        assert features['technology'] > 0  # Should detect technology keywords
        assert features['has_question'] == 1  # Has question mark
        assert features['paragraph_count'] == 1  # Single paragraph

    def test_minimal_content(self):
        """Test classification with minimal content"""
        source_item = SourceItem(
            source_id="sspai",
            source_item_id="606",
            title="短标题",
            url="https://sspai.com/short",
        )

        classification = self.classifier.classify(source_item)

        # Should still classify based on title
        assert classification.content_type is not None

    def test_empty_content(self):
        """Test classification with empty content"""
        source_item = SourceItem(
            source_id="sspai",
            source_item_id="707",
            title="",
            url="https://sspai.com/empty",
        )

        classification = self.classifier.classify(source_item)

        assert classification.content_type == ContentType.UNKNOWN
        assert classification.confidence == 0.0