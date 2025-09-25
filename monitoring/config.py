"""
Monitoring configuration and alert rules.
"""

from typing import Dict, List, Any
import os
from dataclasses import dataclass


@dataclass
class AlertRule:
    """Alert rule configuration"""
    name: str
    metric: str
    condition: str  # 'gt', 'lt', 'eq'
    threshold: float
    window_minutes: int
    severity: str  # 'info', 'warning', 'critical'
    description: str
    action: str


class MonitoringConfig:
    """Monitoring configuration"""
    
    # Alert rules
    ALERT_RULES = [
        AlertRule(
            name='high_response_time',
            metric='response_time_p95',
            condition='gt',
            threshold=1.0,
            window_minutes=5,
            severity='warning',
            description='95th percentile response time exceeds 1 second',
            action='Check slow endpoints and database queries'
        ),
        AlertRule(
            name='very_high_response_time',
            metric='response_time_p99',
            condition='gt',
            threshold=2.0,
            window_minutes=5,
            severity='critical',
            description='99th percentile response time exceeds 2 seconds',
            action='Immediate investigation required - possible service degradation'
        ),
        AlertRule(
            name='high_error_rate',
            metric='error_rate',
            condition='gt',
            threshold=0.05,
            window_minutes=5,
            severity='critical',
            description='Error rate exceeds 5%',
            action='Check application logs for exceptions'
        ),
        AlertRule(
            name='low_cache_hit_rate',
            metric='cache_hit_rate',
            condition='lt',
            threshold=0.5,
            window_minutes=15,
            severity='warning',
            description='Cache hit rate below 50%',
            action='Review cache keys and TTL configuration'
        ),
        AlertRule(
            name='high_query_count',
            metric='queries_per_request_p95',
            condition='gt',
            threshold=50,
            window_minutes=5,
            severity='warning',
            description='95th percentile queries per request exceeds 50',
            action='Check for N+1 queries and missing select_related/prefetch_related'
        ),
        AlertRule(
            name='slow_database_queries',
            metric='query_time_p95',
            condition='gt',
            threshold=0.1,
            window_minutes=5,
            severity='warning',
            description='95th percentile query time exceeds 100ms',
            action='Review slow queries and database indexes'
        ),
        AlertRule(
            name='database_connection_pool_exhausted',
            metric='db_connection_errors',
            condition='gt',
            threshold=10,
            window_minutes=1,
            severity='critical',
            description='Database connection errors detected',
            action='Check database connection pool settings and database health'
        )
    ]
    
    # Metric collection settings
    METRICS_RETENTION_HOURS = int(os.environ.get('METRICS_RETENTION_HOURS', '24'))
    METRICS_COLLECTION_INTERVAL = int(os.environ.get('METRICS_COLLECTION_INTERVAL', '60'))
    
    # Dashboard refresh intervals (seconds)
    DASHBOARD_REFRESH_INTERVALS = {
        'real_time': 5,
        'standard': 30,
        'historical': 300
    }
    
    # Notification channels
    NOTIFICATION_CHANNELS = {
        'email': {
            'enabled': os.environ.get('ALERT_EMAIL_ENABLED', 'false').lower() == 'true',
            'recipients': os.environ.get('ALERT_EMAIL_RECIPIENTS', '').split(','),
            'smtp_host': os.environ.get('SMTP_HOST', 'localhost'),
            'smtp_port': int(os.environ.get('SMTP_PORT', '25')),
            'from_address': os.environ.get('ALERT_FROM_EMAIL', 'monitoring@example.com')
        },
        'slack': {
            'enabled': os.environ.get('ALERT_SLACK_ENABLED', 'false').lower() == 'true',
            'webhook_url': os.environ.get('SLACK_WEBHOOK_URL', ''),
            'channel': os.environ.get('SLACK_CHANNEL', '#alerts'),
            'username': 'Django Monitoring'
        },
        'pagerduty': {
            'enabled': os.environ.get('ALERT_PAGERDUTY_ENABLED', 'false').lower() == 'true',
            'integration_key': os.environ.get('PAGERDUTY_INTEGRATION_KEY', ''),
            'severity_mapping': {
                'info': 'info',
                'warning': 'warning',
                'critical': 'error'
            }
        }
    }
    
    # Performance thresholds
    PERFORMANCE_THRESHOLDS = {
        'response_time': {
            'excellent': 0.1,    # < 100ms
            'good': 0.5,         # < 500ms
            'acceptable': 1.0,   # < 1s
            'poor': 2.0          # < 2s
        },
        'query_time': {
            'excellent': 0.01,   # < 10ms
            'good': 0.05,        # < 50ms
            'acceptable': 0.1,   # < 100ms
            'poor': 0.5          # < 500ms
        },
        'cache_hit_rate': {
            'excellent': 0.9,    # > 90%
            'good': 0.7,         # > 70%
            'acceptable': 0.5,   # > 50%
            'poor': 0.3          # > 30%
        }
    }
    
    # Monitoring endpoints to exclude
    EXCLUDED_PATHS = [
        '/monitoring/',
        '/health/',
        '/metrics/',
        '/static/',
        '/media/',
        '/admin/jsi18n/'
    ]
    
    @classmethod
    def should_monitor_path(cls, path: str) -> bool:
        """Check if a path should be monitored"""
        for excluded in cls.EXCLUDED_PATHS:
            if path.startswith(excluded):
                return False
        return True
    
    @classmethod
    def get_performance_rating(cls, metric: str, value: float) -> str:
        """Get performance rating for a metric value"""
        thresholds = cls.PERFORMANCE_THRESHOLDS.get(metric, {})
        
        if metric == 'cache_hit_rate':
            # Higher is better for cache hit rate
            if value >= thresholds.get('excellent', 1.0):
                return 'excellent'
            elif value >= thresholds.get('good', 0.7):
                return 'good'
            elif value >= thresholds.get('acceptable', 0.5):
                return 'acceptable'
            else:
                return 'poor'
        else:
            # Lower is better for time-based metrics
            if value <= thresholds.get('excellent', 0):
                return 'excellent'
            elif value <= thresholds.get('good', float('inf')):
                return 'good'
            elif value <= thresholds.get('acceptable', float('inf')):
                return 'acceptable'
            else:
                return 'poor'


# Export singleton instance
monitoring_config = MonitoringConfig()