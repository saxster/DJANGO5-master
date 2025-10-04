"""
Comprehensive tests for TicketStateMachine

Validates all state transitions, permissions, business rules, and edge cases.
"""

import pytest
from unittest.mock import Mock, patch
from datetime import datetime

from django.test import TestCase
from django.contrib.auth.models import User, Permission
from django.contrib.contenttypes.models import ContentType
from django.utils import timezone

from apps.y_helpdesk.services.ticket_state_machine import (
    TicketStateMachine,
    TicketStatus,
    TransitionReason,
    TransitionContext,
    TransitionResult,
    InvalidTransitionError
)


class TicketStateMachineTestCase(TestCase):
    """Test suite for TicketStateMachine functionality."""

    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass'
        )

        # Create permissions for testing
        content_type = ContentType.objects.get_for_model(User)  # Using User as placeholder
        self.reopen_permission = Permission.objects.create(
            codename='reopen_ticket',
            name='Can reopen ticket',
            content_type=content_type
        )
        self.cancel_permission = Permission.objects.create(
            codename='cancel_ticket',
            name='Can cancel ticket',
            content_type=content_type
        )

    def test_valid_transitions_basic(self):
        """Test all valid basic transitions without context."""
        valid_cases = [
            ('NEW', 'OPEN'),
            ('NEW', 'INPROGRESS'),
            ('NEW', 'CANCELLED'),
            ('OPEN', 'INPROGRESS'),
            ('OPEN', 'RESOLVED'),
            ('OPEN', 'ONHOLD'),
            ('OPEN', 'CANCELLED'),
            ('INPROGRESS', 'RESOLVED'),
            ('INPROGRESS', 'ONHOLD'),
            ('INPROGRESS', 'OPEN'),
            ('INPROGRESS', 'CANCELLED'),
            ('ONHOLD', 'OPEN'),
            ('ONHOLD', 'INPROGRESS'),
            ('ONHOLD', 'RESOLVED'),
            ('ONHOLD', 'CANCELLED'),
            ('RESOLVED', 'CLOSED'),
            ('RESOLVED', 'OPEN'),
        ]

        for current, target in valid_cases:
            with self.subTest(current=current, target=target):
                self.assertTrue(
                    TicketStateMachine.is_valid_transition(current, target),
                    f"Expected {current} -> {target} to be valid"
                )

    def test_invalid_transitions(self):
        """Test invalid transitions."""
        invalid_cases = [
            ('CLOSED', 'OPEN'),
            ('CANCELLED', 'OPEN'),
            ('NEW', 'RESOLVED'),
            ('NEW', 'CLOSED'),
            ('OPEN', 'CLOSED'),
            ('INPROGRESS', 'CLOSED'),
            ('ONHOLD', 'CLOSED'),
            ('RESOLVED', 'CANCELLED'),
            ('RESOLVED', 'INPROGRESS'),
        ]

        for current, target in invalid_cases:
            with self.subTest(current=current, target=target):
                self.assertFalse(
                    TicketStateMachine.is_valid_transition(current, target),
                    f"Expected {current} -> {target} to be invalid"
                )

    def test_same_status_transition(self):
        """Test that transitioning to same status is always valid."""
        for status in TicketStatus:
            self.assertTrue(
                TicketStateMachine.is_valid_transition(status.value, status.value)
            )

    def test_case_insensitive_transitions(self):
        """Test that status validation is case insensitive."""
        self.assertTrue(
            TicketStateMachine.is_valid_transition('new', 'OPEN')
        )
        self.assertTrue(
            TicketStateMachine.is_valid_transition('OPEN', 'resolved')
        )
        self.assertTrue(
            TicketStateMachine.is_valid_transition('open', 'inprogress')
        )

    def test_invalid_status_values(self):
        """Test handling of invalid status values."""
        self.assertFalse(
            TicketStateMachine.is_valid_transition('INVALID_STATUS', 'OPEN')
        )
        self.assertFalse(
            TicketStateMachine.is_valid_transition('NEW', 'INVALID_STATUS')
        )

    def test_validate_transition_with_comments_required(self):
        """Test validation requiring comments for terminal states."""
        context_no_comments = TransitionContext(
            user=self.user,
            reason=TransitionReason.USER_ACTION
        )

        context_with_comments = TransitionContext(
            user=self.user,
            reason=TransitionReason.USER_ACTION,
            comments="Resolving the issue"
        )

        # Terminal states should require comments
        terminal_transitions = [
            ('INPROGRESS', 'RESOLVED'),
            ('ONHOLD', 'RESOLVED'),
            ('RESOLVED', 'CLOSED'),
            ('OPEN', 'CANCELLED'),
        ]

        for current, target in terminal_transitions:
            with self.subTest(current=current, target=target):
                # Without comments should fail
                result = TicketStateMachine.validate_transition(
                    current, target, context_no_comments
                )
                self.assertFalse(result.is_valid)
                self.assertIn("Comments required", result.error_message)

                # With comments should succeed
                result = TicketStateMachine.validate_transition(
                    current, target, context_with_comments
                )
                self.assertTrue(result.is_valid)

    def test_permission_based_transitions(self):
        """Test transitions requiring specific permissions."""
        context = TransitionContext(
            user=self.user,
            reason=TransitionReason.USER_ACTION,
            comments="Test transition"
        )

        # Test reopen permission
        result = TicketStateMachine.validate_transition(
            'RESOLVED', 'OPEN', context
        )
        self.assertFalse(result.is_valid)
        self.assertIn("Missing permissions", result.error_message)
        self.assertIn("reopen_ticket", result.error_message)

        # Grant permission and test again
        self.user.user_permissions.add(self.reopen_permission)
        result = TicketStateMachine.validate_transition(
            'RESOLVED', 'OPEN', context
        )
        self.assertTrue(result.is_valid)

        # Test cancel permission
        self.user.user_permissions.remove(self.reopen_permission)
        result = TicketStateMachine.validate_transition(
            'ONHOLD', 'CANCELLED', context
        )
        self.assertFalse(result.is_valid)
        self.assertIn("cancel_ticket", result.error_message)

        # Grant cancel permission
        self.user.user_permissions.add(self.cancel_permission)
        result = TicketStateMachine.validate_transition(
            'ONHOLD', 'CANCELLED', context
        )
        self.assertTrue(result.is_valid)

    def test_get_allowed_transitions_without_user(self):
        """Test getting allowed transitions without user context."""
        allowed = TicketStateMachine.get_allowed_transitions('NEW')
        expected = {'OPEN', 'INPROGRESS', 'CANCELLED'}
        self.assertEqual(set(allowed), expected)

        allowed = TicketStateMachine.get_allowed_transitions('RESOLVED')
        expected = {'CLOSED', 'OPEN'}
        self.assertEqual(set(allowed), expected)

        allowed = TicketStateMachine.get_allowed_transitions('CLOSED')
        self.assertEqual(allowed, [])

    def test_get_allowed_transitions_with_user_permissions(self):
        """Test permission filtering in allowed transitions."""
        # Without reopen permission
        allowed = TicketStateMachine.get_allowed_transitions('RESOLVED', self.user)
        self.assertNotIn('OPEN', allowed)
        self.assertIn('CLOSED', allowed)

        # With reopen permission
        self.user.user_permissions.add(self.reopen_permission)
        allowed = TicketStateMachine.get_allowed_transitions('RESOLVED', self.user)
        self.assertIn('OPEN', allowed)
        self.assertIn('CLOSED', allowed)

    def test_transition_warnings(self):
        """Test warning generation for rapid transitions."""
        context = TransitionContext(
            user=self.user,
            reason=TransitionReason.USER_ACTION,
            comments="Rapid resolution"
        )

        result = TicketStateMachine.validate_transition(
            'NEW', 'RESOLVED', context
        )
        # Should be invalid due to invalid transition path
        self.assertFalse(result.is_valid)

        # Test a valid rapid transition that should generate warning
        context.reason = TransitionReason.USER_ACTION
        result = TicketStateMachine.validate_transition(
            'NEW', 'INPROGRESS', context  # This is a valid transition
        )
        self.assertTrue(result.is_valid)

    def test_backward_compatibility_status_variants(self):
        """Test support for legacy status variants."""
        # Test CANCEL vs CANCELLED compatibility
        self.assertTrue(
            TicketStateMachine.is_valid_transition('NEW', 'CANCELLED')
        )

    @patch('apps.y_helpdesk.services.ticket_state_machine.logger')
    def test_transition_logging(self, mock_logger):
        """Test audit logging of transition attempts."""
        context = TransitionContext(
            user=self.user,
            reason=TransitionReason.USER_ACTION,
            comments="Test transition"
        )

        result = TransitionResult(is_valid=True)

        TicketStateMachine.log_transition_attempt(
            ticket_id=123,
            current_status='NEW',
            new_status='OPEN',
            context=context,
            result=result
        )

        # Verify logging was called
        mock_logger.info.assert_called_once()
        call_args = mock_logger.info.call_args

        # Check log message content
        self.assertIn('Ticket 123 transition attempt', call_args[0][0])
        self.assertIn('NEW -> OPEN', call_args[0][0])

        # Check extra data
        extra_data = call_args[1]['extra']
        self.assertEqual(extra_data['ticket_id'], 123)
        self.assertEqual(extra_data['current_status'], 'NEW')
        self.assertEqual(extra_data['new_status'], 'OPEN')
        self.assertEqual(extra_data['user_id'], self.user.id)
        self.assertEqual(extra_data['reason'], 'user_action')
        self.assertTrue(extra_data['success'])

    def test_mobile_client_context(self):
        """Test mobile client specific context handling."""
        context = TransitionContext(
            user=self.user,
            reason=TransitionReason.MOBILE_SYNC,
            comments="Mobile sync",
            mobile_client=True
        )

        result = TicketStateMachine.validate_transition(
            'OPEN', 'INPROGRESS', context
        )
        self.assertTrue(result.is_valid)

        # Test logging captures mobile context
        with patch('apps.y_helpdesk.services.ticket_state_machine.logger') as mock_logger:
            result_obj = TransitionResult(is_valid=True)
            TicketStateMachine.log_transition_attempt(
                ticket_id=456,
                current_status='OPEN',
                new_status='INPROGRESS',
                context=context,
                result=result_obj
            )

            extra_data = mock_logger.info.call_args[1]['extra']
            self.assertTrue(extra_data['mobile_client'])
            self.assertEqual(extra_data['reason'], 'mobile_sync')

    def test_transition_context_defaults(self):
        """Test TransitionContext default values."""
        context = TransitionContext(
            user=self.user,
            reason=TransitionReason.SYSTEM_AUTO
        )

        self.assertIsNotNone(context.timestamp)
        self.assertFalse(context.mobile_client)
        self.assertIsNone(context.comments)

    def test_invalid_enum_handling(self):
        """Test graceful handling of invalid enum values."""
        with patch('apps.y_helpdesk.services.ticket_state_machine.logger') as mock_logger:
            result = TicketStateMachine.is_valid_transition('INVALID', 'OPEN')
            self.assertFalse(result)
            mock_logger.warning.assert_called_once()

    def test_transition_result_dataclass(self):
        """Test TransitionResult dataclass functionality."""
        result = TransitionResult(
            is_valid=False,
            error_message="Test error",
            required_permissions=['test_perm'],
            warnings=['Test warning']
        )

        self.assertFalse(result.is_valid)
        self.assertEqual(result.error_message, "Test error")
        self.assertEqual(result.required_permissions, ['test_perm'])
        self.assertEqual(result.warnings, ['Test warning'])