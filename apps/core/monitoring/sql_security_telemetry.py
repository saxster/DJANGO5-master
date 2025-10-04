"""
SQL Security Telemetry and Alerting

Real-time monitoring and alerting for SQL injection attempts.

Features:
- Attack pattern detection and classification
- IP reputation scoring
- Automated alerting (Slack, email, webhooks)
- Grafana dashboard integration
- Attack trend analysis
- Automated IP blocking recommendations

Author: Claude Code
Date: 2025-10-01
"""

import logging
import time
import json
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from collections import Counter

from django.core.cache import cache
from django.conf import settings
from django.utils import timezone

from apps.core.constants.datetime_constants import SECONDS_IN_HOUR, SECONDS_IN_DAY

logger = logging.getLogger('security.sql_telemetry')


class SQLSecurityTelemetry:
    """
    Telemetry system for SQL injection attack monitoring.

    Collects, analyzes, and alerts on SQL injection attempts.
    """

    # Attack pattern classifications
    PATTERN_TYPES = {
        'union': 'Union-based injection',
        'boolean_blind': 'Boolean-based blind injection',
        'time_blind': 'Time-based blind injection',
        'error_based': 'Error-based injection',
        'stacked_queries': 'Stacked queries injection',
        'out_of_band': 'Out-of-band injection',
        'command_execution': 'Command execution attempt'
    }

    # Severity scoring
    PATTERN_SEVERITY = {
        'command_execution': 10,  # Critical
        'stacked_queries': 9,
        'union': 8,
        'error_based': 7,
        'time_blind': 6,
        'boolean_blind': 5,
        'out_of_band': 6
    }

    def __init__(self):
        self.alert_threshold = getattr(settings, 'SQL_SECURITY_ALERT_THRESHOLD', 10)
        self.block_threshold = getattr(settings, 'SQL_SECURITY_BLOCK_THRESHOLD', 50)

    def record_violation(
        self,
        ip_address: str,
        pattern_matched: str,
        endpoint: str,
        user_id: Optional[int] = None,
        request_data: Optional[Dict] = None
    ):
        """
        Record an SQL injection violation.

        Args:
            ip_address: Client IP address
            pattern_matched: SQL pattern that was detected
            endpoint: Request endpoint
            user_id: User ID if authenticated
            request_data: Additional request context
        """
        current_hour = int(time.time() // SECONDS_IN_HOUR)

        # Record violation
        violation = {
            'timestamp': timezone.now().isoformat(),
            'ip_address': ip_address,
            'pattern': pattern_matched,
            'pattern_type': self._classify_pattern(pattern_matched),
            'severity': self._calculate_severity(pattern_matched),
            'endpoint': endpoint,
            'user_id': user_id,
            'request_data': request_data or {}
        }

        # Store in hourly bucket
        violations_key = f"sql_security:violations:{current_hour}"
        violations = cache.get(violations_key, [])
        violations.append(violation)
        cache.set(violations_key, violations, SECONDS_IN_HOUR * 2)

        # Update IP statistics
        self._update_ip_stats(ip_address, violation)

        # Update pattern statistics
        self._update_pattern_stats(pattern_matched)

        # Check for alerting conditions
        self._check_alert_conditions(ip_address, violation)

        logger.warning(
            f"SQL injection attempt detected from {ip_address}",
            extra={
                'ip_address': ip_address,
                'pattern': pattern_matched,
                'endpoint': endpoint,
                'severity': violation['severity']
            }
        )

    def _classify_pattern(self, pattern: str) -> str:
        """Classify the SQL injection pattern"""
        pattern_lower = pattern.lower()

        if 'xp_cmdshell' in pattern_lower or 'sp_execute' in pattern_lower:
            return 'command_execution'
        elif 'union' in pattern_lower:
            return 'union'
        elif 'sleep' in pattern_lower or 'waitfor' in pattern_lower or 'benchmark' in pattern_lower:
            return 'time_blind'
        elif ';' in pattern_lower and any(cmd in pattern_lower for cmd in ['drop', 'delete', 'insert']):
            return 'stacked_queries'
        elif "or '1'='1" in pattern_lower or 'and 1=1' in pattern_lower:
            return 'boolean_blind'
        else:
            return 'error_based'

    def _calculate_severity(self, pattern: str) -> int:
        """Calculate severity score for the pattern"""
        pattern_type = self._classify_pattern(pattern)
        return self.PATTERN_SEVERITY.get(pattern_type, 5)

    def _update_ip_stats(self, ip_address: str, violation: Dict):
        """Update statistics for this IP address"""
        ip_stats_key = f"sql_security:ip_stats:{ip_address}"
        ip_stats = cache.get(ip_stats_key, {
            'violation_count': 0,
            'first_seen': timezone.now().isoformat(),
            'last_seen': timezone.now().isoformat(),
            'patterns': [],
            'severity_score': 0
        })

        ip_stats['violation_count'] += 1
        ip_stats['last_seen'] = timezone.now().isoformat()
        ip_stats['patterns'].append(violation['pattern_type'])
        ip_stats['severity_score'] += violation['severity']

        cache.set(ip_stats_key, ip_stats, SECONDS_IN_DAY)

        # Update top attackers list
        top_ips_key = 'sql_security:top_ips:24h'
        top_ips = cache.get(top_ips_key, {})
        top_ips[ip_address] = ip_stats['violation_count']
        cache.set(top_ips_key, top_ips, SECONDS_IN_DAY)

    def _update_pattern_stats(self, pattern: str):
        """Update pattern statistics"""
        pattern_type = self._classify_pattern(pattern)

        pattern_stats_key = f"sql_security:pattern_stats:{pattern_type}"
        pattern_stats = cache.get(pattern_stats_key, {'count': 0})
        pattern_stats['count'] += 1
        cache.set(pattern_stats_key, pattern_stats, SECONDS_IN_DAY)

    def _check_alert_conditions(self, ip_address: str, violation: Dict):
        """Check if alerting conditions are met"""
        ip_stats_key = f"sql_security:ip_stats:{ip_address}"
        ip_stats = cache.get(ip_stats_key, {})

        violation_count = ip_stats.get('violation_count', 0)

        # High severity individual violation
        if violation['severity'] >= 9:
            self._send_alert(
                level='CRITICAL',
                message=f"Critical SQL injection attempt from {ip_address}",
                details=violation
            )

        # Multiple violations from same IP
        elif violation_count >= self.alert_threshold:
            self._send_alert(
                level='HIGH',
                message=f"Multiple SQL injection attempts from {ip_address} ({violation_count} attempts)",
                details=ip_stats
            )

        # Recommend automatic blocking
        if violation_count >= self.block_threshold:
            self._recommend_ip_block(ip_address, ip_stats)

    def _send_alert(self, level: str, message: str, details: Dict):
        """Send alert via configured channels"""
        logger.critical(
            f"[{level}] SQL Security Alert: {message}",
            extra={'alert_level': level, 'details': details}
        )

        # Slack integration (if configured)
        if hasattr(settings, 'SLACK_WEBHOOK_URL'):
            self._send_slack_alert(level, message, details)

        # Email alert (if configured)
        if hasattr(settings, 'SECURITY_ALERT_EMAILS'):
            self._send_email_alert(level, message, details)

        # Webhook (if configured)
        if hasattr(settings, 'SECURITY_ALERT_WEBHOOK'):
            self._send_webhook_alert(level, message, details)

    def _send_slack_alert(self, level: str, message: str, details: Dict):
        """Send alert to Slack"""
        try:
            import requests
            from apps.core.constants.datetime_constants import NETWORK_TIMEOUT_TUPLE

            slack_webhook = settings.SLACK_WEBHOOK_URL

            color = {
                'CRITICAL': '#ff0000',
                'HIGH': '#ff6600',
                'MEDIUM': '#ffcc00',
                'LOW': '#cccccc'
            }.get(level, '#cccccc')

            payload = {
                'attachments': [{
                    'color': color,
                    'title': f'🚨 SQL Security Alert - {level}',
                    'text': message,
                    'fields': [
                        {'title': 'Details', 'value': json.dumps(details, indent=2)[:500], 'short': False},
                        {'title': 'Timestamp', 'value': timezone.now().isoformat(), 'short': True}
                    ]
                }]
            }

            requests.post(slack_webhook, json=payload, timeout=NETWORK_TIMEOUT_TUPLE)

        except Exception as e:
            logger.error(f"Failed to send Slack alert: {e}", exc_info=True)

    def _send_email_alert(self, level: str, message: str, details: Dict):
        """Send email alert"""
        try:
            from django.core.mail import send_mail

            send_mail(
                subject=f'[{level}] SQL Security Alert',
                message=f"{message}\n\nDetails:\n{json.dumps(details, indent=2)}",
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=settings.SECURITY_ALERT_EMAILS,
                fail_silently=True
            )

        except Exception as e:
            logger.error(f"Failed to send email alert: {e}", exc_info=True)

    def _send_webhook_alert(self, level: str, message: str, details: Dict):
        """Send webhook alert"""
        try:
            import requests
            from apps.core.constants.datetime_constants import NETWORK_TIMEOUT_TUPLE

            webhook_url = settings.SECURITY_ALERT_WEBHOOK

            payload = {
                'level': level,
                'message': message,
                'details': details,
                'timestamp': timezone.now().isoformat()
            }

            requests.post(webhook_url, json=payload, timeout=NETWORK_TIMEOUT_TUPLE)

        except Exception as e:
            logger.error(f"Failed to send webhook alert: {e}", exc_info=True)

    def _recommend_ip_block(self, ip_address: str, ip_stats: Dict):
        """Recommend IP for automatic blocking"""
        block_recommendation_key = f"sql_security:block_recommendation:{ip_address}"

        recommendation = {
            'ip_address': ip_address,
            'violation_count': ip_stats['violation_count'],
            'severity_score': ip_stats['severity_score'],
            'recommended_at': timezone.now().isoformat(),
            'reason': 'Exceeded SQL injection attempt threshold'
        }

        cache.set(block_recommendation_key, recommendation, SECONDS_IN_DAY * 7)

        logger.critical(
            f"Recommend blocking IP {ip_address} - {ip_stats['violation_count']} SQL injection attempts",
            extra={'ip_address': ip_address, 'stats': ip_stats}
        )

        self._send_alert(
            level='CRITICAL',
            message=f"Recommend blocking IP {ip_address}",
            details=recommendation
        )

    def get_attack_trends(self, hours: int = 24) -> Dict[str, Any]:
        """
        Get attack trend analysis.

        Args:
            hours: Number of hours to analyze

        Returns:
            Dictionary with trend analysis
        """
        current_hour = int(time.time() // SECONDS_IN_HOUR)

        violations_by_hour = []
        all_patterns = []
        all_ips = set()

        for hour_offset in range(hours):
            hour_key = current_hour - hour_offset
            violations_key = f"sql_security:violations:{hour_key}"
            violations = cache.get(violations_key, [])

            violations_by_hour.append({
                'hour': hour_key,
                'timestamp': datetime.fromtimestamp(hour_key * SECONDS_IN_HOUR).isoformat(),
                'count': len(violations)
            })

            for violation in violations:
                all_patterns.append(violation.get('pattern_type', 'unknown'))
                all_ips.add(violation.get('ip_address', 'unknown'))

        # Pattern distribution
        pattern_counter = Counter(all_patterns)
        pattern_distribution = [
            {'pattern': pattern, 'count': count}
            for pattern, count in pattern_counter.most_common(10)
        ]

        return {
            'total_violations': sum(h['count'] for h in violations_by_hour),
            'unique_ips': len(all_ips),
            'violations_by_hour': list(reversed(violations_by_hour)),  # Chronological order
            'pattern_distribution': pattern_distribution,
            'most_common_pattern': pattern_counter.most_common(1)[0] if pattern_counter else ('none', 0)
        }

    def get_ip_reputation(self, ip_address: str) -> Dict[str, Any]:
        """
        Get reputation score for an IP address.

        Args:
            ip_address: IP address to check

        Returns:
            Reputation data including score and risk level
        """
        ip_stats_key = f"sql_security:ip_stats:{ip_address}"
        ip_stats = cache.get(ip_stats_key, {})

        if not ip_stats:
            return {
                'ip_address': ip_address,
                'reputation_score': 100,
                'risk_level': 'CLEAN',
                'violation_count': 0
            }

        violation_count = ip_stats.get('violation_count', 0)
        severity_score = ip_stats.get('severity_score', 0)

        # Calculate reputation score (0-100, lower is worse)
        reputation_score = max(0, 100 - (violation_count * 5) - severity_score)

        # Determine risk level
        if reputation_score >= 80:
            risk_level = 'CLEAN'
        elif reputation_score >= 60:
            risk_level = 'LOW'
        elif reputation_score >= 40:
            risk_level = 'MEDIUM'
        elif reputation_score >= 20:
            risk_level = 'HIGH'
        else:
            risk_level = 'CRITICAL'

        return {
            'ip_address': ip_address,
            'reputation_score': reputation_score,
            'risk_level': risk_level,
            'violation_count': violation_count,
            'severity_score': severity_score,
            'first_seen': ip_stats.get('first_seen'),
            'last_seen': ip_stats.get('last_seen'),
            'patterns': list(set(ip_stats.get('patterns', [])))
        }


# Singleton instance
sql_security_telemetry = SQLSecurityTelemetry()


# ============================================================================
# Helper Functions
# ============================================================================

def record_sql_injection_attempt(
    ip_address: str,
    pattern_matched: str,
    endpoint: str,
    user_id: Optional[int] = None,
    request_data: Optional[Dict] = None
):
    """
    Helper function to record SQL injection attempt.

    Called from SQLInjectionProtectionMiddleware.
    """
    sql_security_telemetry.record_violation(
        ip_address=ip_address,
        pattern_matched=pattern_matched,
        endpoint=endpoint,
        user_id=user_id,
        request_data=request_data
    )


def get_attack_trends(hours: int = 24) -> Dict[str, Any]:
    """Get SQL injection attack trends"""
    return sql_security_telemetry.get_attack_trends(hours)


def get_ip_reputation(ip_address: str) -> Dict[str, Any]:
    """Get IP reputation data"""
    return sql_security_telemetry.get_ip_reputation(ip_address)
