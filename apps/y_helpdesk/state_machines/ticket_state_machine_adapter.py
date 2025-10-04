"""
Ticket State Machine Adapter

Adapts the existing TicketStateMachine to work with the BaseStateMachine interface
for use with BulkOperationService.

Compliance with .claude/rules.md:
- Rule #5: Single Responsibility Principle
- Rule #7: Class < 150 lines
- Rule #11: Specific exception handling
"""

import logging
from typing import Optional

from django.utils import timezone

from apps.core.state_machines.base import (
    BaseStateMachine,
    TransitionContext as BaseTransitionContext,
    TransitionResult as BaseTransitionResult,
    InvalidTransitionError,
    PermissionDeniedError,
)

# Import existing ticket state machine
from apps.y_helpdesk.services.ticket_state_machine import (
    TicketStateMachine as LegacyTicketStateMachine,
    TicketStatus,
    TransitionContext,
    TransitionReason,
)

logger = logging.getLogger(__name__)


class TicketStateMachineAdapter(BaseStateMachine):
    """
    Adapter that wraps the existing TicketStateMachine to provide
    BaseStateMachine interface for bulk operations.

    This maintains backward compatibility with the existing
    TicketStateMachine while allowing integration with the new
    BulkOperationService.
    """

    # Map to TicketStatus enum values
    class States:
        """Delegate to TicketStatus enum"""
        NEW = TicketStatus.NEW
        OPEN = TicketStatus.OPEN
        INPROGRESS = TicketStatus.INPROGRESS
        ONHOLD = TicketStatus.ONHOLD
        RESOLVED = TicketStatus.RESOLVED
        CLOSED = TicketStatus.CLOSED
        CANCELLED = TicketStatus.CANCELLED

    # Use existing transition rules from LegacyTicketStateMachine
    VALID_TRANSITIONS = LegacyTicketStateMachine.VALID_TRANSITIONS
    TRANSITION_PERMISSIONS = LegacyTicketStateMachine.TRANSITION_PERMISSIONS

    def _get_current_state(self, instance) -> str:
        """Get current state from ticket instance"""
        return instance.status

    def _set_current_state(self, instance, new_state: str):
        """Set new state on ticket instance"""
        instance.status = new_state

    def _str_to_state(self, state_str: str):
        """Convert string to TicketStatus enum"""
        try:
            return TicketStatus(state_str.upper())
        except ValueError:
            logger.warning(f"Invalid ticket state: {state_str}")
            return None

    def _state_to_str(self, state) -> str:
        """Convert TicketStatus enum to string"""
        if isinstance(state, TicketStatus):
            return state.value
        return str(state)

    def _validate_business_rules(
        self,
        from_state: str,
        to_state: str,
        context: BaseTransitionContext
    ) -> BaseTransitionResult:
        """
        Validate ticket-specific business rules using existing TicketStateMachine.

        Adapts the BaseTransitionContext to the legacy TransitionContext format.
        """
        # Create legacy context
        legacy_context = TransitionContext(
            user=context.user,
            reason=TransitionReason.USER_ACTION,
            comments=context.comments,
            timestamp=context.metadata.get('timestamp') if context.metadata else timezone.now(),
            mobile_client=context.metadata.get('mobile_client', False) if context.metadata else False
        )

        # Use existing validation logic
        legacy_result = LegacyTicketStateMachine.validate_transition(
            from_state,
            to_state,
            legacy_context
        )

        # Convert to BaseTransitionResult
        if not legacy_result.is_valid:
            # Check if it's a permission error
            if legacy_result.required_permissions:
                return BaseTransitionResult(
                    success=False,
                    from_state=from_state,
                    to_state=to_state,
                    error_message=legacy_result.error_message,
                    warnings=legacy_result.warnings or []
                )

            return BaseTransitionResult(
                success=False,
                from_state=from_state,
                to_state=to_state,
                error_message=legacy_result.error_message,
                warnings=legacy_result.warnings or []
            )

        return BaseTransitionResult(
            success=True,
            from_state=from_state,
            to_state=to_state,
            warnings=legacy_result.warnings or []
        )

    def _post_transition_hook(
        self,
        from_state: str,
        to_state: str,
        context: BaseTransitionContext
    ):
        """
        Post-transition actions for tickets.

        Uses the existing audit logging from TicketStateMachine.
        """
        # Create legacy context for logging
        legacy_context = TransitionContext(
            user=context.user,
            reason=TransitionReason.USER_ACTION,
            comments=context.comments,
            timestamp=context.metadata.get('timestamp') if context.metadata else timezone.now(),
            mobile_client=context.metadata.get('mobile_client', False) if context.metadata else False
        )

        # Create result for logging
        legacy_result_dict = {
            'valid': True,
            'message': None,
            'warnings': [],
            'mobile_client': legacy_context.mobile_client,
            'reason': legacy_context.reason.value
        }

        # Use existing audit logging
        if hasattr(self.instance, 'id'):
            LegacyTicketStateMachine.log_transition_attempt(
                ticket_id=self.instance.id,
                current_status=from_state,
                new_status=to_state,
                context=legacy_context,
                result=type('Result', (), legacy_result_dict)()
            )

        logger.info(
            f"Ticket {self.instance.id} transitioned: {from_state} → {to_state}",
            extra={
                'ticket_id': self.instance.id,
                'from_state': from_state,
                'to_state': to_state,
                'user_id': context.user.id if context.user else None
            }
        )
