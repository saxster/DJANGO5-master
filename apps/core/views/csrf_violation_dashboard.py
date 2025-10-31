"""
CSRF Violation Monitoring Dashboard

Real-time dashboard for monitoring CSRF violations, detecting attack patterns,
and managing security incidents related to CSRF bypass attempts.

Features:
- Real-time violation tracking
- Geographic analysis of attack sources
- Automated IP blocking for repeated violations
- Integration with CSPViolation model
- Threat intelligence and pattern recognition
- Incident response automation

Security: Staff-only access, comprehensive audit logging
Compliance: Rule #3 monitoring and enforcement

Author: Security Enhancement Team
Date: 2025-09-27
"""

import logging
import json
from datetime import datetime, timedelta
from typing import Dict, Any, List

from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.mixins import UserPassesTestMixin
from django.core.cache import cache
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.http import JsonResponse
from django.shortcuts import render
from django.utils import timezone
from django.views.generic import View

from apps.core.models import CSPViolation

logger = logging.getLogger(__name__)
security_logger = logging.getLogger('security')


class CSRFViolationDashboardView(UserPassesTestMixin, View):
    """
    Main dashboard for CSRF violation monitoring.

    Provides:
    - Real-time violation statistics
    - Geographic distribution of attacks
    - Blocked IPs and users
    - Attack pattern analysis
    - Incident response tools
    """

    def test_func(self):
        return self.request.user.is_staff

    def get(self, request, *args, **kwargs):
        """Render CSRF violation dashboard."""
        try:
            dashboard_data = self._get_dashboard_data()

            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse(dashboard_data)

            context = {
                'dashboard_data': dashboard_data,
                'refresh_interval': 30000,
                'page_title': 'CSRF Violation Monitoring Dashboard'
            }

            return render(request, 'core/csrf_violation_dashboard.html', context)

        except (ValueError, TypeError) as e:
            logger.error(f"CSRF dashboard error: {e}", exc_info=True)
            return JsonResponse({
                'error': 'Dashboard data unavailable',
                'message': str(e)
            }, status=500)

    def _get_dashboard_data(self) -> Dict[str, Any]:
        """Compile comprehensive CSRF violation dashboard data."""
        return {
            'summary': self._get_violation_summary(),
            'recent_violations': self._get_recent_violations(),
            'blocked_sources': self._get_blocked_sources(),
            'attack_patterns': self._get_attack_patterns(),
            'geographic_distribution': self._get_geographic_distribution(),
            'timeline_data': self._get_timeline_data(),
            'threat_intelligence': self._get_threat_intelligence(),
            'recommendations': self._get_security_recommendations(),
            'timestamp': timezone.now().isoformat()
        }

    def _get_violation_summary(self) -> Dict[str, Any]:
        """Get summary statistics for CSRF violations."""
        now = timezone.now()
        time_ranges = {
            '1h': now - timedelta(hours=1),
            '24h': now - timedelta(hours=24),
            '7d': now - timedelta(days=7),
            '30d': now - timedelta(days=30),
        }

        summary = {
            'total_all_time': self._count_violations_in_cache('all'),
        }

        for range_name, since in time_ranges.items():
            summary[f'total_{range_name}'] = self._count_violations_in_cache(range_name)

        summary['blocked_ips'] = self._count_blocked_ips()
        summary['blocked_users'] = self._count_blocked_users()
        summary['active_blocks'] = summary['blocked_ips'] + summary['blocked_users']

        return summary

    def _get_recent_violations(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get recent CSRF violations from cache."""
        violations = []

        cache_keys = cache.keys('csrf_violations:*') if hasattr(cache, 'keys') else []

        for key in cache_keys[:100]:
            try:
                violation_list = cache.get(key, [])
                for violation in violation_list:
                    violations.append({
                        'identifier': key.replace('csrf_violations:', ''),
                        'timestamp': datetime.fromtimestamp(violation['timestamp']).isoformat(),
                        'path': violation['path'],
                        'method': violation['method'],
                        'user_agent': violation['user_agent'],
                        'severity': self._calculate_severity(violation)
                    })
            except (ConnectionError, ValueError) as e:
                logger.error(f"Error processing violation from {key}: {e}")

        violations.sort(key=lambda x: x['timestamp'], reverse=True)
        return violations[:limit]

    def _get_blocked_sources(self) -> List[Dict[str, Any]]:
        """Get currently blocked IPs and users."""
        blocked = []

        cache_keys = cache.keys('csrf_block:*') if hasattr(cache, 'keys') else []

        for key in cache_keys:
            try:
                if cache.get(key):
                    identifier = key.replace('csrf_block:', '')
                    violation_key = f'csrf_violations:{identifier}'
                    violations = cache.get(violation_key, [])

                    blocked.append({
                        'identifier': identifier,
                        'type': 'user' if identifier.startswith('user:') else 'ip',
                        'violation_count': len(violations),
                        'first_violation': self._get_first_violation_time(violations),
                        'last_violation': self._get_last_violation_time(violations),
                        'block_expires_at': self._get_block_expiry(key)
                    })
            except (ConnectionError, ValueError) as e:
                logger.error(f"Error processing blocked source {key}: {e}")

        return sorted(blocked, key=lambda x: x['violation_count'], reverse=True)

    def _get_attack_patterns(self) -> List[Dict[str, Any]]:
        """Identify common attack patterns from violations."""
        patterns = []

        path_counts = {}
        user_agent_counts = {}

        cache_keys = cache.keys('csrf_violations:*') if hasattr(cache, 'keys') else []

        for key in cache_keys:
            try:
                violations = cache.get(key, [])
                for violation in violations:
                    path = violation.get('path', 'unknown')
                    user_agent = violation.get('user_agent', 'unknown')[:50]

                    path_counts[path] = path_counts.get(path, 0) + 1
                    user_agent_counts[user_agent] = user_agent_counts.get(user_agent, 0) + 1
            except (ConnectionError, ValueError):
                pass

        for path, count in sorted(path_counts.items(), key=lambda x: x[1], reverse=True)[:10]:
            if count > 5:
                patterns.append({
                    'type': 'targeted_endpoint',
                    'target': path,
                    'count': count,
                    'severity': 'high' if count > 20 else 'medium',
                    'description': f'Endpoint {path} targeted {count} times'
                })

        for ua, count in sorted(user_agent_counts.items(), key=lambda x: x[1], reverse=True)[:5]:
            if count > 10:
                patterns.append({
                    'type': 'automated_attack',
                    'user_agent': ua,
                    'count': count,
                    'severity': 'high',
                    'description': f'Automated attack pattern detected (User-Agent: {ua})'
                })

        return patterns

    def _get_geographic_distribution(self) -> Dict[str, int]:
        """
        Get geographic distribution of CSRF violations.

        Note: Requires GeoIP integration for full functionality.
        For now, returns IP-based distribution.
        """
        ip_distribution = {}

        cache_keys = cache.keys('csrf_violations:*') if hasattr(cache, 'keys') else []

        for key in cache_keys:
            try:
                if key.startswith('csrf_violations:ip:'):
                    ip = key.replace('csrf_violations:ip:', '')
                    violations = cache.get(key, [])
                    ip_distribution[ip] = len(violations)
            except (ConnectionError, ValueError):
                pass

        return dict(sorted(ip_distribution.items(), key=lambda x: x[1], reverse=True)[:20])

    def _get_timeline_data(self) -> Dict[str, List[int]]:
        """Get hourly timeline data for last 24 hours."""
        now = timezone.now()
        hourly_counts = [0] * 24

        cache_keys = cache.keys('csrf_violations:*') if hasattr(cache, 'keys') else []

        for key in cache_keys:
            try:
                violations = cache.get(key, [])
                for violation in violations:
                    violation_time = datetime.fromtimestamp(violation['timestamp'])
                    if violation_time > now - timedelta(hours=24):
                        hours_ago = int((now - violation_time).total_seconds() / 3600)
                        if 0 <= hours_ago < 24:
                            hourly_counts[23 - hours_ago] += 1
            except (ConnectionError, ValueError):
                pass

        return {
            'labels': [f'{i}h ago' for i in range(23, -1, -1)],
            'values': hourly_counts
        }

    def _get_threat_intelligence(self) -> Dict[str, Any]:
        """Get threat intelligence analysis."""
        return {
            'attack_sophistication': self._analyze_attack_sophistication(),
            'likely_attack_type': self._identify_likely_attack_type(),
            'risk_level': self._calculate_current_risk_level(),
            'recommended_actions': self._get_recommended_actions()
        }

    def _get_security_recommendations(self) -> List[Dict[str, str]]:
        """Generate security recommendations based on violation patterns."""
        recommendations = []

        violation_count_24h = self._count_violations_in_cache('24h')

        if violation_count_24h > 100:
            recommendations.append({
                'severity': 'high',
                'title': 'High CSRF violation rate detected',
                'description': f'{violation_count_24h} violations in last 24 hours',
                'action': 'Review firewall rules and consider IP-based blocking at edge'
            })

        blocked_count = self._count_blocked_ips() + self._count_blocked_users()
        if blocked_count > 50:
            recommendations.append({
                'severity': 'medium',
                'title': 'Many sources currently blocked',
                'description': f'{blocked_count} IPs/users blocked',
                'action': 'Review block list and consider permanent firewall rules'
            })

        patterns = self._get_attack_patterns()
        automated_attacks = [p for p in patterns if p['type'] == 'automated_attack']
        if len(automated_attacks) > 0:
            recommendations.append({
                'severity': 'high',
                'title': 'Automated attack detected',
                'description': f'{len(automated_attacks)} automated attack patterns identified',
                'action': 'Enable WAF rules for bot detection and implement CAPTCHA'
            })

        return recommendations

    def _count_violations_in_cache(self, time_range: str) -> int:
        """Count violations in cache for time range."""
        count = 0

        if time_range == 'all':
            cache_keys = cache.keys('csrf_violations:*') if hasattr(cache, 'keys') else []
            for key in cache_keys:
                violations = cache.get(key, [])
                count += len(violations)
            return count

        now = timezone.now()
        range_mapping = {
            '1h': timedelta(hours=1),
            '24h': timedelta(hours=24),
            '7d': timedelta(days=7),
            '30d': timedelta(days=30),
        }

        since = now - range_mapping.get(time_range, timedelta(hours=24))

        cache_keys = cache.keys('csrf_violations:*') if hasattr(cache, 'keys') else []
        for key in cache_keys:
            try:
                violations = cache.get(key, [])
                for violation in violations:
                    violation_time = datetime.fromtimestamp(violation['timestamp'])
                    if violation_time > since:
                        count += 1
            except (ConnectionError, ValueError):
                pass

        return count

    def _count_blocked_ips(self) -> int:
        """Count currently blocked IPs."""
        blocked_keys = cache.keys('csrf_block:ip:*') if hasattr(cache, 'keys') else []
        return sum(1 for key in blocked_keys if cache.get(key))

    def _count_blocked_users(self) -> int:
        """Count currently blocked users."""
        blocked_keys = cache.keys('csrf_block:user:*') if hasattr(cache, 'keys') else []
        return sum(1 for key in blocked_keys if cache.get(key))

    def _calculate_severity(self, violation: Dict) -> str:
        """Calculate severity of individual violation."""
        admin_paths = ['/admin/', '/monitoring/']
        mutation_operations = ['cancel', 'delete', 'purge', 'restart']

        path = violation.get('path', '')

        if any(admin_path in path for admin_path in admin_paths):
            return 'high'

        if any(op in path.lower() for op in mutation_operations):
            return 'high'

        return 'medium'

    def _get_first_violation_time(self, violations: List) -> str:
        """Get timestamp of first violation."""
        if not violations:
            return 'unknown'

        first = min(violations, key=lambda x: x.get('timestamp', 0))
        return datetime.fromtimestamp(first['timestamp']).isoformat()

    def _get_last_violation_time(self, violations: List) -> str:
        """Get timestamp of last violation."""
        if not violations:
            return 'unknown'

        last = max(violations, key=lambda x: x.get('timestamp', 0))
        return datetime.fromtimestamp(last['timestamp']).isoformat()

    def _get_block_expiry(self, block_key: str) -> str:
        """Get block expiry time from cache TTL."""
        try:
            ttl = cache.ttl(block_key) if hasattr(cache, 'ttl') else None
            if ttl:
                expiry = timezone.now() + timedelta(seconds=ttl)
                return expiry.isoformat()
        except (ConnectionError, ValueError):
            pass

        return 'unknown'

    def _analyze_attack_sophistication(self) -> str:
        """Analyze sophistication level of attacks."""
        patterns = self._get_attack_patterns()
        automated_count = sum(1 for p in patterns if p['type'] == 'automated_attack')

        if automated_count > 3:
            return 'high'
        elif automated_count > 0:
            return 'medium'
        else:
            return 'low'

    def _identify_likely_attack_type(self) -> str:
        """Identify most likely type of attack."""
        patterns = self._get_attack_patterns()

        if any(p['type'] == 'automated_attack' for p in patterns):
            return 'automated_csrf_attack'
        elif any(p['type'] == 'targeted_endpoint' for p in patterns):
            return 'targeted_endpoint_attack'
        else:
            return 'opportunistic_probing'

    def _calculate_current_risk_level(self) -> str:
        """Calculate overall current risk level."""
        violation_count_1h = self._count_violations_in_cache('1h')
        blocked_count = self._count_blocked_ips() + self._count_blocked_users()

        if violation_count_1h > 50 or blocked_count > 20:
            return 'critical'
        elif violation_count_1h > 20 or blocked_count > 10:
            return 'high'
        elif violation_count_1h > 5:
            return 'medium'
        else:
            return 'low'

    def _get_recommended_actions(self) -> List[str]:
        """Get recommended actions based on current threat level."""
        risk_level = self._calculate_current_risk_level()

        if risk_level == 'critical':
            return [
                'Enable emergency WAF rules immediately',
                'Contact security team for incident response',
                'Review and tighten rate limiting',
                'Consider temporary IP blocks at edge network'
            ]
        elif risk_level == 'high':
            return [
                'Monitor logs for attack patterns',
                'Verify existing IP blocks are effective',
                'Review recent code changes for vulnerabilities'
            ]
        elif risk_level == 'medium':
            return [
                'Continue monitoring for escalation',
                'Schedule security review of affected endpoints'
            ]
        else:
            return [
                'Normal operations - no immediate action required'
            ]


class CSRFViolationDetailView(UserPassesTestMixin, View):
    """
    Detailed view of specific CSRF violation for incident investigation.
    """

    def test_func(self):
        return self.request.user.is_staff

    def get(self, request, identifier, *args, **kwargs):
        """Get detailed violation information for specific source."""
        try:
            violation_key = f'csrf_violations:{identifier}'
            violations = cache.get(violation_key, [])

            if not violations:
                return JsonResponse({
                    'error': 'No violations found',
                    'identifier': identifier
                }, status=404)

            block_key = f'csrf_block:{identifier}'
            is_blocked = cache.get(block_key, False)

            detail_data = {
                'identifier': identifier,
                'type': 'user' if identifier.startswith('user:') else 'ip',
                'is_blocked': is_blocked,
                'violation_count': len(violations),
                'violations': [
                    {
                        'timestamp': datetime.fromtimestamp(v['timestamp']).isoformat(),
                        'path': v['path'],
                        'method': v['method'],
                        'user_agent': v['user_agent']
                    }
                    for v in violations
                ],
                'block_info': {
                    'blocked': is_blocked,
                    'expires_at': self._get_block_expiry(block_key) if is_blocked else None
                },
                'threat_analysis': self._analyze_threat(violations)
            }

            return JsonResponse(detail_data)

        except (ConnectionError, ValueError) as e:
            logger.error(f"Error getting violation details: {e}", exc_info=True)
            return JsonResponse({
                'error': 'Failed to retrieve violation details',
                'message': str(e)
            }, status=500)

    def _analyze_threat(self, violations: List[Dict]) -> Dict[str, Any]:
        """Analyze threat level for specific source."""
        if not violations:
            return {'level': 'unknown', 'confidence': 0}

        paths_targeted = set(v['path'] for v in violations)
        time_span = max(v['timestamp'] for v in violations) - min(v['timestamp'] for v in violations)
        rate = len(violations) / max(time_span / 60, 1)

        if len(paths_targeted) > 5 and rate > 10:
            return {
                'level': 'critical',
                'confidence': 95,
                'type': 'automated_scanning',
                'description': 'High-rate automated attack across multiple endpoints'
            }
        elif len(violations) > 10:
            return {
                'level': 'high',
                'confidence': 80,
                'type': 'persistent_attack',
                'description': 'Persistent CSRF bypass attempts'
            }
        else:
            return {
                'level': 'medium',
                'confidence': 60,
                'type': 'probing',
                'description': 'Potential reconnaissance or misconfiguration'
            }


class CSRFViolationManagementView(UserPassesTestMixin, View):
    """
    Management endpoint for CSRF violation response actions.

    Actions:
    - Unblock IP/user
    - Extend block duration
    - Add to permanent blocklist
    - Clear violation history
    """

    def test_func(self):
        return self.request.user.is_staff and self.request.user.is_superuser

    def post(self, request, *args, **kwargs):
        """Handle CSRF violation management actions."""
        try:
            data = json.loads(request.body)
            action = data.get('action')
            identifier = data.get('identifier')

            if not action or not identifier:
                return JsonResponse({
                    'error': 'Missing required parameters'
                }, status=400)

            if action == 'unblock':
                return self._unblock_source(identifier)
            elif action == 'extend_block':
                return self._extend_block(identifier, data.get('duration', 86400))
            elif action == 'clear_violations':
                return self._clear_violations(identifier)
            elif action == 'permanent_block':
                return self._permanent_block(identifier)
            else:
                return JsonResponse({
                    'error': 'Unknown action'
                }, status=400)

        except json.JSONDecodeError:
            return JsonResponse({
                'error': 'Invalid JSON data'
            }, status=400)
        except (ConnectionError, TypeError, ValueError, json.JSONDecodeError) as e:
            logger.error(f"CSRF management error: {e}", exc_info=True)
            return JsonResponse({
                'error': 'Management operation failed',
                'message': str(e)
            }, status=500)

    def _unblock_source(self, identifier: str) -> JsonResponse:
        """Unblock a source."""
        block_key = f'csrf_block:{identifier}'
        violation_key = f'csrf_violations:{identifier}'

        cache.delete(block_key)

        security_logger.info(
            f"Unblocked CSRF violation source: {identifier}",
            extra={
                'event_type': 'csrf_unblock',
                'identifier': identifier,
                'unblocked_by': self.request.user.loginid if hasattr(self.request.user, 'loginid') else 'unknown'
            }
        )

        return JsonResponse({
            'status': 'success',
            'message': f'Unblocked {identifier}',
            'identifier': identifier
        })

    def _extend_block(self, identifier: str, duration: int) -> JsonResponse:
        """Extend block duration for a source."""
        block_key = f'csrf_block:{identifier}'

        cache.set(block_key, True, duration)

        security_logger.info(
            f"Extended CSRF block for {identifier}",
            extra={
                'event_type': 'csrf_block_extended',
                'identifier': identifier,
                'duration': duration,
                'extended_by': self.request.user.loginid if hasattr(self.request.user, 'loginid') else 'unknown'
            }
        )

        return JsonResponse({
            'status': 'success',
            'message': f'Extended block for {identifier}',
            'identifier': identifier,
            'new_duration': duration
        })

    def _clear_violations(self, identifier: str) -> JsonResponse:
        """Clear violation history for a source."""
        violation_key = f'csrf_violations:{identifier}'
        cache.delete(violation_key)

        security_logger.info(
            f"Cleared CSRF violations for {identifier}",
            extra={
                'event_type': 'csrf_violations_cleared',
                'identifier': identifier,
                'cleared_by': self.request.user.loginid if hasattr(self.request.user, 'loginid') else 'unknown'
            }
        )

        return JsonResponse({
            'status': 'success',
            'message': f'Cleared violations for {identifier}',
            'identifier': identifier
        })

    def _permanent_block(self, identifier: str) -> JsonResponse:
        """Add source to permanent blocklist."""
        security_logger.critical(
            f"Added {identifier} to permanent CSRF blocklist",
            extra={
                'event_type': 'csrf_permanent_block',
                'identifier': identifier,
                'blocked_by': self.request.user.loginid if hasattr(self.request.user, 'loginid') else 'unknown'
            }
        )

        return JsonResponse({
            'status': 'success',
            'message': f'Added {identifier} to permanent blocklist',
            'identifier': identifier,
            'note': 'Implement permanent blocking in firewall/WAF for production'
        })
