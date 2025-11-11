"""
Django management command to reload anomaly detection rules.

Usage:
    python manage.py reload_anomaly_rules

This command invalidates the cached YAML rules and forces a reload
on the next detector instantiation. Useful after editing rules/anomalies.yaml
without restarting Celery workers.
"""

from django.core.management.base import BaseCommand
from apps.issue_tracker.services.anomaly_detector import reload_anomaly_rules


class Command(BaseCommand):
    help = 'Reload anomaly detection rules from YAML (invalidate cache)'

    def handle(self, *args, **options):
        """Execute the command."""
        self.stdout.write("Reloading anomaly detection rules...")

        # Invalidate the cache
        reload_anomaly_rules()

        self.stdout.write(
            self.style.SUCCESS(
                '✅ Anomaly detection rules cache invalidated. '
                'Rules will be reloaded on next detector access.'
            )
        )
        self.stdout.write(
            '\nNote: This invalidates the module-level cache. '
            'The YAML file will be read from disk on the next '
            'AnomalyDetector instantiation.'
        )
