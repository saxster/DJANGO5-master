"""
Command Center URL Configuration
=================================
Routes for the new Command Center (Portfolio & Site dashboards).

Phase 1 (Oct 2025):
- Portfolio Command Center (multi-site view)
- Enhanced Site Operations Dashboard
- Unified navigation

Following .claude/rules.md patterns for clean URL structure.
"""

from django.urls import path
from apps.core.views.portfolio_command_center_view import PortfolioCommandCenterView

app_name = "core"

urlpatterns = [
    # Portfolio Command Center (Zoom Level 1)
    path(
        "command-center/portfolio/",
        PortfolioCommandCenterView.as_view(),
        name="portfolio_command_center"
    ),

    # Site Operations Dashboard will be added here
    # path(
    #     "command-center/site/<int:bu_id>/",
    #     SiteOperationsDashboardView.as_view(),
    #     name="site_operations_dashboard"
    # ),
]
