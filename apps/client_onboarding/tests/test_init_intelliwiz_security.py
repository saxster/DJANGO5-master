"""
Comprehensive Security Tests for init_intelliwiz Management Command

Tests password logging vulnerability fix (CVSS 9.1).
Ensures no credentials are exposed in logs during superuser creation.

Author: Claude Code
Date: 2025-10-01
"""

import logging
import pytest
from io import StringIO
from django.core.management import call_command
from django.test import TestCase, override_settings
from unittest.mock import Mock, patch, MagicMock
from apps.peoples.models import People
from apps.client_onboarding.models import Bt
from apps.core_onboarding.models import TypeAssist
from apps.client_onboarding.management.commands.init_intelliwiz import create_superuser


@pytest.mark.unit
@pytest.mark.security
class TestInitIntellwizPasswordSecurity(TestCase):
    """Test suite for password logging vulnerability fix."""

    def setUp(self):
        """Set up test environment."""
        # Create required TypeAssist entries
        bvidentifier = TypeAssist.objects.create(
            tatype_id=1,
            tacode='BVIDENTIFIER',
            taname='BV Identifier'
        )
        TypeAssist.objects.create(
            tatype=bvidentifier,
            tacode='CLIENT',
            taname='Client'
        )
        TypeAssist.objects.create(
            tatype=bvidentifier,
            tacode='SITE',
            taname='Site'
        )

        # Create NONE Bt as parent
        Bt.objects.create(
            bucode='NONE',
            buname='None',
            enable=True
        )

    def tearDown(self):
        """Clean up after tests."""
        People.objects.filter(loginid="superadmin").delete()
        Bt.objects.all().delete()
        TypeAssist.objects.all().delete()

    @patch('apps.client_onboarding.management.commands.init_intelliwiz.log')
    def test_password_not_logged_in_superuser_creation(self, mock_log):
        """
        CRITICAL: Verify that passwords are NEVER logged during superuser creation.

        Security Impact: CVSS 9.1 if passwords are logged (PCI-DSS violation)
        """
        # Create test client and site
        from apps.client_onboarding.management.commands.init_intelliwiz import create_dummy_client_and_site
        client, site = create_dummy_client_and_site()

        # Create superuser
        user = create_superuser(client, site)

        # Assert user was created
        assert user is not None
        assert user.loginid == "superadmin"

        # CRITICAL ASSERTION: Password must NOT appear in any log call
        for call in mock_log.info.call_args_list:
            call_str = str(call)
            assert 'superadmin@2022#' not in call_str, \
                f"❌ PASSWORD FOUND IN LOG: {call_str}"
            assert 'password' not in call_str.lower() or \
                   'password' in call_str.lower() and 'superadmin@2022#' not in call_str, \
                f"❌ PASSWORD CONTEXT FOUND IN LOG: {call_str}"

    @patch('apps.client_onboarding.management.commands.init_intelliwiz.log')
    def test_loginid_is_logged(self, mock_log):
        """Verify that loginid (non-sensitive) IS logged for tracking."""
        from apps.client_onboarding.management.commands.init_intelliwiz import create_dummy_client_and_site
        client, site = create_dummy_client_and_site()

        user = create_superuser(client, site)

        # Assert loginid is logged (allowed)
        logged_loginid = False
        for call in mock_log.info.call_args_list:
            if 'superadmin' in str(call):
                logged_loginid = True
                break

        assert logged_loginid, "✅ loginid should be logged for audit trail"

    @patch('apps.client_onboarding.management.commands.init_intelliwiz.log')
    def test_correlation_id_present_in_logs(self, mock_log):
        """Verify correlation ID is present for tracking without exposing credentials."""
        from apps.client_onboarding.management.commands.init_intelliwiz import create_dummy_client_and_site
        client, site = create_dummy_client_and_site()

        user = create_superuser(client, site)

        # Check for correlation_id in log extra data
        found_correlation_id = False
        for call in mock_log.info.call_args_list:
            if len(call.kwargs) > 0 and 'extra' in call.kwargs:
                extra = call.kwargs['extra']
                if 'correlation_id' in extra:
                    found_correlation_id = True
                    # Validate correlation_id format (UUID)
                    import re
                    uuid_pattern = r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
                    assert re.match(uuid_pattern, extra['correlation_id']), \
                        "Correlation ID should be valid UUID"
                    break

        assert found_correlation_id, "Correlation ID should be present for secure tracking"

    @patch('apps.client_onboarding.management.commands.init_intelliwiz.log')
    def test_security_event_tracking(self, mock_log):
        """Verify security_event field is present for audit purposes."""
        from apps.client_onboarding.management.commands.init_intelliwiz import create_dummy_client_and_site
        client, site = create_dummy_client_and_site()

        user = create_superuser(client, site)

        # Check for security_event in log extra data
        found_security_event = False
        for call in mock_log.info.call_args_list:
            if len(call.kwargs) > 0 and 'extra' in call.kwargs:
                extra = call.kwargs['extra']
                if 'security_event' in extra:
                    found_security_event = True
                    assert extra['security_event'] == 'superuser_creation', \
                        "Security event should be 'superuser_creation'"
                    break

        assert found_security_event, "Security event should be tracked in logs"

    def test_password_set_correctly(self):
        """Verify password is set correctly even though not logged."""
        from apps.client_onboarding.management.commands.init_intelliwiz import (
            create_dummy_client_and_site,
            DEFAULT_PASSWORD
        )
        client, site = create_dummy_client_and_site()

        user = create_superuser(client, site)

        # Verify password was set correctly
        assert user.check_password(DEFAULT_PASSWORD), \
            "Password should be set correctly even if not logged"

    @patch('apps.client_onboarding.management.commands.init_intelliwiz.log')
    def test_existing_superuser_not_recreated(self, mock_log):
        """Verify existing superuser doesn't trigger password logging."""
        from apps.client_onboarding.management.commands.init_intelliwiz import create_dummy_client_and_site
        client, site = create_dummy_client_and_site()

        # Create first time
        user1 = create_superuser(client, site)
        initial_log_count = mock_log.info.call_count

        # Try to create again
        user2 = create_superuser(client, site)

        # Verify same user returned
        assert user1.id == user2.id, "Same user should be returned"

        # Verify password still not in any logs
        for call in mock_log.info.call_args_list:
            call_str = str(call)
            assert 'superadmin@2022#' not in call_str, \
                f"❌ PASSWORD FOUND IN LOG (existing user path): {call_str}"

    @pytest.mark.django_db
    def test_pci_dss_compliance_no_password_logging(self):
        """
        PCI-DSS Requirement 8.2.1: Passwords must not be logged.

        This test validates compliance with payment card industry data security standards.
        """
        from apps.client_onboarding.management.commands.init_intelliwiz import (
            create_dummy_client_and_site,
            DEFAULT_PASSWORD
        )

        # Capture all log output
        with patch('apps.client_onboarding.management.commands.init_intelliwiz.log') as mock_log:
            client, site = create_dummy_client_and_site()
            user = create_superuser(client, site)

            # Convert all log calls to string for comprehensive search
            all_log_output = ""
            for call in mock_log.info.call_args_list + mock_log.warning.call_args_list + \
                        mock_log.error.call_args_list + mock_log.debug.call_args_list:
                all_log_output += str(call)

            # CRITICAL: Password must NEVER appear in logs
            assert DEFAULT_PASSWORD not in all_log_output, \
                "❌ PCI-DSS VIOLATION: Password found in logs"

    @pytest.mark.django_db
    def test_gdpr_compliance_no_excessive_data_logging(self):
        """
        GDPR Article 5(1)(c): Data minimization.

        Only necessary information should be logged.
        """
        from apps.client_onboarding.management.commands.init_intelliwiz import create_dummy_client_and_site

        with patch('apps.client_onboarding.management.commands.init_intelliwiz.log') as mock_log:
            client, site = create_dummy_client_and_site()
            user = create_superuser(client, site)

            # Check that only necessary fields are logged
            for call in mock_log.info.call_args_list:
                if 'extra' in call.kwargs:
                    extra = call.kwargs['extra']
                    # These are acceptable
                    acceptable_fields = {'user_id', 'correlation_id', 'security_event', 'peoplecode'}
                    # These should NOT be present
                    forbidden_fields = {'password', 'password_hash', 'mobno', 'email'}

                    for field in forbidden_fields:
                        assert field not in extra, \
                            f"❌ GDPR VIOLATION: Excessive data '{field}' in logs"


@pytest.mark.integration
@pytest.mark.security
class TestInitIntellwizManagementCommandSecurity(TestCase):
    """Integration tests for full management command execution."""

    @pytest.mark.django_db(transaction=True)
    @override_settings(DEBUG=False)  # Test in production-like environment
    def test_full_command_execution_no_password_leakage(self):
        """
        Integration test: Full management command execution with log monitoring.

        Simulates production environment to ensure no password leakage.
        """
        # Note: This test requires database 'default' to exist
        # In real execution, would use: python manage.py init_intelliwiz default

        from apps.client_onboarding.management.commands.init_intelliwiz import (
            create_dummy_client_and_site,
            DEFAULT_PASSWORD
        )

        # Set up logging capture
        log_stream = StringIO()
        handler = logging.StreamHandler(log_stream)
        handler.setLevel(logging.INFO)
        logger = logging.getLogger('apps.client_onboarding.management.commands.init_intelliwiz')
        logger.addHandler(handler)

        try:
            client, site = create_dummy_client_and_site()
            user = create_superuser(client, site)

            # Get all logged output
            log_output = log_stream.getvalue()

            # CRITICAL: Password must not be in output
            assert DEFAULT_PASSWORD not in log_output, \
                f"❌ PASSWORD LEAKED IN LOGS:\n{log_output}"

            # Verify user was created successfully
            assert user is not None
            assert People.objects.filter(loginid="superadmin").exists()

        finally:
            logger.removeHandler(handler)
            handler.close()


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
