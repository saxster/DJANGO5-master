"""
Observability Infrastructure

Centralized tracing, metrics, and structured logging.
Follows .claude/rules.md Rule #16 (explicit __all__).
"""

from .tracing import TracingService, trace_function, get_current_span
from .structured_logging import StructuredLogger, get_logger

# Import new modules (Sentry & OTel enhancements)
try:
    from .sentry_integration import SentryIntegration, configure_sentry
except ImportError:
    SentryIntegration = None
    configure_sentry = None

try:
    from .otel_exporters import OTelExporterConfig, configure_otel_exporters
except ImportError:
    OTelExporterConfig = None
    configure_otel_exporters = None

try:
    from .performance_spans import (
        PerformanceSpanInstrumentor,
        trace_graphql_operation,
        trace_celery_task,
        trace_external_api_call,
        trace_database_query,
    )
except ImportError:
    PerformanceSpanInstrumentor = None
    trace_graphql_operation = None
    trace_celery_task = None
    trace_external_api_call = None
    trace_database_query = None

# Try to import metrics collector (may not exist yet)
try:
    from .metrics import MetricsCollector
except ImportError:
    MetricsCollector = None

__all__ = [
    # Tracing
    'TracingService',
    'trace_function',
    'get_current_span',

    # Logging
    'StructuredLogger',
    'get_logger',

    # Sentry (new)
    'SentryIntegration',
    'configure_sentry',

    # OpenTelemetry (new)
    'OTelExporterConfig',
    'configure_otel_exporters',

    # Performance Spans (new)
    'PerformanceSpanInstrumentor',
    'trace_graphql_operation',
    'trace_celery_task',
    'trace_external_api_call',
    'trace_database_query',

    # Metrics
    'MetricsCollector',
]
