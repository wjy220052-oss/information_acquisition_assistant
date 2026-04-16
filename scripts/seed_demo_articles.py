"""
Seed demo articles for testing recommendations.

This script inserts minimal demo data into the development database
for testing the recommendation flow. It uses upsert to avoid duplicates.

Usage:
    python scripts/seed_demo_articles.py
"""

import sys
from pathlib import Path
from datetime import datetime, timezone
from uuid import uuid4
from decimal import Decimal

from sqlalchemy import select

# Add parent directory to path for imports
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.core.database import get_db
from app.core.logging import get_logger
from app.models.db.tables import Article, Source

logger = get_logger(__name__)


# Demo articles data
DEMO_ARTICLES = [
    {
        "source_item_id": "demo_tech_001",
        "url": "https://example.com/tech/001",
        "title": "深入理解 Python 异步编程：从 asyncio 到实际应用",
        "content": "Python 的 asyncio 模块为并发编程提供了强大的支持...",
        "content_type": "technology",
        "overall_score": Decimal("0.85"),
        "quality_level": "high",
    },
    {
        "source_item_id": "demo_product_001",
        "url": "https://example.com/product/001",
        "title": "产品思维：如何从用户反馈中发现真正的需求",
        "content": "产品经理每天都在面对大量的用户反馈...",
        "content_type": "product",
        "overall_score": Decimal("0.78"),
        "quality_level": "high",
    },
    {
        "source_item_id": "demo_culture_001",
        "url": "https://example.com/culture/001",
        "title": "阅读的本质：在信息洪流中重建深度思考",
        "content": "在短视频和碎片化信息充斥的时代...",
        "content_type": "culture",
        "overall_score": Decimal("0.72"),
        "quality_level": "high",
    },
    {
        "source_item_id": "demo_tech_002",
        "url": "https://example.com/tech/002",
        "title": "分布式系统设计的核心原则与实践",
        "content": "构建可靠的分布式系统需要理解一致性...",
        "content_type": "technology",
        "overall_score": Decimal("0.68"),
        "quality_level": "high",
    },
]


def get_or_create_demo_source(db):
    """Get existing demo source or create a new one."""
    # Try to find existing demo source
    stmt = select(Source).where(Source.source_key == "demo_source")
    result = db.execute(stmt)
    source = result.scalar_one_or_none()

    if source:
        logger.info(f"Found existing demo source: {source.id}")
        return source

    # Create new demo source
    source = Source(
        id=uuid4(),
        name="Demo Source",
        domain="example.com",
        type="api",
        base_url="https://example.com",
        source_key="demo_source",
        slug="demo",
    )
    db.add(source)
    db.commit()
    logger.info(f"Created demo source: {source.id}")
    return source


def seed_articles(db, source_id: str) -> tuple:
    """
    Seed demo articles using upsert.

    Returns:
        tuple: (inserted_count, skipped_count)
    """
    inserted = 0
    skipped = 0

    for article_data in DEMO_ARTICLES:
        # Check if article already exists by source_item_id and source_id
        stmt = select(Article).where(
            Article.source_id == source_id,
            Article.source_item_id == article_data["source_item_id"]
        )
        result = db.execute(stmt)
        existing = result.scalar_one_or_none()

        if existing:
            logger.info(f"Skipping existing article: {article_data['title'][:40]}...")
            skipped += 1
            continue

        # Create new article
        article = Article(
            id=uuid4(),
            source_id=source_id,
            source_item_id=article_data["source_item_id"],
            url=article_data["url"],
            normalized_url=article_data["url"],
            title=article_data["title"],
            original_content=article_data["content"],
            content_type=article_data["content_type"],
            overall_score=float(article_data["overall_score"]),
            quality_level=article_data["quality_level"],
            crawl_time=datetime.now(timezone.utc),
            publish_time=datetime.now(timezone.utc),
        )
        db.add(article)
        inserted += 1
        logger.info(f"Inserted article: {article_data['title'][:40]}...")

    db.commit()
    return inserted, skipped


def main():
    """Main entry point."""
    logger.info("Starting demo data seeding...")

    with get_db() as db:
        # Get or create demo source
        source = get_or_create_demo_source(db)

        # Seed articles
        inserted, skipped = seed_articles(db, source.id)

    logger.info("=" * 50)
    logger.info(f"Seeding complete!")
    logger.info(f"  Inserted: {inserted} articles")
    logger.info(f"  Skipped:  {skipped} articles (already exist)")
    logger.info(f"  Total:    {inserted + skipped} articles")
    logger.info("=" * 50)

    return inserted, skipped


if __name__ == "__main__":
    try:
        inserted, skipped = main()
        print(f"\n{'='*50}")
        print(f"Seeding complete!")
        print(f"  Inserted: {inserted} articles")
        print(f"  Skipped:  {skipped} articles")
        print(f"  Total:    {inserted + skipped} articles")
        print(f"{'='*50}")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Seeding failed: {e}")
        print(f"\nError: {e}")
        sys.exit(1)
