"""
Network and Operation Timeout Constants

Centralized timeout values for all network requests, database operations,
and long-running processes. Prevents hardcoded timeout magic numbers across
the codebase.

Usage:
    from apps.core.constants.timeouts import (
        REQUEST_TIMEOUT_SHORT,
        REQUEST_TIMEOUT_LONG,
        DATABASE_TIMEOUT,
        WEBSOCKET_TIMEOUT
    )

    response = requests.get(url, timeout=REQUEST_TIMEOUT_SHORT)

Compliance:
- Eliminates magic numbers from network calls (prevents worker hangs)
- Ensures consistent timeout policies across application
- Supports environment-based timeout customization
"""

from typing import Tuple, Final

# =============================================================================
# HTTP REQUEST TIMEOUTS (in seconds)
# =============================================================================

# Format: (connect_timeout, read_timeout)
# Standard HTTP API calls - quick metadata/status endpoints
REQUEST_TIMEOUT_SHORT: Final[Tuple[int, int]] = (5, 15)

# File downloads and moderate operations
REQUEST_TIMEOUT_MEDIUM: Final[Tuple[int, int]] = (5, 30)

# Long operations like report generation, data exports
REQUEST_TIMEOUT_LONG: Final[Tuple[int, int]] = (5, 60)

# Webhook callbacks and notifications (async, can be longer)
REQUEST_TIMEOUT_WEBHOOK: Final[Tuple[int, int]] = (10, 30)

# =============================================================================
# NETWORK OPERATION TIMEOUTS (single value, in seconds)
# =============================================================================

# Redis operations
REDIS_OPERATION_TIMEOUT: Final[int] = 5

# Database connection timeout
DATABASE_TIMEOUT: Final[int] = 5

# Cache operations
CACHE_OPERATION_TIMEOUT: Final[int] = 5

# =============================================================================
# TASK EXECUTION TIMEOUTS (in seconds)
# =============================================================================

# Soft time limit - task should gracefully shut down before this
CELERY_SOFT_TIMEOUT_SHORT: Final[int] = 300  # 5 minutes
CELERY_SOFT_TIMEOUT_MEDIUM: Final[int] = 600  # 10 minutes
CELERY_SOFT_TIMEOUT_LONG: Final[int] = 1800  # 30 minutes

# Hard time limit - task forcefully killed after this
CELERY_HARD_TIMEOUT_SHORT: Final[int] = 600  # 10 minutes
CELERY_HARD_TIMEOUT_MEDIUM: Final[int] = 1200  # 20 minutes
CELERY_HARD_TIMEOUT_LONG: Final[int] = 3600  # 1 hour
CELERY_HARD_TIMEOUT_EXTRA_LONG: Final[int] = 7200  # 2 hours

# =============================================================================
# TASK EXPIRATION TIMEOUTS (in seconds)
# =============================================================================

# Tasks expire and are removed from queue if not executed
TASK_EXPIRES_SHORT: Final[int] = 300  # 5 minutes
TASK_EXPIRES_MEDIUM: Final[int] = 900  # 15 minutes
TASK_EXPIRES_STANDARD: Final[int] = 3600  # 1 hour
TASK_EXPIRES_LONG: Final[int] = 7200  # 2 hours
TASK_EXPIRES_VERY_LONG: Final[int] = 86400  # 24 hours

# =============================================================================
# WEBSOCKET TIMEOUTS (in seconds)
# =============================================================================

# JWT cache for WebSocket authentication
WEBSOCKET_JWT_CACHE_TIMEOUT: Final[int] = 300  # 5 minutes

# WebSocket presence detection timeout
WEBSOCKET_PRESENCE_TIMEOUT: Final[int] = 300  # 5 minutes

# WebSocket connection idle timeout
WEBSOCKET_IDLE_TIMEOUT: Final[int] = 3600  # 1 hour

# =============================================================================
# VISIBILITY TIMEOUTS (for message queues, in seconds)
# =============================================================================

# SQS/message queue visibility - time before message redelivered
MESSAGE_VISIBILITY_TIMEOUT: Final[int] = 3600  # 1 hour

# Dead letter queue processing timeout
DEAD_LETTER_VISIBILITY_TIMEOUT: Final[int] = 3600  # 1 hour

# =============================================================================
# API & EXTERNAL SERVICE TIMEOUTS (in seconds)
# =============================================================================

# Google Maps API calls
GOOGLE_MAPS_TIMEOUT: Final[Tuple[int, int]] = (5, 15)

# Frappe/external system integration
FRAPPE_TIMEOUT: Final[Tuple[int, int]] = (5, 30)

# Geofence validation service
GEOFENCE_VALIDATION_TIMEOUT: Final[Tuple[int, int]] = (5, 10)

# =============================================================================
# FILE UPLOAD OPERATION TIMEOUTS (in seconds)
# =============================================================================

# Virus scanning timeout (ClamAV or similar)
FILE_UPLOAD_VIRUS_SCAN_TIMEOUT: Final[int] = 30

# EXIF metadata extraction and processing timeout
FILE_UPLOAD_EXIF_PROCESSING_TIMEOUT: Final[int] = 15

# Cloud storage upload timeout (S3, Azure, etc.)
FILE_UPLOAD_CLOUD_UPLOAD_TIMEOUT: Final[int] = 60

# Maximum total time for complete upload pipeline
FILE_UPLOAD_MAX_TOTAL_TIMEOUT: Final[int] = 120

# =============================================================================
# MODULE EXPORTS
# =============================================================================

__all__ = [
    # HTTP request timeouts
    'REQUEST_TIMEOUT_SHORT',
    'REQUEST_TIMEOUT_MEDIUM',
    'REQUEST_TIMEOUT_LONG',
    'REQUEST_TIMEOUT_WEBHOOK',

    # Network operation timeouts
    'REDIS_OPERATION_TIMEOUT',
    'DATABASE_TIMEOUT',
    'CACHE_OPERATION_TIMEOUT',

    # Task execution timeouts
    'CELERY_SOFT_TIMEOUT_SHORT',
    'CELERY_SOFT_TIMEOUT_MEDIUM',
    'CELERY_SOFT_TIMEOUT_LONG',
    'CELERY_HARD_TIMEOUT_SHORT',
    'CELERY_HARD_TIMEOUT_MEDIUM',
    'CELERY_HARD_TIMEOUT_LONG',
    'CELERY_HARD_TIMEOUT_EXTRA_LONG',

    # Task expiration
    'TASK_EXPIRES_SHORT',
    'TASK_EXPIRES_MEDIUM',
    'TASK_EXPIRES_STANDARD',
    'TASK_EXPIRES_LONG',
    'TASK_EXPIRES_VERY_LONG',

    # WebSocket timeouts
    'WEBSOCKET_JWT_CACHE_TIMEOUT',
    'WEBSOCKET_PRESENCE_TIMEOUT',
    'WEBSOCKET_IDLE_TIMEOUT',

    # Visibility timeouts
    'MESSAGE_VISIBILITY_TIMEOUT',
    'DEAD_LETTER_VISIBILITY_TIMEOUT',

    # API service timeouts
    'GOOGLE_MAPS_TIMEOUT',
    'FRAPPE_TIMEOUT',
    'GEOFENCE_VALIDATION_TIMEOUT',

    # File upload operation timeouts
    'FILE_UPLOAD_VIRUS_SCAN_TIMEOUT',
    'FILE_UPLOAD_EXIF_PROCESSING_TIMEOUT',
    'FILE_UPLOAD_CLOUD_UPLOAD_TIMEOUT',
    'FILE_UPLOAD_MAX_TOTAL_TIMEOUT',
]
