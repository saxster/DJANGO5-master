"""
Core Exceptions Module

Provides standardized exception handling for the Django application.

Usage:
    from apps.core.exceptions import (
        BusinessLogicError,
        DataAccessError,
        ExternalServiceError,
        SecurityViolationError,
        StandardizedExceptionHandler,
        safe_operation
    )

    # Use specific exceptions instead of generic Exception
    raise BusinessLogicError("Invalid operation", error_code="INVALID_OP")

    # Use standardized handler in views
    try:
        # your code here
    except ValidationError as e:
        return StandardizedExceptionHandler.handle_validation_error(e, "operation_name")

    # Use decorator for automatic handling
    @safe_operation("create_user")
    def create_user(data):
        # your code here
"""

from .standardized_exceptions import (
    BusinessLogicError,
    DataAccessError,
    ExternalServiceError,
    SecurityViolationError,
    ConfigurationError,
    StandardizedExceptionHandler,
    safe_operation
)

__all__ = [
    'BusinessLogicError',
    'DataAccessError',
    'ExternalServiceError',
    'SecurityViolationError',
    'ConfigurationError',
    'StandardizedExceptionHandler',
    'safe_operation'
]