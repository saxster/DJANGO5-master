"""
Comprehensive Session Management Tests

Tests for multi-device session tracking, revocation, and security monitoring.

Security Focus:
    - Session isolation between users
    - Device fingerprinting
    - Suspicious activity detection
    - Session revocation
    - Admin oversight
"""

import pytest
from django.test import TestCase, RequestFactory
from django.contrib.auth import get_user_model
from django.contrib.sessions.models import Session
from datetime import timedelta
from django.utils import timezone
from unittest.mock import patch, MagicMock

from apps.peoples.models.session_models import UserSession, SessionActivityLog
from apps.peoples.services.session_management_service import session_management_service
from apps.peoples.signals.session_signals import track_user_login

People = get_user_model()


class UserSessionModelTests(TestCase):
    """Test UserSession model functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.user = People.objects.create_user(
            loginid='testuser',
            password='testpass123',
            peoplename='Test User',
            email='test@example.com'
        )

        self.session = Session.objects.create(
            session_key='test_session_key',
            expire_date=timezone.now() + timedelta(hours=2)
        )

    def test_create_user_session(self):
        """Test creating a UserSession."""
        user_session = UserSession.objects.create(
            user=self.user,
            session=self.session,
            device_fingerprint='abc123',
            device_name='Chrome on Windows',
            device_type='desktop',
            user_agent='Mozilla/5.0...',
            browser='Chrome',
            browser_version='120.0',
            os='Windows',
            os_version='10',
            ip_address='192.168.1.1',
            expires_at=self.session.expire_date
        )

        self.assertIsNotNone(user_session.id)
        self.assertEqual(user_session.user, self.user)
        self.assertFalse(user_session.revoked)

    def test_device_fingerprint_generation(self):
        """Test device fingerprint generation."""
        fingerprint1 = UserSession.generate_device_fingerprint(
            'Mozilla/5.0 Chrome',
            '192.168.1.1'
        )
        fingerprint2 = UserSession.generate_device_fingerprint(
            'Mozilla/5.0 Chrome',
            '192.168.1.1'
        )
        fingerprint3 = UserSession.generate_device_fingerprint(
            'Mozilla/5.0 Firefox',
            '192.168.1.1'
        )

        # Same input = same fingerprint
        self.assertEqual(fingerprint1, fingerprint2)

        # Different input = different fingerprint
        self.assertNotEqual(fingerprint1, fingerprint3)

    def test_session_expiration(self):
        """Test session expiration check."""
        # Create expired session
        expired_session = UserSession.objects.create(
            user=self.user,
            session=self.session,
            device_fingerprint='abc123',
            user_agent='Test',
            ip_address='192.168.1.1',
            expires_at=timezone.now() - timedelta(hours=1)  # Expired 1 hour ago
        )

        self.assertTrue(expired_session.is_expired())
        self.assertFalse(expired_session.is_active())

    def test_session_revocation(self):
        """Test session revocation."""
        user_session = UserSession.objects.create(
            user=self.user,
            session=self.session,
            device_fingerprint='abc123',
            user_agent='Test',
            ip_address='192.168.1.1',
            expires_at=timezone.now() + timedelta(hours=2)
        )

        self.assertTrue(user_session.is_active())

        # Revoke session
        user_session.revoke(revoked_by=self.user, reason='user_action')

        self.assertTrue(user_session.revoked)
        self.assertIsNotNone(user_session.revoked_at)
        self.assertEqual(user_session.revoked_by, self.user)
        self.assertFalse(user_session.is_active())


class SessionManagementServiceTests(TestCase):
    """Test SessionManagementService functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.user = People.objects.create_user(
            loginid='testuser',
            password='testpass123',
            peoplename='Test User'
        )

        # Create multiple sessions
        for i in range(3):
            session = Session.objects.create(
                session_key=f'session_{i}',
                expire_date=timezone.now() + timedelta(hours=2)
            )

            UserSession.objects.create(
                user=self.user,
                session=session,
                device_fingerprint=f'fingerprint_{i}',
                device_name=f'Device {i}',
                device_type='desktop',
                user_agent=f'UserAgent {i}',
                browser='Chrome',
                os='Windows',
                ip_address='192.168.1.1',
                expires_at=session.expire_date,
                is_current=(i == 0)  # First session is current
            )

    def test_get_user_sessions(self):
        """Test getting user sessions."""
        sessions = session_management_service.get_user_sessions(self.user)

        self.assertEqual(len(sessions), 3)
        self.assertIsInstance(sessions[0].device_name, str)

    def test_revoke_session(self):
        """Test revoking a specific session."""
        session = UserSession.objects.filter(user=self.user).first()

        success, message = session_management_service.revoke_session(
            session_id=session.id,
            revoked_by=self.user,
            reason='user_action'
        )

        self.assertTrue(success)
        session.refresh_from_db()
        self.assertTrue(session.revoked)

    def test_revoke_session_unauthorized(self):
        """Test preventing unauthorized session revocation."""
        other_user = People.objects.create_user(
            loginid='otheruser',
            password='testpass123',
            peoplename='Other User'
        )

        session = UserSession.objects.filter(user=self.user).first()

        success, message = session_management_service.revoke_session(
            session_id=session.id,
            revoked_by=other_user,
            reason='user_action'
        )

        self.assertFalse(success)
        self.assertIn('own sessions', message)

    def test_revoke_all_sessions(self):
        """Test revoking all sessions."""
        sessions = list(UserSession.objects.filter(user=self.user))
        current_session_key = sessions[0].session.session_key

        count, message = session_management_service.revoke_all_sessions(
            user=self.user,
            except_current=True,
            current_session_key=current_session_key
        )

        # Should revoke all except current (3 total, 1 current = 2 revoked)
        self.assertEqual(count, 2)

        # Verify current session still active
        sessions[0].refresh_from_db()
        self.assertFalse(sessions[0].revoked)

        # Verify others revoked
        for session in sessions[1:]:
            session.refresh_from_db()
            self.assertTrue(session.revoked)

    def test_get_session_statistics(self):
        """Test getting session statistics."""
        stats = session_management_service.get_session_statistics(self.user)

        self.assertEqual(stats['total_sessions'], 3)
        self.assertEqual(stats['active_sessions'], 3)
        self.assertIn('device_breakdown', stats)
        self.assertIn('recent_logins', stats)

    def test_cleanup_expired_sessions(self):
        """Test cleaning up expired sessions."""
        # Create expired session
        expired_session_obj = Session.objects.create(
            session_key='expired_session',
            expire_date=timezone.now() + timedelta(hours=1)
        )

        UserSession.objects.create(
            user=self.user,
            session=expired_session_obj,
            device_fingerprint='expired',
            user_agent='Test',
            ip_address='192.168.1.1',
            expires_at=timezone.now() - timedelta(hours=1)  # Expired
        )

        count = session_management_service.cleanup_expired_sessions()

        self.assertGreaterEqual(count, 1)


class SessionSignalsTests(TestCase):
    """Test session signal handlers."""

    def setUp(self):
        """Set up test fixtures."""
        self.factory = RequestFactory()
        self.user = People.objects.create_user(
            loginid='testuser',
            password='testpass123',
            peoplename='Test User'
        )

    @patch('apps.peoples.signals.session_signals.parse')
    def test_user_login_creates_session(self, mock_parse):
        """Test that user login creates UserSession."""
        # Mock user agent parsing
        mock_ua = MagicMock()
        mock_ua.is_mobile = False
        mock_ua.is_tablet = False
        mock_ua.is_pc = True
        mock_ua.browser.family = 'Chrome'
        mock_ua.browser.version_string = '120.0'
        mock_ua.os.family = 'Windows'
        mock_ua.os.version_string = '10'
        mock_parse.return_value = mock_ua

        # Create request
        request = self.factory.get('/', HTTP_USER_AGENT='Mozilla/5.0')
        request.session = self.client.session
        request.session.create()

        # Trigger signal
        track_user_login(
            sender=None,
            request=request,
            user=self.user
        )

        # Verify UserSession created
        user_sessions = UserSession.objects.filter(user=self.user)
        self.assertGreater(user_sessions.count(), 0)


class SessionAPITests(TestCase):
    """Test session management API endpoints."""

    def setUp(self):
        """Set up test fixtures."""
        self.user = People.objects.create_user(
            loginid='testuser',
            password='testpass123',
            peoplename='Test User'
        )

        self.client.force_login(self.user)

        # Create session
        session = Session.objects.create(
            session_key=self.client.session.session_key or 'test_key',
            expire_date=timezone.now() + timedelta(hours=2)
        )

        self.user_session = UserSession.objects.create(
            user=self.user,
            session=session,
            device_fingerprint='test_fingerprint',
            device_name='Test Device',
            device_type='desktop',
            user_agent='Test Agent',
            browser='Chrome',
            os='Windows',
            ip_address='192.168.1.1',
            expires_at=session.expire_date
        )

    def test_list_sessions_api(self):
        """Test listing sessions via API."""
        response = self.client.get('/api/sessions/')

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'])
        self.assertIn('sessions', data)

    def test_revoke_session_api(self):
        """Test revoking session via API."""
        response = self.client.delete(f'/api/sessions/{self.user_session.id}/')

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'])

    def test_revoke_all_sessions_api(self):
        """Test revoking all sessions via API."""
        response = self.client.post('/api/sessions/revoke-all/')

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data['success'])


class SuspiciousActivityDetectionTests(TestCase):
    """Test suspicious activity detection."""

    def setUp(self):
        """Set up test fixtures."""
        self.user = People.objects.create_user(
            loginid='testuser',
            password='testpass123',
            peoplename='Test User'
        )

    def test_new_device_flagged_as_suspicious(self):
        """Test that login from new device is flagged when there are existing sessions."""
        # Create existing session
        existing_session = Session.objects.create(
            session_key='existing',
            expire_date=timezone.now() + timedelta(hours=2)
        )

        UserSession.objects.create(
            user=self.user,
            session=existing_session,
            device_fingerprint='known_device',
            device_name='Known Device',
            user_agent='Known Agent',
            ip_address='192.168.1.1',
            expires_at=existing_session.expire_date
        )

        # Create new device session
        new_session = Session.objects.create(
            session_key='new',
            expire_date=timezone.now() + timedelta(hours=2)
        )

        new_user_session = UserSession.objects.create(
            user=self.user,
            session=new_session,
            device_fingerprint='new_device',
            device_name='New Device',
            user_agent='New Agent',
            ip_address='10.0.0.1',
            expires_at=new_session.expire_date
        )

        # Check for suspicious activity
        from apps.peoples.signals.session_signals import _check_suspicious_activity
        _check_suspicious_activity(new_user_session, self.user)

        new_user_session.refresh_from_db()
        self.assertTrue(new_user_session.is_suspicious)

    def test_multiple_simultaneous_sessions_flagged(self):
        """Test that many simultaneous sessions are flagged."""
        # Create 5 active sessions
        for i in range(5):
            session = Session.objects.create(
                session_key=f'session_{i}',
                expire_date=timezone.now() + timedelta(hours=2)
            )

            UserSession.objects.create(
                user=self.user,
                session=session,
                device_fingerprint=f'device_{i}',
                device_name=f'Device {i}',
                user_agent=f'Agent {i}',
                ip_address='192.168.1.1',
                expires_at=session.expire_date,
                is_current=True
            )

        # Check last session
        last_session = UserSession.objects.filter(user=self.user).last()
        from apps.peoples.signals.session_signals import _check_suspicious_activity
        _check_suspicious_activity(last_session, self.user)

        last_session.refresh_from_db()
        self.assertTrue(last_session.is_suspicious)
        self.assertIn('simultaneous sessions', last_session.suspicious_reason.lower())
