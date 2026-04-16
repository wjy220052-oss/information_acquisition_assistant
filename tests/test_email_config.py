"""
Tests for email configuration validation logic

Covers:
- Configuration state detection (not_configured, partially_configured, configured)
- Missing field identification
- Config preview generation with masked sensitive fields
- Help message generation
"""

import pytest
from unittest.mock import Mock, patch

from app.core.mailer import EmailConfig, get_email_config_status


class TestEmailConfigStateDetection:
    """Tests for detecting configuration state"""

    def test_all_fields_missing_returns_not_configured(self):
        """When all required fields are missing, state should be 'not_configured'"""
        config = EmailConfig()
        config.smtp_host = None
        config.smtp_user = None
        config.smtp_password = None
        config.from_email = None
        config.to_email = None

        status = config.get_config_status()

        assert status['is_configured'] is False
        assert status['state'] == 'not_configured'
        assert status['configured_count'] == 0
        assert status['total_required'] == 5
        assert len(status['missing_fields']) == 5

    def test_partial_config_returns_partially_configured(self):
        """When some fields are set, state should be 'partially_configured'"""
        config = EmailConfig()
        config.smtp_host = "smtp.gmail.com"
        config.smtp_user = "user@gmail.com"
        config.smtp_password = None
        config.from_email = None
        config.to_email = None

        status = config.get_config_status()

        assert status['is_configured'] is False
        assert status['state'] == 'partially_configured'
        assert status['configured_count'] == 2
        assert len(status['missing_fields']) == 3

    def test_all_fields_set_returns_configured(self):
        """When all required fields are set, state should be 'configured'"""
        config = EmailConfig()
        config.smtp_host = "smtp.gmail.com"
        config.smtp_user = "user@gmail.com"
        config.smtp_password = "secret"
        config.from_email = "user@gmail.com"
        config.to_email = "user@gmail.com"

        status = config.get_config_status()

        assert status['is_configured'] is True
        assert status['state'] == 'configured'
        assert status['configured_count'] == 5
        assert len(status['missing_fields']) == 0


class TestEmailConfigMissingFields:
    """Tests for identifying missing fields"""

    def test_missing_host_only(self):
        """Correctly identifies SMTP_HOST as missing"""
        config = EmailConfig()
        config.smtp_host = None
        config.smtp_user = "user"
        config.smtp_password = "pass"
        config.from_email = "from"
        config.to_email = "to"

        missing = config.get_missing_fields()

        assert 'SMTP_HOST' in missing
        assert 'SMTP_USER' not in missing
        assert 'SMTP_PASSWORD' not in missing
        assert 'EMAIL_FROM' not in missing
        assert 'EMAIL_TO' not in missing

    def test_missing_user_only(self):
        """Correctly identifies SMTP_USER as missing"""
        config = EmailConfig()
        config.smtp_host = "host"
        config.smtp_user = None
        config.smtp_password = "pass"
        config.from_email = "from"
        config.to_email = "to"

        missing = config.get_missing_fields()

        assert 'SMTP_HOST' not in missing
        assert 'SMTP_USER' in missing
        assert 'SMTP_PASSWORD' not in missing
        assert 'EMAIL_FROM' not in missing
        assert 'EMAIL_TO' not in missing

    def test_missing_password_only(self):
        """Correctly identifies SMTP_PASSWORD as missing"""
        config = EmailConfig()
        config.smtp_host = "host"
        config.smtp_user = "user"
        config.smtp_password = None
        config.from_email = "from"
        config.to_email = "to"

        missing = config.get_missing_fields()

        assert 'SMTP_PASSWORD' in missing

    def test_missing_from_only(self):
        """Correctly identifies EMAIL_FROM as missing"""
        config = EmailConfig()
        config.smtp_host = "host"
        config.smtp_user = "user"
        config.smtp_password = "pass"
        config.from_email = None
        config.to_email = "to"

        missing = config.get_missing_fields()

        assert 'EMAIL_FROM' in missing

    def test_missing_to_only(self):
        """Correctly identifies EMAIL_TO as missing"""
        config = EmailConfig()
        config.smtp_host = "host"
        config.smtp_user = "user"
        config.smtp_password = "pass"
        config.from_email = "from"
        config.to_email = None

        missing = config.get_missing_fields()

        assert 'EMAIL_TO' in missing

    def test_multiple_missing_fields(self):
        """Correctly identifies multiple missing fields"""
        config = EmailConfig()
        config.smtp_host = None
        config.smtp_user = None
        config.smtp_password = "pass"
        config.from_email = "from"
        config.to_email = "to"

        missing = config.get_missing_fields()

        assert 'SMTP_HOST' in missing
        assert 'SMTP_USER' in missing
        assert 'SMTP_PASSWORD' not in missing
        assert 'EMAIL_FROM' not in missing
        assert 'EMAIL_TO' not in missing
        assert len(missing) == 2


class TestEmailConfigPreview:
    """Tests for configuration preview generation"""

    def test_password_is_masked(self):
        """Password should be masked as '********' in preview"""
        config = EmailConfig()
        config.smtp_host = "smtp.gmail.com"
        config.smtp_user = "user@gmail.com"
        config.smtp_password = "my_secret_password"
        config.from_email = "user@gmail.com"
        config.to_email = "user@gmail.com"

        status = config.get_config_status()
        preview = status['config_preview']

        assert preview['smtp_password'] == '********'
        assert 'my_secret_password' not in str(preview)

    def test_missing_fields_show_not_set(self):
        """Missing fields should show '(not set)' in preview"""
        config = EmailConfig()
        config.smtp_host = None
        config.smtp_user = "user@gmail.com"
        config.smtp_password = None
        config.from_email = "user@gmail.com"
        config.to_email = "user@gmail.com"

        status = config.get_config_status()
        preview = status['config_preview']

        assert preview['smtp_host'] == '(not set)'
        assert preview['smtp_password'] == '(not set)'
        assert preview['smtp_user'] == 'user@gmail.com'

    def test_port_is_always_shown(self):
        """Port should always be shown in preview"""
        config = EmailConfig()
        # Even with no config, port has default value
        status = config.get_config_status()
        preview = status['config_preview']

        assert 'smtp_port' in preview
        assert preview['smtp_port'] == 587


class TestEmailConfigHelpMessages:
    """Tests for help message generation"""

    def test_not_configured_help_message_includes_env_example(self):
        """Help message for unconfigured state should include .env example"""
        config = EmailConfig()
        config.smtp_host = None
        config.smtp_user = None
        config.smtp_password = None
        config.from_email = None
        config.to_email = None

        status = config.get_config_status()

        assert 'not configured' in status['help_message'].lower()
        assert 'SMTP_HOST=' in status['help_message']
        assert 'Gmail' in status['help_message'] or 'App Password' in status['help_message']

    def test_partially_configured_help_message_lists_missing_fields(self):
        """Help message for partial config should list missing fields"""
        config = EmailConfig()
        config.smtp_host = "smtp.gmail.com"
        config.smtp_user = None
        config.smtp_password = None
        config.from_email = "user@gmail.com"
        config.to_email = "user@gmail.com"

        status = config.get_config_status()

        assert 'incomplete' in status['help_message'].lower() or 'Missing' in status['help_message']
        assert 'SMTP_USER' in status['help_message']
        assert 'SMTP_PASSWORD' in status['help_message']

    def test_configured_help_message_is_positive(self):
        """Help message for configured state should be positive"""
        config = EmailConfig()
        config.smtp_host = "smtp.gmail.com"
        config.smtp_user = "user@gmail.com"
        config.smtp_password = "secret"
        config.from_email = "user@gmail.com"
        config.to_email = "user@gmail.com"

        status = config.get_config_status()

        assert 'configured' in status['help_message'].lower() or 'ready' in status['help_message'].lower()

    def test_help_url_is_always_present(self):
        """Help URL should be present in all states"""
        config = EmailConfig()

        # Test not configured
        config.smtp_host = None
        status = config.get_config_status()
        assert 'help_url' in status
        assert status['help_url'].startswith('http')

        # Test configured
        config.smtp_host = "smtp.gmail.com"
        config.smtp_user = "user@gmail.com"
        config.smtp_password = "secret"
        config.from_email = "user@gmail.com"
        config.to_email = "user@gmail.com"
        status = config.get_config_status()
        assert 'help_url' in status


class TestGetEmailConfigStatusFunction:
    """Tests for the get_email_config_status helper function"""

    def test_returns_dict_with_all_expected_keys(self):
        """Function should return dict with all expected keys"""
        status = get_email_config_status()

        expected_keys = [
            'is_configured', 'state', 'configured_count', 'total_required',
            'missing_fields', 'config_preview', 'help_message', 'help_url'
        ]

        for key in expected_keys:
            assert key in status, f"Missing key: {key}"

    def test_missing_fields_is_list(self):
        """missing_fields should be a list"""
        status = get_email_config_status()

        assert isinstance(status['missing_fields'], list)

    def test_config_preview_is_dict(self):
        """config_preview should be a dict"""
        status = get_email_config_status()

        assert isinstance(status['config_preview'], dict)

    def test_state_is_valid_value(self):
        """state should be one of the valid values"""
        status = get_email_config_status()

        valid_states = ['not_configured', 'partially_configured', 'configured']
        assert status['state'] in valid_states


class TestEmailConfigIsConfiguredProperty:
    """Tests for the is_configured property"""

    def test_returns_true_when_all_fields_set(self):
        """is_configured should be True when all required fields are set"""
        config = EmailConfig()
        config.smtp_host = "smtp.gmail.com"
        config.smtp_user = "user@gmail.com"
        config.smtp_password = "secret"
        config.from_email = "user@gmail.com"
        config.to_email = "user@gmail.com"

        assert config.is_configured is True

    def test_returns_false_when_any_field_missing(self):
        """is_configured should be False when any required field is missing"""
        config = EmailConfig()
        config.smtp_host = "smtp.gmail.com"
        config.smtp_user = "user@gmail.com"
        config.smtp_password = None  # Missing
        config.from_email = "user@gmail.com"
        config.to_email = "user@gmail.com"

        assert config.is_configured is False

    def test_returns_false_when_all_fields_missing(self):
        """is_configured should be False when all fields are missing"""
        config = EmailConfig()
        config.smtp_host = None
        config.smtp_user = None
        config.smtp_password = None
        config.from_email = None
        config.to_email = None

        assert config.is_configured is False
