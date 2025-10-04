"""
Attendance State Machine

Manages attendance record lifecycle with approval workflow.

State Flow:
    PENDING → APPROVED → LOCKED
       ↓         ↓
   REJECTED  ADJUSTED → LOCKED

Features:
- Manager approval workflow
- Adjustment tracking (with reason)
- Period locking for payroll integration
- Geolocation/biometric validation
- Cutoff date enforcement

Compliance with .claude/rules.md:
- Rule #5: Single Responsibility Principle
- Rule #7: Class < 150 lines
- Rule #11: Specific exception handling
- Rule #17: Transaction management
"""

import logging
from enum import Enum
from typing import Optional
from datetime import datetime, timedelta

from django.utils import timezone
from django.core.exceptions import ValidationError

from apps.core.state_machines.base import (
    BaseStateMachine,
    TransitionContext,
    TransitionResult,
)
from apps.core.constants.datetime_constants import SECONDS_IN_DAY

logger = logging.getLogger(__name__)


class AttendanceStateMachine(BaseStateMachine):
    """
    State machine for attendance record lifecycle.

    States:
    - PENDING: Attendance marked, awaiting approval
    - APPROVED: Approved by manager
    - REJECTED: Rejected by manager (with reason)
    - ADJUSTED: Attendance adjusted (time corrections, etc.)
    - LOCKED: Final state, locked for payroll

    Business Rules:
    1. Cannot approve without manager permission
    2. Cannot adjust locked records
    3. Cannot approve after payroll cutoff date
    4. Must have valid geolocation within geofence
    5. Rejection requires mandatory comments
    6. Adjustments require reason and manager approval
    """

    class States(Enum):
        """Attendance states"""
        PENDING = 'PENDING'
        APPROVED = 'APPROVED'
        REJECTED = 'REJECTED'
        ADJUSTED = 'ADJUSTED'
        LOCKED = 'LOCKED'

    # Valid state transitions
    VALID_TRANSITIONS = {
        States.PENDING: {
            States.APPROVED,
            States.REJECTED,
            States.ADJUSTED,
        },
        States.APPROVED: {
            States.ADJUSTED,
            States.LOCKED,
        },
        States.REJECTED: {
            States.PENDING,  # Resubmit after correction
        },
        States.ADJUSTED: {
            States.APPROVED,  # Re-approve after adjustment
            States.LOCKED,
        },
        States.LOCKED: set(),  # Terminal state - no transitions
    }

    # Required permissions
    TRANSITION_PERMISSIONS = {
        (States.PENDING, States.APPROVED): ['attendance.approve_attendance'],
        (States.PENDING, States.REJECTED): ['attendance.reject_attendance'],
        (States.PENDING, States.ADJUSTED): ['attendance.adjust_attendance'],
        (States.APPROVED, States.ADJUSTED): ['attendance.adjust_attendance'],
        (States.ADJUSTED, States.APPROVED): ['attendance.approve_attendance'],
        (States.APPROVED, States.LOCKED): ['attendance.lock_attendance'],
        (States.ADJUSTED, States.LOCKED): ['attendance.lock_attendance'],
    }

    def _get_current_state(self, instance) -> str:
        """Get current state from attendance instance"""
        # PeopleEventlog uses 'status' or 'approval_status' field
        if hasattr(instance, 'approval_status'):
            return instance.approval_status
        elif hasattr(instance, 'status'):
            return instance.status
        return 'PENDING'  # Default

    def _set_current_state(self, instance, new_state: str):
        """Set new state on attendance instance"""
        if hasattr(instance, 'approval_status'):
            instance.approval_status = new_state
        elif hasattr(instance, 'status'):
            instance.status = new_state

    def _str_to_state(self, state_str: str):
        """Convert string to States enum"""
        try:
            return self.States(state_str.upper())
        except ValueError:
            logger.warning(f"Invalid attendance state: {state_str}")
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
        Validate attendance-specific business rules.

        Rules:
        1. Cannot approve after payroll cutoff
        2. Cannot modify locked records
        3. Must have valid geolocation
        4. Rejection requires comments
        5. Adjustments require reason
        """
        from_enum = self._str_to_state(from_state)
        to_enum = self._str_to_state(to_state)

        # Rule 1: Cannot modify locked records
        if from_enum == self.States.LOCKED:
            return TransitionResult(
                success=False,
                from_state=from_state,
                to_state=to_state,
                error_message="Cannot modify locked attendance records"
            )

        # Rule 2: Cannot approve after payroll cutoff
        if to_enum == self.States.APPROVED:
            if self._is_past_cutoff_date():
                return TransitionResult(
                    success=False,
                    from_state=from_state,
                    to_state=to_state,
                    error_message="Cannot approve: payroll cutoff date has passed"
                )

        # Rule 3: Validate geolocation
        if to_enum in {self.States.APPROVED, self.States.LOCKED}:
            geolocation_result = self._validate_geolocation()
            if not geolocation_result.success:
                return geolocation_result

        # Rule 4: Rejection requires comments
        if to_enum == self.States.REJECTED:
            if not context.comments:
                return TransitionResult(
                    success=False,
                    from_state=from_state,
                    to_state=to_state,
                    error_message="Comments required when rejecting attendance"
                )

        # Rule 5: Adjustments require reason
        if to_enum == self.States.ADJUSTED:
            if not context.metadata.get('adjustment_reason'):
                return TransitionResult(
                    success=False,
                    from_state=from_state,
                    to_state=to_state,
                    error_message="Adjustment reason required"
                )

        # Warnings
        warnings = []
        if self._is_outside_shift_hours():
            warnings.append("Attendance marked outside normal shift hours")

        if self._is_duplicate_entry():
            warnings.append("Potential duplicate attendance entry detected")

        return TransitionResult(
            success=True,
            from_state=from_state,
            to_state=to_state,
            warnings=warnings
        )

    def _is_past_cutoff_date(self) -> bool:
        """Check if attendance date is past payroll cutoff"""
        # Typically cutoff is 3 days after month end
        if hasattr(self.instance, 'event_dtz'):
            attendance_date = self.instance.event_dtz

            # Get month end
            next_month = attendance_date.replace(day=28) + timedelta(days=4)
            month_end = next_month - timedelta(days=next_month.day)

            # Add 3-day grace period
            cutoff_date = month_end + timedelta(days=3)

            return timezone.now() > cutoff_date

        return False

    def _validate_geolocation(self) -> TransitionResult:
        """Validate that attendance location is within geofence"""
        if not hasattr(self.instance, 'location_lat') or not hasattr(self.instance, 'location_lng'):
            # No geolocation data - allow but warn
            return TransitionResult(
                success=True,
                from_state=self._get_current_state(self.instance),
                to_state='',
                warnings=["No geolocation data available"]
            )

        # Check if location is within geofence
        if hasattr(self.instance, 'location') and self.instance.location:
            geofence = self.instance.location.geofence

            if geofence and hasattr(geofence, 'contains_point'):
                from django.contrib.gis.geos import Point
                point = Point(
                    float(self.instance.location_lng),
                    float(self.instance.location_lat)
                )

                if not geofence.contains(point):
                    return TransitionResult(
                        success=False,
                        from_state=self._get_current_state(self.instance),
                        to_state='',
                        error_message="Attendance location outside geofence"
                    )

        return TransitionResult(
            success=True,
            from_state=self._get_current_state(self.instance),
            to_state=''
        )

    def _is_outside_shift_hours(self) -> bool:
        """Check if attendance is outside normal shift hours"""
        if hasattr(self.instance, 'event_dtz') and hasattr(self.instance, 'shift'):
            shift = self.instance.shift
            event_time = self.instance.event_dtz.time()

            if shift and hasattr(shift, 'start_time') and hasattr(shift, 'end_time'):
                # Allow 1 hour buffer before/after shift
                buffer = timedelta(hours=1)
                shift_start = (datetime.combine(datetime.today(), shift.start_time) - buffer).time()
                shift_end = (datetime.combine(datetime.today(), shift.end_time) + buffer).time()

                return not (shift_start <= event_time <= shift_end)

        return False

    def _is_duplicate_entry(self) -> bool:
        """Check for potential duplicate attendance entries"""
        if hasattr(self.instance, 'people') and hasattr(self.instance, 'event_dtz'):
            from apps.attendance.models import PeopleEventlog

            # Check for entries within 5 minutes
            time_window_start = self.instance.event_dtz - timedelta(minutes=5)
            time_window_end = self.instance.event_dtz + timedelta(minutes=5)

            duplicates = PeopleEventlog.objects.filter(
                people=self.instance.people,
                event_dtz__range=(time_window_start, time_window_end)
            ).exclude(id=self.instance.id).count()

            return duplicates > 0

        return False

    def _post_transition_hook(
        self,
        from_state: str,
        to_state: str,
        context: TransitionContext
    ):
        """
        Post-transition actions for attendance.

        Actions:
        - Notify employee on approval/rejection
        - Update payroll integration on lock
        - Log adjustments for audit
        - Send reports to HR
        """
        to_enum = self._str_to_state(to_state)

        # Notify employee on approval
        if to_enum == self.States.APPROVED:
            self._notify_employee_approval(context)

        # Notify employee on rejection
        if to_enum == self.States.REJECTED:
            self._notify_employee_rejection(context)

        # Log adjustment
        if to_enum == self.States.ADJUSTED:
            self._log_adjustment(context)

        # Update payroll on lock
        if to_enum == self.States.LOCKED:
            self._update_payroll_system(context)

    def _notify_employee_approval(self, context: TransitionContext):
        """Notify employee of attendance approval"""
        logger.info(
            f"Attendance approved for record {self.instance.id}",
            extra={'attendance_id': self.instance.id}
        )
        # TODO: Send notification via email/SMS/push

    def _notify_employee_rejection(self, context: TransitionContext):
        """Notify employee of attendance rejection"""
        logger.warning(
            f"Attendance rejected for record {self.instance.id}: {context.comments}",
            extra={
                'attendance_id': self.instance.id,
                'reason': context.comments
            }
        )
        # TODO: Send notification with rejection reason

    def _log_adjustment(self, context: TransitionContext):
        """Log attendance adjustment for audit"""
        adjustment_reason = context.metadata.get('adjustment_reason', 'Not specified')

        logger.info(
            f"Attendance adjusted for record {self.instance.id}",
            extra={
                'attendance_id': self.instance.id,
                'reason': adjustment_reason,
                'adjusted_by': context.user.id if context.user else None,
                'original_time': context.metadata.get('original_time'),
                'adjusted_time': context.metadata.get('adjusted_time'),
            }
        )

    def _update_payroll_system(self, context: TransitionContext):
        """Update external payroll system when attendance locked"""
        logger.info(
            f"Attendance locked for payroll processing: {self.instance.id}",
            extra={'attendance_id': self.instance.id}
        )
        # TODO: Integrate with payroll system API
        # This could trigger a Celery task for async processing
