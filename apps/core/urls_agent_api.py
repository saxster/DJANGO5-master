"""
Agent Intelligence API URL Configuration
========================================
REST API endpoints for dashboard agent recommendations.

Dashboard Agent Intelligence - Phase 4
"""

from django.urls import path
from apps.core.views.dashboard_agent_api import (
    DashboardAgentInsightsView,
    AgentStatusView
)

app_name = "agent_api"

urlpatterns = [
    # Agent recommendations endpoint
    path(
        "agent-insights/",
        DashboardAgentInsightsView.as_view(),
        name="agent_insights"
    ),

    # Agent status and activity feed
    path(
        "agent-status/",
        AgentStatusView.as_view(),
        name="agent_status"
    ),
]
