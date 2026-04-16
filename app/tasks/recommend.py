"""
Recommend task - Generate daily content recommendations

This module provides the recommendation generation task that:
1. Fetches high-quality articles from the database
2. Ranks them by overall_score
3. Saves recommendations to the database
4. Provides statistics and error handling
"""

import logging
from datetime import datetime, timezone
from typing import Optional

from app.core.database import get_db
from app.core.logging import get_logger
from app.repositories.article_repository import ArticleRepository
from app.repositories.recommendation_repository import RecommendationRepository
from app.services.recommendation.reranker import SimpleReranker
from app.models.schemas.recommendation import (
    RecommendationConfig,
    RecommendationResult,
)

logger = get_logger(__name__)


class RecommendTask:
    """
    Recommendation generation task

    Generates daily recommendations from high-quality articles.
    """

    def __init__(self, config: RecommendationConfig = None):
        """
        Initialize recommend task

        Args:
            config: RecommendationConfig instance
        """
        self.config = config or RecommendationConfig()
        self.reranker = SimpleReranker(config=self.config)

    def run(self, batch_date: Optional[str] = None) -> RecommendationResult:
        """
        Execute the recommend task

        Args:
            batch_date: Batch date string (YYYY-MM-DD). Defaults to today.

        Returns:
            RecommendationResult with statistics
        """
        # Use today if not specified
        if batch_date is None:
            batch_date = datetime.now(timezone.utc).strftime('%Y-%m-%d')

        logger.info(
            f"Starting recommend task for {batch_date}, "
            f"min_score={self.config.min_overall_score}, "
            f"max={self.config.max_recommendations}"
        )

        result = RecommendationResult(
            batch_date=batch_date,
            recommendation_type=self.config.recommendation_type,
            total_candidates=0,
            filtered_count=0,
            selected_count=0,
            skipped_count=0,
        )

        try:
            with get_db() as db:
                # Initialize repositories
                article_repo = ArticleRepository(db)
                recommendation_repo = RecommendationRepository(db)

                # Step 1: Get already recommended articles for this batch
                existing_article_ids = recommendation_repo.get_already_recommended_article_ids(
                    batch_date=batch_date,
                    recommendation_type=self.config.recommendation_type,
                )
                logger.debug(f"Already recommended today: {len(existing_article_ids)} articles")

                # Step 2: Fetch high-quality articles
                articles = article_repo.get_articles_for_recommendation(
                    min_overall_score=self.config.min_overall_score,
                    limit=100,  # Fetch more than needed for selection
                    exclude_article_ids=existing_article_ids if existing_article_ids else None,
                )
                result.total_candidates = len(articles)

                if not articles:
                    logger.warning(
                        f"No articles found with overall_score >= {self.config.min_overall_score}"
                    )
                    return result

                logger.info(f"Found {len(articles)} candidates meeting quality threshold")
                result.filtered_count = len(articles)

                # Step 3: Rank articles
                items = self.reranker.rank(articles)

                if not items:
                    logger.warning("No recommendations generated after ranking")
                    return result

                # Step 4: Save recommendations
                saved_count, skipped_count = recommendation_repo.save_batch(
                    items=items,
                    batch_date=batch_date,
                    recommendation_type=self.config.recommendation_type,
                )

                result.selected_count = saved_count
                result.skipped_count = skipped_count
                result.items = items

                logger.info(
                    f"Recommend task completed: {saved_count} saved, "
                    f"{skipped_count} skipped for {batch_date}"
                )

                return result

        except Exception as e:
            logger.exception(f"Fatal error in recommend task for {batch_date}")
            raise


def run_recommend_task(
    batch_date: Optional[str] = None,
    min_overall_score: float = 0.35,
    max_recommendations: int = 10,
) -> RecommendationResult:
    """
    Convenience function to run recommendation task

    Args:
        batch_date: Batch date (YYYY-MM-DD), defaults to today
        min_overall_score: Minimum quality threshold
        max_recommendations: Maximum recommendations to generate

    Returns:
        RecommendationResult with generated recommendations
    """
    config = RecommendationConfig(
        min_overall_score=min_overall_score,
        max_recommendations=max_recommendations,
        recommendation_type='daily_digest',
    )
    task = RecommendTask(config=config)
    return task.run(batch_date=batch_date)


if __name__ == '__main__':
    # Command-line entry point
    import argparse
    import sys

    parser = argparse.ArgumentParser(description='Generate daily content recommendations')
    parser.add_argument(
        '--date',
        type=str,
        help='Batch date (YYYY-MM-DD), defaults to today',
    )
    parser.add_argument(
        '--min-score',
        type=float,
        default=0.35,
        help='Minimum overall_score threshold (default: 0.35 after quality calibration)',
    )
    parser.add_argument(
        '--max',
        type=int,
        default=10,
        help='Maximum recommendations (default: 10)',
    )
    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Show detailed output',
    )

    args = parser.parse_args()

    # Handle 'today' as a special value
    batch_date = args.date
    if batch_date == 'today':
        batch_date = datetime.now(timezone.utc).strftime('%Y-%m-%d')

    try:
        result = run_recommend_task(
            batch_date=batch_date,
            min_overall_score=args.min_score,
            max_recommendations=args.max,
        )

        print(f"\nRecommendation Generation Results")
        print(f"{'=' * 50}")
        print(f"Batch Date: {result.batch_date}")
        print(f"Total Candidates: {result.total_candidates}")
        print(f"Meeting Threshold: {result.filtered_count}")
        print(f"Saved: {result.selected_count}")
        print(f"Skipped (duplicates): {result.skipped_count}")

        if args.verbose and result.items:
            print(f"\nTop Recommendations:")
            for item in result.items[:5]:
                print(f"  Rank {item.rank}: Article {item.article_id[:8]}... (score: {item.score:.3f})")

        # Exit with error if no recommendations
        sys.exit(0 if result.selected_count > 0 else 1)

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
