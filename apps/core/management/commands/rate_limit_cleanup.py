"""
Rate Limiting Cleanup Management Command

Performs maintenance tasks for rate limiting system:
- Cleanup expired blocks
- Cleanup expired trusted IPs
- Archive old violation logs
- Generate cleanup report

Usage:
    python manage.py rate_limit_cleanup
    python manage.py rate_limit_cleanup --dry-run
    python manage.py rate_limit_cleanup --days=30
"""

from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from apps.core.models.rate_limiting import (
    RateLimitBlockedIP,
    RateLimitTrustedIP,
    RateLimitViolationLog
)


class Command(BaseCommand):
    help = 'Cleanup expired rate limiting data'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be cleaned up without making changes'
        )

        parser.add_argument(
            '--days',
            type=int,
            default=90,
            help='Number of days to keep violation logs (default: 90)'
        )

        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Show detailed output'
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        retention_days = options['days']
        verbose = options['verbose']

        self.stdout.write(self.style.SUCCESS('=' * 80))
        self.stdout.write(self.style.SUCCESS('RATE LIMITING CLEANUP'))
        self.stdout.write(self.style.SUCCESS('=' * 80))
        self.stdout.write()

        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN MODE - No changes will be made'))
            self.stdout.write()

        total_cleaned = 0

        total_cleaned += self._cleanup_expired_blocks(dry_run, verbose)
        total_cleaned += self._cleanup_expired_trusted_ips(dry_run, verbose)
        total_cleaned += self._cleanup_old_violations(retention_days, dry_run, verbose)

        self.stdout.write()
        self.stdout.write(self.style.SUCCESS('=' * 80))
        self.stdout.write(self.style.SUCCESS(f'CLEANUP COMPLETE: {total_cleaned} records processed'))
        self.stdout.write(self.style.SUCCESS('=' * 80))

    def _cleanup_expired_blocks(self, dry_run: bool, verbose: bool) -> int:
        """Cleanup expired IP blocks."""
        self.stdout.write(self.style.HTTP_INFO('\n1. Cleaning up expired IP blocks...'))

        expired_blocks = RateLimitBlockedIP.objects.filter(
            blocked_until__lt=timezone.now(),
            is_active=True
        )

        count = expired_blocks.count()

        if verbose and count > 0:
            for block in expired_blocks[:10]:
                self.stdout.write(
                    f"   - {block.ip_address} (expired {block.blocked_until})"
                )
            if count > 10:
                self.stdout.write(f"   ... and {count - 10} more")

        if not dry_run and count > 0:
            expired_blocks.update(is_active=False)
            self.stdout.write(self.style.SUCCESS(f'   ✅ Deactivated {count} expired blocks'))
        else:
            self.stdout.write(f'   Found {count} expired blocks')

        return count

    def _cleanup_expired_trusted_ips(self, dry_run: bool, verbose: bool) -> int:
        """Cleanup expired trusted IPs."""
        self.stdout.write(self.style.HTTP_INFO('\n2. Cleaning up expired trusted IPs...'))

        expired_trusted = RateLimitTrustedIP.objects.filter(
            expires_at__lt=timezone.now(),
            is_active=True
        )

        count = expired_trusted.count()

        if verbose and count > 0:
            for trusted in expired_trusted:
                self.stdout.write(
                    f"   - {trusted.ip_address} ({trusted.description})"
                )

        if not dry_run and count > 0:
            expired_trusted.update(is_active=False)
            self.stdout.write(self.style.SUCCESS(f'   ✅ Deactivated {count} expired trusted IPs'))
        else:
            self.stdout.write(f'   Found {count} expired trusted IPs')

        return count

    def _cleanup_old_violations(self, retention_days: int, dry_run: bool, verbose: bool) -> int:
        """Cleanup old violation logs."""
        self.stdout.write(self.style.HTTP_INFO(f'\n3. Cleaning up violation logs older than {retention_days} days...'))

        cutoff_date = timezone.now() - timedelta(days=retention_days)

        old_violations = RateLimitViolationLog.objects.filter(
            timestamp__lt=cutoff_date
        )

        count = old_violations.count()

        if verbose and count > 0:
            endpoint_summary = old_violations.values('endpoint_type').annotate(
                count=models.Count('id')
            )

            self.stdout.write('   Violations by endpoint:')
            for item in endpoint_summary:
                self.stdout.write(f"   - {item['endpoint_type']}: {item['count']}")

        if not dry_run and count > 0:
            old_violations.delete()
            self.stdout.write(self.style.SUCCESS(f'   ✅ Deleted {count} old violation logs'))
        else:
            self.stdout.write(f'   Found {count} old violation logs')

        return count


from django.db import models