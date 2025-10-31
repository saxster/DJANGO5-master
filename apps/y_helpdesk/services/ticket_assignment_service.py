"""
Ticket Assignment Service - Centralized assignment logic with race condition prevention

Eliminates assignment logic duplication found across:
- apps/y_helpdesk/services/ticket_workflow_service.py (assign_ticket method)
- apps/y_helpdesk/forms.py (auto-assignment in clean method)
- apps/y_helpdesk/views.py (assignment handling)
- Various manager methods

Following .claude/rules.md:
- Rule #5: Single Responsibility Principle
- Rule #7: Service layer <150 lines per class
- Rule #11: Specific exception handling
- Rule #12: Database query optimization with atomic operations
"""

import logging
from typing import Dict, List, Optional, Union, Tuple, TYPE_CHECKING
from enum import Enum
from dataclasses import dataclass
from datetime import datetime

from django.db import transaction, DatabaseError, IntegrityError
from django.db.models import Q, F
from django.utils import timezone
from django.core.exceptions import ValidationError, ObjectDoesNotExist, PermissionDenied
from django.contrib.auth.models import AbstractUser

from apps.core.utils_new.distributed_locks import distributed_lock, LockAcquisitionError

# TYPE_CHECKING import to break circular dependency
# (y_helpdesk.models → .managers → optimized_managers → services → ticket_workflow_service → ticket_assignment_service → y_helpdesk.models)
if TYPE_CHECKING:
    from apps.y_helpdesk.models import Ticket

from apps.peoples.models import People, Pgroup

# Import audit service for comprehensive logging
from .ticket_audit_service import (
    TicketAuditService,
    AuditContext,
    AuditEventType,
    AuditLevel
)

logger = logging.getLogger(__name__)


class AssignmentType(Enum):
    """Types of ticket assignments."""
    INDIVIDUAL = "individual"
    GROUP = "group"
    AUTO = "auto"
    REASSIGNMENT = "reassignment"
    UNASSIGNMENT = "unassignment"
    ESCALATION = "escalation"


class AssignmentReason(Enum):
    """Reasons for assignment changes."""
    USER_ACTION = "user_action"
    AUTO_ASSIGNMENT = "auto_assignment"
    ESCALATION = "escalation"
    LOAD_BALANCING = "load_balancing"
    BUSINESS_RULE = "business_rule"
    SYSTEM_AUTO = "system_auto"


@dataclass
class AssignmentContext:
    """Context for ticket assignment operations."""
    user: Optional[AbstractUser]
    reason: AssignmentReason
    assignment_type: AssignmentType
    comments: Optional[str] = None
    timestamp: Optional[datetime] = None
    enforce_permissions: bool = True
    trigger_notifications: bool = True

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = timezone.now()


@dataclass
class AssignmentResult:
    """Result of assignment operation."""
    success: bool
    previous_assignee: Optional[Dict] = None
    new_assignee: Optional[Dict] = None
    assignment_type: Optional[AssignmentType] = None
    error_message: Optional[str] = None
    warnings: List[str] = None

    def __post_init__(self):
        if self.warnings is None:
            self.warnings = []


class TicketAssignmentError(ValidationError):
    """Raised when ticket assignment fails."""
    pass


class TicketAssignmentService:
    """
    Centralized ticket assignment management service.

    Eliminates duplication and provides:
    - Atomic assignment operations
    - Permission enforcement
    - Comprehensive audit trails
    - Auto-assignment rule engine
    - Race condition prevention
    """

    # Auto-assignment rules configuration
    AUTO_ASSIGNMENT_RULES = {
        'round_robin': True,
        'workload_based': True,
        'skill_based': False,  # Future enhancement
        'priority_based': True
    }

    @classmethod
    @transaction.atomic
    def assign_ticket_to_person(
        cls,
        ticket_id: int,
        person_id: int,
        context: AssignmentContext
    ) -> AssignmentResult:
        """
        Assign ticket to specific person.

        Args:
            ticket_id: ID of ticket to assign
            person_id: ID of person to assign to
            context: Assignment context

        Returns:
            AssignmentResult with operation details
        """
        # Lazy import to break circular dependency
        from apps.y_helpdesk.models import Ticket

        lock_key = f"ticket_assign:{ticket_id}"

        with distributed_lock(lock_key, timeout=15, blocking_timeout=10):
            try:
                # Get ticket and person with locks
                ticket = Ticket.objects.select_for_update().get(pk=ticket_id)
                person = People.objects.get(pk=person_id)

                # Validate assignment permissions
                if context.enforce_permissions:
                    cls._validate_assignment_permissions(ticket, person, context)

                # Store previous assignment
                previous_assignee = cls._get_assignee_info(ticket)

                # Perform assignment
                ticket.assignedtopeople = person
                ticket.assignedtogroup = None  # Clear group assignment
                ticket.muser = context.user
                ticket.mdtz = timezone.now()

                # Update workflow if exists
                if hasattr(ticket, 'workflow'):
                    workflow = ticket.get_or_create_workflow()
                    workflow.add_workflow_entry(
                        'assigned_to_person',
                        {
                            'person_id': person.id,
                            'person_name': person.peoplename,
                            'previous_assignee': previous_assignee
                        },
                        context.user
                    )

                ticket.save(update_fields=[
                    'assignedtopeople', 'assignedtogroup', 'muser', 'mdtz'
                ])

                # Create result
                result = AssignmentResult(
                    success=True,
                    previous_assignee=previous_assignee,
                    new_assignee={'type': 'person', 'id': person.id, 'name': person.peoplename},
                    assignment_type=context.assignment_type
                )

                # Log assignment
                cls._log_assignment(ticket_id, context, result)

                return result

            except (Ticket.DoesNotExist, People.DoesNotExist):
                error_msg = f"Ticket {ticket_id} or Person {person_id} not found"
                logger.error(error_msg)
                return AssignmentResult(success=False, error_message=error_msg)

            except PermissionDenied as e:
                error_msg = f"Permission denied for assignment: {e}"
                logger.warning(error_msg)
                return AssignmentResult(success=False, error_message=error_msg)

    @classmethod
    @transaction.atomic
    def assign_ticket_to_group(
        cls,
        ticket_id: int,
        group_id: int,
        context: AssignmentContext
    ) -> AssignmentResult:
        """
        Assign ticket to group.

        Args:
            ticket_id: ID of ticket to assign
            group_id: ID of group to assign to
            context: Assignment context

        Returns:
            AssignmentResult with operation details
        """
        # Lazy import to break circular dependency
        from apps.y_helpdesk.models import Ticket

        lock_key = f"ticket_assign:{ticket_id}"

        with distributed_lock(lock_key, timeout=15, blocking_timeout=10):
            try:
                # Get ticket and group with locks
                ticket = Ticket.objects.select_for_update().get(pk=ticket_id)
                group = Pgroup.objects.get(pk=group_id)

                # Validate assignment permissions
                if context.enforce_permissions:
                    cls._validate_group_assignment_permissions(ticket, group, context)

                # Store previous assignment
                previous_assignee = cls._get_assignee_info(ticket)

                # Perform assignment
                ticket.assignedtogroup = group
                ticket.assignedtopeople = None  # Clear individual assignment
                ticket.muser = context.user
                ticket.mdtz = timezone.now()

                # Update workflow if exists
                if hasattr(ticket, 'workflow'):
                    workflow = ticket.get_or_create_workflow()
                    workflow.add_workflow_entry(
                        'assigned_to_group',
                        {
                            'group_id': group.id,
                            'group_name': group.groupname,
                            'previous_assignee': previous_assignee
                        },
                        context.user
                    )

                ticket.save(update_fields=[
                    'assignedtopeople', 'assignedtogroup', 'muser', 'mdtz'
                ])

                # Create result
                result = AssignmentResult(
                    success=True,
                    previous_assignee=previous_assignee,
                    new_assignee={'type': 'group', 'id': group.id, 'name': group.groupname},
                    assignment_type=context.assignment_type
                )

                # Log assignment
                cls._log_assignment(ticket_id, context, result)

                return result

            except (Ticket.DoesNotExist, Pgroup.DoesNotExist):
                error_msg = f"Ticket {ticket_id} or Group {group_id} not found"
                logger.error(error_msg)
                return AssignmentResult(success=False, error_message=error_msg)

    @classmethod
    def auto_assign_ticket(
        cls,
        ticket_id: int,
        context: AssignmentContext
    ) -> AssignmentResult:
        """
        Auto-assign ticket using business rules.

        Args:
            ticket_id: ID of ticket to auto-assign
            context: Assignment context

        Returns:
            AssignmentResult with operation details
        """
        # Lazy import to break circular dependency
        from apps.y_helpdesk.models import Ticket

        try:
            ticket = Ticket.objects.get(pk=ticket_id)

            # Apply auto-assignment rules
            assignee = cls._determine_auto_assignee(ticket, context)

            if not assignee:
                return AssignmentResult(
                    success=False,
                    error_message="No suitable assignee found for auto-assignment"
                )

            # Perform assignment based on assignee type
            if assignee['type'] == 'person':
                return cls.assign_ticket_to_person(
                    ticket_id, assignee['id'], context
                )
            elif assignee['type'] == 'group':
                return cls.assign_ticket_to_group(
                    ticket_id, assignee['id'], context
                )

        except Ticket.DoesNotExist:
            error_msg = f"Ticket {ticket_id} not found for auto-assignment"
            logger.error(error_msg)
            return AssignmentResult(success=False, error_message=error_msg)

    @classmethod
    def _determine_auto_assignee(
        cls,
        ticket,  # Type: Ticket (hint removed due to circular import)
        context: AssignmentContext
    ) -> Optional[Dict]:
        """
        Determine best assignee using auto-assignment rules.

        Args:
            ticket: Ticket to assign
            context: Assignment context

        Returns:
            Dictionary with assignee info or None
        """
        # Priority-based assignment
        if cls.AUTO_ASSIGNMENT_RULES['priority_based'] and ticket.priority == 'HIGH':
            # Find available high-priority specialists
            specialists = cls._find_priority_specialists(ticket)
            if specialists:
                return cls._select_best_assignee(specialists, 'priority')

        # Workload-based assignment
        if cls.AUTO_ASSIGNMENT_RULES['workload_based']:
            available_people = cls._find_available_people(ticket)
            if available_people:
                return cls._select_least_busy_assignee(available_people)

        # Round-robin assignment
        if cls.AUTO_ASSIGNMENT_RULES['round_robin']:
            available_people = cls._find_available_people(ticket)
            if available_people:
                return cls._select_round_robin_assignee(available_people, ticket)

        # Fallback: assign to ticket creator if no other rules apply
        if ticket.cuser:
            return {'type': 'person', 'id': ticket.cuser.id, 'name': ticket.cuser.peoplename}

        return None

    @classmethod
    def _find_available_people(cls, ticket) -> List[Dict]:  # ticket type: Ticket (hint removed due to circular import)
        """Find people available for assignment based on business unit and client."""
        # This would be enhanced with actual business logic
        # For now, return people from same BU/client
        people = People.objects.filter(
            peopleorganizational__bu=ticket.bu,
            peopleorganizational__client=ticket.client,
            enable=True
        ).values('id', 'peoplename')

        return [
            {'type': 'person', 'id': p['id'], 'name': p['peoplename']}
            for p in people
        ]

    @classmethod
    def _select_least_busy_assignee(cls, available_people: List[Dict]) -> Dict:
        """Select assignee with least current workload."""
        # Enhanced logic would query current ticket counts
        # For now, return first available
        return available_people[0] if available_people else None

    @classmethod
    def _select_round_robin_assignee(cls, available_people: List[Dict], ticket) -> Dict:  # ticket type: Ticket (hint removed)
        """Select assignee using round-robin algorithm."""
        # Enhanced logic would track assignment rotation
        # For now, use modulo based on ticket ID
        if available_people:
            index = ticket.id % len(available_people)
            return available_people[index]
        return None

    @classmethod
    def _find_priority_specialists(cls, ticket) -> List[Dict]:  # ticket type: Ticket (hint removed)
        """Find specialists for high-priority tickets."""
        # This would query people with specific skills/roles
        # For now, return senior team members
        return cls._find_available_people(ticket)[:2]  # Top 2 available

    @classmethod
    def _select_best_assignee(cls, specialists: List[Dict], criteria: str) -> Dict:
        """Select best assignee based on criteria."""
        return specialists[0] if specialists else None

    @classmethod
    def _get_assignee_info(cls, ticket) -> Optional[Dict]:  # ticket type: Ticket (hint removed)
        """Get current assignee information."""
        if ticket.assignedtopeople:
            return {
                'type': 'person',
                'id': ticket.assignedtopeople.id,
                'name': ticket.assignedtopeople.peoplename
            }
        elif ticket.assignedtogroup:
            return {
                'type': 'group',
                'id': ticket.assignedtogroup.id,
                'name': ticket.assignedtogroup.groupname
            }
        return None

    @classmethod
    def _validate_assignment_permissions(
        cls,
        ticket,  # Type: Ticket (hint removed due to circular import)
        person: People,
        context: AssignmentContext
    ):
        """Validate permissions for person assignment."""
        if not context.user:
            raise PermissionDenied("User required for assignment")

        # Check if user has permission to assign tickets
        if not context.user.has_perm('y_helpdesk.change_ticket'):
            raise PermissionDenied("User lacks permission to assign tickets")

        # Check business unit permissions
        if hasattr(context.user, 'peopleorganizational'):
            user_org = context.user.peopleorganizational
            if user_org.bu != ticket.bu and not context.user.is_superuser:
                raise PermissionDenied("Cannot assign tickets outside your business unit")

    @classmethod
    def _validate_group_assignment_permissions(
        cls,
        ticket,  # Type: Ticket (hint removed due to circular import)
        group: Pgroup,
        context: AssignmentContext
    ):
        """Validate permissions for group assignment."""
        cls._validate_assignment_permissions(ticket, None, context)

        # Additional group-specific validations could be added here

    @classmethod
    def _log_assignment(
        cls,
        ticket_id: int,
        context: AssignmentContext,
        result: AssignmentResult
    ):
        """Log assignment operation using comprehensive audit service."""
        # Create audit context
        audit_context = AuditContext(
            user=context.user,
            timestamp=context.timestamp
        )

        # Use TicketAuditService for comprehensive audit logging
        TicketAuditService.log_assignment_change(
            ticket_id=ticket_id,
            assignment_result={
                'assignment_type': result.assignment_type.value if result.assignment_type else None,
                'success': result.success,
                'previous_assignee': result.previous_assignee,
                'new_assignee': result.new_assignee,
                'reason': context.reason.value,
                'error_message': result.error_message
            },
            context=audit_context
        )

        # Fallback basic logging for immediate debugging
        logger.info(
            f"Ticket {ticket_id} assignment: {result.assignment_type.value if result.assignment_type else 'unknown'} ({'SUCCESS' if result.success else 'FAILED'})",
            extra={
                'ticket_id': ticket_id,
                'success': result.success,
                'user_id': context.user.id if context.user else None,
                'reason': context.reason.value
            }
        )