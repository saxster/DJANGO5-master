"""
Session Transaction Atomicity Tests

Tests for transaction.atomic wrapping in session revocation operations.

Tests implemented security fixes from November 5, 2025 code review:
- Atomic session revocation + audit log creation
- Rollback on errors (no partial writes)
- Multi-tenant database routing

Compliance:
- Rule #17: Mandatory Transaction Management
"""

import pytest
from django.test import TestCase, TransactionTestCase
from django.contrib.auth import get_user_model
from django.db import transaction, IntegrityError
from unittest.mock import patch, Mock
from apps.peoples.models import UserSession, SessionActivityLog
from apps.peoples.services.session_management_service import session_management_service

People = get_user_model()


@pytest.mark.django_db
class TestSessionRevocationAtomicity(TransactionTestCase):
    """Test atomic transaction behavior in session revocation."""

    def setUp(self):
        """Set up test users and sessions."""
        self.user = People.objects.create_user(
            loginid='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
    def test_session_revoke_creates_audit_log_atomically(self):
        """Test that session revoke + audit log happen atomically."""
        # Create session
        session = UserSession.objects.create(
            user=self.user,
            device_name='Test Device',
            device_type='desktop'
        )
        
        # Revoke session
        success, message = session_management_service.revoke_session(
            session_id=session.id,
            revoked_by=self.user,
            reason='test'
        )
        
        assert success is True
        
        # Verify both session revoked AND audit log created
        session.refresh_from_db()
        assert session.revoked is True
        
        audit_logs = SessionActivityLog.objects.filter(session=session)
        assert audit_logs.count() == 1
        assert audit_logs.first().activity_type == 'logout'

    def test_session_revoke_rollback_on_audit_log_failure(self):
        """Test that session revoke rolls back if audit log creation fails."""
        session = UserSession.objects.create(
            user=self.user,
            device_name='Test Device',
            device_type='desktop'
        )
        
        # Mock SessionActivityLog.objects.create to raise an error
        with patch('apps.peoples.models.SessionActivityLog.objects.create') as mock_create:
            mock_create.side_effect = IntegrityError("Test integrity error")
            
            # Attempt to revoke session (should fail)
            try:
                session_management_service.revoke_session(
                    session_id=session.id,
                    revoked_by=self.user,
                    reason='test'
                )
            except IntegrityError:
                pass
            
            # Verify session was NOT revoked (transaction rolled back)
            session.refresh_from_db()
            assert session.revoked is False
            
            # Verify no audit log was created
            assert SessionActivityLog.objects.filter(session=session).count() == 0

    def test_bulk_revoke_all_or_nothing(self):
        """Test that bulk session revoke is atomic (all or nothing)."""
        # Create multiple sessions
        sessions = [
            UserSession.objects.create(
                user=self.user,
                device_name=f'Device {i}',
                device_type='mobile'
            )
            for i in range(3)
        ]
        
        # Revoke all sessions
        count, message = session_management_service.revoke_all_sessions(
            user=self.user,
            except_current=False,
            reason='test_bulk'
        )
        
        assert count == 3
        
        # Verify ALL sessions revoked
        for session in sessions:
            session.refresh_from_db()
            assert session.revoked is True
        
        # Verify ALL audit logs created
        audit_logs = SessionActivityLog.objects.filter(
            session__in=sessions,
            activity_type='logout'
        )
        assert audit_logs.count() == 3

    def test_bulk_revoke_rollback_on_error(self):
        """Test that bulk revoke rolls back entirely on error."""
        # Create multiple sessions
        sessions = [
            UserSession.objects.create(
                user=self.user,
                device_name=f'Device {i}',
                device_type='mobile'
            )
            for i in range(3)
        ]
        
        # Mock the revoke method to fail on second iteration
        original_revoke = UserSession.revoke
        call_count = [0]
        
        def mock_revoke_fail_second(self, *args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 2:
                raise IntegrityError("Test error on second revoke")
            return original_revoke(self, *args, **kwargs)
        
        with patch.object(UserSession, 'revoke', mock_revoke_fail_second):
            try:
                session_management_service.revoke_all_sessions(
                    user=self.user,
                    except_current=False,
                    reason='test_rollback'
                )
            except IntegrityError:
                pass
        
        # Verify NONE of the sessions were revoked (full rollback)
        for session in sessions:
            session.refresh_from_db()
            assert session.revoked is False
        
        # Verify NO audit logs were created
        assert SessionActivityLog.objects.filter(session__in=sessions).count() == 0

    def test_cleanup_expired_sessions_atomic(self):
        """Test that expired session cleanup is atomic."""
        from django.utils import timezone
        from datetime import timedelta
        
        # Create expired session
        session = UserSession.objects.create(
            user=self.user,
            device_name='Expired Device',
            device_type='mobile',
            expires_at=timezone.now() - timedelta(hours=1)
        )
        
        # Run cleanup
        count = session_management_service.cleanup_expired_sessions()
        
        assert count == 1
        
        # Verify session was revoked
        session.refresh_from_db()
        assert session.revoked is True


@pytest.mark.django_db  
class TestMultiTenantDatabaseRouting(TransactionTestCase):
    """Test that transactions use correct database in multi-tenant setup."""

    def setUp(self):
        """Set up test user."""
        self.user = People.objects.create_user(
            loginid='testuser',
            email='test@example.com',
            password='testpass123'
        )

    def test_transaction_uses_current_db_name(self):
        """Test that transaction.atomic uses get_current_db_name()."""
        from apps.core.utils_new.db_utils import get_current_db_name
        
        # Create session
        session = UserSession.objects.create(
            user=self.user,
            device_name='Test Device',
            device_type='desktop'
        )
        
        # Mock get_current_db_name to return 'tenant_db'
        with patch('apps.core.utils_new.db_utils.get_current_db_name') as mock_db:
            mock_db.return_value = 'default'  # Use default for test
            
            # Revoke session
            success, message = session_management_service.revoke_session(
                session_id=session.id,
                revoked_by=self.user,
                reason='test'
            )
            
            # Verify get_current_db_name was called
            assert mock_db.called
            assert success is True


__all__ = [
    'TestSessionRevocationAtomicity',
    'TestMultiTenantDatabaseRouting',
]
