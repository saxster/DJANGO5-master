"""
Standardized Exception Handling

This module provides specific exception types and handlers to replace
generic 'except Exception:' patterns throughout the codebase.

Following Django best practices for exception handling:
- Specific exception types for different error scenarios
- Proper logging with correlation IDs
- User-friendly error messages
- Security-conscious error responses
"""

import logging
from typing import Optional, Dict, Any
from django.core.exceptions import ValidationError, PermissionDenied
from django.db import DatabaseError, IntegrityError, OperationalError
from django.http import JsonResponse, HttpResponse
from django.contrib import messages


logger = logging.getLogger("django")
security_logger = logging.getLogger("security")
error_logger = logging.getLogger("error_logger")


class BusinessLogicError(Exception):
    """
    Exception for business logic violations.

    Use this instead of generic Exception for business rule violations.
    """
    def __init__(self, message: str, error_code: str = None, context: Dict = None):
        self.message = message
        self.error_code = error_code
        self.context = context or {}
        super().__init__(self.message)


class DataAccessError(Exception):
    """
    Exception for data access issues.

    Use this for database-related errors that aren't covered by Django's built-in exceptions.
    """
    def __init__(self, message: str, original_error: Exception = None, query_info: Dict = None):
        self.message = message
        self.original_error = original_error
        self.query_info = query_info or {}
        super().__init__(self.message)


class ExternalServiceError(Exception):
    """
    Exception for external service communication failures.

    Use this for API calls, file system operations, etc.
    """
    def __init__(self, message: str, service_name: str, status_code: int = None, response_data: Dict = None):
        self.message = message
        self.service_name = service_name
        self.status_code = status_code
        self.response_data = response_data or {}
        super().__init__(self.message)


class SecurityViolationError(Exception):
    """
    Exception for security violations.

    Use this for authentication, authorization, and security-related errors.
    """
    def __init__(self, message: str, violation_type: str, user_id: int = None, ip_address: str = None):
        self.message = message
        self.violation_type = violation_type
        self.user_id = user_id
        self.ip_address = ip_address
        super().__init__(self.message)


class ConfigurationError(Exception):
    """
    Exception for configuration-related errors.

    Use this for missing settings, invalid configurations, etc.
    """
    def __init__(self, message: str, setting_name: str = None, expected_type: str = None):
        self.message = message
        self.setting_name = setting_name
        self.expected_type = expected_type
        super().__init__(self.message)


class StandardizedExceptionHandler:
    """
    Centralized exception handling with proper logging and user feedback.

    Replaces generic 'except Exception:' patterns with specific handling.
    """

    @staticmethod
    def handle_database_error(
        error: Exception,
        operation: str,
        correlation_id: str = None,
        user_id: int = None
    ) -> JsonResponse:
        """
        Handle database-related errors with proper logging.

        Args:
            error: The exception that occurred
            operation: Description of the operation that failed
            correlation_id: Request correlation ID for tracking
            user_id: ID of the user who triggered the error

        Returns:
            JsonResponse with appropriate error message
        """
        # Log the error with context
        logger.error(
            f"Database error during {operation}",
            extra={
                'error_type': type(error).__name__,
                'error_message': str(error),
                'operation': operation,
                'correlation_id': correlation_id,
                'user_id': user_id
            },
            exc_info=True
        )

        # Determine specific error type and response
        if isinstance(error, IntegrityError):
            return JsonResponse({
                'success': False,
                'error': 'Data integrity constraint violation',
                'message': 'The operation conflicts with existing data',
                'correlation_id': correlation_id
            }, status=400)

        elif isinstance(error, OperationalError):
            return JsonResponse({
                'success': False,
                'error': 'Database operation failed',
                'message': 'Database is temporarily unavailable',
                'correlation_id': correlation_id
            }, status=503)

        elif isinstance(error, DatabaseError):
            return JsonResponse({
                'success': False,
                'error': 'Database error',
                'message': 'A database error occurred',
                'correlation_id': correlation_id
            }, status=500)

        else:
            return JsonResponse({
                'success': False,
                'error': 'Database operation failed',
                'message': 'An unexpected database error occurred',
                'correlation_id': correlation_id
            }, status=500)

    @staticmethod
    def handle_validation_error(
        error: ValidationError,
        operation: str,
        correlation_id: str = None,
        user_id: int = None
    ) -> JsonResponse:
        """
        Handle validation errors with detailed feedback.

        Args:
            error: The ValidationError that occurred
            operation: Description of the operation that failed
            correlation_id: Request correlation ID for tracking
            user_id: ID of the user who triggered the error

        Returns:
            JsonResponse with validation error details
        """
        logger.warning(
            f"Validation error during {operation}",
            extra={
                'error_messages': error.messages if hasattr(error, 'messages') else [str(error)],
                'operation': operation,
                'correlation_id': correlation_id,
                'user_id': user_id
            }
        )

        # Extract validation messages
        if hasattr(error, 'message_dict'):
            errors = error.message_dict
        elif hasattr(error, 'messages'):
            errors = {'general': error.messages}
        else:
            errors = {'general': [str(error)]}

        return JsonResponse({
            'success': False,
            'error': 'Validation failed',
            'errors': errors,
            'correlation_id': correlation_id
        }, status=400)

    @staticmethod
    def handle_permission_error(
        error: PermissionDenied,
        operation: str,
        correlation_id: str = None,
        user_id: int = None,
        ip_address: str = None
    ) -> JsonResponse:
        """
        Handle permission denied errors with security logging.

        Args:
            error: The PermissionDenied exception
            operation: Description of the operation that failed
            correlation_id: Request correlation ID for tracking
            user_id: ID of the user who triggered the error
            ip_address: IP address of the request

        Returns:
            JsonResponse with permission error message
        """
        # Log security violation
        security_logger.warning(
            f"Permission denied for {operation}",
            extra={
                'error_message': str(error),
                'operation': operation,
                'correlation_id': correlation_id,
                'user_id': user_id,
                'ip_address': ip_address,
                'violation_type': 'permission_denied'
            }
        )

        return JsonResponse({
            'success': False,
            'error': 'Permission denied',
            'message': 'You do not have permission to perform this operation',
            'correlation_id': correlation_id
        }, status=403)

    @staticmethod
    def handle_business_logic_error(
        error: BusinessLogicError,
        operation: str,
        correlation_id: str = None,
        user_id: int = None
    ) -> JsonResponse:
        """
        Handle business logic errors with context.

        Args:
            error: The BusinessLogicError that occurred
            operation: Description of the operation that failed
            correlation_id: Request correlation ID for tracking
            user_id: ID of the user who triggered the error

        Returns:
            JsonResponse with business logic error details
        """
        logger.warning(
            f"Business logic error during {operation}",
            extra={
                'error_message': error.message,
                'error_code': error.error_code,
                'context': error.context,
                'operation': operation,
                'correlation_id': correlation_id,
                'user_id': user_id
            }
        )

        return JsonResponse({
            'success': False,
            'error': 'Business logic violation',
            'message': error.message,
            'error_code': error.error_code,
            'correlation_id': correlation_id
        }, status=400)

    @staticmethod
    def handle_external_service_error(
        error: ExternalServiceError,
        operation: str,
        correlation_id: str = None,
        user_id: int = None
    ) -> JsonResponse:
        """
        Handle external service errors with retry information.

        Args:
            error: The ExternalServiceError that occurred
            operation: Description of the operation that failed
            correlation_id: Request correlation ID for tracking
            user_id: ID of the user who triggered the error

        Returns:
            JsonResponse with external service error details
        """
        error_logger.error(
            f"External service error during {operation}",
            extra={
                'error_message': error.message,
                'service_name': error.service_name,
                'status_code': error.status_code,
                'operation': operation,
                'correlation_id': correlation_id,
                'user_id': user_id
            }
        )

        return JsonResponse({
            'success': False,
            'error': 'External service unavailable',
            'message': f'Service {error.service_name} is temporarily unavailable',
            'retry_after': 300,  # Suggest retry after 5 minutes
            'correlation_id': correlation_id
        }, status=503)

    @staticmethod
    def handle_security_violation(
        error: SecurityViolationError,
        operation: str,
        correlation_id: str = None
    ) -> JsonResponse:
        """
        Handle security violations with comprehensive logging.

        Args:
            error: The SecurityViolationError that occurred
            operation: Description of the operation that failed
            correlation_id: Request correlation ID for tracking

        Returns:
            JsonResponse with security error message (minimal details)
        """
        # Log security violation with full details
        security_logger.critical(
            f"Security violation during {operation}",
            extra={
                'violation_type': error.violation_type,
                'error_message': error.message,
                'user_id': error.user_id,
                'ip_address': error.ip_address,
                'operation': operation,
                'correlation_id': correlation_id
            }
        )

        # Return minimal error information to prevent information disclosure
        return JsonResponse({
            'success': False,
            'error': 'Security violation',
            'message': 'Access denied',
            'correlation_id': correlation_id
        }, status=403)

    @staticmethod
    def handle_generic_error(
        error: Exception,
        operation: str,
        correlation_id: str = None,
        user_id: int = None
    ) -> JsonResponse:
        """
        Handle unexpected errors as a last resort.

        Use this only when specific error types don't match.

        Args:
            error: The unexpected exception
            operation: Description of the operation that failed
            correlation_id: Request correlation ID for tracking
            user_id: ID of the user who triggered the error

        Returns:
            JsonResponse with generic error message
        """
        # Log the unexpected error with full details
        error_logger.error(
            f"Unexpected error during {operation}",
            extra={
                'error_type': type(error).__name__,
                'error_message': str(error),
                'operation': operation,
                'correlation_id': correlation_id,
                'user_id': user_id
            },
            exc_info=True
        )

        return JsonResponse({
            'success': False,
            'error': 'Internal server error',
            'message': 'An unexpected error occurred. Please try again later.',
            'correlation_id': correlation_id
        }, status=500)

    @staticmethod
    def add_error_message_to_request(request, message: str, level: str = "error"):
        """
        Add error message to Django messages framework.

        Args:
            request: Django request object
            message: Error message to display
            level: Message level (error, warning, info, success)
        """
        message_level = getattr(messages, level.upper(), messages.ERROR)
        messages.add_message(request, message_level, message)


def safe_operation(operation_name: str, correlation_id: str = None, user_id: int = None):
    """
    Decorator for safe operation execution with standardized error handling.

    Example usage:

    @safe_operation("user_creation", correlation_id=request.correlation_id, user_id=request.user.id)
    def create_user(user_data):
        # Your operation code here
        pass
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except ValidationError as e:
                return StandardizedExceptionHandler.handle_validation_error(
                    e, operation_name, correlation_id, user_id
                )
            except PermissionDenied as e:
                return StandardizedExceptionHandler.handle_permission_error(
                    e, operation_name, correlation_id, user_id
                )
            except (DatabaseError, IntegrityError, OperationalError) as e:
                return StandardizedExceptionHandler.handle_database_error(
                    e, operation_name, correlation_id, user_id
                )
            except BusinessLogicError as e:
                return StandardizedExceptionHandler.handle_business_logic_error(
                    e, operation_name, correlation_id, user_id
                )
            except ExternalServiceError as e:
                return StandardizedExceptionHandler.handle_external_service_error(
                    e, operation_name, correlation_id, user_id
                )
            except SecurityViolationError as e:
                return StandardizedExceptionHandler.handle_security_violation(
                    e, operation_name, correlation_id
                )
            except (ValueError, TypeError, AttributeError) as e:
                return StandardizedExceptionHandler.handle_generic_error(
                    e, operation_name, correlation_id, user_id
                )
        return wrapper
    return decorator