"""
Analytics Dashboard URL Configuration

URL patterns for advanced analytics dashboard endpoints.

Author: Claude Code
Date: 2025-10-01
"""

from django.urls import path
from apps.onboarding_api.views.analytics_dashboard_views import (
    DashboardOverviewView,
    DropOffHeatmapView,
    SessionReplayView,
    CohortTrendsView,
)

app_name = 'analytics_dashboard'

urlpatterns = [
    # Dashboard overview
    path(
        'overview/',
        DashboardOverviewView.as_view(),
        name='dashboard-overview'
    ),

    # Visualization data
    path(
        'heatmap/',
        DropOffHeatmapView.as_view(),
        name='drop-off-heatmap'
    ),

    # Session analysis
    path(
        'session-replay/<uuid:session_id>/',
        SessionReplayView.as_view(),
        name='session-replay'
    ),

    # Trend analysis
    path(
        'cohort-trends/',
        CohortTrendsView.as_view(),
        name='cohort-trends'
    ),
]

# API Endpoint Documentation
"""
Analytics Dashboard API Endpoints:

1. GET /api/v1/onboarding/dashboard/overview/
   - Comprehensive dashboard with all key metrics
   - Query params: client_id, time_range_hours
   - Permissions: IsAuthenticated, IsAdminUser

2. GET /api/v1/onboarding/dashboard/heatmap/
   - Drop-off heatmap visualization data
   - Query params: start_date, end_date, granularity
   - Permissions: IsAuthenticated, IsAdminUser

3. GET /api/v1/onboarding/dashboard/session-replay/{session_id}/
   - Complete session timeline for analysis
   - Includes all events, checkpoints, Q&A
   - Permissions: IsAuthenticated

4. GET /api/v1/onboarding/dashboard/cohort-trends/
   - Cohort trend analysis over time
   - Query params: start_date, end_date, cohort_type
   - Permissions: IsAuthenticated, IsAdminUser

Example Usage:
--------------

# Get dashboard overview (last 24 hours)
GET /api/v1/onboarding/dashboard/overview/?time_range_hours=24

# Get drop-off heatmap (daily granularity, last 7 days)
GET /api/v1/onboarding/dashboard/heatmap/?granularity=daily

# Get session replay for specific session
GET /api/v1/onboarding/dashboard/session-replay/550e8400-e29b-41d4-a716-446655440000/

# Get weekly cohort trends (last 30 days)
GET /api/v1/onboarding/dashboard/cohort-trends/?cohort_type=weekly
"""
