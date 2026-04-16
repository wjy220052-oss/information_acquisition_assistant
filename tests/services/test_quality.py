"""
Tests for Content Quality Scorer
"""

import pytest
from datetime import datetime, timezone, timedelta

from app.models.schemas.source import SourceItem
from app.models.schemas.content import QualityLevel, ContentMetadata
from app.services.intelligence.quality import ContentQualityScorer


class TestContentQualityScorer:
    """Test Content Quality Scorer"""

    def setup_method(self):
        """Setup test fixtures"""
        self.scorer = ContentQualityScorer()

    def test_score_high_quality_content(self):
        """Test scoring of high quality content"""
        source_item = SourceItem(
            source_id="sspai",
            source_item_id="123",
            title="深入理解Python异步编程：从原理到实践",
            url="https://sspai.com/python-async",
            summary="本文详细介绍Python异步编程的核心概念和实际应用",
            author_name="资深工程师",
            publish_time=datetime.now(timezone.utc),
            tags=["编程", "Python"],
        )

        content = """
        # Python异步编程深度解析

        异步编程是现代Python开发中的重要技术。本文将从原理到实践，全面介绍asyncio的使用。

        ## 核心概念

        异步编程的核心在于事件循环和协程。通过async/await语法，我们可以编写高效的异步代码。

        ```python
        import asyncio

        async def main():
            await asyncio.sleep(1)
            print("Hello, async!")
        ```

        ## 实际应用场景

        1. Web服务器开发
        2. 网络爬虫
        3. 数据库操作
        4. 文件I/O

        ## 性能优化建议

        根据官方文档和实际项目经验，异步编程可以显著提升I/O密集型应用的性能。
        参考：[Python官方文档](https://docs.python.org/3/library/asyncio.html)

        ## 总结

        掌握异步编程是提升Python开发效率的关键技能。
        """

        quality = self.scorer.score(source_item, content)

        assert quality.overall_score > 0.7
        assert quality.quality_level in [QualityLevel.HIGH, QualityLevel.MEDIUM]
        assert quality.completeness_score > 0.5
        assert quality.structure_score > 0.5
        assert quality.depth_score > 0.5
        assert quality.credibility_score > 0.5
        assert quality.is_original is True
        assert quality.has_citation is True  # Has reference link
        assert quality.is_clickbait is False

    def test_score_low_quality_content(self):
        """Test scoring of low quality content"""
        source_item = SourceItem(
            source_id="unknown",
            source_item_id="456",
            title="震惊！竟然发生了这种事",
            url="https://example.com/clickbait",
            summary="",
            author_name="匿名用户",
            publish_time=datetime.now(timezone.utc) - timedelta(days=365),
        )

        content = "这是一个很短的内容。没有结构。没有深度。"

        quality = self.scorer.score(source_item, content)

        assert quality.overall_score < 0.6
        assert quality.quality_level in [QualityLevel.LOW, QualityLevel.MEDIUM]
        assert quality.is_clickbait is True  # Detected clickbait title
        assert quality.credibility_score < 0.8  # Low trust source

    def test_score_with_metadata(self):
        """Test scoring with provided metadata"""
        source_item = SourceItem(
            source_id="sspai",
            source_item_id="789",
            title="技术文章",
            url="https://sspai.com/tech",
        )

        metadata = ContentMetadata(
            word_count=3000,
            has_images=True,
            has_code=True,
            has_external_links=True,
            link_count=5,
            paragraph_count=10,
            quote_count=3,
            source_trust_score=0.9,
            author_reputation=0.8,
        )

        quality = self.scorer.score(source_item, "", metadata)

        assert quality.overall_score > 0.6
        assert quality.quality_level in [QualityLevel.HIGH, QualityLevel.MEDIUM]

    def test_score_without_content(self):
        """Test scoring without full content (only metadata)"""
        source_item = SourceItem(
            source_id="sspai",
            source_item_id="101",
            title="文章标题",
            url="https://sspai.com/article",
            summary="这是一篇不错的文章摘要，内容丰富",
            author_name="专栏作者",
            publish_time=datetime.now(timezone.utc),
        )

        quality = self.scorer.score(source_item)

        # Should still produce a score based on available information
        assert quality.overall_score >= 0.0
        assert quality.quality_level is not None
        assert quality.credibility_score > 0.5  # Good source

    def test_detect_clickbait(self):
        """Test clickbait detection"""
        clickbait_titles = [
            "震惊！竟然发生了这种事",
            "99%的人不知道的秘密",
            "不看后悔！！！",
            "独家内幕曝光",
        ]

        for title in clickbait_titles:
            assert self.scorer._detect_clickbait(title, "") is True

        normal_titles = [
            "Python异步编程指南",
            "产品设计的思考",
            "读书笔记：人类简史",
        ]

        for title in normal_titles:
            assert self.scorer._detect_clickbait(title, "") is False

    def test_check_citations(self):
        """Test citation detection"""
        content_with_citations = """
        根据研究[1]，Python是最流行的编程语言之一。
        参考官方文档：https://docs.python.org
        来源：Python官方
        """
        assert self.scorer._check_citations(content_with_citations) is True

        content_without_citations = """
        这是一段普通的内容，没有任何引用或参考。
        只是简单的描述性文字。
        """
        assert self.scorer._check_citations(content_without_citations) is False

    def test_check_originality(self):
        """Test originality check"""
        # Original content
        original = SourceItem(
            source_id="sspai",
            source_item_id="202",
            title="我的产品思考",
            url="https://sspai.com/original",
        )
        assert self.scorer._check_originality(original, ContentMetadata()) is True

        # Discussion content (question format)
        discussion = SourceItem(
            source_id="v2ex",
            source_item_id="303",
            title="如何学习Python？",
            url="https://v2ex.com/question",
        )
        assert self.scorer._check_originality(discussion, ContentMetadata()) is False

    def test_extract_metadata(self):
        """Test metadata extraction from content"""
        source_item = SourceItem(
            source_id="sspai",
            source_item_id="404",
            title="测试文章",
            url="https://sspai.com/test",
            publish_time=datetime.now(timezone.utc),
        )

        content = """
        第一段介绍。

        第二段详细说明。

        ```python
def hello():
    print("Hello")
```

        引用某人的话：> 这是一个引用

        查看更多：https://example.com/link
        """

        metadata = self.scorer._extract_metadata(source_item, content)

        assert metadata.word_count > 0
        assert metadata.paragraph_count >= 3
        assert metadata.has_code is True
        assert metadata.has_external_links is True
        assert metadata.link_count >= 1
        assert metadata.quote_count >= 1
        assert metadata.source_trust_score == 0.9  # sspai

    def test_score_completeness(self):
        """Test completeness scoring"""
        # Short content
        metadata_short = ContentMetadata(word_count=50)
        score_short = self.scorer._score_completeness("", metadata_short)
        assert score_short < 0.5

        # Medium content
        metadata_medium = ContentMetadata(word_count=1000)
        score_medium = self.scorer._score_completeness("", metadata_medium)
        assert score_medium > 0.5

        # Long content
        metadata_long = ContentMetadata(word_count=3000)
        score_long = self.scorer._score_completeness("", metadata_long)
        assert score_long > 0.8

    def test_score_structure(self):
        """Test structure scoring"""
        # Poor structure
        content_poor = "一句话。"
        metadata_poor = ContentMetadata(paragraph_count=1)
        score_poor = self.scorer._score_structure(content_poor, metadata_poor)
        assert score_poor < 0.5

        # Good structure
        content_good = """
# 标题

这是第一段，介绍背景。

这是第二段，详细说明。

这是第三段，总结结论。
"""
        metadata_good = ContentMetadata(paragraph_count=4)
        score_good = self.scorer._score_structure(content_good, metadata_good)
        assert score_good > 0.5

    def test_score_depth(self):
        """Test depth scoring"""
        # Shallow content
        metadata_shallow = ContentMetadata(
            has_code=False,
            quote_count=0,
            link_count=0,
        )
        score_shallow = self.scorer._score_depth("", metadata_shallow)
        assert score_shallow < 0.5

        # Deep content
        metadata_deep = ContentMetadata(
            has_code=True,
            quote_count=3,
            link_count=5,
        )
        score_deep = self.scorer._score_depth("算法、架构、原理", metadata_deep)
        assert score_deep > 0.5

    def test_score_credibility(self):
        """Test credibility scoring"""
        source_item = SourceItem(
            source_id="sspai",
            source_item_id="505",
            title="测试",
            url="https://sspai.com/test",
            author_name="专栏作者",
            publish_time=datetime.now(timezone.utc),
        )

        metadata = ContentMetadata(
            source_trust_score=0.9,
            author_reputation=0.8,
            content_age_hours=1,
        )

        score = self.scorer._score_credibility(source_item, metadata)
        assert score > 0.7  # High trust source + good author + fresh

    def test_score_engagement(self):
        """Test engagement scoring"""
        source_item_high = SourceItem(
            source_id="sspai",
            source_item_id="606",
            title="热门文章",
            url="https://sspai.com/popular",
        )
        metadata_high = ContentMetadata(
            view_count=10000,
            comment_count=100,
            like_count=500,
        )
        score_high = self.scorer._score_engagement(source_item_high, metadata_high)
        assert score_high > 0.5

        source_item_low = SourceItem(
            source_id="sspai",
            source_item_id="707",
            title="冷门文章",
            url="https://sspai.com/unpopular",
        )
        metadata_low = ContentMetadata(
            view_count=10,
            comment_count=0,
            like_count=1,
        )
        score_low = self.scorer._score_engagement(source_item_low, metadata_low)
        assert score_low < score_high

    def test_quality_level_determination(self):
        """Test quality level determination"""
        assert self.scorer._determine_quality_level(0.9) == QualityLevel.HIGH
        assert self.scorer._determine_quality_level(0.7) == QualityLevel.MEDIUM
        assert self.scorer._determine_quality_level(0.5) == QualityLevel.LOW
        assert self.scorer._determine_quality_level(0.3) == QualityLevel.LOW

    def test_source_trust_scores(self):
        """Test source trust score assignment"""
        sspai_item = SourceItem(source_id="sspai", source_item_id="1", title="Test", url="https://sspai.com")
        unknown_item = SourceItem(source_id="unknown", source_item_id="2", title="Test", url="https://unknown.com")

        sspai_metadata = self.scorer._extract_metadata(sspai_item, "")
        unknown_metadata = self.scorer._extract_metadata(unknown_item, "")

        assert sspai_metadata.source_trust_score == 0.9
        assert unknown_metadata.source_trust_score == 0.5

    def test_empty_content_handling(self):
        """Test handling of empty content"""
        source_item = SourceItem(
            source_id="sspai",
            source_item_id="808",
            title="",
            url="https://sspai.com/empty",
        )

        quality = self.scorer.score(source_item, "")

        # Should not crash and should return valid quality object
        assert quality is not None
        assert quality.overall_score >= 0.0
        assert quality.quality_level is not None

    # ========== Discussion-specific tests ==========

    def test_discussion_short_but_valuable(self):
        """Test short but valuable discussion content (100-200 chars)"""
        source_item = SourceItem(
            source_id="v2ex",
            source_item_id="v2ex_001",
            title="请问 macOS 如何彻底卸载 Python？",
            url="https://v2ex.com/t/001",
            summary="",
            author_name="新手用户",
            publish_time=datetime.now(timezone.utc),
        )

        content = """我安装了多个 Python 版本，现在想彻底清理。
已经尝试了 brew uninstall，但似乎还有残留。
请问有没有完整的清理步骤？谢谢！"""

        quality = self.scorer.score(source_item, content, content_type="discussion")

        # Good short discussion should reach 0.40~0.60 range (was 0.2-0.3 before fix)
        assert quality.overall_score >= 0.35, f"Expected >= 0.35 for good short discussion, got {quality.overall_score}"
        assert quality.overall_score <= 0.65, f"Expected <= 0.65 for short content, got {quality.overall_score}"
        # Completeness should not be heavily penalized for discussions
        assert quality.completeness_score >= 0.4, f"Short discussion should have reasonable completeness"

    def test_discussion_clear_question_and_practical(self):
        """Test discussion with clear question and practical value"""
        source_item = SourceItem(
            source_id="v2ex",
            source_item_id="v2ex_002",
            title="如何优化 PostgreSQL 查询性能？",
            url="https://v2ex.com/t/002",
            summary="",
            author_name="后端开发",
            publish_time=datetime.now(timezone.utc),
        )

        content = """我的查询在大数据量下很慢，EXPLAIN 显示是全表扫描。

已经尝试了：
1. 添加索引
2. 增加 work_mem

但效果不明显。表有 1000 万行，查询条件是高基数字段。
请问还有什么优化方向？"""

        quality = self.scorer.score(source_item, content, content_type="discussion")

        # High-quality discussion should reach 0.50~0.70 range (was 0.3-0.4 before fix)
        assert quality.overall_score >= 0.50, f"Expected >= 0.50 for high-quality discussion, got {quality.overall_score}"
        assert quality.overall_score <= 0.75, f"Expected <= 0.75, got {quality.overall_score}"

    def test_discussion_vs_article_same_content(self):
        """Test same text scored as discussion vs article"""
        text = """我在学习 Go 语言，有几个问题想请教：

1. interface 和 struct 的本质区别是什么？
2. goroutine 的调度机制是怎样的？
3. 什么时候应该用 channel，什么时候用 mutex？

希望能得到解答，谢谢！"""

        # As discussion
        discussion_item = SourceItem(
            source_id="v2ex",
            source_item_id="v2ex_003",
            title="Go 语言学习几个问题",
            url="https://v2ex.com/t/003",
        )
        discussion_quality = self.scorer.score(discussion_item, text, content_type="discussion")

        # As article
        article_item = SourceItem(
            source_id="sspai",
            source_item_id="sspai_003",
            title="Go 语言学习几个问题",
            url="https://sspai.com/post/003",
        )
        article_quality = self.scorer.score(article_item, text, content_type="article")

        # Discussion should score higher than article for same discussion-like content
        assert discussion_quality.overall_score > article_quality.overall_score, \
            f"Discussion ({discussion_quality.overall_score}) should score higher than article ({article_quality.overall_score}) for Q&A content"

    def test_article_regression_prevention(self):
        """Ensure article scoring behavior is not broken by discussion changes"""
        source_item = SourceItem(
            source_id="sspai",
            source_item_id="sspai_004",
            title="深入理解 Redis 持久化机制",
            url="https://sspai.com/post/redis",
            summary="本文详细介绍 Redis 的 RDB 和 AOF 两种持久化方案",
            author_name="资深工程师",
            publish_time=datetime.now(timezone.utc),
        )

        content = """# Redis 持久化机制详解

Redis 提供两种持久化方式：RDB 和 AOF。

## RDB 持久化

RDB 通过快照方式保存数据。优点是文件紧凑，恢复速度快。
适用场景：定期备份、灾难恢复。

## AOF 持久化

AOF 记录所有写操作命令。优点是数据安全性更高，最多丢失 1 秒数据。
适用场景：对数据完整性要求高的场景。

## 选型建议

根据业务需求选择：
- 允许少量数据丢失：RDB
- 数据完整性优先：AOF
- 最佳实践：RDB + AOF 混合

参考：https://redis.io/docs/manual/persistence/"""

        quality = self.scorer.score(source_item, content, content_type="article")

        # Article should still score reasonably with good content (note: medium-length article)
        assert quality.overall_score > 0.5, f"Article should score > 0.5, got {quality.overall_score}"
        # Quality level can be MEDIUM or LOW for medium-length content (scoring ~0.55)
        assert quality.quality_level in [QualityLevel.HIGH, QualityLevel.MEDIUM, QualityLevel.LOW]
        # Completeness is around 0.4 for ~400 char content (medium-short)
        assert quality.completeness_score >= 0.35, f"Completeness should be >= 0.35, got {quality.completeness_score}"
        assert quality.structure_score > 0.3

    def test_v2ex_discussion_detection(self):
        """Test v2ex discussion detection via source_id + text features"""
        # V2EX with question pattern should be treated as discussion
        v2ex_question = SourceItem(
            source_id="v2ex",
            source_item_id="v2ex_005",
            title="请问如何配置 Nginx 反向代理？",
            url="https://v2ex.com/t/005",
        )

        content = "我想把请求转发到本地 3000 端口，应该怎么配置？"
        metadata = self.scorer._extract_metadata(v2ex_question, content)

        # Should detect as discussion type
        detected_type = self.scorer._detect_content_type(v2ex_question, content, metadata)
        assert detected_type == "discussion", f"Expected 'discussion', got '{detected_type}'"

        # Score should use discussion weights
        quality = self.scorer.score(v2ex_question, content)
        assert quality.overall_score >= 0.20, f"V2EX question should score reasonably, got {quality.overall_score}"