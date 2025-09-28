"""
Management command to invalidate application caches
Useful for manual cache clearing and troubleshooting
"""

import logging
from typing import Dict, Any
from django.core.management.base import BaseCommand, CommandError
from django.core.cache import cache

from apps.core.caching.utils import clear_cache_pattern, CACHE_PATTERNS
from apps.core.caching.invalidation import (
    invalidate_cache_pattern,
    invalidate_model_caches,
    cache_invalidation_manager
)

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Invalidate application caches by pattern or model'

    def add_arguments(self, parser):
        parser.add_argument(
            '--pattern',
            type=str,
            help='Cache pattern to invalidate (dashboard, dropdown, user, etc.)'
        )
        parser.add_argument(
            '--model',
            type=str,
            help='Model name to invalidate caches for (People, Asset, etc.)'
        )
        parser.add_argument(
            '--tenant-id',
            type=int,
            help='Specific tenant ID to scope invalidation to'
        )
        parser.add_argument(
            '--all',
            action='store_true',
            help='Clear ALL application caches (use with caution!)'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be invalidated without actually clearing'
        )
        parser.add_argument(
            '--list-patterns',
            action='store_true',
            help='List all available cache patterns'
        )
        parser.add_argument(
            '--list-models',
            action='store_true',
            help='List all models with registered cache dependencies'
        )

    def handle(self, *args, **options):
        """
        Main command handler
        """
        self.verbosity = options.get('verbosity', 1)
        self.dry_run = options.get('dry_run', False)

        # Handle list operations
        if options.get('list_patterns'):
            self._list_cache_patterns()
            return

        if options.get('list_models'):
            self._list_model_dependencies()
            return

        # Validate arguments
        pattern = options.get('pattern')
        model = options.get('model')
        clear_all = options.get('all')
        tenant_id = options.get('tenant_id')

        if not any([pattern, model, clear_all]):
            raise CommandError(
                'You must specify --pattern, --model, --all, --list-patterns, or --list-models'
            )

        if self.dry_run:
            self.stdout.write(
                self.style.WARNING('DRY RUN MODE - No caches will actually be cleared')
            )

        try:
            if clear_all:
                self._invalidate_all_caches()
            elif pattern:
                self._invalidate_pattern(pattern, tenant_id)
            elif model:
                self._invalidate_model(model, tenant_id)

            self.stdout.write(
                self.style.SUCCESS('Cache invalidation completed successfully!')
            )

        except (FileNotFoundError, IOError, OSError, PermissionError, TypeError, ValidationError, ValueError) as e:
            logger.error(f'Cache invalidation failed: {e}', exc_info=True)
            raise CommandError(f'Cache invalidation failed: {str(e)}')

    def _list_cache_patterns(self):
        """
        List all available cache patterns
        """
        self.stdout.write(
            self.style.SUCCESS('Available Cache Patterns:')
        )
        self.stdout.write('')

        for pattern_name, pattern in CACHE_PATTERNS.items():
            self.stdout.write(f'  {pattern_name:<25} → {pattern}')

        self.stdout.write('')
        self.stdout.write('Usage examples:')
        self.stdout.write('  python manage.py invalidate_caches --pattern dashboard')
        self.stdout.write('  python manage.py invalidate_caches --pattern dropdown --tenant-id 1')

    def _list_model_dependencies(self):
        """
        List all models with registered cache dependencies
        """
        self.stdout.write(
            self.style.SUCCESS('Models with Cache Dependencies:')
        )
        self.stdout.write('')

        dependencies = cache_invalidation_manager.model_dependencies

        for model_name, patterns in sorted(dependencies.items()):
            self.stdout.write(f'  {model_name}:')
            for pattern in sorted(patterns):
                self.stdout.write(f'    - {pattern}')
            self.stdout.write('')

        self.stdout.write(f'Total registered models: {len(dependencies)}')
        self.stdout.write('')
        self.stdout.write('Usage example:')
        self.stdout.write('  python manage.py invalidate_caches --model People --tenant-id 1')

    def _invalidate_all_caches(self):
        """
        Invalidate ALL application caches
        """
        self.stdout.write(
            self.style.WARNING('⚠️  WARNING: Clearing ALL application caches!')
        )

        if self.dry_run:
            self.stdout.write('Would clear all cache keys')
            return

        # Require confirmation for this dangerous operation
        confirmation = input('Type "CLEAR ALL" to confirm: ')
        if confirmation != 'CLEAR ALL':
            raise CommandError('Operation cancelled - confirmation did not match')

        try:
            cache.clear()
            self.stdout.write(
                self.style.SUCCESS('✓ All caches cleared successfully')
            )
        except (FileNotFoundError, IOError, OSError, PermissionError, TypeError, ValidationError, ValueError) as e:
            raise CommandError(f'Failed to clear all caches: {str(e)}')

    def _invalidate_pattern(self, pattern: str, tenant_id: int = None):
        """
        Invalidate caches matching a specific pattern
        """
        # Validate pattern
        if pattern not in CACHE_PATTERNS and pattern not in CACHE_PATTERNS.values():
            # Check if it's a pattern key
            pattern_value = CACHE_PATTERNS.get(pattern.upper().replace('-', '_'))
            if not pattern_value:
                raise CommandError(
                    f'Unknown cache pattern: {pattern}. '
                    f'Use --list-patterns to see available patterns.'
                )
            pattern = pattern_value

        self.stdout.write(
            f'Invalidating caches for pattern: {pattern}'
        )

        if tenant_id:
            self.stdout.write(f'Scoped to tenant ID: {tenant_id}')

        if self.dry_run:
            full_pattern = f'tenant:{tenant_id}:*{pattern}*' if tenant_id else f'tenant:*:*{pattern}*'
            self.stdout.write(f'Would clear pattern: {full_pattern}')
            return

        try:
            result = invalidate_cache_pattern(pattern, tenant_id)

            if result['success']:
                self.stdout.write(
                    self.style.SUCCESS(
                        f'✓ Cleared {result["keys_cleared"]} cache keys'
                    )
                )
            else:
                self.stderr.write(
                    self.style.ERROR(
                        f'✗ Failed to clear pattern: {result.get("error", "Unknown error")}'
                    )
                )

        except (FileNotFoundError, IOError, OSError, PermissionError, TypeError, ValidationError, ValueError) as e:
            raise CommandError(f'Pattern invalidation failed: {str(e)}')

    def _invalidate_model(self, model_name: str, tenant_id: int = None):
        """
        Invalidate all caches associated with a model
        """
        # Validate model
        patterns = cache_invalidation_manager.get_patterns_for_model(model_name)
        if not patterns:
            raise CommandError(
                f'Model "{model_name}" has no registered cache dependencies. '
                f'Use --list-models to see available models.'
            )

        self.stdout.write(
            f'Invalidating caches for model: {model_name}'
        )
        self.stdout.write(
            f'Registered patterns: {", ".join(patterns)}'
        )

        if tenant_id:
            self.stdout.write(f'Scoped to tenant ID: {tenant_id}')

        if self.dry_run:
            self.stdout.write(
                f'Would invalidate {len(patterns)} cache patterns for {model_name}'
            )
            return

        try:
            result = invalidate_model_caches(model_name, tenant_id)

            if result['total_cleared'] > 0:
                self.stdout.write(
                    self.style.SUCCESS(
                        f'✓ Cleared {result["total_cleared"]} cache keys '
                        f'across {result["patterns_processed"]} patterns'
                    )
                )

                if result['errors']:
                    self.stderr.write(
                        self.style.WARNING(
                            f'⚠️  {len(result["errors"])} errors occurred during invalidation'
                        )
                    )
                    for error in result['errors']:
                        self.stderr.write(f'  - {error}')
            else:
                self.stdout.write(
                    self.style.WARNING('No cache keys found to clear')
                )

        except (FileNotFoundError, IOError, OSError, PermissionError, TypeError, ValidationError, ValueError) as e:
            raise CommandError(f'Model invalidation failed: {str(e)}')