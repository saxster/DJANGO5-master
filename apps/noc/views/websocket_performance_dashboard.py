"""
WebSocket Performance Profiling Dashboard

Real-time WebSocket performance metrics and analytics.

Features:
- Latency tracking (P50, P95, P99)
- Message throughput analysis
- Connection duration percentiles
- Active connections by consumer type
- Error rate monitoring

Compliance with .claude/rules.md Rule #7 (<150 lines per view).
"""

from django.views.generic import TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.utils.decorators import method_decorator

from monitoring.services.websocket_metrics_collector import websocket_metrics
from apps.core.constants.datetime_constants import MINUTES_IN_HOUR

__all__ = ['WebSocketPerformanceDashboardView', 'websocket_metrics_api']


class WebSocketPerformanceDashboardView(LoginRequiredMixin, TemplateView):
    """
    Dashboard view for WebSocket performance metrics.

    Requires staff permissions.
    """
    template_name = 'noc/websocket_performance_dashboard.html'

    def dispatch(self, request, *args, **kwargs):
        """Check staff permissions."""
        if not request.user.is_staff:
            return JsonResponse({'error': 'Staff access required'}, status=403)
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        """Add performance metrics to context."""
        context = super().get_context_data(**kwargs)

        # Get current stats
        stats = websocket_metrics.get_websocket_stats(window_minutes=MINUTES_IN_HOUR)

        context.update({
            'total_active': stats.get('total_active', 0),
            'active_by_type': stats.get('active_connections', {}),
            'rejection_rate': f"{stats.get('rejection_rate', 0):.1f}%",
            'connection_duration_avg': stats.get('connection_duration', {}).get('avg', 0),
            'top_rejection_reasons': stats.get('top_rejection_reasons', {}),
        })

        return context


@require_http_methods(["GET"])
def websocket_metrics_api(request):
    """
    API endpoint for real-time WebSocket metrics.

    Returns JSON with current performance metrics.
    """
    if not request.user.is_staff:
        return JsonResponse({'error': 'Staff access required'}, status=403)

    window_minutes = int(request.GET.get('window', MINUTES_IN_HOUR))
    stats = websocket_metrics.get_websocket_stats(window_minutes=window_minutes)

    return JsonResponse({
        'success': True,
        'data': stats,
        'timestamp': stats.get('timestamp', None)
    })
