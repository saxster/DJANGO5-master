"""
GraphQL Monitoring Views

Provides detailed GraphQL performance and security metrics.

Endpoints:
- /monitoring/graphql/ - GraphQL metrics overview
- /monitoring/graphql/complexity/ - Complexity distribution
- /monitoring/graphql/rejections/ - Rejection analysis

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
from monitoring.services.graphql_metrics_collector import graphql_metrics
from monitoring.services.pii_redaction_service import MonitoringPIIRedactionService

logger = logging.getLogger('monitoring.graphql')

__all__ = ['GraphQLMonitoringView', 'GraphQLComplexityView', 'GraphQLRejectionsView']


@method_decorator(require_monitoring_api_key, name='dispatch')
class GraphQLMonitoringView(View):
    """
    Overview of GraphQL metrics.

    Security: Requires monitoring API key authentication.
    """

    def get(self, request):
        """Return GraphQL metrics overview"""
        window_minutes = int(request.GET.get('window', MINUTES_IN_HOUR))

        # Get GraphQL statistics
        stats = graphql_metrics.get_graphql_stats(window_minutes)

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
        """Generate GraphQL optimization recommendations"""
        recommendations = []

        rejection_rate = stats.get('rejection_rate', 0)
        if rejection_rate > 10:
            recommendations.append({
                'level': 'warning',
                'message': f'High GraphQL rejection rate: {rejection_rate:.1f}%',
                'action': 'Review rejected query patterns and adjust limits or educate API consumers'
            })

        complexity_p95 = stats.get('complexity_stats', {}).get('p95', 0)
        if complexity_p95 > 800:
            recommendations.append({
                'level': 'info',
                'message': f'95th percentile complexity approaching limit: {complexity_p95}',
                'action': 'Consider pagination or query optimization in high-complexity operations'
            })

        validation_p95 = stats.get('validation_performance', {}).get('p95', 0)
        if validation_p95 > 10:
            recommendations.append({
                'level': 'info',
                'message': f'Query validation taking > 10ms at p95: {validation_p95:.2f}ms',
                'action': 'Validation performance is acceptable but monitor for degradation'
            })

        return recommendations


@method_decorator(require_monitoring_api_key, name='dispatch')
class GraphQLComplexityView(View):
    """
    Detailed complexity metrics and distribution.

    Security: Requires monitoring API key authentication.
    """

    def get(self, request):
        """Return complexity distribution and analysis"""
        window_minutes = int(request.GET.get('window', MINUTES_IN_HOUR))

        stats = graphql_metrics.get_graphql_stats(window_minutes)

        complexity_stats = stats.get('complexity_stats', {})
        depth_stats = stats.get('depth_stats', {})

        response_data = {
            'timestamp': datetime.now().isoformat(),
            'window_minutes': window_minutes,
            'complexity': {
                'distribution': complexity_stats,
                'histogram': self._generate_histogram(
                    graphql_metrics.complexity_distribution,
                    bins=10
                )
            },
            'depth': {
                'distribution': depth_stats,
                'histogram': self._generate_histogram(
                    graphql_metrics.depth_distribution,
                    bins=5
                )
            },
            'correlation_id': getattr(request, 'correlation_id', None)
        }

        sanitized_data = MonitoringPIIRedactionService.sanitize_dashboard_data(response_data)

        return JsonResponse(sanitized_data)

    def _generate_histogram(self, values, bins=10):
        """Generate histogram from values"""
        if not values:
            return []

        min_val = min(values)
        max_val = max(values)
        bin_width = (max_val - min_val) / bins if max_val > min_val else 1

        histogram = []
        for i in range(bins):
            bin_start = min_val + (i * bin_width)
            bin_end = bin_start + bin_width
            count = sum(1 for v in values if bin_start <= v < bin_end)
            histogram.append({
                'bin_start': round(bin_start, 2),
                'bin_end': round(bin_end, 2),
                'count': count
            })

        return histogram


@method_decorator(require_monitoring_api_key, name='dispatch')
class GraphQLRejectionsView(View):
    """
    Detailed rejection analysis and patterns.

    Security: Requires monitoring API key authentication.
    """

    def get(self, request):
        """Return rejection analysis"""
        window_minutes = int(request.GET.get('window', MINUTES_IN_HOUR))

        stats = graphql_metrics.get_graphql_stats(window_minutes)

        response_data = {
            'timestamp': datetime.now().isoformat(),
            'window_minutes': window_minutes,
            'rejection_summary': {
                'total_rejections': stats.get('total_rejections', 0),
                'rejection_rate': stats.get('rejection_rate', 0),
                'top_reasons': stats.get('top_rejection_reasons', {}),
            },
            'rejected_patterns': stats.get('top_rejected_patterns', []),
            'recommendations': self._generate_rejection_recommendations(stats),
            'correlation_id': getattr(request, 'correlation_id', None)
        }

        sanitized_data = MonitoringPIIRedactionService.sanitize_dashboard_data(response_data)

        return JsonResponse(sanitized_data)

    def _generate_rejection_recommendations(self, stats):
        """Generate recommendations based on rejection patterns"""
        recommendations = []

        top_reasons = stats.get('top_rejection_reasons', {})

        if 'depth_exceeded' in top_reasons and top_reasons['depth_exceeded'] > 10:
            recommendations.append({
                'level': 'info',
                'message': 'Multiple depth limit violations detected',
                'action': 'Educate API consumers about using fragments to reduce query depth'
            })

        if 'complexity_exceeded' in top_reasons and top_reasons['complexity_exceeded'] > 10:
            recommendations.append({
                'level': 'info',
                'message': 'Multiple complexity limit violations detected',
                'action': 'Consider implementing pagination or limiting field selections'
            })

        return recommendations
