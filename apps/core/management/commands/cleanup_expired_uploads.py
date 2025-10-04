"""
Management command to cleanup expired upload sessions.

Sprint 3: Automated cleanup of expired resumable upload sessions
and their temporary files.

Usage:
    python manage.py cleanup_expired_uploads [--dry-run] [--hours=24]

Schedule with cron:
    0 * * * * /path/to/venv/bin/python /path/to/manage.py cleanup_expired_uploads

Complies with:
- Rule #15: Logging data sanitization
- Automated resource management
"""

import os
import shutil
import logging
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from datetime import timedelta
from apps.core.models.upload_session import UploadSession

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Cleanup expired upload sessions and temporary files'

    def add_arguments(self, parser):
        """Add command arguments."""
        parser.add_argument(
            '--hours',
            type=int,
            default=24,
            help='Clean up sessions older than this many hours (default: 24)'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be deleted without actually deleting'
        )
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Show detailed output'
        )

    def handle(self, *args, **options):
        """Execute the cleanup command."""
        hours = options['hours']
        dry_run = options['dry_run']
        verbose = options['verbose']

        cutoff_time = timezone.now() - timedelta(hours=hours)

        self.stdout.write(
            self.style.SUCCESS(
                f"{'[DRY RUN] ' if dry_run else ''}Cleaning up upload sessions older than {hours} hours"
            )
        )

        expired_sessions = UploadSession.objects.filter(
            expires_at__lt=timezone.now(),
            status__in=['active', 'assembling']
        )

        old_completed_sessions = UploadSession.objects.filter(
            completed_at__lt=cutoff_time,
            status='completed'
        )

        old_failed_sessions = UploadSession.objects.filter(
            created_at__lt=cutoff_time,
            status__in=['failed', 'cancelled']
        )

        stats = {
            'expired_cleaned': 0,
            'completed_cleaned': 0,
            'failed_cleaned': 0,
            'temp_dirs_cleaned': 0,
            'temp_dirs_failed': 0
        }

        sessions_to_clean = list(expired_sessions) + list(old_completed_sessions) + list(old_failed_sessions)

        for session in sessions_to_clean:
            try:
                if verbose:
                    self.stdout.write(
                        f"Processing session {session.upload_id}: {session.filename} ({session.status})"
                    )

                if not dry_run:
                    if os.path.exists(session.temp_directory):
                        shutil.rmtree(session.temp_directory)
                        stats['temp_dirs_cleaned'] += 1
                        if verbose:
                            self.stdout.write(f"  Removed temp directory: {session.temp_directory}")
                    else:
                        if verbose:
                            self.stdout.write(f"  Temp directory already removed: {session.temp_directory}")

                    if session.status in ['active', 'assembling']:
                        session.status = 'expired'
                        session.save(update_fields=['status'])
                        stats['expired_cleaned'] += 1
                    elif session.status == 'completed':
                        session.delete()
                        stats['completed_cleaned'] += 1
                    else:
                        session.delete()
                        stats['failed_cleaned'] += 1
                else:
                    if verbose:
                        self.stdout.write(f"  Would delete session and temp directory")

            except (OSError, IOError) as e:
                stats['temp_dirs_failed'] += 1
                logger.error(
                    "Failed to cleanup temp directory",
                    extra={
                        'upload_id': str(session.upload_id),
                        'temp_directory': session.temp_directory,
                        'error': str(e)
                    }
                )
                if verbose:
                    self.stdout.write(
                        self.style.ERROR(f"  Failed to remove temp directory: {e}")
                    )

        self.stdout.write(
            self.style.SUCCESS(
                f"\n{'[DRY RUN] ' if dry_run else ''}Cleanup Summary:"
            )
        )
        self.stdout.write(f"  Expired sessions cleaned: {stats['expired_cleaned']}")
        self.stdout.write(f"  Completed sessions cleaned: {stats['completed_cleaned']}")
        self.stdout.write(f"  Failed/Cancelled sessions cleaned: {stats['failed_cleaned']}")
        self.stdout.write(f"  Temp directories removed: {stats['temp_dirs_cleaned']}")
        if stats['temp_dirs_failed'] > 0:
            self.stdout.write(
                self.style.WARNING(f"  Temp directories failed: {stats['temp_dirs_failed']}")
            )

        total_cleaned = stats['expired_cleaned'] + stats['completed_cleaned'] + stats['failed_cleaned']

        logger.info(
            "Upload session cleanup completed",
            extra={
                'total_sessions_cleaned': total_cleaned,
                'temp_dirs_cleaned': stats['temp_dirs_cleaned'],
                'dry_run': dry_run
            }
        )

        if not dry_run and total_cleaned == 0:
            self.stdout.write(self.style.SUCCESS("\nNo expired sessions to clean up."))