"""
Query Performance Dashboard

Real-time monitoring dashboard for:
- Slow queries per view
- Cache hit/miss ratios
- SQL security violations
- Middleware performance metrics

Features:
- Admin-only access
- Real-time metrics from Redis
- Interactive charts (Chart.js integration)
- CSV export functionality
- Alerting integration

Author: Claude Code
Date: 2025-10-01
"""

import json
import time
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional

from django.contrib.admin.views.decorators import staff_member_required
from django.http import JsonResponse, HttpResponse, HttpRequest
from django.shortcuts import render
from django.core.cache import cache
from django.db import connection
from django.utils import timezone
from django.conf import settings

from apps.core.constants.datetime_constants import SECONDS_IN_HOUR, SECONDS_IN_DAY
from apps.core.exceptions.patterns import NETWORK_EXCEPTIONS



@staff_member_required
def query_performance_dashboard(request: HttpRequest) -> HttpResponse:
    """
    Main query performance dashboard view.

    Displays:
    - Slow queries (> 100ms) in last 24 hours
    - Cache performance metrics
    - SQL security violation trends
    - Per-view performance breakdown
    """
    context = {
        'slow_queries': get_slow_queries(hours=24, limit=50),
        'cache_metrics': get_cache_performance_metrics(),
        'sql_security_metrics': get_sql_security_metrics(),
        'view_performance': get_view_performance_breakdown(),
        'middleware_overhead': get_middleware_overhead_metrics(),
        'timestamp': timezone.now(),
    }

    return render(request, 'admin/query_performance_dashboard.html', context)


@staff_member_required
def query_performance_api(request: HttpRequest) -> JsonResponse:
    """
    API endpoint for real-time metrics (AJAX polling).

    Returns JSON with current performance metrics.
    """
    hours = int(request.GET.get('hours', 1))
    limit = int(request.GET.get('limit', 50))

    data = {
        'slow_queries': get_slow_queries(hours=hours, limit=limit),
        'cache_metrics': get_cache_performance_metrics(),
        'sql_security_metrics': get_sql_security_metrics(),
        'timestamp': timezone.now().isoformat(),
    }

    return JsonResponse(data, safe=False)


@staff_member_required
def export_slow_queries_csv(request: HttpRequest) -> HttpResponse:
    """
    Export slow queries to CSV format.
    """
    import csv
    from io import StringIO

    hours = int(request.GET.get('hours', 24))
    queries = get_slow_queries(hours=hours, limit=1000)

    output = StringIO()
    writer = csv.writer(output)

    # Write header
    writer.writerow([
        'Timestamp',
        'View Name',
        'Query',
        'Duration (ms)',
        'Request Path',
        'User ID'
    ])

    # Write data
    for query in queries:
        writer.writerow([
            query.get('timestamp', ''),
            query.get('view_name', ''),
            query.get('sql', '')[:200],  # Truncate long queries
            query.get('duration_ms', 0),
            query.get('path', ''),
            query.get('user_id', 'anonymous')
        ])

    response = HttpResponse(output.getvalue(), content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="slow_queries_{timezone.now().date()}.csv"'

    return response


def get_slow_queries(hours: int = 24, limit: int = 50) -> List[Dict[str, Any]]:
    """
    Retrieve slow queries from cache (populated by QueryPerformanceMonitoringMiddleware).

    Args:
        hours: Number of hours to look back
        limit: Maximum number of queries to return

    Returns:
        List of slow query dictionaries
    """
    slow_queries = []

    # Query performance data is stored in Redis with hourly keys
    current_hour = int(time.time() // SECONDS_IN_HOUR)

    for hour_offset in range(hours):
        hour_key = current_hour - hour_offset
        cache_key = f"query_performance:slow:{hour_key}"

        queries_in_hour = cache.get(cache_key, [])
        slow_queries.extend(queries_in_hour)

    # Sort by duration (slowest first)
    slow_queries.sort(key=lambda q: q.get('duration_ms', 0), reverse=True)

    return slow_queries[:limit]


def get_cache_performance_metrics() -> Dict[str, Any]:
    """
    Calculate cache performance metrics.

    Returns:
        Dictionary with hit rates, miss counts, and performance stats
    """
    metrics = {
        'hit_rate': 0.0,
        'total_hits': 0,
        'total_misses': 0,
        'avg_get_time_ms': 0.0,
        'prefixes': {}
    }

    # Get cache stats from Redis (if available)
    cache_stats_key = 'cache_stats:current_hour'
    stats = cache.get(cache_stats_key, {})

    if stats:
        total_requests = stats.get('hits', 0) + stats.get('misses', 0)
        if total_requests > 0:
            metrics['hit_rate'] = (stats.get('hits', 0) / total_requests) * 100
        metrics['total_hits'] = stats.get('hits', 0)
        metrics['total_misses'] = stats.get('misses', 0)
        metrics['avg_get_time_ms'] = stats.get('avg_get_time_ms', 0.0)

    # Get per-prefix stats
    for prefix in ['cap', 'bt', 'rpt', 'usr', 'ast']:
        prefix_key = f"cache_stats:prefix:{prefix}"
        prefix_stats = cache.get(prefix_key, {})

        if prefix_stats:
            prefix_total = prefix_stats.get('hits', 0) + prefix_stats.get('misses', 0)
            prefix_hit_rate = 0.0
            if prefix_total > 0:
                prefix_hit_rate = (prefix_stats.get('hits', 0) / prefix_total) * 100

            metrics['prefixes'][prefix] = {
                'hit_rate': prefix_hit_rate,
                'hits': prefix_stats.get('hits', 0),
                'misses': prefix_stats.get('misses', 0)
            }

    return metrics


def get_sql_security_metrics() -> Dict[str, Any]:
    """
    Get SQL security violation metrics.

    Returns:
        Dictionary with violation counts, top attacking IPs, and patterns
    """
    metrics = {
        'total_violations_24h': 0,
        'violations_by_pattern': {},
        'top_attacking_ips': [],
        'blocked_requests_per_hour': []
    }

    # Get violations from last 24 hours
    current_hour = int(time.time() // SECONDS_IN_HOUR)

    total_violations = 0
    pattern_counts = {}

    for hour_offset in range(24):
        hour_key = current_hour - hour_offset
        cache_key = f"sql_security:violations:{hour_key}"

        violations = cache.get(cache_key, [])
        total_violations += len(violations)

        # Count patterns
        for violation in violations:
            pattern = violation.get('pattern_matched', 'unknown')
            pattern_counts[pattern] = pattern_counts.get(pattern, 0) + 1

    metrics['total_violations_24h'] = total_violations
    metrics['violations_by_pattern'] = pattern_counts

    # Get top attacking IPs
    ip_violations_key = 'sql_security:top_ips:24h'
    top_ips = cache.get(ip_violations_key, {})

    # Sort by violation count
    sorted_ips = sorted(top_ips.items(), key=lambda x: x[1], reverse=True)[:10]
    metrics['top_attacking_ips'] = [
        {'ip': ip, 'count': count} for ip, count in sorted_ips
    ]

    return metrics


def get_view_performance_breakdown() -> List[Dict[str, Any]]:
    """
    Get performance breakdown per view.

    Returns:
        List of views with average response times and query counts
    """
    breakdown = []

    # Get view performance data from cache
    view_stats_key = 'view_performance:24h'
    view_stats = cache.get(view_stats_key, {})

    for view_name, stats in view_stats.items():
        breakdown.append({
            'view_name': view_name,
            'avg_response_time_ms': stats.get('avg_response_time_ms', 0),
            'p95_response_time_ms': stats.get('p95_response_time_ms', 0),
            'p99_response_time_ms': stats.get('p99_response_time_ms', 0),
            'request_count': stats.get('request_count', 0),
            'avg_query_count': stats.get('avg_query_count', 0),
            'error_count': stats.get('error_count', 0)
        })

    # Sort by p95 response time (slowest first)
    breakdown.sort(key=lambda v: v['p95_response_time_ms'], reverse=True)

    return breakdown[:20]  # Top 20 slowest views


def get_middleware_overhead_metrics() -> Dict[str, Any]:
    """
    Calculate total middleware overhead.

    Returns:
        Dictionary with middleware timing breakdown
    """
    metrics = {
        'total_overhead_ms': 0.0,
        'middleware_breakdown': []
    }

    # Get middleware timing data
    middleware_stats_key = 'middleware_performance:current_hour'
    middleware_stats = cache.get(middleware_stats_key, {})

    total_overhead = 0.0
    breakdown = []

    for middleware_name, timing in middleware_stats.items():
        avg_time = timing.get('avg_time_ms', 0.0)
        total_overhead += avg_time

        breakdown.append({
            'name': middleware_name.split('.')[-1],  # Short name
            'avg_time_ms': avg_time,
            'max_time_ms': timing.get('max_time_ms', 0.0),
            'call_count': timing.get('call_count', 0)
        })

    # Sort by average time (slowest first)
    breakdown.sort(key=lambda m: m['avg_time_ms'], reverse=True)

    metrics['total_overhead_ms'] = total_overhead
    metrics['middleware_breakdown'] = breakdown

    return metrics


@staff_member_required
def database_query_stats(request: HttpRequest) -> JsonResponse:
    """
    Get real-time database query statistics.

    Uses Django's connection.queries in DEBUG mode,
    or pg_stat_statements in production.
    """
    stats = {
        'query_count': 0,
        'total_time_ms': 0.0,
        'slowest_queries': []
    }

    if settings.DEBUG:
        # DEBUG mode - use connection.queries
        queries = connection.queries
        stats['query_count'] = len(queries)
        stats['total_time_ms'] = sum(float(q.get('time', 0)) * 1000 for q in queries)

        # Get slowest queries
        sorted_queries = sorted(
            queries,
            key=lambda q: float(q.get('time', 0)),
            reverse=True
        )[:10]

        stats['slowest_queries'] = [
            {
                'sql': q['sql'][:200],  # Truncate
                'time_ms': float(q['time']) * 1000
            }
            for q in sorted_queries
        ]

    else:
        # Production - use pg_stat_statements if available
        try:
            with connection.cursor() as cursor:
                cursor.execute("""
                    SELECT
                        calls,
                        total_exec_time,
                        mean_exec_time,
                        query
                    FROM pg_stat_statements
                    WHERE query NOT LIKE '%pg_stat_statements%'
                    ORDER BY mean_exec_time DESC
                    LIMIT 10
                """)

                rows = cursor.fetchall()
                stats['query_count'] = sum(row[0] for row in rows)
                stats['total_time_ms'] = sum(row[1] for row in rows)

                stats['slowest_queries'] = [
                    {
                        'sql': row[3][:200],
                        'time_ms': row[2],
                        'call_count': row[0]
                    }
                    for row in rows
                ]
        except NETWORK_EXCEPTIONS as e:
            stats['error'] = f"pg_stat_statements not available: {e}"

    return JsonResponse(stats)


def record_slow_query(
    sql: str,
    duration_ms: float,
    view_name: str,
    path: str,
    user_id: Optional[int] = None
):
    """
    Record a slow query for dashboard display.

    Called by QueryPerformanceMonitoringMiddleware.

    Args:
        sql: SQL query text
        duration_ms: Query duration in milliseconds
        view_name: Django view name
        path: Request path
        user_id: User ID if authenticated
    """
    current_hour = int(time.time() // SECONDS_IN_HOUR)
    cache_key = f"query_performance:slow:{current_hour}"

    # Get existing slow queries
    slow_queries = cache.get(cache_key, [])

    # Add new query
    slow_queries.append({
        'timestamp': timezone.now().isoformat(),
        'sql': sql[:500],  # Truncate long queries
        'duration_ms': duration_ms,
        'view_name': view_name,
        'path': path,
        'user_id': user_id or 'anonymous'
    })

    # Keep last 100 queries per hour
    slow_queries = slow_queries[-100:]

    # Store with 2-hour expiry
    cache.set(cache_key, slow_queries, SECONDS_IN_HOUR * 2)


def record_cache_hit(cache_key: str, hit: bool, get_time_ms: float):
    """
    Record cache hit/miss for metrics.

    Args:
        cache_key: Cache key accessed
        hit: True if cache hit, False if miss
        get_time_ms: Time taken to get from cache
    """
    stats_key = 'cache_stats:current_hour'
    stats = cache.get(stats_key, {'hits': 0, 'misses': 0, 'total_time': 0.0, 'count': 0})

    if hit:
        stats['hits'] += 1
    else:
        stats['misses'] += 1

    stats['total_time'] += get_time_ms
    stats['count'] += 1
    stats['avg_get_time_ms'] = stats['total_time'] / stats['count']

    # Store with 2-hour expiry
    cache.set(stats_key, stats, SECONDS_IN_HOUR * 2)

    # Record per-prefix stats
    prefix = cache_key.split(':')[0] if ':' in cache_key else 'unknown'
    prefix_key = f"cache_stats:prefix:{prefix}"
    prefix_stats = cache.get(prefix_key, {'hits': 0, 'misses': 0})

    if hit:
        prefix_stats['hits'] += 1
    else:
        prefix_stats['misses'] += 1

    cache.set(prefix_key, prefix_stats, SECONDS_IN_HOUR * 2)
