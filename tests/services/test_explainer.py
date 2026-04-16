"""
Tests for Recommendation Explainer

Covers:
- Rank-based explanations
- Quality-based explanations
- Source-based explanations
- Combined explanations
"""

import pytest
from app.services.recommendation.explainer import (
    RecommendationExplainer,
    ExplanationContext,
)


class TestRecommendationExplainerBasics:
    """Tests for basic explainer functionality"""

    def test_explainer_init(self):
        """Should initialize with default phrases"""
        explainer = RecommendationExplainer()

        assert 'high' in explainer.quality_phrases
        assert 1 in explainer.rank_phrases
        assert 'article' in explainer.content_type_phrases


class TestRankBasedExplanations:
    """Tests for rank-based explanation generation"""

    def test_first_place_explanation(self):
        """Should generate '今日首选' for rank 1"""
        explainer = RecommendationExplainer()
        context = ExplanationContext(
            title="Test",
            source_name=None,
            author_name=None,
            content_type=None,
            quality_level=None,
            classification_tags=None,
            reading_time_minutes=None,
            score=0.8,
            rank=1,
            total_recommendations=10,
        )

        explanation = explainer.explain(context)
        assert "今日首选" in explanation

    def test_second_place_explanation(self):
        """Should generate '强烈推荐' for rank 2"""
        explainer = RecommendationExplainer()
        context = ExplanationContext(
            title="Test",
            source_name=None,
            author_name=None,
            content_type=None,
            quality_level=None,
            classification_tags=None,
            reading_time_minutes=None,
            score=0.8,
            rank=2,
            total_recommendations=10,
        )

        explanation = explainer.explain(context)
        assert "强烈推荐" in explanation

    def test_third_place_explanation(self):
        """Should generate '值得一看' for rank 3"""
        explainer = RecommendationExplainer()
        context = ExplanationContext(
            title="Test",
            source_name=None,
            author_name=None,
            content_type=None,
            quality_level=None,
            classification_tags=None,
            reading_time_minutes=None,
            score=0.8,
            rank=3,
            total_recommendations=10,
        )

        explanation = explainer.explain(context)
        assert "值得一看" in explanation


class TestQualityBasedExplanations:
    """Tests for quality-based explanation generation"""

    def test_high_quality_explanation(self):
        """Should mention quality for high quality content"""
        explainer = RecommendationExplainer()
        context = ExplanationContext(
            title="Test",
            source_name=None,
            author_name=None,
            content_type=None,
            quality_level='high',
            classification_tags=None,
            reading_time_minutes=None,
            score=0.8,
            rank=5,
            total_recommendations=10,
        )

        explanation = explainer.explain(context)
        assert "高质量" in explanation

    def test_medium_quality_explanation(self):
        """Should mention worth reading for medium quality"""
        explainer = RecommendationExplainer()
        context = ExplanationContext(
            title="Test",
            source_name=None,
            author_name=None,
            content_type=None,
            quality_level='medium',
            classification_tags=None,
            reading_time_minutes=None,
            score=0.5,
            rank=5,
            total_recommendations=10,
        )

        explanation = explainer.explain(context)
        assert "值得一读" in explanation


class TestSourceBasedExplanations:
    """Tests for source-based explanation generation"""

    def test_v2ex_source(self):
        """Should mention V2EX for v2ex source"""
        explainer = RecommendationExplainer()
        context = ExplanationContext(
            title="Test",
            source_name='v2ex',
            author_name=None,
            content_type=None,
            quality_level=None,
            classification_tags=None,
            reading_time_minutes=None,
            score=0.5,
            rank=5,
            total_recommendations=10,
        )

        explanation = explainer.explain(context)
        assert "V2EX" in explanation

    def test_ruanyf_source(self):
        """Should mention 阮一峰周刊 for ruanyf_weekly source"""
        explainer = RecommendationExplainer()
        context = ExplanationContext(
            title="Test",
            source_name='ruanyf_weekly',
            author_name=None,
            content_type=None,
            quality_level=None,
            classification_tags=None,
            reading_time_minutes=None,
            score=0.5,
            rank=5,
            total_recommendations=10,
        )

        explanation = explainer.explain(context)
        assert "阮一峰" in explanation


class TestCombinedExplanations:
    """Tests for combined explanation generation"""

    def test_rank_and_quality_combined(self):
        """Should combine rank and quality phrases"""
        explainer = RecommendationExplainer()
        context = ExplanationContext(
            title="Test",
            source_name=None,
            author_name=None,
            content_type=None,
            quality_level='high',
            classification_tags=None,
            reading_time_minutes=None,
            score=0.9,
            rank=1,
            total_recommendations=10,
        )

        explanation = explainer.explain(context)
        assert "今日首选" in explanation
        assert "高质量" in explanation
        assert "·" in explanation  # Should have separator

    def test_limited_to_two_reasons(self):
        """Should limit to maximum 2 reasons"""
        explainer = RecommendationExplainer()
        context = ExplanationContext(
            title="Test",
            source_name='v2ex',
            author_name=None,
            content_type='article',
            quality_level='high',
            classification_tags=None,
            reading_time_minutes=20,
            score=0.9,
            rank=1,
            total_recommendations=10,
        )

        explanation = explainer.explain(context)
        separators = explanation.count("·")
        assert separators <= 1  # At most 1 separator means 2 parts


class TestFallbackExplanation:
    """Tests for fallback explanation"""

    def test_fallback_when_no_reasons(self):
        """Should return fallback message when no reasons apply"""
        explainer = RecommendationExplainer()
        context = ExplanationContext(
            title="Test",
            source_name='unknown_source',
            author_name=None,
            content_type=None,
            quality_level='low',
            classification_tags=None,
            reading_time_minutes=None,
            score=0.3,
            rank=8,
            total_recommendations=10,
        )

        explanation = explainer.explain(context)
        assert "偏好推荐" in explanation


class TestAuthorBasedExplanations:
    """Tests for author-based explanation generation"""

    def test_known_author_explanation(self):
        """Should mention known quality authors"""
        explainer = RecommendationExplainer()
        context = ExplanationContext(
            title="Test",
            source_name=None,
            author_name='阮一峰',
            content_type=None,
            quality_level=None,
            classification_tags=None,
            reading_time_minutes=None,
            score=0.5,
            rank=5,
            total_recommendations=10,
        )

        explanation = explainer.explain(context)
        assert "阮一峰" in explanation
        assert "出品" in explanation


class TestReadingTimeExplanations:
    """Tests for reading time based explanations"""

    def test_long_article_explanation(self):
        """Should mention depth for long articles"""
        explainer = RecommendationExplainer()
        context = ExplanationContext(
            title="Test",
            source_name=None,
            author_name=None,
            content_type=None,
            quality_level=None,
            classification_tags=None,
            reading_time_minutes=20,
            score=0.5,
            rank=5,
            total_recommendations=10,
        )

        explanation = explainer.explain(context)
        assert "深度长文" in explanation

    def test_short_article_explanation(self):
        """Should mention brevity for short articles"""
        explainer = RecommendationExplainer()
        context = ExplanationContext(
            title="Test",
            source_name=None,
            author_name=None,
            content_type=None,
            quality_level=None,
            classification_tags=None,
            reading_time_minutes=2,
            score=0.5,
            rank=5,
            total_recommendations=10,
        )

        explanation = explainer.explain(context)
        assert "短小精悍" in explanation
