"""
Management command to monitor and report on legacy URL redirect usage.

Usage:
    python manage.py monitor_legacy_redirects
    python manage.py monitor_legacy_redirects --export redirect_stats.json
    python manage.py monitor_legacy_redirects --clear
"""

import json
from django.core.management.base import BaseCommand, CommandError
from apps.core.middleware.legacy_url_redirect import (
    get_redirect_report,
    export_redirect_statistics_json,
    LegacyURLRedirectMiddleware
)


class Command(BaseCommand):
    help = 'Monitor and report on legacy URL redirect usage'

    def add_arguments(self, parser):
        parser.add_argument(
            '--export',
            type=str,
            help='Export statistics to JSON file'
        )
        parser.add_argument(
            '--clear',
            action='store_true',
            help='Clear all redirect statistics'
        )
        parser.add_argument(
            '--format',
            type=str,
            choices=['text', 'json'],
            default='text',
            help='Output format (text or json)'
        )

    def handle(self, *args, **options):
        # Clear statistics if requested
        if options['clear']:
            self.stdout.write(self.style.WARNING('Clearing all redirect statistics...'))
            LegacyURLRedirectMiddleware.clear_redirect_statistics()
            self.stdout.write(self.style.SUCCESS('✓ Statistics cleared'))
            return

        # Export to file if requested
        if options['export']:
            export_file = options['export']
            self.stdout.write(f'Exporting statistics to {export_file}...')

            try:
                stats = export_redirect_statistics_json()
                with open(export_file, 'w') as f:
                    json.dump(stats, f, indent=2)

                self.stdout.write(
                    self.style.SUCCESS(f'✓ Statistics exported to {export_file}')
                )
                self.stdout.write(
                    f"  Total Unique URLs: {stats['total_unique_urls']}"
                )
                self.stdout.write(
                    f"  Total Redirects: {stats['total_redirects']}"
                )

            except Exception as e:
                raise CommandError(f'Error exporting statistics: {e}')

            return

        # Display report
        if options['format'] == 'json':
            stats = export_redirect_statistics_json()
            self.stdout.write(json.dumps(stats, indent=2))
        else:
            report = get_redirect_report()
            self.stdout.write(report)
