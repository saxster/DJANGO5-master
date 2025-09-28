"""
Management command to bump cache version and clear old caches.
Used after schema changes or major data migrations.
"""

import logging
from django.core.management.base import BaseCommand, CommandError
from apps.core.caching.versioning import bump_cache_version, clear_old_version_caches

logger = logging.getLogger(__name__)

__all__ = ['Command']


class Command(BaseCommand):
    help = 'Bump cache version to invalidate stale caches after schema changes'

    def add_arguments(self, parser):
        parser.add_argument(
            '--version',
            type=str,
            help='Explicit version string (e.g., "2.0"). Auto-increments if not specified.'
        )
        parser.add_argument(
            '--keep-old-versions',
            type=int,
            default=1,
            help='Number of old versions to keep (default: 1)'
        )
        parser.add_argument(
            '--no-cleanup',
            action='store_true',
            help='Skip cleanup of old version caches'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be done without making changes'
        )

    def handle(self, *args, **options):
        """Execute cache version bump"""
        try:
            new_version = options.get('version')
            keep_versions = options.get('keep_old_versions', 1)
            skip_cleanup = options.get('no_cleanup', False)
            dry_run = options.get('dry_run', False)

            if dry_run:
                self.stdout.write(
                    self.style.WARNING('DRY RUN MODE - No changes will be made')
                )

            from apps.core.caching.versioning import cache_version_manager

            old_version = cache_version_manager.get_version()

            if new_version:
                self.stdout.write(f'Current version: {old_version}')
                self.stdout.write(f'New version: {new_version}')
            else:
                auto_version = cache_version_manager._increment_version(old_version)
                self.stdout.write(f'Current version: {old_version}')
                self.stdout.write(f'Auto-increment to: {auto_version}')

            if dry_run:
                self.stdout.write('Would bump cache version')
                if not skip_cleanup:
                    self.stdout.write(f'Would cleanup old versions (keeping {keep_versions} recent)')
                return

            result = bump_cache_version(new_version)

            if result['success']:
                self.stdout.write(
                    self.style.SUCCESS(
                        f'✓ Cache version bumped: {result["old_version"]} → {result["new_version"]}'
                    )
                )

                if not skip_cleanup:
                    self.stdout.write('Cleaning up old version caches...')
                    cleanup_result = clear_old_version_caches(keep_versions)

                    if cleanup_result['success']:
                        self.stdout.write(
                            self.style.SUCCESS(
                                f'✓ Cleared {cleanup_result["keys_cleared"]} cache keys '
                                f'from {cleanup_result["versions_cleared"]} old versions'
                            )
                        )
                    else:
                        self.stderr.write(
                            self.style.WARNING(
                                f'⚠️  Cleanup had errors: {cleanup_result.get("error")}'
                            )
                        )

                self.stdout.write('')
                self.stdout.write(
                    self.style.SUCCESS('Cache version bump completed successfully!')
                )
                self.stdout.write('All new caches will use the updated version.')

            else:
                raise CommandError(f'Version bump failed: {result.get("error")}')

        except ImportError as e:
            raise CommandError(f'Cache versioning module not found: {str(e)}')
        except (FileNotFoundError, IOError, OSError, PermissionError, TypeError, ValidationError, ValueError) as e:
            logger.error(f'Cache version bump failed: {e}', exc_info=True)
            raise CommandError(f'Version bump failed: {str(e)}')