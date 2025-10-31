"""
Standardized Error Code Taxonomy

Machine-readable error codes for all APIs.
Follows .claude/rules.md Rule #7 (< 150 lines).
"""

from enum import Enum


class ErrorCode(Enum):
    """
    Standardized error codes across the platform.

    Format: CATEGORY_SPECIFIC_ERROR
    Categories: AUTH, VALIDATION, BUSINESS, RATE_LIMIT, SERVER
    """

    # Authentication & Authorization (1000-1999)
    AUTH_REQUIRED = ("AUTH_001", "Authentication required")
    AUTH_INVALID_CREDENTIALS = ("AUTH_002", "Invalid credentials")
    AUTH_TOKEN_EXPIRED = ("AUTH_003", "Authentication token expired")
    AUTH_TOKEN_INVALID = ("AUTH_004", "Invalid authentication token")
    AUTH_INSUFFICIENT_PERMISSIONS = ("AUTH_005", "Insufficient permissions")
    AUTH_ACCOUNT_DISABLED = ("AUTH_006", "Account disabled")
    AUTH_MFA_REQUIRED = ("AUTH_007", "Multi-factor authentication required")

    # Validation (2000-2999)
    VALIDATION_FAILED = ("VAL_001", "Validation failed")
    VALIDATION_MISSING_FIELD = ("VAL_002", "Required field missing")
    VALIDATION_INVALID_FORMAT = ("VAL_003", "Invalid format")
    VALIDATION_INVALID_VALUE = ("VAL_004", "Invalid value")
    VALIDATION_OUT_OF_RANGE = ("VAL_005", "Value out of range")
    VALIDATION_DUPLICATE = ("VAL_006", "Duplicate value")

    # Business Logic (3000-3999)
    BUSINESS_RULE_VIOLATION = ("BUS_001", "Business rule violation")
    RESOURCE_NOT_FOUND = ("BUS_002", "Resource not found")
    RESOURCE_ALREADY_EXISTS = ("BUS_003", "Resource already exists")
    OPERATION_NOT_ALLOWED = ("BUS_004", "Operation not allowed")
    RESOURCE_LOCKED = ("BUS_005", "Resource locked")
    QUOTA_EXCEEDED = ("BUS_006", "Quota exceeded")

    # Rate Limiting (4000-4999)
    RATE_LIMIT_EXCEEDED = ("RATE_001", "Rate limit exceeded")
    RATE_LIMIT_COMPLEXITY = ("RATE_002", "Query complexity limit exceeded")
    RATE_LIMIT_CONCURRENT = ("RATE_003", "Concurrent request limit exceeded")

    # Server Errors (5000-5999)
    SERVER_ERROR = ("SRV_001", "Internal server error")
    SERVER_DATABASE_ERROR = ("SRV_002", "Database error")
    SERVER_EXTERNAL_SERVICE = ("SRV_003", "External service error")
    SERVER_TIMEOUT = ("SRV_004", "Request timeout")
    SERVER_UNAVAILABLE = ("SRV_005", "Service unavailable")

    def __init__(self, code: str, message: str):
        self.code = code
        self.default_message = message

    def to_dict(self):
        """Convert to API response format."""
        return {
            'code': self.code,
            'message': self.default_message
        }


# HTTP status code mapping
ERROR_CODE_HTTP_STATUS = {
    # Authentication
    ErrorCode.AUTH_REQUIRED: 401,
    ErrorCode.AUTH_INVALID_CREDENTIALS: 401,
    ErrorCode.AUTH_TOKEN_EXPIRED: 401,
    ErrorCode.AUTH_TOKEN_INVALID: 401,
    ErrorCode.AUTH_INSUFFICIENT_PERMISSIONS: 403,
    ErrorCode.AUTH_ACCOUNT_DISABLED: 403,
    ErrorCode.AUTH_MFA_REQUIRED: 403,

    # Validation
    ErrorCode.VALIDATION_FAILED: 400,
    ErrorCode.VALIDATION_MISSING_FIELD: 400,
    ErrorCode.VALIDATION_INVALID_FORMAT: 400,
    ErrorCode.VALIDATION_INVALID_VALUE: 400,
    ErrorCode.VALIDATION_OUT_OF_RANGE: 400,
    ErrorCode.VALIDATION_DUPLICATE: 409,

    # Business Logic
    ErrorCode.BUSINESS_RULE_VIOLATION: 422,
    ErrorCode.RESOURCE_NOT_FOUND: 404,
    ErrorCode.RESOURCE_ALREADY_EXISTS: 409,
    ErrorCode.OPERATION_NOT_ALLOWED: 403,
    ErrorCode.RESOURCE_LOCKED: 423,
    ErrorCode.QUOTA_EXCEEDED: 429,

    # Rate Limiting
    ErrorCode.RATE_LIMIT_EXCEEDED: 429,
    ErrorCode.RATE_LIMIT_COMPLEXITY: 429,
    ErrorCode.RATE_LIMIT_CONCURRENT: 429,

    # Server Errors
    ErrorCode.SERVER_ERROR: 500,
    ErrorCode.SERVER_DATABASE_ERROR: 500,
    ErrorCode.SERVER_EXTERNAL_SERVICE: 502,
    ErrorCode.SERVER_TIMEOUT: 504,
    ErrorCode.SERVER_UNAVAILABLE: 503,
}


def get_http_status(error_code: ErrorCode) -> int:
    """Get HTTP status code for error code."""
    return ERROR_CODE_HTTP_STATUS.get(error_code, 500)
