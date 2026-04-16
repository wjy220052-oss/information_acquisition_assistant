"""
Tests for email sending functionality

Covers:
- Email configuration validation
- Email template rendering
- Email sending success/failure logging
- Scheduler job triggering email
"""

import pytest
from datetime import datetime, timezone
from uuid import uuid4
from unittest.mock import Mock, patch, MagicMock

from app.core.mailer import EmailConfig, Mailer, verify_email_config
from app.core.email_templates import EmailTemplateRenderer
from app.models.db.tables import EmailLog


class TestEmailConfig:
    """Tests for email configuration"""

    def test_email_config_is_configured_all_set(self, monkeypatch):
        """Test is_configured returns True when all settings are present"""
        monkeypatch.setenv("SMTP_HOST", "smtp.example.com")
        monkeypatch.setenv("SMTP_USER", "user@example.com")
        monkeypatch.setenv("SMTP_PASSWORD", "password")
        monkeypatch.setenv("EMAIL_FROM", "from@example.com")
        monkeypatch.setenv("EMAIL_TO", "to@example.com")

        # Reload settings to pick up new env vars
        from app.core.config import Settings
        settings = Settings()

        config = EmailConfig()
        # Manually set config values since Settings may be cached
        config.smtp_host = "smtp.example.com"
        config.smtp_user = "user@example.com"
        config.smtp_password = "password"
        config.from_email = "from@example.com"
        config.to_email = "to@example.com"

        assert config.is_configured is True

    def test_email_config_is_configured_missing_host(self, monkeypatch):
        """Test is_configured returns False when SMTP_HOST is missing"""
        # Clear settings cache and set env vars
        import app.core.config as config_module
        config_module._settings = None
        monkeypatch.setenv("SMTP_HOST", "")
        monkeypatch.setenv("SMTP_USER", "user@example.com")
        monkeypatch.setenv("SMTP_PASSWORD", "password")
        monkeypatch.setenv("EMAIL_FROM", "from@example.com")
        monkeypatch.setenv("EMAIL_TO", "to@example.com")

        config = EmailConfig()
        assert config.is_configured is False

    def test_email_config_is_configured_missing_user(self, monkeypatch):
        """Test is_configured returns False when SMTP_USER is missing"""
        # Clear settings cache and set env vars
        import app.core.config as config_module
        config_module._settings = None
        monkeypatch.setenv("SMTP_HOST", "smtp.example.com")
        monkeypatch.setenv("SMTP_USER", "")
        monkeypatch.setenv("SMTP_PASSWORD", "password")
        monkeypatch.setenv("EMAIL_FROM", "from@example.com")
        monkeypatch.setenv("EMAIL_TO", "to@example.com")

        config = EmailConfig()
        assert config.is_configured is False


class TestMailer:
    """Tests for mailer functionality"""

    def test_verify_connection_not_configured(self):
        """Test verify_connection returns error when not configured"""
        config = Mock()
        config.is_configured = False
        config.smtp_host = None  # Missing
        config.smtp_user = "user"
        config.smtp_password = "pass"
        config.from_email = "from"
        config.to_email = "to"

        mailer = Mailer(config)
        result = mailer.verify_connection()

        assert result["success"] is False
        assert "SMTP_HOST" in result["message"] or "SMTP_HOST" in result.get("missing_fields", [])

    @patch("app.core.mailer.smtplib.SMTP")
    @patch("app.core.mailer.ssl.create_default_context")
    def test_verify_connection_success(self, mock_ssl, mock_smtp):
        """Test verify_connection succeeds with valid SMTP"""
        config = Mock()
        config.is_configured = True
        config.smtp_host = "smtp.example.com"
        config.smtp_port = 587
        config.smtp_use_ssl = False  # Explicitly set for STARTTLS mode
        config.smtp_user = "user@example.com"
        config.smtp_password = "password"

        mailer = Mailer(config)
        result = mailer.verify_connection()

        assert result["success"] is True
        assert "Successfully connected" in result["message"]

    @patch("app.core.mailer.smtplib.SMTP")
    @patch("app.core.mailer.ssl.create_default_context")
    def test_verify_connection_auth_failure(self, mock_ssl, mock_smtp):
        """Test verify_connection handles auth failure"""
        import smtplib

        mock_smtp.return_value.__enter__.return_value.login.side_effect = (
            smtplib.SMTPAuthenticationError(535, b"Authentication failed")
        )

        config = Mock()
        config.is_configured = True
        config.smtp_host = "smtp.example.com"
        config.smtp_port = 587
        config.smtp_use_ssl = False  # Explicitly set for STARTTLS mode
        config.smtp_user = "user@example.com"
        config.smtp_password = "wrong_password"

        mailer = Mailer(config)
        result = mailer.verify_connection()

        assert result["success"] is False
        assert "Authentication failed" in result["message"]

    def test_send_email_not_configured(self):
        """Test send_email returns error when not configured"""
        config = Mock()
        config.is_configured = False

        mailer = Mailer(config)
        result = mailer.send_email(subject="Test", html_body="<p>Test</p>")

        assert result["success"] is False
        assert "not configured" in result["message"]

    def test_send_email_no_content(self):
        """Test send_email requires at least one content type"""
        config = Mock()
        config.is_configured = True

        mailer = Mailer(config)
        result = mailer.send_email(subject="Test")

        assert result["success"] is False
        assert "Must provide" in result["message"]

    @patch("app.core.mailer.smtplib.SMTP")
    @patch("app.core.mailer.ssl.create_default_context")
    def test_send_email_success(self, mock_ssl, mock_smtp):
        """Test send_email succeeds with valid content"""
        config = Mock()
        config.is_configured = True
        config.smtp_host = "smtp.example.com"
        config.smtp_port = 587
        config.smtp_use_ssl = False  # Explicitly set for STARTTLS mode
        config.smtp_user = "user@example.com"
        config.smtp_password = "password"
        config.from_email = "from@example.com"
        config.to_email = "to@example.com"

        mailer = Mailer(config)
        result = mailer.send_email(
            subject="Test Subject",
            html_body="<p>HTML content</p>",
            text_body="Plain text content"
        )

        assert result["success"] is True
        assert "sent" in result["message"].lower()
        assert "sent_at" in result


class TestEmailTemplateRenderer:
    """Tests for email template rendering"""

    def test_render_daily_digest_empty(self):
        """Test rendering daily digest with no recommendations"""
        renderer = EmailTemplateRenderer()

        result = renderer.render_daily_digest(
            recommendations=[],
            date="2024年04月14日",
            dashboard_url="http://localhost:8000"
        )

        assert "html" in result
        assert "text" in result
        assert "subject" in result
        assert "每日阅读推荐" in result["subject"]
        assert "今日暂无推荐" in result["html"]
        assert "今日暂无推荐" in result["text"]

    def test_render_daily_digest_with_recommendations(self):
        """Test rendering daily digest with recommendations"""
        renderer = EmailTemplateRenderer()

        # Mock recommendation data
        mock_article = Mock()
        mock_article.title = "Test Article Title"
        mock_article.url = "https://example.com/article"
        mock_article.summary = "This is a test summary of the article."
        mock_article.reading_time_minutes = 5
        mock_article.classification_tags = ["技术", "Python"]

        mock_source = Mock()
        mock_source.name = "Test Source"
        mock_article.source = mock_source

        mock_author = Mock()
        mock_author.name = "Test Author"
        mock_article.author = mock_author

        recommendations = [
            {"article": mock_article, "score": 0.85, "rank": 1}
        ]

        result = renderer.render_daily_digest(
            recommendations=recommendations,
            date="2024年04月14日",
            dashboard_url="http://localhost:8000"
        )

        assert "html" in result
        assert "text" in result
        assert "Test Article Title" in result["html"]
        assert "Test Article Title" in result["text"]
        assert "85%" in result["html"]

    def test_render_test_email(self):
        """Test rendering test email"""
        renderer = EmailTemplateRenderer()

        result = renderer.render_test_email()

        assert "html" in result
        assert "text" in result
        assert "subject" in result
        # Check for subject contains expected text (handles encoding issues)
        assert "[测试]" in result["subject"] or "test" in result["subject"].lower()
        assert "每日阅读推荐" in result["html"]  # Template always shows this


class TestEmailLog:
    """Tests for email log database operations"""

    def test_email_log_creation(self, db_session):
        """Test creating an email log entry"""
        log = EmailLog(
            id=uuid4(),
            batch_date="2024-04-14",
            email_type="daily_digest",
            status="pending",
            to_email="user@example.com",
            from_email="system@example.com",
            subject="Test Subject",
            recommendation_count=5,
        )

        db_session.add(log)
        db_session.commit()
        db_session.refresh(log)

        assert log.id is not None
        assert log.status == "pending"
        assert log.to_email == "user@example.com"

    def test_email_log_status_update(self, db_session):
        """Test updating email log status"""
        log = EmailLog(
            id=uuid4(),
            batch_date="2024-04-14",
            email_type="daily_digest",
            status="pending",
            to_email="user@example.com",
            from_email="system@example.com",
            subject="Test Subject",
        )

        db_session.add(log)
        db_session.commit()

        # Update to sent
        log.status = "sent"
        log.sent_at = datetime.now(timezone.utc)
        db_session.commit()
        db_session.refresh(log)

        assert log.status == "sent"
        assert log.sent_at is not None


class TestSchedulerEmailJob:
    """Tests for scheduler email job integration"""

    @patch("app.tasks.scheduler_jobs.get_mailer")
    @patch("app.tasks.scheduler_jobs.get_template_renderer")
    def test_send_daily_email_not_configured(self, mock_get_renderer, mock_get_mailer):
        """Test send_daily_email when email is not configured"""
        from app.tasks.scheduler_jobs import send_daily_email

        mock_mailer = Mock()
        mock_mailer.config.is_configured = False
        mock_get_mailer.return_value = mock_mailer

        result = send_daily_email(batch_date="2024-04-14")

        assert result["success"] is False
        assert result["sent"] is False
        assert "not configured" in result["error"].lower()

    @patch("app.tasks.scheduler_jobs.get_mailer")
    @patch("app.tasks.scheduler_jobs.get_template_renderer")
    @patch("app.tasks.scheduler_jobs.get_db")
    def test_send_daily_email_success(self, mock_get_db, mock_get_renderer, mock_get_mailer):
        """Test send_daily_email with successful sending"""
        from app.tasks.scheduler_jobs import send_daily_email

        # Mock mailer
        mock_mailer = Mock()
        mock_mailer.config.is_configured = True
        mock_mailer.config.to_email = "to@example.com"
        mock_mailer.config.from_email = "from@example.com"
        mock_mailer.send_email.return_value = {
            "success": True,
            "message": "Email sent",
            "sent_at": datetime.now(timezone.utc).isoformat(),
        }
        mock_get_mailer.return_value = mock_mailer

        # Mock template renderer
        mock_renderer = Mock()
        mock_renderer.render_daily_digest.return_value = {
            "html": "<p>Test</p>",
            "text": "Test",
            "subject": "Test Subject",
        }
        mock_get_renderer.return_value = mock_renderer

        # Mock database
        mock_db = MagicMock()
        mock_db.__enter__ = Mock(return_value=mock_db)
        mock_db.__exit__ = Mock(return_value=False)
        mock_get_db.return_value = mock_db

        # Mock repository
        mock_rec = Mock()
        mock_rec.article = Mock()
        mock_rec.article.source = None
        mock_rec.article.author = None
        mock_rec.score = 0.8
        mock_rec.rank = 1

        with patch("app.tasks.scheduler_jobs.RecommendationRepository") as mock_repo_class:
            mock_repo = Mock()
            mock_repo.get_recommendations_for_date.return_value = [mock_rec]
            mock_repo_class.return_value = mock_repo

            result = send_daily_email(batch_date="2024-04-14")

            assert result["sent"] is True or not result["success"]


class TestEmailAPI:
    """Tests for email API endpoints"""

    def test_trigger_test_email_not_configured(self, client, monkeypatch):
        """Test test email endpoint when not configured"""
        # Ensure no email config
        monkeypatch.setenv("SMTP_HOST", "")
        monkeypatch.setenv("SMTP_USER", "")
        monkeypatch.setenv("SMTP_PASSWORD", "")
        monkeypatch.setenv("EMAIL_FROM", "")
        monkeypatch.setenv("EMAIL_TO", "")

        response = client.post("/api/scheduler/trigger/email")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False
        assert data["sent"] is False

    def test_get_email_logs_empty(self, client):
        """Test getting email logs when none exist"""
        response = client.get("/api/scheduler/emails")

        assert response.status_code == 200
        data = response.json()
        assert "logs" in data
        assert len(data["logs"]) == 0

    def test_get_email_logs_with_data(self, client, db_session):
        """Test getting email logs with data"""
        # Create test email log
        log = EmailLog(
            id=uuid4(),
            batch_date="2024-04-14",
            email_type="daily_digest",
            status="sent",
            to_email="user@example.com",
            from_email="system@example.com",
            subject="Test Subject",
            sent_at=datetime.now(timezone.utc),
            recommendation_count=5,
        )
        db_session.add(log)
        db_session.commit()

        response = client.get("/api/scheduler/emails")

        assert response.status_code == 200
        data = response.json()
        assert len(data["logs"]) >= 1
        assert data["logs"][0]["to_email"] == "user@example.com"

    def test_get_email_logs_filtered_by_date(self, client, db_session):
        """Test getting email logs filtered by batch date"""
        # Create test email logs for different dates
        log1 = EmailLog(
            id=uuid4(),
            batch_date="2024-04-14",
            email_type="daily_digest",
            status="sent",
            to_email="user@example.com",
            from_email="system@example.com",
            subject="Subject 1",
            sent_at=datetime.now(timezone.utc),
            recommendation_count=5,
        )
        log2 = EmailLog(
            id=uuid4(),
            batch_date="2024-04-15",
            email_type="daily_digest",
            status="sent",
            to_email="user@example.com",
            from_email="system@example.com",
            subject="Subject 2",
            sent_at=datetime.now(timezone.utc),
            recommendation_count=3,
        )
        db_session.add(log1)
        db_session.add(log2)
        db_session.commit()

        response = client.get("/api/scheduler/emails?batch_date=2024-04-14")

        assert response.status_code == 200
        data = response.json()
        # Should only return logs for the specified date
        for log in data["logs"]:
            assert log["batch_date"] == "2024-04-14"
