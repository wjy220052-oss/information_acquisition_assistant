"""
Content processing schemas

Defines data structures for content classification and quality scoring.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, List, Dict, Any
from datetime import datetime

from app.models.schemas.source import SourceItem


class ContentType(str, Enum):
    """Content type classification"""
    TECHNOLOGY = "technology"      # 技术
    PRODUCT = "product"          # 产品
    LIFE = "life"                # 生活
    CULTURE = "culture"          # 文化/书影音
    DISCUSSION = "discussion"    # 讨论
    NEWS = "news"                # 新闻
    TUTORIAL = "tutorial"        # 教程
    OPINION = "opinion"          # 观点
    UNKNOWN = "unknown"


class QualityLevel(str, Enum):
    """Quality level classification"""
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


@dataclass
class ContentMetadata:
    """Metadata extracted from content"""
    # Content characteristics
    word_count: int = 0
    has_images: bool = False
    has_code: bool = False
    has_external_links: bool = False
    link_count: int = 0
    paragraph_count: int = 0
    quote_count: int = 0

    # Source characteristics
    source_trust_score: float = 0.0  # 0.0 - 1.0
    author_reputation: float = 0.0  # 0.0 - 1.0

    # Engagement metrics (if available)
    view_count: Optional[int] = None
    like_count: Optional[int] = None
    comment_count: Optional[int] = None
    share_count: Optional[int] = None

    # Content age
    content_age_hours: float = 0.0  # Hours since publish


@dataclass
class ContentClassification:
    """Content classification result"""
    # Primary classification
    content_type: ContentType = ContentType.UNKNOWN

    # Confidence score for classification (0.0 - 1.0)
    confidence: float = 0.0

    # Additional tags
    tags: List[str] = field(default_factory=list)

    # Sub-categories
    subcategories: List[str] = field(default_factory=list)

    # Content metadata
    metadata: ContentMetadata = field(default_factory=ContentMetadata)


@dataclass
class QualityScore:
    """Quality scoring result"""
    # Overall quality score (0.0 - 1.0)
    overall_score: float = 0.0

    # Quality level
    quality_level: QualityLevel = QualityLevel.LOW

    # Score breakdown
    completeness_score: float = 0.0  # 内容完整性
    structure_score: float = 0.0      # 结构清晰度
    depth_score: float = 0.0          # 内容深度
    credibility_score: float = 0.0    # 可信度
    engagement_score: float = 0.0     # 互动质量

    # Quality flags
    is_original: bool = True
    has_citation: bool = False
    is_clickbait: bool = False
    contains_sensitive: bool = False


@dataclass
class ContentProcessingResult:
    """Result of content processing"""
    # Original source item
    source_item: SourceItem

    # Processing metadata
    processed_at: datetime = field(default_factory=lambda: datetime.now())

    # Classification result
    classification: ContentClassification = field(default_factory=ContentClassification)

    # Quality score
    quality: QualityScore = field(default_factory=QualityScore)

    # Processing flags
    is_processed: bool = False
    processing_error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage"""
        return {
            "source_item_id": self.source_item.source_item_id,
            "source_id": self.source_item.source_id,
            "processed_at": self.processed_at.isoformat(),
            "content_type": self.classification.content_type.value,
            "confidence": self.classification.confidence,
            "tags": self.classification.tags,
            "overall_quality": self.quality.overall_score,
            "quality_level": self.quality.quality_level.value,
            "is_processed": self.is_processed,
            "processing_error": self.processing_error,
        }