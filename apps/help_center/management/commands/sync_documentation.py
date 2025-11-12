"""
Management Command: Sync Documentation

Bulk import help articles from markdown files in docs/ directory.

Usage:
python manage.py sync_documentation --dir=docs/ --tenant=1 --user=1

Following CLAUDE.md:
- Specific exception handling
- Clear error messages
- Idempotent operation
"""

import logging
from django.core.management.base import BaseCommand
from django.core.exceptions import ValidationError
from apps.tenants.models import Tenant
from apps.peoples.models import People
from apps.help_center.services.knowledge_service import KnowledgeService
from apps.core.exceptions.patterns import FILE_EXCEPTIONS


logger = logging.getLogger(__name__)


class Command(BaseCommand):
    """Sync documentation from markdown files to help articles."""

    help = 'Import help articles from markdown files in docs/ directory'

    def add_arguments(self, parser):
        """Add command arguments."""
        parser.add_argument(
            '--dir',
            type=str,
            default='docs/',
            help='Directory containing markdown files (default: docs/)'
        )

        parser.add_argument(
            '--tenant',
            type=int,
            required=True,
            help='Tenant ID for articles'
        )

        parser.add_argument(
            '--user',
            type=int,
            required=True,
            help='User ID (author of imported articles)'
        )

        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Preview import without saving'
        )

    def handle(self, *args, **options):
        """Execute command."""
        markdown_dir = options['dir']
        tenant_id = options['tenant']
        user_id = options['user']
        dry_run = options['dry_run']

        try:
            tenant = Tenant.objects.get(id=tenant_id)
            user = People.objects.get(id=user_id)

        except Tenant.DoesNotExist:
            self.stdout.write(self.style.ERROR(f'Tenant {tenant_id} not found'))
            return

        except People.DoesNotExist:
            self.stdout.write(self.style.ERROR(f'User {user_id} not found'))
            return

        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN - No changes will be saved'))

        self.stdout.write(f'Importing from: {markdown_dir}')
        self.stdout.write(f'Tenant: {tenant.tenantname}')
        self.stdout.write(f'Author: {user.username}')
        self.stdout.write('')

        if not dry_run:
            try:
                articles = KnowledgeService.bulk_import_from_markdown(
                    tenant=tenant,
                    markdown_dir=markdown_dir,
                    created_by=user
                )

                self.stdout.write(
                    self.style.SUCCESS(f'Successfully imported {len(articles)} articles')
                )

                for article in articles:
                    self.stdout.write(f'  ✓ {article.title}')

            except ValidationError as e:
                self.stdout.write(self.style.ERROR(f'Import failed: {e}'))

            except FILE_EXCEPTIONS as e:
                logger.error(f'Unexpected import error: {e}', exc_info=True)
                self.stdout.write(self.style.ERROR(f'Unexpected error: {e}'))

        else:
            self.stdout.write(self.style.WARNING('Dry run complete - use without --dry-run to import'))
