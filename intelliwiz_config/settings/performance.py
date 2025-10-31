"""
Performance Budget Configuration

Per-endpoint SLA definitions and enforcement settings.
"""

from datetime import timedelta

# Performance budgets (milliseconds)
ENDPOINT_PERFORMANCE_BUDGETS = {
    # REST API endpoints
    '/api/v1/sync/': {
        'p50': 100,
        'p95': 200,
        'p99': 500,
        'timeout': 3000,
    },

    # Operations endpoints
    '/operations/tasks/': {
        'p50': 150,
        'p95': 300,
        'p99': 800,
        'timeout': 2000,
    },

    '/operations/reports/': {
        'p50': 500,
        'p95': 2000,
        'p99': 5000,
        'timeout': 30000,
    },

    # Default budget for unspecified endpoints
    'default': {
        'p50': 300,
        'p95': 1000,
        'p99': 3000,
        'timeout': 5000,
    }
}

# Alerting thresholds
PERFORMANCE_ALERT_THRESHOLDS = {
    'p95_violation_count': 10,  # Alert after 10 violations in window
    'p99_violation_count': 5,
    'alert_window': timedelta(minutes=5),
}

# Cache stampede prevention
CACHE_STAMPEDE_PREVENTION = {
    'enabled': True,
    'beta_factor': 1.0,  # Probabilistic early expiration factor
    'lock_timeout': 30,  # Seconds
}
