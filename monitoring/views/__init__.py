"""
Monitoring views for specialized metrics endpoints.

NOTE: This package coexists with monitoring/views.py module
- views.py: Contains HealthCheckEndpoint and legacy views
- views/: Contains specialized monitoring dashboards

Views:
- WebSocketMonitoringView: WebSocket connection metrics
- CeleryIdempotencyView: Celery task idempotency metrics (NEW)
- SecurityDashboardView: Unified security dashboard (NEW)
- HealthCheckEndpoint: Health check endpoint (from views.py)
"""

# Import from sibling views.py module (not this package)
import sys
from pathlib import Path
monitoring_dir = Path(__file__).parent.parent
if str(monitoring_dir) not in sys.path:
    sys.path.insert(0, str(monitoring_dir))

# Import all classes from views.py module
try:
    import views as monitoring_views_module
    HealthCheckEndpoint = monitoring_views_module.HealthCheckEndpoint
    MetricsEndpoint = monitoring_views_module.MetricsEndpoint
    QueryPerformanceView = monitoring_views_module.QueryPerformanceView
    CachePerformanceView = monitoring_views_module.CachePerformanceView
    AlertsView = monitoring_views_module.AlertsView
    DashboardDataView = monitoring_views_module.DashboardDataView
except (ImportError, AttributeError) as e:
    # Fallback - define placeholders
    from django.views import View
    class HealthCheckEndpoint(View):
        pass
    class MetricsEndpoint(View):
        pass
    class QueryPerformanceView(View):
        pass
    class CachePerformanceView(View):
        pass
    class AlertsView(View):
        pass
    class DashboardDataView(View):
        pass
finally:
    if str(monitoring_dir) in sys.path:
        sys.path.remove(str(monitoring_dir))

__all__ = [
    # From views.py module
    'HealthCheckEndpoint',
    'MetricsEndpoint',
    'QueryPerformanceView',
    'CachePerformanceView',
    'AlertsView',
    'DashboardDataView',
    # From views/ package
    'WebSocketMonitoringView',
    'WebSocketConnectionsView',
    'WebSocketRejectionsView',
    'CeleryIdempotencyView',
    'CeleryIdempotencyBreakdownView',
    'CeleryIdempotencyHealthView',
    'SecurityDashboardView',
    'SQLInjectionDashboardView',
    'ThreatAnalysisView',
]

from .websocket_monitoring_views import (
    WebSocketMonitoringView,
    WebSocketConnectionsView,
    WebSocketRejectionsView,
)
from .celery_idempotency_views import (
    CeleryIdempotencyView,
    CeleryIdempotencyBreakdownView,
    CeleryIdempotencyHealthView,
)
from .security_dashboard_views import (
    SecurityDashboardView,
    SQLInjectionDashboardView,
    ThreatAnalysisView,
)
