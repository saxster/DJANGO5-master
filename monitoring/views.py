"""
Monitoring views for health checks and metrics endpoints.

CSRF Protection Compliance (Rule #3):
All monitoring endpoints use require_monitoring_api_key decorator for authentication
instead of CSRF tokens. This is the documented alternative protection method for
read-only endpoints accessed by external monitoring systems (Prometheus, Grafana, etc.).

Security:
- API key authentication required for all endpoints
- Rate limiting per API key (1000 requests/hour)
- IP whitelisting support (optional)
- Audit logging for all accesses
- All endpoints are GET-only and read-only (no state modification)

Compliance: Rule #3 Alternative Protection - API key auth for monitoring systems
"""

import json
import time
from datetime import datetime, timedelta

from django.http import JsonResponse, HttpResponse
from django.views import View
from django.utils.decorators import method_decorator
from django.db import connection
from django.core.cache import cache
from django.conf import settings

from apps.core.decorators import require_monitoring_api_key
from .django_monitoring import (
    metrics_collector,
    HealthCheckView,
    export_metrics_prometheus
)


@method_decorator(require_monitoring_api_key, name='dispatch')
class HealthCheckEndpoint(View):
    """
    Health check endpoint for load balancers and monitoring systems.

    Security: Requires monitoring API key authentication (Rule #3 alternative protection).
    """
    
    def get(self, request):
        """Perform health checks and return status"""
        health_status = {
            'status': 'healthy',
            'timestamp': datetime.now().isoformat(),
            'checks': {}
        }
        
        # Database check
        db_check = HealthCheckView.check_database()
        health_status['checks']['database'] = db_check
        if db_check['status'] == 'unhealthy':
            health_status['status'] = 'unhealthy'
        
        # Cache check
        cache_check = HealthCheckView.check_cache()
        health_status['checks']['cache'] = cache_check
        if cache_check['status'] == 'unhealthy':
            health_status['status'] = 'unhealthy'
        
        # Check for critical alerts
        alerts = metrics_collector.check_thresholds()
        critical_alerts = [a for a in alerts if a['level'] == 'CRITICAL']
        if critical_alerts:
            health_status['status'] = 'unhealthy'
            health_status['alerts'] = critical_alerts
        
        # Return appropriate status code
        status_code = 200 if health_status['status'] == 'healthy' else 503
        
        return JsonResponse(health_status, status=status_code)


@method_decorator(require_monitoring_api_key, name='dispatch')
class MetricsEndpoint(View):
    """
    Metrics endpoint for monitoring systems.

    Security: Requires monitoring API key authentication (Rule #3 alternative protection).
    """
    
    def get(self, request):
        """Return metrics in requested format"""
        format_type = request.GET.get('format', 'json')
        
        if format_type == 'prometheus':
            # Return Prometheus format
            metrics_text = export_metrics_prometheus()
            return HttpResponse(
                metrics_text, 
                content_type='text/plain; version=0.0.4'
            )
        else:
            # Return JSON format
            metrics_data = {
                'timestamp': datetime.now().isoformat(),
                'uptime': time.time() - metrics_collector.start_time,
                'metrics': HealthCheckView.get_metrics_summary(),
                'system': self._get_system_metrics()
            }
            
            return JsonResponse(metrics_data)
    
    def _get_system_metrics(self):
        """Get system-level metrics"""
        import psutil
        
        try:
            return {
                'cpu_percent': psutil.cpu_percent(interval=0.1),
                'memory': {
                    'total': psutil.virtual_memory().total,
                    'available': psutil.virtual_memory().available,
                    'percent': psutil.virtual_memory().percent
                },
                'disk': {
                    'total': psutil.disk_usage('/').total,
                    'free': psutil.disk_usage('/').free,
                    'percent': psutil.disk_usage('/').percent
                }
            }
        except:
            return {}


@method_decorator(require_monitoring_api_key, name='dispatch')
class QueryPerformanceView(View):
    """
    Detailed query performance metrics.

    Security: Requires monitoring API key authentication (Rule #3 alternative protection).
    """
    
    def get(self, request):
        """Return query performance data"""
        # Get query stats from the last hour
        window_minutes = int(request.GET.get('window', 60))
        
        query_stats = metrics_collector.get_stats('query_time', window_minutes)
        query_count_stats = metrics_collector.get_stats('query_count', window_minutes)
        
        # Get slow queries
        slow_queries = []
        with metrics_collector.lock:
            query_metrics = metrics_collector.metrics.get('query_time', [])
            for metric in query_metrics[-100:]:  # Last 100 queries
                if metric['value'] > 0.1:  # Queries over 100ms
                    slow_queries.append({
                        'timestamp': metric['timestamp'],
                        'time': metric['value'],
                        'sql': metric['tags'].get('sql', 'Unknown')
                    })
        
        # Sort by time descending
        slow_queries.sort(key=lambda x: x['time'], reverse=True)
        
        response_data = {
            'timestamp': datetime.now().isoformat(),
            'window_minutes': window_minutes,
            'query_performance': query_stats,
            'queries_per_request': query_count_stats,
            'slow_queries': slow_queries[:20],  # Top 20 slowest
            'recommendations': self._get_recommendations(query_stats, slow_queries)
        }
        
        return JsonResponse(response_data)
    
    def _get_recommendations(self, query_stats, slow_queries):
        """Generate performance recommendations"""
        recommendations = []
        
        if query_stats.get('p95', 0) > 0.1:
            recommendations.append({
                'level': 'warning',
                'message': '95th percentile query time exceeds 100ms',
                'action': 'Review slow queries and add appropriate indexes'
            })
        
        if query_stats.get('p99', 0) > 0.5:
            recommendations.append({
                'level': 'critical',
                'message': '99th percentile query time exceeds 500ms',
                'action': 'Critical performance issue - investigate immediately'
            })
        
        # Check for repeated slow queries
        sql_counts = {}
        for query in slow_queries:
            sql = query['sql']
            sql_counts[sql] = sql_counts.get(sql, 0) + 1
        
        for sql, count in sql_counts.items():
            if count > 5:
                recommendations.append({
                    'level': 'warning',
                    'message': f'Query executed {count} times slowly: {sql[:50]}...',
                    'action': 'Consider adding an index or optimizing this query'
                })
        
        return recommendations


@method_decorator(require_monitoring_api_key, name='dispatch')
class CachePerformanceView(View):
    """
    Cache performance metrics.

    Security: Requires monitoring API key authentication (Rule #3 alternative protection).
    """
    
    def get(self, request):
        """Return cache performance data"""
        window_minutes = int(request.GET.get('window', 60))
        
        # Get cache stats
        cache_hit_stats = metrics_collector.get_stats('cache_hit', window_minutes)
        cache_miss_stats = metrics_collector.get_stats('cache_miss', window_minutes)
        cache_get_stats = metrics_collector.get_stats('cache_get', window_minutes)
        cache_set_stats = metrics_collector.get_stats('cache_set', window_minutes)
        
        # Calculate hit rate
        total_hits = cache_hit_stats.get('count', 0)
        total_misses = cache_miss_stats.get('count', 0)
        total_requests = total_hits + total_misses
        
        hit_rate = (total_hits / total_requests * 100) if total_requests > 0 else 0
        
        response_data = {
            'timestamp': datetime.now().isoformat(),
            'window_minutes': window_minutes,
            'hit_rate': hit_rate,
            'total_requests': total_requests,
            'hits': total_hits,
            'misses': total_misses,
            'get_performance': cache_get_stats,
            'set_performance': cache_set_stats,
            'recommendations': self._get_cache_recommendations(hit_rate, cache_get_stats)
        }
        
        return JsonResponse(response_data)
    
    def _get_cache_recommendations(self, hit_rate, get_stats):
        """Generate cache recommendations"""
        recommendations = []
        
        if hit_rate < 50:
            recommendations.append({
                'level': 'warning',
                'message': f'Low cache hit rate: {hit_rate:.1f}%',
                'action': 'Review cache keys and TTL settings'
            })
        
        if get_stats.get('p95', 0) > 0.01:
            recommendations.append({
                'level': 'info',
                'message': 'Cache GET operations taking over 10ms at p95',
                'action': 'Consider using local memory cache or Redis Cluster'
            })
        
        return recommendations


@method_decorator(require_monitoring_api_key, name='dispatch')
class AlertsView(View):
    """
    Current alerts and threshold violations.

    Security: Requires monitoring API key authentication (Rule #3 alternative protection).
    """
    
    def get(self, request):
        """Return current alerts"""
        alerts = metrics_collector.check_thresholds()
        
        # Group by level
        alerts_by_level = {
            'critical': [],
            'warning': [],
            'info': []
        }
        
        for alert in alerts:
            level = alert['level'].lower()
            if level in alerts_by_level:
                alerts_by_level[level].append(alert)
        
        response_data = {
            'timestamp': datetime.now().isoformat(),
            'total_alerts': len(alerts),
            'alerts': alerts_by_level,
            'thresholds': metrics_collector.THRESHOLDS
        }
        
        return JsonResponse(response_data)


@method_decorator(require_monitoring_api_key, name='dispatch')
class DashboardDataView(View):
    """
    Aggregated data for monitoring dashboards.

    Security: Requires monitoring API key authentication (Rule #3 alternative protection).
    """
    
    def get(self, request):
        """Return dashboard data"""
        # Time ranges
        ranges = {
            '5m': 5,
            '15m': 15,
            '1h': 60,
            '24h': 1440
        }
        
        dashboard_data = {
            'timestamp': datetime.now().isoformat(),
            'current_alerts': len(metrics_collector.check_thresholds()),
            'time_series': {}
        }
        
        # Get metrics for each time range
        for range_name, minutes in ranges.items():
            dashboard_data['time_series'][range_name] = {
                'response_time': metrics_collector.get_stats('response_time', minutes),
                'query_performance': metrics_collector.get_stats('query_time', minutes),
                'error_rate': self._calculate_error_rate(minutes),
                'cache_hit_rate': self._calculate_cache_hit_rate(minutes),
                'requests_per_minute': self._calculate_rpm(minutes)
            }
        
        # Add top endpoints
        dashboard_data['top_endpoints'] = self._get_top_endpoints()
        
        return JsonResponse(dashboard_data)
    
    def _calculate_error_rate(self, window_minutes):
        """Calculate error rate for time window"""
        total_requests = metrics_collector.get_stats('request', window_minutes).get('count', 0)
        total_errors = metrics_collector.get_stats('error', window_minutes).get('count', 0)
        
        if total_requests == 0:
            return 0
        
        return (total_errors / total_requests) * 100
    
    def _calculate_cache_hit_rate(self, window_minutes):
        """Calculate cache hit rate for time window"""
        hits = metrics_collector.get_stats('cache_hit', window_minutes).get('count', 0)
        misses = metrics_collector.get_stats('cache_miss', window_minutes).get('count', 0)
        total = hits + misses
        
        if total == 0:
            return 0
        
        return (hits / total) * 100
    
    def _calculate_rpm(self, window_minutes):
        """Calculate requests per minute"""
        total = metrics_collector.get_stats('request', window_minutes).get('count', 0)
        return total / window_minutes if window_minutes > 0 else 0
    
    def _get_top_endpoints(self):
        """Get top endpoints by request count"""
        endpoint_counts = {}
        
        with metrics_collector.lock:
            request_metrics = metrics_collector.metrics.get('request', [])
            for metric in request_metrics[-1000:]:  # Last 1000 requests
                path = metric['tags'].get('path', 'Unknown')
                endpoint_counts[path] = endpoint_counts.get(path, 0) + 1
        
        # Sort and return top 10
        sorted_endpoints = sorted(
            endpoint_counts.items(), 
            key=lambda x: x[1], 
            reverse=True
        )
        
        return [
            {'path': path, 'count': count} 
            for path, count in sorted_endpoints[:10]
        ]