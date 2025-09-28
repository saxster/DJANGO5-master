"""
Exception Handling Mixin

Eliminates duplicated POST exception handling patterns found in 800+ lines
across 15+ view files.

Following .claude/rules.md:
- Specific exception handling (Rule 11)
- No debug info exposure (Rule 5)
- Correlation ID tracking
- Sanitized error responses
"""

import logging
from typing import Dict, Any, Callable, Optional
from functools import wraps
from django.http import JsonResponse
from django.core.exceptions import ValidationError, PermissionDenied, ObjectDoesNotExist
from django.db import IntegrityError, DatabaseError
from apps.core.error_handling import ErrorHandler
from apps.core.exceptions import (
    ActivityManagementException,
    DatabaseException,
    SystemException,
    BusinessLogicException,
    ServiceException,
)

logger = logging.getLogger(__name__)

__all__ = [
    'ExceptionHandlingMixin',
    'with_exception_handling',
]


class ExceptionHandlingMixin:
    """
    Mixin providing standardized exception handling for view methods.

    Handles common exception types with appropriate HTTP status codes
    and correlation ID tracking for debugging.

    Usage:
        class AssetView(ExceptionHandlingMixin, LoginRequiredMixin, View):
            def post(self, request):
                return self.handle_exceptions(request, self._process_post)

            def _process_post(self, request):
                # Your business logic here
                # Exceptions are automatically caught and handled
                ...
    """

    def handle_exceptions(self, request, handler: Callable, *args, **kwargs):
        """
        Execute handler with comprehensive exception handling.

        Args:
            request: HTTP request object
            handler: Callable to execute with exception protection
            *args, **kwargs: Arguments to pass to handler

        Returns:
            JsonResponse with appropriate status code
        """
        view_name = self.__class__.__name__

        try:
            return handler(request, *args, **kwargs)

        except ValidationError as e:
            logger.warning(f"{view_name} form validation error: {e}")
            error_data = ErrorHandler.handle_exception(request, e, f"{view_name} validation failed")
            return JsonResponse({
                "error": "Invalid form data",
                "details": str(e),
                "correlation_id": error_data.get("correlation_id")
            }, status=400)

        except ActivityManagementException as e:
            logger.error(f"{view_name} activity management error: {e}")
            error_data = ErrorHandler.handle_exception(request, e, f"{view_name} activity error")
            return JsonResponse({
                "error": "Activity management error",
                "correlation_id": error_data.get("correlation_id")
            }, status=422)

        except BusinessLogicException as e:
            logger.error(f"{view_name} business logic error: {e}")
            error_data = ErrorHandler.handle_exception(request, e, f"{view_name} business error")
            return JsonResponse({
                "error": "Business logic error",
                "correlation_id": error_data.get("correlation_id")
            }, status=422)

        except PermissionDenied as e:
            logger.warning(f"{view_name} permission denied: {e}")
            error_data = ErrorHandler.handle_exception(request, e, f"{view_name} access denied")
            return JsonResponse({
                "error": "Access denied",
                "correlation_id": error_data.get("correlation_id")
            }, status=403)

        except ObjectDoesNotExist as e:
            logger.error(f"{view_name} object not found: {e}")
            error_data = ErrorHandler.handle_exception(request, e, f"{view_name} not found")
            return JsonResponse({
                "error": "Object not found",
                "correlation_id": error_data.get("correlation_id")
            }, status=404)

        except (ValueError, TypeError) as e:
            logger.warning(f"{view_name} data processing error: {e}")
            error_data = ErrorHandler.handle_exception(request, e, f"{view_name} data error")
            return JsonResponse({
                "error": "Invalid data format",
                "correlation_id": error_data.get("correlation_id")
            }, status=400)

        except (IntegrityError, DatabaseError) as e:
            logger.error(f"{view_name} database error: {e}")
            error_data = ErrorHandler.handle_exception(request, e, f"{view_name} database error")
            return JsonResponse({
                "error": "Database operation failed",
                "correlation_id": error_data.get("correlation_id")
            }, status=422)

        except (SystemException, ServiceException) as e:
            logger.critical(f"{view_name} system error: {e}")
            error_data = ErrorHandler.handle_exception(request, e, f"{view_name} system error")
            return JsonResponse({
                "error": "System error occurred",
                "correlation_id": error_data.get("correlation_id")
            }, status=500)


def with_exception_handling(method):
    """
    Decorator for adding exception handling to individual methods.

    Usage:
        @with_exception_handling
        def post(self, request):
            # Your logic here
            ...
    """
    @wraps(method)
    def wrapper(self, request, *args, **kwargs):
        if not isinstance(self, ExceptionHandlingMixin):
            raise TypeError(
                f"with_exception_handling requires ExceptionHandlingMixin, "
                f"got {self.__class__.__name__}"
            )

        return self.handle_exceptions(request, method, *args, **kwargs)

    return wrapper