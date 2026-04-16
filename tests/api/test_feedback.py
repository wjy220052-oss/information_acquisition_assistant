"""
Feedback API tests

Tests for feedback and click tracking endpoints.
"""

import pytest
from datetime import datetime, timezone
from uuid import uuid4, UUID

from app.models.db.tables import (
    Recommendation, Article, Source, Author, Feedback, MVP_USER_ID
)


@pytest.fixture
def test_source(db_session):
    """Create a test source with unique identifier"""
    unique_id = str(uuid4())[:8]
    source = Source(
        id=uuid4(),
        name=f"Test Source {unique_id}",
        domain="test.com",
        type="api",
        base_url="https://test.com",
        source_key=f"test_source_{unique_id}",
        slug=f"test-source-{unique_id}",
    )
    db_session.add(source)
    db_session.flush()  # Flush to get the ID assigned without committing
    db_session.refresh(source)  # Refresh to populate any defaults
    return source


@pytest.fixture
def test_author(db_session, test_source):
    """Create a test author"""
    unique_id = str(uuid4())[:8]
    author = Author(
        id=uuid4(),
        source_id=test_source.id,
        name=f"Test Author {unique_id}",
        username=f"testauthor_{unique_id}",
    )
    db_session.add(author)
    db_session.flush()
    db_session.refresh(author)
    return author


@pytest.fixture
def test_article(db_session, test_source, test_author):
    """Create a test article with unique identifier"""
    unique_id = str(uuid4())[:8]
    article = Article(
        id=uuid4(),
        source_id=test_source.id,
        author_id=test_author.id,
        source_item_id=f"test-{unique_id}",
        title=f"Test Article {unique_id}",
        url=f"https://test.com/article/{unique_id}",
        normalized_url=f"https://test.com/article/{unique_id}",
        original_content="Test content",
        summary="Test summary",
        content_type="article",
        word_count=1000,
        reading_time_minutes=5,
    )
    db_session.add(article)
    db_session.flush()
    db_session.refresh(article)
    return article


@pytest.fixture
def test_recommendation(db_session, test_article):
    """Create a test recommendation"""
    rec = Recommendation(
        id=uuid4(),
        user_id=UUID(MVP_USER_ID),
        article_id=test_article.id,
        recommendation_type="daily_digest",
        score=0.5,
        rank=1,
        batch_date=datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        status="pending",
    )
    db_session.add(rec)
    db_session.flush()
    db_session.refresh(rec)
    return rec


class TestClickAPI:
    """Tests for POST /api/recommendations/{id}/click"""

    def test_click_records_status_change(self, client, db_session, test_recommendation):
        """点击 API 应更新 recommendation.status 为 clicked"""
        response = client.post(
            f"/api/recommendations/{test_recommendation.id}/click",
            json={"source": "homepage"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "redirect_url" in data

        # Verify database update
        db_session.refresh(test_recommendation)
        assert test_recommendation.status == "clicked"

    def test_click_returns_redirect_url(self, client, db_session, test_recommendation, test_article):
        """点击 API 应返回原文链接用于跳转"""
        response = client.post(
            f"/api/recommendations/{test_recommendation.id}/click",
            json={}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["redirect_url"] == test_article.url

    def test_click_without_source_param(self, client, test_recommendation):
        """点击 API 应允许不带 source 参数"""
        response = client.post(
            f"/api/recommendations/{test_recommendation.id}/click",
            json={}
        )

        assert response.status_code == 200
        assert response.json()["success"] is True

    def test_click_nonexistent_recommendation(self, client):
        """对不存在的推荐点击应返回 404"""
        fake_id = "12345678-1234-1234-1234-123456789abc"
        response = client.post(
            f"/api/recommendations/{fake_id}/click",
            json={}
        )

        assert response.status_code == 404

    def test_click_repeat_is_tolerated(self, client, db_session, test_recommendation):
        """重复点击不应报错（返回 200 或恰当状态）"""
        # First click
        response1 = client.post(
            f"/api/recommendations/{test_recommendation.id}/click",
            json={}
        )
        assert response1.status_code == 200

        # Second click (repeat)
        response2 = client.post(
            f"/api/recommendations/{test_recommendation.id}/click",
            json={}
        )
        # Should not be 500, can be 200 (idempotent) or another appropriate code
        assert response2.status_code != 500


class TestFeedbackAPI:
    """Tests for POST /api/recommendations/{id}/feedback"""

    def test_like_creates_rating_feedback(self, client, db_session, test_recommendation):
        """like 应创建 feedback_type='rating', rating=8 的记录"""
        response = client.post(
            f"/api/recommendations/{test_recommendation.id}/feedback",
            json={"action": "like"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "feedback_id" in data

        # Verify database
        feedback = db_session.query(Feedback).filter(
            Feedback.recommendation_id == test_recommendation.id
        ).first()
        assert feedback is not None
        assert feedback.feedback_type == "rating"
        assert feedback.rating == 8

    def test_dislike_creates_low_rating(self, client, db_session, test_recommendation):
        """dislike 应创建 rating=2 的记录"""
        response = client.post(
            f"/api/recommendations/{test_recommendation.id}/feedback",
            json={"action": "dislike"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

        # Verify database
        feedback = db_session.query(Feedback).filter(
            Feedback.recommendation_id == test_recommendation.id
        ).first()
        assert feedback is not None
        assert feedback.feedback_type == "rating"
        assert feedback.rating == 2

    def test_skip_creates_ignore_feedback(self, client, db_session, test_recommendation):
        """skip 应创建 feedback_type='ignore' 的记录"""
        response = client.post(
            f"/api/recommendations/{test_recommendation.id}/feedback",
            json={"action": "skip"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

        # Verify database
        feedback = db_session.query(Feedback).filter(
            Feedback.recommendation_id == test_recommendation.id
        ).first()
        assert feedback is not None
        assert feedback.feedback_type == "ignore"
        assert feedback.rating is None

    def test_invalid_action_returns_422(self, client, test_recommendation):
        """非法 feedback 值应返回 4xx"""
        response = client.post(
            f"/api/recommendations/{test_recommendation.id}/feedback",
            json={"action": "invalid_action"}
        )

        assert response.status_code == 422

    def test_feedback_for_nonexistent_recommendation(self, client):
        """对不存在的推荐反馈应返回 404"""
        fake_id = "12345678-1234-1234-1234-123456789abc"
        response = client.post(
            f"/api/recommendations/{fake_id}/feedback",
            json={"action": "like"}
        )

        assert response.status_code == 404

    def test_duplicate_feedback_is_tolerated(self, client, db_session, test_recommendation):
        """重复反馈不应 500（应更新或忽略）"""
        # First feedback
        response1 = client.post(
            f"/api/recommendations/{test_recommendation.id}/feedback",
            json={"action": "like"}
        )
        assert response1.status_code == 200

        # Second feedback (repeat)
        response2 = client.post(
            f"/api/recommendations/{test_recommendation.id}/feedback",
            json={"action": "like"}
        )
        # Should not be 500
        assert response2.status_code != 500
        # Can be 200 (updated) or another success code
        assert response2.status_code in [200, 201]

    def test_feedback_updates_existing_record(self, client, db_session, test_recommendation):
        """重复反馈应更新现有记录而非创建新记录"""
        # First like
        client.post(
            f"/api/recommendations/{test_recommendation.id}/feedback",
            json={"action": "like"}
        )

        # Then dislike (should update)
        response = client.post(
            f"/api/recommendations/{test_recommendation.id}/feedback",
            json={"action": "dislike"}
        )
        assert response.status_code == 200

        # Should only have one feedback record
        feedbacks = db_session.query(Feedback).filter(
            Feedback.recommendation_id == test_recommendation.id
        ).all()
        assert len(feedbacks) == 1
        assert feedbacks[0].rating == 2

    def test_feedback_without_action_returns_422(self, client, test_recommendation):
        """缺少 action 参数应返回 422"""
        response = client.post(
            f"/api/recommendations/{test_recommendation.id}/feedback",
            json={}
        )

        assert response.status_code == 422
