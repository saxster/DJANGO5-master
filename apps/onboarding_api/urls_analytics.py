"""
Funnel Analytics URL Configuration

URL patterns for onboarding funnel analytics API endpoints.

Author: Claude Code
Date: 2025-10-01
"""

from django.urls import path
from apps.onboarding_api.views.funnel_analytics_views import (
    FunnelMetricsView,
    DropOffHeatmapView,
    CohortComparisonView,
    OptimizationRecommendationsView,
    RealtimeFunnelDashboardView,
    FunnelComparisonView,
)

app_name = 'onboarding_analytics'

urlpatterns = [
    # Funnel Metrics
    path(
        'funnel/',
        FunnelMetricsView.as_view(),
        name='funnel-metrics'
    ),

    # Drop-off Analysis
    path(
        'drop-off-heatmap/',
        DropOffHeatmapView.as_view(),
        name='drop-off-heatmap'
    ),

    # Cohort Analysis
    path(
        'cohort-comparison/',
        CohortComparisonView.as_view(),
        name='cohort-comparison'
    ),

    # Optimization Recommendations
    path(
        'recommendations/',
        OptimizationRecommendationsView.as_view(),
        name='optimization-recommendations'
    ),

    # Real-time Dashboard
    path(
        'realtime/',
        RealtimeFunnelDashboardView.as_view(),
        name='realtime-dashboard'
    ),

    # Period Comparison
    path(
        'comparison/',
        FunnelComparisonView.as_view(),
        name='funnel-comparison'
    ),
]

# API Endpoint Documentation
"""
Funnel Analytics API Endpoints:

1. GET /api/v1/onboarding/analytics/funnel/
   - Complete funnel metrics with stage breakdown
   - Query params: start_date, end_date, client_id, user_segment
   - Permissions: IsAuthenticated, IsAdminUser

2. GET /api/v1/onboarding/analytics/drop-off-heatmap/
   - Drop-off visualization data
   - Query params: start_date, end_date, client_id
   - Permissions: IsAuthenticated, IsAdminUser

3. GET /api/v1/onboarding/analytics/cohort-comparison/
   - User segment performance comparison
   - Query params: start_date, end_date, client_id
   - Permissions: IsAuthenticated, IsAdminUser

4. GET /api/v1/onboarding/analytics/recommendations/
   - AI-generated optimization suggestions
   - Query params: start_date, end_date, client_id, priority
   - Permissions: IsAuthenticated, IsAdminUser

5. GET /api/v1/onboarding/analytics/realtime/
   - Real-time dashboard metrics (last 24h)
   - Query params: client_id
   - Permissions: IsAuthenticated

6. GET /api/v1/onboarding/analytics/comparison/
   - Compare two time periods
   - Query params: period1_start, period1_end, period2_start, period2_end, client_id
   - Permissions: IsAuthenticated, IsAdminUser

Example Usage:
--------------

# Get last 7 days funnel metrics
GET /api/v1/onboarding/analytics/funnel/?start_date=2025-09-24T00:00:00Z&end_date=2025-10-01T00:00:00Z

# Get drop-off heatmap for specific client
GET /api/v1/onboarding/analytics/drop-off-heatmap/?client_id=123

# Get optimization recommendations (high priority only)
GET /api/v1/onboarding/analytics/recommendations/?priority=high

# Real-time dashboard (cached for 5 minutes)
GET /api/v1/onboarding/analytics/realtime/

# Compare this week vs last week
GET /api/v1/onboarding/analytics/comparison/?period1_start=2025-09-24&period1_end=2025-10-01&period2_start=2025-09-17&period2_end=2025-09-24
"""
