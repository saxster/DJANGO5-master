"""
HTTP Status Code and Application Status Constants

Centralized status codes to eliminate magic numbers across the codebase.

Following .claude/rules.md:
- Rule #11: Explicit constants instead of magic numbers
- HTTP status codes aligned with RFC 7231

Usage:
    from apps.core.constants.status_constants import HTTP_200_OK, HTTP_404_NOT_FOUND
    return JsonResponse(data, status=HTTP_200_OK)
"""

from typing import Final

# ===========================================
# HTTP STATUS CODES (RFC 7231)
# ===========================================

# 2xx Success
HTTP_200_OK: Final[int] = 200
HTTP_201_CREATED: Final[int] = 201
HTTP_202_ACCEPTED: Final[int] = 202
HTTP_204_NO_CONTENT: Final[int] = 204

# 3xx Redirection
HTTP_301_MOVED_PERMANENTLY: Final[int] = 301
HTTP_302_FOUND: Final[int] = 302
HTTP_304_NOT_MODIFIED: Final[int] = 304

# 4xx Client Errors
HTTP_400_BAD_REQUEST: Final[int] = 400
HTTP_401_UNAUTHORIZED: Final[int] = 401
HTTP_403_FORBIDDEN: Final[int] = 403
HTTP_404_NOT_FOUND: Final[int] = 404
HTTP_405_METHOD_NOT_ALLOWED: Final[int] = 405
HTTP_406_NOT_ACCEPTABLE: Final[int] = 406
HTTP_409_CONFLICT: Final[int] = 409
HTTP_410_GONE: Final[int] = 410
HTTP_413_PAYLOAD_TOO_LARGE: Final[int] = 413
HTTP_422_UNPROCESSABLE_ENTITY: Final[int] = 422
HTTP_429_TOO_MANY_REQUESTS: Final[int] = 429

# 5xx Server Errors
HTTP_500_INTERNAL_SERVER_ERROR: Final[int] = 500
HTTP_501_NOT_IMPLEMENTED: Final[int] = 501
HTTP_502_BAD_GATEWAY: Final[int] = 502
HTTP_503_SERVICE_UNAVAILABLE: Final[int] = 503
HTTP_504_GATEWAY_TIMEOUT: Final[int] = 504

# ===========================================
# IMAGE/MEDIA PROCESSING STATUS
# ===========================================

# Image dimension limits (found in attd_capture.py)
IMAGE_MAX_DIMENSION: Final[int] = 512
IMAGE_QUALITY_DEFAULT: Final[int] = 85
IMAGE_QUALITY_HIGH: Final[int] = 95
IMAGE_QUALITY_LOW: Final[int] = 75

# JPEG quality (0-100 scale)
JPEG_QUALITY_MAXIMUM: Final[int] = 255  # Internal OpenCV scale

# ===========================================
# BUSINESS STATUS CODES
# ===========================================

# Work Order Status
WORK_ORDER_PENDING: Final[int] = 1
WORK_ORDER_IN_PROGRESS: Final[int] = 2
WORK_ORDER_COMPLETED: Final[int] = 3
WORK_ORDER_CANCELLED: Final[int] = 4
WORK_ORDER_ON_HOLD: Final[int] = 5

# Ticket Status  
TICKET_OPEN: Final[int] = 1
TICKET_IN_PROGRESS: Final[int] = 2
TICKET_RESOLVED: Final[int] = 3
TICKET_CLOSED: Final[int] = 4
TICKET_REOPENED: Final[int] = 5

# Attendance Status
ATTENDANCE_PRESENT: Final[int] = 1
ATTENDANCE_ABSENT: Final[int] = 2
ATTENDANCE_LATE: Final[int] = 3
ATTENDANCE_ON_LEAVE: Final[int] = 4
ATTENDANCE_HALF_DAY: Final[int] = 5

# Approval Status
APPROVAL_PENDING: Final[int] = 0
APPROVAL_APPROVED: Final[int] = 1
APPROVAL_REJECTED: Final[int] = 2
APPROVAL_CANCELLED: Final[int] = 3

# Alert Severity Levels
SEVERITY_INFO: Final[int] = 1
SEVERITY_WARNING: Final[int] = 2
SEVERITY_ERROR: Final[int] = 3
SEVERITY_CRITICAL: Final[int] = 4

# ===========================================
# PAGINATION & LIMITS
# ===========================================

# Default pagination limits
DEFAULT_PAGE_SIZE: Final[int] = 20
MAX_PAGE_SIZE: Final[int] = 100
MIN_PAGE_SIZE: Final[int] = 5

# Batch processing limits
DEFAULT_BATCH_SIZE: Final[int] = 50
MAX_BATCH_SIZE: Final[int] = 500
MIN_BATCH_SIZE: Final[int] = 10

# ===========================================
# VALIDATION THRESHOLDS
# ===========================================

# String length limits
MAX_USERNAME_LENGTH: Final[int] = 150
MAX_EMAIL_LENGTH: Final[int] = 254
MAX_PHONE_LENGTH: Final[int] = 15
MAX_NAME_LENGTH: Final[int] = 100
MAX_DESCRIPTION_LENGTH: Final[int] = 500
MAX_TEXT_LENGTH: Final[int] = 5000

# Numeric limits
MAX_PERCENTAGE: Final[int] = 100
MIN_PERCENTAGE: Final[int] = 0
MAX_RATING: Final[int] = 5
MIN_RATING: Final[int] = 1

# ===========================================
# RETRY & BACKOFF CONSTANTS
# ===========================================

# Maximum retry attempts
MAX_RETRY_ATTEMPTS: Final[int] = 3
MAX_RETRY_ATTEMPTS_CRITICAL: Final[int] = 5
MAX_RETRY_ATTEMPTS_NETWORK: Final[int] = 3

# Backoff multipliers
BACKOFF_MULTIPLIER_DEFAULT: Final[int] = 2
BACKOFF_MULTIPLIER_AGGRESSIVE: Final[int] = 3

# ===========================================
# EXPORT ALL CONSTANTS
# ===========================================

__all__ = [
    # HTTP Status Codes
    'HTTP_200_OK',
    'HTTP_201_CREATED',
    'HTTP_202_ACCEPTED',
    'HTTP_204_NO_CONTENT',
    'HTTP_301_MOVED_PERMANENTLY',
    'HTTP_302_FOUND',
    'HTTP_304_NOT_MODIFIED',
    'HTTP_400_BAD_REQUEST',
    'HTTP_401_UNAUTHORIZED',
    'HTTP_403_FORBIDDEN',
    'HTTP_404_NOT_FOUND',
    'HTTP_405_METHOD_NOT_ALLOWED',
    'HTTP_406_NOT_ACCEPTABLE',
    'HTTP_409_CONFLICT',
    'HTTP_410_GONE',
    'HTTP_413_PAYLOAD_TOO_LARGE',
    'HTTP_422_UNPROCESSABLE_ENTITY',
    'HTTP_429_TOO_MANY_REQUESTS',
    'HTTP_500_INTERNAL_SERVER_ERROR',
    'HTTP_501_NOT_IMPLEMENTED',
    'HTTP_502_BAD_GATEWAY',
    'HTTP_503_SERVICE_UNAVAILABLE',
    'HTTP_504_GATEWAY_TIMEOUT',
    
    # Image Processing
    'IMAGE_MAX_DIMENSION',
    'IMAGE_QUALITY_DEFAULT',
    'IMAGE_QUALITY_HIGH',
    'IMAGE_QUALITY_LOW',
    'JPEG_QUALITY_MAXIMUM',
    
    # Business Status
    'WORK_ORDER_PENDING',
    'WORK_ORDER_IN_PROGRESS',
    'WORK_ORDER_COMPLETED',
    'WORK_ORDER_CANCELLED',
    'WORK_ORDER_ON_HOLD',
    'TICKET_OPEN',
    'TICKET_IN_PROGRESS',
    'TICKET_RESOLVED',
    'TICKET_CLOSED',
    'TICKET_REOPENED',
    'ATTENDANCE_PRESENT',
    'ATTENDANCE_ABSENT',
    'ATTENDANCE_LATE',
    'ATTENDANCE_ON_LEAVE',
    'ATTENDANCE_HALF_DAY',
    'APPROVAL_PENDING',
    'APPROVAL_APPROVED',
    'APPROVAL_REJECTED',
    'APPROVAL_CANCELLED',
    'SEVERITY_INFO',
    'SEVERITY_WARNING',
    'SEVERITY_ERROR',
    'SEVERITY_CRITICAL',
    
    # Pagination & Limits
    'DEFAULT_PAGE_SIZE',
    'MAX_PAGE_SIZE',
    'MIN_PAGE_SIZE',
    'DEFAULT_BATCH_SIZE',
    'MAX_BATCH_SIZE',
    'MIN_BATCH_SIZE',
    
    # Validation
    'MAX_USERNAME_LENGTH',
    'MAX_EMAIL_LENGTH',
    'MAX_PHONE_LENGTH',
    'MAX_NAME_LENGTH',
    'MAX_DESCRIPTION_LENGTH',
    'MAX_TEXT_LENGTH',
    'MAX_PERCENTAGE',
    'MIN_PERCENTAGE',
    'MAX_RATING',
    'MIN_RATING',
    
    # Retry & Backoff
    'MAX_RETRY_ATTEMPTS',
    'MAX_RETRY_ATTEMPTS_CRITICAL',
    'MAX_RETRY_ATTEMPTS_NETWORK',
    'BACKOFF_MULTIPLIER_DEFAULT',
    'BACKOFF_MULTIPLIER_AGGRESSIVE',
]
