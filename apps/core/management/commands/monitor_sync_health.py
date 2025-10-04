"""
Management command for monitoring sync system health.

Usage:
    python manage.py monitor_sync_health
    python manage.py monitor_sync_health --tenant 123 --hours 24
    python manage.py monitor_sync_health --webhook https://alerts.example.com/webhook
    python manage.py monitor_sync_health --continuous --interval 300

Follows .claude/rules.md:
- Rule #8: View methods < 30 lines
- Rule #11: Specific exception handling
"""

import time
import logging
from django.core.management.base import BaseCommand, CommandError
from django.conf import settings

from apps.core.services.sync_health_monitoring_service import sync_health_monitor

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Monitor sync system health and send alerts'

    def add_arguments(self, parser):
        parser.add_argument(
            '--tenant',
            type=int,
            help='Tenant ID to monitor (default: all tenants)',
        )
        parser.add_argument(
            '--hours',
            type=int,
            default=1,
            help='Time window in hours to analyze (default: 1)',
        )
        parser.add_argument(
            '--webhook',
            type=str,
            help='Webhook URL for alerts',
        )
        parser.add_argument(
            '--slack-webhook',
            type=str,
            help='Slack webhook URL for alerts',
        )
        parser.add_argument(
            '--continuous',
            action='store_true',
            help='Run continuously (for background monitoring)',
        )
        parser.add_argument(
            '--interval',
            type=int,
            default=300,
            help='Check interval in seconds for continuous mode (default: 300)',
        )
        parser.add_argument(
            '--alert-threshold',
            type=str,
            choices=['any', 'warning', 'critical'],
            default='warning',
            help='Minimum severity to send alerts (default: warning)',
        )

    def handle(self, *args, **options):
        tenant_id = options.get('tenant')
        hours = options.get('hours')
        webhook_url = options.get('webhook') or getattr(settings, 'SYNC_ALERT_WEBHOOK', None)
        slack_webhook = options.get('slack_webhook') or getattr(settings, 'SYNC_SLACK_WEBHOOK', None)
        continuous = options.get('continuous')
        interval = options.get('interval')
        alert_threshold = options.get('alert_threshold')

        self.stdout.write(self.style.SUCCESS('[Sync Health Monitor]'))
        self.stdout.write(f"Tenant: {tenant_id or 'All'}")
        self.stdout.write(f"Time window: {hours} hours")
        self.stdout.write(f"Alert threshold: {alert_threshold}")

        if continuous:
            self.stdout.write(f"Running in continuous mode (interval: {interval}s)")
            self._run_continuous(tenant_id, hours, webhook_url, slack_webhook,
                               alert_threshold, interval)
        else:
            self._run_once(tenant_id, hours, webhook_url, slack_webhook,
                          alert_threshold)

    def _run_once(self, tenant_id, hours, webhook_url, slack_webhook,
                  alert_threshold):
        """Run health check once and exit."""
        try:
            health_summary = sync_health_monitor.check_sync_health(
                tenant_id=tenant_id,
                hours=hours
            )

            self._display_health_summary(health_summary)
            self._send_alerts(health_summary, webhook_url, slack_webhook,
                            alert_threshold)

        except (ValueError, IOError) as e:
            raise CommandError(f"Health check failed: {e}")

    def _run_continuous(self, tenant_id, hours, webhook_url, slack_webhook,
                       alert_threshold, interval):
        """Run health check continuously."""
        self.stdout.write(self.style.WARNING("Press Ctrl+C to stop"))

        try:
            while True:
                try:
                    health_summary = sync_health_monitor.check_sync_health(
                        tenant_id=tenant_id,
                        hours=hours
                    )

                    self._display_health_summary(health_summary)
                    self._send_alerts(health_summary, webhook_url, slack_webhook,
                                    alert_threshold)

                except (ValueError, IOError) as e:
                    self.stdout.write(self.style.ERROR(f"Check failed: {e}"))

                self.stdout.write(f"\nNext check in {interval} seconds...")
                time.sleep(interval)

        except KeyboardInterrupt:
            self.stdout.write(self.style.SUCCESS("\nMonitoring stopped"))

    def _display_health_summary(self, health_summary):
        """Display health summary in terminal."""
        if 'error' in health_summary:
            self.stdout.write(self.style.ERROR(f"ERROR: {health_summary['error']}"))
            return

        status = health_summary['health_status']
        style = {
            'healthy': self.style.SUCCESS,
            'degraded': self.style.WARNING,
            'critical': self.style.ERROR,
        }.get(status, self.style.WARNING)

        self.stdout.write("\n" + "=" * 60)
        self.stdout.write(style(f"Health Status: {status.upper()}"))
        self.stdout.write("=" * 60)

        metrics = health_summary.get('metrics', {})
        self.stdout.write("\nMetrics:")
        self.stdout.write(f"  Success Rate:         {metrics.get('success_rate', 0):.1f}%")
        self.stdout.write(f"  Conflict Rate:        {metrics.get('conflict_rate', 0):.1f}%")
        self.stdout.write(f"  Avg Sync Duration:    {metrics.get('avg_sync_duration_ms', 0):.1f}ms")
        self.stdout.write(f"  Failed Syncs/Minute:  {metrics.get('failed_syncs_per_minute', 0):.1f}")
        self.stdout.write(f"  Upload Abandonment:   {metrics.get('upload_abandonment_rate', 0):.1f}%")
        self.stdout.write(f"  Avg Device Health:    {metrics.get('avg_device_health_score', 0):.1f}")

        alerts = health_summary.get('alerts', [])
        if alerts:
            self.stdout.write(f"\nAlerts ({len(alerts)}):")
            for alert in alerts:
                alert_style = {
                    'critical': self.style.ERROR,
                    'warning': self.style.WARNING,
                    'info': self.style.SUCCESS,
                }.get(alert['severity'], self.style.WARNING)

                self.stdout.write(
                    alert_style(f"  [{alert['severity'].upper()}] {alert['message']}")
                )
        else:
            self.stdout.write(self.style.SUCCESS("\nNo alerts - system healthy"))

    def _send_alerts(self, health_summary, webhook_url, slack_webhook,
                    alert_threshold):
        """Send alerts based on threshold."""
        alerts = health_summary.get('alerts', [])
        if not alerts:
            return

        severity_levels = {'any': 0, 'warning': 1, 'critical': 2}
        threshold_level = severity_levels.get(alert_threshold, 1)

        severity_map = {'info': 0, 'warning': 1, 'critical': 2}

        alerts_to_send = [
            alert for alert in alerts
            if severity_map.get(alert['severity'], 0) >= threshold_level
        ]

        if not alerts_to_send:
            self.stdout.write("No alerts meet threshold - skipping notifications")
            return

        for alert_data in alerts_to_send:
            from apps.core.services.sync_health_monitoring_service import SyncHealthAlert

            alert = SyncHealthAlert(
                severity=alert_data['severity'],
                metric=alert_data['metric'],
                current_value=alert_data['current_value'],
                threshold=alert_data['threshold'],
                message=alert_data['message']
            )

            success = sync_health_monitor.send_alert(
                alert,
                webhook_url=webhook_url,
                slack_webhook=slack_webhook
            )

            if success:
                self.stdout.write(self.style.SUCCESS(f"Alert sent: {alert.metric}"))
            else:
                self.stdout.write(self.style.WARNING(f"Failed to send alert: {alert.metric}"))