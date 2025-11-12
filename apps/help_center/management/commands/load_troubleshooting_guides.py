"""
Load Troubleshooting Guide Fixtures

Management command to populate help center with troubleshooting articles
created during remediation work (Phases 1-6).

Usage:
    python manage.py load_troubleshooting_guides
    python manage.py load_troubleshooting_guides --clear  # Clear existing first
"""

from django.core.management.base import BaseCommand
from django.core.management import call_command
from apps.help_center.models import HelpArticle, HelpCategory, HelpTag


class Command(BaseCommand):
    help = 'Load troubleshooting guide fixtures into help center'

    def add_arguments(self, parser):
        parser.add_argument(
            '--clear',
            action='store_true',
            help='Clear existing troubleshooting content before loading',
        )

    def handle(self, *args, **options):
        if options['clear']:
            self.stdout.write('Clearing existing troubleshooting content...')
            
            # Delete troubleshooting categories and their articles
            HelpCategory.objects.filter(
                slug__startswith='troubleshooting-'
            ).delete()
            
            # Delete troubleshooting tags
            HelpTag.objects.filter(
                slug__in=[
                    'security', 'performance', 'code-quality',
                    'testing', 'refactoring', 'idor', 'n-plus-one',
                    'exception-handling', 'deep-nesting', 'god-files'
                ]
            ).delete()
            
            self.stdout.write(self.style.SUCCESS('✓ Cleared existing content'))

        fixtures = [
            'troubleshooting_guides_nov_2025.json',
            'troubleshooting_articles_security.json',
            'troubleshooting_articles_performance.json',
            'troubleshooting_articles_code_quality.json',
        ]

        self.stdout.write('Loading troubleshooting guides...')
        
        for fixture in fixtures:
            self.stdout.write(f'  Loading {fixture}...')
            try:
                call_command(
                    'loaddata',
                    f'apps/help_center/fixtures/{fixture}',
                    verbosity=0
                )
                self.stdout.write(self.style.SUCCESS(f'    ✓ Loaded {fixture}'))
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f'    ✗ Error loading {fixture}: {e}')
                )

        # Report statistics
        self.stdout.write('\n' + '=' * 60)
        self.stdout.write('📊 Troubleshooting Guide Statistics')
        self.stdout.write('=' * 60)
        
        categories = HelpCategory.objects.filter(
            slug__startswith='troubleshooting-'
        ).count()
        
        articles = HelpArticle.objects.filter(
            category__slug__startswith='troubleshooting-'
        ).count()
        
        tags = HelpTag.objects.filter(
            slug__in=[
                'security', 'performance', 'code-quality',
                'testing', 'refactoring', 'idor', 'n-plus-one',
                'exception-handling', 'deep-nesting', 'god-files'
            ]
        ).count()
        
        self.stdout.write(f'Categories: {categories}')
        self.stdout.write(f'Articles: {articles}')
        self.stdout.write(f'Tags: {tags}')
        self.stdout.write('=' * 60)
        
        self.stdout.write(
            self.style.SUCCESS('\n✓ Troubleshooting guides loaded successfully!')
        )
        self.stdout.write('\nAccess at: /help-center/ or /api/help-center/')
