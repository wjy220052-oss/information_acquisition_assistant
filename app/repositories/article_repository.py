"""
Article repository for database operations
"""

import hashlib
import logging
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy.orm import Session
from sqlalchemy import select, and_, or_

from app.models.db.tables import Article, Source, Author
from app.models.schemas.source import SourceItem, SourceType

logger = logging.getLogger(__name__)


class ArticleRepository:
    """Repository for Article CRUD operations"""

    def __init__(self, db: Session):
        """
        Initialize repository with database session

        Args:
            db: SQLAlchemy session
        """
        self.db = db

    def get_or_create_source(
        self,
        name: str,
        domain: str,
        source_type: SourceType,
        base_url: str,
        source_key: str,
        slug: str,
    ) -> Source:
        """
        Get existing source or create new one

        Args:
            name: Source name
            domain: Source domain
            source_type: Source type enum
            base_url: Base URL
            source_key: Unique key for the source
            slug: URL-friendly slug

        Returns:
            Source instance
        """
        # Try to find by source_key
        stmt = select(Source).where(Source.source_key == source_key)
        result = self.db.execute(stmt).scalar_one_or_none()

        if result:
            return result

        # Create new source
        source = Source(
            id=uuid4(),
            name=name,
            domain=domain,
            type=source_type.value,
            base_url=base_url,
            source_key=source_key,
            slug=slug,
            is_active=True,
            priority=1,
            articles_per_day=10,
            created_at=datetime.now(timezone.utc),
        )
        self.db.add(source)
        self.db.commit()
        self.db.refresh(source)
        logger.info(f"Created new source: {name} ({source_key})")
        return source

    def get_or_create_author(
        self,
        source_id: str,
        username: Optional[str] = None,
        name: Optional[str] = None,
        author_url: Optional[str] = None,
        description: Optional[str] = None,
        avatar_url: Optional[str] = None,
    ) -> Optional[Author]:
        """
        Get existing author or create new one

        Args:
            source_id: Source ID
            username: Author username
            name: Display name
            author_url: Profile URL
            description: Bio/description
            avatar_url: Avatar image URL

        Returns:
            Author instance or None if no author info provided
        """
        # If no author info, return None
        if not username and not name:
            return None

        # Try to find by source_id and username
        if username:
            stmt = select(Author).where(
                and_(
                    Author.source_id == source_id,
                    Author.username == username
                )
            )
            result = self.db.execute(stmt).scalar_one_or_none()
            if result:
                return result

        # Try to find by author_url
        if author_url:
            stmt = select(Author).where(
                and_(
                    Author.source_id == source_id,
                    Author.author_url == author_url
                )
            )
            result = self.db.execute(stmt).scalar_one_or_none()
            if result:
                return result

        # Create new author
        author = Author(
            id=uuid4(),
            source_id=source_id,
            username=username,
            name=name,
            author_url=author_url,
            description=description,
            avatar_url=avatar_url,
            created_at=datetime.now(timezone.utc),
        )
        self.db.add(author)
        self.db.commit()
        self.db.refresh(author)
        logger.debug(f"Created new author: {username or name}")
        return author

    def upsert_article(
        self,
        item: SourceItem,
        source_id: str,
        author_id: Optional[str] = None,
        original_content: Optional[str] = None,
        classification: Optional[Dict[str, Any]] = None,
        quality: Optional[Dict[str, Any]] = None,
    ) -> tuple[Article, bool]:
        """
        Insert new article or update existing one

        Args:
            item: SourceItem containing article data
            source_id: Source ID
            author_id: Optional author ID
            original_content: Full article content
            classification: Optional classification dict with keys:
                - content_type: str
                - confidence: float
                - tags: List[str]
                - subcategories: List[str]
            quality: Optional quality dict with keys:
                - overall_score: float
                - quality_level: str
                - completeness_score: float
                - structure_score: float
                - depth_score: float
                - credibility_score: float
                - engagement_score: float
                - is_original: bool
                - has_citation: bool
                - is_clickbait: bool

        Returns:
            Tuple of (Article instance, is_new boolean)
        """
        # Generate content hash for deduplication
        content_hash = self._generate_content_hash(item.title, item.url, item.summary)

        # Check for existing article by (source_id, source_item_id)
        stmt = select(Article).where(
            and_(
                Article.source_id == source_id,
                Article.source_item_id == item.source_item_id
            )
        )
        result = self.db.execute(stmt).scalar_one_or_none()

        if result:
            # Update existing article
            result.title = item.title
            result.url = item.url
            result.normalized_url = item.normalized_url
            result.summary = item.summary
            result.original_content = original_content or result.original_content
            result.content_hash = content_hash
            result.publish_time = item.publish_time or result.publish_time
            if author_id:
                result.author_id = author_id
            if item.raw_data:
                result.raw_payload = item.raw_data
            result.crawl_time = datetime.now(timezone.utc)

            # Update classification fields if provided
            if classification:
                if classification.get('content_type'):
                    result.content_type = classification['content_type']
                if classification.get('confidence') is not None:
                    result.classification_confidence = classification['confidence']
                if classification.get('tags'):
                    result.classification_tags = classification['tags']
                if classification.get('subcategories'):
                    result.classification_subcategories = classification['subcategories']

            # Update quality fields if provided
            if quality:
                if quality.get('overall_score') is not None:
                    result.overall_score = quality['overall_score']
                if quality.get('quality_level'):
                    result.quality_level = quality['quality_level']
                if quality.get('completeness_score') is not None:
                    result.completeness_score = quality['completeness_score']
                if quality.get('structure_score') is not None:
                    result.structure_score = quality['structure_score']
                if quality.get('depth_score') is not None:
                    result.depth_score = quality['depth_score']
                if quality.get('credibility_score') is not None:
                    result.credibility_score = quality['credibility_score']
                if quality.get('engagement_score') is not None:
                    result.engagement_score = quality['engagement_score']
                if quality.get('is_original') is not None:
                    result.is_original = quality['is_original']
                if quality.get('has_citation') is not None:
                    result.has_citation = quality['has_citation']
                if quality.get('is_clickbait') is not None:
                    result.is_clickbait = quality['is_clickbait']

            self.db.commit()
            self.db.refresh(result)
            logger.debug(f"Updated article: {item.source_item_id}")
            return result, False
        else:
            # Build article data with optional classification/quality fields
            article_data = dict(
                id=uuid4(),
                source_id=source_id,
                source_item_id=item.source_item_id,
                title=item.title,
                url=item.url,
                normalized_url=item.normalized_url,
                original_content=original_content or item.summary or "",
                summary=item.summary,
                content_hash=content_hash,
                author_id=author_id,
                language="zh-CN",
                status="pending",
                publish_time=item.publish_time,
                crawl_time=datetime.now(timezone.utc),
                raw_payload=item.raw_data,
                created_at=datetime.now(timezone.utc),
            )

            # Add classification fields if provided
            if classification:
                article_data['content_type'] = classification.get('content_type', 'unknown')
                article_data['classification_confidence'] = classification.get('confidence')
                article_data['classification_tags'] = classification.get('tags', [])
                article_data['classification_subcategories'] = classification.get('subcategories', [])

            # Add quality fields if provided
            if quality:
                article_data['overall_score'] = quality.get('overall_score')
                article_data['quality_level'] = quality.get('quality_level')
                article_data['completeness_score'] = quality.get('completeness_score')
                article_data['structure_score'] = quality.get('structure_score')
                article_data['depth_score'] = quality.get('depth_score')
                article_data['credibility_score'] = quality.get('credibility_score')
                article_data['engagement_score'] = quality.get('engagement_score')
                article_data['is_original'] = quality.get('is_original', True)
                article_data['has_citation'] = quality.get('has_citation', False)
                article_data['is_clickbait'] = quality.get('is_clickbait', False)

            article = Article(**article_data)
            self.db.add(article)
            self.db.commit()
            self.db.refresh(article)
            logger.info(f"Created new article: {item.source_item_id} - {item.title}")
            return article, True

    def get_articles_by_status(self, status: str, limit: int = 100) -> List[Article]:
        """
        Get articles by status

        Args:
            status: Article status (pending, processed, failed)
            limit: Maximum number to return

        Returns:
            List of Article instances
        """
        stmt = (
            select(Article)
            .where(Article.status == status)
            .order_by(Article.crawl_time.desc())
            .limit(limit)
        )
        result = self.db.execute(stmt).scalars().all()
        return list(result)

    def update_article_status(
        self,
        article_id: str,
        status: str,
        process_time: Optional[datetime] = None
    ) -> Optional[Article]:
        """
        Update article status

        Args:
            article_id: Article ID
            status: New status
            process_time: Optional process time

        Returns:
            Updated Article instance or None
        """
        stmt = select(Article).where(Article.id == article_id)
        result = self.db.execute(stmt).scalar_one_or_none()

        if result:
            result.status = status
            result.process_time = process_time or datetime.now(timezone.utc)
            self.db.commit()
            self.db.refresh(result)
            logger.debug(f"Updated article {article_id} status to {status}")
            return result

        return None

    def _generate_content_hash(self, title: str, url: str, summary: Optional[str]) -> str:
        """
        Generate content hash for deduplication

        Args:
            title: Article title
            url: Article URL
            summary: Optional summary

        Returns:
            SHA256 hash string
        """
        content = f"{title}|{url}|{summary or ''}"
        return hashlib.sha256(content.encode()).hexdigest()

    def get_articles_for_recommendation(
        self,
        min_overall_score: float = 0.6,
        limit: int = 100,
        exclude_article_ids: Optional[List[str]] = None,
    ) -> List[Article]:
        """
        Get high-quality articles for recommendation generation

        Args:
            min_overall_score: Minimum overall_score threshold
            limit: Maximum number of articles to return
            exclude_article_ids: Article IDs to exclude (e.g., already recommended)

        Returns:
            List of Article instances sorted by overall_score DESC
        """
        from sqlalchemy import desc

        stmt = (
            select(Article)
            .where(
                and_(
                    Article.overall_score >= min_overall_score,
                    Article.status == 'pending'  # Only recommend pending articles
                )
            )
            .order_by(desc(Article.overall_score), desc(Article.crawl_time))
            .limit(limit)
        )

        # Exclude already recommended articles if provided
        if exclude_article_ids:
            stmt = stmt.where(~Article.id.in_(exclude_article_ids))

        result = self.db.execute(stmt).scalars().all()
        return list(result)

    def get_article_by_id(self, article_id: str) -> Optional[Article]:
        """Get article by ID"""
        stmt = select(Article).where(Article.id == article_id)
        result = self.db.execute(stmt).scalar_one_or_none()
        return result
