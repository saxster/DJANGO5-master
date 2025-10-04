"""
Spatial Query Performance Dashboard Views

Provides dashboard interface for monitoring spatial query performance,
viewing slow queries, and analyzing trends.

Following .claude/rules.md:
- Rule #7: Views < 150 lines
- Rule #8: View methods < 30 lines
- Rule #11: Specific exception handling
"""

import json
import logging
from datetime import datetime, timedelta
from typing import Dict, Any
from django.http import JsonResponse, HttpRequest
from django.views.decorators.http import require_http_methods
from django.views.decorators.cache import cache_page
from django.contrib.auth.decorators import login_required, user_passes_test
from django.core.exceptions import ValidationError, PermissionDenied

from apps.core.services.spatial_query_performance_monitor import spatial_query_monitor
from apps.core.constants.datetime_constants import SECONDS_IN_HOUR

logger = logging.getLogger(__name__)


def is_admin_or_staff(user):
    """Check if user is admin or staff."""
    return user.is_authenticated and (user.is_staff or user.is_superuser)


@login_required
@user_passes_test(is_admin_or_staff)
@require_http_methods(["GET"])
@cache_page(60)  # Cache for 1 minute
def spatial_performance_dashboard(request: HttpRequest) -> JsonResponse:
    """
    Get spatial query performance dashboard data.

    Returns real-time metrics including:
    - Total queries processed
    - Average query execution time
    - Slow query counts by severity
    - Health status

    Query Parameters:
        None

    Returns:
        JsonResponse with dashboard summary data

    Example Response:
        {
            "status": "success",
            "data": {
                "total_queries_today": 1523,
                "avg_query_time_ms": 42.5,
                "slow_queries_count": 8,
                "slow_queries_by_severity": {
                    "CRITICAL": 1,
                    "HIGH": 2,
                    "MEDIUM": 5
                },
                "health_status": "HEALTHY"
            }
        }
    """
    try:
        summary = spatial_query_monitor.get_dashboard_summary()

        return JsonResponse({
            'status': 'success',
            'data': summary,
            'timestamp': datetime.now().isoformat()
        })

    except (ValidationError, ValueError, TypeError) as e:
        logger.error(f"Error generating dashboard data: {e}")
        return JsonResponse({
            'status': 'error',
            'message': 'Failed to generate dashboard data'
        }, status=500)


@login_required
@user_passes_test(is_admin_or_staff)
@require_http_methods(["GET"])
def spatial_slow_queries(request: HttpRequest) -> JsonResponse:
    """
    Get list of slow spatial queries.

    Query Parameters:
        date (optional): Date in YYYY-MM-DD format (default: today)
        severity (optional): Filter by severity (MEDIUM, HIGH, CRITICAL)
        limit (optional): Maximum number of queries to return (default: 50)

    Returns:
        JsonResponse with list of slow queries

    Example Response:
        {
            "status": "success",
            "data": [
                {
                    "timestamp": "2025-09-30T14:23:45.123456",
                    "query_type": "geofence_check",
                    "execution_time_ms": 752.3,
                    "severity": "HIGH",
                    "query_params": {"geofence_id": 123}
                }
            ],
            "count": 8
        }
    """
    try:
        # Parse query parameters
        date_str = request.GET.get('date')
        severity = request.GET.get('severity')
        limit = int(request.GET.get('limit', 50))

        # Validate limit
        if limit > 200:
            limit = 200

        # Parse date
        if date_str:
            try:
                date = datetime.strptime(date_str, '%Y-%m-%d')
            except ValueError:
                return JsonResponse({
                    'status': 'error',
                    'message': 'Invalid date format. Use YYYY-MM-DD'
                }, status=400)
        else:
            date = datetime.now()

        # Validate severity
        if severity and severity not in ['MEDIUM', 'HIGH', 'CRITICAL']:
            return JsonResponse({
                'status': 'error',
                'message': 'Invalid severity. Must be MEDIUM, HIGH, or CRITICAL'
            }, status=400)

        # Get slow queries
        slow_queries = spatial_query_monitor.get_slow_queries(
            date=date,
            severity=severity
        )

        # Apply limit
        slow_queries = slow_queries[:limit]

        return JsonResponse({
            'status': 'success',
            'data': slow_queries,
            'count': len(slow_queries),
            'filters': {
                'date': date.strftime('%Y-%m-%d'),
                'severity': severity,
                'limit': limit
            }
        })

    except (ValidationError, ValueError, TypeError) as e:
        logger.error(f"Error fetching slow queries: {e}")
        return JsonResponse({
            'status': 'error',
            'message': 'Failed to fetch slow queries'
        }, status=500)


@login_required
@user_passes_test(is_admin_or_staff)
@require_http_methods(["GET"])
@cache_page(300)  # Cache for 5 minutes
def spatial_performance_metrics(request: HttpRequest) -> JsonResponse:
    """
    Get detailed performance metrics.

    Query Parameters:
        date (optional): Date in YYYY-MM-DD format (default: today)

    Returns:
        JsonResponse with detailed metrics by query type

    Example Response:
        {
            "status": "success",
            "data": {
                "total_queries": 1523,
                "total_time_ms": 64725.3,
                "avg_time_ms": 42.5,
                "queries_by_type": {
                    "geofence_check": {
                        "count": 845,
                        "avg_time_ms": 38.2,
                        "min_time_ms": 5.1,
                        "max_time_ms": 752.3
                    }
                }
            }
        }
    """
    try:
        # Parse date parameter
        date_str = request.GET.get('date')
        if date_str:
            try:
                date = datetime.strptime(date_str, '%Y-%m-%d')
            except ValueError:
                return JsonResponse({
                    'status': 'error',
                    'message': 'Invalid date format. Use YYYY-MM-DD'
                }, status=400)
        else:
            date = datetime.now()

        # Get metrics
        metrics = spatial_query_monitor.get_performance_metrics(date=date)

        return JsonResponse({
            'status': 'success',
            'data': metrics,
            'date': date.strftime('%Y-%m-%d')
        })

    except (ValidationError, ValueError, TypeError) as e:
        logger.error(f"Error fetching performance metrics: {e}")
        return JsonResponse({
            'status': 'error',
            'message': 'Failed to fetch performance metrics'
        }, status=500)


@login_required
@user_passes_test(is_admin_or_staff)
@require_http_methods(["GET"])
def spatial_performance_health(request: HttpRequest) -> JsonResponse:
    """
    Get health status of spatial query performance.

    Simple endpoint for health monitoring and alerting systems.

    Returns:
        JsonResponse with health status

    Example Response:
        {
            "status": "success",
            "health": "HEALTHY",
            "checks": {
                "avg_query_time_ok": true,
                "slow_query_rate_ok": true,
                "critical_queries_ok": true
            }
        }
    """
    try:
        summary = spatial_query_monitor.get_dashboard_summary()
        health_status = summary['health_status']

        # Detailed health checks
        avg_time_ms = summary.get('avg_query_time_ms', 0)
        total_queries = summary.get('total_queries_today', 0)
        slow_queries = summary.get('slow_queries_count', 0)
        critical_count = summary.get('slow_queries_by_severity', {}).get('CRITICAL', 0)

        health_checks = {
            'avg_query_time_ok': avg_time_ms < 500,
            'slow_query_rate_ok': (
                slow_queries / total_queries < 0.1 if total_queries > 0 else True
            ),
            'critical_queries_ok': critical_count < 5
        }

        return JsonResponse({
            'status': 'success',
            'health': health_status,
            'checks': health_checks,
            'metrics': {
                'avg_query_time_ms': avg_time_ms,
                'total_queries': total_queries,
                'slow_queries': slow_queries,
                'critical_queries': critical_count
            }
        })

    except (ValidationError, ValueError, TypeError) as e:
        logger.error(f"Error checking health status: {e}")
        return JsonResponse({
            'status': 'error',
            'message': 'Failed to check health status'
        }, status=500)