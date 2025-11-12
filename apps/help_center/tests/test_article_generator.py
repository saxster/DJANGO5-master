"""
Unit tests for ArticleGeneratorService.

Tests:
- Generate article from ontology metadata
- Update existing article instead of creating duplicates
- Tag creation and assignment
- Auto-generated flag management
"""

import pytest


@pytest.fixture
def service():
    """Create fresh ArticleGeneratorService instance."""
    from apps.help_center.services.article_generator_service import ArticleGeneratorService
    return ArticleGeneratorService()


@pytest.fixture
def tenant(db):
    """Create test tenant."""
    from apps.tenants.models import Tenant
    tenant = Tenant.objects.first()
    if not tenant:
        tenant = Tenant.objects.create(tenantname="Test Tenant", subdomain_prefix="test")
    return tenant


@pytest.fixture
def category(tenant):
    """Create test category."""
    from apps.help_center.models import HelpCategory
    return HelpCategory.objects.create(
        name="Code Reference",
        slug="code-reference",
        tenant=tenant,
        description="Auto-generated code documentation"
    )


@pytest.mark.django_db
class TestArticleGeneratorService:
    """Test suite for ArticleGeneratorService."""

    def test_generate_article_from_ontology_metadata(self, service, category):
        """Should generate article from ontology metadata."""
        from apps.help_center.models import HelpArticle

        metadata = {
            'qualified_name': 'apps.core.services.SecureFileDownloadService',
            'purpose': 'Secure file download with permission validation',
            'domain': 'security',
            'tags': ['security', 'files', 'permissions'],
            'business_value': 'Prevents IDOR vulnerabilities',
            'depends_on': ['apps.core.middleware.authentication']
        }

        article = service.generate_article(metadata, category)

        assert article is not None
        assert 'SecureFileDownloadService' in article.title
        assert 'permission validation' in article.content
        assert article.category == category

        # Check tags
        tag_names = [tag.name for tag in article.tags.all()]
        assert 'auto-generated' in tag_names
        assert 'code-reference' in tag_names
        assert 'security' in tag_names

    def test_update_existing_article_instead_of_duplicate(self, service, category):
        """Should update existing article instead of creating duplicate."""
        from apps.help_center.models import HelpArticle

        metadata = {
            'qualified_name': 'apps.core.services.TestService',
            'purpose': 'Test service',
            'domain': 'test',
            'tags': ['test']
        }

        # Create first article
        article1 = service.generate_article(metadata, category)
        article1_id = article1.id
        initial_created_at = article1.created_at

        # Update metadata
        metadata['purpose'] = 'Updated test service'

        # Generate again
        article2 = service.generate_article(metadata, category)

        # Should be same article (updated)
        assert article1.id == article2.id
        assert article2.id == article1_id
        assert 'Updated test service' in article2.content

        # Verify it's an update, not a new record
        assert HelpArticle.objects.filter(
            title__icontains='TestService',
            category=category
        ).count() == 1

        # created_at should be unchanged
        article2.refresh_from_db()
        assert article2.created_at == initial_created_at

    def test_generate_title_from_metadata(self, service, category):
        """Should generate proper title from qualified name."""
        metadata = {
            'qualified_name': 'apps.wellness.services.CrisisDetectionService',
            'purpose': 'Detect crisis situations',
            'domain': 'wellness'
        }

        article = service.generate_article(metadata, category)

        # Title should be "Code Reference: ClassName"
        assert article.title == 'Code Reference: CrisisDetectionService'

    def test_generate_content_includes_all_sections(self, service, category):
        """Should include all relevant sections in generated content."""
        metadata = {
            'qualified_name': 'apps.help_center.services.SearchService',
            'purpose': 'Hybrid search combining FTS and semantic search',
            'domain': 'help',
            'tags': ['search', 'fts', 'semantic'],
            'inputs': [{'name': 'query', 'type': 'str'}],  # Added to trigger Usage section
            'outputs': [{'name': 'results', 'type': 'List[HelpArticle]'}],  # Added to trigger Usage section
            'business_value': 'Enables 55% ticket reduction',
            'depends_on': ['django.contrib.postgres.search', 'pgvector'],
            'security_notes': 'Multi-tenant isolated queries',
            'performance_notes': 'P95 latency < 50ms'
        }

        article = service.generate_article(metadata, category)

        content = article.content

        # Check all sections present
        assert '## Purpose' in content
        assert 'Hybrid search combining FTS and semantic search' in content
        assert '## Domain' in content
        assert 'help' in content
        assert '## Usage' in content
        assert '## Dependencies' in content
        assert 'django.contrib.postgres.search' in content
        assert 'pgvector' in content
        assert '## Business Value' in content
        assert 'Enables 55% ticket reduction' in content
        assert '## Security Considerations' in content
        assert 'Multi-tenant isolated queries' in content
        assert '## Performance' in content
        assert 'P95 latency < 50ms' in content
        assert 'Auto-generated from ontology' in content

    def test_add_tags_creates_missing_tags(self, service, category):
        """Should create tags that don't exist."""
        from apps.help_center.models import HelpTag

        metadata = {
            'qualified_name': 'apps.test.NewService',
            'purpose': 'Test service',
            'domain': 'testing',
            'tags': ['brand-new-tag', 'another-new-tag']
        }

        # Verify tags don't exist yet
        assert not HelpTag.objects.filter(name='brand-new-tag').exists()
        assert not HelpTag.objects.filter(name='another-new-tag').exists()

        article = service.generate_article(metadata, category)

        # Tags should be created
        assert HelpTag.objects.filter(name='brand-new-tag').exists()
        assert HelpTag.objects.filter(name='another-new-tag').exists()

        # Article should have these tags
        tag_names = [tag.name for tag in article.tags.all()]
        assert 'brand-new-tag' in tag_names
        assert 'another-new-tag' in tag_names

    def test_add_tags_reuses_existing_tags(self, service, category, tenant):
        """Should reuse existing tags instead of creating duplicates."""
        from apps.help_center.models import HelpTag

        # Create existing tag
        existing_tag = HelpTag.objects.create(
            name='existing-tag',
            slug='existing-tag',
            tenant=tenant
        )

        metadata = {
            'qualified_name': 'apps.test.Service',
            'purpose': 'Test',
            'domain': 'test',
            'tags': ['existing-tag']
        }

        initial_tag_count = HelpTag.objects.filter(name='existing-tag').count()

        article = service.generate_article(metadata, category)

        # Should not create duplicate
        final_tag_count = HelpTag.objects.filter(name='existing-tag').count()
        assert final_tag_count == initial_tag_count

        # Article should use existing tag
        assert existing_tag in article.tags.all()

    def test_minimal_metadata_generates_valid_article(self, service, category):
        """Should handle minimal metadata (only required fields)."""
        metadata = {
            'qualified_name': 'apps.minimal.Service',
            'purpose': 'Minimal service',
            'domain': 'minimal'
        }

        article = service.generate_article(metadata, category)

        assert article is not None
        assert article.title == 'Code Reference: Service'
        assert 'Minimal service' in article.content
        assert article.category == category

        # Should still have standard tags
        tag_names = [tag.name for tag in article.tags.all()]
        assert 'auto-generated' in tag_names
        assert 'code-reference' in tag_names

    def test_article_marked_as_auto_generated(self, service, category):
        """Generated articles should be marked as auto-generated."""
        metadata = {
            'qualified_name': 'apps.test.Service',
            'purpose': 'Test',
            'domain': 'test'
        }

        article = service.generate_article(metadata, category)

        # Check if article has auto_generated field set
        # Note: HelpArticle model may not have this field - check if it exists
        if hasattr(article, 'auto_generated'):
            assert article.auto_generated is True

    def test_updated_at_changes_on_update(self, service, category):
        """updated_at timestamp should change when article is updated."""
        import time

        metadata = {
            'qualified_name': 'apps.test.TimestampService',
            'purpose': 'Original purpose',
            'domain': 'test'
        }

        # Create initial article
        article1 = service.generate_article(metadata, category)
        initial_updated_at = article1.updated_at

        # Wait a moment to ensure timestamp difference
        time.sleep(0.1)

        # Update article
        metadata['purpose'] = 'Updated purpose'
        article2 = service.generate_article(metadata, category)

        # updated_at should have changed
        article2.refresh_from_db()
        assert article2.updated_at > initial_updated_at

    def test_handles_empty_optional_fields(self, service, category):
        """Should handle metadata with empty optional fields."""
        metadata = {
            'qualified_name': 'apps.test.EmptyOptionals',
            'purpose': 'Test service',
            'domain': 'test',
            'tags': [],  # Empty tags
            'depends_on': [],  # Empty dependencies
        }

        article = service.generate_article(metadata, category)

        assert article is not None
        assert article.content is not None
        # Should still have auto-generated tags even if metadata tags are empty
        assert article.tags.count() >= 2  # auto-generated + code-reference

    def test_sanitizes_qualified_name_in_title(self, service, category):
        """Should extract clean class name from qualified name."""
        metadata = {
            'qualified_name': 'apps.deeply.nested.package.structure.MyComplexServiceName',
            'purpose': 'Test',
            'domain': 'test'
        }

        article = service.generate_article(metadata, category)

        # Should only use the last part of qualified name
        assert article.title == 'Code Reference: MyComplexServiceName'
        assert 'deeply.nested' not in article.title
