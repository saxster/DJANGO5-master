"""
Management command to sync ontology components to help_center articles.

Usage:
    python manage.py sync_ontology_articles --dry-run
    python manage.py sync_ontology_articles --criticality=high
    python manage.py sync_ontology_articles --criticality=all

This command calls the Celery task sync_ontology_articles_task synchronously
for manual execution. For scheduled background execution, the task runs
automatically via Celery beat at 2 AM daily.

Following CLAUDE.md:
- Clear, concise command documentation
- Explicit error handling
- User-friendly output formatting
"""

from django.core.management.base import BaseCommand, CommandError
from apps.help_center.tasks import sync_ontology_articles_task


class Command(BaseCommand):
    help = "Sync ontology components to help_center articles"

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Log only, no database writes (preview mode)'
        )
        parser.add_argument(
            '--criticality',
            type=str,
            default='high',
            choices=['high', 'medium', 'low', 'all'],
            help='Filter by criticality level (default: high)'
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        criticality = options['criticality']

        # Display start message
        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    f"\n🔍 DRY RUN MODE: No database changes will be made"
                )
            )

        self.stdout.write(
            f"\nStarting ontology article sync..."
            f"\n  Criticality: {criticality}"
            f"\n  Dry run: {dry_run}"
            f"\n"
        )

        try:
            # Call the Celery task synchronously
            result = sync_ontology_articles_task(
                dry_run=dry_run,
                criticality=criticality
            )

            # Check if task was successful
            if not result.get('success', False):
                error_msg = result.get('error', 'Unknown error')
                raise CommandError(f"❌ Sync failed: {error_msg}")

            # Display results
            self.stdout.write(
                self.style.SUCCESS(
                    f"\n✅ Sync complete!"
                )
            )

            self.stdout.write(
                f"\nResults:"
                f"\n  Total components: {result['total_components']}"
                f"\n  Articles created: {result['articles_created']}"
                f"\n  Articles updated: {result['articles_updated']}"
                f"\n  Errors: {result['errors']}"
                f"\n  Dry run: {result['dry_run']}"
                f"\n"
            )

            if result['errors'] > 0:
                self.stdout.write(
                    self.style.WARNING(
                        f"⚠️  {result['errors']} errors occurred during sync. Check logs for details."
                    )
                )

            if dry_run:
                self.stdout.write(
                    self.style.WARNING(
                        f"\n💡 This was a dry run. Run without --dry-run to apply changes."
                    )
                )

        except (ValueError, TypeError, KeyError, AttributeError, ImportError) as e:
            raise CommandError(f"❌ Unexpected error during sync: {e}")
