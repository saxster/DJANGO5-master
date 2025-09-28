"""
Generate File Upload Security Report

Management command for generating comprehensive file upload security reports.

Usage:
    python manage.py generate_file_upload_report
    python manage.py generate_file_upload_report --days 30 --format json
    python manage.py generate_file_upload_report --export-siem
"""

from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from apps.core.services.file_upload_audit_service import FileUploadAuditService


class Command(BaseCommand):
    help = 'Generate file upload security and compliance reports'

    def add_arguments(self, parser):
        parser.add_argument(
            '--days',
            type=int,
            default=7,
            help='Number of days to include in report (default: 7)'
        )
        parser.add_argument(
            '--format',
            choices=['text', 'json', 'csv'],
            default='text',
            help='Report output format'
        )
        parser.add_argument(
            '--export-siem',
            action='store_true',
            help='Export to SIEM format'
        )
        parser.add_argument(
            '--siem-format',
            choices=['json', 'cef', 'syslog'],
            default='json',
            help='SIEM export format'
        )
        parser.add_argument(
            '--output-file',
            type=str,
            help='Output file path (default: stdout)'
        )

    def handle(self, *args, **options):
        """Generate report based on options."""

        if options['export_siem']:
            self.export_siem(options['siem_format'], options['days'], options.get('output_file'))
        else:
            self.generate_report(options['days'], options['format'], options.get('output_file'))

    def generate_report(self, days, format, output_file):
        """Generate standard compliance report."""
        self.stdout.write(self.style.HTTP_INFO(f'📊 Generating {days}-day file upload report...'))

        end_date = timezone.now()
        start_date = end_date - timedelta(days=days)

        report = FileUploadAuditService.generate_compliance_report(start_date, end_date)

        if not report:
            self.stdout.write(self.style.ERROR('❌ Failed to generate report'))
            return

        if format == 'json':
            output = self._format_json(report)
        elif format == 'csv':
            output = self._format_csv(report)
        else:
            output = self._format_text(report)

        if output_file:
            with open(output_file, 'w') as f:
                f.write(output)
            self.stdout.write(self.style.SUCCESS(f'✅ Report saved to {output_file}'))
        else:
            self.stdout.write(output)

    def export_siem(self, siem_format, days, output_file):
        """Export audit logs to SIEM format."""
        self.stdout.write(self.style.HTTP_INFO(f'📤 Exporting to SIEM format: {siem_format}...'))

        end_date = timezone.now()
        start_date = end_date - timedelta(days=days)

        export_data = FileUploadAuditService.export_to_siem(
            format=siem_format,
            start_date=start_date,
            end_date=end_date
        )

        if not export_data:
            self.stdout.write(self.style.ERROR('❌ SIEM export failed'))
            return

        if output_file:
            with open(output_file, 'w') as f:
                f.write(export_data)
            self.stdout.write(self.style.SUCCESS(f'✅ SIEM data exported to {output_file}'))
        else:
            self.stdout.write(export_data)

    def check_and_send_alerts(self):
        """Check for security alerts."""
        self.stdout.write(self.style.HTTP_INFO('🚨 Checking for security alerts...'))

        incidents = FileUploadAuditService.get_security_incidents(hours=1)

        if incidents:
            self.stdout.write(
                self.style.ERROR(f'❌ Found {len(incidents)} security incidents')
            )
            for incident in incidents[:5]:
                self.stdout.write(
                    f"  - {incident['event_type']}: {incident['filename']}"
                )
        else:
            self.stdout.write(self.style.SUCCESS('✅ No recent security incidents'))

    def cleanup_old_logs(self):
        """Cleanup old audit logs."""
        self.stdout.write(self.style.HTTP_INFO('🧹 Cleaning up old audit logs...'))

        deleted = FileUploadAuditService.cleanup_old_logs(retention_days=90)

        self.stdout.write(self.style.SUCCESS(f'✅ Deleted {deleted} old audit log entries'))

    def _format_text(self, report):
        """Format report as text."""
        import json
        return json.dumps(report, indent=2)

    def _format_json(self, report):
        """Format report as JSON."""
        import json
        return json.dumps(report, indent=2)

    def _format_csv(self, report):
        """Format report as CSV."""
        return "CSV format not yet implemented"