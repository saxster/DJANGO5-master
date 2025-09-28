"""
Django management command to generate API deprecation reports.

Usage:
    python manage.py api_deprecation_report
    python manage.py api_deprecation_report --format json
    python manage.py api_deprecation_report --sunset-only

Compliance with .claude/rules.md:
- Rule #11: Specific exception handling
- Rule #15: No sensitive data in output
"""

from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from apps.core.models.api_deprecation import APIDeprecation, APIDeprecationUsage
from apps.core.services.api_deprecation_service import APIDeprecationService
import json


class Command(BaseCommand):
    help = 'Generate API deprecation report'

    def add_arguments(self, parser):
        parser.add_argument(
            '--format',
            type=str,
            default='table',
            choices=['table', 'json', 'csv'],
            help='Output format'
        )
        parser.add_argument(
            '--sunset-only',
            action='store_true',
            help='Show only endpoints in sunset warning period'
        )

    def handle(self, *args, **options):
        """Generate and display deprecation report."""
        output_format = options['format']
        sunset_only = options['sunset_only']

        try:
            if sunset_only:
                endpoints = APIDeprecationService.get_sunset_warnings()
                self.stdout.write(self.style.WARNING('\n🚨 SUNSET WARNINGS\n'))
            else:
                endpoints = APIDeprecationService.get_deprecated_endpoints()
                self.stdout.write(self.style.WARNING('\n📋 DEPRECATED API ENDPOINTS\n'))

            if not endpoints:
                self.stdout.write(self.style.SUCCESS('✅ No deprecated endpoints found'))
                return

            if output_format == 'json':
                self._output_json(endpoints)
            elif output_format == 'csv':
                self._output_csv(endpoints)
            else:
                self._output_table(endpoints)

        except (FileNotFoundError, IOError, OSError, PermissionError) as e:
            self.stdout.write(self.style.ERROR(f'Error generating report: {e}'))

    def _output_table(self, endpoints):
        """Output in table format."""
        self.stdout.write(
            f"{'Endpoint':<40} {'Type':<15} {'Status':<20} {'Sunset':<15} {'Replacement':<30}"
        )
        self.stdout.write('-' * 120)

        for endpoint in endpoints:
            sunset_str = endpoint.sunset_date.date() if endpoint.sunset_date else 'N/A'
            days_left = (endpoint.sunset_date - timezone.now()).days if endpoint.sunset_date else '-'

            status_str = f"{endpoint.status} ({days_left}d)" if days_left != '-' else endpoint.status

            self.stdout.write(
                f"{endpoint.endpoint_pattern:<40} "
                f"{endpoint.api_type:<15} "
                f"{status_str:<20} "
                f"{sunset_str:<15} "
                f"{endpoint.replacement_endpoint or 'N/A':<30}"
            )

    def _output_json(self, endpoints):
        """Output in JSON format."""
        data = [
            {
                'endpoint': e.endpoint_pattern,
                'api_type': e.api_type,
                'status': e.status,
                'deprecated_date': e.deprecated_date.isoformat(),
                'sunset_date': e.sunset_date.isoformat() if e.sunset_date else None,
                'replacement': e.replacement_endpoint,
                'migration_url': e.migration_url,
            }
            for e in endpoints
        ]
        self.stdout.write(json.dumps(data, indent=2))

    def _output_csv(self, endpoints):
        """Output in CSV format."""
        self.stdout.write('endpoint,api_type,status,deprecated_date,sunset_date,replacement,migration_url')

        for e in endpoints:
            self.stdout.write(
                f'"{e.endpoint_pattern}",'
                f'{e.api_type},'
                f'{e.status},'
                f'{e.deprecated_date.isoformat()},'
                f'{e.sunset_date.isoformat() if e.sunset_date else ""},'
                f'"{e.replacement_endpoint or ""}",'
                f'"{e.migration_url or ""}"'
            )