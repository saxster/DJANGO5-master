"""
Search Monitoring Module

Provides Prometheus metrics collection and dashboard export for search performance.

Components:
- MetricsCollector: Aggregates search performance metrics
- DashboardExporter: Exports metrics for Grafana dashboards

Compliance with .claude/rules.md:
- Rule #5: Single Responsibility Principle
- Rule #7: Module < 150 lines per class
- Rule #11: Specific exception handling
"""

__all__ = [
    'SearchMetricsCollector',
    'SearchDashboardExporter',
]

from apps.search.monitoring.metrics_collector import SearchMetricsCollector
from apps.search.monitoring.dashboard_exporter import SearchDashboardExporter
