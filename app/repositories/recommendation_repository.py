"""
Recommendation repository for database operations

Handles saving and retrieving recommendation results.
"""

import logging
from typing import List, Optional, Tuple
from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy.orm import Session
from sqlalchemy import select, and_, desc
from sqlalchemy.dialects.postgresql import insert

from app.models.db.tables import Recommendation, Article
from app.models.schemas.recommendation import RecommendationItem, RecommendationResult

logger = logging.getLogger(__name__)


class RecommendationRepository:
    """Repository for Recommendation CRUD operations"""

    def __init__(self, db: Session):
        """
        Initialize repository with database session

        Args:
            db: SQLAlchemy session
        """
        self.db = db

    def save_batch(
        self,
        items: List[RecommendationItem],
        batch_date: str,
        recommendation_type: str = 'daily_digest',
    ) -> Tuple[int, int]:
        """
        Save recommendation items to database

        Handles duplicates by skipping existing (user_id, article_id, type, batch_date) combinations.

        Args:
            items: List of recommendation items to save
            batch_date: Batch date string (YYYY-MM-DD)
            recommendation_type: Type of recommendation

        Returns:
            Tuple of (saved_count, skipped_count)
        """
        from app.models.db.tables import MVP_USER_ID

        saved_count = 0
        skipped_count = 0

        for item in items:
            try:
                # Check if already exists
                existing = self._get_existing_recommendation(
                    user_id=MVP_USER_ID,
                    article_id=item.article_id,
                    recommendation_type=recommendation_type,
                    batch_date=batch_date,
                )

                if existing:
                    logger.debug(
                        f"Skipping duplicate recommendation: article_id={item.article_id}, "
                        f"batch_date={batch_date}"
                    )
                    skipped_count += 1
                    continue

                # Create new recommendation
                recommendation = Recommendation(
                    id=uuid4(),
                    user_id=MVP_USER_ID,
                    article_id=item.article_id,
                    recommendation_type=recommendation_type,
                    score=item.score,
                    rank=item.rank,
                    batch_date=batch_date,
                    status='pending',
                    created_at=datetime.now(timezone.utc),
                )
                self.db.add(recommendation)
                saved_count += 1

            except Exception as e:
                logger.warning(f"Failed to save recommendation for article {item.article_id}: {e}")
                skipped_count += 1

        # Commit all successful inserts
        if saved_count > 0:
            self.db.commit()
            logger.info(
                f"Saved {saved_count} recommendations for {batch_date} "
                f"({skipped_count} skipped)"
            )

        return saved_count, skipped_count

    def _get_existing_recommendation(
        self,
        user_id: str,
        article_id: str,
        recommendation_type: str,
        batch_date: str,
    ) -> Optional[Recommendation]:
        """Check if recommendation already exists"""
        stmt = select(Recommendation).where(
            and_(
                Recommendation.user_id == user_id,
                Recommendation.article_id == article_id,
                Recommendation.recommendation_type == recommendation_type,
                Recommendation.batch_date == batch_date,
            )
        )
        result = self.db.execute(stmt).scalar_one_or_none()
        return result

    def get_recommendations_by_batch(
        self,
        batch_date: str,
        recommendation_type: str = 'daily_digest',
        limit: int = 10,
    ) -> List[Recommendation]:
        """
        Get recommendations for a specific batch date

        Args:
            batch_date: Batch date string (YYYY-MM-DD)
            recommendation_type: Type of recommendation
            limit: Maximum number to return

        Returns:
            List of Recommendation instances ordered by rank
        """
        stmt = (
            select(Recommendation)
            .where(
                and_(
                    Recommendation.batch_date == batch_date,
                    Recommendation.recommendation_type == recommendation_type,
                )
            )
            .order_by(Recommendation.rank)
            .limit(limit)
        )
        result = self.db.execute(stmt).scalars().all()
        return list(result)

    def get_recommendations_with_articles(
        self,
        batch_date: str,
        recommendation_type: str = 'daily_digest',
        limit: int = 10,
    ) -> List[Tuple[Recommendation, Article]]:
        """
        Get recommendations with full article data

        Args:
            batch_date: Batch date string (YYYY-MM-DD)
            recommendation_type: Type of recommendation
            limit: Maximum number to return

        Returns:
            List of (Recommendation, Article) tuples
        """
        stmt = (
            select(Recommendation, Article)
            .join(Article, Recommendation.article_id == Article.id)
            .where(
                and_(
                    Recommendation.batch_date == batch_date,
                    Recommendation.recommendation_type == recommendation_type,
                )
            )
            .order_by(Recommendation.rank)
            .limit(limit)
        )
        result = self.db.execute(stmt).all()
        return list(result)

    def get_already_recommended_article_ids(
        self,
        batch_date: str,
        recommendation_type: str = 'daily_digest',
    ) -> List[str]:
        """
        Get list of article IDs already recommended for this batch

        Args:
            batch_date: Batch date string (YYYY-MM-DD)
            recommendation_type: Type of recommendation

        Returns:
            List of article IDs as strings
        """
        stmt = select(Recommendation.article_id).where(
            and_(
                Recommendation.batch_date == batch_date,
                Recommendation.recommendation_type == recommendation_type,
            )
        )
        result = self.db.execute(stmt).scalars().all()
        return [str(r) for r in result]

    def update_recommendation_status(
        self,
        recommendation_id: str,
        status: str,
        delivered_at: Optional[datetime] = None,
    ) -> Optional[Recommendation]:
        """
        Update recommendation status

        Args:
            recommendation_id: Recommendation ID
            status: New status (pending, delivered, viewed, clicked, finished)
            delivered_at: Optional delivery timestamp

        Returns:
            Updated Recommendation instance or None
        """
        stmt = select(Recommendation).where(Recommendation.id == recommendation_id)
        result = self.db.execute(stmt).scalar_one_or_none()

        if result:
            result.status = status
            if delivered_at:
                result.delivered_at = delivered_at
            self.db.commit()
            self.db.refresh(result)
            logger.debug(f"Updated recommendation {recommendation_id} status to {status}")
            return result

        return None

    def get_recommendations_for_date(
        self,
        batch_date: str,
        recommendation_type: str = 'daily_digest',
    ) -> List[Recommendation]:
        """
        Get recommendations for a specific date with eager-loaded articles

        Args:
            batch_date: Batch date string (YYYY-MM-DD)
            recommendation_type: Type of recommendation

        Returns:
            List of Recommendation instances with article relationship loaded
        """
        from sqlalchemy.orm import joinedload

        stmt = (
            select(Recommendation)
            .options(joinedload(Recommendation.article))
            .where(
                and_(
                    Recommendation.batch_date == batch_date,
                    Recommendation.recommendation_type == recommendation_type,
                )
            )
            .order_by(Recommendation.rank)
        )
        result = self.db.execute(stmt).unique().scalars().all()
        return list(result)
