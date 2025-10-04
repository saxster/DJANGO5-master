"""
DateTime Constants Module

Centralized constants for datetime operations across the application.
Eliminates scattered magic numbers and provides standardized format strings.

This module addresses:
- 86400, 3600, 60 second constants found in 180+ files
- 15+ different datetime format patterns across codebase
- Inconsistent timedelta calculations

Usage:
    from apps.core.constants.datetime_constants import (
        SECONDS_IN_DAY, ISO_DATETIME_FORMAT, COMMON_TIMEDELTAS
    )

Compliance:
- Rule #7: Single responsibility (datetime constants only)
- Rule #11: No generic exception handling
- All constants are immutable and clearly named
"""

from datetime import timedelta
from typing import Dict, Final

# =============================================================================
# TIME CONVERSION CONSTANTS
# =============================================================================

# Basic time unit conversions
SECONDS_IN_MINUTE: Final[int] = 60
SECONDS_IN_HOUR: Final[int] = 3600  # 60 * 60
SECONDS_IN_DAY: Final[int] = 86400  # 60 * 60 * 24
SECONDS_IN_WEEK: Final[int] = 604800  # 86400 * 7

MINUTES_IN_HOUR: Final[int] = 60
MINUTES_IN_DAY: Final[int] = 1440  # 60 * 24
MINUTES_IN_WEEK: Final[int] = 10080  # 1440 * 7

HOURS_IN_DAY: Final[int] = 24
HOURS_IN_WEEK: Final[int] = 168  # 24 * 7

DAYS_IN_WEEK: Final[int] = 7
DAYS_IN_MONTH_APPROX: Final[int] = 30  # Approximation for business logic
DAYS_IN_YEAR: Final[int] = 365  # Non-leap year approximation

# =============================================================================
# DATETIME FORMAT STRINGS
# =============================================================================

# Standard ISO formats
ISO_DATETIME_FORMAT: Final[str] = "%Y-%m-%dT%H:%M:%S.%fZ"
ISO_DATETIME_NO_MICRO: Final[str] = "%Y-%m-%dT%H:%M:%SZ"
ISO_DATE_FORMAT: Final[str] = "%Y-%m-%d"
ISO_TIME_FORMAT: Final[str] = "%H:%M:%S"

# Common application formats (found across codebase)
DISPLAY_DATETIME_FORMAT: Final[str] = "%d-%b-%Y %H:%M"  # 01-Jan-2025 14:30
DISPLAY_DATE_FORMAT: Final[str] = "%d-%b-%Y"  # 01-Jan-2025
DISPLAY_TIME_FORMAT: Final[str] = "%H:%M"  # 14:30

# Database/API formats
DB_DATETIME_FORMAT: Final[str] = "%Y-%m-%d %H:%M:%S"  # 2025-01-01 14:30:00
DB_DATE_FORMAT: Final[str] = "%Y-%m-%d"  # 2025-01-01
DB_TIME_FORMAT: Final[str] = "%H:%M:%S"  # 14:30:00

# File/logging formats
FILE_TIMESTAMP_FORMAT: Final[str] = "%Y%m%d_%H%M%S"  # 20250101_143000
LOG_DATETIME_FORMAT: Final[str] = "%Y-%m-%d %H:%M:%S"  # 2025-01-01 14:30:00

# Report formats (from background_tasks/report_tasks.py)
REPORT_DATETIME_FORMAT: Final[str] = "%d-%b-%Y %H-%M-%S"  # 01-Jan-2025 14-30-00
REPORT_DATE_FORMAT: Final[str] = "%d-%b-%Y"  # 01-Jan-2025
REPORT_TIME_FORMAT: Final[str] = "%H-%M-%S"  # 14-30-00

# Django settings formats
DJANGO_DATETIME_INPUT_FORMATS: Final[tuple] = (
    "%d-%b-%Y %H:%M:%S",
    "%Y-%m-%d %H:%M:%S",
    "%d-%b-%Y %H:%M"
)

DJANGO_DATE_INPUT_FORMATS: Final[tuple] = (
    "%d-%b-%Y",
    "%d/%b/%Y",
    "%d/%m/%Y",
    "%Y-%m-%d",
    "%Y/%m/%d",
    "%Y-%m-%dT%H:%M:%S%z"
)

# =============================================================================
# COMMON TIMEDELTA CONSTANTS
# =============================================================================

# Frequently used timedelta objects
COMMON_TIMEDELTAS: Final[Dict[str, timedelta]] = {
    # Minutes
    'ONE_MINUTE': timedelta(minutes=1),
    'FIVE_MINUTES': timedelta(minutes=5),
    'FIFTEEN_MINUTES': timedelta(minutes=15),
    'THIRTY_MINUTES': timedelta(minutes=30),

    # Hours
    'ONE_HOUR': timedelta(hours=1),
    'TWO_HOURS': timedelta(hours=2),
    'EIGHT_HOURS': timedelta(hours=8),
    'TWELVE_HOURS': timedelta(hours=12),

    # Days
    'ONE_DAY': timedelta(days=1),
    'ONE_WEEK': timedelta(days=7),
    'TWO_WEEKS': timedelta(days=14),
    'ONE_MONTH': timedelta(days=30),
    'THREE_MONTHS': timedelta(days=90),
    'SIX_MONTHS': timedelta(days=180),
    'ONE_YEAR': timedelta(days=365),
}

# Business/application specific timedeltas
BUSINESS_TIMEDELTAS: Final[Dict[str, timedelta]] = {
    # Session timeouts (from settings)
    'SESSION_TIMEOUT': timedelta(hours=2),
    'API_TOKEN_LIFETIME': timedelta(hours=1),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),

    # Cache timeouts
    'CACHE_SHORT': timedelta(minutes=5),
    'CACHE_MEDIUM': timedelta(minutes=30),
    'CACHE_LONG': timedelta(hours=1),
    'CACHE_DAILY': timedelta(hours=24),

    # Monitoring intervals (from celery config)
    'AUTO_CLOSE_INTERVAL': timedelta(minutes=30),
    'ESCALATION_INTERVAL': timedelta(minutes=30),
    'JOB_CREATION_INTERVAL': timedelta(hours=8),

    # Data retention
    'LOG_RETENTION': timedelta(days=30),
    'METRICS_RETENTION': timedelta(days=90),
    'ARCHIVE_RETENTION': timedelta(days=365),
}

# =============================================================================
# TIMEZONE CONSTANTS
# =============================================================================

# Common timezone offset constants (in minutes)
TIMEZONE_OFFSETS: Final[Dict[str, int]] = {
    'UTC': 0,
    'IST': 330,  # India Standard Time (+05:30)
    'EST': -300,  # Eastern Standard Time (-05:00)
    'PST': -480,  # Pacific Standard Time (-08:00)
    'GMT': 0,     # Greenwich Mean Time
}

# =============================================================================
# VALIDATION CONSTANTS
# =============================================================================

# Limits for datetime validation
DATETIME_LIMITS: Final[Dict[str, int]] = {
    'MIN_YEAR': 1970,  # Unix epoch start
    'MAX_YEAR': 2100,  # Reasonable future limit
    'MAX_AUDIO_DURATION_SECONDS': 60,  # From voice integration
    'MAX_SESSION_DURATION_HOURS': 24,
    'MIN_BUSINESS_HOUR': 9,  # 9 AM
    'MAX_BUSINESS_HOUR': 17,  # 5 PM
}

# =============================================================================
# UTILITY MAPPINGS
# =============================================================================

# Format mapping for easy lookup
FORMAT_CHOICES: Final[Dict[str, str]] = {
    'iso_datetime': ISO_DATETIME_FORMAT,
    'iso_date': ISO_DATE_FORMAT,
    'iso_time': ISO_TIME_FORMAT,
    'display_datetime': DISPLAY_DATETIME_FORMAT,
    'display_date': DISPLAY_DATE_FORMAT,
    'db_datetime': DB_DATETIME_FORMAT,
    'file_timestamp': FILE_TIMESTAMP_FORMAT,
    'log_datetime': LOG_DATETIME_FORMAT,
    'report_datetime': REPORT_DATETIME_FORMAT,
}

# =============================================================================
# MODULE EXPORTS
# =============================================================================

__all__ = [
    # Time conversion constants
    'SECONDS_IN_MINUTE', 'SECONDS_IN_HOUR', 'SECONDS_IN_DAY', 'SECONDS_IN_WEEK',
    'MINUTES_IN_HOUR', 'MINUTES_IN_DAY', 'MINUTES_IN_WEEK',
    'HOURS_IN_DAY', 'HOURS_IN_WEEK',
    'DAYS_IN_WEEK', 'DAYS_IN_MONTH_APPROX', 'DAYS_IN_YEAR',

    # Format strings
    'ISO_DATETIME_FORMAT', 'ISO_DATETIME_NO_MICRO', 'ISO_DATE_FORMAT', 'ISO_TIME_FORMAT',
    'DISPLAY_DATETIME_FORMAT', 'DISPLAY_DATE_FORMAT', 'DISPLAY_TIME_FORMAT',
    'DB_DATETIME_FORMAT', 'DB_DATE_FORMAT', 'DB_TIME_FORMAT',
    'FILE_TIMESTAMP_FORMAT', 'LOG_DATETIME_FORMAT',
    'REPORT_DATETIME_FORMAT', 'REPORT_DATE_FORMAT', 'REPORT_TIME_FORMAT',
    'DJANGO_DATETIME_INPUT_FORMATS', 'DJANGO_DATE_INPUT_FORMATS',

    # Timedelta constants
    'COMMON_TIMEDELTAS', 'BUSINESS_TIMEDELTAS',

    # Timezone constants
    'TIMEZONE_OFFSETS',

    # Validation constants
    'DATETIME_LIMITS',

    # Utility mappings
    'FORMAT_CHOICES',
]