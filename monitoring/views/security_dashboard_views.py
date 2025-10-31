"""
Unified Security Monitoring Dashboard

Aggregates security metrics across key attack vectors:
- SQL injection attempts and patterns
- XSS attack patterns
- Overall threat assessment

Endpoints:
- /monitoring/security/ - Security overview
- /monitoring/security/sqli/ - SQL injection details
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
from monitoring.services.pii_redaction_service import MonitoringPIIRedactionService

logger = logging.getLogger('monitoring.security')

__all__ = [
    'SecurityDashboardView',
    'SQLInjectionDashboardView',
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

        # Aggregate metrics from security sources
        sqli_metrics = sql_security_telemetry.get_attack_trends(window_hours)

        # Calculate overall threat score
        threat_score = self._calculate_threat_score(sqli_metrics)

        response_data = {
            'timestamp': datetime.now().isoformat(),
            'window_hours': window_hours,
            'overall_threat_score': threat_score,
            'sqli_summary': self._summarize_sqli(sqli_metrics),
            'recommendations': self._generate_security_recommendations(threat_score, sqli_metrics),
            'correlation_id': getattr(request, 'correlation_id', None)
        }

        # Sanitize for PII (Rule #15 compliance)
        sanitized_data = MonitoringPIIRedactionService.sanitize_dashboard_data(response_data)

        return JsonResponse(sanitized_data)

    def _calculate_threat_score(self, sqli_metrics: dict) -> float:
        """Calculate overall threat score 0-100 (Rule #8: < 30 lines)"""
        # Threat score calculation based on SQL injection activity
        sqli_score = min(sqli_metrics.get('total_violations', 0) / 10, 100)
        return round(min(sqli_score, 100), 2)

    def _summarize_sqli(self, sqli_metrics: dict) -> dict:
        """Summarize SQL injection metrics (Rule #8: < 30 lines)"""
        return {
            'total_attempts': sqli_metrics.get('total_violations', 0),
            'unique_ips': sqli_metrics.get('unique_ips', 0),
            'most_common_pattern': sqli_metrics.get('most_common_pattern', ('none', 0))[0]
        }

    def _generate_security_recommendations(self, threat_score: float, sqli_metrics: dict) -> list:
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
class ThreatAnalysisView(View):
    """
    Advanced threat pattern analysis and predictions.

    Security: Requires monitoring API key (Rule #3 alternative protection).
    """

    def get(self, request):
        """Return threat pattern analysis"""
        window_hours = int(request.GET.get('window', 24))

        sqli_metrics = sql_security_telemetry.get_attack_trends(window_hours)
        pattern_distribution = sqli_metrics.get('pattern_distribution', [])

        response_data = {
            'timestamp': datetime.now().isoformat(),
            'window_hours': window_hours,
            'detected_patterns': len(pattern_distribution),
            'patterns': pattern_distribution,
            'correlation_id': getattr(request, 'correlation_id', None)
        }

        # Sanitize for PII (Rule #15 compliance)
        sanitized_data = MonitoringPIIRedactionService.sanitize_dashboard_data(response_data)

        return JsonResponse(sanitized_data)
