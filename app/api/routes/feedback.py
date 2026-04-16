"""
Feedback API routes

Provides endpoints for user feedback and click tracking on recommendations.
"""

from datetime import datetime, timezone
from typing import Optional
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, field_validator
from sqlalchemy import select, and_
from sqlalchemy.orm import Session

from app.core.database import get_db_dependency as get_db
from app.core.logging import get_logger
from app.models.db.tables import Recommendation, Feedback, Article, MVP_USER_ID

logger = get_logger(__name__)
router = APIRouter()


# ========== Request/Response Schemas ==========

class ClickRequest(BaseModel):
    """Request schema for click tracking"""
    source: Optional[str] = None  # e.g., "homepage", "email", "api"


class ClickResponse(BaseModel):
    """Response schema for click tracking"""
    success: bool
    redirect_url: str


class FeedbackRequest(BaseModel):
    """Request schema for feedback submission"""
    action: str  # "like", "dislike", "skip"
    context: Optional[str] = None  # e.g., "homepage"

    @field_validator('action')
    @classmethod
    def validate_action(cls, v: str) -> str:
        """Validate action is one of allowed values"""
        allowed = {'like', 'dislike', 'skip'}
        if v not in allowed:
            raise ValueError(f'action must be one of: {", ".join(allowed)}')
        return v


class FeedbackResponse(BaseModel):
    """Response schema for feedback submission"""
    success: bool
    feedback_id: str


# ========== Helper Functions ==========

def get_recommendation_or_404(
    db: Session,
    recommendation_id: UUID
) -> Recommendation:
    """
    Get recommendation by ID or raise 404

    Args:
        db: Database session
        recommendation_id: Recommendation UUID

    Returns:
        Recommendation instance

    Raises:
        HTTPException: 404 if not found
    """
    stmt = select(Recommendation).where(Recommendation.id == recommendation_id)
    result = db.execute(stmt).scalar_one_or_none()

    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Recommendation {recommendation_id} not found"
        )

    return result


def get_article_url(db: Session, article_id: UUID) -> str:
    """Get article URL by ID"""
    stmt = select(Article.url).where(Article.id == article_id)
    result = db.execute(stmt).scalar_one_or_none()
    return result or ""


def upsert_feedback(
    db: Session,
    user_id: UUID,
    article_id: UUID,
    recommendation_id: UUID,
    feedback_type: str,
    rating: Optional[int],
) -> Feedback:
    """
    Create or update feedback record

    If feedback already exists for this recommendation, update it.
    Otherwise, create a new one.

    Args:
        db: Database session
        user_id: User ID
        article_id: Article ID
        recommendation_id: Recommendation ID
        feedback_type: Type of feedback (rating, ignore, etc.)
        rating: Optional rating value (1-9)

    Returns:
        Feedback instance (new or updated)
    """
    # Check for existing feedback
    stmt = select(Feedback).where(
        and_(
            Feedback.recommendation_id == recommendation_id,
            Feedback.user_id == user_id,
        )
    )
    existing = db.execute(stmt).scalar_one_or_none()

    if existing:
        # Update existing feedback
        existing.feedback_type = feedback_type
        existing.rating = rating
        existing.created_at = datetime.now(timezone.utc)  # Update timestamp
        db.commit()
        db.refresh(existing)
        logger.debug(f"Updated feedback {existing.id} for recommendation {recommendation_id}")
        return existing
    else:
        # Create new feedback
        feedback = Feedback(
            id=uuid4(),
            user_id=user_id,
            article_id=article_id,
            recommendation_id=recommendation_id,
            feedback_type=feedback_type,
            rating=rating,
        )
        db.add(feedback)
        db.commit()
        db.refresh(feedback)
        logger.info(f"Created feedback {feedback.id} for recommendation {recommendation_id}")
        return feedback


# ========== API Endpoints ==========

@router.post(
    "/{recommendation_id}/click",
    response_model=ClickResponse,
    summary="Record click and get redirect URL",
    description="Record that user clicked on a recommendation and return the original article URL",
    responses={
        200: {"description": "Click recorded successfully"},
        404: {"description": "Recommendation not found"},
    }
)
async def record_click(
    recommendation_id: UUID,
    request: ClickRequest,
    db: Session = Depends(get_db)
) -> ClickResponse:
    """
    Record click on a recommendation.

    Updates recommendation status to 'clicked' and returns the original article URL.
    Idempotent - multiple clicks on same recommendation are tolerated.

    Args:
        recommendation_id: The UUID of the recommendation
        request: Click request with optional source
        db: Database session

    Returns:
        ClickResponse with success status and redirect URL
    """
    # Get recommendation (raises 404 if not found)
    recommendation = get_recommendation_or_404(db, recommendation_id)

    # Update status to clicked
    recommendation.status = "clicked"
    db.commit()

    # Get article URL
    redirect_url = get_article_url(db, recommendation.article_id)

    logger.info(
        f"Recorded click for recommendation {recommendation_id}, "
        f"source={request.source or 'unknown'}"
    )

    return ClickResponse(
        success=True,
        redirect_url=redirect_url
    )


@router.post(
    "/{recommendation_id}/feedback",
    response_model=FeedbackResponse,
    summary="Submit feedback on a recommendation",
    description="Submit like/dislike/skip feedback for a recommendation",
    responses={
        200: {"description": "Feedback recorded successfully"},
        404: {"description": "Recommendation not found"},
        422: {"description": "Invalid action value"},
    }
)
async def submit_feedback(
    recommendation_id: UUID,
    request: FeedbackRequest,
    db: Session = Depends(get_db)
) -> FeedbackResponse:
    """
    Submit feedback on a recommendation.

    Actions:
    - like: Records rating=8 (high quality/relevant)
    - dislike: Records rating=2 (low quality/not relevant)
    - skip: Records feedback_type='ignore' (not interested now)

    Idempotent - subsequent feedback updates the existing record.

    Args:
        recommendation_id: The UUID of the recommendation
        request: Feedback request with action
        db: Database session

    Returns:
        FeedbackResponse with success status and feedback ID
    """
    # Get recommendation (raises 404 if not found)
    recommendation = get_recommendation_or_404(db, recommendation_id)

    # Map action to feedback values
    action_mapping = {
        "like": ("rating", 8),
        "dislike": ("rating", 2),
        "skip": ("ignore", None),
    }

    feedback_type, rating = action_mapping[request.action]

    # Create or update feedback
    feedback = upsert_feedback(
        db=db,
        user_id=UUID(MVP_USER_ID),
        article_id=recommendation.article_id,
        recommendation_id=recommendation.id,
        feedback_type=feedback_type,
        rating=rating,
    )

    return FeedbackResponse(
        success=True,
        feedback_id=str(feedback.id)
    )
