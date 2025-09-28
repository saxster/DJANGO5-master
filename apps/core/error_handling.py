"""
Centralized error handling framework for YOUTILITY3.
Provides structured error responses, correlation IDs, and proper logging.
"""
import logging
import traceback
import uuid
from datetime import datetime
from django.http import JsonResponse, HttpResponse
from django.utils.deprecation import MiddlewareMixin
from django.conf import settings
from django.core.exceptions import ValidationError, PermissionDenied
from django.db import IntegrityError, DatabaseError
from django.shortcuts import render
from django.template import TemplateDoesNotExist, TemplateSyntaxError
from typing import Optional, Dict, Any

from apps.core.exceptions import (
    ExceptionFactory,
    convert_django_validation_error,
    EnhancedValidationException,
    DatabaseException,
    SecurityException
)
from apps.core.middleware.logging_sanitization import LogSanitizationService

logger = logging.getLogger("error_handler")


class CorrelationIDMiddleware(MiddlewareMixin):
    """
    Middleware to add correlation IDs to all requests for error tracking.
    """

    def __init__(self, get_response=None):
        """Initialize middleware with get_response callable."""
        self.get_response = get_response
        super().__init__(get_response)

    def process_request(self, request):
        """Add correlation ID to request."""
        correlation_id = str(uuid.uuid4())
        request.correlation_id = correlation_id

        # Add to response headers later
        request._correlation_id = correlation_id
        return None

    def process_response(self, request, response):
        """Add correlation ID to response headers."""
        if hasattr(request, "_correlation_id"):
            response["X-Correlation-ID"] = request._correlation_id
        return response


class GlobalExceptionMiddleware(MiddlewareMixin):
    """
    Global exception handler middleware for structured error responses.
    """

    def __init__(self, get_response=None):
        """Initialize middleware with get_response callable."""
        self.get_response = get_response
        super().__init__(get_response)

    def process_exception(self, request, exception):
        """Handle uncaught exceptions with structured responses."""
        correlation_id = getattr(request, "correlation_id", str(uuid.uuid4()))

        raw_traceback = traceback.format_exc()
        sanitized_traceback = LogSanitizationService.sanitize_message(raw_traceback)

        error_context = {
            "correlation_id": correlation_id,
            "path": request.path,
            "method": request.method,
            "user_id": request.user.id if request.user.is_authenticated else None,
            "ip": self._get_client_ip(request),
            "exception_type": type(exception).__name__,
            "exception_message": LogSanitizationService.sanitize_message(str(exception)),
        }

        logger.error(
            "Unhandled exception occurred",
            extra={
                **error_context,
                'sanitized_traceback': sanitized_traceback
            }
        )

        # Determine response type based on request
        if self._is_api_request(request):
            return self._create_api_error_response(exception, correlation_id)
        else:
            return self._create_web_error_response(request, exception, correlation_id)

    def _get_client_ip(self, request):
        """Get client IP address."""
        x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
        if x_forwarded_for:
            ip = x_forwarded_for.split(",")[0]
        else:
            ip = request.META.get("REMOTE_ADDR")
        return ip

    def _is_api_request(self, request):
        """Determine if request is for API endpoint."""
        return (
            request.path.startswith("/api/")
            or request.path.startswith("/graphql/")
            or request.META.get("HTTP_ACCEPT", "").startswith("application/json")
            or request.META.get("CONTENT_TYPE", "").startswith("application/json")
        )

    def _create_api_error_response(self, exception, correlation_id):
        """Create structured JSON error response for API requests."""
        if isinstance(exception, ValidationError):
            status_code = 400
            error_code = "VALIDATION_ERROR"
            message = "Invalid input data"
        elif isinstance(exception, PermissionDenied):
            status_code = 403
            error_code = "PERMISSION_DENIED"
            message = "Access denied"
        elif isinstance(exception, (IntegrityError, DatabaseError)):
            status_code = 500
            error_code = "DATABASE_ERROR"
            message = "Database operation failed"
        else:
            status_code = 500
            error_code = "INTERNAL_ERROR"
            message = "An unexpected error occurred"

        error_response = {
            "error": {
                "code": error_code,
                "message": message,
                "correlation_id": correlation_id,
                "timestamp": datetime.now().isoformat(),
            }
        }

        return JsonResponse(error_response, status=status_code)

    def _create_web_error_response(self, request, exception, correlation_id):
        """Create user-friendly error page for web requests."""
        if isinstance(exception, PermissionDenied):
            template = "errors/403.html"
            status_code = 403
        elif isinstance(exception, ValidationError):
            template = "errors/400.html"
            status_code = 400
        else:
            template = "errors/500.html"
            status_code = 500

        context = {
            "correlation_id": correlation_id,
            "error_message": "An error occurred while processing your request.",
            "support_email": getattr(
                settings, "SUPPORT_EMAIL", "support@youtility.com"
            ),
        }

        try:
            return render(request, template, context, status=status_code)
        except (TemplateDoesNotExist, TemplateSyntaxError) as e:
            # Template rendering failed - use simple fallback
            logger.error(
                f"Template rendering failed for error page: {type(e).__name__}",
                extra={
                    'correlation_id': correlation_id,
                    'template': template,
                    'error_message': str(e)
                }
            )
            return HttpResponse(
                f"Error {status_code}: An error occurred. Correlation ID: {correlation_id}",
                status=status_code,
            )
        except (TypeError, ValidationError, ValueError) as e:
            # Unexpected template rendering error - this should be very rare
            logger.critical(
                f"Critical error in template rendering: {type(e).__name__}",
                extra={
                    'correlation_id': correlation_id,
                    'template': template,
                    'error_message': str(e)
                },
                exc_info=True
            )
            return HttpResponse(
                f"Error {status_code}: An error occurred. Correlation ID: {correlation_id}",
                status=status_code,
            )


class ErrorHandler:
    """
    Centralized error handling utility class.
    """

    @staticmethod
    def get_timestamp() -> str:
        """Get current timestamp in ISO format."""
        return datetime.now().isoformat()

    @staticmethod
    def handle_exception(
        exception: Exception,
        context: Optional[Dict[str, Any]] = None,
        correlation_id: Optional[str] = None,
        level: str = "error",
    ) -> str:
        """
        Handle an exception with proper logging and return correlation ID.

        Args:
            exception: The exception to handle
            context: Additional context information
            correlation_id: Optional correlation ID (will generate if not provided)
            level: Log level ('error', 'warning', 'critical')

        Returns:
            Correlation ID for the error
        """
        if correlation_id is None:
            correlation_id = str(uuid.uuid4())

        error_data = {
            "correlation_id": correlation_id,
            "exception_type": type(exception).__name__,
            "exception_message": str(exception),
            "timestamp": datetime.now().isoformat(),
            "traceback": traceback.format_exc(),
        }

        if context:
            error_data["context"] = context

        # Log based on level
        log_method = getattr(logger, level, logger.error)
        log_method(f"Exception handled: {error_data}")

        return correlation_id

    @staticmethod
    def safe_execute(
        func,
        default_return=None,
        exception_types: tuple = (Exception,),
        context: Optional[Dict[str, Any]] = None,
        log_level: str = "error",
    ):
        """
        Safely execute a function with proper exception handling.

        Args:
            func: Function to execute
            default_return: Default value to return on exception
            exception_types: Tuple of exception types to catch
            context: Additional context for logging
            log_level: Log level for exceptions

        Returns:
            Function result or default_return on exception
        """
        try:
            return func()
        except exception_types as e:
            # Use specific exception handling instead of generic
            if isinstance(e, (ValidationError, TypeError, ValueError)):
                correlation_id = ErrorHandler.handle_exception(
                    e, context=context, level='warning'
                )
                # Convert to enhanced validation exception for consistency
                enhanced_exception = ExceptionFactory.create_validation_error(
                    str(e), correlation_id=correlation_id
                )
                # Log the enhanced exception
                logger.warning(
                    f"Validation error in safe_execute: {enhanced_exception.message}",
                    extra=enhanced_exception.to_dict()
                )
            elif isinstance(e, (DatabaseError, IntegrityError)):
                correlation_id = ErrorHandler.handle_exception(
                    e, context=context, level='error'
                )
                enhanced_exception = ExceptionFactory.create_database_error(
                    "Database operation failed", correlation_id=correlation_id
                )
                logger.error(
                    f"Database error in safe_execute: {enhanced_exception.message}",
                    extra=enhanced_exception.to_dict()
                )
            else:
                # Handle other specific exception types
                correlation_id = ErrorHandler.handle_exception(
                    e, context=context, level=log_level
                )
                logger.error(
                    f"Unexpected error in safe_execute: {type(e).__name__}",
                    extra={
                        'correlation_id': correlation_id,
                        'error_type': type(e).__name__,
                        'error_message': str(e),
                        'context': context
                    }
                )
            return default_return

    @staticmethod
    def create_error_response(
        message: str,
        error_code: str = "GENERIC_ERROR",
        status_code: int = 500,
        correlation_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> JsonResponse:
        """
        Create a structured error response for API endpoints.

        Args:
            message: User-friendly error message
            error_code: Application-specific error code
            status_code: HTTP status code
            correlation_id: Correlation ID for tracking
            details: Additional error details

        Returns:
            JsonResponse with structured error data
        """
        if correlation_id is None:
            correlation_id = str(uuid.uuid4())

        error_response = {
            "error": {
                "code": error_code,
                "message": message,
                "correlation_id": correlation_id,
                "timestamp": datetime.now().isoformat(),
            }
        }

        if details:
            error_response["error"]["details"] = details

        return JsonResponse(error_response, status=status_code)

    @staticmethod
    def create_secure_task_response(
        success: bool = True,
        message: str = "Task completed successfully",
        data: Optional[Dict[str, Any]] = None,
        error_code: Optional[str] = None,
        correlation_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Create a secure task response that never exposes stack traces.

        Args:
            success: Whether the task was successful
            message: User-safe message about the task result
            data: Additional data to include in response
            error_code: Error code if task failed
            correlation_id: Correlation ID for tracking

        Returns:
            Dictionary with secure task response data
        """
        if correlation_id is None:
            correlation_id = str(uuid.uuid4())

        response = {
            "success": success,
            "message": message,
            "correlation_id": correlation_id,
            "timestamp": datetime.now().isoformat(),
        }

        if data:
            response["data"] = data

        if error_code and not success:
            response["error_code"] = error_code

        # NEVER include traceback or detailed error info in task responses
        return response

    @staticmethod
    def handle_task_exception(
        exception: Exception,
        task_name: str,
        task_params: Optional[Dict[str, Any]] = None,
        correlation_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Handle exceptions in background tasks with secure response.

        This method:
        1. Logs full exception details (including stack trace) for debugging
        2. Returns sanitized response without sensitive information
        3. Uses correlation IDs for tracking

        Args:
            exception: The exception that occurred
            task_name: Name of the task that failed
            task_params: Parameters passed to the task (sensitive data will be redacted)
            correlation_id: Optional correlation ID

        Returns:
            Secure task response dictionary
        """
        if correlation_id is None:
            correlation_id = str(uuid.uuid4())

        # Sanitize task parameters for logging (remove sensitive data)
        safe_params = ErrorHandler._sanitize_task_params(task_params) if task_params else {}

        # Log full exception details (including stack trace) for debugging
        error_context = {
            "correlation_id": correlation_id,
            "task_name": task_name,
            "task_params": safe_params,
            "exception_type": type(exception).__name__,
            "exception_message": str(exception),
            "traceback": traceback.format_exc(),  # Full stack trace for logs only
        }

        logger.error(f"Background task failed: {error_context}")

        # Return secure response without stack trace
        return ErrorHandler.create_secure_task_response(
            success=False,
            message="Task execution failed",
            error_code="TASK_EXECUTION_ERROR",
            correlation_id=correlation_id,
        )

    @staticmethod
    def _sanitize_task_params(params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Sanitize task parameters to remove sensitive information before logging.

        Args:
            params: Original task parameters

        Returns:
            Sanitized parameters safe for logging
        """
        if not isinstance(params, dict):
            return {"params": str(type(params).__name__)}

        sanitized = {}
        sensitive_keys = {
            'password', 'passwd', 'pwd', 'secret', 'key', 'token', 'auth',
            'credential', 'cert', 'api_key', 'access_token', 'refresh_token'
        }

        for key, value in params.items():
            key_lower = str(key).lower()
            if any(sensitive in key_lower for sensitive in sensitive_keys):
                sanitized[key] = "[REDACTED]"
            elif isinstance(value, (str, int, float, bool)):
                sanitized[key] = value
            elif isinstance(value, (dict, list)):
                sanitized[key] = f"<{type(value).__name__}>"
            else:
                sanitized[key] = str(type(value).__name__)

        return sanitized

    @staticmethod
    def handle_api_error(
        request,
        exception: Exception,
        status_code: int = 500,
        correlation_id: Optional[str] = None,
    ) -> JsonResponse:
        """
        Handle API errors with proper JSON response format.

        Args:
            request: Django HttpRequest object
            exception: The exception that occurred
            status_code: HTTP status code to return
            correlation_id: Optional correlation ID

        Returns:
            JsonResponse with structured error data
        """
        if correlation_id is None:
            correlation_id = getattr(request, "correlation_id", str(uuid.uuid4()))

        # Determine error code and message based on exception type
        if isinstance(exception, ValidationError):
            error_code = "VALIDATION_ERROR"
            message = "Invalid input data"
        elif isinstance(exception, PermissionDenied):
            error_code = "PERMISSION_DENIED" 
            message = "Access denied"
            status_code = 403
        elif hasattr(exception, '__class__') and exception.__class__.__name__ == 'SuspiciousOperation':
            error_code = "SECURITY_ERROR"
            message = str(exception)
            status_code = 400
        elif isinstance(exception, (IntegrityError, DatabaseError)):
            error_code = "DATABASE_ERROR"
            message = "Database operation failed"
            status_code = 500
        else:
            error_code = "INTERNAL_ERROR"
            message = "An unexpected error occurred"
            status_code = 500

        error_response = {
            "error": {
                "code": error_code,
                "message": message,
                "correlation_id": correlation_id,
                "timestamp": datetime.now().isoformat(),
            }
        }

        return JsonResponse(error_response, status=status_code)


class ValidationError(Exception):
    """Custom validation error with structured details."""

    def __init__(
        self, message: str, field: Optional[str] = None, code: Optional[str] = None
    ):
        self.message = message
        self.field = field
        self.code = code
        super().__init__(message)


class BusinessLogicError(Exception):
    """Custom exception for business logic violations."""

    def __init__(self, message: str, code: Optional[str] = None):
        self.message = message
        self.code = code
        super().__init__(message)


def handle_db_exception(func):
    """
    Decorator to handle database exceptions with proper logging.
    """

    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except IntegrityError as e:
            correlation_id = ErrorHandler.handle_exception(
                e,
                context={"function": func.__name__, "args": str(args)[:100]},
                level="warning",
            )
            raise BusinessLogicError(
                f"Data integrity constraint violated. Correlation ID: {correlation_id}"
            )
        except DatabaseError as e:
            correlation_id = ErrorHandler.handle_exception(
                e,
                context={"function": func.__name__, "args": str(args)[:100]},
                level="error",
            )
            raise BusinessLogicError(
                f"Database operation failed. Correlation ID: {correlation_id}"
            )

    return wrapper


def handle_validation_exception(func):
    """
    Decorator to handle validation exceptions with proper logging.
    """

    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except (ValueError, TypeError) as e:
            correlation_id = ErrorHandler.handle_exception(
                e,
                context={"function": func.__name__, "args": str(args)[:100]},
                level="warning",
            )
            raise ValidationError(
                f"Invalid input data. Correlation ID: {correlation_id}"
            )

    return wrapper
