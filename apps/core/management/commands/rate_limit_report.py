"""
Rate Limiting Security Report Command

Generates comprehensive security reports for rate limiting activity:
- Top violating IPs
- Attack pattern analysis
- Blocked IPs summary
- Recommended actions

Usage:
    python manage.py rate_limit_report
    python manage.py rate_limit_report --hours=24
    python manage.py rate_limit_report --export=json
"""

import json
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db.models import Count
from datetime import timedelta
from apps.core.models.rate_limiting import (
    RateLimitBlockedIP,
    RateLimitTrustedIP,
    RateLimitViolationLog
)


class Command(BaseCommand):
    help = 'Generate rate limiting security report'

    def add_arguments(self, parser):
        parser.add_argument(
            '--hours',
            type=int,
            default=24,
            help='Number of hours to analyze (default: 24)'
        )

        parser.add_argument(
            '--export',
            type=str,
            choices=['json', 'text'],
            default='text',
            help='Export format (default: text)'
        )

        parser.add_argument(
            '--top',
            type=int,
            default=10,
            help='Number of top violators to show (default: 10)'
        )

    def handle(self, *args, **options):
        hours = options['hours']
        export_format = options['export']
        top_n = options['top']

        cutoff = timezone.now() - timedelta(hours=hours)

        report_data = self._generate_report(cutoff, top_n)

        if export_format == 'json':
            self._export_json(report_data)
        else:
            self._display_text_report(report_data, hours)

    def _generate_report(self, cutoff, top_n):
        """Generate report data."""
        total_violations = RateLimitViolationLog.objects.filter(
            timestamp__gte=cutoff
        ).count()

        unique_ips = RateLimitViolationLog.objects.filter(
            timestamp__gte=cutoff
        ).values('client_ip').distinct().count()

        top_ips = list(
            RateLimitViolationLog.objects.filter(
                timestamp__gte=cutoff
            ).values('client_ip').annotate(
                violation_count=Count('id')
            ).order_by('-violation_count')[:top_n]
        )

        endpoint_distribution = list(
            RateLimitViolationLog.objects.filter(
                timestamp__gte=cutoff
            ).values('endpoint_type').annotate(
                count=Count('id')
            ).order_by('-count')
        )

        blocked_ips = RateLimitBlockedIP.objects.filter(
            is_active=True,
            blocked_until__gt=timezone.now()
        ).count()

        trusted_ips = RateLimitTrustedIP.objects.filter(
            is_active=True
        ).count()

        authenticated_violations = RateLimitViolationLog.objects.filter(
            timestamp__gte=cutoff,
            user__isnull=False
        ).count()

        return {
            'summary': {
                'total_violations': total_violations,
                'unique_ips': unique_ips,
                'blocked_ips': blocked_ips,
                'trusted_ips': trusted_ips,
                'authenticated_violations': authenticated_violations,
                'anonymous_violations': total_violations - authenticated_violations
            },
            'top_violating_ips': top_ips,
            'endpoint_distribution': endpoint_distribution
        }

    def _display_text_report(self, data, hours):
        """Display report in text format."""
        self.stdout.write(self.style.SUCCESS('=' * 80))
        self.stdout.write(self.style.SUCCESS(f'RATE LIMITING SECURITY REPORT (Last {hours} hours)'))
        self.stdout.write(self.style.SUCCESS('=' * 80))
        self.stdout.write()

        summary = data['summary']

        self.stdout.write(self.style.HTTP_INFO('📊 SUMMARY'))
        self.stdout.write(f"  Total Violations:        {summary['total_violations']}")
        self.stdout.write(f"  Unique IPs:              {summary['unique_ips']}")
        self.stdout.write(f"  Currently Blocked IPs:   {summary['blocked_ips']}")
        self.stdout.write(f"  Trusted IPs:             {summary['trusted_ips']}")
        self.stdout.write(f"  Authenticated Attacks:   {summary['authenticated_violations']}")
        self.stdout.write(f"  Anonymous Attacks:       {summary['anonymous_violations']}")
        self.stdout.write()

        if data['top_violating_ips']:
            self.stdout.write(self.style.WARNING('🚨 TOP VIOLATING IPs'))
            for i, ip_data in enumerate(data['top_violating_ips'], 1):
                self.stdout.write(
                    f"  {i}. {ip_data['client_ip']:<20} - {ip_data['violation_count']} violations"
                )
            self.stdout.write()

        if data['endpoint_distribution']:
            self.stdout.write(self.style.HTTP_INFO('🎯 ENDPOINT DISTRIBUTION'))
            for endpoint in data['endpoint_distribution']:
                self.stdout.write(
                    f"  {endpoint['endpoint_type']:<15} - {endpoint['count']} violations"
                )
            self.stdout.write()

        self._display_recommendations(data)

    def _display_recommendations(self, data):
        """Display security recommendations."""
        self.stdout.write(self.style.HTTP_INFO('💡 RECOMMENDATIONS'))

        summary = data['summary']

        if summary['total_violations'] > 100:
            self.stdout.write(
                self.style.WARNING('  ⚠️  High volume of violations detected - possible attack in progress')
            )

        if summary['blocked_ips'] > 10:
            self.stdout.write(
                self.style.WARNING('  ⚠️  Many blocked IPs - review for coordinated attack patterns')
            )

        if summary['unique_ips'] > 50:
            self.stdout.write(
                self.style.ERROR('  🚨 CRITICAL: Distributed attack detected - escalate to infrastructure team')
            )

        if data['top_violating_ips']:
            top_ip = data['top_violating_ips'][0]
            if top_ip['violation_count'] > 50:
                self.stdout.write(
                    self.style.ERROR(
                        f"  🚨 CRITICAL: IP {top_ip['client_ip']} has {top_ip['violation_count']} violations - investigate immediately"
                    )
                )

        if summary['total_violations'] == 0:
            self.stdout.write(self.style.SUCCESS('  ✅ No violations detected - system operating normally'))

        self.stdout.write()

    def _export_json(self, data):
        """Export report as JSON."""
        print(json.dumps(data, indent=2, default=str))