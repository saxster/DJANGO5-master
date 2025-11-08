"""
Management Command: Update Admin Ontology
=========================================

Registers all admin enhancement knowledge into the ontology system.

Usage:
    python manage.py update_admin_ontology
    python manage.py update_admin_ontology --verbose
    python manage.py update_admin_ontology --dry-run

Created: November 7, 2025
"""

from django.core.management.base import BaseCommand
from django.db import transaction
from apps.ontology.registrations.admin_enhancements_nov2025 import (
    register_admin_enhancement_knowledge
)


class Command(BaseCommand):
    help = 'Updates ontology with admin enhancement knowledge (100+ entries)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Show detailed output',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Simulate without making changes',
        )

    def handle(self, *args, **options):
        verbose = options['verbose']
        dry_run = options['dry-run']

        if dry_run:
            self.stdout.write(
                self.style.WARNING('🔍 DRY RUN MODE - No changes will be made')
            )

        self.stdout.write(
            self.style.SUCCESS('🚀 Updating Admin Ontology Knowledge...\n')
        )

        try:
            if dry_run:
                # Don't actually save
                result = {
                    'categories': 8,
                    'knowledge_entries': 100,
                    'relationships': 50,
                    'best_practices': 20,
                    'troubleshooting': 30
                }
                self.stdout.write('  (Dry run - simulated results)')
            else:
                # Actually register
                result = register_admin_enhancement_knowledge()

            # Display results
            self.stdout.write('\n' + '='*60)
            self.stdout.write(self.style.SUCCESS('✅ ONTOLOGY UPDATE COMPLETE!'))
            self.stdout.write('='*60)
            self.stdout.write(f"📁 Categories: {result['categories']}")
            self.stdout.write(f"📚 Knowledge Entries: {result['knowledge_entries']}")
            self.stdout.write(f"🔗 Relationships: {result['relationships']}")
            self.stdout.write(f"✅ Best Practices: {result['best_practices']}")
            self.stdout.write(f"🔧 Troubleshooting: {result['troubleshooting']}")
            self.stdout.write('='*60 + '\n')

            if not dry_run:
                self.stdout.write(
                    self.style.SUCCESS(
                        '✅ All knowledge successfully registered in ontology!'
                    )
                )

        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'❌ Error: {str(e)}')
            )
            if verbose:
                import traceback
                self.stdout.write(traceback.format_exc())
            raise
