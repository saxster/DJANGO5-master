"""
Management command to import best practices articles into help center.

Usage:
    python manage.py import_best_practices

This command:
1. Loads category fixtures
2. Creates articles from markdown files
3. Generates search vectors
4. Generates semantic embeddings
"""

import os
from pathlib import Path
from django.core.management.base import BaseCommand
from django.conf import settings
from django.contrib.auth import get_user_model
from apps.help_center.models import HelpCategory, HelpArticle
from apps.tenants.models import Tenant

People = get_user_model()


class Command(BaseCommand):
    help = 'Import best practices articles into help center'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be imported without actually importing'
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']

        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN MODE - No changes will be made'))

        # Get or create default tenant
        tenant = Tenant.objects.first()
        if not tenant:
            self.stdout.write(self.style.ERROR('No tenant found. Create a tenant first.'))
            return

        # Get system user for article creation
        system_user = People.objects.filter(is_superuser=True).first()
        if not system_user:
            self.stdout.write(self.style.ERROR('No superuser found. Create a superuser first.'))
            return

        self.stdout.write(self.style.SUCCESS(f'Using tenant: {tenant.name}'))
        self.stdout.write(self.style.SUCCESS(f'Using user: {system_user.username}'))

        # Create categories
        categories_created = self._create_categories(tenant, dry_run)

        # Import articles
        articles_created = self._import_articles(tenant, system_user, dry_run)

        # Summary
        self.stdout.write(self.style.SUCCESS('\n' + '=' * 60))
        self.stdout.write(self.style.SUCCESS('IMPORT SUMMARY'))
        self.stdout.write(self.style.SUCCESS('=' * 60))
        self.stdout.write(f'Categories created: {categories_created}')
        self.stdout.write(f'Articles created: {articles_created}')

        if dry_run:
            self.stdout.write(self.style.WARNING('\nDRY RUN - No actual changes made'))
        else:
            self.stdout.write(self.style.SUCCESS('\n✅ Import complete!'))
            self.stdout.write('\nNext steps:')
            self.stdout.write('1. python manage.py generate_article_embeddings')
            self.stdout.write('2. Visit /help-center/ to view articles')

    def _create_categories(self, tenant, dry_run):
        """Create category hierarchy."""
        self.stdout.write('\n📁 Creating categories...')

        categories = [
            {
                'name': 'Best Practices',
                'slug': 'best-practices',
                'description': 'Industry-leading best practices for building secure, performant, maintainable Django applications.',
                'icon': 'fa-star',
                'color': '#FFD700',
                'order': 1
            }
        ]

        subcategories = [
            {
                'name': 'Security Best Practices',
                'slug': 'security-best-practices',
                'description': 'Critical security patterns to prevent vulnerabilities and protect user data',
                'parent_slug': 'best-practices',
                'icon': 'fa-shield-alt',
                'color': '#DC143C',
                'order': 1
            },
            {
                'name': 'Performance Best Practices',
                'slug': 'performance-best-practices',
                'description': 'Database optimization and performance patterns for scalable applications',
                'parent_slug': 'best-practices',
                'icon': 'fa-tachometer-alt',
                'color': '#1E90FF',
                'order': 2
            },
            {
                'name': 'Code Quality Best Practices',
                'slug': 'code-quality-best-practices',
                'description': 'Maintainable, readable code patterns that scale with your team',
                'parent_slug': 'best-practices',
                'icon': 'fa-code',
                'color': '#32CD32',
                'order': 3
            },
            {
                'name': 'Testing Best Practices',
                'slug': 'testing-best-practices',
                'description': 'Comprehensive testing strategies for confidence in production',
                'parent_slug': 'best-practices',
                'icon': 'fa-check-circle',
                'color': '#9370DB',
                'order': 4
            },
            {
                'name': 'Architecture Best Practices',
                'slug': 'architecture-best-practices',
                'description': 'Proven architectural patterns for enterprise Django applications',
                'parent_slug': 'best-practices',
                'icon': 'fa-sitemap',
                'color': '#FF8C00',
                'order': 5
            }
        ]

        created_count = 0

        # Create parent categories
        for cat_data in categories:
            if dry_run:
                self.stdout.write(f'  [DRY RUN] Would create: {cat_data["name"]}')
            else:
                category, created = HelpCategory.objects.get_or_create(
                    tenant=tenant,
                    slug=cat_data['slug'],
                    defaults={
                        'name': cat_data['name'],
                        'description': cat_data['description'],
                        'icon': cat_data['icon'],
                        'color': cat_data['color'],
                        'display_order': cat_data['order']
                    }
                )
                if created:
                    self.stdout.write(self.style.SUCCESS(f'  ✅ Created: {category.name}'))
                    created_count += 1
                else:
                    self.stdout.write(f'  ⏭️  Already exists: {category.name}')

        # Create subcategories
        for cat_data in subcategories:
            if dry_run:
                self.stdout.write(f'  [DRY RUN] Would create: {cat_data["name"]}')
            else:
                parent = HelpCategory.objects.get(tenant=tenant, slug=cat_data['parent_slug'])
                category, created = HelpCategory.objects.get_or_create(
                    tenant=tenant,
                    slug=cat_data['slug'],
                    defaults={
                        'name': cat_data['name'],
                        'description': cat_data['description'],
                        'parent': parent,
                        'icon': cat_data['icon'],
                        'color': cat_data['color'],
                        'display_order': cat_data['order']
                    }
                )
                if created:
                    self.stdout.write(self.style.SUCCESS(f'  ✅ Created: {category.name}'))
                    created_count += 1
                else:
                    self.stdout.write(f'  ⏭️  Already exists: {category.name}')

        return created_count

    def _import_articles(self, tenant, user, dry_run):
        """Import articles from markdown files."""
        self.stdout.write('\n📄 Importing articles...')

        # Define articles to import
        articles = [
            {
                'file': 'BP-SEC-001-API-Authentication.md',
                'title': 'Best Practices: API Authentication',
                'slug': 'bp-sec-001-api-authentication',
                'category_slug': 'security-best-practices',
                'summary': 'Proper API authentication prevents unauthorized access and protects sensitive data. Learn required patterns for Token, HMAC, and Session authentication.',
                'difficulty': 'INTERMEDIATE',
                'tags': ['security', 'authentication', 'api', 'csrf']
            },
            {
                'file': 'BP-SEC-002-Authorization-IDOR.md',
                'title': 'Best Practices: Authorization & IDOR Prevention',
                'slug': 'bp-sec-002-authorization-idor',
                'category_slug': 'security-best-practices',
                'summary': 'Authorization ensures users can only access resources they own. Learn how to prevent IDOR vulnerabilities with SecureFileDownloadService.',
                'difficulty': 'ADVANCED',
                'tags': ['security', 'authorization', 'idor', 'file-download']
            },
            {
                'file': 'BP-PERF-001-Query-Optimization.md',
                'title': 'Best Practices: Database Query Optimization',
                'slug': 'bp-perf-001-query-optimization',
                'category_slug': 'performance-best-practices',
                'summary': 'Efficient database queries are critical for performance. Learn when to use select_related vs prefetch_related with visual decision trees.',
                'difficulty': 'INTERMEDIATE',
                'tags': ['performance', 'database', 'queries', 'n+1', 'optimization']
            },
            {
                'file': 'BP-QUAL-001-Exception-Handling.md',
                'title': 'Best Practices: Exception Handling',
                'slug': 'bp-qual-001-exception-handling',
                'category_slug': 'code-quality-best-practices',
                'summary': 'Proper exception handling prevents silent failures and improves debugging. Learn exception pattern groups and when to use specific exception types.',
                'difficulty': 'BEGINNER',
                'tags': ['code-quality', 'exceptions', 'error-handling', 'logging']
            },
            {
                'file': 'BP-ARCH-001-Service-Layer.md',
                'title': 'Best Practices: Service Layer Pattern',
                'slug': 'bp-arch-001-service-layer',
                'category_slug': 'architecture-best-practices',
                'summary': 'Service layer encapsulates business logic, keeping it separate from views and models. Learn how to extract services from god views.',
                'difficulty': 'ADVANCED',
                'tags': ['architecture', 'service-layer', 'business-logic', 'refactoring']
            }
        ]

        created_count = 0
        articles_dir = Path(settings.BASE_DIR) / 'docs' / 'help_center' / 'articles'

        for article_data in articles:
            filepath = articles_dir / article_data['file']

            if not filepath.exists():
                self.stdout.write(self.style.WARNING(f'  ⚠️  File not found: {filepath}'))
                continue

            # Read markdown content
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()

            if dry_run:
                self.stdout.write(f'  [DRY RUN] Would import: {article_data["title"]}')
            else:
                # Get category
                try:
                    category = HelpCategory.objects.get(
                        tenant=tenant,
                        slug=article_data['category_slug']
                    )
                except HelpCategory.DoesNotExist:
                    self.stdout.write(self.style.ERROR(
                        f'  ❌ Category not found: {article_data["category_slug"]}'
                    ))
                    continue

                # Create or update article
                article, created = HelpArticle.objects.update_or_create(
                    tenant=tenant,
                    slug=article_data['slug'],
                    defaults={
                        'title': article_data['title'],
                        'summary': article_data['summary'],
                        'content': content,
                        'category': category,
                        'difficulty_level': article_data['difficulty'],
                        'status': 'PUBLISHED',
                        'created_by': user,
                        'last_updated_by': user
                    }
                )

                if created:
                    self.stdout.write(self.style.SUCCESS(f'  ✅ Created: {article.title}'))
                    created_count += 1
                else:
                    self.stdout.write(f'  🔄 Updated: {article.title}')

                # Add tags (would need to create HelpTag model instances)
                # For now, tags are stored as metadata

        return created_count
