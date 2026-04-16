"""
Tests for scheduler email API endpoints

Covers:
- GET /api/scheduler/email/config-check
- POST /api/scheduler/trigger/email
- GET /api/scheduler/emails
- Response format validation
- Configuration state reporting
"""

import pytest
from datetime import datetime, timezone
from uuid import uuid4
from unittest.mock import Mock, patch
from fastapi import status

from app.models.db.tables import EmailLog


class TestEmailConfigCheckEndpoint:
    """Tests for GET /api/scheduler/email/config-check"""

    def test_config_check_returns_all_required_fields(self, client):
        """Response should include all expected fields"""
        response = client.get("/api/scheduler/email/config-check")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        # Verify all expected fields are present
        required_fields = [
            'is_configured', 'state', 'configured_count', 'total_required',
            'missing_fields', 'config_preview', 'help_message', 'help_url'
        ]
        for field in required_fields:
            assert field in data, f"Missing field: {field}"

    def test_config_check_state_is_valid(self, client):
        """State should be one of valid values"""
        response = client.get("/api/scheduler/email/config-check")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        valid_states = ['not_configured', 'partially_configured', 'configured']
        assert data['state'] in valid_states

    def test_config_check_missing_fields_is_list(self, client):
        """missing_fields should be a list"""
        response = client.get("/api/scheduler/email/config-check")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert isinstance(data['missing_fields'], list)

    def test_config_check_config_preview_is_dict(self, client):
        """config_preview should be a dict with masked values"""
        response = client.get("/api/scheduler/email/config-check")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert isinstance(data['config_preview'], dict)
        # Verify password is masked if present
        if 'smtp_password' in data['config_preview']:
            preview = data['config_preview']['smtp_password']
            assert preview == '********' or preview == '(not set)'

    def test_config_check_has_help_url(self, client):
        """Response should include help URL"""
        response = client.get("/api/scheduler/email/config-check")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert 'help_url' in data
        assert data['help_url'].startswith('http')

    def test_config_check_has_help_message(self, client):
        """Response should include help message"""
        response = client.get("/api/scheduler/email/config-check")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert 'help_message' in data
        assert len(data['help_message']) > 0

    def test_config_check_counts_are_integers(self, client):
        """configured_count and total_required should be integers"""
        response = client.get("/api/scheduler/email/config-check")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert isinstance(data['configured_count'], int)
        assert isinstance(data['total_required'], int)
        assert data['configured_count'] >= 0
        assert data['total_required'] == 5

    def test_config_check_is_configured_is_boolean(self, client):
        """is_configured should be a boolean"""
        response = client.get("/api/scheduler/email/config-check")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert isinstance(data['is_configured'], bool)

    @patch('app.api.routes.scheduler.get_email_config_status')
    def test_config_check_uses_helper_function(self, mock_get_status, client):
        """Endpoint should use get_email_config_status helper"""
        mock_get_status.return_value = {
            'is_configured': True,
            'state': 'configured',
            'configured_count': 5,
            'total_required': 5,
            'missing_fields': [],
            'config_preview': {
                'smtp_host': 'smtp.gmail.com',
                'smtp_port': 587,
                'smtp_user': 'user@gmail.com',
                'smtp_password': '********',
                'from_email': 'user@gmail.com',
                'to_email': 'user@gmail.com',
            },
            'help_message': 'Email is configured',
            'help_url': 'https://example.com/help'
        }

        response = client.get("/api/scheduler/email/config-check")

        assert response.status_code == status.HTTP_200_OK
        mock_get_status.assert_called_once()


class TestTriggerEmailEndpoint:
    """Tests for POST /api/scheduler/trigger/email"""

    @patch('app.api.routes.scheduler.send_test_email')
    @patch('app.api.routes.scheduler.verify_email_config')
    def test_trigger_email_not_configured(self, mock_verify, mock_send, client):
        """Should return helpful error when email not configured"""
        # Mock verify_email_config to return not configured state
        mock_verify.return_value = {
            "success": False,
            "message": "Email not configured. Missing: SMTP_HOST, SMTP_USER, SMTP_PASSWORD, EMAIL_FROM, EMAIL_TO",
            "state": "not_configured",
            "missing_fields": ["SMTP_HOST", "SMTP_USER", "SMTP_PASSWORD", "EMAIL_FROM", "EMAIL_TO"],
        }

        response = client.post("/api/scheduler/trigger/email")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert data['success'] is False
        assert data['sent'] is False
        assert 'message' in data
        # Should have helpful message about configuration
        assert 'not configured' in data['message'].lower() or 'Missing' in data['message']
        # Send function should not be called when not configured
        mock_send.assert_not_called()

    @patch('app.api.routes.scheduler.send_test_email')
    @patch('app.api.routes.scheduler.verify_email_config')
    def test_trigger_email_success(self, mock_verify, mock_send, client):
        """Should return success when email is sent"""
        mock_verify.return_value = {
            "success": True,
            "message": "Connected successfully"
        }
        mock_send.return_value = {
            "success": True,
            "message": "Test email sent",
            "sent": True
        }

        response = client.post("/api/scheduler/trigger/email")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert data['success'] is True
        assert data['sent'] is True

    @patch('app.api.routes.scheduler.verify_email_config')
    def test_trigger_email_config_check_fails(self, mock_verify, client):
        """Should not attempt send if config check fails"""
        mock_verify.return_value = {
            "success": False,
            "message": "Email not configured. Missing: SMTP_HOST",
            "state": "not_configured",
            "missing_fields": ["SMTP_HOST"]
        }

        response = client.post("/api/scheduler/trigger/email")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert data['success'] is False
        assert data['sent'] is False

    def test_trigger_email_returns_correct_response_format(self, client):
        """Response should have expected format"""
        response = client.post("/api/scheduler/trigger/email")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        # Verify response has required fields
        assert 'success' in data
        assert 'message' in data
        assert 'sent' in data

        # Verify types
        assert isinstance(data['success'], bool)
        assert isinstance(data['sent'], bool)
        assert isinstance(data['message'], str)


class TestGetEmailLogsEndpoint:
    """Tests for GET /api/scheduler/emails"""

    def test_get_email_logs_empty(self, client):
        """Should return empty list when no logs exist"""
        response = client.get("/api/scheduler/emails")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert 'logs' in data
        assert isinstance(data['logs'], list)
        assert len(data['logs']) == 0

    def test_get_email_logs_returns_list(self, client):
        """Response should always have logs as a list"""
        response = client.get("/api/scheduler/emails")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert 'logs' in data
        assert isinstance(data['logs'], list)

    def test_get_email_logs_with_data(self, client, db_session):
        """Should return logs when data exists"""
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

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert len(data['logs']) >= 1
        # Verify first log has expected fields
        first_log = data['logs'][0]
        assert 'id' in first_log
        assert 'batch_date' in first_log
        assert 'email_type' in first_log
        assert 'status' in first_log
        assert 'to_email' in first_log
        assert 'subject' in first_log

    def test_get_email_logs_filtered_by_batch_date(self, client, db_session):
        """Should filter logs by batch_date parameter"""
        # Create logs for different dates
        log1 = EmailLog(
            id=uuid4(),
            batch_date="2024-04-14",
            email_type="daily_digest",
            status="sent",
            to_email="user@example.com",
            from_email="system@example.com",
            subject="April 14",
            sent_at=datetime.now(timezone.utc),
        )
        log2 = EmailLog(
            id=uuid4(),
            batch_date="2024-04-15",
            email_type="daily_digest",
            status="sent",
            to_email="user@example.com",
            from_email="system@example.com",
            subject="April 15",
            sent_at=datetime.now(timezone.utc),
        )
        db_session.add(log1)
        db_session.add(log2)
        db_session.commit()

        response = client.get("/api/scheduler/emails?batch_date=2024-04-14")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        # All returned logs should have the specified batch_date
        for log in data['logs']:
            assert log['batch_date'] == "2024-04-14"

    def test_get_email_logs_respects_limit(self, client, db_session):
        """Should respect the limit parameter"""
        # Create multiple logs
        for i in range(5):
            log = EmailLog(
                id=uuid4(),
                batch_date=f"2024-04-{10+i:02d}",
                email_type="daily_digest",
                status="sent",
                to_email="user@example.com",
                from_email="system@example.com",
                subject=f"Log {i}",
                sent_at=datetime.now(timezone.utc),
            )
            db_session.add(log)
        db_session.commit()

        response = client.get("/api/scheduler/emails?limit=3")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        # Should return at most 3 logs
        assert len(data['logs']) <= 3

    def test_get_email_logs_log_format(self, client, db_session):
        """Each log should have consistent format"""
        log = EmailLog(
            id=uuid4(),
            batch_date="2024-04-14",
            email_type="test",
            status="sent",
            to_email="user@example.com",
            from_email="system@example.com",
            subject="Test",
            sent_at=datetime.now(timezone.utc),
            failed_at=None,
            recommendation_count=3,
            error_message=None,
        )
        db_session.add(log)
        db_session.commit()

        response = client.get("/api/scheduler/emails")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert len(data['logs']) >= 1
        first_log = data['logs'][0]

        # Verify required fields
        required_fields = [
            'id', 'batch_date', 'email_type', 'status', 'to_email',
            'subject', 'sent_at', 'failed_at', 'recommendation_count', 'error_message'
        ]
        for field in required_fields:
            assert field in first_log, f"Missing field: {field}"

        # Verify types
        assert isinstance(first_log['id'], str)
        assert isinstance(first_log['batch_date'], str)
        assert isinstance(first_log['status'], str)


class TestEmailEndpointsIntegration:
    """Integration tests for email endpoints"""

    def test_config_check_then_trigger_email_flow(self, client):
        """Full flow: check config, then attempt to send"""
        # Step 1: Check configuration
        config_response = client.get("/api/scheduler/email/config-check")
        assert config_response.status_code == status.HTTP_200_OK
        config_data = config_response.json()

        # Step 2: Attempt to send email
        trigger_response = client.post("/api/scheduler/trigger/email")
        assert trigger_response.status_code == status.HTTP_200_OK
        trigger_data = trigger_response.json()

        # If not configured, trigger should fail gracefully
        if not config_data['is_configured']:
            assert trigger_data['success'] is False
            assert trigger_data['sent'] is False

    def test_logs_endpoint_after_trigger(self, client):
        """After trigger attempt, logs endpoint should be accessible"""
        # Trigger email (may succeed or fail)
        client.post("/api/scheduler/trigger/email")

        # Logs endpoint should still work
        logs_response = client.get("/api/scheduler/emails")
        assert logs_response.status_code == status.HTTP_200_OK
        logs_data = logs_response.json()

        assert 'logs' in logs_data
        assert isinstance(logs_data['logs'], list)
