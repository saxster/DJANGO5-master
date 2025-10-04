"""
Distributed Tracing Service

OpenTelemetry-based distributed tracing for requests, Celery tasks, GraphQL.
Follows .claude/rules.md Rule #7 (< 150 lines), Rule #11 (specific exceptions).
"""

import logging
from functools import wraps
from typing import Optional, Dict, Any, Callable
from contextlib import contextmanager

from django.conf import settings

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.jaeger.thrift import JaegerExporter
from opentelemetry.sdk.resources import SERVICE_NAME, Resource

logger = logging.getLogger(__name__)


class TracingService:
    """
    Centralized tracing service for distributed tracing.

    Initializes OpenTelemetry and provides tracing utilities.
    """

    _initialized = False
    _tracer = None

    @classmethod
    def initialize(cls):
        """Initialize OpenTelemetry tracing."""
        if cls._initialized:
            return

        try:
            # Create resource with service name
            resource = Resource(attributes={
                SERVICE_NAME: getattr(settings, 'SERVICE_NAME', 'intelliwiz')
            })

            # Create tracer provider
            provider = TracerProvider(resource=resource)

            # Configure Jaeger exporter
            jaeger_host = getattr(settings, 'JAEGER_HOST', 'localhost')
            jaeger_port = getattr(settings, 'JAEGER_PORT', 6831)

            jaeger_exporter = JaegerExporter(
                agent_host_name=jaeger_host,
                agent_port=jaeger_port,
            )

            # Add span processor
            provider.add_span_processor(
                BatchSpanProcessor(jaeger_exporter)
            )

            # Set global tracer provider
            trace.set_tracer_provider(provider)

            # Get tracer
            cls._tracer = trace.get_tracer(__name__)

            cls._initialized = True

            logger.info(
                f"Tracing initialized: Jaeger at {jaeger_host}:{jaeger_port}"
            )

        except Exception as e:
            logger.error(f"Failed to initialize tracing: {e}", exc_info=True)

    @classmethod
    def get_tracer(cls):
        """Get the global tracer instance."""
        if not cls._initialized:
            cls.initialize()

        return cls._tracer

    @classmethod
    @contextmanager
    def create_span(
        cls,
        name: str,
        attributes: Optional[Dict[str, Any]] = None
    ):
        """
        Create a new span with context manager.

        Args:
            name: Span name
            attributes: Span attributes

        Usage:
            with TracingService.create_span('database_query'):
                # Your code here
        """
        tracer = cls.get_tracer()

        with tracer.start_as_current_span(name) as span:
            if attributes:
                for key, value in attributes.items():
                    span.set_attribute(key, str(value))

            yield span


def trace_function(span_name: Optional[str] = None):
    """
    Decorator to trace function execution.

    Args:
        span_name: Custom span name (defaults to function name)

    Usage:
        @trace_function('user_login')
        def login_user(username):
            ...
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            name = span_name or func.__name__

            with TracingService.create_span(
                name,
                attributes={'function': func.__name__}
            ):
                return func(*args, **kwargs)

        return wrapper
    return decorator


def get_current_span():
    """Get the current active span."""
    return trace.get_current_span()


def add_span_attribute(key: str, value: Any):
    """Add attribute to current span."""
    span = get_current_span()
    if span:
        span.set_attribute(key, str(value))


def add_span_event(name: str, attributes: Optional[Dict[str, Any]] = None):
    """Add event to current span."""
    span = get_current_span()
    if span:
        span.add_event(name, attributes=attributes or {})
