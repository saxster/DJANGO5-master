"""
Sentinel Value Constants

Defines standard sentinel values (NONE records) used throughout the application
for handling null/empty foreign key relationships.

Following .claude/rules.md:
- Rule #6: Settings < 200 lines
- Clear, maintainable constant definitions
"""


class DatabaseConstants:
    """Database-level sentinel values and constants"""

    # Sentinel record IDs for "NONE" records
    NONE_RECORD_ID = 1
    ID_SYSTEM = 1  # System/NONE record ID
    ID_ROOT = -1   # Root/NULL parent ID

    # Default values for NONE records
    DEFAULT_CODE = 'NONE'
    DEFAULT_NAME = 'NONE'

    # Default database operations
    DEFAULT_DB_ALIAS = 'default'
    DEFAULT_CONN_MAX_AGE = 600  # 10 minutes

    # Query performance
    MAX_QUERY_RESULTS = 10000
    SLOW_QUERY_THRESHOLD_MS = 1000  # 1 second


class JobConstants:
    """Job/Task-related constants"""

    class Identifier:
        """Job identifier constants"""
        TASK = 'TASK'
        INTERNALTOUR = 'INTERNALTOUR'
        EXTERNALTOUR = 'EXTERNALTOUR'
        SITEREPORT = 'SITEREPORT'

    # Job identifiers (backward compatibility)
    TASK_IDENTIFIER = 'TASK'
    INTERNAL_TOUR_IDENTIFIER = 'INTERNALTOUR'
    EXTERNAL_TOUR_IDENTIFIER = 'EXTERNALTOUR'

    # Job statuses
    STATUS_ASSIGNED = 'ASSIGNED'
    STATUS_INPROGRESS = 'INPROGRESS'
    STATUS_COMPLETED = 'COMPLETED'
    STATUS_AUTOCLOSED = 'AUTOCLOSED'
    STATUS_PARTIALLYCOMPLETED = 'PARTIALLYCOMPLETED'

    # Scan types
    SCAN_TYPE_QR = 'QR'
    SCAN_TYPE_NFC = 'NFC'
    SCAN_TYPE_SKIP = 'SKIP'
    SCAN_TYPE_ENTERED = 'ENTERED'

    # Priority levels
    PRIORITY_LOW = 'LOW'
    PRIORITY_MEDIUM = 'MEDIUM'
    PRIORITY_HIGH = 'HIGH'

    # Sentinel values
    NONE_JOB_ID = 1
    DEFAULT_SEQUENCE_NUMBER = -1


class AssetConstants:
    """Asset-related constants"""

    class Identifier:
        """Asset identifier constants"""
        ASSET = 'ASSET'
        CHECKPOINT = 'CHECKPOINT'
        EQUIPMENT = 'EQUIPMENT'
        LOCATION = 'LOCATION'

    # Sentinel values
    NONE_ASSET_ID = 1
    NONE_ASSET_CODE = 'NONE'

    # Asset types (backward compatibility)
    TYPE_CHECKPOINT = 'CHECKPOINT'
    TYPE_EQUIPMENT = 'EQUIPMENT'
    TYPE_LOCATION = 'LOCATION'

    # Asset statuses
    STATUS_ACTIVE = 'ACTIVE'
    STATUS_INACTIVE = 'INACTIVE'
    STATUS_MAINTENANCE = 'MAINTENANCE'


class PeopleConstants:
    """People/User-related constants"""

    # Sentinel values
    NONE_PEOPLE_ID = 1
    NONE_PEOPLE_CODE = 'NONE'

    # Sentinel group values
    NONE_GROUP_ID = 1
    NONE_GROUP_NAME = 'NONE'


class GeofenceConstants:
    """Geofence-related constants"""

    # Sentinel values
    NONE_GEOFENCE_ID = 1

    # Default geofence radius (meters)
    DEFAULT_GEOFENCE_RADIUS = 100


class TenantConstants:
    """Tenant-related constants"""

    # Sentinel values
    NONE_TENANT_ID = 1

    # Default tenant settings
    DEFAULT_TENANT_CODE = 'NONE'


class SiteGroupConstants:
    """Site group-related constants"""

    # Sentinel values
    NONE_SITEGROUP_ID = 1


class ShiftConstants:
    """Shift-related constants"""

    # Sentinel values
    NONE_SHIFT_ID = 1

    # Default shift timings
    DEFAULT_SHIFT_HOURS = 8


__all__ = [
    'DatabaseConstants',
    'JobConstants',
    'AssetConstants',
    'PeopleConstants',
    'GeofenceConstants',
    'TenantConstants',
    'SiteGroupConstants',
    'ShiftConstants',
]
