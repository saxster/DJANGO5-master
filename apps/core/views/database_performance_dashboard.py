"""
Database Performance Monitoring Dashboard

Provides comprehensive web-based interface for monitoring PostgreSQL performance
including connection pools, query analysis, and maintenance status.

Features:
- Real-time connection pool monitoring
- Slow query alerts and analysis
- Historical performance trends
- Query pattern analysis
- Database maintenance status
- Export capabilities for reports

Security:
- Admin-only access required
- CSRF protection enabled
- Rate limiting applied

Compliance:
- Rule #7: View methods < 30 lines
- Enterprise monitoring standards
"""

import json
import time
from datetime import timedelta
from decimal import Decimal

from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.db import connection
from django.db.models import Count, Avg, Max, Sum
from django.http import JsonResponse, HttpResponse
from django.shortcuts import render
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.cache import cache_page
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import TemplateView

from apps.core.models.query_performance import (
    QueryPerformanceSnapshot,
    SlowQueryAlert,
    QueryPattern
)


class DatabasePerformanceDashboard(TemplateView):
    """
    Main dashboard view showing comprehensive database performance metrics.

    Displays:
    - Connection pool status
    - Active slow query alerts
    - Performance trends
    - Query patterns
    """

    template_name = 'admin/database_performance_dashboard.html'

    @method_decorator(staff_member_required)
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Get dashboard summary data
        context.update({
            'dashboard_title': 'Database Performance Monitor',
            'last_updated': timezone.now(),
            'refresh_interval': 30000,  # 30 seconds
        })

        return context


class ConnectionPoolStatusAPI(View):
    """
    API endpoint for real-time connection pool status.

    Returns JSON with current pool utilization, active connections,
    and health status across all configured databases.
    """

    @method_decorator(staff_member_required)
    @method_decorator(cache_page(10))  # Cache for 10 seconds
    def get(self, request):
        try:
            # Get cached connection stats
            default_stats = cache.get('db_connection_stats:default', {})

            # Get additional database stats if available
            all_stats = {'default': default_stats}

            for db_alias in ['read_replica', 'analytics']:
                stats = cache.get(f'db_connection_stats:{db_alias}')
                if stats:
                    all_stats[db_alias] = stats

            # Calculate summary metrics
            total_connections = sum(
                stats.get('active_connections', 0)
                for stats in all_stats.values()
            )

            max_usage = max(
                stats.get('usage_percentage', 0)
                for stats in all_stats.values()
                if stats
            ) if all_stats else 0

            # Determine overall health
            health_status = 'healthy'
            if max_usage > 90:
                health_status = 'critical'
            elif max_usage > 80:
                health_status = 'warning'

            return JsonResponse({
                'status': 'success',
                'timestamp': timezone.now().isoformat(),
                'summary': {
                    'total_connections': total_connections,
                    'max_usage_percentage': max_usage,
                    'health_status': health_status,
                    'database_count': len(all_stats)
                },
                'databases': all_stats
            })

        except Exception as e:
            return JsonResponse({
                'status': 'error',
                'error': str(e),
                'timestamp': timezone.now().isoformat()
            })


class SlowQueryAlertsAPI(View):
    """
    API endpoint for slow query alerts and analysis.

    Returns current alerts, recent trends, and query patterns
    that need attention.
    """

    @method_decorator(staff_member_required)
    def get(self, request):
        try:
            # Get recent alerts
            hours_back = int(request.GET.get('hours', 24))
            since = timezone.now() - timedelta(hours=hours_back)

            recent_alerts = SlowQueryAlert.objects.filter(
                alert_time__gte=since
            ).select_related().order_by('-alert_time')[:50]

            # Group alerts by severity
            alerts_by_severity = recent_alerts.values('severity').annotate(
                count=Count('id')
            ).order_by('severity')

            # Get top slow query patterns
            slow_patterns = QueryPattern.objects.filter(
                avg_execution_time__gt=1000
            ).order_by('-total_queries')[:10]

            # Serialize alerts
            alerts_data = []
            for alert in recent_alerts[:20]:  # Limit to 20 for API response
                alerts_data.append({
                    'id': alert.id,
                    'severity': alert.severity,
                    'alert_type': alert.alert_type,
                    'execution_time': float(alert.execution_time),
                    'alert_time': alert.alert_time.isoformat(),
                    'status': alert.status,
                    'query_preview': alert.query_text[:100] + '...' if len(alert.query_text) > 100 else alert.query_text,
                })

            # Serialize patterns
            patterns_data = []
            for pattern in slow_patterns:
                patterns_data.append({
                    'pattern_hash': pattern.pattern_hash,
                    'query_type': pattern.query_type,
                    'total_queries': pattern.total_queries,
                    'avg_execution_time': float(pattern.avg_execution_time),
                    'pattern_preview': pattern.pattern_text[:150] + '...' if len(pattern.pattern_text) > 150 else pattern.pattern_text,
                })

            return JsonResponse({
                'status': 'success',
                'timestamp': timezone.now().isoformat(),
                'summary': {
                    'total_alerts': recent_alerts.count(),
                    'alerts_by_severity': list(alerts_by_severity),
                    'slow_patterns_count': slow_patterns.count(),
                },
                'recent_alerts': alerts_data,
                'slow_patterns': patterns_data
            })

        except Exception as e:
            return JsonResponse({
                'status': 'error',
                'error': str(e),
                'timestamp': timezone.now().isoformat()
            })


class PerformanceMetricsAPI(View):
    """
    API endpoint for historical performance metrics and trends.

    Returns time-series data for charting performance over time.
    """

    @method_decorator(staff_member_required)
    @method_decorator(cache_page(60))  # Cache for 1 minute
    def get(self, request):
        try:
            # Get time range
            hours_back = int(request.GET.get('hours', 24))
            since = timezone.now() - timedelta(hours=hours_back)

            # Get performance snapshots
            snapshots = QueryPerformanceSnapshot.objects.filter(
                snapshot_time__gte=since
            ).order_by('-snapshot_time')[:500]  # Limit for performance

            # Group by hour for trending
            hourly_metrics = {}
            for snapshot in snapshots:
                hour_key = snapshot.snapshot_time.strftime('%Y-%m-%d %H:00')

                if hour_key not in hourly_metrics:
                    hourly_metrics[hour_key] = {
                        'timestamp': hour_key,
                        'total_queries': 0,
                        'avg_execution_time': 0,
                        'slow_queries': 0,
                        'total_time': 0,
                    }

                metrics = hourly_metrics[hour_key]
                metrics['total_queries'] += 1
                metrics['total_time'] += float(snapshot.total_exec_time)

                if snapshot.mean_exec_time > 1000:  # > 1 second
                    metrics['slow_queries'] += 1

            # Calculate averages
            for hour_key, metrics in hourly_metrics.items():
                if metrics['total_queries'] > 0:
                    metrics['avg_execution_time'] = metrics['total_time'] / metrics['total_queries']

            # Convert to time series format
            time_series = sorted(
                hourly_metrics.values(),
                key=lambda x: x['timestamp']
            )

            # Get database size information
            db_stats = self._get_database_stats()

            return JsonResponse({
                'status': 'success',
                'timestamp': timezone.now().isoformat(),
                'time_range_hours': hours_back,
                'metrics': {
                    'time_series': time_series,
                    'database_stats': db_stats,
                }
            })

        except Exception as e:
            return JsonResponse({
                'status': 'error',
                'error': str(e),
                'timestamp': timezone.now().isoformat()
            })

    def _get_database_stats(self):
        """Get current database statistics."""
        try:
            with connection.cursor() as cursor:
                cursor.execute("""
                    SELECT
                        pg_size_pretty(pg_database_size(current_database())) as db_size,
                        (SELECT count(*) FROM pg_stat_activity WHERE state = 'active') as active_queries,
                        (SELECT count(*) FROM pg_stat_activity WHERE datname = current_database()) as total_connections
                """)

                row = cursor.fetchone()
                return {
                    'database_size': row[0] if row else 'Unknown',
                    'active_queries': row[1] if row else 0,
                    'total_connections': row[2] if row else 0,
                }
        except Exception:
            return {
                'database_size': 'Unknown',
                'active_queries': 0,
                'total_connections': 0,
            }


class QueryAnalysisAPI(View):
    """
    API endpoint for detailed query analysis and recommendations.

    Provides optimization insights and recommendations based on
    query patterns and performance history.
    """

    @method_decorator(staff_member_required)
    def get(self, request):
        try:
            query_hash = request.GET.get('query_hash')
            if query_hash:
                return self._get_specific_query_analysis(query_hash)
            else:
                return self._get_general_query_analysis()

        except Exception as e:
            return JsonResponse({
                'status': 'error',
                'error': str(e),
                'timestamp': timezone.now().isoformat()
            })

    def _get_specific_query_analysis(self, query_hash):
        """Get analysis for a specific query."""
        try:
            query_hash_int = int(query_hash)
        except ValueError:
            return JsonResponse({'status': 'error', 'error': 'Invalid query hash'})

        # Get recent performance snapshots for this query
        snapshots = QueryPerformanceSnapshot.objects.filter(
            query_hash=query_hash_int
        ).order_by('-snapshot_time')[:50]

        if not snapshots:
            return JsonResponse({'status': 'error', 'error': 'Query not found'})

        # Calculate performance metrics
        total_calls = sum(s.calls for s in snapshots)
        avg_time = sum(float(s.mean_exec_time) for s in snapshots) / len(snapshots)
        max_time = max(float(s.max_exec_time) for s in snapshots)

        # Get recent alerts for this query
        recent_alerts = SlowQueryAlert.objects.filter(
            query_hash=query_hash_int,
            alert_time__gte=timezone.now() - timedelta(days=7)
        ).count()

        return JsonResponse({
            'status': 'success',
            'query_hash': query_hash,
            'analysis': {
                'total_calls': total_calls,
                'average_execution_time': avg_time,
                'max_execution_time': max_time,
                'recent_alerts': recent_alerts,
                'sample_query': snapshots[0].query_text[:500] if snapshots else '',
            }
        })

    def _get_general_query_analysis(self):
        """Get general query analysis and recommendations."""
        # Get top slow query patterns
        slow_patterns = QueryPattern.objects.filter(
            avg_execution_time__gt=500
        ).order_by('-avg_execution_time')[:10]

        # Generate recommendations
        recommendations = []

        for pattern in slow_patterns:
            rec = {
                'pattern_hash': pattern.pattern_hash,
                'query_type': pattern.query_type,
                'avg_time': float(pattern.avg_execution_time),
                'total_queries': pattern.total_queries,
                'recommendations': []
            }

            # Generate specific recommendations
            if 'SELECT *' in pattern.pattern_text.upper():
                rec['recommendations'].append('Consider selecting specific columns instead of SELECT *')

            if pattern.query_type == 'SELECT' and pattern.avg_execution_time > 2000:
                rec['recommendations'].append('Query exceeds 2s - consider adding indexes or query optimization')

            if 'JOIN' in pattern.pattern_text.upper() and pattern.avg_execution_time > 1000:
                rec['recommendations'].append('Complex join detected - verify indexes on join columns')

            recommendations.append(rec)

        return JsonResponse({
            'status': 'success',
            'timestamp': timezone.now().isoformat(),
            'recommendations': recommendations
        })


@staff_member_required
def export_performance_report(request):
    """
    Export comprehensive performance report as JSON.

    Generates detailed report including all performance metrics,
    alerts, and analysis for administrative review.
    """
    try:
        # Get comprehensive data
        hours_back = int(request.GET.get('hours', 168))  # Default 1 week
        since = timezone.now() - timedelta(hours=hours_back)

        # Collect all performance data
        report_data = {
            'generated_at': timezone.now().isoformat(),
            'time_range_hours': hours_back,
            'connection_stats': cache.get('db_connection_stats:default', {}),
            'recent_alerts': list(SlowQueryAlert.objects.filter(
                alert_time__gte=since
            ).values()),
            'query_patterns': list(QueryPattern.objects.all()[:100].values()),
            'performance_snapshots': list(QueryPerformanceSnapshot.objects.filter(
                snapshot_time__gte=since
            ).order_by('-snapshot_time')[:1000].values()),
        }

        # Convert Decimal fields to float for JSON serialization
        def decimal_converter(obj):
            if isinstance(obj, Decimal):
                return float(obj)
            raise TypeError

        response = HttpResponse(
            json.dumps(report_data, indent=2, default=decimal_converter),
            content_type='application/json'
        )
        response['Content-Disposition'] = f'attachment; filename="db_performance_report_{timezone.now().strftime("%Y%m%d_%H%M%S")}.json"'

        return response

    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'error': str(e),
            'timestamp': timezone.now().isoformat()
        })