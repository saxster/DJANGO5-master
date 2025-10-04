"""
Unified Security Monitoring Dashboard

Aggregates security metrics across all attack vectors:
- SQL injection attempts and patterns
- GraphQL security events (CSRF, rate limits, complexity violations)
- XSS attack patterns
- Overall threat assessment

Endpoints:
- /monitoring/security/ - Security overview
- /monitoring/security/sqli/ - SQL injection details
- /monitoring/security/graphql/ - GraphQL security details
- /monitoring/security/threats/ - Threat analysis

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
from apps.core.decorators import require_monitoring_api_key
from apps.core.monitoring.sql_security_telemetry import sql_security_telemetry
from apps.core.monitoring.graphql_security_monitor import security_monitor
from monitoring.services.pii_redaction_service import MonitoringPIIRedactionService

logger = logging.getLogger('monitoring.security')

__all__ = [
    'SecurityDashboardView',
    'SQLInjectionDashboardView',
    'GraphQLSecurityDashboardView',
    'ThreatAnalysisView'
]


@method_decorator(require_monitoring_api_key, name='dispatch')
class SecurityDashboardView(View):
    """
    Unified security metrics overview.

    Security: Requires monitoring API key (Rule #3 alternative protection).
    Rule #8 compliant: View methods < 30 lines
    """

    def get(self, request):
        """Return comprehensive security metrics overview"""
        window_hours = int(request.GET.get('window', 24))

        # Aggregate metrics from all security sources
        sqli_metrics = sql_security_telemetry.get_attack_trends(window_hours)
        graphql_metrics = security_monitor.get_security_metrics(window_hours * 60)

        # Calculate overall threat score
        threat_score = self._calculate_threat_score(sqli_metrics, graphql_metrics)

        response_data = {
            'timestamp': datetime.now().isoformat(),
            'window_hours': window_hours,
            'overall_threat_score': threat_score,
            'sqli_summary': self._summarize_sqli(sqli_metrics),
            'graphql_summary': self._summarize_graphql(graphql_metrics),
            'recommendations': self._generate_security_recommendations(threat_score, sqli_metrics, graphql_metrics),
            'correlation_id': getattr(request, 'correlation_id', None)
        }

        # Sanitize for PII (Rule #15 compliance)
        sanitized_data = MonitoringPIIRedactionService.sanitize_dashboard_data(response_data)

        return JsonResponse(sanitized_data)

    def _calculate_threat_score(self, sqli_metrics: dict, graphql_metrics) -> float:
        """Calculate overall threat score 0-100 (Rule #8: < 30 lines)"""
        # Threat score calculation
        sqli_score = min(sqli_metrics.get('total_violations', 0) / 10, 50)
        graphql_score = min(graphql_metrics.threat_score * 50, 50)

        total_score = sqli_score + graphql_score

        return round(min(total_score, 100), 2)

    def _summarize_sqli(self, sqli_metrics: dict) -> dict:
        """Summarize SQL injection metrics (Rule #8: < 30 lines)"""
        return {
            'total_attempts': sqli_metrics.get('total_violations', 0),
            'unique_ips': sqli_metrics.get('unique_ips', 0),
            'most_common_pattern': sqli_metrics.get('most_common_pattern', ('none', 0))[0]
        }

    def _summarize_graphql(self, graphql_metrics) -> dict:
        """Summarize GraphQL security metrics (Rule #8: < 30 lines)"""
        return {
            'total_requests': graphql_metrics.total_requests,
            'blocked_requests': graphql_metrics.blocked_requests,
            'csrf_violations': graphql_metrics.csrf_violations,
            'rate_limit_violations': graphql_metrics.rate_limit_violations
        }

    def _generate_security_recommendations(self, threat_score: float, sqli_metrics: dict, graphql_metrics) -> list:
        """Generate actionable security recommendations (Rule #8: < 30 lines)"""
        recommendations = []

        if threat_score > 75:
            recommendations.append({
                'level': 'critical',
                'message': f'Critical threat level: {threat_score}/100',
                'action': 'Immediate security team notification required'
            })

        if sqli_metrics.get('total_violations', 0) > 50:
            recommendations.append({
                'level': 'warning',
                'message': f"High SQL injection activity: {sqli_metrics['total_violations']} attempts",
                'action': 'Review and potentially block attacking IPs'
            })

        if graphql_metrics.rate_limit_violations > 100:
            recommendations.append({
                'level': 'warning',
                'message': f'Excessive GraphQL rate limit violations: {graphql_metrics.rate_limit_violations}',
                'action': 'Consider tightening rate limits or investigating API abuse'
            })

        return recommendations


@method_decorator(require_monitoring_api_key, name='dispatch')
class SQLInjectionDashboardView(View):
    """
    Detailed SQL injection attack monitoring.

    Security: Requires monitoring API key (Rule #3 alternative protection).
    """

    def get(self, request):
        """Return detailed SQL injection attack metrics"""
        window_hours = int(request.GET.get('window', 24))

        sqli_metrics = sql_security_telemetry.get_attack_trends(window_hours)

        response_data = {
            'timestamp': datetime.now().isoformat(),
            'window_hours': window_hours,
            'total_attempts': sqli_metrics.get('total_violations', 0),
            'unique_ips': sqli_metrics.get('unique_ips', 0),
            'violations_by_hour': sqli_metrics.get('violations_by_hour', []),
            'pattern_distribution': sqli_metrics.get('pattern_distribution', []),
            'top_attackers': self._get_top_attackers(10),
            'correlation_id': getattr(request, 'correlation_id', None)
        }

        # Sanitize for PII (Rule #15 compliance)
        sanitized_data = MonitoringPIIRedactionService.sanitize_dashboard_data(response_data)

        return JsonResponse(sanitized_data)

    def _get_top_attackers(self, limit: int = 10) -> list:
        """Get top attacking IPs with reputation scores (Rule #8: < 30 lines)"""
        from django.core.cache import cache

        top_ips_key = 'sql_security:top_ips:24h'
        top_ips = cache.get(top_ips_key, {})

        # Sort by violation count and get top N
        sorted_ips = sorted(
            top_ips.items(),
            key=lambda x: x[1],
            reverse=True
        )[:limit]

        return [
            {
                'ip_address': ip,
                'violation_count': count,
                'reputation': sql_security_telemetry.get_ip_reputation(ip)
            }
            for ip, count in sorted_ips
        ]


@method_decorator(require_monitoring_api_key, name='dispatch')
class GraphQLSecurityDashboardView(View):
    """
    Detailed GraphQL security event monitoring.

    Security: Requires monitoring API key (Rule #3 alternative protection).
    """

    def get(self, request):
        """Return detailed GraphQL security metrics"""
        window_hours = int(request.GET.get('window', 24))

        graphql_metrics = security_monitor.get_security_metrics(window_hours * 60)

        response_data = {
            'timestamp': datetime.now().isoformat(),
            'window_hours': window_hours,
            'total_requests': graphql_metrics.total_requests,
            'blocked_requests': graphql_metrics.blocked_requests,
            'csrf_violations': graphql_metrics.csrf_violations,
            'rate_limit_violations': graphql_metrics.rate_limit_violations,
            'origin_violations': graphql_metrics.origin_violations,
            'query_analysis_failures': graphql_metrics.query_analysis_failures,
            'threat_score': graphql_metrics.threat_score,
            'correlation_id': getattr(request, 'correlation_id', None)
        }

        # Sanitize for PII (Rule #15 compliance)
        sanitized_data = MonitoringPIIRedactionService.sanitize_dashboard_data(response_data)

        return JsonResponse(sanitized_data)


@method_decorator(require_monitoring_api_key, name='dispatch')
class ThreatAnalysisView(View):
    """
    Advanced threat pattern analysis and predictions.

    Security: Requires monitoring API key (Rule #3 alternative protection).
    """

    def get(self, request):
        """Return threat pattern analysis"""
        window_hours = int(request.GET.get('window', 24))

        # Get threat patterns from GraphQL security monitor
        threat_patterns = security_monitor.get_threat_patterns(window_hours)

        response_data = {
            'timestamp': datetime.now().isoformat(),
            'window_hours': window_hours,
            'detected_patterns': len(threat_patterns),
            'patterns': [
                {
                    'pattern_name': pattern.pattern_name,
                    'threat_level': pattern.threat_level,
                    'detection_count': pattern.detection_count,
                    'affected_users_count': len(pattern.affected_users),
                    'affected_ips_count': len(pattern.affected_ips)
                }
                for pattern in threat_patterns
            ],
            'correlation_id': getattr(request, 'correlation_id', None)
        }

        # Sanitize for PII (Rule #15 compliance)
        sanitized_data = MonitoringPIIRedactionService.sanitize_dashboard_data(response_data)

        return JsonResponse(sanitized_data)
