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

from django.core.exceptions import ValidationError
from .standardized_exceptions import (
    BusinessLogicError,
    DataAccessError,
    ExternalServiceError,
    SecurityViolationError,
    ConfigurationError,
    StandardizedExceptionHandler,
    safe_operation
)

try:
    # Legacy file validation exception for backward compatibility
    from ..exceptions import FileValidationException  # type: ignore
except ImportError:
    class FileValidationException(ValidationError):  # type: ignore
        """Fallback FileValidationException when legacy module is unavailable."""
        pass

# Backward compatibility aliases for legacy code
DatabaseException = DataAccessError
SecurityException = SecurityViolationError
CSRFException = SecurityViolationError  # CSRF violations are security violations
CacheException = ConfigurationError  # Cache errors are configuration/system errors
IntegrationException = ExternalServiceError  # Integration errors are external service errors
EnhancedValidationException = ValidationError
BusinessLogicException = BusinessLogicError  # Alias for consistency
ServiceException = ExternalServiceError  # Service communication errors
SystemException = ConfigurationError  # System/configuration errors
AuthenticationError = SecurityViolationError  # Authentication failures are security violations
WrongCredsError = SecurityViolationError  # Wrong credentials are security violations
PermissionDeniedError = SecurityViolationError  # Permission denied is security violation
UserManagementException = BusinessLogicError  # User management errors are business logic
EmailServiceException = ExternalServiceError  # Email service errors are external service issues
ActivityManagementException = BusinessLogicError  # Activity management errors are business logic
DatabaseIntegrityException = DataAccessError  # Database integrity errors are data access issues
NoClientPeopleError = BusinessLogicError  # No client/people assignment errors are business logic
MultiDevicesError = BusinessLogicError  # Multiple device assignment errors are business logic
NotRegisteredError = SecurityViolationError  # Unregistered user/device errors are security violations
NoSiteError = BusinessLogicError  # No site assignment errors are business logic
NotBelongsToClientError = SecurityViolationError  # Wrong client assignment is security violation
SchedulingException = BusinessLogicError  # Scheduling/cron errors are business logic
LLMServiceException = ExternalServiceError  # LLM service errors are external service errors


def convert_django_validation_error(error, correlation_id=None):
    """
    Convert Django ValidationError to enhanced validation exception.

    Args:
        error: Django ValidationError
        correlation_id: Optional correlation ID for tracking

    Returns:
        ValidationError with additional context
    """
    if hasattr(error, 'message_dict'):
        message = str(error.message_dict)
    elif hasattr(error, 'messages'):
        message = '; '.join(error.messages)
    else:
        message = str(error)

    enhanced_error = ValidationError(message)
    enhanced_error.correlation_id = correlation_id
    return enhanced_error


class ExceptionFactory:
    """
    Factory for creating standardized exceptions with consistent formatting.

    Provides backward compatibility for legacy code using ExceptionFactory pattern.
    """

    @staticmethod
    def create_validation_error(message, correlation_id=None, field=None, code=None):
        """
        Create an enhanced validation error.

        Args:
            message: Error message
            correlation_id: Optional correlation ID
            field: Optional field name
            code: Optional error code

        Returns:
            ValidationError instance
        """
        error = ValidationError(message)
        error.correlation_id = correlation_id
        error.field = field
        error.code = code
        error.message = message
        return error

    @staticmethod
    def create_database_error(message, correlation_id=None, query_info=None):
        """
        Create a database error.

        Args:
            message: Error message
            correlation_id: Optional correlation ID
            query_info: Optional query information

        Returns:
            DataAccessError instance
        """
        error = DataAccessError(message, query_info=query_info)
        error.correlation_id = correlation_id
        error.message = message
        return error

    @staticmethod
    def create_security_error(message, correlation_id=None, violation_type=None):
        """
        Create a security violation error.

        Args:
            message: Error message
            correlation_id: Optional correlation ID
            violation_type: Type of security violation

        Returns:
            SecurityViolationError instance
        """
        error = SecurityViolationError(message, violation_type=violation_type or "generic")
        error.correlation_id = correlation_id
        error.message = message
        return error

    @staticmethod
    def to_dict(error):
        """
        Convert exception to dictionary for logging.

        Args:
            error: Exception instance

        Returns:
            Dictionary with error details
        """
        return {
            'error_type': type(error).__name__,
            'message': str(error),
            'correlation_id': getattr(error, 'correlation_id', None),
            'field': getattr(error, 'field', None),
            'code': getattr(error, 'code', None),
        }


__all__ = [
    'BusinessLogicError',
    'DataAccessError',
    'ExternalServiceError',
    'SecurityViolationError',
    'ConfigurationError',
    'StandardizedExceptionHandler',
    'safe_operation',
    # Backward compatibility aliases
    'DatabaseException',
    'SecurityException',
    'CSRFException',
    'CacheException',
    'IntegrationException',
    'EnhancedValidationException',
    'BusinessLogicException',
    'ServiceException',
    'SystemException',
    'AuthenticationError',
    'WrongCredsError',
    'PermissionDeniedError',
    'UserManagementException',
    'EmailServiceException',
    'ActivityManagementException',
    'DatabaseIntegrityException',
    'NoClientPeopleError',
    'MultiDevicesError',
    'NotRegisteredError',
    'NoSiteError',
    'NotBelongsToClientError',
    'SchedulingException',
    'LLMServiceException',
    'FileValidationException',
    'convert_django_validation_error',
    'ExceptionFactory',
]
