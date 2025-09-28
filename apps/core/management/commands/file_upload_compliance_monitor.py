"""
File Upload Compliance Monitoring Management Command

Automated compliance monitoring and reporting for file upload security.
Runs periodic scans and generates compliance reports.

Usage:
    python manage.py file_upload_compliance_monitor --scan
    python manage.py file_upload_compliance_monitor --report
    python manage.py file_upload_compliance_monitor --alert-check
"""

import json
import logging
from datetime import timedelta
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.core.mail import send_mail
from django.conf import settings
from apps.core.services.file_upload_audit_service import FileUploadAuditService, FileUploadAuditLog

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Monitor file upload compliance and generate security reports'

    def add_arguments(self, parser):
        parser.add_argument(
            '--scan',
            action='store_true',
            help='Scan codebase for file upload vulnerabilities'
        )
        parser.add_argument(
            '--report',
            action='store_true',
            help='Generate compliance report'
        )
        parser.add_argument(
            '--alert-check',
            action='store_true',
            help='Check for security alerts and send notifications'
        )
        parser.add_argument(
            '--cleanup',
            action='store_true',
            help='Cleanup old audit logs based on retention policy'
        )
        parser.add_argument(
            '--days',
            type=int,
            default=7,
            help='Number of days for report generation'
        )

    def handle(self, *args, **options):
        """Execute compliance monitoring tasks."""

        if options['scan']:
            self.run_vulnerability_scan()

        if options['report']:
            self.generate_compliance_report(options['days'])

        if options['alert_check']:
            self.check_and_send_alerts()

        if options['cleanup']:
            self.cleanup_old_logs()

        if not any([options['scan'], options['report'], options['alert_check'], options['cleanup']]):
            self.stdout.write(
                self.style.WARNING('No action specified. Use --scan, --report, --alert-check, or --cleanup')
            )
            self.stdout.write('Run with --help for usage information')

    def run_vulnerability_scan(self):
        """Run automated vulnerability scan."""
        self.stdout.write(self.style.HTTP_INFO('🔍 Running file upload vulnerability scan...'))

        import subprocess
        result = subprocess.run(
            ['python', 'scripts/scan_file_upload_vulnerabilities.py', '--detailed'],
            capture_output=True,
            text=True
        )

        self.stdout.write(result.stdout)

        if result.returncode == 0:
            self.stdout.write(self.style.SUCCESS('✅ Vulnerability scan passed - no issues found'))
        else:
            self.stdout.write(self.style.ERROR(f'❌ Vulnerability scan failed - {result.returncode} issues found'))
            self.stdout.write(result.stderr)

            self._send_security_alert(
                subject='File Upload Vulnerability Scan Failed',
                message=f'Vulnerability scan detected issues:\n\n{result.stdout}'
            )

    def generate_compliance_report(self, days):
        """Generate and display compliance report."""
        self.stdout.write(self.style.HTTP_INFO(f'📊 Generating compliance report for last {days} days...'))

        end_date = timezone.now()
        start_date = end_date - timedelta(days=days)

        report = FileUploadAuditService.generate_compliance_report(start_date, end_date)

        if report:
            self.stdout.write(self.style.SUCCESS('\n' + '=' * 80))
            self.stdout.write(self.style.SUCCESS('FILE UPLOAD COMPLIANCE REPORT'))
            self.stdout.write(self.style.SUCCESS('=' * 80))
            self.stdout.write(f"Period: {start_date.date()} to {end_date.date()}")
            self.stdout.write(f"Total Events: {report['total_events']}")
            self.stdout.write(f"Security Incidents: {report['security_incidents']}")
            self.stdout.write(f"Malware Detections: {report['malware_detections']}")
            self.stdout.write(f"Path Traversal Attempts: {report['path_traversal_attempts']}")
            self.stdout.write(f"Unique Users: {report['unique_users']}")
            self.stdout.write(f"Total Data Uploaded: {report['total_data_uploaded_mb']:.2f} MB")
            self.stdout.write('\nCompliance Metrics:')
            self.stdout.write(f"  Authentication Rate: {report['compliance_metrics']['authentication_rate']}%")
            self.stdout.write(f"  Validation Rate: {report['compliance_metrics']['validation_rate']}%")
            self.stdout.write(self.style.SUCCESS('=' * 80))

            if report['security_incidents'] > 0:
                self.stdout.write(
                    self.style.WARNING(f'\n⚠️  {report["security_incidents"]} security incidents require review')
                )

        else:
            self.stdout.write(self.style.ERROR('❌ Failed to generate compliance report'))

    def check_and_send_alerts(self):
        """Check for security alerts and send notifications."""
        self.stdout.write(self.style.HTTP_INFO('🚨 Checking for security alerts...'))

        hours = 1
        incidents = FileUploadAuditService.get_security_incidents(hours=hours)

        if incidents:
            self.stdout.write(
                self.style.ERROR(f'❌ Found {len(incidents)} security incidents in last {hours} hour(s)')
            )

            for incident in incidents[:5]:
                self.stdout.write(
                    f"  - {incident['event_type']}: {incident['filename']} "
                    f"by {incident.get('user__peoplename', 'Anonymous')} "
                    f"from {incident.get('ip_address', 'unknown')}"
                )

            self._send_security_alert(
                subject=f'File Upload Security Alert - {len(incidents)} incidents',
                message=self._format_incidents_email(incidents)
            )

        else:
            self.stdout.write(self.style.SUCCESS('✅ No security incidents in last hour'))

    def cleanup_old_logs(self):
        """Cleanup old audit logs based on retention policy."""
        self.stdout.write(self.style.HTTP_INFO('🧹 Cleaning up old audit logs...'))

        retention_days = getattr(settings, 'AUDIT_LOG_RETENTION_DAYS', 90)

        deleted_count = FileUploadAuditService.cleanup_old_logs(retention_days=retention_days)

        self.stdout.write(
            self.style.SUCCESS(f'✅ Deleted {deleted_count} old audit logs (retention: {retention_days} days)')
        )

    def _send_security_alert(self, subject, message):
        """Send security alert email."""
        try:
            recipient_list = getattr(settings, 'SECURITY_ALERT_EMAILS', [])

            if not recipient_list:
                logger.warning('No security alert email recipients configured')
                return

            send_mail(
                subject=f'[SECURITY] {subject}',
                message=message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=recipient_list,
                fail_silently=False,
            )

            logger.info(f'Security alert sent: {subject}')

        except (FileNotFoundError, IOError, OSError, PermissionError) as e:
            logger.error(
                f'Failed to send security alert: {e}',
                extra={'subject': subject}
            )

    def _format_incidents_email(self, incidents):
        """Format incidents for email notification."""
        lines = [
            'File Upload Security Incidents Detected',
            '=' * 80,
            f'Total Incidents: {len(incidents)}',
            f'Timestamp: {timezone.now().isoformat()}',
            '',
            'Incident Details:',
            ''
        ]

        for incident in incidents[:10]:
            lines.append(f"- {incident['timestamp']}")
            lines.append(f"  Event: {incident['event_type']}")
            lines.append(f"  Severity: {incident['severity']}")
            lines.append(f"  User: {incident.get('user__peoplename', 'Anonymous')}")
            lines.append(f"  IP: {incident.get('ip_address', 'unknown')}")
            lines.append(f"  File: {incident['filename']}")
            lines.append(f"  Error: {incident.get('error_message', 'N/A')}")
            lines.append(f"  Correlation ID: {incident['correlation_id']}")
            lines.append('')

        if len(incidents) > 10:
            lines.append(f'... and {len(incidents) - 10} more incidents')

        lines.append('')
        lines.append('Dashboard: https://yourdomain.com/security/file-upload/dashboard/')

        return '\n'.join(lines)