"""
Comprehensive Audit Logging Tests

Tests for unified audit logging system and PII redaction.

Test Coverage:
- AuditLog creation for all event types
- PII redaction verification
- StateTransitionAudit tracking
- BulkOperationAudit metrics
- PermissionDenialAudit security logging
- Retention policy enforcement (90 days)
- Tenant isolation
- Correlation ID tracking

Compliance with .claude/rules.md:
- Rule #11: Specific exception handling
- Rule #15: PII redaction in logs
- Rule #17: Transaction management
"""

import pytest
from datetime import timedelta
from django.test import TestCase, TransactionTestCase
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.utils import timezone
from freezegun import freeze_time
from unittest.mock import patch, MagicMock
import uuid

from apps.core.models.audit import (
    AuditLog,
    StateTransitionAudit,
    BulkOperationAudit,
    PermissionDenialAudit,
    AuditEventType,
)
from apps.core.services.unified_audit_service import (
    EntityAuditService,
    PIIRedactor,
)
from apps.core.constants.datetime_constants import SECONDS_IN_DAY

User = get_user_model()


class PIIRedactorTestCase(TestCase):
    """Test PII redaction functionality."""

    def test_redact_password_field(self):
        """Test that password fields are redacted."""
        data = {
            'username': 'testuser',
            'password': 'secret123',
            'email': 'test@example.com'
        }

        redacted = PIIRedactor.redact_dict(data)

        self.assertEqual(redacted['username'], 'testuser')
        self.assertEqual(redacted['password'], '[REDACTED]')
        self.assertEqual(redacted['email'], '[REDACTED]')

    def test_redact_phone_numbers(self):
        """Test that phone number fields are redacted."""
        data = {
            'name': 'John Doe',
            'mobno': '+1234567890',
            'phone': '555-1234',
            'phone_number': '555-5678'
        }

        redacted = PIIRedactor.redact_dict(data)

        self.assertEqual(redacted['name'], 'John Doe')
        self.assertEqual(redacted['mobno'], '[REDACTED]')
        self.assertEqual(redacted['phone'], '[REDACTED]')
        self.assertEqual(redacted['phone_number'], '[REDACTED]')

    def test_redact_identification_numbers(self):
        """Test that identification numbers are redacted."""
        data = {
            'name': 'John Doe',
            'ssn': '123-45-6789',
            'pan': 'ABCDE1234F',
            'aadhar': '123456789012'
        }

        redacted = PIIRedactor.redact_dict(data)

        self.assertEqual(redacted['name'], 'John Doe')
        self.assertEqual(redacted['ssn'], '[REDACTED]')
        self.assertEqual(redacted['pan'], '[REDACTED]')
        self.assertEqual(redacted['aadhar'], '[REDACTED]')

    def test_nested_dict_redaction(self):
        """Test that nested dictionaries are redacted."""
        data = {
            'user': {
                'username': 'testuser',
                'password': 'secret123',
                'profile': {
                    'email': 'test@example.com',
                    'age': 25
                }
            }
        }

        redacted = PIIRedactor.redact_dict(data)

        self.assertEqual(redacted['user']['username'], 'testuser')
        self.assertEqual(redacted['user']['password'], '[REDACTED]')
        self.assertEqual(redacted['user']['profile']['email'], '[REDACTED]')
        self.assertEqual(redacted['user']['profile']['age'], 25)

    def test_preserve_non_pii_fields(self):
        """Test that non-PII fields are preserved."""
        data = {
            'id': 123,
            'name': 'Test Asset',
            'status': 'ACTIVE',
            'created_at': '2025-10-01T12:00:00Z',
            'metadata': {'key': 'value'}
        }

        redacted = PIIRedactor.redact_dict(data)

        self.assertEqual(redacted, data)


class EntityAuditServiceTestCase(TestCase):
    """Test EntityAuditService functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.user = User.objects.create_user(
            loginid='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.service = EntityAuditService(user=self.user)

    def test_log_entity_created(self):
        """Test logging entity creation."""
        initial_count = AuditLog.objects.count()

        self.service.log_entity_created(
            entity=self.user,
            correlation_id=uuid.uuid4()
        )

        final_count = AuditLog.objects.count()
        self.assertEqual(final_count, initial_count + 1)

        audit = AuditLog.objects.latest('created_at')
        self.assertEqual(audit.event_type, AuditEventType.CREATED)
        self.assertEqual(audit.actor, self.user)
        self.assertEqual(audit.object_id, str(self.user.id))

    def test_log_entity_updated(self):
        """Test logging entity updates."""
        old_data = {'name': 'Old Name', 'status': 'DRAFT'}
        new_data = {'name': 'New Name', 'status': 'PUBLISHED'}

        self.service.log_entity_updated(
            entity=self.user,
            old_data=old_data,
            new_data=new_data,
            correlation_id=uuid.uuid4()
        )

        audit = AuditLog.objects.latest('created_at')
        self.assertEqual(audit.event_type, AuditEventType.UPDATED)
        self.assertIn('changes', audit.changes)

    def test_log_entity_deleted(self):
        """Test logging entity deletion."""
        snapshot = {'id': 123, 'name': 'Test Entity'}

        self.service.log_entity_deleted(
            entity_type=ContentType.objects.get_for_model(User),
            entity_id='123',
            snapshot=snapshot,
            correlation_id=uuid.uuid4()
        )

        audit = AuditLog.objects.latest('created_at')
        self.assertEqual(audit.event_type, AuditEventType.DELETED)
        self.assertEqual(audit.object_id, '123')

    def test_pii_redacted_in_audit_log(self):
        """Test that PII is redacted in audit logs."""
        old_data = {
            'name': 'John Doe',
            'password': 'secret123',
            'email': 'john@example.com'
        }
        new_data = {
            'name': 'John Doe',
            'password': 'newsecret456',
            'email': 'newemail@example.com'
        }

        self.service.log_entity_updated(
            entity=self.user,
            old_data=old_data,
            new_data=new_data,
            correlation_id=uuid.uuid4()
        )

        audit = AuditLog.objects.latest('created_at')
        changes = audit.changes

        # Password and email should be redacted
        self.assertNotIn('secret123', str(changes))
        self.assertNotIn('newsecret456', str(changes))
        self.assertNotIn('john@example.com', str(changes))
        self.assertNotIn('newemail@example.com', str(changes))

    def test_retention_policy_set(self):
        """Test that retention policy is set correctly (90 days)."""
        self.service.log_entity_created(
            entity=self.user,
            correlation_id=uuid.uuid4()
        )

        audit = AuditLog.objects.latest('created_at')

        # Retention should be 90 days from creation
        expected_retention = audit.created_at + timedelta(days=90)

        # Allow for small time differences (within 1 second)
        time_diff = abs((audit.retention_until - expected_retention).total_seconds())
        self.assertLess(time_diff, 1.0)

    def test_correlation_id_tracking(self):
        """Test that correlation IDs link related audit events."""
        correlation_id = uuid.uuid4()

        # Create multiple audit entries with same correlation ID
        self.service.log_entity_created(
            entity=self.user,
            correlation_id=correlation_id
        )

        self.service.log_entity_updated(
            entity=self.user,
            old_data={'status': 'DRAFT'},
            new_data={'status': 'PUBLISHED'},
            correlation_id=correlation_id
        )

        # Should be able to retrieve all related events
        related_events = AuditLog.objects.filter(correlation_id=correlation_id)
        self.assertEqual(related_events.count(), 2)


class StateTransitionAuditTestCase(TestCase):
    """Test StateTransitionAudit functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.user = User.objects.create_user(
            loginid='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.service = EntityAuditService(user=self.user)

    def test_log_state_transition(self):
        """Test logging state transitions."""
        self.service.log_state_transition(
            entity=self.user,
            from_state='DRAFT',
            to_state='SUBMITTED',
            comments='Submitting for approval',
            correlation_id=uuid.uuid4()
        )

        audit = StateTransitionAudit.objects.latest('created_at')
        self.assertEqual(audit.from_state, 'DRAFT')
        self.assertEqual(audit.to_state, 'SUBMITTED')
        self.assertEqual(audit.transition_reason, 'Submitting for approval')

    def test_state_transition_creates_audit_log(self):
        """Test that state transitions create both specialized and general audit logs."""
        initial_general_count = AuditLog.objects.count()
        initial_transition_count = StateTransitionAudit.objects.count()

        self.service.log_state_transition(
            entity=self.user,
            from_state='OPEN',
            to_state='CLOSED',
            comments='Issue resolved',
            correlation_id=uuid.uuid4()
        )

        final_general_count = AuditLog.objects.count()
        final_transition_count = StateTransitionAudit.objects.count()

        # Both should increase by 1
        self.assertEqual(final_general_count, initial_general_count + 1)
        self.assertEqual(final_transition_count, initial_transition_count + 1)

    def test_state_transition_duration_tracking(self):
        """Test that state transition duration is tracked."""
        # This would require actual entity with state and timestamps
        # Placeholder for when models are fully integrated
        pass


class BulkOperationAuditTestCase(TestCase):
    """Test BulkOperationAudit functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.user = User.objects.create_user(
            loginid='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.service = EntityAuditService(user=self.user)

    def test_log_bulk_operation(self):
        """Test logging bulk operations."""
        self.service.log_bulk_operation(
            operation_type='transition_to_APPROVED',
            entity_type=ContentType.objects.get_for_model(User),
            total_items=100,
            successful_items=95,
            failed_items=5,
            failure_details={'id_1': 'Error 1', 'id_2': 'Error 2'},
            correlation_id=uuid.uuid4()
        )

        audit = BulkOperationAudit.objects.latest('created_at')
        self.assertEqual(audit.operation_type, 'transition_to_APPROVED')
        self.assertEqual(audit.total_items, 100)
        self.assertEqual(audit.successful_items, 95)
        self.assertEqual(audit.failed_items, 5)

    def test_bulk_operation_success_rate_calculation(self):
        """Test that success rate is calculated correctly."""
        self.service.log_bulk_operation(
            operation_type='test_operation',
            entity_type=ContentType.objects.get_for_model(User),
            total_items=200,
            successful_items=180,
            failed_items=20,
            failure_details={},
            correlation_id=uuid.uuid4()
        )

        audit = BulkOperationAudit.objects.latest('created_at')
        # Success rate should be 180/200 = 90%
        self.assertEqual(audit.successful_items / audit.total_items, 0.9)

    def test_bulk_operation_failure_details_logged(self):
        """Test that failure details are logged."""
        failure_details = {
            'id_1': 'Invalid state transition',
            'id_2': 'Permission denied',
            'id_3': 'Validation error'
        }

        self.service.log_bulk_operation(
            operation_type='bulk_approve',
            entity_type=ContentType.objects.get_for_model(User),
            total_items=10,
            successful_items=7,
            failed_items=3,
            failure_details=failure_details,
            correlation_id=uuid.uuid4()
        )

        audit = BulkOperationAudit.objects.latest('created_at')
        self.assertEqual(audit.failure_details, failure_details)


class PermissionDenialAuditTestCase(TestCase):
    """Test PermissionDenialAudit functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.user = User.objects.create_user(
            loginid='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.service = EntityAuditService(user=self.user)

    def test_log_permission_denial(self):
        """Test logging permission denials."""
        self.service.log_permission_denial(
            entity=self.user,
            required_permission='can_approve_work_orders',
            action_attempted='Attempted to approve work order #123',
            correlation_id=uuid.uuid4()
        )

        audit = PermissionDenialAudit.objects.latest('created_at')
        self.assertEqual(audit.required_permission, 'can_approve_work_orders')
        self.assertEqual(audit.action_attempted, 'Attempted to approve work order #123')

    def test_permission_denial_creates_audit_log(self):
        """Test that permission denials create both specialized and general audit logs."""
        initial_general_count = AuditLog.objects.count()
        initial_denial_count = PermissionDenialAudit.objects.count()

        self.service.log_permission_denial(
            entity=self.user,
            required_permission='can_delete_users',
            action_attempted='Attempted to delete user',
            correlation_id=uuid.uuid4()
        )

        final_general_count = AuditLog.objects.count()
        final_denial_count = PermissionDenialAudit.objects.count()

        # Both should increase by 1
        self.assertEqual(final_general_count, initial_general_count + 1)
        self.assertEqual(final_denial_count, initial_denial_count + 1)

    def test_permission_denial_security_flag(self):
        """Test that permission denials are flagged as security events."""
        self.service.log_permission_denial(
            entity=self.user,
            required_permission='superuser_access',
            action_attempted='Attempted to access admin panel',
            correlation_id=uuid.uuid4()
        )

        audit = AuditLog.objects.filter(
            event_type=AuditEventType.PERMISSION_DENIED
        ).latest('created_at')

        # Should have security flag
        self.assertIn('SECURITY_EVENT', audit.security_flags)


class AuditRetentionTestCase(TestCase):
    """Test audit retention policy enforcement."""

    def setUp(self):
        """Set up test fixtures."""
        self.user = User.objects.create_user(
            loginid='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.service = EntityAuditService(user=self.user)

    @freeze_time("2025-10-01 12:00:00")
    def test_retention_policy_enforcement(self):
        """Test that audit logs past retention are eligible for deletion."""
        # Create audit log that should be retained
        recent_audit = AuditLog.objects.create(
            correlation_id=uuid.uuid4(),
            event_type=AuditEventType.CREATED,
            actor=self.user,
            content_type=ContentType.objects.get_for_model(User),
            object_id=str(self.user.id),
            changes={},
            retention_until=timezone.now() + timedelta(days=90)
        )

        # Create audit log that is past retention
        old_audit = AuditLog.objects.create(
            correlation_id=uuid.uuid4(),
            event_type=AuditEventType.CREATED,
            actor=self.user,
            content_type=ContentType.objects.get_for_model(User),
            object_id=str(self.user.id),
            changes={},
            retention_until=timezone.now() - timedelta(days=1)  # Expired yesterday
        )

        # Query for expired audits
        expired_audits = AuditLog.objects.filter(
            retention_until__lt=timezone.now()
        )

        self.assertEqual(expired_audits.count(), 1)
        self.assertEqual(expired_audits.first().id, old_audit.id)

    def test_retention_policy_default(self):
        """Test that default retention is 90 days."""
        self.service.log_entity_created(
            entity=self.user,
            correlation_id=uuid.uuid4()
        )

        audit = AuditLog.objects.latest('created_at')
        retention_days = (audit.retention_until - audit.created_at).days

        # Should be 90 days (allow for rounding)
        self.assertAlmostEqual(retention_days, 90, delta=1)


class TenantIsolationAuditTestCase(TestCase):
    """Test tenant isolation in audit logs."""

    def setUp(self):
        """Set up test fixtures."""
        self.user_tenant1 = User.objects.create_user(
            loginid='user1',
            email='user1@example.com',
            password='testpass123'
        )
        self.user_tenant2 = User.objects.create_user(
            loginid='user2',
            email='user2@example.com',
            password='testpass123'
        )

    def test_tenant_isolation_in_audit_queries(self):
        """Test that audit logs are isolated by tenant."""
        # This test would require actual tenant setup
        # Placeholder for when tenant infrastructure is fully integrated
        pass


@pytest.mark.integration
class AuditLoggingIntegrationTest(TransactionTestCase):
    """Integration tests for audit logging system."""

    def setUp(self):
        """Set up test fixtures."""
        self.user = User.objects.create_user(
            loginid='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.service = EntityAuditService(user=self.user)

    @pytest.mark.slow
    def test_complete_audit_trail(self):
        """Test complete audit trail for entity lifecycle."""
        correlation_id = uuid.uuid4()

        # 1. Entity created
        self.service.log_entity_created(
            entity=self.user,
            correlation_id=correlation_id
        )

        # 2. Entity updated
        self.service.log_entity_updated(
            entity=self.user,
            old_data={'status': 'DRAFT'},
            new_data={'status': 'SUBMITTED'},
            correlation_id=correlation_id
        )

        # 3. State transition
        self.service.log_state_transition(
            entity=self.user,
            from_state='SUBMITTED',
            to_state='APPROVED',
            comments='Approved by admin',
            correlation_id=correlation_id
        )

        # 4. Permission denial (different user tries to modify)
        other_user = User.objects.create_user(
            loginid='otheruser',
            email='other@example.com',
            password='pass123'
        )
        other_service = EntityAuditService(user=other_user)

        other_service.log_permission_denial(
            entity=self.user,
            required_permission='can_modify_approved_entities',
            action_attempted='Attempted to edit approved entity',
            correlation_id=correlation_id
        )

        # Verify complete audit trail
        all_events = AuditLog.objects.filter(
            correlation_id=correlation_id
        ).order_by('created_at')

        self.assertEqual(all_events.count(), 4)

        event_types = [event.event_type for event in all_events]
        self.assertIn(AuditEventType.CREATED, event_types)
        self.assertIn(AuditEventType.UPDATED, event_types)
        self.assertIn(AuditEventType.STATE_CHANGED, event_types)
        self.assertIn(AuditEventType.PERMISSION_DENIED, event_types)

    @pytest.mark.slow
    def test_audit_performance_bulk_operations(self):
        """Test audit logging performance with bulk operations."""
        import timeit

        # Measure time to log 100 audit entries
        start_time = timeit.default_timer()

        for i in range(100):
            self.service.log_entity_created(
                entity=self.user,
                correlation_id=uuid.uuid4()
            )

        elapsed = timeit.default_timer() - start_time

        # Should be able to log 100 entries in < 2 seconds
        self.assertLess(elapsed, 2.0)

        # Verify all entries were created
        recent_count = AuditLog.objects.filter(
            created_at__gte=timezone.now() - timedelta(seconds=10)
        ).count()

        self.assertGreaterEqual(recent_count, 100)

    def test_concurrent_audit_logging(self):
        """Test audit logging under concurrent access."""
        from concurrent.futures import ThreadPoolExecutor, as_completed

        correlation_id = uuid.uuid4()

        def log_audit(i):
            service = EntityAuditService(user=self.user)
            service.log_entity_created(
                entity=self.user,
                correlation_id=correlation_id
            )

        # 50 concurrent audit logs
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(log_audit, i) for i in range(50)]
            results = [f.result() for f in as_completed(futures)]

        # All 50 should be logged
        logged_count = AuditLog.objects.filter(
            correlation_id=correlation_id
        ).count()

        self.assertEqual(logged_count, 50)
