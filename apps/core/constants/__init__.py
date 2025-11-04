"""
Core Constants Package

Centralized constants for the application including datetime, validation,
and other shared constants.
"""

from .datetime_constants import *
from .sentinel_constants import (
    DatabaseConstants,
    JobConstants,
    AssetConstants,
    PeopleConstants,
    GeofenceConstants,
    TenantConstants,
    SiteGroupConstants,
    ShiftConstants,
)

# Explicit __all__ to control namespace (Rule #16: Wildcard Import Prevention)
__all__ = [
    # From datetime_constants.py - Time conversion constants
    'SECONDS_IN_MINUTE', 'SECONDS_IN_HOUR', 'SECONDS_IN_DAY', 'SECONDS_IN_WEEK',
    'MINUTES_IN_HOUR', 'MINUTES_IN_DAY', 'MINUTES_IN_WEEK',
    'HOURS_IN_DAY', 'HOURS_IN_WEEK',
    'DAYS_IN_WEEK', 'DAYS_IN_MONTH_APPROX', 'DAYS_IN_YEAR',

    # From datetime_constants.py - Format strings
    'ISO_DATETIME_FORMAT', 'ISO_DATETIME_NO_MICRO', 'ISO_DATE_FORMAT', 'ISO_TIME_FORMAT',
    'DISPLAY_DATETIME_FORMAT', 'DISPLAY_DATE_FORMAT', 'DISPLAY_TIME_FORMAT',
    'DB_DATETIME_FORMAT', 'DB_DATE_FORMAT', 'DB_TIME_FORMAT',
    'FILE_TIMESTAMP_FORMAT', 'LOG_DATETIME_FORMAT',
    'REPORT_DATETIME_FORMAT', 'REPORT_DATE_FORMAT', 'REPORT_TIME_FORMAT',
    'DJANGO_DATETIME_INPUT_FORMATS', 'DJANGO_DATE_INPUT_FORMATS',

    # From datetime_constants.py - Timedelta constants
    'COMMON_TIMEDELTAS', 'BUSINESS_TIMEDELTAS',

    # From datetime_constants.py - Timezone constants
    'TIMEZONE_OFFSETS',

    # From datetime_constants.py - Validation constants
    'DATETIME_LIMITS',

    # From datetime_constants.py - Utility mappings
    'FORMAT_CHOICES',

    # From sentinel_constants.py - Sentinel constants
    'DatabaseConstants',
    'JobConstants',
    'AssetConstants',
    'PeopleConstants',
    'GeofenceConstants',
    'TenantConstants',
    'SiteGroupConstants',
    'ShiftConstants',
]