"""
Core Registry Package

Central registry system for application components including:
- Dashboard registry (single source of truth for all dashboards)
- Future: API endpoint registry
- Future: Report registry
- Future: Background task registry

Usage:
    from apps.core.registry import dashboard_registry

    # Get all dashboards for user
    dashboards = dashboard_registry.get_dashboards_for_user(request.user)

    # Get dashboards by category
    security_dashboards = dashboard_registry.get_by_category('security')
"""

from .dashboard_registry import (
    Dashboard,
    DashboardRegistry,
    dashboard_registry,
    register_core_dashboards
)

__all__ = [
    'Dashboard',
    'DashboardRegistry',
    'dashboard_registry',
    'register_core_dashboards'
]
