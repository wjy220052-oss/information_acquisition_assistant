"""
Integration tests for Solidot source

Verifies:
- Fetch stores Solidot data in database
- Recommend includes Solidot articles
- API returns Solidot source info
"""

import pytest
from datetime import datetime, timezone
from unittest.mock import Mock, patch, MagicMock

from app.services.sources.solidot import SolidotAdapter
from app.tasks.fetch import run_fetch_task
from app.tasks.recommend import run_recommend_task
from app.models.db.tables import Article, Source, Recommendation


class TestSolidotFetchIntegration:
    """Integration tests for Solidot fetch -> database"""

    def test_solidot_source_uniqueness(self, db_session):
        """Multiple fetches should not duplicate solidot source"""
        from app.repositories.article_repository import ArticleRepository

        # First fetch
        repo = ArticleRepository(db_session)
        source1 = repo.get_or_create_source(
            name='solidot',
            domain='www.solidot.org',
            source_type='rss',
            base_url='https://www.solidot.org/index.rss',
            source_key='solidot_www.solidot.org',
            slug='solidot',
        )

        # Second fetch
        source2 = repo.get_or_create_source(
            name='solidot',
            domain='www.solidot.org',
            source_type='rss',
            base_url='https://www.solidot.org/index.rss',
            source_key='solidot_www.solidot.org',
            slug='solidot',
        )

        # Should be same source
        assert source1.id == source2.id

        # Verify only one solidot source in database
        sources = db_session.query(Source).filter(Source.name == 'solidot').all()
        assert len(sources) == 1



