"""
WebSocket Monitoring Views

Provides detailed WebSocket connection and throttling metrics.

Endpoints:
- /monitoring/websocket/ - WebSocket metrics overview
- /monitoring/websocket/connections/ - Active connections details
- /monitoring/websocket/rejections/ - Rejection analysis

Compliance: .claude/rules.md Rule #8 (View methods < 30 lines)
Security: API key authentication required
"""

import logging
from datetime import datetime
from django.http import JsonResponse
from django.views import View
from django.utils.decorators import method_decorator
from apps.core.decorators import require_monitoring_api_key
from apps.core.constants.datetime_constants import MINUTES_IN_HOUR, MINUTES_IN_DAY
from monitoring.services.websocket_metrics_collector import websocket_metrics
from monitoring.services.pii_redaction_service import MonitoringPIIRedactionService

logger = logging.getLogger('monitoring.websocket')

__all__ = ['WebSocketMonitoringView', 'WebSocketConnectionsView', 'WebSocketRejectionsView']


@method_decorator(require_monitoring_api_key, name='dispatch')
class WebSocketMonitoringView(View):
    """
    Overview of WebSocket metrics.

    Security: Requires monitoring API key authentication.
    """

    def get(self, request):
        """Return WebSocket metrics overview"""
        window_minutes = int(request.GET.get('window', MINUTES_IN_HOUR))

        # Get WebSocket statistics
        stats = websocket_metrics.get_websocket_stats(window_minutes)

        # Generate recommendations
        recommendations = self._generate_recommendations(stats)

        response_data = {
            'timestamp': datetime.now().isoformat(),
            'window_minutes': window_minutes,
            'statistics': stats,
            'recommendations': recommendations,
            'correlation_id': getattr(request, 'correlation_id', None)
        }

        # Sanitize for PII
        sanitized_data = MonitoringPIIRedactionService.sanitize_dashboard_data(response_data)

        return JsonResponse(sanitized_data)

    def _generate_recommendations(self, stats):
        """Generate WebSocket optimization recommendations"""
        recommendations = []

        rejection_rate = stats.get('rejection_rate', 0)
        if rejection_rate > 15:
            recommendations.append({
                'level': 'warning',
                'message': f'High WebSocket rejection rate: {rejection_rate:.1f}%',
                'action': 'Review throttle limits or investigate potential attack'
            })

        total_active = stats.get('total_active', 0)
        if total_active > 1000:
            recommendations.append({
                'level': 'info',
                'message': f'High number of active connections: {total_active}',
                'action': 'Monitor server resources and consider horizontal scaling'
            })

        avg_duration = stats.get('connection_duration', {}).get('mean', 0)
        if avg_duration < 5:
            recommendations.append({
                'level': 'info',
                'message': f'Short average connection duration: {avg_duration:.1f}s',
                'action': 'Investigate why connections are closing quickly'
            })

        return recommendations


@method_decorator(require_monitoring_api_key, name='dispatch')
class WebSocketConnectionsView(View):
    """
    Detailed active connections metrics.

    Security: Requires monitoring API key authentication.
    """

    def get(self, request):
        """Return active connections details"""
        window_minutes = int(request.GET.get('window', MINUTES_IN_HOUR))

        stats = websocket_metrics.get_websocket_stats(window_minutes)

        # Calculate connection limits
        from django.conf import settings
        throttle_limits = getattr(settings, 'WEBSOCKET_THROTTLE_LIMITS', {
            'anonymous': 5,
            'authenticated': 20,
            'staff': 100,
        })

        # Calculate utilization
        active_connections = stats.get('active_connections', {})
        utilization = {}
        for user_type, count in active_connections.items():
            limit = throttle_limits.get(user_type, 0)
            utilization[user_type] = {
                'active': count,
                'limit': limit,
                'utilization_percent': (count / limit * 100) if limit > 0 else 0
            }

        response_data = {
            'timestamp': datetime.now().isoformat(),
            'window_minutes': window_minutes,
            'active_connections': active_connections,
            'total_active': stats.get('total_active', 0),
            'utilization': utilization,
            'connection_duration': stats.get('connection_duration', {}),
            'correlation_id': getattr(request, 'correlation_id', None)
        }

        sanitized_data = MonitoringPIIRedactionService.sanitize_dashboard_data(response_data)

        return JsonResponse(sanitized_data)


@method_decorator(require_monitoring_api_key, name='dispatch')
class WebSocketRejectionsView(View):
    """
    Detailed rejection analysis and patterns.

    Security: Requires monitoring API key authentication.
    """

    def get(self, request):
        """Return rejection analysis"""
        window_minutes = int(request.GET.get('window', MINUTES_IN_HOUR))

        stats = websocket_metrics.get_websocket_stats(window_minutes)

        response_data = {
            'timestamp': datetime.now().isoformat(),
            'window_minutes': window_minutes,
            'rejection_summary': {
                'total_rejections': stats.get('total_rejections', 0),
                'rejection_rate': stats.get('rejection_rate', 0),
                'top_reasons': stats.get('top_rejection_reasons', {}),
            },
            'top_rejected_ips': stats.get('top_rejected_ips', []),
            'top_rejected_users': stats.get('top_rejected_users', []),
            'recommendations': self._generate_rejection_recommendations(stats),
            'correlation_id': getattr(request, 'correlation_id', None)
        }

        sanitized_data = MonitoringPIIRedactionService.sanitize_dashboard_data(response_data)

        return JsonResponse(sanitized_data)

    def _generate_rejection_recommendations(self, stats):
        """Generate recommendations based on rejection patterns"""
        recommendations = []

        top_reasons = stats.get('top_rejection_reasons', {})

        if 'rate_limit' in top_reasons and top_reasons['rate_limit'] > 50:
            recommendations.append({
                'level': 'warning',
                'message': 'High rate limit rejections detected',
                'action': 'Possible connection flood attack - review top rejected IPs'
            })

        top_rejected_ips = stats.get('top_rejected_ips', [])
        if top_rejected_ips and top_rejected_ips[0].get('count', 0) > 100:
            recommendations.append({
                'level': 'critical',
                'message': f'IP {top_rejected_ips[0]["ip"]} rejected {top_rejected_ips[0]["count"]} times',
                'action': 'Consider blocking this IP at firewall level'
            })

        return recommendations
