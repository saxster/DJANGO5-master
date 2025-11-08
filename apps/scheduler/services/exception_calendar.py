"""
Scheduler Exception Calendar Service

Manages scheduling blackout windows, holidays, and maintenance periods.
Prevents scheduling during specified time windows and provides
rescheduling with audit trail.

Features:
- Holiday calendar support
- Maintenance window blocking
- Event-based blackouts
- Automatic rescheduling suggestions
- Audit logging with reason tracking

Stores configuration in TypeAssist.other_data with structure:
{
    "exception_calendar": {
        "holidays": [{"date": "2025-12-25", "name": "Christmas", "recurring": true}],
        "blackout_windows": [{"start": "2025-11-10T00:00:00Z", "end": "2025-11-10T06:00:00Z", "reason": "HVAC Maintenance"}],
        "active": true
    }
}

Compliance: CLAUDE.md Rule #7 (file size), Rule #11 (specific exceptions)
"""

import logging
from datetime import datetime, timedelta, timezone as dt_timezone
from typing import Dict, List, Optional, Tuple

from django.core.exceptions import ValidationError, ObjectDoesNotExist
from django.db import IntegrityError

from apps.core_onboarding.models import TypeAssist
from apps.core.exceptions.patterns import DATABASE_EXCEPTIONS, JSON_EXCEPTIONS
from apps.core.utils_new.datetime_utilities import get_current_utc, convert_to_utc
from apps.core.constants.datetime_constants import SECONDS_IN_DAY

logger = logging.getLogger(__name__)


class ExceptionCalendarService:
    """
    Service for managing scheduler exception windows.
    """

    EXCEPTION_TYPES = {
        'HOLIDAY': 'Holiday',
        'MAINTENANCE': 'Scheduled Maintenance',
        'EVENT': 'Special Event',
        'BLACKOUT': 'Administrative Blackout',
    }

    @classmethod
    def is_schedulable(cls, proposed_datetime: datetime, tenant_id: int) -> Tuple[bool, Optional[str]]:
        """
        Check if a datetime is available for scheduling.

        Args:
            proposed_datetime: Datetime to check
            tenant_id: Tenant identifier

        Returns:
            Tuple of (is_available, blocking_reason)
        """
        try:
            config = cls._get_calendar_config(tenant_id)
            if not config or not config.get('active', False):
                return True, None

            utc_dt = convert_to_utc(proposed_datetime)

            if cls._is_holiday(utc_dt, config.get('holidays', [])):
                return False, "Blocked by holiday calendar"

            blocking_window = cls._find_blocking_window(
                utc_dt,
                config.get('blackout_windows', [])
            )
            if blocking_window:
                return False, f"Blocked: {blocking_window.get('reason', 'Blackout window')}"

            return True, None

        except JSON_EXCEPTIONS as e:
            logger.error(f"Calendar config parse error for tenant {tenant_id}: {e}")
            return True, None
        except (ValueError, TypeError) as e:
            logger.error(f"Invalid datetime for schedulability check: {e}")
            raise ValidationError(f"Invalid datetime: {e}")

    @classmethod
    def add_blackout_window(
        cls,
        tenant_id: int,
        start: datetime,
        end: datetime,
        reason: str,
        exception_type: str = 'BLACKOUT'
    ) -> bool:
        """
        Add a blackout window to the calendar.

        Args:
            tenant_id: Tenant identifier
            start: Window start datetime
            end: Window end datetime
            reason: Human-readable reason
            exception_type: Type from EXCEPTION_TYPES

        Returns:
            True if added successfully

        Raises:
            ValidationError: If validation fails
        """
        if exception_type not in cls.EXCEPTION_TYPES:
            raise ValidationError(f"Invalid exception type: {exception_type}")

        if start >= end:
            raise ValidationError("Start must be before end")

        try:
            type_assist = cls._get_or_create_calendar(tenant_id)
            config = type_assist.other_data.get('exception_calendar', {})

            blackout_windows = config.get('blackout_windows', [])
            blackout_windows.append({
                'start': convert_to_utc(start).isoformat(),
                'end': convert_to_utc(end).isoformat(),
                'reason': reason,
                'type': exception_type,
                'created_at': get_current_utc().isoformat(),
            })

            config['blackout_windows'] = blackout_windows
            config['active'] = True
            type_assist.other_data['exception_calendar'] = config
            type_assist.save()

            logger.info(
                f"Added blackout window for tenant {tenant_id}: "
                f"{start} to {end} ({reason})"
            )
            return True

        except DATABASE_EXCEPTIONS as e:
            logger.error(f"Database error adding blackout window: {e}", exc_info=True)
            raise ValidationError("Failed to save blackout window")

    @classmethod
    def suggest_reschedule(
        cls,
        blocked_datetime: datetime,
        tenant_id: int,
        look_ahead_days: int = 7
    ) -> Optional[datetime]:
        """
        Suggest next available scheduling slot.

        Args:
            blocked_datetime: Originally requested datetime
            tenant_id: Tenant identifier
            look_ahead_days: Days to search forward

        Returns:
            Next available datetime or None
        """
        current = convert_to_utc(blocked_datetime)
        end_search = current + timedelta(days=look_ahead_days)

        while current <= end_search:
            current += timedelta(hours=1)
            is_available, _ = cls.is_schedulable(current, tenant_id)
            if is_available:
                logger.info(
                    f"Rescheduled from {blocked_datetime} to {current} "
                    f"for tenant {tenant_id}"
                )
                return current

        logger.warning(
            f"No available slot found within {look_ahead_days} days "
            f"for tenant {tenant_id}"
        )
        return None

    @classmethod
    def _get_calendar_config(cls, tenant_id: int) -> Optional[Dict]:
        """Get exception calendar configuration for tenant."""
        try:
            type_assist = TypeAssist.objects.filter(
                tenant_id=tenant_id,
                tacode='EXCEPTION_CALENDAR'
            ).first()

            if not type_assist:
                return None

            return type_assist.other_data.get('exception_calendar', {})

        except DATABASE_EXCEPTIONS as e:
            logger.error(f"Error fetching calendar config: {e}")
            return None

    @classmethod
    def _get_or_create_calendar(cls, tenant_id: int) -> TypeAssist:
        """Get or create calendar TypeAssist record."""
        try:
            type_assist, created = TypeAssist.objects.get_or_create(
                tenant_id=tenant_id,
                tacode='EXCEPTION_CALENDAR',
                defaults={
                    'taname': 'Scheduler Exception Calendar',
                    'other_data': {'exception_calendar': {'active': True}},
                }
            )
            if created:
                logger.info(f"Created exception calendar for tenant {tenant_id}")

            return type_assist

        except DATABASE_EXCEPTIONS as e:
            logger.error(f"Error creating calendar record: {e}", exc_info=True)
            raise

    @classmethod
    def _is_holiday(cls, check_date: datetime, holidays: List[Dict]) -> bool:
        """Check if date matches any configured holiday."""
        check_str = check_date.strftime('%Y-%m-%d')

        for holiday in holidays:
            holiday_date = holiday.get('date', '')

            if holiday.get('recurring', False):
                if check_str[5:] == holiday_date[5:]:
                    return True
            else:
                if check_str == holiday_date:
                    return True

        return False

    @classmethod
    def _find_blocking_window(
        cls,
        check_datetime: datetime,
        windows: List[Dict]
    ) -> Optional[Dict]:
        """Find if datetime falls within any blackout window."""
        for window in windows:
            try:
                start = datetime.fromisoformat(window['start'].replace('Z', '+00:00'))
                end = datetime.fromisoformat(window['end'].replace('Z', '+00:00'))

                if start <= check_datetime <= end:
                    return window

            except (KeyError, ValueError) as e:
                logger.warning(f"Invalid blackout window format: {e}")
                continue

        return None
