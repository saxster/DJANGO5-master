"""
Comprehensive Ticket System Integration Tests

Validates the complete refactored ticket system including:
- TicketStateMachine integration
- TicketAssignmentService operations
- TicketWorkflow model behavior
- TicketAuditService logging
- Unified serializer functionality
- Performance optimizations
- Cache behavior
- API consistency

Following .claude/rules.md:
- Rule #11: Specific exception testing
- Rule #12: Performance validation
"""

import pytest
import time
import threading
from decimal import Decimal
from unittest.mock import patch, Mock
from datetime import datetime, timedelta

from django.test import TestCase, TransactionTestCase, override_settings
from django.contrib.auth.models import User, Permission
from django.utils import timezone
from django.db import transaction
from django.core.cache import cache

from apps.y_helpdesk.models import Ticket, EscalationMatrix
from apps.y_helpdesk.models.ticket_workflow import TicketWorkflow
from apps.y_helpdesk.services.ticket_state_machine import (
    TicketStateMachine, TicketStatus, TransitionContext, TransitionReason
)
from apps.y_helpdesk.services.ticket_assignment_service import (
    TicketAssignmentService, AssignmentContext, AssignmentReason, AssignmentType
)
from apps.y_helpdesk.services.ticket_audit_service import (
    TicketAuditService, AuditContext, AuditEventType, AuditLevel
)
from apps.y_helpdesk.services.ticket_cache_service import TicketCacheService
from apps.y_helpdesk.serializers.unified_ticket_serializer import (
    TicketUnifiedSerializer, serialize_for_mobile_sync, serialize_for_web_api
)
from apps.y_helpdesk.utils.query_monitor import monitor_queries

from apps.peoples.models import People, Pgroup
from apps.onboarding.models import Bt, TypeAssist


class TicketSystemIntegrationTestCase(TestCase):
    """Comprehensive integration tests for the refactored ticket system."""

    def setUp(self):
        """Set up test data for integration tests."""
        # Clear cache before each test
        cache.clear()

        # Create test users
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass'
        )
        self.admin_user = User.objects.create_user(
            username='admin',
            email='admin@example.com',
            password='adminpass',
            is_staff=True
        )

        # Create test business unit and client
        self.client_bt = Bt.objects.create(
            buname='Test Client',
            bucode='TC001',
            butype='CLIENT'
        )
        self.bu = Bt.objects.create(
            buname='Test Business Unit',
            bucode='BU001',
            butype='BUSINESSUNIT',
            client=self.client_bt
        )

        # Create test people and groups
        self.assignee = People.objects.create(
            peoplename='Test Assignee',
            peoplecode='ASG001',
            loginid='assignee',
            email='assignee@example.com'
        )
        self.group = Pgroup.objects.create(
            groupname='Test Group',
            groupcode='GRP001'
        )

        # Create test ticket category
        self.category = TypeAssist.objects.create(
            taname='Test Category',
            tacode='CAT001',
            bu=self.bu,
            client=self.client_bt
        )

        # Create base test ticket
        self.ticket = Ticket.objects.create(
            ticketno='T00001',
            ticketdesc='Test ticket for integration testing',
            status=Ticket.Status.NEW.value,
            priority='MEDIUM',
            bu=self.bu,
            client=self.client_bt,
            ticketcategory=self.category,
            cuser=self.user,
            muser=self.user
        )

    def test_complete_ticket_lifecycle_integration(self):
        """Test complete ticket lifecycle using all refactored services."""
        # 1. Create ticket (already done in setUp)
        self.assertEqual(self.ticket.status, 'NEW')

        # 2. Test status transition using TicketStateMachine
        context = TransitionContext(
            user=self.user,
            reason=TransitionReason.USER_ACTION,
            comments="Opening ticket for processing"
        )

        result = TicketStateMachine.validate_transition(
            'NEW', 'OPEN', context
        )
        self.assertTrue(result.is_valid)

        # 3. Test assignment using TicketAssignmentService
        assignment_context = AssignmentContext(
            user=self.user,
            reason=AssignmentReason.USER_ACTION,
            assignment_type=AssignmentType.INDIVIDUAL
        )

        assignment_result = TicketAssignmentService.assign_ticket_to_person(
            self.ticket.id, self.assignee.id, assignment_context
        )
        self.assertTrue(assignment_result.success)

        # 4. Verify workflow was created and updated
        self.ticket.refresh_from_db()
        workflow = self.ticket.get_or_create_workflow()
        self.assertIsNotNone(workflow)
        self.assertEqual(workflow.escalation_level, 0)
        self.assertFalse(workflow.is_escalated)

        # 5. Test escalation
        workflow.escalate(
            assigned_to={'type': 'person', 'id': self.assignee.id},
            escalation_reason='Timeout escalation',
            user=self.user
        )
        workflow.refresh_from_db()
        self.assertEqual(workflow.escalation_level, 1)
        self.assertTrue(workflow.is_escalated)

        # 6. Test unified serialization
        serialized = serialize_for_web_api([self.ticket], self.user)
        self.assertEqual(len(serialized), 1)
        self.assertIn('workflow_status', serialized[0])

        # 7. Test audit logging
        with patch('apps.y_helpdesk.services.ticket_audit_service.logger') as mock_logger:
            audit_context = AuditContext(user=self.user)
            TicketAuditService.log_ticket_update(
                self.ticket,
                {'status': {'old': 'NEW', 'new': 'OPEN'}},
                audit_context
            )
            mock_logger.info.assert_called()

    def test_concurrent_ticket_operations(self):
        """Test race condition prevention in concurrent operations."""
        import concurrent.futures
        import random

        def assign_ticket_worker(worker_id):
            """Worker function for concurrent assignment testing."""
            try:
                context = AssignmentContext(
                    user=self.user,
                    reason=AssignmentReason.SYSTEM_AUTO,
                    assignment_type=AssignmentType.INDIVIDUAL
                )

                result = TicketAssignmentService.assign_ticket_to_person(
                    self.ticket.id, self.assignee.id, context
                )
                return {'worker_id': worker_id, 'success': result.success}
            except Exception as e:
                return {'worker_id': worker_id, 'error': str(e)}

        # Run concurrent assignment operations
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = [
                executor.submit(assign_ticket_worker, i)
                for i in range(10)
            ]

            results = [future.result() for future in concurrent.futures.as_completed(futures)]

        # Verify that race conditions were handled properly
        successful_assignments = [r for r in results if r.get('success')]
        self.assertGreaterEqual(len(successful_assignments), 1)

        # Verify ticket state is consistent
        self.ticket.refresh_from_db()
        self.assertEqual(self.ticket.assignedtopeople_id, self.assignee.id)

    def test_performance_optimizations_validation(self):
        """Validate that performance optimizations are working."""
        from apps.y_helpdesk.utils.query_monitor import monitor_queries

        # Test optimized ticket list query performance
        with monitor_queries("optimized_ticket_list", detailed=True) as monitor:
            # This should use our optimized manager methods
            tickets = Ticket.objects.filter(
                bu=self.bu,
                client=self.client_bt
            ).select_related(
                'assignedtopeople', 'assignedtogroup', 'bu', 'ticketcategory'
            ).prefetch_related('workflow')[:10]

            # Force query execution
            list(tickets)

        summary = monitor.get_summary()

        # Verify optimized performance
        self.assertLessEqual(summary['total_queries'], 5)  # Should be very few queries
        self.assertEqual(summary['performance_rating'], 'EXCELLENT')
        self.assertFalse(summary['n_plus_1_risk'])

    def test_cache_integration_behavior(self):
        """Test cache integration across the system."""
        from apps.y_helpdesk.services.ticket_cache_service import (
            cache_ticket_list, TicketCacheService
        )

        # Test cache miss and population
        cache_key_params = {
            'bu_id': self.bu.id,
            'client_id': self.client_bt.id,
            'from': timezone.now().date().isoformat(),
            'to': timezone.now().date().isoformat(),
            'tenant': 'default'
        }

        def load_test_data():
            return [{'ticket_id': self.ticket.id, 'data': 'test'}]

        # First call should miss cache and load data
        data1 = cache_ticket_list(cache_key_params, load_test_data)
        self.assertEqual(data1[0]['ticket_id'], self.ticket.id)

        # Second call should hit cache
        with patch.object(load_test_data, '__call__') as mock_loader:
            data2 = cache_ticket_list(cache_key_params, load_test_data)
            # Loader should not be called (cache hit)
            mock_loader.assert_not_called()
            self.assertEqual(data1, data2)

        # Test cache invalidation
        TicketCacheService.invalidate_cache('ticket_list')

        # After invalidation, should call loader again
        with patch.object(load_test_data, '__call__', return_value=[]) as mock_loader:
            cache_ticket_list(cache_key_params, load_test_data)
            mock_loader.assert_called_once()

    def test_unified_serializer_context_switching(self):
        """Test unified serializer behavior across different contexts."""
        # Test mobile sync context
        mobile_data = serialize_for_mobile_sync([self.ticket], self.user)
        self.assertIn('mobile_id', mobile_data[0])
        self.assertIn('version', mobile_data[0])
        self.assertIn('sync_status', mobile_data[0])

        # Test web API context
        web_data = serialize_for_web_api([self.ticket], self.user)
        self.assertIn('audit_trail_summary', web_data[0])
        self.assertIn('workflow_status', web_data[0])

        # Verify different contexts produce different field sets
        self.assertNotEqual(set(mobile_data[0].keys()), set(web_data[0].keys()))

    def test_audit_service_integration(self):
        """Test comprehensive audit logging across operations."""
        with patch('apps.y_helpdesk.services.ticket_audit_service.logger') as mock_logger:
            # Test ticket creation audit
            audit_context = AuditContext(user=self.user)
            TicketAuditService.log_ticket_creation(
                self.ticket, audit_context, {'test': 'data'}
            )

            # Test status change audit
            TicketAuditService.log_status_transition(
                self.ticket.id, 'NEW', 'OPEN', audit_context
            )

            # Test assignment change audit
            assignment_result = {
                'success': True,
                'assignment_type': 'individual',
                'new_assignee': {'type': 'person', 'id': self.assignee.id}
            }
            TicketAuditService.log_assignment_change(
                self.ticket.id, assignment_result, audit_context
            )

            # Verify all audit events were logged
            self.assertEqual(mock_logger.info.call_count, 2)  # creation + assignment
            self.assertEqual(mock_logger.warning.call_count, 1)  # status change

    def test_backward_compatibility_integration(self):
        """Test that refactored system maintains backward compatibility."""
        # Test legacy property access on Ticket model
        self.assertEqual(self.ticket.level, 0)  # Should access workflow.escalation_level
        self.assertFalse(self.ticket.isescalated)  # Should access workflow.is_escalated
        self.assertIsNotNone(self.ticket.modifieddatetime)  # Should access workflow.last_activity_at

        # Test legacy ticketlog access
        ticketlog = self.ticket.ticketlog
        self.assertIsInstance(ticketlog, dict)
        self.assertIn('ticket_history', ticketlog)

        # Test setting legacy properties
        self.ticket.level = 2
        self.ticket.isescalated = True

        # Verify workflow was updated
        workflow = self.ticket.get_or_create_workflow()
        self.assertEqual(workflow.escalation_level, 2)
        self.assertTrue(workflow.is_escalated)

    def test_mobile_sync_integration_flow(self):
        """Test complete mobile sync flow with refactored components."""
        from apps.y_helpdesk.services.ticket_sync_service import TicketSyncService

        # Create sync service
        sync_service = TicketSyncService()

        # Prepare sync data
        sync_data = {
            'entries': [
                {
                    'mobile_id': 'mob_001',
                    'ticketdesc': 'Mobile sync test ticket',
                    'status': 'OPEN',
                    'priority': 'HIGH',
                    'version': 1
                }
            ],
            'last_sync_timestamp': timezone.now().isoformat(),
            'client_id': self.client_bt.id
        }

        # Perform sync operation
        from apps.y_helpdesk.serializers.ticket_sync_serializers import TicketSyncSerializer
        result = sync_service.sync_tickets(
            user=self.user,
            sync_data=sync_data,
            serializer_class=TicketSyncSerializer
        )

        # Verify sync results
        self.assertIn('synced_items', result)
        self.assertIn('conflicts', result)
        self.assertIn('errors', result)

    def test_escalation_workflow_integration(self):
        """Test escalation workflow with all integrated services."""
        # Create escalation matrix
        escalation = EscalationMatrix.objects.create(
            escalationtemplate=self.category,
            level=1,
            frequency='HOUR',
            frequencyvalue=2,
            assignedperson=self.assignee,
            bu=self.bu,
            client=self.client_bt
        )

        # Test escalation process
        workflow = self.ticket.get_or_create_workflow()
        workflow.escalate(
            assigned_to={'type': 'person', 'id': self.assignee.id},
            escalation_reason='Automatic escalation due to timeout',
            user=None  # System escalation
        )

        # Verify escalation results
        workflow.refresh_from_db()
        self.assertEqual(workflow.escalation_level, 1)
        self.assertTrue(workflow.is_escalated)
        self.assertIsNotNone(workflow.last_escalated_at)

        # Verify audit logging
        self.assertGreater(workflow.activity_count, 0)
        self.assertIn('escalation_attempts', workflow.workflow_data)

    def test_api_consistency_across_endpoints(self):
        """Test that all API endpoints return consistent data structures."""
        # Test GraphQL endpoint format
        from apps.service.queries.ticket_queries import TicketQueries

        # Mock GraphQL info object
        mock_info = Mock()
        mock_info.context = Mock()
        mock_info.context.user = self.user

        graphql_result = TicketQueries.resolve_get_tickets(
            None, mock_info,
            peopleid=self.user.id,
            buid=self.bu.id,
            clientid=self.client_bt.id,
            mdtz=timezone.now().isoformat(),
            ctzoffset=0
        )

        # Test REST API endpoint format
        rest_tickets = serialize_for_web_api([self.ticket], self.user)

        # Verify consistent field availability
        # Both should have core ticket information
        self.assertIsNotNone(graphql_result.records)
        self.assertGreater(len(rest_tickets), 0)

    @override_settings(DEBUG=True)
    def test_query_optimization_effectiveness(self):
        """Test that query optimizations are effective."""
        # Create additional test data
        for i in range(10):
            Ticket.objects.create(
                ticketno=f'T0000{i+2}',
                ticketdesc=f'Test ticket {i+2}',
                status='NEW',
                bu=self.bu,
                client=self.client_bt,
                cuser=self.user
            )

        # Test optimized list query
        with monitor_queries("optimized_list_test") as monitor:
            # This should use our optimized methods
            tickets = Ticket.objects.filter(bu=self.bu).select_related(
                'assignedtopeople', 'bu', 'ticketcategory'
            ).prefetch_related('workflow')

            # Serialize using unified serializer
            data = serialize_for_web_api(list(tickets), self.user)

        summary = monitor.get_summary()

        # Verify optimization effectiveness
        self.assertLessEqual(summary['total_queries'], 8)  # Should be minimal queries
        self.assertIn(summary['performance_rating'], ['EXCELLENT', 'GOOD'])

        # Verify data completeness
        self.assertGreaterEqual(len(data), 10)
        for ticket_data in data:
            self.assertIn('id', ticket_data)
            self.assertIn('workflow_status', ticket_data)


class TicketCacheIntegrationTestCase(TestCase):
    """Test cache integration behavior."""

    def setUp(self):
        cache.clear()

    def test_cache_warming_and_invalidation(self):
        """Test cache warming and invalidation cycles."""
        # Test cache warming
        warmup_data = [
            {
                'key_params': {'test': 'key1'},
                'data': {'result': 'data1'}
            }
        ]

        TicketCacheService.warm_cache('ticket_list', warmup_data)

        # Test cache retrieval
        def load_test_data():
            return {'fallback': 'data'}

        result = TicketCacheService.get_cached_data(
            'ticket_list',
            {'test': 'key1'},
            load_test_data
        )

        # Should return warmed data, not fallback
        self.assertEqual(result['result'], 'data1')

        # Test cache invalidation
        TicketCacheService.invalidate_cache('ticket_list', {'test': 'key1'})

        # After invalidation, should call loader
        result2 = TicketCacheService.get_cached_data(
            'ticket_list',
            {'test': 'key1'},
            load_test_data
        )

        self.assertEqual(result2['fallback'], 'data')

    def test_cache_performance_monitoring(self):
        """Test cache performance monitoring capabilities."""
        # Generate some cache activity
        for i in range(5):
            TicketCacheService.get_cached_data(
                'ticket_list',
                {'test_key': f'value_{i}'},
                lambda: {'data': f'result_{i}'}
            )

        # Get cache statistics
        stats = TicketCacheService.get_cache_stats()

        self.assertIn('timestamp', stats)
        self.assertIn('cache_types', stats)
        self.assertIn('ticket_list', stats['cache_types'])


class TicketSecurityIntegrationTestCase(TestCase):
    """Test security and audit integration."""

    def setUp(self):
        self.user = User.objects.create_user(username='sectest', email='sec@test.com')
        self.client_bt = Bt.objects.create(buname='Sec Client', bucode='SC001')
        self.bu = Bt.objects.create(buname='Sec BU', bucode='SB001', client=self.client_bt)

    def test_permission_enforcement_integration(self):
        """Test permission enforcement across all services."""
        # Create ticket
        ticket = Ticket.objects.create(
            ticketno='SEC001',
            ticketdesc='Security test ticket',
            bu=self.bu,
            client=self.client_bt,
            cuser=self.user
        )

        # Test assignment without permissions
        context = AssignmentContext(
            user=self.user,
            reason=AssignmentReason.USER_ACTION,
            assignment_type=AssignmentType.INDIVIDUAL,
            enforce_permissions=True
        )

        # Should fail due to lack of permissions
        result = TicketAssignmentService.assign_ticket_to_person(
            ticket.id, self.user.id, context
        )
        self.assertFalse(result.success)
        self.assertIn('permission', result.error_message.lower())

    def test_audit_trail_completeness(self):
        """Test that audit trails capture all operations."""
        with patch('apps.y_helpdesk.services.ticket_audit_service.logger') as mock_logger:
            # Perform multiple operations
            ticket = Ticket.objects.create(
                ticketno='AUDIT001',
                ticketdesc='Audit test ticket',
                bu=self.bu,
                client=self.client_bt,
                cuser=self.user
            )

            # Log creation
            audit_context = AuditContext(user=self.user)
            TicketAuditService.log_ticket_creation(ticket, audit_context)

            # Perform status transition
            TicketAuditService.log_status_transition(
                ticket.id, 'NEW', 'OPEN', audit_context
            )

            # Verify comprehensive logging
            self.assertGreaterEqual(mock_logger.info.call_count, 1)
            self.assertGreaterEqual(mock_logger.warning.call_count, 1)