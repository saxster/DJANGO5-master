"""
Sync Status State Machine - Centralized status transition validation

Consolidates different status validation implementations found in:
- TaskSyncService (apps/activity:112-140)
- TicketSyncService (apps/y_helpdesk:111-145)
- AttendanceSyncService (server-wins policy)

Following .claude/rules.md:
- Rule #7: Service <150 lines
- Rule #11: Specific exception handling
"""

import logging
from enum import Enum
from typing import Dict, List, Set, Optional, Tuple
from dataclasses import dataclass
from django.core.exceptions import ValidationError
from django.core.cache import cache

logger = logging.getLogger(__name__)


class TransitionPolicy(Enum):
    """Defines how transitions are enforced."""
    STRICT = "strict"          # Only defined transitions allowed
    PERMISSIVE = "permissive"  # Allow any transition not explicitly forbidden
    WORKFLOW = "workflow"      # Complex business rules with conditions


@dataclass
class StatusTransition:
    """Represents a single status transition rule."""
    from_status: str
    to_status: str
    conditions: Optional[Dict] = None
    requires_permission: Optional[str] = None
    description: str = ""


@dataclass
class TransitionResult:
    """Result of transition validation."""
    allowed: bool
    reason: str = ""
    warnings: List[str] = None

    def __post_init__(self):
        if self.warnings is None:
            self.warnings = []


class SyncStatusStateMachine:
    """
    Centralized state machine for sync status transitions.

    Provides configurable status validation for different domains
    with support for business rules and permission checking.
    """

    def __init__(self):
        """Initialize state machine with domain configurations."""
        self._domain_configs: Dict[str, Dict] = {}
        self._load_default_configurations()

    def register_domain(
        self,
        domain: str,
        transitions: List[StatusTransition],
        policy: TransitionPolicy = TransitionPolicy.STRICT,
        default_status: str = "NEW"
    ) -> None:
        """
        Register status transitions for a domain.

        Args:
            domain: Domain name (task, ticket, attendance, etc.)
            transitions: List of allowed transitions
            policy: How strictly to enforce transitions
            default_status: Default status for new records
        """
        # Build transition map for fast lookup
        transition_map = {}
        for transition in transitions:
            from_status = transition.from_status.upper()
            to_status = transition.to_status.upper()

            if from_status not in transition_map:
                transition_map[from_status] = []

            transition_map[from_status].append(transition)

        self._domain_configs[domain] = {
            'transitions': transition_map,
            'policy': policy,
            'default_status': default_status.upper(),
            'all_statuses': self._extract_all_statuses(transitions)
        }

        logger.info(f"Registered {len(transitions)} transitions for domain '{domain}'")

    def validate_transition(
        self,
        domain: str,
        from_status: str,
        to_status: str,
        context: Optional[Dict] = None
    ) -> TransitionResult:
        """
        Validate status transition for domain.

        Args:
            domain: Domain name
            from_status: Current status
            to_status: Proposed status
            context: Additional context for business rules

        Returns:
            TransitionResult with validation outcome
        """
        try:
            if domain not in self._domain_configs:
                return TransitionResult(
                    allowed=True,
                    reason=f"No transitions configured for domain '{domain}'"
                )

            config = self._domain_configs[domain]
            from_upper = from_status.upper() if from_status else config['default_status']
            to_upper = to_status.upper() if to_status else config['default_status']

            # Same status is always allowed
            if from_upper == to_upper:
                return TransitionResult(allowed=True, reason="Same status")

            # Check if transition exists
            allowed_transitions = config['transitions'].get(from_upper, [])
            matching_transition = None

            for transition in allowed_transitions:
                if transition.to_status.upper() == to_upper:
                    matching_transition = transition
                    break

            if not matching_transition:
                if config['policy'] == TransitionPolicy.PERMISSIVE:
                    return TransitionResult(
                        allowed=True,
                        reason="Permissive policy allows undefined transitions",
                        warnings=[f"Transition {from_status} → {to_status} not explicitly defined"]
                    )
                else:
                    return TransitionResult(
                        allowed=False,
                        reason=f"Transition {from_status} → {to_status} not allowed"
                    )

            # Check conditions if present
            if matching_transition.conditions:
                condition_result = self._evaluate_conditions(
                    matching_transition.conditions,
                    context or {}
                )
                if not condition_result.allowed:
                    return condition_result

            # Check permissions if required
            if matching_transition.requires_permission:
                permission_result = self._check_permission(
                    matching_transition.requires_permission,
                    context or {}
                )
                if not permission_result.allowed:
                    return permission_result

            return TransitionResult(
                allowed=True,
                reason=f"Valid transition: {matching_transition.description or 'allowed'}"
            )

        except Exception as e:
            logger.error(f"Error validating transition: {e}", exc_info=True)
            return TransitionResult(
                allowed=False,
                reason=f"Validation error: {str(e)}"
            )

    def get_allowed_transitions(self, domain: str, from_status: str) -> List[str]:
        """
        Get list of allowed transitions from current status.

        Args:
            domain: Domain name
            from_status: Current status

        Returns:
            List of allowed target statuses
        """
        if domain not in self._domain_configs:
            return []

        config = self._domain_configs[domain]
        from_upper = from_status.upper() if from_status else config['default_status']

        transitions = config['transitions'].get(from_upper, [])
        return [t.to_status for t in transitions]

    def get_domain_statuses(self, domain: str) -> Set[str]:
        """
        Get all valid statuses for domain.

        Args:
            domain: Domain name

        Returns:
            Set of valid status values
        """
        if domain not in self._domain_configs:
            return set()

        return self._domain_configs[domain]['all_statuses']

    def _load_default_configurations(self) -> None:
        """Load default domain configurations."""

        # Task/JobNeed status transitions (from TaskSyncService)
        task_transitions = [
            StatusTransition('ASSIGNED', 'INPROGRESS', description='Start working on task'),
            StatusTransition('ASSIGNED', 'STANDBY', description='Put task on hold'),
            StatusTransition('INPROGRESS', 'COMPLETED', description='Complete task'),
            StatusTransition('INPROGRESS', 'PARTIALLYCOMPLETED', description='Partial completion'),
            StatusTransition('INPROGRESS', 'STANDBY', description='Put in progress task on hold'),
            StatusTransition('PARTIALLYCOMPLETED', 'COMPLETED', description='Complete remaining work'),
            StatusTransition('PARTIALLYCOMPLETED', 'INPROGRESS', description='Resume partial work'),
            StatusTransition('PARTIALLYCOMPLETED', 'STANDBY', description='Put partial task on hold'),
            StatusTransition('STANDBY', 'ASSIGNED', description='Reactivate assigned task'),
            StatusTransition('STANDBY', 'INPROGRESS', description='Resume work from standby'),
            StatusTransition('COMPLETED', 'STANDBY', description='Reopen completed task'),
        ]

        # Ticket status transitions (from TicketSyncService)
        ticket_transitions = [
            StatusTransition('NEW', 'OPEN', description='Open new ticket'),
            StatusTransition('OPEN', 'INPROGRESS', description='Start working on ticket'),
            StatusTransition('OPEN', 'ONHOLD', description='Put ticket on hold'),
            StatusTransition('OPEN', 'CANCELLED', description='Cancel open ticket'),
            StatusTransition('INPROGRESS', 'RESOLVED', description='Resolve ticket'),
            StatusTransition('INPROGRESS', 'ONHOLD', description='Put in-progress ticket on hold'),
            StatusTransition('INPROGRESS', 'CANCELLED', description='Cancel in-progress ticket'),
            StatusTransition('ONHOLD', 'INPROGRESS', description='Resume work on ticket'),
            StatusTransition('ONHOLD', 'CANCELLED', description='Cancel held ticket'),
            StatusTransition('RESOLVED', 'CLOSED', description='Close resolved ticket'),
            StatusTransition('RESOLVED', 'OPEN', description='Reopen resolved ticket'),
        ]

        # Attendance transitions (server-wins, minimal transitions)
        attendance_transitions = [
            StatusTransition('PENDING', 'VERIFIED', description='Verify attendance record'),
            StatusTransition('PENDING', 'REJECTED', description='Reject attendance record'),
            StatusTransition('VERIFIED', 'CORRECTED', description='Correct verified record'),
            StatusTransition('REJECTED', 'PENDING', description='Re-submit rejected record'),
        ]

        # Register default domains
        self.register_domain('task', task_transitions, TransitionPolicy.STRICT, 'ASSIGNED')
        self.register_domain('ticket', ticket_transitions, TransitionPolicy.STRICT, 'NEW')
        self.register_domain('attendance', attendance_transitions, TransitionPolicy.WORKFLOW, 'PENDING')

    def _extract_all_statuses(self, transitions: List[StatusTransition]) -> Set[str]:
        """Extract all unique statuses from transitions."""
        statuses = set()
        for transition in transitions:
            statuses.add(transition.from_status.upper())
            statuses.add(transition.to_status.upper())
        return statuses

    def _evaluate_conditions(self, conditions: Dict, context: Dict) -> TransitionResult:
        """
        Evaluate transition conditions.

        Args:
            conditions: Condition rules to evaluate
            context: Context data for evaluation

        Returns:
            TransitionResult indicating if conditions are met
        """
        # Simple condition evaluation - can be extended for complex rules
        for key, expected_value in conditions.items():
            actual_value = context.get(key)
            if actual_value != expected_value:
                return TransitionResult(
                    allowed=False,
                    reason=f"Condition not met: {key} = {actual_value}, expected {expected_value}"
                )

        return TransitionResult(allowed=True, reason="All conditions satisfied")

    def _check_permission(self, permission: str, context: Dict) -> TransitionResult:
        """
        Check if user has required permission.

        Args:
            permission: Permission name to check
            context: Context containing user data

        Returns:
            TransitionResult indicating permission status
        """
        user = context.get('user')
        if not user:
            return TransitionResult(
                allowed=False,
                reason="User context required for permission check"
            )

        # Simple permission check - integrate with your permission system
        if hasattr(user, 'has_perm') and user.has_perm(permission):
            return TransitionResult(allowed=True, reason="Permission granted")

        # Admin users can bypass most restrictions
        if getattr(user, 'isadmin', False):
            return TransitionResult(
                allowed=True,
                reason="Admin override",
                warnings=[f"Admin bypassed permission: {permission}"]
            )

        return TransitionResult(
            allowed=False,
            reason=f"User lacks required permission: {permission}"
        )


# Global instance
sync_state_machine = SyncStatusStateMachine()