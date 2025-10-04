"""
GraphQL Mutation Monitoring Views

Provides detailed GraphQL mutation analytics and performance metrics.

Endpoints:
- /monitoring/graphql/mutations/ - Mutation metrics overview
- /monitoring/graphql/mutations/breakdown/ - Mutation type breakdown
- /monitoring/graphql/mutations/performance/ - Performance analysis

Compliance:
- .claude/rules.md Rule #8 (View methods < 30 lines)
- Rule #3: API key authentication required (alternative CSRF protection)
- Rule #15: PII sanitization in all responses

Security: API key authentication required for all endpoints
"""

import logging
from datetime import datetime
from django.http import JsonResponse
from django.views import View
from django.utils.decorators import method_decorator
from apps.core.decorators import require_monitoring_api_key
from apps.core.constants.datetime_constants import MINUTES_IN_HOUR, MINUTES_IN_DAY
from monitoring.services.graphql_mutation_collector import graphql_mutation_collector
from monitoring.services.pii_redaction_service import MonitoringPIIRedactionService

logger = logging.getLogger('monitoring.graphql_mutations')

__all__ = ['GraphQLMutationView', 'GraphQLMutationBreakdownView', 'GraphQLMutationPerformanceView']


@method_decorator(require_monitoring_api_key, name='dispatch')
class GraphQLMutationView(View):
    """
    Overview of GraphQL mutation metrics.

    Security: Requires monitoring API key (Rule #3 alternative protection).
    Rule #8 compliant: View methods < 30 lines
    """

    def get(self, request):
        """Return GraphQL mutation metrics overview"""
        window_minutes = int(request.GET.get('window', MINUTES_IN_HOUR))

        # Get mutation statistics
        stats = graphql_mutation_collector.get_mutation_stats(window_minutes)

        # Generate recommendations
        recommendations = self._generate_recommendations(stats)

        response_data = {
            'timestamp': datetime.now().isoformat(),
            'window_minutes': window_minutes,
            'statistics': stats,
            'recommendations': recommendations,
            'correlation_id': getattr(request, 'correlation_id', None)
        }

        # Sanitize for PII (Rule #15 compliance)
        sanitized_data = MonitoringPIIRedactionService.sanitize_dashboard_data(response_data)

        return JsonResponse(sanitized_data)

    def _generate_recommendations(self, stats: dict) -> list:
        """Generate mutation optimization recommendations (Rule #8: < 30 lines)"""
        recommendations = []

        success_rate = stats.get('success_rate', 100)
        if success_rate < 95:
            recommendations.append({
                'level': 'warning',
                'message': f'Low mutation success rate: {success_rate:.1f}%',
                'action': 'Investigate error patterns and improve error handling'
            })

        exec_p95 = stats.get('execution_time', {}).get('p95', 0)
        if exec_p95 > 1000:
            recommendations.append({
                'level': 'warning',
                'message': f'Slow mutation execution: p95 = {exec_p95:.0f}ms',
                'action': 'Review database queries and optimize N+1 query patterns'
            })

        exec_p99 = stats.get('execution_time', {}).get('p99', 0)
        if exec_p99 > 3000:
            recommendations.append({
                'level': 'critical',
                'message': f'Critical mutation performance: p99 = {exec_p99:.0f}ms',
                'action': 'Immediate optimization required - investigate timeout risks'
            })

        return recommendations


@method_decorator(require_monitoring_api_key, name='dispatch')
class GraphQLMutationBreakdownView(View):
    """
    Detailed breakdown of mutation types and error patterns.

    Security: Requires monitoring API key (Rule #3 alternative protection).
    """

    def get(self, request):
        """Return mutation type breakdown and error analysis"""
        window_minutes = int(request.GET.get('window', MINUTES_IN_HOUR))

        stats = graphql_mutation_collector.get_mutation_stats(window_minutes)

        response_data = {
            'timestamp': datetime.now().isoformat(),
            'window_minutes': window_minutes,
            'mutation_breakdown': stats.get('mutation_breakdown', {}),
            'error_breakdown': stats.get('error_breakdown', {}),
            'top_mutations': self._get_top_mutations(stats),
            'top_errors': self._get_top_errors(stats),
            'correlation_id': getattr(request, 'correlation_id', None)
        }

        # Sanitize for PII (Rule #15 compliance)
        sanitized_data = MonitoringPIIRedactionService.sanitize_dashboard_data(response_data)

        return JsonResponse(sanitized_data)

    def _get_top_mutations(self, stats: dict) -> list:
        """Get top 10 mutations by count (Rule #8: < 30 lines)"""
        mutation_breakdown = stats.get('mutation_breakdown', {})

        top_mutations = sorted(
            mutation_breakdown.items(),
            key=lambda x: x[1],
            reverse=True
        )[:10]

        return [
            {'mutation_name': name, 'count': count}
            for name, count in top_mutations
        ]

    def _get_top_errors(self, stats: dict) -> list:
        """Get top 10 error types (Rule #8: < 30 lines)"""
        error_breakdown = stats.get('error_breakdown', {})

        top_errors = sorted(
            error_breakdown.items(),
            key=lambda x: x[1],
            reverse=True
        )[:10]

        return [
            {'error_type': error_type, 'count': count}
            for error_type, count in top_errors
        ]


@method_decorator(require_monitoring_api_key, name='dispatch')
class GraphQLMutationPerformanceView(View):
    """
    Detailed mutation performance analysis.

    Security: Requires monitoring API key (Rule #3 alternative protection).
    """

    def get(self, request):
        """Return mutation performance metrics and trends"""
        window_minutes = int(request.GET.get('window', MINUTES_IN_HOUR))

        stats = graphql_mutation_collector.get_mutation_stats(window_minutes)

        exec_time = stats.get('execution_time', {})

        response_data = {
            'timestamp': datetime.now().isoformat(),
            'window_minutes': window_minutes,
            'performance_summary': {
                'mean_execution_time_ms': exec_time.get('mean', 0),
                'p50_execution_time_ms': exec_time.get('p50', 0),
                'p95_execution_time_ms': exec_time.get('p95', 0),
                'p99_execution_time_ms': exec_time.get('p99', 0),
                'max_execution_time_ms': exec_time.get('max', 0),
            },
            'complexity_stats': stats.get('complexity_stats'),
            'slo_compliance': self._check_slo_compliance(exec_time),
            'correlation_id': getattr(request, 'correlation_id', None)
        }

        # Sanitize for PII (Rule #15 compliance)
        sanitized_data = MonitoringPIIRedactionService.sanitize_dashboard_data(response_data)

        return JsonResponse(sanitized_data)

    def _check_slo_compliance(self, exec_time: dict) -> dict:
        """Check mutation SLO compliance (Rule #8: < 30 lines)"""
        # SLO targets
        p95_target = 500  # 500ms target for p95
        p99_target = 1000  # 1s target for p99

        p95_actual = exec_time.get('p95', 0)
        p99_actual = exec_time.get('p99', 0)

        return {
            'p95_target_ms': p95_target,
            'p95_actual_ms': p95_actual,
            'p95_compliant': p95_actual <= p95_target,
            'p99_target_ms': p99_target,
            'p99_actual_ms': p99_actual,
            'p99_compliant': p99_actual <= p99_target,
            'overall_compliant': p95_actual <= p95_target and p99_actual <= p99_target
        }
