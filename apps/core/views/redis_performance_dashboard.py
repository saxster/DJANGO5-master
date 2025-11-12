"""
Redis Performance Dashboard Views

Provides comprehensive Redis performance monitoring through Django admin interface with:
- Real-time metrics display
- Performance trends and charts
- Alert management
- Capacity planning insights
- Multi-instance monitoring support

Integration with Django admin for operational visibility.
"""

import json
from datetime import datetime, timedelta
from typing import Dict, List, Any

from django.contrib.admin.views.decorators import staff_member_required
from django.http import JsonResponse, HttpResponse
from django.shortcuts import render
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views import View
from django.views.generic import TemplateView
from django.contrib import messages

from apps.core.services.redis_metrics_collector import redis_metrics_collector
from apps.core.services.redis_memory_manager import redis_memory_manager
from apps.core.health_checks.cache import (
from apps.core.exceptions.patterns import CACHE_EXCEPTIONS

from apps.core.exceptions.patterns import DATABASE_EXCEPTIONS

    check_redis_connectivity, check_redis_memory_health,
    check_redis_performance, check_default_cache
)


@method_decorator(staff_member_required, name='dispatch')
class RedisPerformanceDashboardView(TemplateView):
    """
    Main Redis performance dashboard view.

    Displays comprehensive Redis metrics, alerts, and performance trends
    in the Django admin interface.
    """
    template_name = 'admin/redis_performance_dashboard.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        try:
            # Collect current metrics
            current_metrics = redis_metrics_collector.collect_metrics('main')

            if current_metrics:
                # Get performance alerts
                performance_alerts = redis_metrics_collector.analyze_performance(current_metrics)

                # Get capacity recommendations
                capacity_recommendations = redis_metrics_collector.get_capacity_recommendations(current_metrics)

                # Get performance trends
                trends_24h = redis_metrics_collector.get_performance_trends(hours_back=24)

                # Get health check results
                health_checks = {
                    'connectivity': check_redis_connectivity(),
                    'memory_health': check_redis_memory_health(),
                    'performance': check_redis_performance(),
                    'cache_functionality': check_default_cache()
                }

                # Calculate overall health score
                health_statuses = [check['status'] for check in health_checks.values()]
                overall_health = self._calculate_overall_health(health_statuses)

                context.update({
                    'current_metrics': current_metrics,
                    'performance_alerts': performance_alerts,
                    'capacity_recommendations': capacity_recommendations,
                    'performance_trends': trends_24h,
                    'health_checks': health_checks,
                    'overall_health': overall_health,
                    'dashboard_timestamp': timezone.now(),
                    'critical_alerts_count': len([a for a in performance_alerts if a.alert_level == 'critical']),
                    'warning_alerts_count': len([a for a in performance_alerts if a.alert_level == 'warning']),
                })

            else:
                messages.error(self.request, 'Unable to collect Redis metrics - check connection')
                context.update({
                    'metrics_error': 'Unable to connect to Redis',
                    'dashboard_timestamp': timezone.now(),
                })

        except CACHE_EXCEPTIONS as e:
            messages.error(self.request, f'Dashboard error: {str(e)}')
            context.update({
                'dashboard_error': str(e),
                'dashboard_timestamp': timezone.now(),
            })

        return context

    def _calculate_overall_health(self, health_statuses: List[str]) -> str:
        """Calculate overall health from individual check statuses."""
        if 'error' in health_statuses:
            return 'error'
        elif 'degraded' in health_statuses:
            return 'degraded'
        else:
            return 'healthy'


@method_decorator(staff_member_required, name='dispatch')
class RedisMetricsAPIView(View):
    """
    API endpoint for real-time Redis metrics (AJAX).

    Provides JSON metrics data for dashboard charts and real-time updates.
    """

    def get(self, request):
        try:
            # Get current metrics
            metrics = redis_metrics_collector.collect_metrics('main')

            if not metrics:
                return JsonResponse({
                    'error': 'Unable to collect Redis metrics',
                    'timestamp': timezone.now().isoformat()
                }, status=503)

            # Convert metrics to JSON-serializable format
            metrics_data = {
                'timestamp': metrics.timestamp.isoformat(),
                'instance_name': metrics.instance_name,
                'instance_role': metrics.instance_role,

                # Memory metrics
                'memory': {
                    'used_memory_mb': metrics.used_memory / 1024 / 1024,
                    'used_memory_human': metrics.used_memory_human,
                    'memory_usage_percent': (
                        (metrics.used_memory / metrics.maxmemory) * 100
                        if metrics.maxmemory > 0 else 0
                    ),
                    'fragmentation_ratio': metrics.memory_fragmentation_ratio,
                    'evicted_keys': metrics.evicted_keys
                },

                # Performance metrics
                'performance': {
                    'ops_per_second': metrics.instantaneous_ops_per_sec,
                    'hit_ratio': metrics.hit_ratio,
                    'total_commands': metrics.total_commands_processed,
                    'input_kbps': metrics.instantaneous_input_kbps,
                    'output_kbps': metrics.instantaneous_output_kbps
                },

                # Connection metrics
                'connections': {
                    'connected_clients': metrics.connected_clients,
                    'blocked_clients': metrics.blocked_clients,
                    'tracking_clients': metrics.tracking_clients
                },

                # System metrics
                'system': {
                    'uptime_hours': metrics.uptime_in_seconds / 3600,
                    'redis_version': metrics.redis_version,
                    'process_id': metrics.process_id
                }
            }

            # Add performance alerts
            alerts = redis_metrics_collector.analyze_performance(metrics)
            metrics_data['alerts'] = [
                {
                    'level': alert.alert_level,
                    'metric': alert.metric_name,
                    'message': alert.message,
                    'recommendation': alert.recommendation,
                    'current_value': alert.current_value,
                    'threshold_value': alert.threshold_value
                }
                for alert in alerts
            ]

            return JsonResponse(metrics_data)

        except (ValueError, TypeError, AttributeError) as e:
            return JsonResponse({
                'error': f'Metrics collection failed: {str(e)}',
                'timestamp': timezone.now().isoformat()
            }, status=500)


@method_decorator(staff_member_required, name='dispatch')
class RedisPerformanceTrendsAPIView(View):
    """
    API endpoint for Redis performance trends data.

    Provides historical performance data for charts and analysis.
    """

    def get(self, request):
        try:
            # Get query parameters
            hours_back = int(request.GET.get('hours', 24))
            hours_back = min(hours_back, 168)  # Limit to 1 week

            # Get trends data
            trends = redis_metrics_collector.get_performance_trends(hours_back)

            return JsonResponse(trends)

        except ValueError as e:
            return JsonResponse({
                'error': f'Invalid parameters: {str(e)}',
                'timestamp': timezone.now().isoformat()
            }, status=400)

        except DATABASE_EXCEPTIONS as e:
            return JsonResponse({
                'error': f'Trends analysis failed: {str(e)}',
                'timestamp': timezone.now().isoformat()
            }, status=500)


@method_decorator(staff_member_required, name='dispatch')
class RedisMemoryOptimizationView(View):
    """
    View for triggering Redis memory optimization.

    Allows administrators to manually trigger memory optimization
    and view optimization results.
    """

    def post(self, request):
        try:
            # Get parameters
            force = request.POST.get('force', 'false').lower() == 'true'

            # Trigger memory optimization
            optimization_results = redis_memory_manager.optimize_memory_usage(force=force)

            return JsonResponse({
                'status': 'completed',
                'optimization_results': optimization_results,
                'timestamp': timezone.now().isoformat()
            })

        except DATABASE_EXCEPTIONS as e:
            return JsonResponse({
                'error': f'Memory optimization failed: {str(e)}',
                'timestamp': timezone.now().isoformat()
            }, status=500)

    def get(self, request):
        """Get current memory status and optimization recommendations."""
        try:
            # Get memory statistics
            memory_stats = redis_memory_manager.get_memory_stats()

            if not memory_stats:
                return JsonResponse({
                    'error': 'Unable to retrieve memory statistics',
                    'timestamp': timezone.now().isoformat()
                }, status=503)

            # Get health alerts
            memory_alerts = redis_memory_manager.check_memory_health()

            # Get optimization recommendations
            recommendations = redis_memory_manager.get_optimization_recommendations()

            return JsonResponse({
                'memory_stats': {
                    'used_memory_human': memory_stats.used_memory_human,
                    'maxmemory_human': memory_stats.maxmemory_human,
                    'fragmentation_ratio': memory_stats.memory_fragmentation_ratio,
                    'hit_ratio': memory_stats.hit_ratio,
                    'evicted_keys': memory_stats.evicted_keys,
                    'expired_keys': memory_stats.expired_keys
                },
                'alerts': [
                    {
                        'level': alert.level,
                        'message': alert.message,
                        'recommended_action': alert.recommended_action,
                        'current_usage': alert.current_usage
                    }
                    for alert in memory_alerts
                ],
                'recommendations': recommendations,
                'timestamp': timezone.now().isoformat()
            })

        except CACHE_EXCEPTIONS as e:
            return JsonResponse({
                'error': f'Memory status retrieval failed: {str(e)}',
                'timestamp': timezone.now().isoformat()
            }, status=500)


@method_decorator(staff_member_required, name='dispatch')
class RedisHealthCheckAPIView(View):
    """
    API endpoint for comprehensive Redis health checks.

    Provides detailed health status for monitoring integration.
    """

    def get(self, request):
        try:
            # Run all health checks
            health_results = {
                'connectivity': check_redis_connectivity(),
                'memory_health': check_redis_memory_health(),
                'performance': check_redis_performance(),
                'cache_functionality': check_default_cache()
            }

            # Check if Sentinel is enabled and add Sentinel checks
            try:
                import os
                if os.environ.get('REDIS_SENTINEL_ENABLED') == 'true':
                    from apps.core.health_checks.sentinel import (
                        check_sentinel_cluster_health,
                        check_sentinel_quorum
                    )
                    health_results.update({
                        'sentinel_cluster': check_sentinel_cluster_health(),
                        'sentinel_quorum': check_sentinel_quorum()
                    })
            except (ImportError, Exception):
                pass  # Sentinel not available

            # Calculate overall status
            all_statuses = [result['status'] for result in health_results.values()]
            if 'error' in all_statuses:
                overall_status = 'error'
            elif 'degraded' in all_statuses:
                overall_status = 'degraded'
            else:
                overall_status = 'healthy'

            return JsonResponse({
                'overall_status': overall_status,
                'health_checks': health_results,
                'timestamp': timezone.now().isoformat(),
                'checks_count': len(health_results),
                'healthy_checks': len([s for s in all_statuses if s == 'healthy']),
                'degraded_checks': len([s for s in all_statuses if s == 'degraded']),
                'error_checks': len([s for s in all_statuses if s == 'error'])
            })

        except CACHE_EXCEPTIONS as e:
            return JsonResponse({
                'error': f'Health check failed: {str(e)}',
                'timestamp': timezone.now().isoformat()
            }, status=500)


# Export view functions for URL configuration
redis_performance_dashboard = RedisPerformanceDashboardView.as_view()
redis_metrics_api = RedisMetricsAPIView.as_view()
redis_trends_api = RedisPerformanceTrendsAPIView.as_view()
redis_memory_optimization = RedisMemoryOptimizationView.as_view()
redis_health_check_api = RedisHealthCheckAPIView.as_view()

# Export for URL patterns
__all__ = [
    'RedisPerformanceDashboardView',
    'RedisMetricsAPIView',
    'RedisPerformanceTrendsAPIView',
    'RedisMemoryOptimizationView',
    'RedisHealthCheckAPIView',
    'redis_performance_dashboard',
    'redis_metrics_api',
    'redis_trends_api',
    'redis_memory_optimization',
    'redis_health_check_api'
]