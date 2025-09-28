"""
Rotate Monitoring API Keys

Management command to automate monitoring API key rotation for security.

Features:
- Automatic rotation of keys based on schedule
- Zero-downtime rotation with grace periods
- Email notifications to monitoring system admins
- Rollback support for failed rotations
- Audit logging for compliance

Usage:
    python manage.py rotate_monitoring_keys --auto
    python manage.py rotate_monitoring_keys --key-id 42
    python manage.py rotate_monitoring_keys --all --notify

Author: Security Enhancement Team
Date: 2025-09-27
"""

import logging
import sys
from datetime import timedelta
from typing import List, Optional

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from django.core.mail import send_mail
from django.conf import settings

from apps.core.models.monitoring_api_key import MonitoringAPIKey

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Rotate monitoring API keys for security'

    def add_arguments(self, parser):
        parser.add_argument(
            '--auto',
            action='store_true',
            help='Automatically rotate all keys needing rotation'
        )

        parser.add_argument(
            '--key-id',
            type=int,
            help='Rotate specific key by ID'
        )

        parser.add_argument(
            '--all',
            action='store_true',
            help='Rotate all active keys (use with caution)'
        )

        parser.add_argument(
            '--no-grace-period',
            action='store_true',
            help='Force immediate rotation without grace period'
        )

        parser.add_argument(
            '--notify',
            action='store_true',
            help='Send email notifications about rotations'
        )

        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be rotated without making changes'
        )

    def handle(self, *args, **options):
        """Execute the key rotation command."""
        self.stdout.write(self.style.SUCCESS('\n🔄 Monitoring API Key Rotation\n'))

        try:
            if options['auto']:
                self._rotate_keys_needing_rotation(options)
            elif options['key_id']:
                self._rotate_specific_key(options['key_id'], options)
            elif options['all']:
                self._rotate_all_keys(options)
            else:
                self.stdout.write(
                    self.style.ERROR('Error: Must specify --auto, --key-id, or --all')
                )
                return

        except (FileNotFoundError, IOError, OSError, PermissionError) as e:
            logger.error(f"Key rotation failed: {e}", exc_info=True)
            raise CommandError(f'Key rotation failed: {e}')

    def _rotate_keys_needing_rotation(self, options: dict):
        """Rotate all keys that need rotation based on schedule."""
        keys_to_rotate = MonitoringAPIKey.get_keys_needing_rotation()

        if not keys_to_rotate.exists():
            self.stdout.write(
                self.style.SUCCESS('✅ No keys need rotation at this time')
            )
            return

        self.stdout.write(
            f'📋 Found {keys_to_rotate.count()} key(s) needing rotation:\n'
        )

        for key in keys_to_rotate:
            self.stdout.write(f'  • {key.name} (ID: {key.id}) - Next rotation: {key.next_rotation_at}')

        if options['dry_run']:
            self.stdout.write(self.style.WARNING('\n🔍 DRY RUN - No changes made'))
            return

        rotated_count = 0
        failed_count = 0

        for key in keys_to_rotate:
            try:
                self._rotate_key(key, options)
                rotated_count += 1
            except (FileNotFoundError, IOError, OSError, PermissionError) as e:
                logger.error(f"Failed to rotate key {key.id}: {e}", exc_info=True)
                self.stdout.write(
                    self.style.ERROR(f'  ❌ Failed to rotate {key.name}: {e}')
                )
                failed_count += 1

        self.stdout.write(
            self.style.SUCCESS(f'\n✅ Rotation complete: {rotated_count} succeeded, {failed_count} failed')
        )

    def _rotate_specific_key(self, key_id: int, options: dict):
        """Rotate a specific key by ID."""
        try:
            key = MonitoringAPIKey.objects.get(id=key_id)
        except MonitoringAPIKey.DoesNotExist:
            raise CommandError(f'Monitoring API key with ID {key_id} not found')

        self.stdout.write(f'🔄 Rotating key: {key.name} (ID: {key.id})\n')

        if options['dry_run']:
            self.stdout.write(self.style.WARNING('🔍 DRY RUN - No changes made'))
            return

        self._rotate_key(key, options)

        self.stdout.write(self.style.SUCCESS('✅ Key rotated successfully'))

    def _rotate_all_keys(self, options: dict):
        """Rotate all active keys."""
        keys = MonitoringAPIKey.objects.filter(is_active=True)

        if not keys.exists():
            self.stdout.write(self.style.WARNING('⚠️  No active keys found'))
            return

        self.stdout.write(
            self.style.WARNING(
                f'⚠️  WARNING: This will rotate ALL {keys.count()} active monitoring keys!'
            )
        )

        if not options.get('no_input', False):
            confirm = input('Type "yes" to confirm: ')
            if confirm.lower() != 'yes':
                self.stdout.write(self.style.ERROR('❌ Operation cancelled'))
                return

        if options['dry_run']:
            self.stdout.write(self.style.WARNING('\n🔍 DRY RUN - No changes made'))
            for key in keys:
                self.stdout.write(f'  • Would rotate: {key.name} (ID: {key.id})')
            return

        rotated_count = 0
        failed_count = 0

        for key in keys:
            try:
                self._rotate_key(key, options)
                rotated_count += 1
            except (DatabaseError, FileNotFoundError, IOError, IntegrityError, OSError, ObjectDoesNotExist, PermissionError) as e:
                logger.error(f"Failed to rotate key {key.id}: {e}", exc_info=True)
                failed_count += 1

        self.stdout.write(
            self.style.SUCCESS(f'\n✅ Rotated {rotated_count} keys ({failed_count} failed)')
        )

    def _rotate_key(self, key: MonitoringAPIKey, options: dict):
        """
        Perform the actual key rotation.

        Args:
            key: MonitoringAPIKey instance to rotate
            options: Command options
        """
        if options.get('no_grace_period'):
            key.rotation_grace_period_hours = 0

        new_key, new_raw_key = key.rotate_key()

        self.stdout.write(
            self.style.SUCCESS(f'\n✅ Rotated: {key.name}')
        )
        self.stdout.write(f'  📋 Old Key ID: {key.id}')
        self.stdout.write(f'  📋 New Key ID: {new_key.id}')
        self.stdout.write(
            self.style.WARNING(f'  🔑 New API Key: {new_raw_key}')
        )
        self.stdout.write(
            self.style.WARNING('     ⚠️  SAVE THIS KEY - It cannot be retrieved later!')
        )
        self.stdout.write(f'  ⏱️  Old key valid until: {key.expires_at}')
        self.stdout.write(f'  ⏱️  Grace period: {key.rotation_grace_period_hours} hours\n')

        logger.info(
            f"Monitoring API key rotated: {key.name}",
            extra={
                'event_type': 'monitoring_key_rotation',
                'old_key_id': key.id,
                'new_key_id': new_key.id,
                'grace_period_hours': key.rotation_grace_period_hours
            }
        )

        if options.get('notify'):
            self._send_notification(key, new_key, new_raw_key)

        next_rotation = self._calculate_next_rotation(new_key)
        if next_rotation:
            new_key.next_rotation_at = next_rotation
            new_key.save(update_fields=['next_rotation_at'])

            self.stdout.write(f'  📅 Next rotation scheduled: {next_rotation}')

    def _calculate_next_rotation(self, key: MonitoringAPIKey) -> Optional[timezone.datetime]:
        """Calculate next rotation date based on schedule."""
        rotation_days = {
            'never': None,
            'monthly': 30,
            'quarterly': 90,
            'yearly': 365,
        }

        days = rotation_days.get(key.rotation_schedule)
        if days is None:
            return None

        return timezone.now() + timedelta(days=days)

    def _send_notification(self, old_key: MonitoringAPIKey, new_key: MonitoringAPIKey, new_raw_key: str):
        """
        Send email notification about key rotation.

        Args:
            old_key: Old MonitoringAPIKey instance
            new_key: New MonitoringAPIKey instance
            new_raw_key: New API key (plaintext)
        """
        contact_email = old_key.metadata.get('contact_email')

        if not contact_email:
            self.stdout.write(
                self.style.WARNING('  ⚠️  No contact_email in metadata - skipping notification')
            )
            return

        subject = f'Monitoring API Key Rotated: {old_key.name}'

        message = f"""
Monitoring API Key Rotation Notice

Your monitoring API key has been rotated for security:

Old Key Details:
- Name: {old_key.name}
- ID: {old_key.id}
- Valid Until: {old_key.expires_at}
- Grace Period: {old_key.rotation_grace_period_hours} hours

New Key Details:
- Name: {new_key.name}
- ID: {new_key.id}
- API Key: {new_raw_key}

IMPORTANT: Save the new API key immediately. It cannot be retrieved later.

Action Required:
1. Update your monitoring system configuration with the new API key
2. Test the new API key before the grace period expires
3. Remove the old API key from your configuration after {old_key.rotation_grace_period_hours} hours

Configuration Example (Prometheus):
```yaml
authorization:
  type: Bearer
  credentials: '{new_raw_key}'
```

Grace Period:
The old API key will remain valid until {old_key.expires_at} to allow zero-downtime updates.

Support:
- Documentation: docs/security/monitoring-api-authentication.md
- Security Team: security@company.com
- Escalation: {old_key.metadata.get('escalation', 'N/A')}

This is an automated security notification.
        """

        try:
            send_mail(
                subject=subject,
                message=message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[contact_email],
                fail_silently=False
            )

            self.stdout.write(
                self.style.SUCCESS(f'  📧 Notification sent to: {contact_email}')
            )

        except (DatabaseError, FileNotFoundError, IOError, IntegrityError, OSError, ObjectDoesNotExist, PermissionError) as e:
            logger.error(f"Failed to send rotation notification: {e}", exc_info=True)
            self.stdout.write(
                self.style.ERROR(f'  ❌ Failed to send notification: {e}')
            )