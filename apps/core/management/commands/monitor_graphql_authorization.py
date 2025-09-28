"""
GraphQL Authorization Security Monitoring Command

Real-time monitoring command for GraphQL authorization security events.

Features:
- Continuous monitoring of authorization denials
- Real-time alerting for suspicious patterns
- Automatic detection of attack patterns
- Statistical analysis of authorization events
- Security incident reporting

Usage:
    python manage.py monitor_graphql_authorization
    python manage.py monitor_graphql_authorization --alert-threshold 10
    python manage.py monitor_graphql_authorization --watch-interval 60
    python manage.py monitor_graphql_authorization --export-report

Security Compliance:
- Part of CVSS 7.2 remediation - GraphQL Authorization Gaps
- Provides real-time security visibility
- Enables proactive threat detection
"""

import time
import json
from datetime import timedelta
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.core.cache import cache
from django.conf import settings
import logging


security_logger = logging.getLogger('security')


class Command(BaseCommand):
    help = 'Monitor GraphQL authorization events in real-time'

    def add_arguments(self, parser):
        """Add command arguments."""
        parser.add_argument(
            '--alert-threshold',
            type=int,
            default=10,
            help='Number of denials before alerting'
        )

        parser.add_argument(
            '--watch-interval',
            type=int,
            default=30,
            help='Monitoring interval in seconds'
        )

        parser.add_argument(
            '--export-report',
            action='store_true',
            help='Export monitoring report and exit'
        )

        parser.add_argument(
            '--duration',
            type=int,
            default=3600,
            help='Total monitoring duration in seconds (0 for infinite)'
        )

    def handle(self, *args, **options):
        """Execute the monitoring command."""
        alert_threshold = options['alert_threshold']
        watch_interval = options['watch_interval']
        export_report = options['export_report']
        duration = options['duration']

        if export_report:
            self._export_security_report()
            return

        self.stdout.write(self.style.SUCCESS('Starting GraphQL authorization monitoring...'))
        self.stdout.write(f'Alert threshold: {alert_threshold} denials')
        self.stdout.write(f'Watch interval: {watch_interval} seconds')
        self.stdout.write(f'Duration: {"Infinite" if duration == 0 else f"{duration} seconds"}')
        self.stdout.write('=' * 80)

        start_time = time.time()

        try:
            while True:
                if duration > 0 and (time.time() - start_time) > duration:
                    self.stdout.write(self.style.SUCCESS('\nMonitoring duration completed'))
                    break

                stats = self._collect_stats()

                self._display_stats(stats)

                alerts = self._check_for_alerts(stats, alert_threshold)

                if alerts:
                    self._display_alerts(alerts)

                time.sleep(watch_interval)

        except KeyboardInterrupt:
            self.stdout.write(self.style.WARNING('\n\nMonitoring stopped by user'))
            self._export_final_report()

    def _collect_stats(self) -> Dict[str, Any]:
        """Collect current authorization statistics."""
        since = timezone.now() - timedelta(hours=1)

        auth_denials = cache.get(f'graphql_auth_denials_count:{since.hour}', 0)
        field_denials = cache.get(f'graphql_field_denials_count:{since.hour}', 0)
        object_denials = cache.get(f'graphql_object_denials_count:{since.hour}', 0)
        introspection_attempts = cache.get(f'graphql_introspection_blocked:{since.hour}', 0)
        mutation_violations = cache.get(f'graphql_mutation_chain_violations:{since.hour}', 0)

        return {
            'timestamp': timezone.now().isoformat(),
            'auth_denials': auth_denials,
            'field_denials': field_denials,
            'object_denials': object_denials,
            'introspection_attempts': introspection_attempts,
            'mutation_violations': mutation_violations,
            'total_denials': auth_denials + field_denials + object_denials
        }

    def _display_stats(self, stats: Dict[str, Any]):
        """Display statistics in terminal."""
        self.stdout.write(f"\n[{stats['timestamp']}]")
        self.stdout.write(f"  Auth Denials: {stats['auth_denials']}")
        self.stdout.write(f"  Field Denials: {stats['field_denials']}")
        self.stdout.write(f"  Object Denials: {stats['object_denials']}")
        self.stdout.write(f"  Introspection Blocked: {stats['introspection_attempts']}")
        self.stdout.write(f"  Mutation Chain Violations: {stats['mutation_violations']}")
        self.stdout.write(self.style.WARNING(f"  Total Denials: {stats['total_denials']}"))

    def _check_for_alerts(self, stats: Dict[str, Any], threshold: int) -> List[Dict[str, str]]:
        """Check for alert conditions."""
        alerts = []

        if stats['total_denials'] >= threshold:
            alerts.append({
                'severity': 'high',
                'type': 'denial_threshold_exceeded',
                'message': f"Total denials ({stats['total_denials']}) exceeded threshold ({threshold})",
                'recommendation': 'Investigate for potential attack pattern'
            })

        if stats['introspection_attempts'] > 0:
            alerts.append({
                'severity': 'medium',
                'type': 'introspection_attempt',
                'message': f"{stats['introspection_attempts']} introspection attempts blocked",
                'recommendation': 'Review introspection attempt sources'
            })

        if stats['mutation_violations'] > 0:
            alerts.append({
                'severity': 'high',
                'type': 'mutation_chaining_violation',
                'message': f"{stats['mutation_violations']} mutation chaining violations detected",
                'recommendation': 'Check for automated attack scripts'
            })

        recent_cross_tenant_attempts = cache.get('recent_cross_tenant_attempts', 0)
        if recent_cross_tenant_attempts > 5:
            alerts.append({
                'severity': 'critical',
                'type': 'cross_tenant_attack',
                'message': f"{recent_cross_tenant_attempts} cross-tenant access attempts",
                'recommendation': 'IMMEDIATE ACTION: Potential data breach attempt'
            })

        return alerts

    def _display_alerts(self, alerts: List[Dict[str, str]]):
        """Display security alerts."""
        self.stdout.write('\n' + '=' * 80)
        self.stdout.write(self.style.ERROR('  SECURITY ALERTS'))
        self.stdout.write('=' * 80)

        for alert in alerts:
            severity_style = {
                'critical': self.style.ERROR,
                'high': self.style.WARNING,
                'medium': self.style.NOTICE,
                'low': self.style.HTTP_INFO
            }.get(alert['severity'], self.style.WARNING)

            self.stdout.write(severity_style(f"\n  [{alert['severity'].upper()}] {alert['type']}"))
            self.stdout.write(f"  Message: {alert['message']}")
            self.stdout.write(f"  Recommendation: {alert['recommendation']}")

        self.stdout.write('=' * 80)

    def _export_security_report(self):
        """Export comprehensive security report."""
        self.stdout.write(self.style.SUCCESS('Generating GraphQL security report...'))

        since = timezone.now() - timedelta(hours=24)

        report = {
            'report_date': timezone.now().isoformat(),
            'period': '24 hours',
            'summary': {
                'auth_denials': _get_auth_denial_stats(since),
                'field_denials': _get_field_denial_stats(since),
                'object_denials': _get_object_denial_stats(since),
                'introspection_attempts': _get_introspection_attempt_stats(since),
                'mutation_violations': _get_mutation_chain_violation_stats(since),
            },
            'configuration': {
                'introspection_disabled': getattr(settings, 'GRAPHQL_DISABLE_INTROSPECTION_IN_PRODUCTION', True),
                'max_query_depth': getattr(settings, 'GRAPHQL_MAX_QUERY_DEPTH', 10),
                'max_query_complexity': getattr(settings, 'GRAPHQL_MAX_QUERY_COMPLEXITY', 1000),
                'max_mutations_per_request': getattr(settings, 'GRAPHQL_MAX_MUTATIONS_PER_REQUEST', 5),
                'rate_limit_max': getattr(settings, 'GRAPHQL_RATE_LIMIT_MAX', 100),
            }
        }

        report_json = json.dumps(report, indent=2)
        report_file = f'graphql_security_report_{timezone.now().strftime("%Y%m%d_%H%M%S")}.json'

        with open(report_file, 'w') as f:
            f.write(report_json)

        self.stdout.write(self.style.SUCCESS(f'Report exported to: {report_file}'))

    def _export_final_report(self):
        """Export final monitoring report when stopping."""
        self.stdout.write(self.style.SUCCESS('\nGenerating final monitoring report...'))
        self._export_security_report()