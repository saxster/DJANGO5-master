"""
Create Monitoring API Key

Interactive management command to create new monitoring API keys
for external monitoring systems.

Features:
- Interactive key generation
- Permission configuration
- IP whitelisting setup
- Automatic rotation scheduling

Usage:
    python manage.py create_monitoring_key --name "Prometheus" --system prometheus

Author: Security Enhancement Team
Date: 2025-09-27
"""

import logging
from typing import List

from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth import get_user_model

from apps.core.models.monitoring_api_key import MonitoringAPIKey, MonitoringPermission

User = get_user_model()
logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Create a new monitoring API key'

    def add_arguments(self, parser):
        parser.add_argument(
            '--name',
            type=str,
            required=True,
            help='Name for the API key (e.g., "Prometheus Production")'
        )

        parser.add_argument(
            '--system',
            type=str,
            choices=['prometheus', 'grafana', 'datadog', 'new_relic', 'cloudwatch', 'stackdriver', 'custom'],
            default='custom',
            help='Type of monitoring system'
        )

        parser.add_argument(
            '--permissions',
            type=str,
            help='Comma-separated permissions (health,metrics,performance,alerts,dashboard,admin)'
        )

        parser.add_argument(
            '--ips',
            type=str,
            help='Comma-separated allowed IP addresses'
        )

        parser.add_argument(
            '--expires-days',
            type=int,
            help='Days until key expires (default: never)'
        )

        parser.add_argument(
            '--rotation',
            type=str,
            choices=['never', 'monthly', 'quarterly', 'yearly'],
            default='quarterly',
            help='Automatic rotation schedule'
        )

        parser.add_argument(
            '--contact-email',
            type=str,
            help='Contact email for rotation notifications'
        )

        parser.add_argument(
            '--description',
            type=str,
            help='Description and purpose of this key'
        )

    def handle(self, *args, **options):
        """Create monitoring API key."""
        self.stdout.write(self.style.SUCCESS('\n🔑 Create Monitoring API Key\n'))

        try:
            permissions = self._parse_permissions(options.get('permissions'))
            allowed_ips = self._parse_ips(options.get('ips'))

            metadata = {}
            if options.get('contact_email'):
                metadata['contact_email'] = options['contact_email']
            if options.get('description'):
                metadata['description'] = options['description']

            self._show_configuration_summary(
                options['name'],
                options['system'],
                permissions,
                allowed_ips,
                options.get('expires_days'),
                options['rotation']
            )

            if not options.get('no_input', False):
                confirm = input('\nCreate this API key? (yes/no): ')
                if confirm.lower() != 'yes':
                    self.stdout.write(self.style.ERROR('❌ Operation cancelled'))
                    return

            key_instance, raw_api_key = MonitoringAPIKey.create_key(
                name=options['name'],
                monitoring_system=options['system'],
                permissions=permissions,
                allowed_ips=allowed_ips,
                expires_days=options.get('expires_days'),
                rotation_schedule=options['rotation'],
                metadata=metadata,
                description=options.get('description', '')
            )

            self._show_success_output(key_instance, raw_api_key, metadata)

            logger.info(
                f"Created monitoring API key: {key_instance.name}",
                extra={
                    'event_type': 'monitoring_key_created',
                    'key_id': key_instance.id,
                    'monitoring_system': key_instance.monitoring_system,
                    'permissions': key_instance.permissions
                }
            )

        except (FileNotFoundError, IOError, OSError, PermissionError) as e:
            logger.error(f"Failed to create monitoring key: {e}", exc_info=True)
            raise CommandError(f'Failed to create API key: {e}')

    def _parse_permissions(self, permissions_str: Optional[str]) -> List[str]:
        """Parse permissions from comma-separated string."""
        if not permissions_str:
            return [MonitoringPermission.ADMIN.value]

        permission_map = {
            'health': MonitoringPermission.HEALTH_CHECK.value,
            'metrics': MonitoringPermission.METRICS.value,
            'performance': MonitoringPermission.PERFORMANCE.value,
            'alerts': MonitoringPermission.ALERTS.value,
            'dashboard': MonitoringPermission.DASHBOARD.value,
            'admin': MonitoringPermission.ADMIN.value,
        }

        perms = []
        for perm_name in permissions_str.split(','):
            perm_name = perm_name.strip().lower()
            if perm_name in permission_map:
                perms.append(permission_map[perm_name])
            else:
                raise CommandError(f'Invalid permission: {perm_name}')

        return perms if perms else [MonitoringPermission.ADMIN.value]

    def _parse_ips(self, ips_str: Optional[str]) -> Optional[List[str]]:
        """Parse IP addresses from comma-separated string."""
        if not ips_str:
            return None

        return [ip.strip() for ip in ips_str.split(',')]

    def _show_configuration_summary(self, name: str, system: str, permissions: List[str],
                                     allowed_ips: Optional[List[str]], expires_days: Optional[int],
                                     rotation: str):
        """Show configuration summary before creation."""
        self.stdout.write('Configuration Summary:')
        self.stdout.write(f'  Name: {name}')
        self.stdout.write(f'  System: {system}')
        self.stdout.write(f'  Permissions: {", ".join(permissions)}')
        self.stdout.write(f'  Allowed IPs: {", ".join(allowed_ips) if allowed_ips else "All IPs"}')
        self.stdout.write(f'  Expires: {f"In {expires_days} days" if expires_days else "Never"}')
        self.stdout.write(f'  Rotation: {rotation}')

    def _show_success_output(self, key_instance: MonitoringAPIKey, raw_api_key: str, metadata: dict):
        """Show success message with API key details."""
        self.stdout.write(self.style.SUCCESS('\n✅ Monitoring API Key Created Successfully\n'))

        self.stdout.write('Key Details:')
        self.stdout.write(f'  ID: {key_instance.id}')
        self.stdout.write(f'  Name: {key_instance.name}')
        self.stdout.write(f'  System: {key_instance.monitoring_system}')
        self.stdout.write(f'  Permissions: {", ".join(key_instance.permissions)}')

        if key_instance.allowed_ips:
            self.stdout.write(f'  Allowed IPs: {", ".join(key_instance.allowed_ips)}')

        if key_instance.expires_at:
            self.stdout.write(f'  Expires: {key_instance.expires_at}')

        self.stdout.write(f'  Rotation: {key_instance.rotation_schedule}')

        if key_instance.next_rotation_at:
            self.stdout.write(f'  Next Rotation: {key_instance.next_rotation_at}')

        self.stdout.write(
            self.style.WARNING(f'\n🔑 API Key: {raw_api_key}')
        )
        self.stdout.write(
            self.style.WARNING('   ⚠️  SAVE THIS KEY SECURELY - It cannot be retrieved later!\n')
        )

        self.stdout.write('Usage Example:')
        self.stdout.write(f'  curl -H "Authorization: Bearer {raw_api_key}" \\')
        self.stdout.write('    https://your-app.com/monitoring/health/')

        if metadata.get('contact_email'):
            self.stdout.write(f'\n📧 Notifications will be sent to: {metadata["contact_email"]}')