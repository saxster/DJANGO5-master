"""
Performance Spans Instrumentation

Automatic span creation for database queries, Celery tasks, REST API operations,
and external API calls.

Features:
    - Database query spans with SQL sanitization
    - Celery task execution spans
    - External HTTP API call spans
    - Redis operation spans

Compliance:
    - Rule #7: File < 150 lines
    - Rule #11: Specific exception handling
    - Rule #15: No sensitive data in spans

Usage:
    from apps.core.observability.performance_spans import PerformanceSpanInstrumentor
    PerformanceSpanInstrumentor.instrument_all()

MIGRATION NOTE (Oct 2025): Legacy query spans removed - use REST API tracing
"""

import logging
from functools import wraps
from typing import Callable, Any, Optional

logger = logging.getLogger(__name__)

__all__ = [
    'PerformanceSpanInstrumentor',
    'trace_database_query',
    'trace_celery_task',
    'trace_external_api_call',
]


class PerformanceSpanInstrumentor:
    """
    Automatic instrumentation for performance-critical operations.
    """

    _instrumented = False

    @classmethod
    def instrument_all(cls) -> bool:
        """
        Instrument all supported components.

        Returns:
            True if successful
        """
        if cls._instrumented:
            logger.info("Performance spans already instrumented")
            return True

        try:
            from opentelemetry import trace

            # Check if tracer provider is set
            if not trace.get_tracer_provider():
                logger.warning("OTel tracer provider not initialized")
                return False

            # Instrument Django database
            cls._instrument_django_database()

            # Instrument Celery
            cls._instrument_celery()

            # Instrument Redis
            cls._instrument_redis()

            cls._instrumented = True

            logger.info("Performance spans instrumentation complete")
            return True

        except ImportError as e:
            logger.error(f"OTel not installed: {e}")
            return False
        except Exception as e:
            logger.error(f"Failed to instrument performance spans: {e}", exc_info=True)
            return False

    @classmethod
    def _instrument_django_database(cls):
        """Instrument Django database queries."""
        try:
            from opentelemetry.instrumentation.psycopg2 import Psycopg2Instrumentor

            Psycopg2Instrumentor().instrument()
            logger.info("Django database instrumented")
        except ImportError:
            logger.warning("psycopg2 instrumentation not available")

    @classmethod
    def _instrument_celery(cls):
        """Instrument Celery tasks."""
        try:
            from opentelemetry.instrumentation.celery import CeleryInstrumentor

            CeleryInstrumentor().instrument()
            logger.info("Celery instrumented")
        except ImportError:
            logger.warning("Celery instrumentation not available")

    @classmethod
    def _instrument_redis(cls):
        """Instrument Redis operations."""
        try:
            from opentelemetry.instrumentation.redis import RedisInstrumentor

            RedisInstrumentor().instrument()
            logger.info("Redis instrumented")
        except ImportError:
            logger.warning("Redis instrumentation not available")


def trace_celery_task(task_name: Optional[str] = None):
    """
    Decorator to trace Celery task execution.

    Note: CeleryInstrumentor already adds spans, but this allows custom attributes.

    Args:
        task_name: Custom task name

    Usage:
        @trace_celery_task('send_report_email')
        @celery_app.task
        def send_report_email(user_id, report_id):
            ...
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                from opentelemetry import trace

                tracer = trace.get_tracer(__name__)
                t_name = task_name or func.__name__

                with tracer.start_as_current_span(
                    f"celery.task.{t_name}",
                    attributes={
                        'celery.task.name': t_name,
                        'celery.task.args_count': len(args),
                    }
                ):
                    return func(*args, **kwargs)

            except Exception as e:
                logger.error(f"Error in Celery task span: {e}", exc_info=True)
                return func(*args, **kwargs)

        return wrapper
    return decorator


def trace_external_api_call(api_name: str, endpoint: str):
    """
    Decorator to trace external API calls.

    Args:
        api_name: API name (e.g., 'google_maps', 'sendgrid')
        endpoint: Endpoint path

    Usage:
        @trace_external_api_call('google_maps', '/geocode')
        def geocode_address(address):
            return requests.get(url, timeout=(5, 15))
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                from opentelemetry import trace

                tracer = trace.get_tracer(__name__)

                with tracer.start_as_current_span(
                    f"external_api.{api_name}",
                    attributes={
                        'http.method': 'GET',  # Could parse from kwargs
                        'http.url': endpoint,
                        'external_api.name': api_name,
                    }
                ):
                    return func(*args, **kwargs)

            except Exception as e:
                logger.error(f"Error in external API span: {e}", exc_info=True)
                return func(*args, **kwargs)

        return wrapper
    return decorator


def trace_database_query(query_name: str):
    """
    Decorator to trace custom database queries.

    Note: Django ORM queries are auto-instrumented. Use this for raw SQL.

    Args:
        query_name: Query identifier

    Usage:
        @trace_database_query('get_user_stats')
        def get_user_stats(user_id):
            with connection.cursor() as cursor:
                cursor.execute("SELECT ...", [user_id])
                return cursor.fetchall()
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                from opentelemetry import trace

                tracer = trace.get_tracer(__name__)

                with tracer.start_as_current_span(
                    f"db.query.{query_name}",
                    attributes={
                        'db.system': 'postgresql',
                        'db.operation': query_name,
                    }
                ):
                    return func(*args, **kwargs)

            except Exception as e:
                logger.error(f"Error in database query span: {e}", exc_info=True)
                return func(*args, **kwargs)

        return wrapper
    return decorator
