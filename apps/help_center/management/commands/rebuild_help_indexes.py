"""
Management Command: Rebuild Help Indexes

Rebuild search vectors (FTS) and regenerate embeddings (pgvector).

Usage:
python manage.py rebuild_help_indexes [--tenant=1] [--embeddings-only] [--fts-only]

Following CLAUDE.md:
- Specific exception handling
- Progress reporting
- Batch processing for performance
"""

import logging
from django.core.management.base import BaseCommand
from django.contrib.postgres.search import SearchVector
from apps.tenants.models import Tenant
from apps.help_center.models import HelpArticle
from apps.help_center.tasks import generate_article_embedding

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    """Rebuild search indexes for help articles."""

    help = 'Rebuild FTS search_vector and pgvector embeddings for all articles'

    def add_arguments(self, parser):
        """Add command arguments."""
        parser.add_argument(
            '--tenant',
            type=int,
            help='Limit to specific tenant ID'
        )

        parser.add_argument(
            '--embeddings-only',
            action='store_true',
            help='Only regenerate embeddings (skip FTS)'
        )

        parser.add_argument(
            '--fts-only',
            action='store_true',
            help='Only rebuild FTS search vectors (skip embeddings)'
        )

    def handle(self, *args, **options):
        """Execute command."""
        tenant_id = options.get('tenant')
        embeddings_only = options['embeddings_only']
        fts_only = options['fts_only']

        # Build queryset
        qs = HelpArticle.objects.all()

        if tenant_id:
            try:
                tenant = Tenant.objects.get(id=tenant_id)
                qs = qs.filter(tenant=tenant)
                self.stdout.write(f'Limiting to tenant: {tenant.tenantname}')
            except Tenant.DoesNotExist:
                self.stdout.write(self.style.ERROR(f'Tenant {tenant_id} not found'))
                return

        article_count = qs.count()
        self.stdout.write(f'Processing {article_count} articles...\n')

        # Rebuild FTS search vectors
        if not embeddings_only:
            self.stdout.write('Rebuilding FTS search vectors...')

            updated = qs.update(
                search_vector=(
                    SearchVector('title', weight='A', config='english') +
                    SearchVector('summary', weight='B', config='english') +
                    SearchVector('content', weight='C', config='english')
                )
            )

            self.stdout.write(self.style.SUCCESS(f'✓ Updated {updated} search vectors'))

        # Regenerate embeddings
        if not fts_only:
            self.stdout.write('\nRegenerating embeddings (background tasks)...')

            for idx, article in enumerate(qs.iterator(), 1):
                generate_article_embedding.apply_async(
                    args=[article.id],
                    countdown=idx * 2  # Stagger to avoid rate limits
                )

                if idx % 10 == 0:
                    self.stdout.write(f'  Queued {idx}/{article_count} articles...')

            self.stdout.write(self.style.SUCCESS(f'✓ Queued {article_count} embedding tasks'))
            self.stdout.write(self.style.WARNING('Note: Embeddings will be generated in background'))

        self.stdout.write('\n' + self.style.SUCCESS('Index rebuild complete!'))
