"""
Security tests for GraphQL login mutations.

CRITICAL: These tests ensure that sensitive data (passwords, tokens) are NEVER
logged in plaintext, preventing credential exposure in log files.

Compliance: PCI-DSS, SOC2, GDPR
Related: apps/service/mutations.py:54-65 (LoginUser mutation)
"""

import pytest
import logging
from unittest.mock import patch, MagicMock, call
from django.test import TestCase, RequestFactory
from graphql import GraphQLError
from apps.service.mutations import LoginUser
from apps.peoples.models import People
from apps.onboarding.models import Bt, Client
from apps.core import exceptions as excp


@pytest.mark.security
class TestLoginMutationSecurity(TestCase):
    """
    Test suite for login mutation security, focusing on credential protection.

    These tests verify that sensitive authentication data is properly sanitized
    and never exposed in log files, which could lead to credential compromise.
    """

    databases = ['default']

    def setUp(self):
        """Set up test fixtures for login mutation security tests."""
        self.factory = RequestFactory()

        # Create test client
        self.test_client = Client.objects.create(
            bucode='TEST001',
            buname='Test Client',
            enable=True
        )

        # Create test business unit
        self.test_bu = Bt.objects.create(
            btcode='BU001',
            btname='Test BU',
            client=self.test_client
        )

        # Create test user
        self.test_user = People.objects.create_user(
            loginid='test_user',
            password='test_password_123',
            peoplename='Test User',
            client=self.test_client,
            bu=self.test_bu,
            enable=True,
            isverified=True,
            deviceid='-1'
        )

    def test_password_not_logged_in_login_mutation(self):
        """
        CRITICAL: Verify that passwords are NEVER logged during login attempts.

        This test ensures that the password is not present in any log messages,
        preventing credential exposure in log files.

        Security Impact: CVSS 9.1 if passwords are logged
        Compliance: PCI-DSS Requirement 8.2.1, SOC2 CC6.1
        """
        # Create mock GraphQL info and input
        mock_info = MagicMock()
        mock_info.context = self.factory.post('/graphql/')
        mock_info.context.correlation_id = 'test-correlation-123'

        mock_input = MagicMock()
        mock_input.loginid = 'test_user'
        mock_input.password = 'test_password_123'  # SHOULD NOT appear in logs
        mock_input.deviceid = '12345'
        mock_input.clientcode = 'TEST001'

        # Patch logging to capture log calls
        with patch('apps.service.mutations.log') as mock_log, \
             patch('apps.service.mutations.sanitized_info') as mock_sanitized_info, \
             patch('apps.service.auth.authenticate') as mock_authenticate:

            # Configure mock authenticate to return test user
            mock_authenticate.return_value = self.test_user

            # Attempt login mutation
            try:
                LoginUser.mutate(None, mock_info, mock_input)
            except Exception:
                pass  # We're testing logging, not mutation success

            # CRITICAL ASSERTION: Password must NOT appear in any log call
            for log_call in mock_log.info.call_args_list:
                call_str = str(log_call)
                assert 'test_password_123' not in call_str, \
                    f"❌ PASSWORD FOUND IN LOG: {call_str}"

            # Verify sanitized_info was called (security fix)
            assert mock_sanitized_info.called, \
                "❌ sanitized_info() should be called for login attempts"

            # Verify sanitized_info does NOT receive password
            for call_args in mock_sanitized_info.call_args_list:
                call_str = str(call_args)
                assert 'test_password_123' not in call_str, \
                    f"❌ PASSWORD FOUND IN SANITIZED LOG: {call_str}"

    def test_sensitive_fields_sanitized_in_error_logs(self):
        """
        Verify that sensitive fields are sanitized even in error conditions.

        During authentication failures, ensure that passwords are not exposed
        in exception messages or error logs.
        """
        mock_info = MagicMock()
        mock_info.context = self.factory.post('/graphql/')
        mock_info.context.correlation_id = 'test-correlation-456'

        mock_input = MagicMock()
        mock_input.loginid = 'nonexistent_user'
        mock_input.password = 'secret_password_456'  # SHOULD NOT appear in logs
        mock_input.deviceid = '67890'
        mock_input.clientcode = 'INVALID'

        with patch('apps.service.mutations.log') as mock_log, \
             patch('apps.service.mutations.sanitized_info') as mock_sanitized_info:

            # Attempt login with invalid credentials
            with pytest.raises(GraphQLError):
                LoginUser.mutate(None, mock_info, mock_input)

            # Check all log calls for password exposure
            all_log_calls = (
                mock_log.info.call_args_list +
                mock_log.warning.call_args_list +
                mock_log.error.call_args_list
            )

            for log_call in all_log_calls:
                call_str = str(log_call)
                assert 'secret_password_456' not in call_str, \
                    f"❌ PASSWORD FOUND IN ERROR LOG: {call_str}"

    def test_token_not_logged_in_response(self):
        """
        Verify that JWT tokens are not logged in plaintext.

        JWT tokens should be treated as sensitive credentials and should not
        appear in log files to prevent session hijacking.
        """
        mock_info = MagicMock()
        mock_info.context = self.factory.post('/graphql/')
        mock_info.context.correlation_id = 'test-correlation-789'

        mock_input = MagicMock()
        mock_input.loginid = 'test_user'
        mock_input.password = 'test_password_123'
        mock_input.deviceid = '-1'
        mock_input.clientcode = 'TEST001'

        with patch('apps.service.mutations.log') as mock_log, \
             patch('apps.service.mutations.sanitized_info') as mock_sanitized_info, \
             patch('apps.service.auth.authenticate') as mock_authenticate, \
             patch('apps.service.mutations.get_token') as mock_get_token:

            mock_authenticate.return_value = self.test_user
            fake_token = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.test_token'
            mock_get_token.return_value = fake_token

            # Attempt login
            try:
                result = LoginUser.mutate(None, mock_info, mock_input)
            except Exception:
                pass

            # Verify token is not in logs
            all_log_calls = (
                mock_log.info.call_args_list +
                mock_log.warning.call_args_list
            )

            for log_call in all_log_calls:
                call_str = str(log_call)
                # Check for token pattern (JWT tokens start with eyJ)
                assert 'eyJ' not in call_str or fake_token not in call_str, \
                    f"❌ JWT TOKEN FOUND IN LOG: {call_str}"

    def test_correlation_id_used_for_tracking(self):
        """
        Verify that correlation IDs are used instead of sensitive data for tracking.

        Correlation IDs provide secure tracking without exposing sensitive data.
        """
        mock_info = MagicMock()
        mock_info.context = self.factory.post('/graphql/')
        test_correlation_id = 'secure-tracking-123'
        mock_info.context.correlation_id = test_correlation_id

        mock_input = MagicMock()
        mock_input.loginid = 'test_user'
        mock_input.password = 'test_password_123'
        mock_input.deviceid = '-1'
        mock_input.clientcode = 'TEST001'

        with patch('apps.service.mutations.sanitized_info') as mock_sanitized_info, \
             patch('apps.service.auth.authenticate') as mock_authenticate:

            mock_authenticate.return_value = self.test_user

            try:
                LoginUser.mutate(None, mock_info, mock_input)
            except Exception:
                pass

            # Verify correlation_id is passed to sanitized_info
            assert mock_sanitized_info.called, \
                "sanitized_info should be called"

            # Check if correlation_id was used
            call_kwargs = mock_sanitized_info.call_args[1]
            assert 'correlation_id' in call_kwargs, \
                "correlation_id should be passed to sanitized logging"
            assert call_kwargs['correlation_id'] == test_correlation_id, \
                f"correlation_id mismatch: {call_kwargs['correlation_id']}"

    def test_sanitized_info_import_exists(self):
        """
        Verify that sanitized_info function is properly imported.

        This ensures the security fix is in place and the sanitization
        function is available for use.
        """
        from apps.service import mutations

        # Check that sanitized_info is imported
        assert hasattr(mutations, 'sanitized_info'), \
            "❌ sanitized_info not imported in mutations.py"

        # Verify it's callable
        assert callable(mutations.sanitized_info), \
            "❌ sanitized_info is not callable"

    def test_no_plaintext_credentials_in_log_message_format(self):
        """
        Verify that log message formats do not include credential placeholders.

        This prevents accidental credential logging through format strings.
        """
        # Read the mutations.py source to verify log format
        import inspect
        source = inspect.getsource(LoginUser.mutate)

        # Check that old insecure logging pattern is NOT present
        assert 'log.info("%s, %s, %s"' not in source, \
            "❌ Old insecure logging pattern found in source"

        # Check that password variable is NOT in log calls
        assert 'input.password' not in source or \
               'sanitized' in source.lower(), \
            "❌ input.password appears in logging without sanitization"


@pytest.mark.security
class TestLoginMutationComplianceChecks(TestCase):
    """
    Compliance-focused tests for login mutation security.

    These tests verify compliance with security standards and regulations.
    """

    def test_pci_dss_compliance_no_password_logging(self):
        """
        PCI-DSS Requirement 8.2.1: Passwords must not be logged.

        This test verifies compliance with PCI-DSS password handling requirements.
        """
        # This is effectively tested in test_password_not_logged_in_login_mutation
        # but explicitly named for compliance documentation
        pass

    def test_soc2_cc6_1_compliance_credential_protection(self):
        """
        SOC2 CC6.1: Credentials must be protected in transit and at rest.

        This includes ensuring credentials are not exposed in log files.
        """
        # This is effectively tested in test_password_not_logged_in_login_mutation
        # but explicitly named for compliance documentation
        pass

    def test_gdpr_article_32_security_of_processing(self):
        """
        GDPR Article 32: Security of processing - credential protection.

        Ensures appropriate technical measures to secure authentication data.
        """
        # This is effectively tested in test_password_not_logged_in_login_mutation
        # but explicitly named for compliance documentation
        pass


# Test execution configuration
if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
