"""
Django management command to update deprecation statuses.
Run this daily via cron to automatically update statuses.

Usage:
    python manage.py api_update_deprecation_status

Compliance with .claude/rules.md:
- Rule #11: Specific exception handling
"""

from django.core.management.base import BaseCommand
from apps.core.services.api_deprecation_service import APIDeprecationService


class Command(BaseCommand):
    help = 'Update API deprecation statuses based on current dates'

    def handle(self, *args, **options):
        """Update all deprecation statuses."""
        try:
            updated_count = APIDeprecationService.update_all_statuses()

            if updated_count > 0:
                self.stdout.write(
                    self.style.SUCCESS(
                        f'✅ Updated {updated_count} deprecation statuses'
                    )
                )
            else:
                self.stdout.write(
                    self.style.SUCCESS(
                        '✅ All statuses are current'
                    )
                )

        except (FileNotFoundError, IOError, OSError, PermissionError) as e:
            self.stdout.write(
                self.style.ERROR(f'❌ Error updating statuses: {e}')
            )