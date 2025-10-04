"""
URL Configuration for Spatial Performance Dashboard

Routes for monitoring spatial query performance and viewing metrics.

Following .claude/rules.md:
- Rule #7: Keep URL patterns organized and documented
"""

from django.urls import path
from apps.core.views.spatial_performance_dashboard import (
    spatial_performance_dashboard,
    spatial_slow_queries,
    spatial_performance_metrics,
    spatial_performance_health,
)

app_name = 'spatial_performance'

urlpatterns = [
    # Dashboard summary endpoint
    path(
        'dashboard/',
        spatial_performance_dashboard,
        name='dashboard'
    ),

    # Slow queries list
    path(
        'slow-queries/',
        spatial_slow_queries,
        name='slow_queries'
    ),

    # Detailed metrics
    path(
        'metrics/',
        spatial_performance_metrics,
        name='metrics'
    ),

    # Health check endpoint
    path(
        'health/',
        spatial_performance_health,
        name='health'
    ),
]