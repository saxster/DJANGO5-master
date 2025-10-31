"""
Observability Settings

Centralized configuration for Sentry, OpenTelemetry, and monitoring.

Environment Variables:
    SENTRY_DSN: Sentry project DSN
    SENTRY_TRACES_SAMPLE_RATE: Performance traces sample rate (0.0-1.0)
    OTEL_EXPORTER_OTLP_ENDPOINT: OpenTelemetry collector endpoint
    JAEGER_HOST: Jaeger agent host (fallback)
    JAEGER_PORT: Jaeger agent port (fallback)

Compliance:
    - Rule #6: File < 200 lines
"""

import os
from typing import Dict, Any

# Service metadata
SERVICE_NAME = os.getenv('SERVICE_NAME', 'intelliwiz')
ENVIRONMENT = os.getenv('ENVIRONMENT', 'development')

# ============================================================================
# SENTRY CONFIGURATION
# ============================================================================

SENTRY_ENABLED = os.getenv('SENTRY_ENABLED', 'false').lower() == 'true'
SENTRY_DSN = os.getenv('SENTRY_DSN', '')

# Sample rates by environment (can be overridden via env vars)
SENTRY_TRACES_SAMPLE_RATE = float(os.getenv('SENTRY_TRACES_SAMPLE_RATE', {
    'production': '0.1',
    'staging': '0.5',
    'development': '1.0',
}.get(ENVIRONMENT, '0.1')))

SENTRY_PROFILES_SAMPLE_RATE = float(os.getenv('SENTRY_PROFILES_SAMPLE_RATE', {
    'production': '0.01',
    'staging': '0.05',
    'development': '0.1',
}.get(ENVIRONMENT, '0.01')))

# Send PII to Sentry (ONLY in development, NEVER in production)
SENTRY_SEND_DEFAULT_PII = (ENVIRONMENT == 'development')

# Attach stack local variables
SENTRY_ATTACH_STACKTRACE = True

# Max breadcrumbs to capture
SENTRY_MAX_BREADCRUMBS = 50

# Ignore common errors
SENTRY_IGNORE_ERRORS = [
    'KeyboardInterrupt',
    'django.http.response.Http404',
    'django.core.exceptions.PermissionDenied',
]

# ============================================================================
# OPENTELEMETRY CONFIGURATION
# ============================================================================

OTEL_ENABLED = os.getenv('OTEL_ENABLED', 'true').lower() == 'true'

# OTLP exporter endpoint (e.g., Jaeger, Tempo, Honeycomb)
OTEL_EXPORTER_OTLP_ENDPOINT = os.getenv('OTEL_EXPORTER_OTLP_ENDPOINT', '')

# Jaeger fallback (development)
JAEGER_HOST = os.getenv('JAEGER_HOST', 'localhost')
JAEGER_PORT = int(os.getenv('JAEGER_PORT', 6831))

# Trace sampling rate
OTEL_TRACES_SAMPLE_RATE = float(os.getenv('OTEL_TRACES_SAMPLE_RATE', {
    'production': '0.1',
    'staging': '0.5',
    'development': '1.0',
}.get(ENVIRONMENT, '0.1')))

# ============================================================================
# MONITORING CONFIGURATION
# ============================================================================

# Enable Prometheus metrics export
PROMETHEUS_METRICS_ENABLED = os.getenv('PROMETHEUS_METRICS_ENABLED', 'true').lower() == 'true'

# Metrics export endpoint
PROMETHEUS_METRICS_PATH = '/metrics'

# Enable custom monitoring dashboards
MONITORING_DASHBOARDS_ENABLED = os.getenv('MONITORING_DASHBOARDS_ENABLED', 'true').lower() == 'true'

# ============================================================================
# WEBSOCKET MONITORING
# ============================================================================

# Heartbeat interval (seconds)
WEBSOCKET_HEARTBEAT_INTERVAL = int(os.getenv('WEBSOCKET_HEARTBEAT_INTERVAL', 30))

# Connection timeout (seconds)
WEBSOCKET_PRESENCE_TIMEOUT = int(os.getenv('WEBSOCKET_PRESENCE_TIMEOUT', 300))

# Enable backpressure detection
WEBSOCKET_BACKPRESSURE_ENABLED = os.getenv('WEBSOCKET_BACKPRESSURE_ENABLED', 'true').lower() == 'true'

# Slow consumer threshold (milliseconds)
WEBSOCKET_SLOW_CONSUMER_THRESHOLD_MS = int(os.getenv('WEBSOCKET_SLOW_CONSUMER_THRESHOLD_MS', 500))

# ============================================================================
# CACHE MONITORING
# ============================================================================

# Enable per-tenant cache metrics
TENANT_CACHE_METRICS_ENABLED = os.getenv('TENANT_CACHE_METRICS_ENABLED', 'true').lower() == 'true'

# Cache leak detection enabled
CACHE_LEAK_DETECTION_ENABLED = os.getenv('CACHE_LEAK_DETECTION_ENABLED', 'true').lower() == 'true'

# Scan interval for cache leaks (seconds)
CACHE_LEAK_SCAN_INTERVAL = int(os.getenv('CACHE_LEAK_SCAN_INTERVAL', 3600))  # 1 hour

# ============================================================================
# UNIFIED OBSERVABILITY DASHBOARD
# ============================================================================

# Enable unified dashboard
UNIFIED_OBSERVABILITY_DASHBOARD_ENABLED = os.getenv('UNIFIED_OBSERVABILITY_DASHBOARD_ENABLED', 'true').lower() == 'true'

# Dashboard refresh interval (seconds)
OBSERVABILITY_DASHBOARD_REFRESH_INTERVAL = int(os.getenv('OBSERVABILITY_DASHBOARD_REFRESH_INTERVAL', 30))

# ============================================================================
# ANOMALY DETECTION
# ============================================================================

# Enable ML-based anomaly detection
ANOMALY_DETECTION_ENABLED = os.getenv('ANOMALY_DETECTION_ENABLED', 'false').lower() == 'true'

# Anomaly detection sensitivity (0.0-1.0, higher = more sensitive)
ANOMALY_DETECTION_SENSITIVITY = float(os.getenv('ANOMALY_DETECTION_SENSITIVITY', '0.8'))

# ============================================================================
# EXPORT ALL SETTINGS
# ============================================================================

__all__ = [
    # Sentry
    'SENTRY_ENABLED',
    'SENTRY_DSN',
    'SENTRY_TRACES_SAMPLE_RATE',
    'SENTRY_PROFILES_SAMPLE_RATE',
    'SENTRY_SEND_DEFAULT_PII',
    'SENTRY_ATTACH_STACKTRACE',
    'SENTRY_MAX_BREADCRUMBS',
    'SENTRY_IGNORE_ERRORS',

    # OpenTelemetry
    'OTEL_ENABLED',
    'OTEL_EXPORTER_OTLP_ENDPOINT',
    'JAEGER_HOST',
    'JAEGER_PORT',
    'OTEL_TRACES_SAMPLE_RATE',

    # Monitoring
    'PROMETHEUS_METRICS_ENABLED',
    'PROMETHEUS_METRICS_PATH',
    'MONITORING_DASHBOARDS_ENABLED',

    # WebSocket
    'WEBSOCKET_HEARTBEAT_INTERVAL',
    'WEBSOCKET_PRESENCE_TIMEOUT',
    'WEBSOCKET_BACKPRESSURE_ENABLED',
    'WEBSOCKET_SLOW_CONSUMER_THRESHOLD_MS',

    # Cache
    'TENANT_CACHE_METRICS_ENABLED',
    'CACHE_LEAK_DETECTION_ENABLED',
    'CACHE_LEAK_SCAN_INTERVAL',

    # Dashboard
    'UNIFIED_OBSERVABILITY_DASHBOARD_ENABLED',
    'OBSERVABILITY_DASHBOARD_REFRESH_INTERVAL',

    # Anomaly Detection
    'ANOMALY_DETECTION_ENABLED',
    'ANOMALY_DETECTION_SENSITIVITY',

    # Service
    'SERVICE_NAME',
    'ENVIRONMENT',
]
