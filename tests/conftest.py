"""
Shared pytest fixtures
"""

import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.core.database import create_tables, drop_tables, check_connection, get_db_session, get_db_dependency


def pytest_configure(config):
    """Configure pytest - check if database is available"""
    config.database_available = check_connection()


@pytest.fixture(scope="module")
def database_available():
    """Check if database is available"""
    return check_connection()


@pytest.fixture(scope="module")
def setup_database(database_available):
    """Setup test database - creates tables before all tests, cleans up after"""
    if not database_available:
        pytest.skip("Database not available")
    create_tables()
    yield
    # Don't drop tables to allow subsequent test files to use them
    # drop_tables()  # Uncomment if you want to clean up after all tests


@pytest.fixture
def db_session(setup_database):
    """
    Create a database session for tests with automatic rollback.

    Each test runs in its own transaction that is rolled back at the end,
    ensuring test isolation and preventing data from leaking between tests.
    """
    session = get_db_session()
    try:
        yield session
        # Always rollback to ensure test isolation
        # This prevents unique constraint violations and other conflicts
        session.rollback()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


@pytest.fixture(autouse=True)
def clean_email_logs(setup_database):
    """
    Clean email_logs table before each test to ensure test isolation.
    This prevents test pollution from previous test runs.
    """
    from app.models.db.tables import EmailLog
    session = get_db_session()
    try:
        # Delete all email logs
        session.query(EmailLog).delete()
        session.commit()
    except Exception:
        session.rollback()
    finally:
        session.close()
    yield


@pytest.fixture
def client(db_session):
    """
    Create test client with database dependency override

    This fixture ensures that API endpoints use the test database session
    instead of creating their own, allowing tests to control transaction scope.
    """
    def override_get_db():
        """Override FastAPI's database dependency with test session"""
        try:
            yield db_session
        except Exception:
            db_session.rollback()
            raise

    # Override the dependency
    app.dependency_overrides[get_db_dependency] = override_get_db

    with TestClient(app) as test_client:
        yield test_client

    # Clean up overrides after test
    app.dependency_overrides.clear()
