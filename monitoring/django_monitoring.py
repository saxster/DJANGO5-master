"""
Django monitoring middleware and utilities for production monitoring.
Tracks query performance, errors, and system health.
"""

import time
import json
import logging
import traceback
from datetime import datetime
from typing import Dict, Any, Optional, List
from collections import defaultdict
from threading import Lock

from django.conf import settings
from django.core.cache import cache
from django.db import connection
from django.http import HttpRequest, HttpResponse
from django.utils.deprecation import MiddlewareMixin
from django.core.signals import request_started, request_finished
from django.db.backends.signals import connection_created
from django.dispatch import receiver

logger = logging.getLogger('monitoring')


class MetricsCollector:
    """Collects and aggregates performance metrics"""
    
    def __init__(self):
        self.metrics = defaultdict(list)
        self.lock = Lock()
        self.start_time = time.time()
        
        # Thresholds for alerting
        self.THRESHOLDS = {
            'response_time': 1.0,      # 1 second
            'query_time': 0.1,         # 100ms
            'query_count': 50,         # queries per request
            'error_rate': 0.05,        # 5% error rate
            'cache_miss_rate': 0.5,    # 50% cache miss rate
        }
    
    def record_metric(self, metric_type: str, value: float, tags: Optional[Dict] = None):
        """Record a metric value"""
        with self.lock:
            metric_data = {
                'timestamp': datetime.now().isoformat(),
                'value': value,
                'tags': tags or {}
            }
            self.metrics[metric_type].append(metric_data)
            
            # Keep only last 1000 metrics per type
            if len(self.metrics[metric_type]) > 1000:
                self.metrics[metric_type] = self.metrics[metric_type][-1000:]
    
    def get_stats(self, metric_type: str, window_minutes: int = 5) -> Dict[str, float]:
        """Get statistics for a metric type"""
        with self.lock:
            metrics = self.metrics.get(metric_type, [])
            if not metrics:
                return {}
            
            # Filter by time window
            cutoff_time = time.time() - (window_minutes * 60)
            recent_metrics = [
                m for m in metrics 
                if datetime.fromisoformat(m['timestamp']).timestamp() > cutoff_time
            ]
            
            if not recent_metrics:
                return {}
            
            values = [m['value'] for m in recent_metrics]
            
            return {
                'count': len(values),
                'mean': sum(values) / len(values),
                'min': min(values),
                'max': max(values),
                'p50': sorted(values)[len(values) // 2],
                'p95': sorted(values)[int(len(values) * 0.95)] if len(values) > 20 else max(values),
                'p99': sorted(values)[int(len(values) * 0.99)] if len(values) > 100 else max(values),
            }
    
    def check_thresholds(self) -> List[Dict[str, Any]]:
        """Check if any metrics exceed thresholds"""
        alerts = []
        
        # Check response time
        response_stats = self.get_stats('response_time')
        if response_stats.get('p95', 0) > self.THRESHOLDS['response_time']:
            alerts.append({
                'level': 'WARNING',
                'metric': 'response_time',
                'message': f"95th percentile response time ({response_stats['p95']:.2f}s) exceeds threshold ({self.THRESHOLDS['response_time']}s)",
                'value': response_stats['p95']
            })
        
        # Check query time
        query_stats = self.get_stats('query_time')
        if query_stats.get('p95', 0) > self.THRESHOLDS['query_time']:
            alerts.append({
                'level': 'WARNING',
                'metric': 'query_time',
                'message': f"95th percentile query time ({query_stats['p95']:.3f}s) exceeds threshold ({self.THRESHOLDS['query_time']}s)",
                'value': query_stats['p95']
            })
        
        # Check error rate
        total_requests = self.get_stats('request')['count']
        total_errors = self.get_stats('error')['count']
        if total_requests > 100:  # Only check if we have enough data
            error_rate = total_errors / total_requests
            if error_rate > self.THRESHOLDS['error_rate']:
                alerts.append({
                    'level': 'CRITICAL',
                    'metric': 'error_rate',
                    'message': f"Error rate ({error_rate:.1%}) exceeds threshold ({self.THRESHOLDS['error_rate']:.1%})",
                    'value': error_rate
                })
        
        return alerts


# Global metrics collector
metrics_collector = MetricsCollector()


class QueryMonitoringMiddleware(MiddlewareMixin):
    """Middleware to monitor database queries"""
    
    def process_request(self, request: HttpRequest):
        """Start monitoring for this request"""
        request._monitoring_start_time = time.time()
        request._monitoring_query_count = len(connection.queries)
        
        # Record request start
        metrics_collector.record_metric('request', 1, {
            'method': request.method,
            'path': request.path
        })
    
    def process_response(self, request: HttpRequest, response: HttpResponse) -> HttpResponse:
        """End monitoring and record metrics"""
        if hasattr(request, '_monitoring_start_time'):
            # Calculate response time
            response_time = time.time() - request._monitoring_start_time
            metrics_collector.record_metric('response_time', response_time, {
                'method': request.method,
                'path': request.path,
                'status': response.status_code
            })
            
            # Calculate query metrics
            if hasattr(request, '_monitoring_query_count'):
                query_count = len(connection.queries) - request._monitoring_query_count
                metrics_collector.record_metric('query_count', query_count, {
                    'path': request.path
                })
                
                # Log slow requests
                if response_time > 1.0 or query_count > 50:
                    logger.warning(
                        f"Slow request: {request.method} {request.path} - "
                        f"{response_time:.2f}s, {query_count} queries"
                    )
                
                # Analyze individual queries
                if settings.DEBUG or getattr(settings, 'MONITOR_QUERIES', False):
                    for query in connection.queries[request._monitoring_query_count:]:
                        query_time = float(query.get('time', 0))
                        metrics_collector.record_metric('query_time', query_time, {
                            'sql': query['sql'][:100]  # First 100 chars
                        })
                        
                        # Log slow queries
                        if query_time > 0.1:
                            logger.warning(
                                f"Slow query ({query_time}s): {query['sql'][:200]}"
                            )
        
        return response
    
    def process_exception(self, request: HttpRequest, exception: Exception):
        """Record exceptions"""
        metrics_collector.record_metric('error', 1, {
            'type': type(exception).__name__,
            'path': request.path,
            'method': request.method
        })
        
        # Log the full exception
        logger.error(
            f"Exception in {request.method} {request.path}: {exception}",
            exc_info=True
        )


class CacheMonitoringMiddleware(MiddlewareMixin):
    """Monitor cache performance"""
    
    def __init__(self, get_response):
        self.get_response = get_response
        self._original_cache_get = None
        self._original_cache_set = None
        super().__init__(get_response)
    
    def __call__(self, request):
        # Monkey patch cache methods to monitor
        if not self._original_cache_get:
            self._patch_cache_methods()
        
        response = self.get_response(request)
        return response
    
    def _patch_cache_methods(self):
        """Patch cache methods to add monitoring"""
        from django.core.cache import cache
        
        self._original_cache_get = cache.get
        self._original_cache_set = cache.set
        
        def monitored_get(key, default=None, version=None):
            start_time = time.time()
            result = self._original_cache_get(key, default, version)
            elapsed = time.time() - start_time
            
            # Record metrics
            is_hit = result is not default
            metrics_collector.record_metric('cache_get', elapsed, {
                'hit': is_hit,
                'key_prefix': key.split(':')[0] if ':' in key else 'unknown'
            })
            
            if is_hit:
                metrics_collector.record_metric('cache_hit', 1)
            else:
                metrics_collector.record_metric('cache_miss', 1)
            
            return result
        
        def monitored_set(key, value, timeout=None, version=None):
            start_time = time.time()
            result = self._original_cache_set(key, value, timeout, version)
            elapsed = time.time() - start_time
            
            metrics_collector.record_metric('cache_set', elapsed, {
                'key_prefix': key.split(':')[0] if ':' in key else 'unknown'
            })
            
            return result
        
        cache.get = monitored_get
        cache.set = monitored_set


class HealthCheckView:
    """Health check endpoint for monitoring"""
    
    @staticmethod
    def check_database() -> Dict[str, Any]:
        """Check database connectivity and performance"""
        try:
            start_time = time.time()
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                cursor.fetchone()
            
            elapsed = time.time() - start_time
            return {
                'status': 'healthy' if elapsed < 0.1 else 'degraded',
                'response_time': elapsed,
                'message': 'Database is responsive'
            }
        except Exception as e:
            return {
                'status': 'unhealthy',
                'error': str(e),
                'message': 'Database connection failed'
            }
    
    @staticmethod
    def check_cache() -> Dict[str, Any]:
        """Check cache connectivity"""
        try:
            test_key = 'health_check_test'
            test_value = str(time.time())
            
            cache.set(test_key, test_value, 60)
            retrieved = cache.get(test_key)
            
            if retrieved == test_value:
                return {
                    'status': 'healthy',
                    'message': 'Cache is working'
                }
            else:
                return {
                    'status': 'unhealthy',
                    'message': 'Cache read/write mismatch'
                }
        except Exception as e:
            return {
                'status': 'unhealthy',
                'error': str(e),
                'message': 'Cache connection failed'
            }
    
    @staticmethod
    def get_metrics_summary() -> Dict[str, Any]:
        """Get current metrics summary"""
        return {
            'response_time': metrics_collector.get_stats('response_time'),
            'query_performance': metrics_collector.get_stats('query_time'),
            'cache_performance': {
                'hits': metrics_collector.get_stats('cache_hit')['count'],
                'misses': metrics_collector.get_stats('cache_miss')['count'],
                'hit_rate': metrics_collector.get_stats('cache_hit')['count'] / 
                           (metrics_collector.get_stats('cache_hit')['count'] + 
                            metrics_collector.get_stats('cache_miss')['count'])
                           if (metrics_collector.get_stats('cache_hit')['count'] + 
                               metrics_collector.get_stats('cache_miss')['count']) > 0 else 0
            },
            'alerts': metrics_collector.check_thresholds()
        }


# Signal receivers for additional monitoring
@receiver(connection_created)
def log_database_connection(sender, connection, **kwargs):
    """Log new database connections"""
    logger.info(f"New database connection created: {connection.alias}")


def export_metrics_prometheus():
    """Export metrics in Prometheus format"""
    lines = []
    
    # Response time metrics
    response_stats = metrics_collector.get_stats('response_time')
    if response_stats:
        lines.append(f'# HELP django_response_time_seconds Response time in seconds')
        lines.append(f'# TYPE django_response_time_seconds summary')
        lines.append(f'django_response_time_seconds{{quantile="0.5"}} {response_stats.get("p50", 0)}')
        lines.append(f'django_response_time_seconds{{quantile="0.95"}} {response_stats.get("p95", 0)}')
        lines.append(f'django_response_time_seconds{{quantile="0.99"}} {response_stats.get("p99", 0)}')
        lines.append(f'django_response_time_seconds_count {response_stats.get("count", 0)}')
    
    # Query metrics
    query_stats = metrics_collector.get_stats('query_time')
    if query_stats:
        lines.append(f'# HELP django_query_time_seconds Database query time in seconds')
        lines.append(f'# TYPE django_query_time_seconds summary')
        lines.append(f'django_query_time_seconds{{quantile="0.5"}} {query_stats.get("p50", 0)}')
        lines.append(f'django_query_time_seconds{{quantile="0.95"}} {query_stats.get("p95", 0)}')
        lines.append(f'django_query_time_seconds{{quantile="0.99"}} {query_stats.get("p99", 0)}')
    
    # Cache metrics
    cache_hits = metrics_collector.get_stats('cache_hit')['count']
    cache_misses = metrics_collector.get_stats('cache_miss')['count']
    
    lines.append(f'# HELP django_cache_hits_total Total number of cache hits')
    lines.append(f'# TYPE django_cache_hits_total counter')
    lines.append(f'django_cache_hits_total {cache_hits}')
    
    lines.append(f'# HELP django_cache_misses_total Total number of cache misses')
    lines.append(f'# TYPE django_cache_misses_total counter')
    lines.append(f'django_cache_misses_total {cache_misses}')
    
    return '\n'.join(lines)