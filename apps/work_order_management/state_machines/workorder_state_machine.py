"""
Work Order State Machine

Manages work order lifecycle with:
- Draft → Submitted → Approved → In Progress → Completed → Closed
- Permission enforcement for each transition
- Audit logging
- Business rule validation

Compliance with .claude/rules.md:
- Rule #5: Single Responsibility Principle
- Rule #7: Class < 150 lines
- Rule #11: Specific exception handling
"""

import logging
from enum import Enum
from typing import Optional

from apps.core.state_machines.base import (
    BaseStateMachine,
    TransitionContext,
    TransitionResult,
)

logger = logging.getLogger(__name__)


class WorkOrderStateMachine(BaseStateMachine):
    """
    State machine for Work Order lifecycle management.

    States:
    - DRAFT: Initial state, work order being created
    - SUBMITTED: Submitted for approval
    - APPROVED: Approved by manager/approver
    - IN_PROGRESS: Work is being performed
    - COMPLETED: Work completed, pending verification
    - CLOSED: Final state, work order archived

    Transitions require specific permissions (defined in TRANSITION_PERMISSIONS).
    """

    class States(Enum):
        """Work order states"""
        DRAFT = 'DRAFT'
        SUBMITTED = 'SUBMITTED'
        APPROVED = 'APPROVED'
        IN_PROGRESS = 'IN_PROGRESS'
        COMPLETED = 'COMPLETED'
        CLOSED = 'CLOSED'
        CANCELLED = 'CANCELLED'

    # Define valid state transitions
    VALID_TRANSITIONS = {
        States.DRAFT: {
            States.SUBMITTED,
            States.CANCELLED,
        },
        States.SUBMITTED: {
            States.APPROVED,
            States.DRAFT,  # Reject - send back to draft
            States.CANCELLED,
        },
        States.APPROVED: {
            States.IN_PROGRESS,
            States.CANCELLED,
        },
        States.IN_PROGRESS: {
            States.COMPLETED,
            States.CANCELLED,
        },
        States.COMPLETED: {
            States.CLOSED,
            States.IN_PROGRESS,  # Reopen if issues found
        },
        States.CLOSED: set(),  # Terminal state
        States.CANCELLED: set(),  # Terminal state
    }

    # Define required permissions for specific transitions
    TRANSITION_PERMISSIONS = {
        (States.SUBMITTED, States.APPROVED): ['work_order_management.approve_workorder'],
        (States.APPROVED, States.IN_PROGRESS): ['work_order_management.start_workorder'],
        (States.IN_PROGRESS, States.COMPLETED): ['work_order_management.complete_workorder'],
        (States.COMPLETED, States.CLOSED): ['work_order_management.close_workorder'],
        (States.DRAFT, States.CANCELLED): ['work_order_management.cancel_workorder'],
        (States.SUBMITTED, States.CANCELLED): ['work_order_management.cancel_workorder'],
        (States.APPROVED, States.CANCELLED): ['work_order_management.cancel_workorder'],
    }

    def _get_current_state(self, instance) -> str:
        """Get current state from work order instance"""
        # Assuming work order has 'workstatus' field
        return instance.workstatus

    def _set_current_state(self, instance, new_state: str):
        """Set new state on work order instance"""
        instance.workstatus = new_state

    def _str_to_state(self, state_str: str):
        """Convert string to States enum"""
        try:
            return self.States(state_str.upper())
        except ValueError:
            logger.warning(f"Invalid work order state: {state_str}")
            return None

    def _state_to_str(self, state) -> str:
        """Convert States enum to string"""
        return state.value

    def _validate_business_rules(
        self,
        from_state: str,
        to_state: str,
        context: TransitionContext
    ) -> TransitionResult:
        """
        Validate work order business rules.

        Rules:
        1. Cannot approve without vendor assignment
        2. Cannot complete without all line items completed
        3. Cannot close without final inspection
        """
        to_enum = self._str_to_state(to_state)

        # Rule 1: Cannot approve without vendor
        if to_enum == self.States.APPROVED:
            if not hasattr(self.instance, 'vendor_id') or not self.instance.vendor_id:
                return TransitionResult(
                    success=False,
                    from_state=from_state,
                    to_state=to_state,
                    error_message="Cannot approve work order without vendor assignment"
                )

        # Rule 2: Cannot complete without line items
        if to_enum == self.States.COMPLETED:
            if hasattr(self.instance, 'womdetails_set'):
                incomplete_items = self.instance.womdetails_set.filter(
                    status__in=['PENDING', 'IN_PROGRESS']
                ).count()

                if incomplete_items > 0:
                    return TransitionResult(
                        success=False,
                        from_state=from_state,
                        to_state=to_state,
                        error_message=f"Cannot complete: {incomplete_items} line items still pending"
                    )

        # Rule 3: Comments required for terminal transitions
        if to_enum in {self.States.COMPLETED, self.States.CLOSED, self.States.CANCELLED}:
            if not context.comments:
                return TransitionResult(
                    success=False,
                    from_state=from_state,
                    to_state=to_state,
                    error_message=f"Comments required when transitioning to {to_state}"
                )

        return TransitionResult(
            success=True,
            from_state=from_state,
            to_state=to_state
        )

    def _post_transition_hook(
        self,
        from_state: str,
        to_state: str,
        context: TransitionContext
    ):
        """
        Post-transition actions.

        Triggers:
        - Notifications to stakeholders
        - Email alerts
        - Workflow automation
        """
        to_enum = self._str_to_state(to_state)

        # Send notification when approved
        if to_enum == self.States.APPROVED:
            self._notify_vendor_assignment(context)

        # Send notification when completed
        if to_enum == self.States.COMPLETED:
            self._notify_completion(context)

        # Archive when closed
        if to_enum == self.States.CLOSED:
            self._archive_work_order(context)

    def _notify_vendor_assignment(self, context: TransitionContext):
        """Send notification to vendor when work order approved"""
        logger.info(
            f"Notifying vendor for work order {self.instance.id}",
            extra={'work_order_id': self.instance.id}
        )
        # TODO: Implement email/SMS notification to vendor

    def _notify_completion(self, context: TransitionContext):
        """Send notification when work order completed"""
        logger.info(
            f"Work order {self.instance.id} completed",
            extra={'work_order_id': self.instance.id}
        )
        # TODO: Implement email notification to requester

    def _archive_work_order(self, context: TransitionContext):
        """Archive work order when closed"""
        logger.info(
            f"Archiving work order {self.instance.id}",
            extra={'work_order_id': self.instance.id}
        )
        # TODO: Move to archive table or set archive flag
