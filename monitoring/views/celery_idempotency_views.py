"""
Celery Idempotency Monitoring Views

Provides comprehensive Celery task idempotency analytics including:
- Duplicate detection rate (target: <1%)
- Dedupe savings (tasks prevented from re-execution)
- Breakdown by task type and scope
- Performance metrics

Endpoints:
- /monitoring/celery/idempotency/ - Idempotency overview
- /monitoring/celery/idempotency/breakdown/ - Task breakdown
- /monitoring/celery/idempotency/health/ - Health status

Compliance:
- .claude/rules.md Rule #8 (View methods < 30 lines)
- Rule #3: API key authentication required
- Rule #15: PII sanitization in all responses

Security: API key authentication required for all endpoints
"""

import logging
from datetime import datetime
from django.http import JsonResponse
from django.views import View
from django.utils.decorators import method_decorator
from django.utils import timezone
from apps.core.decorators import require_monitoring_api_key
from monitoring.services.celery_idempotency_collector import celery_idempotency_collector
from monitoring.services.pii_redaction_service import MonitoringPIIRedactionService

logger = logging.getLogger('monitoring.celery_idempotency')

__all__ = [
    'CeleryIdempotencyView',
    'CeleryIdempotencyBreakdownView',
    'CeleryIdempotencyHealthView'
]


@method_decorator(require_monitoring_api_key, name='dispatch')
class CeleryIdempotencyView(View):
    """
    Overview of Celery idempotency metrics.

    Security: Requires monitoring API key (Rule #3 alternative protection).
    Rule #8 compliant: View methods < 30 lines
    """

    def get(self, request):
        """Return Celery idempotency metrics overview"""
        window_hours = int(request.GET.get('window', 24))

        # Get idempotency statistics
        stats = celery_idempotency_collector.get_idempotency_stats(window_hours)

        # Generate recommendations
        recommendations = self._generate_recommendations(stats)

        response_data = {
            'timestamp': timezone.now().isoformat(),
            'window_hours': window_hours,
            'statistics': stats,
            'recommendations': recommendations,
            'correlation_id': getattr(request, 'correlation_id', None)
        }

        # Sanitize for PII (Rule #15 compliance)
        sanitized_data = MonitoringPIIRedactionService.sanitize_dashboard_data(response_data)

        return JsonResponse(sanitized_data)

    def _generate_recommendations(self, stats: dict) -> list:
        """Generate idempotency optimization recommendations (Rule #8: < 30 lines)"""
        recommendations = []

        duplicate_rate = stats.get('duplicate_rate', 0)
        health_status = stats.get('health_status', 'unknown')

        if duplicate_rate > 5:
            recommendations.append({
                'level': 'critical',
                'message': f'High duplicate rate: {duplicate_rate:.1f}% (target: <1%)',
                'action': 'Investigate race conditions or caching issues causing duplicates'
            })
        elif duplicate_rate > 3:
            recommendations.append({
                'level': 'warning',
                'message': f'Elevated duplicate rate: {duplicate_rate:.1f}%',
                'action': 'Monitor for trending increase in duplicate detections'
            })
        elif duplicate_rate < 0.1:
            recommendations.append({
                'level': 'info',
                'message': f'Excellent idempotency: {duplicate_rate:.2f}% duplicate rate',
                'action': 'System operating within optimal parameters'
            })

        return recommendations


@method_decorator(require_monitoring_api_key, name='dispatch')
class CeleryIdempotencyBreakdownView(View):
    """
    Detailed breakdown of idempotency by task type and scope.

    Security: Requires monitoring API key (Rule #3 alternative protection).
    """

    def get(self, request):
        """Return idempotency breakdown analysis"""
        window_hours = int(request.GET.get('window', 24))

        stats = celery_idempotency_collector.get_idempotency_stats(window_hours)

        response_data = {
            'timestamp': timezone.now().isoformat(),
            'window_hours': window_hours,
            'scope_breakdown': stats.get('scope_breakdown', []),
            'top_endpoints': self._format_endpoints(stats.get('top_endpoints', [])),
            'redis_metrics': stats.get('redis_metrics', {}),
            'correlation_id': getattr(request, 'correlation_id', None)
        }

        # Sanitize for PII (Rule #15 compliance)
        sanitized_data = MonitoringPIIRedactionService.sanitize_dashboard_data(response_data)

        return JsonResponse(sanitized_data)

    def _format_endpoints(self, endpoints: list) -> list:
        """Format endpoint data for dashboard (Rule #8: < 30 lines)"""
        formatted = []

        for endpoint in endpoints:
            total_requests = endpoint.get('total_requests', 0)
            duplicate_hits = endpoint.get('duplicate_hits', 0)
            duplicate_rate = (duplicate_hits / total_requests * 100) if total_requests > 0 else 0

            formatted.append({
                'endpoint': endpoint.get('endpoint', 'Unknown'),
                'total_requests': total_requests,
                'duplicate_hits': duplicate_hits,
                'duplicate_rate': round(duplicate_rate, 2),
                'avg_hit_count': round(endpoint.get('avg_hit_count', 0), 2)
            })

        return formatted


@method_decorator(require_monitoring_api_key, name='dispatch')
class CeleryIdempotencyHealthView(View):
    """
    Idempotency health status and SLO compliance.

    Security: Requires monitoring API key (Rule #3 alternative protection).
    """

    def get(self, request):
        """Return idempotency health status"""
        window_hours = int(request.GET.get('window', 24))

        stats = celery_idempotency_collector.get_idempotency_stats(window_hours)

        duplicate_rate = stats.get('duplicate_rate', 0)
        health_status = stats.get('health_status', 'unknown')

        response_data = {
            'timestamp': timezone.now().isoformat(),
            'window_hours': window_hours,
            'health_status': health_status,
            'duplicate_rate': duplicate_rate,
            'slo_compliance': self._check_slo_compliance(stats),
            'total_savings': {
                'duplicates_prevented': stats.get('duplicates_prevented', 0),
                'total_requests': stats.get('total_requests', 0),
                'efficiency_gain': self._calculate_efficiency_gain(stats)
            },
            'correlation_id': getattr(request, 'correlation_id', None)
        }

        # Sanitize for PII (Rule #15 compliance)
        sanitized_data = MonitoringPIIRedactionService.sanitize_dashboard_data(response_data)

        return JsonResponse(sanitized_data)

    def _check_slo_compliance(self, stats: dict) -> dict:
        """Check idempotency SLO compliance (Rule #8: < 30 lines)"""
        duplicate_rate = stats.get('duplicate_rate', 0)

        # SLO target: <1% duplicate rate in steady state
        target_rate = 1.0

        return {
            'target_duplicate_rate': target_rate,
            'actual_duplicate_rate': duplicate_rate,
            'compliant': duplicate_rate < target_rate,
            'health_status': stats.get('health_status', 'unknown'),
            'description': self._get_health_description(stats.get('health_status', 'unknown'))
        }

    def _get_health_description(self, health_status: str) -> str:
        """Get human-readable health description (Rule #8: < 30 lines)"""
        descriptions = {
            'healthy': 'System operating within normal parameters (<1% duplicate rate)',
            'warning': 'Elevated duplicate rate detected (1-3%) - monitor for issues',
            'critical': 'High duplicate rate (>3%) - immediate investigation required',
            'unknown': 'Insufficient data to determine health status'
        }
        return descriptions.get(health_status, 'Unknown health status')

    def _calculate_efficiency_gain(self, stats: dict) -> float:
        """Calculate efficiency gain from idempotency (Rule #8: < 30 lines)"""
        duplicates_prevented = stats.get('duplicates_prevented', 0)
        total_requests = stats.get('total_requests', 0)

        if total_requests == 0:
            return 0.0

        # Efficiency gain: % of work prevented by idempotency
        efficiency_gain = (duplicates_prevented / (total_requests + duplicates_prevented)) * 100

        return round(efficiency_gain, 2)
