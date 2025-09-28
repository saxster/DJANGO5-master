"""
Generate comprehensive health check report.
Provides detailed insights from historical health check logs.
Follows Rule 11: Specific exception handling only.
"""

import json
import logging
from datetime import timedelta
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db import DatabaseError, models
from django.db.models import Count, Avg, Q
from apps.core.models.health_monitoring import HealthCheckLog, ServiceAvailability
from apps.core.services.health_check_service import HealthCheckService

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Generate comprehensive health check report"

    def add_arguments(self, parser):
        parser.add_argument(
            '--hours',
            type=int,
            default=24,
            help='Report time window in hours (default: 24)',
        )
        parser.add_argument(
            '--format',
            type=str,
            choices=['text', 'json'],
            default='text',
            help='Output format (default: text)',
        )
        parser.add_argument(
            '--output',
            type=str,
            help='Output file path (optional)',
        )

    def handle(self, *args, **options):
        hours = options['hours']
        output_format = options['format']
        output_file = options['output']

        health_service = HealthCheckService()

        try:
            report = self._generate_report(health_service, hours)

            if output_format == 'json':
                output = json.dumps(report, indent=2)
            else:
                output = self._format_text_report(report)

            if output_file:
                try:
                    with open(output_file, 'w') as f:
                        f.write(output)
                    self.stdout.write(
                        self.style.SUCCESS(f"Report saved to {output_file}")
                    )
                except (OSError, PermissionError) as e:
                    self.stdout.write(
                        self.style.ERROR(f"Failed to write report file: {e}")
                    )
                    self.stdout.write(output)
            else:
                self.stdout.write(output)

        except DatabaseError as e:
            logger.error(
                f"Failed to generate health report: {e}",
                extra={"error_type": "DatabaseError", "hours": hours},
            )
            self.stdout.write(
                self.style.ERROR(f"Database error generating report: {e}")
            )

        except (ValueError, TypeError) as e:
            logger.error(
                f"Report generation validation error: {e}",
                extra={"error_type": type(e).__name__, "hours": hours},
            )
            self.stdout.write(
                self.style.ERROR(f"Validation error generating report: {e}")
            )

    def _generate_report(self, health_service, hours):
        """Generate report data from health check logs."""
        cutoff_time = timezone.now() - timedelta(hours=hours)

        logs = HealthCheckLog.objects.filter(checked_at__gte=cutoff_time)

        check_summary = logs.values('check_name').annotate(
            total=Count('id'),
            healthy=Count('id', filter=models.Q(status='healthy')),
            degraded=Count('id', filter=models.Q(status='degraded')),
            errors=Count('id', filter=models.Q(status='error')),
            avg_duration_ms=Avg('duration_ms'),
        )

        service_availability = ServiceAvailability.objects.all()

        return {
            "report_period_hours": hours,
            "report_generated_at": timezone.now().isoformat(),
            "total_checks_run": logs.count(),
            "check_summary": list(check_summary),
            "service_availability": [
                {
                    "service_name": service.service_name,
                    "uptime_percentage": service.uptime_percentage,
                    "total_checks": service.total_checks,
                    "successful_checks": service.successful_checks,
                    "failed_checks": service.failed_checks,
                    "degraded_checks": service.degraded_checks,
                }
                for service in service_availability
            ],
        }

    def _format_text_report(self, report):
        """Format report as human-readable text."""
        lines = []
        lines.append("=" * 80)
        lines.append("HEALTH CHECK REPORT")
        lines.append("=" * 80)
        lines.append(f"Report Period: Last {report['report_period_hours']} hours")
        lines.append(f"Generated At: {report['report_generated_at']}")
        lines.append(f"Total Checks Run: {report['total_checks_run']}")
        lines.append("")
        lines.append("CHECK SUMMARY")
        lines.append("-" * 80)

        for check in report['check_summary']:
            lines.append(f"\n{check['check_name']}:")
            lines.append(f"  Total: {check['total']}")
            lines.append(f"  Healthy: {check['healthy']} ({check['healthy']/check['total']*100:.1f}%)")
            lines.append(f"  Degraded: {check['degraded']}")
            lines.append(f"  Errors: {check['errors']}")
            lines.append(f"  Avg Duration: {check['avg_duration_ms']:.2f}ms")

        lines.append("")
        lines.append("SERVICE AVAILABILITY")
        lines.append("-" * 80)

        for service in report['service_availability']:
            lines.append(f"\n{service['service_name']}:")
            lines.append(f"  Uptime: {service['uptime_percentage']:.2f}%")
            lines.append(f"  Total Checks: {service['total_checks']}")
            lines.append(f"  Successful: {service['successful_checks']}")
            lines.append(f"  Failed: {service['failed_checks']}")
            lines.append(f"  Degraded: {service['degraded_checks']}")

        lines.append("")
        lines.append("=" * 80)

        return "\n".join(lines)