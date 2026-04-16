"""
Tests for main FastAPI application
"""

from typing import AsyncGenerator

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.core.config import get_settings


@pytest.fixture
def client() -> TestClient:
    """Create test client for FastAPI app"""
    return TestClient(app)


def test_root_endpoint(client: TestClient, setup_database) -> None:
    """Test root endpoint returns HTML page with today's recommendations"""
    response = client.get("/")

    assert response.status_code == 200
    # Response should be HTML, not JSON
    assert "text/html" in response.headers.get("content-type", "")
    # Should contain expected HTML elements
    content = response.text
    assert "今日推荐" in content
    assert "<!DOCTYPE html>" in content or "<html" in content


def test_health_check(client: TestClient) -> None:
    """Test health check endpoint"""
    response = client.get("/health")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "app" in data
    assert "version" in data


def test_health_check_returns_app_name(client: TestClient) -> None:
    """Test health check returns correct app name"""
    response = client.get("/health")
    data = response.json()

    settings = get_settings()
    assert data["app"] == settings.APP_NAME


def test_health_check_returns_version(client: TestClient) -> None:
    """Test health check returns correct version"""
    response = client.get("/health")
    data = response.json()

    settings = get_settings()
    assert data["version"] == settings.APP_VERSION
