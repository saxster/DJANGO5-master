"""
List Monitoring API Keys

Management command to list and inspect monitoring API keys.

Features:
- List all monitoring keys
- Filter by system type
- Show keys needing rotation
- Display usage statistics

Usage:
    python manage.py list_monitoring_keys
    python manage.py list_monitoring_keys --needs-rotation
    python manage.py list_monitoring_keys --system prometheus

Author: Security Enhancement Team
Date: 2025-09-27
"""

import logging
from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.core.models.monitoring_api_key import MonitoringAPIKey

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'List monitoring API keys'

    def add_arguments(self, parser):
        parser.add_argument(
            '--system',
            type=str,
            help='Filter by monitoring system type'
        )

        parser.add_argument(
            '--needs-rotation',
            action='store_true',
            help='Show only keys that need rotation'
        )

        parser.add_argument(
            '--inactive',
            action='store_true',
            help='Include inactive keys'
        )

    def handle(self, *args, **options):
        """List monitoring API keys."""
        self.stdout.write(self.style.SUCCESS('\n📋 Monitoring API Keys\n'))

        queryset = MonitoringAPIKey.objects.all()

        if not options['inactive']:
            queryset = queryset.filter(is_active=True)

        if options.get('system'):
            queryset = queryset.filter(monitoring_system=options['system'])

        if options.get('needs_rotation'):
            queryset = queryset.filter(
                is_active=True,
                next_rotation_at__lte=timezone.now()
            )

        if not queryset.exists():
            self.stdout.write(self.style.WARNING('No monitoring keys found'))
            return

        for key in queryset:
            self._display_key_info(key)

        self.stdout.write(f'\nTotal: {queryset.count()} key(s)')

    def _display_key_info(self, key: MonitoringAPIKey):
        """Display information for a single key."""
        status_icon = '✅' if key.is_active else '❌'
        rotation_icon = '🔄' if key.needs_rotation() else '✓'

        self.stdout.write(f'\n{status_icon} {key.name} (ID: {key.id})')
        self.stdout.write(f'   System: {key.monitoring_system}')
        self.stdout.write(f'   Permissions: {", ".join(key.permissions)}')
        self.stdout.write(f'   Created: {key.created_at}')

        if key.allowed_ips:
            self.stdout.write(f'   Allowed IPs: {", ".join(key.allowed_ips[:3])}{"..." if len(key.allowed_ips) > 3 else ""}')

        if key.expires_at:
            if key.is_expired():
                self.stdout.write(self.style.ERROR(f'   ⚠️  EXPIRED: {key.expires_at}'))
            else:
                self.stdout.write(f'   Expires: {key.expires_at}')

        if key.last_used_at:
            self.stdout.write(f'   Last Used: {key.last_used_at}')
            self.stdout.write(f'   Usage Count: {key.usage_count}')

        if key.next_rotation_at:
            if key.needs_rotation():
                self.stdout.write(self.style.WARNING(f'   {rotation_icon} NEEDS ROTATION (due {key.next_rotation_at})'))
            else:
                self.stdout.write(f'   Next Rotation: {key.next_rotation_at}')