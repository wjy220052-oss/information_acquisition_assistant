"""
MVP Core database tables

Contains the minimum viable set of tables for the content recommendation system.
"""

from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from sqlalchemy import (
    Column, Integer, String, Text, Boolean, Enum, DECIMAL,
    DateTime, CheckConstraint, UniqueConstraint, Index, ForeignKey
)
from sqlalchemy.dialects.postgresql import UUID as PgUUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.db.base import Base

# User constants for MVP (single user mode)
MVP_USER_ID = "00000000-0000-0000-0000-000000000001"  # Fixed user ID

# PostgreSQL Enum types with explicit names
source_type_enum = Enum(
    'rsshub', 'api', 'rss', 'scraper',
    name='source_type_enum'
)

article_content_type_enum = Enum(
    'unknown', 'article', 'discussion', 'media', 'review',
    name='article_content_type_enum'
)

# Quality level enum for content quality scoring
article_quality_level_enum = Enum(
    'high', 'medium', 'low',
    name='article_quality_level_enum'
)

article_status_enum = Enum(
    'pending', 'processed', 'failed',
    name='article_status_enum'
)

recommendation_type_enum = Enum(
    'daily_digest', 'weekly_author', 'exploration',
    name='recommendation_type_enum'
)

recommendation_status_enum = Enum(
    'pending', 'delivered', 'viewed', 'clicked', 'finished',
    name='recommendation_status_enum'
)

feedback_type_enum = Enum(
    'rating', 'read_later', 'ignore',
    name='feedback_type_enum'
)

reading_queue_status_enum = Enum(
    'active', 'paused', 'completed',
    name='reading_queue_status_enum'
)

scheduler_job_status_enum = Enum(
    'pending', 'running', 'success', 'failed',
    name='scheduler_job_status_enum'
)

email_status_enum = Enum(
    'pending', 'sent', 'failed',
    name='email_status_enum'
)


class Source(Base):
    """Content source management"""
    __tablename__ = "sources"

    # Common fields
    id: Mapped[UUID] = mapped_column(PgUUID(as_uuid=True), primary_key=True, default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

    # Source specific fields
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    domain: Mapped[str] = mapped_column(String(100), nullable=False)
    type: Mapped[str] = mapped_column(
        source_type_enum,
        nullable=False
    )
    base_url: Mapped[str] = mapped_column(String(2048), nullable=False)
    rss_url: Mapped[Optional[str]] = mapped_column(String(2048))
    api_url: Mapped[Optional[str]] = mapped_column(String(2048))
    source_key: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    slug: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    priority: Mapped[int] = mapped_column(Integer, default=1)
    articles_per_day: Mapped[int] = mapped_column(Integer, default=10)

    # Relationships
    articles = relationship("Article", back_populates="source", cascade="all, delete-orphan")
    authors = relationship("Author", back_populates="source", cascade="all, delete-orphan")

    __table_args__ = (
        Index('idx_source_domain', 'domain'),
        Index('idx_source_priority', 'priority'),
        Index('idx_source_active', 'is_active'),
    )


class Author(Base):
    """Content author management"""
    __tablename__ = "authors"

    # Common fields
    id: Mapped[UUID] = mapped_column(PgUUID(as_uuid=True), primary_key=True, default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

    # Author specific fields
    source_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey('sources.id', ondelete='CASCADE'),
        nullable=False
    )
    username: Mapped[Optional[str]] = mapped_column(String(100))
    name: Mapped[Optional[str]] = mapped_column(String(100))
    author_url: Mapped[Optional[str]] = mapped_column(String(2048))
    description: Mapped[Optional[str]] = mapped_column(Text)
    avatar_url: Mapped[Optional[str]] = mapped_column(String(2048))

    # Relationships
    source = relationship("Source", back_populates="authors")
    articles = relationship("Article", back_populates="author")

    __table_args__ = (
        UniqueConstraint('source_id', 'username', name='uq_source_username'),
        Index('idx_author_source_url', 'source_id', 'author_url'),
        Index('idx_author_name', 'name'),
    )


class Article(Base):
    """Content article management"""
    __tablename__ = "articles"

    # Common fields
    id: Mapped[UUID] = mapped_column(PgUUID(as_uuid=True), primary_key=True, default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

    # Article specific fields
    content_hash: Mapped[Optional[str]] = mapped_column(String(64))
    source_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey('sources.id', ondelete='CASCADE'),
        nullable=False
    )
    source_item_id: Mapped[str] = mapped_column(String(256), nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    url: Mapped[str] = mapped_column(String(2048), nullable=False)
    normalized_url: Mapped[str] = mapped_column(String(2048), nullable=False)
    original_content: Mapped[str] = mapped_column(Text, nullable=False)
    summary: Mapped[Optional[str]] = mapped_column(Text)
    content_type: Mapped[str] = mapped_column(
        String(50),
        default='unknown'
    )
    author_id: Mapped[Optional[UUID]] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey('authors.id', ondelete='SET NULL')
    )
    language: Mapped[str] = mapped_column(String(10), default='zh-CN')
    status: Mapped[str] = mapped_column(
        article_status_enum,
        default='pending'
    )
    publish_time: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    crawl_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc)
    )
    process_time: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    word_count: Mapped[int] = mapped_column(Integer, default=0)
    reading_time_minutes: Mapped[int] = mapped_column(Integer, default=0)
    has_images: Mapped[bool] = mapped_column(Boolean, default=False)
    raw_payload: Mapped[Optional[dict]] = mapped_column(JSONB)

    # Classification fields (from ContentClassifier)
    classification_confidence: Mapped[Optional[float]] = mapped_column(DECIMAL(4, 3), nullable=True)
    classification_tags: Mapped[Optional[list]] = mapped_column(JSONB, default=list)
    classification_subcategories: Mapped[Optional[list]] = mapped_column(JSONB, default=list)

    # Quality scoring fields (from ContentQualityScorer)
    quality_level: Mapped[Optional[str]] = mapped_column(article_quality_level_enum, nullable=True)
    overall_score: Mapped[Optional[float]] = mapped_column(DECIMAL(4, 3), nullable=True)
    completeness_score: Mapped[Optional[float]] = mapped_column(DECIMAL(4, 3), nullable=True)
    structure_score: Mapped[Optional[float]] = mapped_column(DECIMAL(4, 3), nullable=True)
    depth_score: Mapped[Optional[float]] = mapped_column(DECIMAL(4, 3), nullable=True)
    credibility_score: Mapped[Optional[float]] = mapped_column(DECIMAL(4, 3), nullable=True)
    engagement_score: Mapped[Optional[float]] = mapped_column(DECIMAL(4, 3), nullable=True)

    # Quality flags
    is_original: Mapped[Optional[bool]] = mapped_column(Boolean, default=True)
    has_citation: Mapped[Optional[bool]] = mapped_column(Boolean, default=False)
    is_clickbait: Mapped[Optional[bool]] = mapped_column(Boolean, default=False)

    # Relationships
    source = relationship("Source", back_populates="articles")
    author = relationship("Author", back_populates="articles")
    recommendations = relationship("Recommendation", back_populates="article", cascade="all, delete-orphan")
    feedbacks = relationship("Feedback", back_populates="article", cascade="all, delete-orphan")
    reading_queues = relationship("ReadingQueue", back_populates="article", cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint('source_id', 'source_item_id', name='uq_source_source_item_id'),
        Index('idx_article_content_hash', 'content_hash'),
        Index('idx_article_crawl_time', 'crawl_time'),
        Index('idx_article_status', 'status'),
        Index('idx_article_author', 'author_id'),
    )


class Recommendation(Base):
    """Content recommendation results"""
    __tablename__ = "recommendations"

    # Common fields
    id: Mapped[UUID] = mapped_column(PgUUID(as_uuid=True), primary_key=True, default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

    # Recommendation specific fields
    user_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True),
        nullable=False,
        default=lambda: MVP_USER_ID
    )
    article_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey('articles.id', ondelete='CASCADE'),
        nullable=False
    )
    recommendation_type: Mapped[str] = mapped_column(
        recommendation_type_enum,
        nullable=False
    )
    score: Mapped[DECIMAL] = mapped_column(DECIMAL(10, 4), nullable=False)
    rank: Mapped[int] = mapped_column(Integer, nullable=False)
    batch_date: Mapped[str] = mapped_column(String(10), nullable=False)  # Format: YYYY-MM-DD
    status: Mapped[str] = mapped_column(
        recommendation_status_enum,
        default='pending'
    )
    delivered_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    # Relationships
    article = relationship("Article", back_populates="recommendations")
    feedbacks = relationship("Feedback", back_populates="recommendation")

    __table_args__ = (
        UniqueConstraint('user_id', 'article_id', 'recommendation_type', 'batch_date',
                        name='uq_user_article_type_batch_date'),
        Index('idx_recommendation_batch_date', 'batch_date'),
        Index('idx_recommendation_status', 'status'),
        Index('idx_recommendation_rank', 'rank'),
    )


class Feedback(Base):
    """User feedback on content"""
    __tablename__ = "feedbacks"

    # Common fields
    id: Mapped[UUID] = mapped_column(PgUUID(as_uuid=True), primary_key=True, default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

    # Feedback specific fields
    user_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True),
        nullable=False,
        default=lambda: MVP_USER_ID
    )
    article_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey('articles.id', ondelete='CASCADE'),
        nullable=False
    )
    recommendation_id: Mapped[Optional[UUID]] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey('recommendations.id', ondelete='SET NULL')
    )
    feedback_type: Mapped[str] = mapped_column(
        feedback_type_enum,
        nullable=False
    )
    rating: Mapped[Optional[int]] = mapped_column(
        Integer,
        CheckConstraint('rating >= 1 AND rating <= 9')
    )

    # Relationships
    article = relationship("Article", back_populates="feedbacks")
    recommendation = relationship("Recommendation", back_populates="feedbacks")

    __table_args__ = (
        Index('idx_feedback_created_at', 'created_at'),
        Index('idx_feedback_article_rating', 'article_id', 'rating'),
        Index('idx_feedback_type', 'feedback_type'),
    )


class ReadingQueue(Base):
    """User's reading queue / to-read list"""
    __tablename__ = "reading_queues"

    # Common fields
    id: Mapped[UUID] = mapped_column(PgUUID(as_uuid=True), primary_key=True, default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

    # ReadingQueue specific fields
    user_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True),
        nullable=False,
        default=lambda: MVP_USER_ID
    )
    article_id: Mapped[UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey('articles.id', ondelete='CASCADE'),
        nullable=False
    )
    status: Mapped[str] = mapped_column(
        reading_queue_status_enum,
        default='active'
    )
    added_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc)
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)

    # Relationships
    article = relationship("Article", back_populates="reading_queues")

    __table_args__ = (
        UniqueConstraint('user_id', 'article_id', name='uq_user_article_id'),
        Index('idx_reading_queue_user_active', 'user_id', 'status'),
        Index('idx_reading_queue_added_at', 'added_at'),
        Index('idx_reading_queue_position', 'position'),
    )


class SchedulerJob(Base):
    """Scheduled job execution history and status tracking"""
    __tablename__ = "scheduler_jobs"

    # Common fields
    id: Mapped[UUID] = mapped_column(PgUUID(as_uuid=True), primary_key=True, default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

    # Job specific fields
    job_name: Mapped[str] = mapped_column(String(100), nullable=False)
    batch_date: Mapped[str] = mapped_column(String(10), nullable=False)  # Format: YYYY-MM-DD
    status: Mapped[str] = mapped_column(
        scheduler_job_status_enum,
        default='pending'
    )
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    duration_seconds: Mapped[Optional[float]] = mapped_column(DECIMAL(10, 3))
    result_message: Mapped[Optional[str]] = mapped_column(Text)
    error_message: Mapped[Optional[str]] = mapped_column(Text)

    # Job parameters and results (JSON for flexibility)
    job_params: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)
    job_results: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)

    __table_args__ = (
        UniqueConstraint('job_name', 'batch_date', name='uq_job_name_batch_date'),
        Index('idx_scheduler_job_batch_date', 'batch_date'),
        Index('idx_scheduler_job_status', 'status'),
        Index('idx_scheduler_job_started_at', 'started_at'),
    )


class EmailLog(Base):
    """Email sending log for tracking delivery status"""
    __tablename__ = "email_logs"

    # Common fields
    id: Mapped[UUID] = mapped_column(PgUUID(as_uuid=True), primary_key=True, default=None)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))

    # Email specific fields
    batch_date: Mapped[str] = mapped_column(String(10), nullable=False)  # Format: YYYY-MM-DD
    email_type: Mapped[str] = mapped_column(String(50), nullable=False)  # 'daily_digest', 'test'
    status: Mapped[str] = mapped_column(
        email_status_enum,
        default='pending'
    )
    to_email: Mapped[str] = mapped_column(String(256), nullable=False)
    from_email: Mapped[str] = mapped_column(String(256), nullable=False)
    subject: Mapped[str] = mapped_column(String(500), nullable=False)

    # Sending timestamps
    sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    failed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    # Content info
    recommendation_count: Mapped[int] = mapped_column(Integer, default=0)

    # Error info
    error_message: Mapped[Optional[str]] = mapped_column(Text)

    # Response info (from email provider)
    message_id: Mapped[Optional[str]] = mapped_column(String(256))

    __table_args__ = (
        Index('idx_email_log_batch_date', 'batch_date'),
        Index('idx_email_log_status', 'status'),
        Index('idx_email_log_sent_at', 'sent_at'),
        Index('idx_email_log_email_type', 'email_type'),
    )