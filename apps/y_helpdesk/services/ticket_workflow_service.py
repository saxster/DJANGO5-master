"""
Ticket Workflow Service - Atomic state management with race condition prevention

Centralizes ticket workflow operations to prevent race conditions in:
- Ticket status transitions
- Escalation level updates
- Ticket log history updates
- Assignment changes

Following .claude/rules.md:
- Service layer pattern (Rule 8: View Method Size Limits)
- Specific exception handling (Rule 11)
- Database query optimization (Rule 12)
- Transaction.atomic() for consistency
"""

import logging
from datetime import datetime
from typing import Dict, Any, Optional, List, TYPE_CHECKING
from enum import Enum

from django.db import transaction, DatabaseError, OperationalError, IntegrityError
from django.db.models import F
from django.utils import timezone
from django.core.exceptions import ValidationError, ObjectDoesNotExist

from apps.core.utils_new.distributed_locks import distributed_lock, LockAcquisitionError
from apps.core.error_handling import ErrorHandler

# TYPE_CHECKING import to break circular dependency
# (y_helpdesk.models → .managers → optimized_managers → services → ticket_workflow_service → y_helpdesk.models)
if TYPE_CHECKING:
    from apps.y_helpdesk.models import Ticket, EscalationMatrix
from .ticket_state_machine import (
    TicketStateMachine,
    TransitionContext,
    TransitionReason,
    InvalidTransitionError
)
from .ticket_assignment_service import (
    TicketAssignmentService,
    AssignmentContext,
    AssignmentReason,
    AssignmentType
)

logger = logging.getLogger(__name__)


__all__ = [
    'TicketWorkflowService',
    'InvalidTicketTransitionError',
]


class InvalidTicketTransitionError(ValidationError):
    """Raised when attempting invalid ticket status transition"""
    pass


class TicketWorkflowService:
    """
    Atomic ticket workflow state management service

    Prevents race conditions in:
    - Ticket status transitions
    - Escalation updates
    - History log updates
    - Assignment changes
    """

    # Status transitions now handled by centralized TicketStateMachine

    @classmethod
    @transaction.atomic
    def transition_ticket_status(
        cls,
        ticket_id: int,
        new_status: str,
        user,
        validate_transition: bool = True,
        comments: Optional[str] = None
    ):  # Return type removed due to circular import
        """
        Atomically transition ticket to new status with validation.

        Args:
            ticket_id: ID of ticket to update
            new_status: Target status
            user: User performing transition
            validate_transition: Whether to validate state transition
            comments: Optional comments for history

        Returns:
            Updated ticket instance

        Raises:
            InvalidTicketTransitionError: If transition invalid
            LockAcquisitionError: If cannot acquire lock
            ObjectDoesNotExist: If ticket not found
        """
        # Lazy import to break circular dependency
        from apps.y_helpdesk.models import Ticket

        lock_key = f"ticket_status:{ticket_id}"

        with distributed_lock(lock_key, timeout=10, blocking_timeout=5):
            try:
                ticket = Ticket.objects.select_for_update().get(pk=ticket_id)
                old_status = ticket.status

                if validate_transition:
                    # Use centralized TicketStateMachine for validation
                    context = TransitionContext(
                        user=user,
                        reason=TransitionReason.SYSTEM_AUTO,
                        comments=comments
                    )

                    result = TicketStateMachine.validate_transition(
                        old_status, new_status, context
                    )

                    if not result.is_valid:
                        raise InvalidTicketTransitionError(result.error_message)

                    # Log transition attempt
                    TicketStateMachine.log_transition_attempt(
                        ticket_id=ticket_id,
                        current_status=old_status,
                        new_status=new_status,
                        context=context,
                        result=result
                    )

                ticket.status = new_status
                ticket.modifieddatetime = timezone.now()
                ticket.muser = user
                ticket.mdtz = timezone.now()

                if comments:
                    ticket.comments = comments

                ticket.save(update_fields=['status', 'modifieddatetime', 'muser', 'mdtz', 'comments'])

                logger.info(
                    f"Ticket {ticket_id} status transition: {old_status} → {new_status}",
                    extra={
                        'ticket_id': ticket_id,
                        'old_status': old_status,
                        'new_status': new_status,
                        'user_id': user.id
                    }
                )

                return ticket

            except Ticket.DoesNotExist:
                logger.error(f"Ticket {ticket_id} not found")
                raise

    @classmethod
    @transaction.atomic
    def escalate_ticket(
        cls,
        ticket_id: int,
        new_level: Optional[int] = None,
        assigned_person_id: Optional[int] = None,
        assigned_group_id: Optional[int] = None,
        user = None
    ):  # Return type removed due to circular import
        """
        Atomically escalate ticket to next level.

        Uses F() expression for atomic level increment to prevent
        concurrent escalations from corrupting level.

        Args:
            ticket_id: ID of ticket to escalate
            new_level: Specific level (if None, increments by 1)
            assigned_person_id: New assignee person ID
            assigned_group_id: New assignee group ID
            user: User performing escalation

        Returns:
            Updated ticket instance

        Raises:
            LockAcquisitionError: If cannot acquire lock
            ObjectDoesNotExist: If ticket not found
        """
        # Lazy import to break circular dependency
        from apps.y_helpdesk.models import Ticket

        lock_key = f"ticket_escalate:{ticket_id}"

        with distributed_lock(lock_key, timeout=15, blocking_timeout=10):
            try:
                ticket = Ticket.objects.select_for_update().get(pk=ticket_id)
                old_level = ticket.level

                update_dict = {
                    'isescalated': True,
                    'modifieddatetime': timezone.now(),
                    'mdtz': timezone.now(),
                }

                if new_level is not None:
                    update_dict['level'] = new_level
                else:
                    update_dict['level'] = F('level') + 1

                if assigned_person_id is not None:
                    update_dict['assignedtopeople_id'] = assigned_person_id

                if assigned_group_id is not None:
                    update_dict['assignedtogroup_id'] = assigned_group_id

                if user:
                    update_dict['muser'] = user

                Ticket.objects.filter(pk=ticket_id).update(**update_dict)

                ticket.refresh_from_db()

                logger.info(
                    f"Ticket {ticket_id} escalated: level {old_level} → {ticket.level}",
                    extra={
                        'ticket_id': ticket_id,
                        'old_level': old_level,
                        'new_level': ticket.level,
                        'assigned_person': assigned_person_id,
                        'assigned_group': assigned_group_id
                    }
                )

                return ticket

            except Ticket.DoesNotExist:
                logger.error(f"Ticket {ticket_id} not found for escalation")
                raise

    @classmethod
    @transaction.atomic
    def append_history_entry(
        cls,
        ticket_id: int,
        history_item: Dict[str, Any]
    ):  # Return type removed due to circular import
        """
        Atomically append entry to ticket history log.

        Prevents concurrent history updates from losing entries.

        Args:
            ticket_id: ID of ticket
            history_item: History entry dict to append

        Returns:
            Updated ticket instance
        """
        # Lazy import to break circular dependency
        from apps.y_helpdesk.models import Ticket

        lock_key = f"ticket_history:{ticket_id}"

        with distributed_lock(lock_key, timeout=10, blocking_timeout=5):
            try:
                ticket = Ticket.objects.select_for_update().get(pk=ticket_id)

                ticketlog = dict(ticket.ticketlog)
                if 'ticket_history' not in ticketlog:
                    ticketlog['ticket_history'] = []

                ticketlog['ticket_history'].append(history_item)

                ticket.ticketlog = ticketlog
                ticket.mdtz = timezone.now()
                ticket.save(update_fields=['ticketlog', 'mdtz'])

                logger.info(
                    f"Ticket {ticket_id} history entry added",
                    extra={
                        'ticket_id': ticket_id,
                        'action': history_item.get('action', 'unknown'),
                        'history_length': len(ticketlog['ticket_history'])
                    }
                )

                return ticket

            except Ticket.DoesNotExist:
                logger.error(f"Ticket {ticket_id} not found for history update")
                raise

    # Transition validation now handled by centralized TicketStateMachine

    @classmethod
    def assign_ticket(
        cls,
        ticket_id: int,
        person_id: Optional[int] = None,
        group_id: Optional[int] = None,
        user = None
    ):  # Return type removed due to circular import
        """
        Assign ticket to person or group using centralized TicketAssignmentService.

        Args:
            ticket_id: ID of ticket to assign
            person_id: Person to assign to
            group_id: Group to assign to
            user: User performing assignment

        Returns:
            Updated ticket instance

        Raises:
            Ticket.DoesNotExist: If ticket not found
            ValidationError: If assignment fails
        """
        # Lazy import to break circular dependency
        from apps.y_helpdesk.models import Ticket

        # Create assignment context
        context = AssignmentContext(
            user=user,
            reason=AssignmentReason.USER_ACTION,
            assignment_type=AssignmentType.INDIVIDUAL if person_id else AssignmentType.GROUP,
            enforce_permissions=True,
            trigger_notifications=True
        )

        # Delegate to centralized assignment service
        if person_id is not None:
            result = TicketAssignmentService.assign_ticket_to_person(
                ticket_id, person_id, context
            )
        elif group_id is not None:
            result = TicketAssignmentService.assign_ticket_to_group(
                ticket_id, group_id, context
            )
        else:
            raise ValidationError("Either person_id or group_id must be provided")

        if not result.success:
            raise ValidationError(result.error_message)

        # Return updated ticket instance
        try:
            return Ticket.objects.get(pk=ticket_id)
        except Ticket.DoesNotExist:
            logger.error(f"Ticket {ticket_id} not found after assignment")
            raise

    @classmethod
    @transaction.atomic
    def bulk_update_tickets(
        cls,
        ticket_ids: List[int],
        updates: Dict[str, Any],
        user = None
    ) -> int:
        """
        Atomically update multiple tickets.

        Args:
            ticket_ids: List of ticket IDs to update
            updates: Dictionary of field updates
            user: User performing updates

        Returns:
            Number of tickets updated
        """
        # Lazy import to break circular dependency
        from apps.y_helpdesk.models import Ticket

        lock_key = f"ticket_bulk_update:{'_'.join(map(str, sorted(ticket_ids[:5])))}"

        with distributed_lock(lock_key, timeout=20, blocking_timeout=15):
            try:
                tickets = Ticket.objects.select_for_update().filter(pk__in=ticket_ids)

                update_dict = {**updates}
                update_dict['modifieddatetime'] = timezone.now()
                update_dict['mdtz'] = timezone.now()

                if user:
                    update_dict['muser'] = user

                count = tickets.update(**update_dict)

                logger.info(
                    f"Bulk updated {count} tickets",
                    extra={
                        'ticket_count': count,
                        'updates': list(updates.keys())
                    }
                )

                return count

            except (DatabaseError, OperationalError) as e:
                logger.error(
                    f"Database error in bulk ticket update",
                    exc_info=True
                )
                raise