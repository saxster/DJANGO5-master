"""
Management Command: Scan Journal PII

Scans journal and wellness data for accidental PII exposure.
Generates detailed reports and alerts admins to potential issues.

Usage:
    # Scan last 30 days
    python manage.py scan_journal_pii

    # Scan last 90 days with detailed report
    python manage.py scan_journal_pii --days 90 --report

    # Scan specific number of entries
    python manage.py scan_journal_pii --max-entries 1000

    # Save report to file
    python manage.py scan_journal_pii --output pii_scan_report.json

Author: Claude Code
Date: 2025-10-01
"""

import json
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from apps.journal.services.pii_detection_service import PIIDetectionScanner
from apps.journal.logging import get_journal_logger

logger = get_journal_logger(__name__)


class Command(BaseCommand):
    help = 'Scan journal and wellness data for accidental PII exposure'

    def add_arguments(self, parser):
        """Add command arguments."""
        parser.add_argument(
            '--days',
            type=int,
            default=30,
            help='Number of days to scan back (default: 30)'
        )

        parser.add_argument(
            '--max-entries',
            type=int,
            default=None,
            help='Maximum entries to scan (default: all)'
        )

        parser.add_argument(
            '--report',
            action='store_true',
            help='Generate detailed report'
        )

        parser.add_argument(
            '--output',
            type=str,
            default=None,
            help='Save report to JSON file'
        )

        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Verbose output'
        )

    def handle(self, *args, **options):
        """Execute command."""
        days = options['days']
        max_entries = options['max_entries']
        generate_report = options['report']
        output_file = options['output']
        verbose = options['verbose']

        self.stdout.write(self.style.SUCCESS('\n=== PII Detection Scanner ===\n'))

        # Initialize scanner
        scanner = PIIDetectionScanner()

        # Run scan
        self.stdout.write(f'Scanning journal entries (last {days} days)...')

        try:
            results = scanner.scan_all_journal_entries(
                days_back=days,
                max_entries=max_entries
            )
        except (ValueError, TypeError, AttributeError) as e:
            raise CommandError(f'Scan failed: {e}')

        # Display summary
        self._display_summary(results)

        # Display detailed report if requested
        if generate_report or verbose:
            self._display_detailed_report(results)

        # Save to file if requested
        if output_file:
            self._save_report(results, output_file)

        # Display recommendations
        self._display_recommendations(results)

        self.stdout.write(self.style.SUCCESS('\n✓ Scan complete\n'))

    def _display_summary(self, results):
        """Display scan summary."""
        summary = results['scan_summary']

        self.stdout.write('\n--- Scan Summary ---')
        self.stdout.write(f"Total entries scanned: {summary['total_entries_scanned']}")
        self.stdout.write(f"Entries with PII: {summary['entries_with_pii']}")
        self.stdout.write(f"Total PII instances: {summary['total_pii_instances']}")
        self.stdout.write(f"Detection rate: {summary['pii_detection_rate']:.2f}%")

    def _display_detailed_report(self, results):
        """Display detailed PII breakdown."""
        self.stdout.write('\n--- PII by Severity ---')
        for severity, count in results['pii_by_severity'].items():
            if count > 0:
                style = self._get_severity_style(severity)
                self.stdout.write(f"{severity.upper()}: {count}", style)

        self.stdout.write('\n--- PII by Type ---')
        for pii_type, count in results['pii_by_type'].items():
            self.stdout.write(f"{pii_type}: {count}")

    def _save_report(self, results, output_file):
        """Save report to JSON file."""
        try:
            with open(output_file, 'w') as f:
                json.dump(results, f, indent=2)

            self.stdout.write(
                self.style.SUCCESS(f'\n✓ Report saved to {output_file}')
            )
        except IOError as e:
            self.stdout.write(
                self.style.ERROR(f'\n✗ Failed to save report: {e}')
            )

    def _display_recommendations(self, results):
        """Display recommendations based on scan results."""
        summary = results['scan_summary']
        severity = results['pii_by_severity']

        self.stdout.write('\n--- Recommendations ---')

        # Critical findings
        if severity.get('critical', 0) > 0:
            self.stdout.write(
                self.style.ERROR(
                    f"⚠ CRITICAL: {severity['critical']} instances of SSN/credit card found!"
                )
            )
            self.stdout.write('  → Review and redact immediately')
            self.stdout.write('  → Notify affected users')
            self.stdout.write('  → Update privacy policies')

        # High findings
        if severity.get('high', 0) > 0:
            self.stdout.write(
                self.style.WARNING(
                    f"⚠ HIGH: {severity['high']} instances of email/phone found"
                )
            )
            self.stdout.write('  → Review journal entry guidelines')
            self.stdout.write('  → Consider input validation')

        # No findings
        if summary['entries_with_pii'] == 0:
            self.stdout.write(
                self.style.SUCCESS('✓ No PII detected - good security hygiene!')
            )

        # General recommendations
        self.stdout.write('\nGeneral Recommendations:')
        self.stdout.write('  • Run this scan monthly')
        self.stdout.write('  • Update user privacy training')
        self.stdout.write('  • Enable PII redaction middleware')
        self.stdout.write('  • Review input validation rules')

    def _get_severity_style(self, severity):
        """Get style for severity level."""
        if severity == 'critical':
            return self.style.ERROR
        elif severity == 'high':
            return self.style.WARNING
        else:
            return self.style.SUCCESS
