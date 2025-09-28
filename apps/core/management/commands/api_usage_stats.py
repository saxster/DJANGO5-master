"""
Django management command to show usage statistics for deprecated APIs.

Usage:
    python manage.py api_usage_stats --endpoint /api/v1/people/ --days 30
    python manage.py api_usage_stats --all

Compliance with .claude/rules.md:
- Rule #11: Specific exception handling
"""

from django.core.management.base import BaseCommand
from apps.core.services.api_deprecation_service import APIDeprecationService
import json


class Command(BaseCommand):
    help = 'Show usage statistics for deprecated API endpoints'

    def add_arguments(self, parser):
        parser.add_argument(
            '--endpoint',
            type=str,
            help='Specific endpoint pattern to analyze'
        )
        parser.add_argument(
            '--days',
            type=int,
            default=7,
            help='Number of days to analyze (default: 7)'
        )
        parser.add_argument(
            '--all',
            action='store_true',
            help='Show stats for all deprecated endpoints'
        )

    def handle(self, *args, **options):
        """Display usage statistics."""
        endpoint = options['endpoint']
        days = options['days']
        show_all = options['all']

        try:
            if show_all:
                self._show_all_stats(days)
            elif endpoint:
                self._show_endpoint_stats(endpoint, days)
            else:
                self.stdout.write(
                    self.style.ERROR('Provide --endpoint or --all')
                )

        except (FileNotFoundError, IOError, OSError, PermissionError) as e:
            self.stdout.write(
                self.style.ERROR(f'Error: {e}')
            )

    def _show_endpoint_stats(self, endpoint, days):
        """Show stats for specific endpoint."""
        stats = APIDeprecationService.get_usage_stats(endpoint, days)

        if not stats:
            self.stdout.write(
                self.style.WARNING(f'No deprecation found for: {endpoint}')
            )
            return

        self.stdout.write(f"\n📊 Usage Statistics for {endpoint}\n")
        self.stdout.write(f"Period: Last {days} days")
        self.stdout.write(f"Total Requests: {stats['total_usage']}")
        self.stdout.write(f"Unique Clients: {stats['unique_clients']}")

        if stats.get('days_until_sunset'):
            self.stdout.write(
                self.style.WARNING(
                    f"⚠️  Days Until Sunset: {stats['days_until_sunset']}"
                )
            )

        self.stdout.write(f"\nReplacement: {stats['replacement']}")

        if stats.get('clients_breakdown'):
            self.stdout.write('\n Client Versions:')
            for client in stats['clients_breakdown']:
                self.stdout.write(
                    f"  - {client['client_version']}: {client['count']} requests"
                )

    def _show_all_stats(self, days):
        """Show stats for all deprecated endpoints."""
        deprecated = APIDeprecationService.get_deprecated_endpoints()

        if not deprecated:
            self.stdout.write(
                self.style.SUCCESS('✅ No deprecated endpoints')
            )
            return

        self.stdout.write(f"\n📊 All Deprecated Endpoints (Last {days} days)\n")

        for dep in deprecated:
            stats = APIDeprecationService.get_usage_stats(dep.endpoint_pattern, days)
            usage = stats.get('total_usage', 0)

            status_style = self.style.WARNING if usage > 100 else self.style.SUCCESS

            self.stdout.write(
                status_style(
                    f"{dep.endpoint_pattern:<40} {usage:>6} requests"
                )
            )