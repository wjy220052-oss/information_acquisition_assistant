"""
Recommendation schemas

Defines data structures for recommendation generation and results.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
from decimal import Decimal


@dataclass
class RecommendationCandidate:
    """A candidate article for recommendation"""
    article_id: str
    title: str
    url: str
    summary: Optional[str]
    content_type: str
    overall_score: float
    quality_level: Optional[str]
    source_id: str
    author_name: Optional[str]
    crawl_time: datetime
    classification_tags: List[str] = field(default_factory=list)


@dataclass
class RecommendationItem:
    """A generated recommendation item"""
    article_id: str
    rank: int
    score: float  # Final recommendation score (can be adjusted from overall_score)
    recommendation_type: str  # e.g., 'daily_digest', 'weekly_author'


@dataclass
class RecommendationResult:
    """Result of recommendation generation"""
    batch_date: str  # Format: YYYY-MM-DD
    recommendation_type: str
    total_candidates: int  # Total articles considered
    filtered_count: int  # Articles passing quality threshold
    selected_count: int  # Final recommendations generated
    skipped_count: int  # Duplicates skipped
    items: List[RecommendationItem] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for logging/storage"""
        return {
            'batch_date': self.batch_date,
            'recommendation_type': self.recommendation_type,
            'total_candidates': self.total_candidates,
            'filtered_count': self.filtered_count,
            'selected_count': self.selected_count,
            'skipped_count': self.skipped_count,
            'item_count': len(self.items),
            'created_at': self.created_at.isoformat(),
        }


@dataclass
class RecommendationConfig:
    """Configuration for recommendation generation"""
    # NOTE: Default threshold raised to 0.35 after quality scoring calibration.
    # Discussion content now scores 0.45-0.60 with the new scoring algorithm.
    # This ensures only genuinely high-quality content is recommended.
    min_overall_score: float = 0.35  # Quality threshold
    max_recommendations: int = 10   # Daily limit
    recommendation_type: str = 'daily_digest'

    def __post_init__(self):
        """Validate config"""
        if self.min_overall_score < 0 or self.min_overall_score > 1:
            raise ValueError("min_overall_score must be between 0 and 1")
        if self.max_recommendations < 1:
            raise ValueError("max_recommendations must be at least 1")
