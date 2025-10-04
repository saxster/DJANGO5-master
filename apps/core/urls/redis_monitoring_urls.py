"""
URL patterns for Redis monitoring and performance dashboard.

Provides URL routing for Redis performance monitoring views,
health checks, and administrative operations.
"""

from django.urls import path
from apps.core.views.redis_performance_dashboard import (
    redis_performance_dashboard,
    redis_metrics_api,
    redis_trends_api,
    redis_memory_optimization,
    redis_health_check_api
)

app_name = 'redis_monitoring'

urlpatterns = [
    # Main dashboard
    path(
        'dashboard/',
        redis_performance_dashboard,
        name='redis_performance_dashboard'
    ),

    # API endpoints for real-time data
    path(
        'api/metrics/',
        redis_metrics_api,
        name='redis_metrics_api'
    ),

    path(
        'api/trends/',
        redis_trends_api,
        name='redis_trends_api'
    ),

    path(
        'api/health/',
        redis_health_check_api,
        name='redis_health_check_api'
    ),

    # Memory optimization endpoint
    path(
        'api/memory/optimize/',
        redis_memory_optimization,
        name='redis_memory_optimization'
    ),
]

# Admin integration URL patterns
admin_urlpatterns = [
    # Redis performance dashboard in admin
    path(
        'redis/performance/',
        redis_performance_dashboard,
        name='redis_performance_dashboard'
    ),

    # API endpoints with admin namespace
    path(
        'redis/api/metrics/',
        redis_metrics_api,
        name='redis_metrics_api'
    ),

    path(
        'redis/api/trends/',
        redis_trends_api,
        name='redis_trends_api'
    ),

    path(
        'redis/api/health/',
        redis_health_check_api,
        name='redis_health_check_api'
    ),

    path(
        'redis/api/memory/optimize/',
        redis_memory_optimization,
        name='redis_memory_optimization'
    ),
]