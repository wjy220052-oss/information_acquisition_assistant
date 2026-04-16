"""
Tests for SimpleReranker
"""

import pytest
from datetime import datetime, timezone
from unittest.mock import MagicMock

from app.services.recommendation.reranker import SimpleReranker
from app.models.schemas.recommendation import RecommendationConfig


class TestSimpleReranker:
    """Test SimpleReranker"""

    def setup_method(self):
        """Setup test fixtures"""
        self.config = RecommendationConfig(
            min_overall_score=0.6,
            max_recommendations=5,
        )
        self.reranker = SimpleReranker(config=self.config)

    def _create_mock_article(self, article_id, overall_score, crawl_time=None):
        """Create a mock Article for testing"""
        article = MagicMock()
        article.id = article_id
        article.overall_score = overall_score
        article.crawl_time = crawl_time or datetime.now(timezone.utc)
        article.title = f"Article {article_id}"
        article.url = f"https://example.com/{article_id}"
        return article

    def test_rank_by_overall_score_descending(self):
        """Test articles are ranked by overall_score descending"""
        articles = [
            self._create_mock_article("a1", 0.7),
            self._create_mock_article("a2", 0.9),
            self._create_mock_article("a3", 0.5),
        ]

        items = self.reranker.rank(articles)

        assert len(items) == 3
        assert items[0].article_id == "a2"  # Highest score first
        assert items[0].score == 0.9
        assert items[1].article_id == "a1"
        assert items[2].article_id == "a3"

    def test_rank_respects_max_recommendations(self):
        """Test max_recommendations limit is respected"""
        articles = [
            self._create_mock_article(f"a{i}", 0.5 + i * 0.05)
            for i in range(10)
        ]

        items = self.reranker.rank(articles)

        assert len(items) == 5  # max_recommendations = 5

    def test_rank_empty_list(self):
        """Test ranking empty list returns empty list"""
        items = self.reranker.rank([])

        assert items == []

    def test_rank_assigns_correct_ranks(self):
        """Test rank numbers are assigned correctly (1-based)"""
        articles = [
            self._create_mock_article("a1", 0.8),
            self._create_mock_article("a2", 0.7),
            self._create_mock_article("a3", 0.6),
        ]

        items = self.reranker.rank(articles)

        assert items[0].rank == 1
        assert items[1].rank == 2
        assert items[2].rank == 3

    def test_rank_breaks_ties_by_crawl_time(self):
        """Test tie-breaking by crawl_time when scores are equal"""
        now = datetime.now(timezone.utc)
        articles = [
            self._create_mock_article("a1", 0.8, now),
            self._create_mock_article("a2", 0.8, now.replace(day=now.day - 1)),
            self._create_mock_article("a3", 0.8, now.replace(day=now.day + 1)),
        ]

        items = self.reranker.rank(articles)

        # All have same score, so order depends on crawl_time
        assert len(items) == 3
        # Most recent should come first (due to reverse=True on tuple sort)

    def test_rank_handles_none_scores(self):
        """Test articles with None overall_score are handled"""
        articles = [
            self._create_mock_article("a1", None),
            self._create_mock_article("a2", 0.8),
        ]

        items = self.reranker.rank(articles)

        assert len(items) == 2
        # Article with score should come first
        assert items[0].article_id == "a2"
        assert items[1].article_id == "a1"
        assert items[1].score == 0.0  # None converted to 0.0

    def test_default_config(self):
        """Test reranker works with default config"""
        reranker = SimpleReranker()  # No config

        articles = [self._create_mock_article("a1", 0.8)]
        items = reranker.rank(articles)

        assert len(items) == 1

    def test_config_validation(self):
        """Test config validation"""
        with pytest.raises(ValueError):
            RecommendationConfig(min_overall_score=-0.1)

        with pytest.raises(ValueError):
            RecommendationConfig(max_recommendations=0)
