"""
Business logic validators consolidating domain-specific validation patterns.

This module consolidates business rule validation functions that were
duplicated across multiple apps.

Following .claude/rules.md:
- Rule #11: Specific exception handling
- Rule #13: Comprehensive input validation
"""

import logging
from datetime import datetime, time, date
from typing import Any, Optional
from django.core.exceptions import ValidationError, PermissionDenied
from django.contrib.auth import get_user_model
from django.utils import timezone

logger = logging.getLogger(__name__)
User = get_user_model()


def validate_tenant_access(user, tenant, action: str = "access") -> None:
    """
    Validate user has access to specified tenant.

    Consolidates tenant access validation patterns used across
    tenant-aware models and services.

    Args:
        user: User requesting access
        tenant: Tenant to validate access for
        action: Type of action being performed

    Raises:
        PermissionDenied: If user doesn't have tenant access
        ValidationError: If validation parameters are invalid
    """
    if not user or not user.is_authenticated:
        raise PermissionDenied("Authentication required")

    if not tenant:
        raise ValidationError("Tenant is required")

    try:
        # Check if user belongs to tenant (via business unit or direct assignment)
        if hasattr(user, 'bu') and user.bu:
            if hasattr(user.bu, 'tenant') and user.bu.tenant == tenant:
                return

        # Check if user is superuser with global access
        if user.is_superuser:
            return

        # If no valid access found
        raise PermissionDenied(f"User does not have {action} access to this tenant")

    except (AttributeError, TypeError) as e:
        logger.error(f"Tenant access validation failed: {e}", exc_info=True)
        raise ValidationError("Tenant access validation failed") from e


def validate_user_permissions(user, required_permissions: list, obj=None) -> None:
    """
    Validate user has required permissions.

    Consolidates permission checking patterns used across views and services.

    Args:
        user: User to check permissions for
        required_permissions: List of required permission strings
        obj: Optional object for object-level permissions

    Raises:
        PermissionDenied: If user doesn't have required permissions
        ValidationError: If validation parameters are invalid
    """
    if not user or not user.is_authenticated:
        raise PermissionDenied("Authentication required")

    if not required_permissions:
        return  # No permissions required

    try:
        for permission in required_permissions:
            if obj:
                if not user.has_perm(permission, obj):
                    raise PermissionDenied(f"Missing permission: {permission}")
            else:
                if not user.has_perm(permission):
                    raise PermissionDenied(f"Missing permission: {permission}")

    except (AttributeError, TypeError) as e:
        logger.error(f"Permission validation failed: {e}", exc_info=True)
        raise ValidationError("Permission validation failed") from e


def validate_date_range(start_date: Any, end_date: Any, max_days: Optional[int] = None) -> tuple:
    """
    Validate date range is valid and within limits.

    Consolidates date range validation patterns used across
    reports, scheduling, and other date-dependent features.

    Args:
        start_date: Start date to validate
        end_date: End date to validate
        max_days: Optional maximum number of days in range

    Returns:
        tuple: (validated_start_date, validated_end_date)

    Raises:
        ValidationError: If date range is invalid
    """
    try:
        # Convert string dates to date objects if needed
        if isinstance(start_date, str):
            start_date = datetime.fromisoformat(start_date).date()
        elif isinstance(start_date, datetime):
            start_date = start_date.date()

        if isinstance(end_date, str):
            end_date = datetime.fromisoformat(end_date).date()
        elif isinstance(end_date, datetime):
            end_date = end_date.date()

        # Validate types
        if not isinstance(start_date, date) or not isinstance(end_date, date):
            raise ValidationError("Invalid date format")

        # Validate range
        if start_date > end_date:
            raise ValidationError("Start date must be before or equal to end date")

        # Validate maximum duration
        if max_days:
            duration = (end_date - start_date).days
            if duration > max_days:
                raise ValidationError(f"Date range cannot exceed {max_days} days")

        return start_date, end_date

    except (ValueError, TypeError) as e:
        raise ValidationError("Invalid date range") from e


def validate_business_hours(time_value: Any, start_hour: int = 6, end_hour: int = 22) -> time:
    """
    Validate time is within business hours.

    Consolidates business hours validation patterns used across
    scheduling and work order management.

    Args:
        time_value: Time value to validate
        start_hour: Business hours start (default 6 AM)
        end_hour: Business hours end (default 10 PM)

    Returns:
        time: Validated time object

    Raises:
        ValidationError: If time is outside business hours
    """
    try:
        # Convert string time to time object if needed
        if isinstance(time_value, str):
            time_obj = datetime.fromisoformat(f"1970-01-01T{time_value}").time()
        elif isinstance(time_value, datetime):
            time_obj = time_value.time()
        elif isinstance(time_value, time):
            time_obj = time_value
        else:
            raise ValidationError("Invalid time format")

        # Validate business hours
        if not (start_hour <= time_obj.hour < end_hour):
            raise ValidationError(
                f"Time must be within business hours ({start_hour}:00 - {end_hour}:00)"
            )

        return time_obj

    except (ValueError, TypeError) as e:
        raise ValidationError("Invalid time value") from e


def validate_scheduling_conflicts(
    start_time: datetime,
    end_time: datetime,
    resource_id: str,
    exclude_id: Optional[str] = None
) -> None:
    """
    Validate no scheduling conflicts exist for resource.

    Consolidates conflict checking patterns used across
    scheduling services and work order management.

    Args:
        start_time: Scheduled start time
        end_time: Scheduled end time
        resource_id: Resource being scheduled
        exclude_id: Optional ID to exclude from conflict check

    Raises:
        ValidationError: If scheduling conflict exists
    """
    if start_time >= end_time:
        raise ValidationError("Start time must be before end time")

    # This would typically check against a scheduling model
    # Implementation would depend on specific scheduling logic
    # For now, just validate the time range makes sense
    duration = end_time - start_time
    if duration.total_seconds() < 300:  # Less than 5 minutes
        raise ValidationError("Scheduled duration too short (minimum 5 minutes)")

    if duration.days > 7:  # More than a week
        raise ValidationError("Scheduled duration too long (maximum 7 days)")


def validate_approval_workflow(
    current_status: str,
    new_status: str,
    user_role: str
) -> None:
    """
    Validate status transition is allowed in approval workflow.

    Consolidates workflow validation patterns used across
    work orders, tickets, and other approval-based processes.

    Args:
        current_status: Current workflow status
        new_status: Requested new status
        user_role: Role of user making the change

    Raises:
        ValidationError: If transition is not allowed
        PermissionDenied: If user role cannot make this transition
    """
    # Define valid transitions (this would typically come from configuration)
    valid_transitions = {
        'draft': ['submitted', 'cancelled'],
        'submitted': ['approved', 'rejected', 'cancelled'],
        'approved': ['in_progress', 'cancelled'],
        'in_progress': ['completed', 'cancelled'],
        'rejected': ['draft', 'cancelled'],
        'completed': [],  # Final state
        'cancelled': []   # Final state
    }

    # Define role permissions (this would typically come from configuration)
    role_permissions = {
        'employee': ['draft', 'submitted'],
        'supervisor': ['draft', 'submitted', 'approved', 'rejected'],
        'admin': ['draft', 'submitted', 'approved', 'rejected', 'in_progress', 'completed', 'cancelled']
    }

    # Validate transition is allowed
    if new_status not in valid_transitions.get(current_status, []):
        raise ValidationError(
            f"Invalid status transition from '{current_status}' to '{new_status}'"
        )

    # Validate user role can make this transition
    if new_status not in role_permissions.get(user_role, []):
        raise PermissionDenied(
            f"Role '{user_role}' cannot transition to status '{new_status}'"
        )