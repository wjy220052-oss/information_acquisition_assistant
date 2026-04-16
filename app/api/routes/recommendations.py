"""
Recommendations API routes

Provides endpoints for fetching daily recommendations.
"""

from datetime import datetime, timezone
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select, and_
from sqlalchemy.orm import joinedload
from sqlalchemy.exc import SQLAlchemyError

from app.core.database import get_db_dependency as get_db
from app.core.logging import get_logger
from app.models.db.tables import Recommendation, Article, Source, Author
from app.services.recommendation.explainer import RecommendationExplainer, ExplanationContext

logger = get_logger(__name__)

# Global explainer instance
_explainer = RecommendationExplainer()
router = APIRouter()


# ========== Response Schemas ==========

class AuthorInfo(BaseModel):
    """Author information in recommendation response"""
    model_config = ConfigDict(from_attributes=True)

    id: Optional[str] = None
    name: Optional[str] = None
    username: Optional[str] = None


class SourceInfo(BaseModel):
    """Source information in recommendation response"""
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    domain: str


class ArticleInfo(BaseModel):
    """Article information in recommendation response"""
    model_config = ConfigDict(from_attributes=True)

    id: str
    title: str
    url: str
    summary: Optional[str] = None
    content_type: str
    source: SourceInfo
    author: Optional[AuthorInfo] = None
    word_count: int = 0
    reading_time_minutes: int = 0
    published_at: Optional[datetime] = None


class RecommendationItem(BaseModel):
    """Single recommendation item"""
    model_config = ConfigDict(from_attributes=True)

    id: str
    article: ArticleInfo
    rank: int
    score: float
    explanation: Optional[str] = Field(None, description="Why this article is recommended")
    status: str
    created_at: datetime


class TodayRecommendationsResponse(BaseModel):
    """Response schema for today's recommendations"""
    date: str = Field(..., description="Recommendation date (YYYY-MM-DD)")
    total: int = Field(..., description="Total number of recommendations")
    items: List[RecommendationItem]


class EmptyRecommendationsResponse(BaseModel):
    """Response when no recommendations available"""
    date: str
    total: int = 0
    items: List[RecommendationItem] = []
    message: str = "No recommendations available for today"


# ========== API Endpoints ==========

@router.get(
    "/today",
    response_model=TodayRecommendationsResponse,
    summary="Get today's recommendations",
    description="Fetch today's recommended articles with full details",
    responses={
        200: {
            "description": "Successfully retrieved today's recommendations (may be empty)",
            "model": TodayRecommendationsResponse,
        },
        503: {
            "description": "Database error or service unavailable",
        },
    }
)
async def get_today_recommendations(
    date: Optional[str] = Query(None, description="Date in YYYY-MM-DD format (defaults to today)"),
    db = Depends(get_db)
) -> TodayRecommendationsResponse:
    """
    Get today's recommended articles.

    Returns a list of recommendations for the specified date (or today),
    ordered by rank. Each recommendation includes the full article details.

    Args:
        date: Date string in YYYY-MM-DD format. Defaults to today.
        db: Database session

    Returns:
        TodayRecommendationsResponse with recommendations list
    """
    # Determine the date to query
    if date is None:
        date = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    logger.info(f"Fetching recommendations for date: {date}")

    try:
        # Query recommendations with joined article, source, and author
        stmt = (
            select(Recommendation)
            .options(
                joinedload(Recommendation.article)
                .joinedload(Article.source),
                joinedload(Recommendation.article)
                .joinedload(Article.author)
            )
            .where(
                and_(
                    Recommendation.batch_date == date,
                    Recommendation.recommendation_type == "daily_digest"
                )
            )
            .order_by(Recommendation.rank.asc())
        )

        result = db.execute(stmt)
        recommendations = result.unique().scalars().all()
    except SQLAlchemyError as e:
        logger.error(f"Database error fetching recommendations: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database error. Please check database connection and try again later."
        )

    logger.info(f"Found {len(recommendations)} recommendations for {date}")

    # Build response items
    items = []
    for rec in recommendations:
        article = rec.article
        source = article.source
        author = article.author

        # Build author info if available
        author_info = None
        if author:
            author_info = AuthorInfo(
                id=str(author.id),
                name=author.name,
                username=author.username
            )

        # Build source info
        source_info = SourceInfo(
            id=str(source.id),
            name=source.name,
            domain=source.domain
        )

        # Build article info
        article_info = ArticleInfo(
            id=str(article.id),
            title=article.title,
            url=article.url,
            summary=article.summary,
            content_type=article.content_type,
            source=source_info,
            author=author_info,
            word_count=article.word_count,
            reading_time_minutes=article.reading_time_minutes,
            published_at=article.publish_time
        )

        # Generate explanation
        context = ExplanationContext(
            title=article.title,
            source_name=source.name if source else None,
            author_name=author.name if author else None,
            content_type=article.content_type,
            quality_level=article.quality_level,
            classification_tags=article.classification_tags,
            reading_time_minutes=article.reading_time_minutes,
            score=float(rec.score) if rec.score else 0.0,
            rank=rec.rank,
            total_recommendations=len(recommendations),
        )
        explanation = _explainer.explain(context)

        # Build recommendation item
        item = RecommendationItem(
            id=str(rec.id),
            article=article_info,
            rank=rec.rank,
            score=float(rec.score),
            explanation=explanation,
            status=rec.status,
            created_at=rec.created_at
        )
        items.append(item)

    return TodayRecommendationsResponse(
        date=date,
        total=len(items),
        items=items
    )


@router.get(
    "/{recommendation_id}",
    response_model=RecommendationItem,
    summary="Get a specific recommendation",
    description="Fetch a single recommendation by its ID",
    responses={
        404: {"description": "Recommendation not found"},
    }
)
async def get_recommendation(
    recommendation_id: UUID,
    db = Depends(get_db)
) -> RecommendationItem:
    """
    Get a specific recommendation by ID.

    Args:
        recommendation_id: The UUID of the recommendation
        db: Database session

    Returns:
        RecommendationItem with full details

    Raises:
        HTTPException: If recommendation not found
    """
    try:
        stmt = (
            select(Recommendation)
            .options(
                joinedload(Recommendation.article)
                .joinedload(Article.source),
                joinedload(Recommendation.article)
                .joinedload(Article.author)
            )
            .where(Recommendation.id == recommendation_id)
        )

        result = db.execute(stmt)
        rec = result.unique().scalar_one_or_none()
    except SQLAlchemyError as e:
        logger.error(f"Database error fetching recommendation {recommendation_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database error. Please try again later."
        )

    if not rec:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Recommendation {recommendation_id} not found"
        )

    article = rec.article
    source = article.source
    author = article.author

    author_info = None
    if author:
        author_info = AuthorInfo(
            id=str(author.id),
            name=author.name,
            username=author.username
        )

    source_info = SourceInfo(
        id=str(source.id),
        name=source.name,
        domain=source.domain
    )

    article_info = ArticleInfo(
        id=str(article.id),
        title=article.title,
        url=article.url,
        summary=article.summary,
        content_type=article.content_type,
        source=source_info,
        author=author_info,
        word_count=article.word_count,
        reading_time_minutes=article.reading_time_minutes,
        published_at=article.publish_time
    )

    # Generate explanation
    context = ExplanationContext(
        title=article.title,
        source_name=source.name if source else None,
        author_name=author.name if author else None,
        content_type=article.content_type,
        quality_level=article.quality_level,
        classification_tags=article.classification_tags,
        reading_time_minutes=article.reading_time_minutes,
        score=float(rec.score) if rec.score else 0.0,
        rank=rec.rank,
        total_recommendations=1,
    )
    explanation = _explainer.explain(context)

    return RecommendationItem(
        id=str(rec.id),
        article=article_info,
        rank=rec.rank,
        score=float(rec.score),
        explanation=explanation,
        status=rec.status,
        created_at=rec.created_at
    )
