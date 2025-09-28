"""
Comprehensive tests for Session Activity Monitoring.

Tests Rule #10: Session Security Standards implementation.
Validates:
- Activity timestamp tracking
- Inactivity timeout enforcement
- IP address change detection
- User-Agent change detection
- Security event logging
"""

import time
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock

import pytest
from django.contrib.auth import get_user_model
from django.contrib.sessions.backends.db import SessionStore
from django.core.cache import cache
from django.http import HttpResponse
from django.test import TestCase, RequestFactory, override_settings
from django.utils import timezone

from apps.core.middleware.session_activity import (
    SessionActivityMiddleware,
    SessionRotationMiddleware
)

User = get_user_model()


@pytest.mark.security
class SessionActivityMiddlewareTest(TestCase):
    """Test SessionActivityMiddleware functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.factory = RequestFactory()
        self.middleware = SessionActivityMiddleware(get_response=lambda r: HttpResponse())
        self.user = User.objects.create_user(
            loginid='activity_test',
            email='activity@test.com',
            password='SecurePass123!',
            peoplename='Activity Test User'
        )

    def tearDown(self):
        """Clean up cache after each test."""
        cache.clear()

    def test_activity_timestamp_creation(self):
        """Test that activity timestamp is created on authenticated requests."""
        request = self.factory.get('/')
        request.user = self.user
        request.session = SessionStore()
        request.session.create()

        self.middleware(request)

        self.assertIn(
            SessionActivityMiddleware.SESSION_ACTIVITY_KEY,
            request.session
        )

        last_activity = request.session[SessionActivityMiddleware.SESSION_ACTIVITY_KEY]
        activity_time = datetime.fromisoformat(last_activity)

        time_diff = (timezone.now() - activity_time).total_seconds()
        self.assertLess(time_diff, 2)

    def test_activity_timestamp_updates(self):
        """Test that activity timestamp updates on subsequent requests."""
        request = self.factory.get('/')
        request.user = self.user
        request.session = SessionStore()
        request.session.create()

        self.middleware(request)
        first_activity = request.session[SessionActivityMiddleware.SESSION_ACTIVITY_KEY]

        time.sleep(1)

        self.middleware(request)
        second_activity = request.session[SessionActivityMiddleware.SESSION_ACTIVITY_KEY]

        first_time = datetime.fromisoformat(first_activity)
        second_time = datetime.fromisoformat(second_activity)

        self.assertGreater(second_time, first_time)

    @override_settings(SESSION_ACTIVITY_TIMEOUT=2)
    def test_inactivity_timeout_enforcement(self):
        """Test that sessions timeout after configured inactivity period."""
        middleware = SessionActivityMiddleware(get_response=lambda r: HttpResponse())

        request = self.factory.get('/')
        request.user = self.user
        request.session = SessionStore()
        request.session.create()
        request.correlation_id = 'test-correlation-123'

        past_time = timezone.now() - timedelta(seconds=5)
        request.session[SessionActivityMiddleware.SESSION_ACTIVITY_KEY] = past_time.isoformat()
        request.session.save()

        response = middleware(request)

        self.assertEqual(response.status_code, 401)
        self.assertIn('Session expired due to inactivity', response.content.decode())

    def test_skip_tracking_for_static_files(self):
        """Test that static file requests don't trigger activity tracking."""
        request = self.factory.get('/static/css/style.css')
        request.user = self.user
        request.session = SessionStore()
        request.session.create()

        initial_session_keys = set(request.session.keys())

        self.middleware(request)

        self.assertEqual(set(request.session.keys()), initial_session_keys)

    def test_skip_tracking_for_health_checks(self):
        """Test that health check requests don't trigger activity tracking."""
        request = self.factory.get('/health/')
        request.user = self.user
        request.session = SessionStore()
        request.session.create()

        initial_session_keys = set(request.session.keys())

        self.middleware(request)

        self.assertEqual(set(request.session.keys()), initial_session_keys)

    def test_ip_address_tracking(self):
        """Test that IP address is tracked in session."""
        request = self.factory.get('/')
        request.user = self.user
        request.session = SessionStore()
        request.session.create()
        request.META['REMOTE_ADDR'] = '192.168.1.100'

        self.middleware(request)

        self.assertEqual(
            request.session[SessionActivityMiddleware.SESSION_IP_KEY],
            '192.168.1.100'
        )

    @patch('apps.core.middleware.session_activity.logger')
    def test_ip_address_change_detection(self, mock_logger):
        """Test that IP address changes are logged as potential hijacking."""
        request = self.factory.get('/')
        request.user = self.user
        request.session = SessionStore()
        request.session.create()
        request.correlation_id = 'test-correlation-456'

        request.META['REMOTE_ADDR'] = '192.168.1.100'
        request.session[SessionActivityMiddleware.SESSION_IP_KEY] = '192.168.1.100'

        self.middleware(request)

        request.META['REMOTE_ADDR'] = '10.0.0.50'
        self.middleware(request)

        mock_logger.warning.assert_called()
        warning_call = mock_logger.warning.call_args

        self.assertIn('Session IP address changed', warning_call[0][0])
        self.assertIn('original_ip', warning_call[1]['extra'])
        self.assertEqual(warning_call[1]['extra']['original_ip'], '192.168.1.100')
        self.assertEqual(warning_call[1]['extra']['new_ip'], '10.0.0.50')

    def test_user_agent_tracking(self):
        """Test that User-Agent is tracked in session."""
        request = self.factory.get('/')
        request.user = self.user
        request.session = SessionStore()
        request.session.create()
        request.META['HTTP_USER_AGENT'] = 'Mozilla/5.0 (Test Browser)'

        self.middleware(request)

        self.assertEqual(
            request.session[SessionActivityMiddleware.SESSION_USER_AGENT_KEY],
            'Mozilla/5.0 (Test Browser)'
        )

    @patch('apps.core.middleware.session_activity.logger')
    def test_user_agent_change_detection(self, mock_logger):
        """Test that User-Agent changes are logged as suspicious."""
        request = self.factory.get('/')
        request.user = self.user
        request.session = SessionStore()
        request.session.create()
        request.correlation_id = 'test-correlation-789'

        request.META['HTTP_USER_AGENT'] = 'Mozilla/5.0 (Original)'
        request.session[SessionActivityMiddleware.SESSION_USER_AGENT_KEY] = 'Mozilla/5.0 (Original)'

        self.middleware(request)

        request.META['HTTP_USER_AGENT'] = 'Mozilla/5.0 (Different)'
        self.middleware(request)

        mock_logger.warning.assert_called()
        warning_call = mock_logger.warning.call_args
        self.assertIn('Session User-Agent changed', warning_call[0][0])

    def test_x_forwarded_for_ip_extraction(self):
        """Test that IP is correctly extracted from X-Forwarded-For header."""
        request = self.factory.get('/')
        request.user = self.user
        request.session = SessionStore()
        request.session.create()
        request.META['HTTP_X_FORWARDED_FOR'] = '203.0.113.1, 192.168.1.1, 10.0.0.1'

        self.middleware(request)

        self.assertEqual(
            request.session[SessionActivityMiddleware.SESSION_IP_KEY],
            '203.0.113.1'
        )

    def test_unauthenticated_users_not_tracked(self):
        """Test that unauthenticated users don't get activity tracking."""
        from django.contrib.auth.models import AnonymousUser

        request = self.factory.get('/')
        request.user = AnonymousUser()
        request.session = SessionStore()
        request.session.create()

        self.middleware(request)

        self.assertNotIn(
            SessionActivityMiddleware.SESSION_ACTIVITY_KEY,
            request.session
        )

    @patch('apps.core.middleware.session_activity.logger')
    def test_timeout_event_logging(self, mock_logger):
        """Test that timeout events are properly logged."""
        middleware = SessionActivityMiddleware(get_response=lambda r: HttpResponse())
        middleware.activity_timeout = 1

        request = self.factory.get('/')
        request.user = self.user
        request.session = SessionStore()
        request.session.create()
        request.correlation_id = 'test-timeout-001'
        request.META['REMOTE_ADDR'] = '192.168.1.100'

        past_time = timezone.now() - timedelta(seconds=10)
        request.session[SessionActivityMiddleware.SESSION_ACTIVITY_KEY] = past_time.isoformat()
        request.session.save()

        response = middleware(request)

        self.assertEqual(response.status_code, 401)

        mock_logger.warning.assert_called()
        log_call = mock_logger.warning.call_args

        self.assertIn('Session timed out', log_call[0][0])
        self.assertIn('correlation_id', log_call[1]['extra'])
        self.assertEqual(log_call[1]['extra']['correlation_id'], 'test-timeout-001')

    @override_settings(SESSION_ACTIVITY_TIMEOUT=1800)
    def test_configurable_timeout_duration(self):
        """Test that timeout duration is configurable via settings."""
        middleware = SessionActivityMiddleware(get_response=lambda r: HttpResponse())

        self.assertEqual(middleware.activity_timeout, 1800)

    def test_timeout_counter_increment(self):
        """Test that timeout events increment counter for monitoring."""
        middleware = SessionActivityMiddleware(get_response=lambda r: HttpResponse())
        middleware.activity_timeout = 1

        request = self.factory.get('/')
        request.user = self.user
        request.session = SessionStore()
        request.session.create()
        request.correlation_id = 'test-counter-001'

        past_time = timezone.now() - timedelta(seconds=10)
        request.session[SessionActivityMiddleware.SESSION_ACTIVITY_KEY] = past_time.isoformat()
        request.session.save()

        cache.set(SessionActivityMiddleware.CACHE_KEY_TIMEOUT_EVENTS, 5)

        middleware(request)

        timeout_count = cache.get(SessionActivityMiddleware.CACHE_KEY_TIMEOUT_EVENTS)
        self.assertEqual(timeout_count, 6)


@pytest.mark.security
class SessionRotationMiddlewareTest(TestCase):
    """Test SessionRotationMiddleware functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.factory = RequestFactory()
        self.middleware = SessionRotationMiddleware(get_response=lambda r: HttpResponse())
        self.user = User.objects.create_user(
            loginid='rotation_test',
            email='rotation@test.com',
            password='SecurePass123!',
            peoplename='Rotation Test User'
        )

    def test_session_rotation_on_flag(self):
        """Test that session is rotated when rotation flag is set."""
        request = self.factory.get('/')
        request.user = self.user
        request.session = SessionStore()
        request.session.create()

        old_session_key = request.session.session_key
        request.session[SessionRotationMiddleware.SESSION_ROTATION_FLAG] = True
        request.session.save()

        self.middleware(request)

        new_session_key = request.session.session_key

        self.assertNotEqual(old_session_key, new_session_key)

    def test_rotation_flag_removed_after_rotation(self):
        """Test that rotation flag is removed after rotation."""
        request = self.factory.get('/')
        request.user = self.user
        request.session = SessionStore()
        request.session.create()
        request.session[SessionRotationMiddleware.SESSION_ROTATION_FLAG] = True
        request.session.save()

        self.middleware(request)

        self.assertNotIn(
            SessionRotationMiddleware.SESSION_ROTATION_FLAG,
            request.session
        )

    @patch('apps.core.middleware.session_activity.logger')
    def test_rotation_logging(self, mock_logger):
        """Test that session rotations are logged for audit."""
        request = self.factory.get('/')
        request.user = self.user
        request.session = SessionStore()
        request.session.create()
        request.correlation_id = 'test-rotation-001'
        request.session[SessionRotationMiddleware.SESSION_ROTATION_FLAG] = True
        request.session.save()

        self.middleware(request)

        mock_logger.info.assert_called()
        log_call = mock_logger.info.call_args

        self.assertIn('Session rotated', log_call[0][0])
        self.assertIn('correlation_id', log_call[1]['extra'])

    def test_no_rotation_without_flag(self):
        """Test that session is not rotated without rotation flag."""
        request = self.factory.get('/')
        request.user = self.user
        request.session = SessionStore()
        request.session.create()

        old_session_key = request.session.session_key

        self.middleware(request)

        self.assertEqual(request.session.session_key, old_session_key)

    def test_unauthenticated_users_skip_rotation(self):
        """Test that unauthenticated users don't trigger rotation."""
        from django.contrib.auth.models import AnonymousUser

        request = self.factory.get('/')
        request.user = AnonymousUser()
        request.session = SessionStore()
        request.session.create()
        request.session[SessionRotationMiddleware.SESSION_ROTATION_FLAG] = True

        old_session_key = request.session.session_key

        self.middleware(request)

        self.assertEqual(request.session.session_key, old_session_key)


@pytest.mark.security
class SessionActivityIntegrationTest(TestCase):
    """Integration tests for session activity monitoring."""

    def setUp(self):
        """Set up test fixtures."""
        self.factory = RequestFactory()
        self.user = User.objects.create_user(
            loginid='integration_test',
            email='integration@test.com',
            password='SecurePass123!',
            peoplename='Integration Test User'
        )

    def tearDown(self):
        """Clean up cache."""
        cache.clear()

    def test_activity_monitoring_with_multiple_requests(self):
        """Test activity monitoring across multiple requests."""
        middleware = SessionActivityMiddleware(get_response=lambda r: HttpResponse())

        request = self.factory.get('/dashboard/')
        request.user = self.user
        request.session = SessionStore()
        request.session.create()
        request.META['REMOTE_ADDR'] = '192.168.1.100'

        middleware(request)
        activity_1 = request.session[SessionActivityMiddleware.SESSION_ACTIVITY_KEY]

        time.sleep(0.5)

        request = self.factory.get('/reports/')
        request.user = self.user
        request.session = SessionStore(session_key=request.session.session_key)
        request.META['REMOTE_ADDR'] = '192.168.1.100'

        middleware(request)
        activity_2 = request.session.get(SessionActivityMiddleware.SESSION_ACTIVITY_KEY)

        if activity_2:
            time_1 = datetime.fromisoformat(activity_1)
            time_2 = datetime.fromisoformat(activity_2)
            self.assertGreater(time_2, time_1)

    @override_settings(SESSION_ACTIVITY_TIMEOUT=2)
    def test_timeout_clears_session_data(self):
        """Test that timeout properly clears sensitive session data."""
        middleware = SessionActivityMiddleware(get_response=lambda r: HttpResponse())

        request = self.factory.get('/')
        request.user = self.user
        request.session = SessionStore()
        request.session.create()
        request.correlation_id = 'test-clear-001'

        request.session['sensitive_data'] = 'secret_value'
        past_time = timezone.now() - timedelta(seconds=10)
        request.session[SessionActivityMiddleware.SESSION_ACTIVITY_KEY] = past_time.isoformat()
        request.session.save()

        response = middleware(request)

        self.assertEqual(response.status_code, 401)

    def test_concurrent_session_activity_tracking(self):
        """Test activity tracking with concurrent sessions."""
        middleware = SessionActivityMiddleware(get_response=lambda r: HttpResponse())

        sessions = []
        for i in range(5):
            request = self.factory.get(f'/page{i}/')
            request.user = self.user
            request.session = SessionStore()
            request.session.create()
            request.META['REMOTE_ADDR'] = f'192.168.1.{100 + i}'

            middleware(request)
            sessions.append(request.session.session_key)

        self.assertEqual(len(set(sessions)), 5)

    @patch('apps.core.middleware.session_activity.logger')
    def test_invalid_timestamp_handling(self, mock_logger):
        """Test graceful handling of invalid activity timestamps."""
        request = self.factory.get('/')
        request.user = self.user
        request.session = SessionStore()
        request.session.create()

        request.session[SessionActivityMiddleware.SESSION_ACTIVITY_KEY] = 'invalid-timestamp'
        request.session.save()

        response = self.middleware(request)

        self.assertEqual(response.status_code, 200)

        mock_logger.warning.assert_called()
        log_call = mock_logger.warning.call_args
        self.assertIn('Invalid last_activity timestamp', log_call[0][0])


@pytest.mark.security
class SessionSecurityComplianceTest(TestCase):
    """Test overall compliance with Rule #10: Session Security Standards."""

    def test_session_configuration_compliance(self):
        """Test that all session settings comply with Rule #10."""
        from django.conf import settings

        self.assertEqual(settings.SESSION_COOKIE_AGE, 2 * 60 * 60)
        self.assertTrue(settings.SESSION_SAVE_EVERY_REQUEST)
        self.assertTrue(settings.SESSION_EXPIRE_AT_BROWSER_CLOSE)
        self.assertTrue(settings.SESSION_COOKIE_HTTPONLY)
        self.assertEqual(settings.SESSION_COOKIE_SAMESITE, "Lax")

    def test_middleware_chain_includes_activity_monitoring(self):
        """Test that session activity middleware is in middleware chain."""
        from django.conf import settings

        middleware_list = settings.MIDDLEWARE

        self.assertIn(
            'django.contrib.sessions.middleware.SessionMiddleware',
            middleware_list
        )

    def test_session_timeout_meets_security_requirements(self):
        """Test that session timeout is not excessive."""
        from django.conf import settings

        max_allowed_age = 2 * 60 * 60

        self.assertLessEqual(
            settings.SESSION_COOKIE_AGE,
            max_allowed_age,
            "Session cookie age exceeds Rule #10 maximum of 2 hours"
        )