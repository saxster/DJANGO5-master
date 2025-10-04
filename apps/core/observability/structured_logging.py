"""
Structured JSON Logging

Production-grade structured logging with trace context.
Follows .claude/rules.md Rule #7 (< 150 lines).
"""

import logging
import json
from datetime import datetime, timezone as dt_timezone
from typing import Dict, Any, Optional

from pythonjsonlogger import jsonlogger
from opentelemetry import trace


class StructuredLogger:
    """
    Structured logger with automatic trace context injection.

    Benefits:
    - Machine-parseable logs
    - Automatic correlation with traces
    - Consistent log format
    - Easy integration with log aggregators (ELK, CloudWatch)
    """

    def __init__(self, name: str):
        self.logger = logging.getLogger(name)

    def _add_trace_context(self, extra: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """Add OpenTelemetry trace context to log entry."""
        if extra is None:
            extra = {}

        # Get current span context
        span = trace.get_current_span()

        if span.get_span_context().is_valid:
            span_context = span.get_span_context()
            extra['trace_id'] = format(span_context.trace_id, '032x')
            extra['span_id'] = format(span_context.span_id, '016x')
            extra['trace_flags'] = span_context.trace_flags

        return extra

    def info(self, message: str, extra: Optional[Dict[str, Any]] = None):
        """Log info message with trace context."""
        extra = self._add_trace_context(extra)
        self.logger.info(message, extra=extra)

    def warning(self, message: str, extra: Optional[Dict[str, Any]] = None):
        """Log warning message with trace context."""
        extra = self._add_trace_context(extra)
        self.logger.warning(message, extra=extra)

    def error(
        self,
        message: str,
        extra: Optional[Dict[str, Any]] = None,
        exc_info: bool = False
    ):
        """Log error message with trace context."""
        extra = self._add_trace_context(extra)
        self.logger.error(message, extra=extra, exc_info=exc_info)

    def debug(self, message: str, extra: Optional[Dict[str, Any]] = None):
        """Log debug message with trace context."""
        extra = self._add_trace_context(extra)
        self.logger.debug(message, extra=extra)


class CustomJsonFormatter(jsonlogger.JsonFormatter):
    """
    Custom JSON formatter with additional fields.

    Adds:
    - ISO 8601 timestamps
    - Environment information
    - Service metadata
    """

    def add_fields(self, log_record, record, message_dict):
        """Add custom fields to log record."""
        super().add_fields(log_record, record, message_dict)

        # Add timestamp in ISO 8601 format
        log_record['timestamp'] = datetime.now(dt_timezone.utc).isoformat()

        # Add level name
        log_record['level'] = record.levelname

        # Add logger name
        log_record['logger'] = record.name

        # Add service metadata
        from django.conf import settings
        log_record['service'] = getattr(settings, 'SERVICE_NAME', 'intelliwiz')
        log_record['environment'] = getattr(settings, 'ENVIRONMENT', 'development')


def get_logger(name: str) -> StructuredLogger:
    """
    Get structured logger instance.

    Args:
        name: Logger name (usually __name__)

    Returns:
        StructuredLogger instance

    Usage:
        logger = get_logger(__name__)
        logger.info('User logged in', extra={'user_id': user.id})
    """
    return StructuredLogger(name)


def configure_structured_logging():
    """
    Configure Django to use structured JSON logging.

    Call this in Django settings or AppConfig.ready()
    """
    import logging.config

    LOGGING = {
        'version': 1,
        'disable_existing_loggers': False,
        'formatters': {
            'json': {
                '()': 'apps.core.observability.structured_logging.CustomJsonFormatter',
                'format': '%(timestamp)s %(level)s %(name)s %(message)s'
            }
        },
        'handlers': {
            'console': {
                'class': 'logging.StreamHandler',
                'formatter': 'json',
            },
            'file': {
                'class': 'logging.handlers.RotatingFileHandler',
                'filename': 'logs/application.json.log',
                'maxBytes': 10485760,  # 10MB
                'backupCount': 5,
                'formatter': 'json',
            }
        },
        'root': {
            'handlers': ['console', 'file'],
            'level': 'INFO',
        }
    }

    logging.config.dictConfig(LOGGING)
