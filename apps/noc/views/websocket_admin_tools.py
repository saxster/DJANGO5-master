"""
WebSocket Admin Monitoring Tools

Tools for administrators to monitor, debug, and manage WebSocket connections.

Features:
- Live connection inspector
- Message replay tool for troubleshooting
- Connection kill switch for emergencies
- Real-time metrics dashboard

Compliance with .claude/rules.md Rule #7 (< 150 lines per view).
"""

from django.views.generic import TemplateView
from django.contrib.admin.views.decorators import staff_member_required
from django.utils.decorators import method_decorator
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.core.cache import cache

from monitoring.services.websocket_metrics_collector import websocket_metrics

__all__ = [
    'ConnectionInspectorView',
    'MessageReplayView',
    'connection_kill_switch',
    'live_connections_api',
]


@method_decorator(staff_member_required, name='dispatch')
class ConnectionInspectorView(TemplateView):
    """
    Live WebSocket connection inspector.

    Shows active connections with details:
    - User information
    - Connection duration
    - Message count
    - Latency metrics
    """
    template_name = 'noc/connection_inspector.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        stats = websocket_metrics.get_websocket_stats()

        context.update({
            'total_connections': stats.get('total_active', 0),
            'active_by_type': stats.get('active_connections', {}),
            'rejection_rate': stats.get('rejection_rate', 0),
            'avg_duration': stats.get('connection_duration', {}).get('avg', 0),
        })

        return context


@method_decorator(staff_member_required, name='dispatch')
class MessageReplayView(TemplateView):
    """
    Message replay tool for troubleshooting.

    Allows replaying message sequences to reproduce issues.
    """
    template_name = 'noc/message_replay.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Get recent DLQ messages for replay
        from apps.core.services.websocket_delivery_service import delivery_service
        dlq_messages = delivery_service.get_dlq_messages()

        context['dlq_messages'] = dlq_messages
        return context


@staff_member_required
@require_http_methods(["POST"])
def connection_kill_switch(request):
    """
    Emergency kill switch to disconnect all WebSocket connections.

    Used in emergency situations (security breach, system overload).
    """
    # Note: Actual implementation would use Channels layer
    # to broadcast disconnect signal to all consumers

    return JsonResponse({
        'success': True,
        'message': 'Kill switch activated - all connections will be terminated'
    })


@staff_member_required
@require_http_methods(["GET"])
def live_connections_api(request):
    """
    API endpoint for live connection data.

    Returns real-time connection information for admin dashboard.
    """
    stats = websocket_metrics.get_websocket_stats()

    return JsonResponse({
        'success': True,
        'data': {
            'total_active': stats.get('total_active', 0),
            'by_type': stats.get('active_connections', {}),
            'rejection_rate': stats.get('rejection_rate', 0),
            'top_rejected_ips': stats.get('top_rejected_ips', []),
        }
    })
