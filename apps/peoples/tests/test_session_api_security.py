"""
Session API Security Tests

Tests for session revocation API endpoints with CSRF protection and rate limiting.

Tests implemented security fixes from November 5, 2025 code review:
- CSRF protection on mutation endpoints
- Rate limiting on session operations
- Permission validation

Compliance:
- Rule #2: CSRF protection on all mutations
- Rule #8: Rate limiting on critical endpoints
"""

import pytest
import json
from django.test import TestCase, Client, override_settings
from django.contrib.auth import get_user_model
from django.urls import reverse
from apps.peoples.models import UserSession, SessionActivityLog
from apps.peoples.services.session_management_service import session_management_service

People = get_user_model()


@pytest.mark.django_db
class TestSessionRevokeCSRFProtection(TestCase):
    """Test CSRF protection on session revocation endpoints."""

    def setUp(self):
        """Set up test client and users."""
        self.client = Client(enforce_csrf_checks=True)
        self.user = People.objects.create_user(
            loginid='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
    def test_session_revoke_requires_csrf_token(self):
        """Test that session revoke endpoint requires CSRF token."""
        # Login user
        self.client.login(loginid='testuser', password='testpass123')
        
        # Create a session to revoke
        session = UserSession.objects.create(
            user=self.user,
            device_name='Test Device',
            device_type='desktop'
        )
        
        # Attempt DELETE without CSRF token
        response = self.client.delete(
            f'/api/sessions/{session.id}/',
            content_type='application/json'
        )
        
        # Should fail with 403 Forbidden
        assert response.status_code == 403
        assert 'CSRF' in str(response.content) or response.status_code == 403
        
        # Verify session was NOT revoked
        session.refresh_from_db()
        assert session.revoked is False
        
    def test_session_revoke_succeeds_with_csrf_token(self):
        """Test that session revoke works with valid CSRF token."""
        # Login user
        self.client.login(loginid='testuser', password='testpass123')
        
        # Get CSRF token
        response = self.client.get('/api/sessions/')
        csrf_token = response.cookies.get('csrftoken')
        
        # Create a session to revoke
        session = UserSession.objects.create(
            user=self.user,
            device_name='Test Device',
            device_type='desktop'
        )
        
        # Attempt DELETE with CSRF token
        response = self.client.delete(
            f'/api/sessions/{session.id}/',
            content_type='application/json',
            HTTP_X_CSRFTOKEN=csrf_token.value if csrf_token else None
        )
        
        # Should succeed (200 or 204)
        assert response.status_code in [200, 204]
        
        # Verify session was revoked
        session.refresh_from_db()
        assert session.revoked is True
        
    def test_session_revoke_all_requires_csrf_token(self):
        """Test that bulk session revoke requires CSRF token."""
        # Login user
        self.client.login(loginid='testuser', password='testpass123')
        
        # Create multiple sessions
        UserSession.objects.create(user=self.user, device_name='Device 1', device_type='mobile')
        UserSession.objects.create(user=self.user, device_name='Device 2', device_type='tablet')
        
        # Attempt POST without CSRF token
        response = self.client.post(
            '/api/sessions/revoke-all/',
            content_type='application/json'
        )
        
        # Should fail with 403 Forbidden
        assert response.status_code == 403
        
        # Verify sessions were NOT revoked
        active_count = UserSession.objects.filter(user=self.user, revoked=False).count()
        assert active_count == 2
        
    def test_session_revoke_all_succeeds_with_csrf_token(self):
        """Test that bulk session revoke works with valid CSRF token."""
        # Login user
        self.client.login(loginid='testuser', password='testpass123')
        
        # Get CSRF token
        response = self.client.get('/api/sessions/')
        csrf_token = response.cookies.get('csrftoken')
        
        # Create multiple sessions
        UserSession.objects.create(user=self.user, device_name='Device 1', device_type='mobile')
        UserSession.objects.create(user=self.user, device_name='Device 2', device_type='tablet')
        
        # Attempt POST with CSRF token
        response = self.client.post(
            '/api/sessions/revoke-all/',
            content_type='application/json',
            HTTP_X_CSRFTOKEN=csrf_token.value if csrf_token else None
        )
        
        # Should succeed
        assert response.status_code == 200
        
        # Verify sessions were revoked
        active_count = UserSession.objects.filter(user=self.user, revoked=False).count()
        assert active_count == 0


@pytest.mark.django_db
class TestSessionRevokeRateLimiting(TestCase):
    """Test rate limiting on session revocation endpoints."""

    def setUp(self):
        """Set up test client and users."""
        self.client = Client()
        self.user = People.objects.create_user(
            loginid='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.client.login(loginid='testuser', password='testpass123')
        
    @override_settings(RATE_LIMIT_ENABLED=True)
    def test_session_revoke_rate_limit_enforced(self):
        """Test that session revoke has rate limiting (30/5min)."""
        # Get CSRF token
        response = self.client.get('/api/sessions/')
        csrf_token = response.cookies.get('csrftoken')
        
        # Create sessions to revoke
        sessions = [
            UserSession.objects.create(
                user=self.user,
                device_name=f'Device {i}',
                device_type='mobile'
            )
            for i in range(35)  # More than rate limit
        ]
        
        success_count = 0
        rate_limited_count = 0
        
        # Attempt to revoke 35 sessions (limit is 30)
        for session in sessions:
            response = self.client.delete(
                f'/api/sessions/{session.id}/',
                content_type='application/json',
                HTTP_X_CSRFTOKEN=csrf_token.value if csrf_token else None
            )
            
            if response.status_code in [200, 204]:
                success_count += 1
            elif response.status_code == 429:  # Too Many Requests
                rate_limited_count += 1
        
        # Should hit rate limit after 30 requests
        assert success_count <= 30
        assert rate_limited_count >= 5
        
    @override_settings(RATE_LIMIT_ENABLED=True)
    def test_session_revoke_all_rate_limit_enforced(self):
        """Test that bulk revoke has stricter rate limiting (10/5min)."""
        # Get CSRF token
        response = self.client.get('/api/sessions/')
        csrf_token = response.cookies.get('csrftoken')
        
        success_count = 0
        rate_limited_count = 0
        
        # Attempt to call revoke-all 15 times (limit is 10)
        for i in range(15):
            response = self.client.post(
                '/api/sessions/revoke-all/',
                content_type='application/json',
                HTTP_X_CSRFTOKEN=csrf_token.value if csrf_token else None
            )
            
            if response.status_code == 200:
                success_count += 1
            elif response.status_code == 429:
                rate_limited_count += 1
        
        # Should hit rate limit after 10 requests
        assert success_count <= 10
        assert rate_limited_count >= 5


@pytest.mark.django_db
class TestSessionRevocationPermissions(TestCase):
    """Test permission validation in session revocation."""

    def setUp(self):
        """Set up test users and sessions."""
        self.client = Client()
        self.user1 = People.objects.create_user(
            loginid='user1',
            email='user1@example.com',
            password='pass123'
        )
        self.user2 = People.objects.create_user(
            loginid='user2',
            email='user2@example.com',
            password='pass123'
        )
        
    def test_user_cannot_revoke_other_users_session(self):
        """Test that users can only revoke their own sessions."""
        # Create session for user2
        session = UserSession.objects.create(
            user=self.user2,
            device_name='User2 Device',
            device_type='mobile'
        )
        
        # Login as user1
        self.client.login(loginid='user1', password='pass123')
        
        # Get CSRF token
        response = self.client.get('/api/sessions/')
        csrf_token = response.cookies.get('csrftoken')
        
        # Attempt to revoke user2's session as user1
        response = self.client.delete(
            f'/api/sessions/{session.id}/',
            HTTP_X_CSRFTOKEN=csrf_token.value if csrf_token else None
        )
        
        # Should fail (403 or 400)
        assert response.status_code in [400, 403]
        
        # Verify session was NOT revoked
        session.refresh_from_db()
        assert session.revoked is False


__all__ = [
    'TestSessionRevokeCSRFProtection',
    'TestSessionRevokeRateLimiting',
    'TestSessionRevocationPermissions',
]
