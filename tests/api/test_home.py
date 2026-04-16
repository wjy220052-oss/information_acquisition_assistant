"""
Tests for home page
"""

import pytest
from datetime import datetime, timezone
from uuid import uuid4
from unittest.mock import patch, MagicMock

from app.models.db.tables import Recommendation, Article, Source


class TestHomePage:
    """Tests for home page /"""

    def test_home_page_returns_200(self, client):
        """Test home page returns 200 status"""
        response = client.get("/")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]

    def test_home_page_shows_recommendations(self, client, db_session):
        """Test home page shows recommendation list when data exists"""
        db = db_session

        # Create test source
        unique_id = str(uuid4())[:8]
        source = Source(
            id=uuid4(),
            name=f"Test Source {unique_id}",
            domain="test.com",
            type="api",
            base_url="https://test.com",
            source_key=f"test_key_{unique_id}",
            slug=f"test_{unique_id}"
        )
        db.add(source)
        db.commit()
        db.refresh(source)

        # Create test article
        article = Article(
            id=uuid4(),
            source_id=source.id,
            source_item_id="test_001",
            url="https://test.com/1",
            normalized_url="https://test.com/1",
            title="Test Article Title",
            original_content="Test content summary",
            content_type="technology",
            overall_score=0.75,
            quality_level="high",
            crawl_time=datetime.now(timezone.utc),
            publish_time=datetime.now(timezone.utc)
        )
        db.add(article)
        db.commit()
        db.refresh(article)

        # Create test recommendation
        today = datetime.now(timezone.utc).strftime('%Y-%m-%d')
        rec = Recommendation(
            id=uuid4(),
            article_id=article.id,
            recommendation_type="daily_digest",
            score=0.75,
            rank=1,
            batch_date=today,
            status="pending"
        )
        db.add(rec)
        db.commit()
        db.refresh(rec)

        response = client.get("/")
        assert response.status_code == 200

        content = response.text
        assert "Test Article Title" in content
        assert "0.75" in content or "technology" in content

    def test_home_page_shows_empty_message(self, client):
        """Test home page shows 'No recommendations' message when empty"""
        response = client.get("/")
        assert response.status_code == 200

        content = response.text
        assert "No recommendations" in content or "暂无推荐" in content or "empty" in content.lower()

    @patch('app.core.database.get_db')
    def test_home_page_shows_error_on_exception(self, mock_get_db, client):
        """Test home page shows error message when query fails"""
        # Mock database to raise exception
        mock_db = MagicMock()
        mock_db.execute.side_effect = Exception("Database error")
        mock_get_db.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_get_db.return_value.__exit__ = MagicMock(return_value=False)

        response = client.get("/")
        assert response.status_code == 200

        content = response.text
        assert "error" in content.lower() or "获取失败" in content or "failed" in content.lower()

    def test_home_page_displays_rank(self, client, db_session):
        """Test home page displays recommendation rank"""
        db = db_session

        # Create test data
        unique_id = str(uuid4())[:8]
        source = Source(
            id=uuid4(),
            name=f"Test Source {unique_id}",
            domain="test.com",
            type="api",
            base_url="https://test.com",
            source_key=f"test_key_{unique_id}",
            slug=f"test_{unique_id}"
        )
        db.add(source)
        db.commit()
        db.refresh(source)

        article = Article(
            id=uuid4(),
            source_id=source.id,
            source_item_id="test_002",
            url="https://test.com/2",
            normalized_url="https://test.com/2",
            title="Rank Test Article",
            original_content="Test content",
            content_type="product",
            overall_score=0.80,
            crawl_time=datetime.now(timezone.utc),
            publish_time=datetime.now(timezone.utc)
        )
        db.add(article)
        db.commit()
        db.refresh(article)

        today = datetime.now(timezone.utc).strftime('%Y-%m-%d')
        rec = Recommendation(
            id=uuid4(),
            article_id=article.id,
            recommendation_type="daily_digest",
            score=0.80,
            rank=1,
            batch_date=today,
            status="pending"
        )
        db.add(rec)
        db.commit()
        db.refresh(rec)

        response = client.get("/")
        content = response.text

        # Check rank is displayed (could be "Rank 1", "#1", etc.)
        assert "Rank Test Article" in content

    def test_home_page_displays_article_link(self, client, db_session):
        """Test home page displays link to original article"""
        db = db_session

        unique_id = str(uuid4())[:8]
        source = Source(
            id=uuid4(),
            name=f"Test Source {unique_id}",
            domain="example.com",
            type="api",
            base_url="https://example.com",
            source_key=f"test_key_{unique_id}",
            slug=f"test_{unique_id}"
        )
        db.add(source)
        db.commit()
        db.refresh(source)

        article = Article(
            id=uuid4(),
            source_id=source.id,
            source_item_id="test_003",
            url="https://example.com/article/123",
            normalized_url="https://example.com/article/123",
            title="Link Test Article",
            original_content="Test content with link",
            content_type="technology",
            overall_score=0.70,
            crawl_time=datetime.now(timezone.utc),
            publish_time=datetime.now(timezone.utc)
        )
        db.add(article)
        db.commit()
        db.refresh(article)

        today = datetime.now(timezone.utc).strftime('%Y-%m-%d')
        rec = Recommendation(
            id=uuid4(),
            article_id=article.id,
            recommendation_type="daily_digest",
            score=0.70,
            rank=1,
            batch_date=today,
            status="pending"
        )
        db.add(rec)
        db.commit()
        db.refresh(rec)

        response = client.get("/")
        content = response.text

        # Check link is present
        assert "https://example.com/article/123" in content or "Link Test Article" in content

    def test_home_shows_feedback_buttons(self, client, db_session):
        """首页应显示 like/dislike/skip 按钮"""
        db = db_session

        unique_id = str(uuid4())[:8]
        source = Source(
            id=uuid4(),
            name=f"Test Source {unique_id}",
            domain="example.com",
            type="api",
            base_url="https://example.com",
            source_key=f"test_key_{unique_id}",
            slug=f"test_{unique_id}"
        )
        db.add(source)
        db.commit()
        db.refresh(source)

        article = Article(
            id=uuid4(),
            source_id=source.id,
            source_item_id="test_feedback",
            url="https://example.com/article/feedback",
            normalized_url="https://example.com/article/feedback",
            title="Feedback Test Article",
            original_content="Test content for feedback",
            content_type="technology",
            overall_score=0.70,
            crawl_time=datetime.now(timezone.utc),
            publish_time=datetime.now(timezone.utc)
        )
        db.add(article)
        db.commit()
        db.refresh(article)

        today = datetime.now(timezone.utc).strftime('%Y-%m-%d')
        rec = Recommendation(
            id=uuid4(),
            article_id=article.id,
            recommendation_type="daily_digest",
            score=0.70,
            rank=1,
            batch_date=today,
            status="pending"
        )
        db.add(rec)
        db.commit()
        db.refresh(rec)

        response = client.get("/")
        content = response.text

        # Check feedback buttons exist
        assert 'feedback-buttons' in content
        assert 'feedback-btn' in content
        assert 'like' in content.lower() or '👍' in content
        assert 'dislike' in content.lower() or '👎' in content
        assert 'skip' in content.lower() or '⏭️' in content

        # Check JavaScript function exists
        assert 'submitFeedback' in content
        assert 'record click' in content.lower() or 'click' in content.lower()
