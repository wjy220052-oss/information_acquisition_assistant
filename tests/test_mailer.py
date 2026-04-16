"""
Tests for email sending with mocked SMTP

Covers:
- SMTP connection verification (success/failure cases)
- Email sending with various content types
- Authentication error handling
- Connection error handling
- SSL/TLS context creation
"""

import pytest
from datetime import datetime, timezone
from unittest.mock import Mock, patch, MagicMock
import smtplib
import ssl

from app.core.mailer import EmailConfig, Mailer, verify_email_config, get_email_config_status


class TestMailerVerifyConnection:
    """Tests for Mailer.verify_connection method"""

    def test_returns_config_status_when_not_configured(self):
        """Should return detailed status when email is not configured"""
        config = EmailConfig()
        config.smtp_host = None
        config.smtp_user = None
        config.smtp_password = None
        config.from_email = None
        config.to_email = None

        mailer = Mailer(config)
        result = mailer.verify_connection()

        assert result['success'] is False
        assert 'state' in result
        assert result['state'] == 'not_configured'
        assert 'missing_fields' in result
        assert 'help_url' in result
        assert len(result['missing_fields']) == 5

    def test_returns_partial_status_when_partially_configured(self):
        """Should return partial config status with missing fields listed"""
        config = EmailConfig()
        config.smtp_host = "smtp.gmail.com"
        config.smtp_user = "user@gmail.com"
        config.smtp_password = None
        config.from_email = "user@gmail.com"
        config.to_email = "user@gmail.com"

        mailer = Mailer(config)
        result = mailer.verify_connection()

        assert result['success'] is False
        assert result['state'] == 'partially_configured'
        assert 'SMTP_PASSWORD' in result['missing_fields']

    @patch("app.core.mailer.smtplib.SMTP")
    @patch("app.core.mailer.ssl.create_default_context")
    def test_successful_connection(self, mock_ssl_context, mock_smtp_class):
        """Should return success when SMTP connection works"""
        # Setup mocks
        mock_server = MagicMock()
        mock_smtp_class.return_value.__enter__ = Mock(return_value=mock_server)
        mock_smtp_class.return_value.__exit__ = Mock(return_value=False)

        config = Mock()
        config.is_configured = True
        config.smtp_host = "smtp.gmail.com"
        config.smtp_port = 587
        config.smtp_use_ssl = False  # Explicitly set for STARTTLS mode
        config.smtp_user = "user@gmail.com"
        config.smtp_password = "password"
        # Mock get_config_status to return a proper dict (not used when is_configured=True, but for safety)
        config.get_config_status.return_value = {
            'is_configured': True,
            'state': 'configured',
            'missing_fields': [],
        }

        mailer = Mailer(config)
        result = mailer.verify_connection()

        assert result['success'] is True
        assert "Successfully connected" in result['message']
        assert "smtp.gmail.com:587" in result['message']

        # Verify SMTP was called correctly
        mock_smtp_class.assert_called_once_with("smtp.gmail.com", 587)
        mock_server.starttls.assert_called_once()
        mock_server.login.assert_called_once_with("user@gmail.com", "password")

    @patch("app.core.mailer.smtplib.SMTP")
    @patch("app.core.mailer.ssl.create_default_context")
    def test_authentication_failure(self, mock_ssl_context, mock_smtp_class):
        """Should handle SMTP authentication errors gracefully"""
        # Setup mocks to raise auth error
        mock_server = MagicMock()
        mock_server.login.side_effect = smtplib.SMTPAuthenticationError(535, b"Authentication failed")
        mock_smtp_class.return_value.__enter__ = Mock(return_value=mock_server)
        mock_smtp_class.return_value.__exit__ = Mock(return_value=False)

        config = Mock()
        config.is_configured = True
        config.smtp_host = "smtp.gmail.com"
        config.smtp_port = 587
        config.smtp_use_ssl = False  # Explicitly set for STARTTLS mode
        config.smtp_user = "user@gmail.com"
        config.smtp_password = "wrong_password"
        config.get_config_status.return_value = {
            'is_configured': True,
            'state': 'configured',
            'missing_fields': [],
        }

        mailer = Mailer(config)
        result = mailer.verify_connection()

        assert result['success'] is False
        assert "Authentication failed" in result['message']

    @patch("app.core.mailer.smtplib.SMTP")
    @patch("app.core.mailer.ssl.create_default_context")
    def test_connection_failure(self, mock_ssl_context, mock_smtp_class):
        """Should handle connection failures gracefully"""
        # Setup mock to raise connection error
        mock_smtp_class.side_effect = Exception("Connection refused")

        config = Mock()
        config.is_configured = True
        config.smtp_host = "invalid.host.com"
        config.smtp_port = 587
        config.smtp_use_ssl = False  # Explicitly set for STARTTLS mode
        config.smtp_user = "user@gmail.com"
        config.smtp_password = "password"
        config.get_config_status.return_value = {
            'is_configured': True,
            'state': 'configured',
            'missing_fields': [],
        }

        mailer = Mailer(config)
        result = mailer.verify_connection()

        assert result['success'] is False
        assert "Connection failed" in result['message']

    @patch("app.core.mailer.smtplib.SMTP")
    @patch("app.core.mailer.ssl.create_default_context")
    def test_uses_ssl_context(self, mock_ssl_context, mock_smtp_class):
        """Should use SSL context for TLS connection"""
        mock_context = Mock()
        mock_ssl_context.return_value = mock_context

        mock_server = MagicMock()
        mock_smtp_class.return_value.__enter__ = Mock(return_value=mock_server)
        mock_smtp_class.return_value.__exit__ = Mock(return_value=False)

        config = Mock()
        config.is_configured = True
        config.smtp_host = "smtp.gmail.com"
        config.smtp_port = 587
        config.smtp_use_ssl = False  # Explicitly set for STARTTLS mode
        config.smtp_user = "user@gmail.com"
        config.smtp_password = "password"
        config.get_config_status.return_value = {
            'is_configured': True,
            'state': 'configured',
            'missing_fields': [],
        }

        mailer = Mailer(config)
        mailer.verify_connection()

        mock_ssl_context.assert_called_once()
        mock_server.starttls.assert_called_once_with(context=mock_context)


class TestMailerSendEmail:
    """Tests for Mailer.send_email method"""

    def test_fails_when_not_configured(self):
        """Should fail immediately if email is not configured"""
        config = Mock()
        config.is_configured = False

        mailer = Mailer(config)
        result = mailer.send_email(subject="Test", html_body="<p>Test</p>")

        assert result['success'] is False
        assert "not configured" in result['message'].lower()

    def test_requires_content(self):
        """Should fail if neither html_body nor text_body is provided"""
        config = Mock()
        config.is_configured = True

        mailer = Mailer(config)
        result = mailer.send_email(subject="Test")

        assert result['success'] is False
        assert "Must provide" in result['message']

    @patch("app.core.mailer.smtplib.SMTP")
    @patch("app.core.mailer.ssl.create_default_context")
    def test_sends_html_email(self, mock_ssl_context, mock_smtp_class):
        """Should successfully send HTML email"""
        mock_server = MagicMock()
        mock_smtp_class.return_value.__enter__ = Mock(return_value=mock_server)
        mock_smtp_class.return_value.__exit__ = Mock(return_value=False)

        config = Mock()
        config.is_configured = True
        config.smtp_host = "smtp.gmail.com"
        config.smtp_port = 587
        config.smtp_use_ssl = False  # Explicitly set for STARTTLS mode
        config.smtp_user = "user@gmail.com"
        config.smtp_password = "password"
        config.from_email = "from@gmail.com"
        config.to_email = "to@gmail.com"

        mailer = Mailer(config)
        result = mailer.send_email(
            subject="Test Subject",
            html_body="<h1>Hello</h1><p>World</p>"
        )

        assert result['success'] is True
        assert "sent" in result['message'].lower()
        assert "sent_at" in result
        assert result['sent_at'] is not None

        # Verify email was sent
        mock_server.sendmail.assert_called_once()
        call_args = mock_server.sendmail.call_args
        assert call_args[0][0] == "from@gmail.com"
        assert call_args[0][1] == "to@gmail.com"

    @patch("app.core.mailer.smtplib.SMTP")
    @patch("app.core.mailer.ssl.create_default_context")
    def test_sends_text_email(self, mock_ssl_context, mock_smtp_class):
        """Should successfully send plain text email"""
        mock_server = MagicMock()
        mock_smtp_class.return_value.__enter__ = Mock(return_value=mock_server)
        mock_smtp_class.return_value.__exit__ = Mock(return_value=False)

        config = Mock()
        config.is_configured = True
        config.smtp_host = "smtp.gmail.com"
        config.smtp_port = 587
        config.smtp_use_ssl = False  # Explicitly set for STARTTLS mode
        config.smtp_user = "user@gmail.com"
        config.smtp_password = "password"
        config.from_email = "from@gmail.com"
        config.to_email = "to@gmail.com"

        mailer = Mailer(config)
        result = mailer.send_email(
            subject="Test Subject",
            text_body="Plain text content"
        )

        assert result['success'] is True

    @patch("app.core.mailer.smtplib.SMTP")
    @patch("app.core.mailer.ssl.create_default_context")
    def test_sends_multipart_email(self, mock_ssl_context, mock_smtp_class):
        """Should send both HTML and text parts"""
        mock_server = MagicMock()
        mock_smtp_class.return_value.__enter__ = Mock(return_value=mock_server)
        mock_smtp_class.return_value.__exit__ = Mock(return_value=False)

        config = Mock()
        config.is_configured = True
        config.smtp_host = "smtp.gmail.com"
        config.smtp_port = 587
        config.smtp_use_ssl = False  # Explicitly set for STARTTLS mode
        config.smtp_user = "user@gmail.com"
        config.smtp_password = "password"
        config.from_email = "from@gmail.com"
        config.to_email = "to@gmail.com"

        mailer = Mailer(config)
        result = mailer.send_email(
            subject="Test Subject",
            html_body="<h1>HTML Content</h1>",
            text_body="Plain text content"
        )

        assert result['success'] is True
        # Verify sendmail was called with message containing both parts
        assert mock_server.sendmail.called

    @patch("app.core.mailer.smtplib.SMTP")
    @patch("app.core.mailer.ssl.create_default_context")
    def test_allows_email_override(self, mock_ssl_context, mock_smtp_class):
        """Should allow overriding to_email and from_email"""
        mock_server = MagicMock()
        mock_smtp_class.return_value.__enter__ = Mock(return_value=mock_server)
        mock_smtp_class.return_value.__exit__ = Mock(return_value=False)

        config = Mock()
        config.is_configured = True
        config.smtp_host = "smtp.gmail.com"
        config.smtp_port = 587
        config.smtp_use_ssl = False  # Explicitly set for STARTTLS mode
        config.smtp_user = "user@gmail.com"
        config.smtp_password = "password"
        config.from_email = "default_from@gmail.com"
        config.to_email = "default_to@gmail.com"

        mailer = Mailer(config)
        result = mailer.send_email(
            subject="Test",
            text_body="Content",
            to_email="override_to@gmail.com",
            from_email="override_from@gmail.com"
        )

        assert result['success'] is True
        call_args = mock_server.sendmail.call_args
        assert call_args[0][0] == "override_from@gmail.com"
        assert call_args[0][1] == "override_to@gmail.com"

    @patch("app.core.mailer.smtplib.SMTP")
    @patch("app.core.mailer.ssl.create_default_context")
    def test_handles_send_failure(self, mock_ssl_context, mock_smtp_class):
        """Should handle send failures gracefully"""
        mock_server = MagicMock()
        mock_server.sendmail.side_effect = Exception("Network error")
        mock_smtp_class.return_value.__enter__ = Mock(return_value=mock_server)
        mock_smtp_class.return_value.__exit__ = Mock(return_value=False)

        config = Mock()
        config.is_configured = True
        config.smtp_host = "smtp.gmail.com"
        config.smtp_port = 587
        config.smtp_use_ssl = False  # Explicitly set for STARTTLS mode
        config.smtp_user = "user@gmail.com"
        config.smtp_password = "password"
        config.from_email = "from@gmail.com"
        config.to_email = "to@gmail.com"

        mailer = Mailer(config)
        result = mailer.send_email(
            subject="Test",
            text_body="Content"
        )

        assert result['success'] is False
        assert "Failed to send" in result['message']


class TestVerifyEmailConfig:
    """Tests for verify_email_config convenience function"""

    @patch("app.core.mailer.get_mailer")
    def test_calls_mailer_verify_connection(self, mock_get_mailer):
        """Should use Mailer.verify_connection internally"""
        mock_mailer = Mock()
        mock_mailer.verify_connection.return_value = {
            "success": True,
            "message": "Connected"
        }
        mock_get_mailer.return_value = mock_mailer

        result = verify_email_config()

        mock_mailer.verify_connection.assert_called_once()
        assert result["success"] is True


class TestGetEmailConfigStatus:
    """Tests for get_email_config_status convenience function"""

    def test_returns_status_dict(self):
        """Should return configuration status as dict"""
        result = get_email_config_status()

        assert isinstance(result, dict)
        assert "is_configured" in result
        assert "state" in result
        assert "missing_fields" in result


class TestDefaultMailerInstance:
    """Tests for default Mailer creation"""

    def test_creates_default_config_when_none_provided(self):
        """Should create default EmailConfig when no config provided"""
        mailer = Mailer()

        assert mailer.config is not None

    def test_uses_provided_config(self):
        """Should use provided config when given"""
        config = Mock()
        mailer = Mailer(config)

        assert mailer.config is config


class TestMailerSSLMode:
    """Tests for SSL mode email sending (port 465)"""

    @patch("app.core.mailer.smtplib.SMTP_SSL")
    @patch("app.core.mailer.ssl.create_default_context")
    def test_uses_smtp_ssl_when_ssl_mode_enabled(self, mock_ssl_context, mock_smtp_ssl_class):
        """Should use SMTP_SSL when smtp_use_ssl is True"""
        mock_context = Mock()
        mock_ssl_context.return_value = mock_context

        mock_server = MagicMock()
        mock_smtp_ssl_class.return_value.__enter__ = Mock(return_value=mock_server)
        mock_smtp_ssl_class.return_value.__exit__ = Mock(return_value=False)

        config = Mock()
        config.is_configured = True
        config.smtp_host = "smtp.exmail.qq.com"
        config.smtp_port = 465
        config.smtp_use_ssl = True
        config.smtp_user = "user@company.com"
        config.smtp_password = "password"
        config.from_email = "from@company.com"
        config.to_email = "to@company.com"

        mailer = Mailer(config)
        result = mailer.send_email(
            subject="Test Subject",
            text_body="Test content"
        )

        assert result['success'] is True
        mock_smtp_ssl_class.assert_called_once_with("smtp.exmail.qq.com", 465, context=mock_context)
        mock_server.login.assert_called_once_with("user@company.com", "password")

    @patch("app.core.mailer.smtplib.SMTP")
    @patch("app.core.mailer.ssl.create_default_context")
    def test_uses_starttls_when_ssl_mode_disabled(self, mock_ssl_context, mock_smtp_class):
        """Should use SMTP+STARTTLS when smtp_use_ssl is False"""
        mock_context = Mock()
        mock_ssl_context.return_value = mock_context

        mock_server = MagicMock()
        mock_smtp_class.return_value.__enter__ = Mock(return_value=mock_server)
        mock_smtp_class.return_value.__exit__ = Mock(return_value=False)

        config = Mock()
        config.is_configured = True
        config.smtp_host = "smtp.qq.com"
        config.smtp_port = 587
        config.smtp_use_ssl = False
        config.smtp_user = "user@qq.com"
        config.smtp_password = "password"
        config.from_email = "from@qq.com"
        config.to_email = "to@qq.com"

        mailer = Mailer(config)
        result = mailer.send_email(
            subject="Test Subject",
            text_body="Test content"
        )

        assert result['success'] is True
        mock_smtp_class.assert_called_once_with("smtp.qq.com", 587)
        mock_server.starttls.assert_called_once_with(context=mock_context)
        mock_server.login.assert_called_once_with("user@qq.com", "password")
