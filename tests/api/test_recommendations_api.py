"""
Tests for recommendations API endpoints
"""

import pytest
from datetime import datetime, timezone
from uuid import uuid4
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
from sqlalchemy.exc import SQLAlchemyError, OperationalError

from app.main import app
from app.core.database import get_db_session
from app.models.db.tables import Source, Article, Recommendation


@pytest.fixture
def client(setup_database):
    """Create test client with database setup"""
    return TestClient(app)


@pytest.fixture
def db_session(setup_database):
    """Create a database session for tests"""
    session = get_db_session()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


@pytest.fixture
def test_source(db_session):
    """Create a test source with unique key"""
    unique_id = str(uuid4())[:8]
    source = Source(
        id=uuid4(),
        name=f"test_source_{unique_id}",
        domain="test.com",
        type="api",
        base_url="https://test.com",
        source_key=f"test_key_{unique_id}",
        slug=f"test_{unique_id}"
    )
    db_session.add(source)
    db_session.commit()
    return source


@pytest.fixture
def test_articles(db_session, test_source):
    """Create test articles"""
    articles = []
    for i in range(3):
        article = Article(
            id=uuid4(),
            source_id=test_source.id,
            source_item_id=f"test_{i}",
            url=f"https://test.com/{i}",
            normalized_url=f"https://test.com/{i}",
            title=f"Test Article {i}",
            original_content=f"Content {i}",
            content_type="article",
            overall_score=0.8 - (i * 0.1),  # 0.8, 0.7, 0.6
            crawl_time=datetime.now(timezone.utc),
            publish_time=datetime.now(timezone.utc)
        )
        db_session.add(article)
        articles.append(article)
    db_session.commit()
    return articles


@pytest.fixture
def unique_date():
    """Generate a unique date for each test to avoid data conflicts"""
    # Generate valid date in YYYY-MM-DD format
    unique_num = uuid4().int % 1000
    month = (unique_num % 12) + 1
    day = (unique_num % 28) + 1
    return f"2026-{month:02d}-{day:02d}"


@pytest.fixture
def test_recommendations(db_session, test_articles, unique_date):
    """Create test recommendations"""
    recs = []
    for i, article in enumerate(test_articles[:2]):  # Only recommend first 2
        rec = Recommendation(
            id=uuid4(),
            article_id=article.id,
            recommendation_type="daily_digest",
            score=article.overall_score,
            rank=i + 1,
            batch_date=unique_date,
            status="pending"
        )
        db_session.add(rec)
        recs.append(rec)
    db_session.commit()
    return recs, unique_date


class TestGetTodayRecommendations:
    """Tests for GET /api/recommendations/today"""

    def test_get_today_recommendations_success(
        self, client, test_recommendations
    ):
        """Test successful retrieval of today's recommendations"""
        recs, date = test_recommendations
        response = client.get(f"/api/recommendations/today?date={date}")

        assert response.status_code == 200
        data = response.json()

        assert data["date"] == date
        assert data["total"] == 2
        assert len(data["items"]) == 2

        # Check first item structure
        item = data["items"][0]
        assert "id" in item
        assert "rank" in item
        assert "score" in item
        assert "status" in item
        assert "article" in item

        # Check article structure
        article = item["article"]
        assert "id" in article
        assert "title" in article
        assert "url" in article
        assert "source" in article

        # Check source structure
        source = article["source"]
        assert "id" in source
        assert "name" in source
        assert "domain" in source

    def test_get_today_recommendations_empty(self, client):
        """Test when no recommendations available for date"""
        response = client.get("/api/recommendations/today?date=2020-01-01")

        assert response.status_code == 200
        data = response.json()

        assert data["date"] == "2020-01-01"
        assert data["total"] == 0
        assert data["items"] == []

    def test_get_today_recommendations_default_date(
        self, client, db_session, test_articles, monkeypatch
    ):
        """Test that default date is today"""
        # Use a unique date based on uuid to avoid conflicts
        unique_suffix = str(uuid4().int % 10000)
        today = f"2026-11-{int(unique_suffix) % 28 + 1:02d}"
        for i, article in enumerate(test_articles[:2]):
            rec = Recommendation(
                id=uuid4(),
                article_id=article.id,
                recommendation_type="daily_digest",
                score=article.overall_score,
                rank=i + 1,
                batch_date=today,
                status="pending"
            )
            db_session.add(rec)
        db_session.commit()

        # Parse the date parts
        year, month, day = today.split('-')

        # Mock today's date
        class MockDateTime:
            @classmethod
            def now(cls, tz=None):
                return datetime(int(year), int(month), int(day), 12, 0, 0, tzinfo=timezone.utc)

        monkeypatch.setattr("app.api.routes.recommendations.datetime", MockDateTime)

        response = client.get("/api/recommendations/today")

        assert response.status_code == 200
        data = response.json()
        assert data["date"] == today
        assert data["total"] == 2

    def test_get_today_recommendations_ordered_by_rank(
        self, client, test_recommendations
    ):
        """Test recommendations are ordered by rank"""
        recs, date = test_recommendations
        response = client.get(f"/api/recommendations/today?date={date}")

        assert response.status_code == 200
        data = response.json()

        ranks = [item["rank"] for item in data["items"]]
        assert ranks == sorted(ranks)

    def test_get_today_recommendations_database_error(self, client):
        """Test 503 response when database error occurs"""
        # Mock the Session.execute to raise SQLAlchemyError
        with patch('sqlalchemy.orm.Session.execute') as mock_execute:
            mock_execute.side_effect = OperationalError(
                statement="SELECT ...",
                params={},
                orig=Exception("relation 'recommendations' does not exist")
            )
            response = client.get("/api/recommendations/today?date=2026-04-11")

        assert response.status_code == 503
        assert "database" in response.json()["detail"].lower() or "error" in response.json()["detail"].lower()


class TestGetRecommendationById:
    """Tests for GET /api/recommendations/{recommendation_id}"""

    def test_get_recommendation_by_id_success(
        self, client, test_recommendations
    ):
        """Test successful retrieval of single recommendation"""
        recs, _ = test_recommendations
        rec_id = str(recs[0].id)
        response = client.get(f"/api/recommendations/{rec_id}")

        assert response.status_code == 200
        data = response.json()

        assert data["id"] == rec_id
        assert "article" in data
        assert "rank" in data
        assert "score" in data

    def test_get_recommendation_not_found(self, client):
        """Test 404 for non-existent recommendation"""
        fake_id = "12345678-1234-1234-1234-123456789abc"
        response = client.get(f"/api/recommendations/{fake_id}")

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()


class TestRecommendationsIntegration:
    """Integration tests for recommendations API"""

    def test_end_to_end_recommendation_flow(
        self, client, test_source, test_articles, db_session
    ):
        """Test complete flow: generate recommendations then retrieve via API"""
        # Use a unique date based on uuid to avoid conflicts
        unique_suffix = str(uuid4().int % 10000)
        test_date = f"2026-10-{int(unique_suffix) % 28 + 1:02d}"

        # First verify no recommendations exist for the date
        response = client.get(f"/api/recommendations/today?date={test_date}")
        assert response.json()["total"] == 0

        # Create recommendations directly
        for i, article in enumerate(test_articles[:2]):
            rec = Recommendation(
                id=uuid4(),
                article_id=article.id,
                recommendation_type="daily_digest",
                score=article.overall_score,
                rank=i + 1,
                batch_date=test_date,
                status="pending"
            )
            db_session.add(rec)
        db_session.commit()

        # Now retrieve via API
        response = client.get(f"/api/recommendations/today?date={test_date}")

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2

        # Verify article scores match
        scores = [item["score"] for item in data["items"]]
        assert 0.7 in scores  # From test_articles fixture
        assert 0.8 in scores
