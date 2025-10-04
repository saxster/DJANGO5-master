"""
Timezone Utilities for Multi-Timezone Mobile Applications

Handles timezone normalization and conversion for mobile clients that send
local datetime with timezone offset.

Following .claude/rules.md:
- Rule #7: Utility functions < 50 lines each
- Rule #11: Specific exception handling
- Rule #18: Timezone awareness requirements

Key Features:
- Client timezone offset normalization (-12h to +14h)
- UTC conversion with validation
- Timezone inference from offset (best guess)
- DST boundary handling
- Comprehensive validation and error handling

Usage:
    from apps.core.utils_new.timezone_utils import (
        normalize_client_timezone,
        validate_timezone_offset,
        get_timezone_name_from_offset
    )

    # Convert client datetime to UTC
    utc_datetime = normalize_client_timezone(
        naive_datetime=datetime(2025, 10, 1, 10, 30),
        client_offset_minutes=330  # IST: UTC+5:30
    )
    # Returns: datetime(2025, 10, 1, 5, 0, tzinfo=UTC)

    # Validate offset
    if validate_timezone_offset(offset_minutes):
        # Process valid offset
        pass
"""

import logging
from datetime import datetime, timedelta, timezone as dt_timezone
from typing import Optional, Tuple
from django.utils import timezone
from django.core.exceptions import ValidationError

logger = logging.getLogger(__name__)


# Timezone offset bounds (in minutes)
MIN_TIMEZONE_OFFSET = -720   # UTC-12:00 (Baker Island)
MAX_TIMEZONE_OFFSET = 840    # UTC+14:00 (Line Islands)


def validate_timezone_offset(offset_minutes: int) -> bool:
    """
    Validate that timezone offset is within valid range.

    Args:
        offset_minutes: Timezone offset in minutes from UTC

    Returns:
        True if offset is valid, False otherwise

    Examples:
        >>> validate_timezone_offset(330)   # IST: +5:30
        True
        >>> validate_timezone_offset(-300)  # EST: -5:00
        True
        >>> validate_timezone_offset(1000)  # Invalid
        False
    """
    if not isinstance(offset_minutes, (int, float)):
        logger.warning(f"Invalid offset type: {type(offset_minutes)}")
        return False

    if not (MIN_TIMEZONE_OFFSET <= offset_minutes <= MAX_TIMEZONE_OFFSET):
        logger.warning(
            f"Timezone offset {offset_minutes} out of valid range "
            f"({MIN_TIMEZONE_OFFSET} to {MAX_TIMEZONE_OFFSET})"
        )
        return False

    return True


def normalize_client_timezone(
    naive_datetime: datetime,
    client_offset_minutes: int
) -> datetime:
    """
    Convert naive client datetime with offset to UTC timezone-aware datetime.

    Mobile clients send local datetime (naive) along with timezone offset.
    This function converts to UTC for server storage.

    Args:
        naive_datetime: Naive datetime from mobile client
        client_offset_minutes: Client timezone offset from UTC in minutes
                              Positive for east of UTC, negative for west

    Returns:
        Timezone-aware datetime in UTC

    Raises:
        ValidationError: If offset is invalid or datetime conversion fails

    Examples:
        # IST (UTC+5:30) to UTC
        >>> client_time = datetime(2025, 10, 1, 16, 0)  # 4:00 PM IST
        >>> normalize_client_timezone(client_time, 330)
        datetime(2025, 10, 1, 10, 30, tzinfo=UTC)  # 10:30 AM UTC

        # PST (UTC-8:00) to UTC
        >>> client_time = datetime(2025, 10, 1, 8, 0)  # 8:00 AM PST
        >>> normalize_client_timezone(client_time, -480)
        datetime(2025, 10, 1, 16, 0, tzinfo=UTC)  # 4:00 PM UTC
    """
    # Validate offset
    if not validate_timezone_offset(client_offset_minutes):
        raise ValidationError(
            f"Invalid timezone offset: {client_offset_minutes}. "
            f"Must be between {MIN_TIMEZONE_OFFSET} and {MAX_TIMEZONE_OFFSET} minutes."
        )

    # Validate datetime
    if not isinstance(naive_datetime, datetime):
        raise ValidationError(
            f"Expected datetime object, got {type(naive_datetime)}"
        )

    try:
        # Create timezone object from offset
        client_tz = dt_timezone(timedelta(minutes=client_offset_minutes))

        # Make datetime timezone-aware in client timezone
        aware_datetime = naive_datetime.replace(tzinfo=client_tz)

        # Convert to UTC
        utc_datetime = aware_datetime.astimezone(dt_timezone.utc)

        logger.debug(
            f"Converted {naive_datetime} (offset: {client_offset_minutes}) to {utc_datetime} UTC"
        )

        return utc_datetime

    except (ValueError, TypeError, OverflowError) as e:
        logger.error(
            f"Failed to convert datetime {naive_datetime} with offset {client_offset_minutes}: {e}",
            exc_info=True
        )
        raise ValidationError(f"Datetime conversion failed: {e}") from e


def denormalize_to_client_timezone(
    utc_datetime: datetime,
    client_offset_minutes: int
) -> datetime:
    """
    Convert UTC datetime to client's local timezone.

    Inverse of normalize_client_timezone(). Used when sending data to mobile clients.

    Args:
        utc_datetime: UTC timezone-aware datetime
        client_offset_minutes: Client timezone offset from UTC in minutes

    Returns:
        Datetime in client's local timezone

    Raises:
        ValidationError: If offset is invalid

    Examples:
        >>> utc_time = datetime(2025, 10, 1, 10, 30, tzinfo=dt_timezone.utc)
        >>> denormalize_to_client_timezone(utc_time, 330)  # Convert to IST
        datetime(2025, 10, 1, 16, 0, tzinfo=...)  # 4:00 PM IST
    """
    if not validate_timezone_offset(client_offset_minutes):
        raise ValidationError(f"Invalid timezone offset: {client_offset_minutes}")

    # Ensure UTC
    if utc_datetime.tzinfo is None:
        utc_datetime = utc_datetime.replace(tzinfo=dt_timezone.utc)
    elif utc_datetime.tzinfo != dt_timezone.utc:
        utc_datetime = utc_datetime.astimezone(dt_timezone.utc)

    # Create client timezone and convert
    client_tz = dt_timezone(timedelta(minutes=client_offset_minutes))
    client_datetime = utc_datetime.astimezone(client_tz)

    return client_datetime


def get_timezone_name_from_offset(offset_minutes: int) -> str:
    """
    Get timezone name/abbreviation from offset (best guess).

    Note: Multiple timezones may have same offset. This returns the most common one.

    Args:
        offset_minutes: Timezone offset in minutes

    Returns:
        Timezone name/abbreviation string

    Examples:
        >>> get_timezone_name_from_offset(330)
        'IST (UTC+5:30)'
        >>> get_timezone_name_from_offset(-300)
        'EST (UTC-5:00)'
    """
    # Common timezone mappings (offset in minutes -> name)
    TIMEZONE_MAP = {
        -720: 'BIT (UTC-12:00)',     # Baker Island Time
        -660: 'SST (UTC-11:00)',     # Samoa Standard Time
        -600: 'HST (UTC-10:00)',     # Hawaii-Aleutian Standard Time
        -540: 'AKST (UTC-9:00)',     # Alaska Standard Time
        -480: 'PST (UTC-8:00)',      # Pacific Standard Time
        -420: 'MST (UTC-7:00)',      # Mountain Standard Time
        -360: 'CST (UTC-6:00)',      # Central Standard Time
        -300: 'EST (UTC-5:00)',      # Eastern Standard Time
        -240: 'AST (UTC-4:00)',      # Atlantic Standard Time
        -180: 'ART (UTC-3:00)',      # Argentina Time
        -120: 'BRT (UTC-2:00)',      # Brasilia Time
        -60: 'AZOT (UTC-1:00)',      # Azores Standard Time
        0: 'UTC (UTC+0:00)',         # Coordinated Universal Time
        60: 'CET (UTC+1:00)',        # Central European Time
        120: 'EET (UTC+2:00)',       # Eastern European Time
        180: 'MSK (UTC+3:00)',       # Moscow Standard Time
        210: 'IRST (UTC+3:30)',      # Iran Standard Time
        240: 'GST (UTC+4:00)',       # Gulf Standard Time
        270: 'AFT (UTC+4:30)',       # Afghanistan Time
        300: 'PKT (UTC+5:00)',       # Pakistan Standard Time
        330: 'IST (UTC+5:30)',       # India Standard Time
        345: 'NPT (UTC+5:45)',       # Nepal Time
        360: 'BST (UTC+6:00)',       # Bangladesh Standard Time
        390: 'MMT (UTC+6:30)',       # Myanmar Time
        420: 'ICT (UTC+7:00)',       # Indochina Time
        480: 'CST (UTC+8:00)',       # China Standard Time
        540: 'JST (UTC+9:00)',       # Japan Standard Time
        570: 'ACST (UTC+9:30)',      # Australian Central Standard Time
        600: 'AEST (UTC+10:00)',     # Australian Eastern Standard Time
        660: 'SBT (UTC+11:00)',      # Solomon Islands Time
        720: 'NZST (UTC+12:00)',     # New Zealand Standard Time
        780: 'TOT (UTC+13:00)',      # Tonga Time
        840: 'LINT (UTC+14:00)',     # Line Islands Time
    }

    # Try exact match first
    if offset_minutes in TIMEZONE_MAP:
        return TIMEZONE_MAP[offset_minutes]

    # Fallback: format as UTC offset
    hours = offset_minutes // 60
    minutes = abs(offset_minutes % 60)
    sign = '+' if offset_minutes >= 0 else '-'

    if minutes == 0:
        return f'UTC{sign}{abs(hours):02d}:00'
    else:
        return f'UTC{sign}{abs(hours):02d}:{minutes:02d}'


def parse_iso_datetime_with_offset(iso_string: str) -> Tuple[datetime, int]:
    """
    Parse ISO datetime string and extract timezone offset.

    Args:
        iso_string: ISO 8601 datetime string (e.g., '2025-10-01T16:00:00+05:30')

    Returns:
        Tuple of (UTC datetime, offset in minutes)

    Raises:
        ValidationError: If ISO string is malformed

    Examples:
        >>> parse_iso_datetime_with_offset('2025-10-01T16:00:00+05:30')
        (datetime(2025, 10, 1, 10, 30, tzinfo=UTC), 330)
    """
    try:
        dt = datetime.fromisoformat(iso_string)

        if dt.tzinfo is None:
            raise ValidationError("ISO string must include timezone information")

        # Extract offset in minutes
        utc_offset = dt.utcoffset()
        if utc_offset is None:
            offset_minutes = 0
        else:
            offset_minutes = int(utc_offset.total_seconds() / 60)

        # Convert to UTC
        utc_dt = dt.astimezone(dt_timezone.utc)

        return utc_dt, offset_minutes

    except (ValueError, AttributeError) as e:
        logger.error(f"Failed to parse ISO datetime: {iso_string}", exc_info=True)
        raise ValidationError(f"Invalid ISO datetime string: {e}") from e


def validate_datetime_not_future(dt: datetime, max_future_minutes: int = 5) -> bool:
    """
    Validate that datetime is not in the future (with small tolerance).

    Useful for attendance punch-in/out validation.

    Args:
        dt: Datetime to validate (should be timezone-aware)
        max_future_minutes: Maximum minutes in future allowed (default: 5)

    Returns:
        True if datetime is valid, False if too far in future

    Examples:
        >>> now = timezone.now()
        >>> validate_datetime_not_future(now)
        True
        >>> future = now + timedelta(hours=1)
        >>> validate_datetime_not_future(future)
        False
    """
    # Ensure timezone-aware comparison
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=dt_timezone.utc)

    now = timezone.now()
    max_future = now + timedelta(minutes=max_future_minutes)

    if dt > max_future:
        logger.warning(
            f"Datetime {dt} is too far in future (now: {now}, max: {max_future})"
        )
        return False

    return True


def get_client_timezone_info(offset_minutes: int) -> dict:
    """
    Get comprehensive timezone information for client offset.

    Args:
        offset_minutes: Timezone offset in minutes

    Returns:
        Dict with timezone details

    Example:
        >>> get_client_timezone_info(330)
        {
            'offset_minutes': 330,
            'offset_hours': 5.5,
            'name': 'IST (UTC+5:30)',
            'is_valid': True,
            'utc_offset_string': '+05:30'
        }
    """
    is_valid = validate_timezone_offset(offset_minutes)
    hours = offset_minutes / 60
    sign = '+' if offset_minutes >= 0 else '-'
    abs_hours = abs(int(hours))
    abs_minutes = abs(offset_minutes % 60)

    return {
        'offset_minutes': offset_minutes,
        'offset_hours': hours,
        'name': get_timezone_name_from_offset(offset_minutes) if is_valid else 'Invalid',
        'is_valid': is_valid,
        'utc_offset_string': f'{sign}{abs_hours:02d}:{abs_minutes:02d}'
    }
