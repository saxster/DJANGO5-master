"""
Logging Sanitization Middleware and Utilities.

This module provides comprehensive sanitization of sensitive data in log messages
to prevent accidental exposure of PII, credentials, and other sensitive information.

CRITICAL: This addresses the security vulnerability where user emails, mobile numbers,
and other sensitive data were being logged in plaintext.
"""
import re
import logging
from typing import Dict, Any, Optional, Union, List
from django.utils.deprecation import MiddlewareMixin
from django.conf import settings

# Configure sanitized logger
sanitized_logger = logging.getLogger("sanitized")


class LogSanitizationService:
    """
    Service for sanitizing sensitive data from log messages and context.

    This service provides comprehensive data sanitization to prevent accidental
    exposure of sensitive information in log files.
    """

    # Sensitive data patterns (compiled regex for performance)
    EMAIL_PATTERN = re.compile(
        r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
        re.IGNORECASE
    )

    PHONE_PATTERN = re.compile(
        r'(?:\+?1[-.\s]?)?(?:\(?[0-9]{3}\)?[-.\s]?)?[0-9]{3}[-.\s]?[0-9]{4}(?:\s?(?:ext|extension|x)\.?\s?\d+)?',
        re.IGNORECASE
    )

    # Credit card patterns
    CREDIT_CARD_PATTERN = re.compile(
        r'\b(?:4[0-9]{12}(?:[0-9]{3})?|5[1-5][0-9]{14}|3[47][0-9]{13}|3[0-9]{13}|6(?:011|5[0-9]{2})[0-9]{12})\b'
    )

    # Password patterns in various contexts
    PASSWORD_PATTERNS = [
        re.compile(r'password["\']?\s*[:=]\s*["\']?([^"\'\s,}]+)["\']?', re.IGNORECASE),
        re.compile(r'passwd["\']?\s*[:=]\s*["\']?([^"\'\s,}]+)["\']?', re.IGNORECASE),
        re.compile(r'pwd["\']?\s*[:=]\s*["\']?([^"\'\s,}]+)["\']?', re.IGNORECASE),
    ]

    # Token patterns
    TOKEN_PATTERNS = [
        re.compile(r'token["\']?\s*[:=]\s*["\']?([A-Za-z0-9+/=]{20,})["\']?', re.IGNORECASE),
        re.compile(r'bearer\s+([A-Za-z0-9+/=]{20,})', re.IGNORECASE),
        re.compile(r'api[_-]?key["\']?\s*[:=]\s*["\']?([A-Za-z0-9+/=]{20,})["\']?', re.IGNORECASE),
    ]

    # Secret key patterns
    SECRET_PATTERNS = [
        re.compile(r'secret[_-]?key["\']?\s*[:=]\s*["\']?([A-Za-z0-9+/=]{20,})["\']?', re.IGNORECASE),
        re.compile(r'secret["\']?\s*[:=]\s*["\']?([A-Za-z0-9+/=]{20,})["\']?', re.IGNORECASE),
    ]

    # Sensitive field names (case insensitive)
    SENSITIVE_FIELDS = {
        'password', 'passwd', 'pwd', 'secret', 'token', 'key', 'api_key',
        'access_token', 'refresh_token', 'auth_token', 'session_key',
        'private_key', 'public_key', 'certificate', 'cert', 'credential',
        'email', 'email_address', 'mail', 'e_mail', 'mobno', 'mobile',
        'mobile_number', 'phone', 'phone_number', 'telephone', 'ssn',
        'social_security_number', 'credit_card', 'cc_number', 'card_number'
    }

    @staticmethod
    def sanitize_message(message: str, replacement: str = '[SANITIZED]') -> str:
        """
        Sanitize a log message by replacing sensitive data patterns.

        Args:
            message: Log message to sanitize
            replacement: String to replace sensitive data with

        Returns:
            str: Sanitized message
        """
        if not message or not isinstance(message, str):
            return message

        sanitized = message

        # Sanitize emails
        sanitized = LogSanitizationService.EMAIL_PATTERN.sub(
            lambda m: f"{m.group(0).split('@')[0][:2]}***@{replacement}", sanitized
        )

        # Sanitize phone numbers
        sanitized = LogSanitizationService.PHONE_PATTERN.sub(replacement, sanitized)

        # Sanitize credit cards
        sanitized = LogSanitizationService.CREDIT_CARD_PATTERN.sub(replacement, sanitized)

        # Sanitize passwords
        for pattern in LogSanitizationService.PASSWORD_PATTERNS:
            sanitized = pattern.sub(lambda m: m.group(0).replace(m.group(1), replacement), sanitized)

        # Sanitize tokens
        for pattern in LogSanitizationService.TOKEN_PATTERNS:
            sanitized = pattern.sub(lambda m: m.group(0).replace(m.group(1), replacement), sanitized)

        # Sanitize secrets
        for pattern in LogSanitizationService.SECRET_PATTERNS:
            sanitized = pattern.sub(lambda m: m.group(0).replace(m.group(1), replacement), sanitized)

        return sanitized

    @staticmethod
    def sanitize_extra_data(extra: Dict[str, Any], replacement: str = '[SANITIZED]') -> Dict[str, Any]:
        """
        Sanitize extra data dictionary for logging.

        Args:
            extra: Dictionary of extra data to sanitize
            replacement: String to replace sensitive values with

        Returns:
            dict: Sanitized extra data
        """
        if not extra or not isinstance(extra, dict):
            return extra

        sanitized = {}

        for key, value in extra.items():
            key_lower = str(key).lower()

            # Check if key is sensitive
            if any(sensitive in key_lower for sensitive in LogSanitizationService.SENSITIVE_FIELDS):
                sanitized[key] = replacement
            else:
                # Sanitize value content
                if isinstance(value, str):
                    sanitized[key] = LogSanitizationService.sanitize_message(value, replacement)
                elif isinstance(value, dict):
                    sanitized[key] = LogSanitizationService.sanitize_extra_data(value, replacement)
                elif isinstance(value, (list, tuple)):
                    sanitized[key] = LogSanitizationService._sanitize_collection(value, replacement)
                else:
                    # For other types, convert to string and sanitize
                    str_value = str(value)
                    sanitized[key] = LogSanitizationService.sanitize_message(str_value, replacement)

        return sanitized

    @staticmethod
    def _sanitize_collection(collection: Union[List, tuple], replacement: str) -> Union[List, tuple]:
        """Sanitize items in a list or tuple."""
        sanitized_items = []

        for item in collection:
            if isinstance(item, str):
                sanitized_items.append(LogSanitizationService.sanitize_message(item, replacement))
            elif isinstance(item, dict):
                sanitized_items.append(LogSanitizationService.sanitize_extra_data(item, replacement))
            else:
                sanitized_items.append(LogSanitizationService.sanitize_message(str(item), replacement))

        return type(collection)(sanitized_items)

    @staticmethod
    def create_safe_user_reference(user_id: Optional[int], peoplename: Optional[str] = None) -> str:
        """
        Create a safe user reference for logging without exposing sensitive data.

        Args:
            user_id: User ID
            peoplename: User's name (optional)

        Returns:
            str: Safe user reference
        """
        if user_id:
            if peoplename:
                # Only show first name and last initial
                name_parts = str(peoplename).split()
                if len(name_parts) > 1:
                    safe_name = f"{name_parts[0]} {name_parts[-1][0]}."
                else:
                    safe_name = f"{name_parts[0][:3]}***"
                return f"User_{user_id}({safe_name})"
            else:
                return f"User_{user_id}"
        return "Anonymous"


class LogSanitizationHandler(logging.Handler):
    """
    Custom logging handler that sanitizes log messages before output.

    This handler wraps existing handlers to provide automatic sanitization
    of sensitive data patterns in log messages and extra data.
    """

    def __init__(self, base_handler: logging.Handler):
        """
        Initialize with a base handler to wrap.

        Args:
            base_handler: The original handler to wrap
        """
        super().__init__()
        self.base_handler = base_handler
        self.setLevel(base_handler.level)
        self.setFormatter(base_handler.formatter)

    def emit(self, record: logging.LogRecord):
        """
        Sanitize and emit the log record.

        Args:
            record: LogRecord to sanitize and emit
        """
        try:
            # Sanitize the message
            if hasattr(record, 'msg') and record.msg:
                record.msg = LogSanitizationService.sanitize_message(str(record.msg))

            # Sanitize arguments
            if hasattr(record, 'args') and record.args:
                if isinstance(record.args, (tuple, list)):
                    sanitized_args = []
                    for arg in record.args:
                        if isinstance(arg, str):
                            sanitized_args.append(LogSanitizationService.sanitize_message(arg))
                        else:
                            sanitized_args.append(arg)
                    record.args = tuple(sanitized_args) if isinstance(record.args, tuple) else sanitized_args

            # Sanitize extra data
            extra_keys = [key for key in record.__dict__.keys()
                         if key not in logging.LogRecord.__dict__ and not key.startswith('_')]

            for key in extra_keys:
                value = getattr(record, key)
                if isinstance(value, dict):
                    sanitized_value = LogSanitizationService.sanitize_extra_data(value)
                    setattr(record, key, sanitized_value)
                elif isinstance(value, str):
                    sanitized_value = LogSanitizationService.sanitize_message(value)
                    setattr(record, key, sanitized_value)

            # Emit through base handler
            self.base_handler.emit(record)

        except (ValueError, TypeError, AttributeError) as e:
            error_record = logging.LogRecord(
                name=record.name,
                level=logging.ERROR,
                pathname=record.pathname,
                lineno=record.lineno,
                msg=f"Log sanitization data error: {type(e).__name__}",
                args=(),
                exc_info=None
            )
            self.base_handler.emit(error_record)
        except KeyError as e:
            error_record = logging.LogRecord(
                name=record.name,
                level=logging.ERROR,
                pathname=record.pathname,
                lineno=record.lineno,
                msg=f"Log record missing expected field: {type(e).__name__}",
                args=(),
                exc_info=None
            )
            self.base_handler.emit(error_record)


class LogSanitizationMiddleware(MiddlewareMixin):
    """
    Middleware to provide request-scoped logging sanitization.

    This middleware ensures that any logging done during request processing
    uses sanitized user references and correlation IDs instead of sensitive data.
    """

    def __init__(self, get_response=None):
        """Initialize middleware with get_response callable."""
        self.get_response = get_response
        super().__init__(get_response)

    def process_request(self, request):
        """Add sanitized user context to request."""
        # Create safe user reference for logging
        if hasattr(request, 'user') and request.user.is_authenticated:
            request.safe_user_ref = LogSanitizationService.create_safe_user_reference(
                getattr(request.user, 'id', None),
                getattr(request.user, 'peoplename', None)
            )
        else:
            request.safe_user_ref = "Anonymous"

        # Add correlation ID if not present
        if not hasattr(request, 'correlation_id'):
            import uuid
            request.correlation_id = str(uuid.uuid4())

        return None

    def process_response(self, request, response):
        """Clean up request-scoped logging context."""
        # Add sanitized logging context to response headers for debugging (if debug mode)
        if getattr(settings, 'DEBUG', False):
            response['X-Safe-User-Ref'] = getattr(request, 'safe_user_ref', 'Anonymous')
            response['X-Correlation-ID'] = getattr(request, 'correlation_id', 'unknown')

        return response


def get_sanitized_logger(name: str) -> logging.Logger:
    """
    Get a logger instance that automatically sanitizes log messages.

    Args:
        name: Logger name

    Returns:
        logging.Logger: Logger with sanitization enabled
    """
    logger = logging.getLogger(f"sanitized.{name}")

    # Configure sanitization if not already done
    if not any(isinstance(handler, LogSanitizationHandler) for handler in logger.handlers):
        # Wrap existing handlers with sanitization
        original_handlers = logger.handlers.copy()
        logger.handlers.clear()

        for handler in original_handlers:
            sanitized_handler = LogSanitizationHandler(handler)
            logger.addHandler(sanitized_handler)

    return logger


def sanitized_log(logger: logging.Logger, level: int, message: str,
                 extra: Optional[Dict[str, Any]] = None, correlation_id: Optional[str] = None):
    """
    Log a message with automatic sanitization.

    Args:
        logger: Logger instance to use
        level: Log level (e.g., logging.INFO)
        message: Message to log
        extra: Extra data to include
        correlation_id: Optional correlation ID
    """
    # Sanitize message and extra data
    sanitized_message = LogSanitizationService.sanitize_message(message)
    sanitized_extra = LogSanitizationService.sanitize_extra_data(extra or {})

    # Add correlation ID to extra data
    if correlation_id:
        sanitized_extra['correlation_id'] = correlation_id

    logger.log(level, sanitized_message, extra=sanitized_extra)


# Convenience functions for common log levels
def sanitized_info(logger: logging.Logger, message: str,
                  extra: Optional[Dict[str, Any]] = None, correlation_id: Optional[str] = None):
    """Log info message with sanitization."""
    sanitized_log(logger, logging.INFO, message, extra, correlation_id)


def sanitized_warning(logger: logging.Logger, message: str,
                     extra: Optional[Dict[str, Any]] = None, correlation_id: Optional[str] = None):
    """Log warning message with sanitization."""
    sanitized_log(logger, logging.WARNING, message, extra, correlation_id)


def sanitized_error(logger: logging.Logger, message: str,
                   extra: Optional[Dict[str, Any]] = None, correlation_id: Optional[str] = None):
    """Log error message with sanitization."""
    sanitized_log(logger, logging.ERROR, message, extra, correlation_id)


class SanitizingFilter(logging.Filter):
    """
    Django logging filter that automatically sanitizes all log records.

    This filter integrates with Django's LOGGING configuration to provide
    framework-level sanitization of all log messages, ensuring sensitive
    data is never written to log files.

    Usage in Django settings:
        LOGGING = {
            'filters': {
                'sanitize': {
                    '()': 'apps.core.middleware.logging_sanitization.SanitizingFilter',
                }
            },
            'handlers': {
                'file': {
                    'filters': ['sanitize'],
                    ...
                }
            }
        }
    """

    def filter(self, record: logging.LogRecord) -> bool:
        """
        Filter and sanitize the log record before output.

        Args:
            record: LogRecord to filter and sanitize

        Returns:
            bool: Always True (we sanitize but don't filter out records)
        """
        try:
            if hasattr(record, 'msg') and record.msg:
                record.msg = LogSanitizationService.sanitize_message(str(record.msg))

            if hasattr(record, 'args') and record.args:
                if isinstance(record.args, (tuple, list)):
                    sanitized_args = []
                    for arg in record.args:
                        if isinstance(arg, str):
                            sanitized_args.append(LogSanitizationService.sanitize_message(arg))
                        elif isinstance(arg, dict):
                            sanitized_args.append(LogSanitizationService.sanitize_extra_data(arg))
                        else:
                            sanitized_args.append(arg)
                    record.args = tuple(sanitized_args) if isinstance(record.args, tuple) else sanitized_args

            extra_keys = [key for key in record.__dict__.keys()
                         if key not in logging.LogRecord.__dict__ and not key.startswith('_')]

            for key in extra_keys:
                value = getattr(record, key)
                if isinstance(value, dict):
                    sanitized_value = LogSanitizationService.sanitize_extra_data(value)
                    setattr(record, key, sanitized_value)
                elif isinstance(value, str):
                    sanitized_value = LogSanitizationService.sanitize_message(value)
                    setattr(record, key, sanitized_value)

            return True

        except (ValueError, TypeError, AttributeError):
            return True