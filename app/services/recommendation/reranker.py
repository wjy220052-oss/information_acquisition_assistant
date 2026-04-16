"""
Simple Reranker for recommendation generation

MVP version: Sorts articles by overall_score in descending order.
Future versions may include personalization, diversity, and exploration.
"""

import logging
from typing import List
from datetime import datetime

from app.models.db.tables import Article
from app.models.schemas.recommendation import (
    RecommendationCandidate,
    RecommendationItem,
    RecommendationConfig,
)

logger = logging.getLogger(__name__)


class SimpleReranker:
    """
    Simple reranker for MVP

    Sorts articles by overall_score descending.
    Breaks ties by crawl_time (newer first).

    Future improvements:
    - User profile matching
    - Diversity injection
    - Exploration content
    - Recency boost
    """

    def __init__(self, config: RecommendationConfig = None):
        """
        Initialize reranker with config

        Args:
            config: RecommendationConfig instance
        """
        self.config = config or RecommendationConfig()

    def rank(
        self,
        articles: List[Article],
    ) -> List[RecommendationItem]:
        """
        Rank articles for recommendation

        Args:
            articles: List of Article instances

        Returns:
            List of RecommendationItem with rank assigned
        """
        if not articles:
            logger.info("No articles to rank")
            return []

        # Sort by overall_score DESC, then crawl_time DESC
        sorted_articles = sorted(
            articles,
            key=lambda a: (
                a.overall_score if a.overall_score is not None else 0.0,
                a.crawl_time or datetime.min,
            ),
            reverse=True,
        )

        # Limit to max_recommendations
        selected = sorted_articles[:self.config.max_recommendations]

        # Create recommendation items
        items = []
        for rank, article in enumerate(selected, start=1):
            # Use overall_score as the recommendation score
            # Future: could adjust based on other factors
            score = float(article.overall_score) if article.overall_score else 0.0

            item = RecommendationItem(
                article_id=str(article.id),
                rank=rank,
                score=score,
                recommendation_type=self.config.recommendation_type,
            )
            items.append(item)

        logger.info(
            f"Ranked {len(articles)} articles, selected top {len(items)} "
            f"(max: {self.config.max_recommendations})"
        )

        return items

    def to_candidates(self, articles: List[Article]) -> List[RecommendationCandidate]:
        """
        Convert Article instances to RecommendationCandidate

        Useful for debugging and analysis.

        Args:
            articles: List of Article instances

        Returns:
            List of RecommendationCandidate
        """
        candidates = []
        for article in articles:
            candidate = RecommendationCandidate(
                article_id=str(article.id),
                title=article.title,
                url=article.url,
                summary=article.summary,
                content_type=article.content_type,
                overall_score=float(article.overall_score) if article.overall_score else 0.0,
                quality_level=article.quality_level,
                source_id=str(article.source_id),
                author_name=article.author.name if article.author else None,
                crawl_time=article.crawl_time or datetime.min,
                classification_tags=article.classification_tags or [],
            )
            candidates.append(candidate)
        return candidates
