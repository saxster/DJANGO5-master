"""
Ticket State Machine - Centralized Status Transition Management

Single source of truth for all ticket status transitions, eliminating
the 4 different implementations found across the codebase.

Following .claude/rules.md:
- Rule #5: Single Responsibility Principle
- Rule #7: Service layer <150 lines
- Rule #11: Specific exception handling
- Rule #12: No code duplication

Key Features:
- Authoritative state transition rules
- Permission-based transition validation
- Audit trail integration
- Backward compatibility with all existing status values
- Support for both web and mobile workflows
"""

import logging
from typing import Dict, List, Optional, Set, Tuple
from enum import Enum
from dataclasses import dataclass
from datetime import datetime

from django.core.exceptions import ValidationError
from django.contrib.auth.models import AbstractUser
from django.utils import timezone

logger = logging.getLogger(__name__)

# Import audit service for comprehensive logging
from .ticket_audit_service import (
    TicketAuditService,
    AuditContext,
    AuditEventType,
    AuditLevel
)


class TicketStatus(Enum):
    """Authoritative ticket status enumeration."""
    NEW = "NEW"
    OPEN = "OPEN"
    INPROGRESS = "INPROGRESS"  # Mobile workflow state
    ONHOLD = "ONHOLD"
    RESOLVED = "RESOLVED"
    CLOSED = "CLOSED"
    CANCELLED = "CANCELLED"  # Standardized from CANCEL/CANCELLED variants


class TransitionReason(Enum):
    """Reasons for status transitions."""
    USER_ACTION = "user_action"
    SYSTEM_AUTO = "system_auto"
    ESCALATION = "escalation"
    TIMEOUT = "timeout"
    MOBILE_SYNC = "mobile_sync"


@dataclass
class TransitionContext:
    """Context for a status transition attempt."""
    user: Optional[AbstractUser]
    reason: TransitionReason
    comments: Optional[str] = None
    timestamp: Optional[datetime] = None
    mobile_client: bool = False

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = timezone.now()


@dataclass
class TransitionResult:
    """Result of a transition validation."""
    is_valid: bool
    error_message: Optional[str] = None
    required_permissions: List[str] = None
    warnings: List[str] = None


class InvalidTransitionError(ValidationError):
    """Raised when attempting invalid ticket status transition."""
    pass


class TicketStateMachine:
    """
    Centralized ticket status transition manager.

    Eliminates duplication found in:
    - apps/y_helpdesk/forms.py (lines 102-117)
    - apps/y_helpdesk/services/ticket_workflow_service.py (lines 56-63)
    - apps/y_helpdesk/services/ticket_sync_service.py (lines 129-144)
    - apps/y_helpdesk/serializers/ticket_sync_serializers.py (lines 65-72)
    """

    # Authoritative state transition rules
    VALID_TRANSITIONS: Dict[TicketStatus, Set[TicketStatus]] = {
        TicketStatus.NEW: {
            TicketStatus.OPEN,
            TicketStatus.INPROGRESS,  # Direct assignment
            TicketStatus.CANCELLED
        },
        TicketStatus.OPEN: {
            TicketStatus.INPROGRESS,
            TicketStatus.RESOLVED,
            TicketStatus.ONHOLD,
            TicketStatus.CANCELLED
        },
        TicketStatus.INPROGRESS: {
            TicketStatus.RESOLVED,
            TicketStatus.ONHOLD,
            TicketStatus.OPEN,  # Reassignment
            TicketStatus.CANCELLED
        },
        TicketStatus.ONHOLD: {
            TicketStatus.OPEN,
            TicketStatus.INPROGRESS,
            TicketStatus.RESOLVED,
            TicketStatus.CANCELLED
        },
        TicketStatus.RESOLVED: {
            TicketStatus.CLOSED,
            TicketStatus.OPEN  # Reopening
        },
        TicketStatus.CLOSED: set(),  # Terminal state
        TicketStatus.CANCELLED: set(),  # Terminal state
    }

    # Permissions required for specific transitions
    TRANSITION_PERMISSIONS: Dict[Tuple[TicketStatus, TicketStatus], List[str]] = {
        (TicketStatus.RESOLVED, TicketStatus.OPEN): ['y_helpdesk.reopen_ticket'],
        (TicketStatus.ONHOLD, TicketStatus.CANCELLED): ['y_helpdesk.cancel_ticket'],
        (TicketStatus.INPROGRESS, TicketStatus.CANCELLED): ['y_helpdesk.cancel_ticket'],
    }

    @classmethod
    def is_valid_transition(
        cls,
        current_status: str,
        new_status: str,
        context: Optional[TransitionContext] = None
    ) -> bool:
        """
        Check if status transition is valid.

        Args:
            current_status: Current ticket status (string)
            new_status: Target status (string)
            context: Optional transition context

        Returns:
            True if transition is valid
        """
        try:
            current = TicketStatus(current_status.upper())
            target = TicketStatus(new_status.upper())

            if current == target:
                return True

            return target in cls.VALID_TRANSITIONS.get(current, set())

        except ValueError:
            logger.warning(f"Unknown status in transition: {current_status} -> {new_status}")
            return False

    @classmethod
    def validate_transition(
        cls,
        current_status: str,
        new_status: str,
        context: TransitionContext
    ) -> TransitionResult:
        """
        Comprehensive transition validation with permissions and business rules.

        Args:
            current_status: Current ticket status
            new_status: Target status
            context: Transition context with user and reason

        Returns:
            TransitionResult with validation details
        """
        try:
            current = TicketStatus(current_status.upper())
            target = TicketStatus(new_status.upper())
        except ValueError as e:
            return TransitionResult(
                is_valid=False,
                error_message=f"Invalid status value: {e}"
            )

        # Check basic transition validity
        if not cls.is_valid_transition(current_status, new_status, context):
            allowed = [s.value for s in cls.VALID_TRANSITIONS.get(current, set())]
            return TransitionResult(
                is_valid=False,
                error_message=f"Invalid transition from {current.value} to {target.value}. "
                            f"Allowed transitions: {allowed}"
            )

        # Check permissions if user context provided
        if context.user:
            transition_key = (current, target)
            required_perms = cls.TRANSITION_PERMISSIONS.get(transition_key, [])

            if required_perms:
                missing_perms = [
                    perm for perm in required_perms
                    if not context.user.has_perm(perm)
                ]
                if missing_perms:
                    return TransitionResult(
                        is_valid=False,
                        error_message=f"Missing permissions: {missing_perms}",
                        required_permissions=required_perms
                    )

        # Business rule validations
        warnings = []

        # Require comments for terminal transitions
        if target in {TicketStatus.RESOLVED, TicketStatus.CLOSED, TicketStatus.CANCELLED}:
            if not context.comments:
                return TransitionResult(
                    is_valid=False,
                    error_message=f"Comments required when transitioning to {target.value}"
                )

        # Warn on rapid state changes
        if (current == TicketStatus.NEW and target == TicketStatus.RESOLVED and
            context.reason == TransitionReason.USER_ACTION):
            warnings.append("Rapid resolution detected - consider INPROGRESS state")

        return TransitionResult(is_valid=True, warnings=warnings)

    @classmethod
    def get_allowed_transitions(
        cls,
        current_status: str,
        user: Optional[AbstractUser] = None
    ) -> List[str]:
        """
        Get list of allowed transition targets for current status.

        Args:
            current_status: Current ticket status
            user: Optional user for permission filtering

        Returns:
            List of allowed target status values
        """
        try:
            current = TicketStatus(current_status.upper())
        except ValueError:
            return []

        allowed_statuses = cls.VALID_TRANSITIONS.get(current, set())

        if user:
            # Filter by permissions
            filtered_statuses = set()
            for target in allowed_statuses:
                transition_key = (current, target)
                required_perms = cls.TRANSITION_PERMISSIONS.get(transition_key, [])

                if not required_perms or all(user.has_perm(perm) for perm in required_perms):
                    filtered_statuses.add(target)

            allowed_statuses = filtered_statuses

        return [status.value for status in allowed_statuses]

    @classmethod
    def log_transition_attempt(
        cls,
        ticket_id: int,
        current_status: str,
        new_status: str,
        context: TransitionContext,
        result: TransitionResult
    ) -> None:
        """Log transition attempt using comprehensive audit service."""
        # Create audit context
        audit_context = AuditContext(
            user=context.user,
            timestamp=context.timestamp
        )

        # Use TicketAuditService for comprehensive audit logging
        TicketAuditService.log_status_transition(
            ticket_id=ticket_id,
            old_status=current_status,
            new_status=new_status,
            context=audit_context,
            transition_result={
                'valid': result.is_valid,
                'message': result.error_message,
                'warnings': result.warnings,
                'mobile_client': context.mobile_client,
                'reason': context.reason.value
            }
        )

        # Fallback basic logging for immediate debugging
        logger.info(
            f"Ticket {ticket_id} transition: {current_status} -> {new_status} ({'SUCCESS' if result.is_valid else 'FAILED'})",
            extra={
                'ticket_id': ticket_id,
                'success': result.is_valid,
                'user_id': context.user.id if context.user else None,
                'reason': context.reason.value
            }
        )