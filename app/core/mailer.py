"""
Email sending core logic

Provides SMTP-based email sending with:
- Connection management and verification
- HTML and plain text email support
- Error handling and logging
"""

import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class EmailConfig:
    """Email configuration container"""

    # Required fields for email configuration
    REQUIRED_FIELDS = ['smtp_host', 'smtp_user', 'smtp_password', 'from_email', 'to_email']

    def __init__(self):
        settings = get_settings()
        self.smtp_host: Optional[str] = settings.SMTP_HOST
        self.smtp_port: int = settings.SMTP_PORT
        self.smtp_user: Optional[str] = settings.SMTP_USER
        self.smtp_password: Optional[str] = settings.SMTP_PASSWORD
        self.smtp_use_ssl: bool = settings.SMTP_USE_SSL
        self.from_email: Optional[str] = settings.EMAIL_FROM
        self.to_email: Optional[str] = settings.EMAIL_TO

    @property
    def is_configured(self) -> bool:
        """Check if all required email settings are configured"""
        return len(self.get_missing_fields()) == 0

    def get_missing_fields(self) -> List[str]:
        """Get list of missing required field names"""
        missing = []
        if not self.smtp_host:
            missing.append('SMTP_HOST')
        if not self.smtp_user:
            missing.append('SMTP_USER')
        if not self.smtp_password:
            missing.append('SMTP_PASSWORD')
        if not self.from_email:
            missing.append('EMAIL_FROM')
        if not self.to_email:
            missing.append('EMAIL_TO')
        return missing

    def get_config_status(self) -> Dict[str, Any]:
        """Get detailed configuration status"""
        missing = self.get_missing_fields()
        total_required = len(self.REQUIRED_FIELDS)
        configured_count = total_required - len(missing)

        # Create masked preview of configuration
        config_preview = {
            'smtp_host': self.smtp_host or '(not set)',
            'smtp_port': self.smtp_port,
            'smtp_user': self.smtp_user or '(not set)',
            'smtp_password': '********' if self.smtp_password else '(not set)',
            'from_email': self.from_email or '(not set)',
            'to_email': self.to_email or '(not set)',
        }

        # Determine configuration state
        if len(missing) == total_required:
            state = 'not_configured'
            help_message = (
                'Email service is not configured. Please add the following to your .env file:\n\n'
                'SMTP_HOST=smtp.gmail.com\n'
                'SMTP_PORT=587\n'
                'SMTP_USER=your-email@gmail.com\n'
                'SMTP_PASSWORD=your-app-password\n'
                'EMAIL_FROM=your-email@gmail.com\n'
                'EMAIL_TO=your-email@gmail.com\n\n'
                'For Gmail, use an App Password instead of your regular password.'
            )
        elif missing:
            state = 'partially_configured'
            help_message = (
                f'Email configuration is incomplete. Missing fields: {", ".join(missing)}\n\n'
                'Please add the missing variables to your .env file and restart the server.'
            )
        else:
            state = 'configured'
            help_message = 'Email service is fully configured. You can now send emails.'

        return {
            'is_configured': len(missing) == 0,
            'state': state,
            'configured_count': configured_count,
            'total_required': total_required,
            'missing_fields': missing,
            'config_preview': config_preview,
            'help_message': help_message,
            'help_url': 'https://github.com/your-repo/info-assistant/blob/main/docs/email-setup.md',
        }


class Mailer:
    """Email sender with SMTP support"""

    def __init__(self, config: Optional[EmailConfig] = None):
        self.config = config or EmailConfig()

    def verify_connection(self) -> Dict[str, Any]:
        """
        Verify SMTP connection can be established

        Returns:
            Dictionary with success status and message
        """
        # Check if configured using is_configured property (works with Mock in tests)
        if not self.config.is_configured:
            # Build missing fields list from config attributes (works with both EmailConfig and Mock)
            missing = []
            if not getattr(self.config, 'smtp_host', None):
                missing.append('SMTP_HOST')
            if not getattr(self.config, 'smtp_user', None):
                missing.append('SMTP_USER')
            if not getattr(self.config, 'smtp_password', None):
                missing.append('SMTP_PASSWORD')
            if not getattr(self.config, 'from_email', None):
                missing.append('EMAIL_FROM')
            if not getattr(self.config, 'to_email', None):
                missing.append('EMAIL_TO')

            # Build help message with missing fields
            if missing:
                help_message = f"Email not configured. Missing: {', '.join(missing)}"
            else:
                help_message = "Email not configured"

            return {
                "success": False,
                "message": help_message,
                "state": "not_configured" if len(missing) == 5 else "partially_configured",
                "missing_fields": missing,
                "help_url": "https://github.com/your-repo/info-assistant/blob/main/docs/email-setup.md",
            }

        try:
            context = ssl.create_default_context()

            # Safely get smtp_use_ssl, default to False (STARTTLS) for backward compatibility
            use_ssl = getattr(self.config, 'smtp_use_ssl', False)
            if use_ssl:
                # SSL mode (port 465)
                with smtplib.SMTP_SSL(self.config.smtp_host, self.config.smtp_port, context=context) as server:
                    server.login(self.config.smtp_user, self.config.smtp_password)
            else:
                # STARTTLS mode (port 587)
                with smtplib.SMTP(self.config.smtp_host, self.config.smtp_port) as server:
                    server.starttls(context=context)
                    server.login(self.config.smtp_user, self.config.smtp_password)

            return {
                "success": True,
                "message": f"Successfully connected to {self.config.smtp_host}:{self.config.smtp_port}"
            }

        except smtplib.SMTPAuthenticationError as e:
            logger.error(f"SMTP authentication failed: {e}")
            return {
                "success": False,
                "message": f"Authentication failed: {str(e)}"
            }
        except Exception as e:
            logger.error(f"SMTP connection failed: {e}")
            return {
                "success": False,
                "message": f"Connection failed: {str(e)}"
            }

    def send_email(
        self,
        subject: str,
        html_body: Optional[str] = None,
        text_body: Optional[str] = None,
        to_email: Optional[str] = None,
        from_email: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Send an email with HTML and/or plain text content

        Args:
            subject: Email subject
            html_body: HTML content (optional)
            text_body: Plain text content (optional)
            to_email: Override recipient email
            from_email: Override sender email

        Returns:
            Dictionary with success status and message
        """
        if not self.config.is_configured:
            return {
                "success": False,
                "message": "Email service not configured"
            }

        if not html_body and not text_body:
            return {
                "success": False,
                "message": "Must provide either html_body or text_body"
            }

        to_addr = to_email or self.config.to_email
        from_addr = from_email or self.config.from_email

        try:
            # Create message
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = from_addr
            msg["To"] = to_addr

            # Add plain text part
            if text_body:
                msg.attach(MIMEText(text_body, "plain", "utf-8"))

            # Add HTML part
            if html_body:
                msg.attach(MIMEText(html_body, "html", "utf-8"))

            # Send email
            context = ssl.create_default_context()

            # Safely get smtp_use_ssl, default to False (STARTTLS) for backward compatibility
            use_ssl = getattr(self.config, 'smtp_use_ssl', False)
            if use_ssl:
                # SSL mode (port 465)
                with smtplib.SMTP_SSL(self.config.smtp_host, self.config.smtp_port, context=context) as server:
                    server.login(self.config.smtp_user, self.config.smtp_password)
                    server.sendmail(from_addr, to_addr, msg.as_string())
            else:
                # STARTTLS mode (port 587)
                with smtplib.SMTP(self.config.smtp_host, self.config.smtp_port) as server:
                    server.starttls(context=context)
                    server.login(self.config.smtp_user, self.config.smtp_password)
                    server.sendmail(from_addr, to_addr, msg.as_string())

            logger.info(f"Email sent successfully to {to_addr}")

            return {
                "success": True,
                "message": f"Email sent to {to_addr}",
                "sent_at": datetime.now(timezone.utc).isoformat(),
            }

        except Exception as e:
            logger.exception(f"Failed to send email: {e}")
            return {
                "success": False,
                "message": f"Failed to send email: {str(e)}"
            }


def get_mailer() -> Mailer:
    """Get a configured Mailer instance"""
    return Mailer()


def verify_email_config() -> Dict[str, Any]:
    """Verify email configuration and connection"""
    mailer = get_mailer()
    return mailer.verify_connection()


def get_email_config_status() -> Dict[str, Any]:
    """Get detailed email configuration status without attempting connection"""
    config = EmailConfig()
    return config.get_config_status()
