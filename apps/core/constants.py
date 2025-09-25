"""
Application-wide constants module.

This module defines constants used throughout the YOUTILITY5 application
to eliminate magic numbers and strings, improving maintainability.
"""

from django.utils.translation import gettext_lazy as _


# =============================================================================
# Database Constants
# =============================================================================

class DatabaseConstants:
    """Database-related constants."""

    # Special ID values
    ID_NONE = -1
    ID_ROOT = -1
    ID_SYSTEM = 1

    # Default string values
    DEFAULT_CODE = "NONE"
    DEFAULT_NAME = "Default"


# =============================================================================
# Job System Constants
# =============================================================================

class JobConstants:
    """Constants for job system."""

    # Job types
    class Type:
        INTERNAL_TOUR = "INTERNALTOUR"
        EXTERNAL_TOUR = "EXTERNALTOUR"
        TASK = "TASK"
        ADHOC = "ADHOC"
        SCHEDULED = "SCHEDULED"

    # Job priorities
    class Priority:
        LOW = "LOW"
        MEDIUM = "MEDIUM"
        HIGH = "HIGH"
        URGENT = "URGENT"
        CRITICAL = "CRITICAL"

    # Job statuses
    class Status:
        PENDING = "PENDING"
        IN_PROGRESS = "IN_PROGRESS"
        COMPLETED = "COMPLETED"
        CANCELLED = "CANCELLED"
        FAILED = "FAILED"
        OVERDUE = "OVERDUE"

    # Job identifiers
    class Identifier:
        INTERNALTOUR = "INTERNALTOUR"
        EXTERNALTOUR = "EXTERNALTOUR"
        TASK = "TASK"
        SITEREPORT = "SITEREPORT"
        CHECKPOINT = "CHECKPOINT"

    # Scan types
    class ScanType:
        QR = "QR"
        NFC = "NFC"
        GPS = "GPS"
        MANUAL = "MANUAL"

    # Default values
    DEFAULT_GRACE_TIME = 5  # minutes
    DEFAULT_EXPIRY_TIME = 0  # minutes
    DEFAULT_MULTIFACTOR = 1


# =============================================================================
# Asset System Constants
# =============================================================================

class AssetConstants:
    """Constants for asset management."""

    # Asset statuses
    class Status:
        ACTIVE = "ACTIVE"
        INACTIVE = "INACTIVE"
        MAINTENANCE = "MAINTENANCE"
        SCRAPPED = "SCRAPPED"
        LOST = "LOST"
        DAMAGED = "DAMAGED"

    # Asset types
    class Type:
        CHECKPOINT = "CHECKPOINT"
        SMARTPLACE = "SMARTPLACE"
        EQUIPMENT = "EQUIPMENT"
        VEHICLE = "VEHICLE"
        FACILITY = "FACILITY"

    # Asset identifiers
    class Identifier:
        CHECKPOINT = "CHECKPOINT"
        SMARTPLACE = "SMARTPLACE"
        ASSET = "ASSET"


# =============================================================================
# User/People System Constants
# =============================================================================

class PeopleConstants:
    """Constants for people/user management."""

    # Gender options
    class Gender:
        MALE = "M"
        FEMALE = "F"
        OTHER = "O"
        CHOICES = [
            (MALE, _("Male")),
            (FEMALE, _("Female")),
            (OTHER, _("Others")),
        ]

    # User roles
    class Role:
        ADMIN = "ADMIN"
        SUPERVISOR = "SUPERVISOR"
        GUARD = "GUARD"
        OPERATOR = "OPERATOR"
        VIEWER = "VIEWER"

    # Default values
    DEFAULT_DEVICE_ID = "-1"
    DEFAULT_PEOPLE_CODE = "NONE"


# =============================================================================
# Location/Geography Constants
# =============================================================================

class LocationConstants:
    """Constants for location and geography."""

    # Default SRID for geographic data
    DEFAULT_SRID = 4326

    # Distance thresholds (in meters)
    GEOFENCE_THRESHOLD = 100
    GPS_ACCURACY_THRESHOLD = 50

    # Location types
    class Type:
        SITE = "SITE"
        CLIENT = "CLIENT"
        CHECKPOINT = "CHECKPOINT"
        OFFICE = "OFFICE"
        WAREHOUSE = "WAREHOUSE"


# =============================================================================
# Time and Date Constants
# =============================================================================

class TimeConstants:
    """Constants for time and date handling."""

    # Time formats
    TIME_FORMAT = "%H:%M:%S"
    DATE_FORMAT = "%Y-%m-%d"
    DATETIME_FORMAT = "%Y-%m-%d %H:%M:%S"
    DISPLAY_DATETIME_FORMAT = "%d-%b-%Y %H:%M:%S"

    # Default time values
    DEFAULT_START_TIME = "00:00:00"
    DEFAULT_END_TIME = "23:59:59"

    # Timezone offset defaults
    DEFAULT_TIMEZONE_OFFSET = 0


# =============================================================================
# Validation Constants
# =============================================================================

class ValidationConstants:
    """Constants for data validation."""

    # String length limits
    MAX_NAME_LENGTH = 100
    MAX_CODE_LENGTH = 50
    MAX_DESCRIPTION_LENGTH = 500
    MAX_EMAIL_LENGTH = 254
    MAX_PHONE_LENGTH = 20

    # Numeric limits
    MAX_LATITUDE = 90.0
    MIN_LATITUDE = -90.0
    MAX_LONGITUDE = 180.0
    MIN_LONGITUDE = -180.0

    # Default values
    DEFAULT_PAGE_SIZE = 25
    MAX_PAGE_SIZE = 100


# =============================================================================
# Security Constants
# =============================================================================

class SecurityConstants:
    """Constants for security and authentication."""

    # Password requirements
    MIN_PASSWORD_LENGTH = 8
    MAX_LOGIN_ATTEMPTS = 3
    LOCKOUT_DURATION = 300  # seconds (5 minutes)

    # Session timeouts
    SESSION_TIMEOUT = 3600  # seconds (1 hour)
    REMEMBER_ME_TIMEOUT = 2592000  # seconds (30 days)


# =============================================================================
# API Response Constants
# =============================================================================

class ResponseConstants:
    """Constants for API responses and messages."""

    # Success messages
    class Success:
        CREATED = "Record created successfully"
        UPDATED = "Record updated successfully"
        DELETED = "Record deleted successfully"
        OPERATION_SUCCESS = "Operation completed successfully"

    # Error messages
    class Error:
        NOT_FOUND = "Record not found"
        INVALID_DATA = "Invalid data provided"
        PERMISSION_DENIED = "Permission denied"
        OPERATION_FAILED = "Operation failed"
        DATABASE_ERROR = "Database operation failed"
        VALIDATION_ERROR = "Data validation failed"

    # HTTP status codes (for reference)
    class StatusCode:
        OK = 200
        CREATED = 201
        BAD_REQUEST = 400
        UNAUTHORIZED = 401
        FORBIDDEN = 403
        NOT_FOUND = 404
        UNPROCESSABLE_ENTITY = 422
        INTERNAL_SERVER_ERROR = 500


# =============================================================================
# File and Media Constants
# =============================================================================

class MediaConstants:
    """Constants for file and media handling."""

    # File size limits (in bytes)
    MAX_IMAGE_SIZE = 5 * 1024 * 1024  # 5MB
    MAX_DOCUMENT_SIZE = 10 * 1024 * 1024  # 10MB
    MAX_VIDEO_SIZE = 50 * 1024 * 1024  # 50MB

    # Allowed file extensions
    ALLOWED_IMAGE_EXTENSIONS = ['.jpg', '.jpeg', '.png', '.gif', '.webp']
    ALLOWED_DOCUMENT_EXTENSIONS = ['.pdf', '.doc', '.docx', '.xls', '.xlsx', '.txt']
    ALLOWED_VIDEO_EXTENSIONS = ['.mp4', '.avi', '.mov', '.wmv']

    # Default paths
    DEFAULT_AVATAR_PATH = '/static/images/default_avatar.png'
    DEFAULT_LOGO_PATH = '/static/images/default_logo.png'


# =============================================================================
# Cache Constants
# =============================================================================

class CacheConstants:
    """Constants for caching system."""

    # Cache timeouts (in seconds)
    SHORT_CACHE_TIMEOUT = 300      # 5 minutes
    MEDIUM_CACHE_TIMEOUT = 1800    # 30 minutes
    LONG_CACHE_TIMEOUT = 3600      # 1 hour
    DAY_CACHE_TIMEOUT = 86400      # 24 hours

    # Cache key prefixes
    USER_CACHE_PREFIX = "user_"
    SESSION_CACHE_PREFIX = "session_"
    QUERY_CACHE_PREFIX = "query_"
    REPORT_CACHE_PREFIX = "report_"


# =============================================================================
# Configuration Constants
# =============================================================================

class ConfigConstants:
    """Constants for application configuration."""

    # Environment types
    class Environment:
        DEVELOPMENT = "development"
        TESTING = "testing"
        STAGING = "staging"
        PRODUCTION = "production"

    # Feature flags
    class Features:
        ENABLE_CACHING = "enable_caching"
        ENABLE_LOGGING = "enable_logging"
        ENABLE_DEBUGGING = "enable_debugging"
        ENABLE_PROFILING = "enable_profiling"

    # Default configuration values
    DEFAULT_LANGUAGE = "en"
    DEFAULT_TIMEZONE = "UTC"
    DEFAULT_CURRENCY = "USD"
    