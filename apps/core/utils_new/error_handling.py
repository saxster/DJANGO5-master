"""
Error handling utilities for consistent exception management.

This module provides standardized error handling patterns to replace
bare exception handling throughout the application.
"""

import logging
from django.http import JsonResponse
from django.db import IntegrityError
from django.core.exceptions import ValidationError
from django.contrib import messages
from functools import wraps

logger = logging.getLogger(__name__)


class ErrorHandler:
    """Centralized error handling utility."""

    @staticmethod
    def handle_form_errors(e, logger_instance=None):
        """Handle common form processing errors."""
        log = logger_instance or logger

        if isinstance(e, (ValueError, KeyError)):
            log.error(f"Form data validation error: {e}", exc_info=True)
            return JsonResponse(
                {"errors": "Invalid form data provided"},
                status=400
            )
        elif isinstance(e, IntegrityError):
            log.error(f"Database integrity error: {e}", exc_info=True)
            return JsonResponse(
                {"errors": "Data integrity error - please check your input"},
                status=422
            )
        elif isinstance(e, ValidationError):
            log.error(f"Validation error: {e}", exc_info=True)
            return JsonResponse(
                {"errors": "Validation failed - please check your input"},
                status=422
            )
        else:
            log.critical(f"Unexpected error: {e}", exc_info=True)
            return JsonResponse(
                {"errors": "An unexpected error occurred"},
                status=500
            )

    @staticmethod
    def handle_view_errors(e, request, logger_instance=None, redirect_url="/dashboard"):
        """Handle common view errors with messages."""
        log = logger_instance or logger

        if isinstance(e, (ValueError, KeyError)):
            log.error(f"View data error: {e}", exc_info=True)
            messages.error(request, "Invalid data provided", "alert alert-danger")
        elif isinstance(e, IntegrityError):
            log.error(f"Database integrity error in view: {e}", exc_info=True)
            messages.error(request, "Data integrity error", "alert alert-danger")
        elif isinstance(e, ValidationError):
            log.error(f"Validation error in view: {e}", exc_info=True)
            messages.error(request, "Validation failed", "alert alert-danger")
        else:
            log.critical(f"Unexpected view error: {e}", exc_info=True)
            messages.error(request, "An unexpected error occurred", "alert alert-danger")

        from django.shortcuts import redirect
        return redirect(redirect_url)


def handle_exceptions(error_type="form", redirect_url="/dashboard"):
    """
    Decorator for standardized exception handling.

    Args:
        error_type: "form" for JSON responses, "view" for HTML responses with messages
        redirect_url: URL to redirect to for view errors
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                # Get logger for the module
                module_logger = logging.getLogger(func.__module__)

                if error_type == "form":
                    return ErrorHandler.handle_form_errors(e, module_logger)
                else:
                    # Assume first arg is request for view functions
                    request = args[1] if len(args) > 1 else args[0]
                    return ErrorHandler.handle_view_errors(
                        e, request, module_logger, redirect_url
                    )
        return wrapper
    return decorator


def safe_property(fallback_value=""):
    """
    Decorator for model properties that might fail.

    Args:
        fallback_value: Value to return if property calculation fails
    """
    def decorator(func):
        @wraps(func)
        def wrapper(self):
            try:
                return func(self)
            except (AttributeError, IndexError, TypeError, ValueError) as e:
                # Log the error but don't raise it for properties
                logger.debug(f"Property {func.__name__} failed: {e}")
                return fallback_value
        return wrapper
    return decorator


# Example usage patterns:
"""
# For form processing views:
@handle_exceptions(error_type="form")
def post(self, request, *args, **kwargs):
    # Your form processing logic here
    pass

# For HTML views:
@handle_exceptions(error_type="view", redirect_url="/custom/redirect/")
def get(self, request, *args, **kwargs):
    # Your view logic here
    pass

# For model properties:
@safe_property(fallback_value="Unknown Location")
def location_display(self):
    coords = self.location.coords
    return f"Lat: {coords[1]:.6f}, Lng: {coords[0]:.6f}"
"""