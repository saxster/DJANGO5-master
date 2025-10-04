"""
Monitoring views for specialized metrics endpoints.

Views:
- GraphQLMonitoringView: GraphQL-specific metrics
- GraphQLMutationView: GraphQL mutation analytics (NEW)
- WebSocketMonitoringView: WebSocket connection metrics
- CeleryIdempotencyView: Celery task idempotency metrics (NEW)
- SecurityDashboardView: Unified security dashboard (NEW)
"""

__all__ = [
    'GraphQLMonitoringView',
    'GraphQLComplexityView',
    'GraphQLRejectionsView',
    'WebSocketMonitoringView',
    'WebSocketConnectionsView',
    'WebSocketRejectionsView',
    'GraphQLMutationView',
    'GraphQLMutationBreakdownView',
    'GraphQLMutationPerformanceView',
    'CeleryIdempotencyView',
    'CeleryIdempotencyBreakdownView',
    'CeleryIdempotencyHealthView',
    'SecurityDashboardView',
    'SQLInjectionDashboardView',
    'GraphQLSecurityDashboardView',
    'ThreatAnalysisView',
]

from .graphql_monitoring_views import (
    GraphQLMonitoringView,
    GraphQLComplexityView,
    GraphQLRejectionsView,
)
from .websocket_monitoring_views import (
    WebSocketMonitoringView,
    WebSocketConnectionsView,
    WebSocketRejectionsView,
)
from .graphql_mutation_views import (
    GraphQLMutationView,
    GraphQLMutationBreakdownView,
    GraphQLMutationPerformanceView,
)
from .celery_idempotency_views import (
    CeleryIdempotencyView,
    CeleryIdempotencyBreakdownView,
    CeleryIdempotencyHealthView,
)
from .security_dashboard_views import (
    SecurityDashboardView,
    SQLInjectionDashboardView,
    GraphQLSecurityDashboardView,
    ThreatAnalysisView,
)
