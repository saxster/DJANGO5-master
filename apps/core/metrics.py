"""
Custom Prometheus Metrics for REST API and Mobile Sync

Following .claude/rules.md:
- Rule #7: Service <150 lines
- Rule #11: Specific exception handling

Created: October 29, 2025 (REST migration finalization)
"""

from prometheus_client import Counter, Histogram, Gauge

# Sync operation metrics
sync_operations_total = Counter(
    'django_sync_operations_total',
    'Total sync operations',
    ['operation_type', 'sync_type', 'status']
)

sync_operations_success = Counter(
    'django_sync_operations_success_total',
    'Successful sync operations',
    ['operation_type', 'sync_type']
)

sync_latency = Histogram(
    'django_sync_latency_seconds',
    'Sync operation latency in seconds',
    ['sync_type'],
    buckets=(0.01, 0.05, 0.1, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0)
)

sync_conflicts = Counter(
    'django_sync_conflicts_total',
    'Total sync conflicts detected',
    ['entity_type']
)

sync_errors = Counter(
    'django_sync_errors_total',
    'Total sync errors',
    ['endpoint', 'error_type']
)

sync_payload_bytes = Histogram(
    'django_sync_payload_bytes',
    'Sync payload size in bytes',
    ['operation', 'sync_type'],
    buckets=(1024, 10240, 102400, 1048576, 10485760)
)

# Idempotency metrics
idempotency_cache_hits = Counter(
    'django_idempotency_cache_hits_total',
    'Idempotency cache hits',
    ['endpoint']
)

idempotency_cache_misses = Counter(
    'django_idempotency_cache_misses_total',
    'Idempotency cache misses',
    ['endpoint']
)

# WebSocket metrics
websocket_connections_active = Gauge(
    'django_websocket_connections_active',
    'Active WebSocket connections'
)

websocket_connections_opened = Counter(
    'django_websocket_connections_opened_total',
    'Total WebSocket connections opened'
)

websocket_connections_closed = Counter(
    'django_websocket_connections_closed_total',
    'Total WebSocket connections closed',
    ['reason']
)

websocket_message_queue_depth = Gauge(
    'django_websocket_message_queue_depth',
    'WebSocket message queue depth'
)

# Mobile app metrics
mobile_app_version_connections = Gauge(
    'django_mobile_app_version_active_connections',
    'Active connections by mobile app version',
    ['app_version', 'platform']
)

# Security metrics
rate_limit_violations = Counter(
    'django_rate_limit_violations_total',
    'Rate limit violations',
    ['endpoint', 'violation_type']
)

csrf_violations = Counter(
    'django_csrf_violations_total',
    'CSRF violations',
    ['endpoint']
)

permission_denied = Counter(
    'django_permission_denied_total',
    'Permission denied events',
    ['endpoint', 'resource']
)

sql_injection_attempts = Counter(
    'django_sql_injection_attempts_blocked_total',
    'SQL injection attempts blocked'
)

xss_attempts = Counter(
    'django_xss_attempts_blocked_total',
    'XSS attempts blocked'
)

file_upload_violations = Counter(
    'django_file_upload_violations_total',
    'File upload security violations',
    ['violation_type']
)


__all__ = [
    'sync_operations_total',
    'sync_operations_success',
    'sync_latency',
    'sync_conflicts',
    'sync_errors',
    'sync_payload_bytes',
    'idempotency_cache_hits',
    'idempotency_cache_misses',
    'websocket_connections_active',
    'websocket_connections_opened',
    'websocket_connections_closed',
    'websocket_message_queue_depth',
    'mobile_app_version_connections',
    'rate_limit_violations',
    'csrf_violations',
    'permission_denied',
    'sql_injection_attempts',
    'xss_attempts',
    'file_upload_violations',
]
