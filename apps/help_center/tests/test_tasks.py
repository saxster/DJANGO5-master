"""
Celery Task Tests for Help Center.

Tests background task execution, retry logic, error handling.

Tasks tested:
- generate_article_embedding
- analyze_ticket_content_gap
- generate_help_analytics
"""

import pytest
from apps.help_center.tasks import (
    generate_article_embedding,
    analyze_ticket_content_gap,
    generate_help_analytics,
)
from apps.help_center.models import HelpArticle, HelpCategory, HelpTicketCorrelation


@pytest.fixture
def tenant(db):
    """Create test tenant."""
    from apps.tenants.models import Tenant
    return Tenant.objects.create(tenantname="Test", subdomain_prefix="test")


@pytest.fixture
def user(db, tenant):
    """Create test user."""
    from apps.peoples.models import People
    return People.objects.create_user(
        username="testuser",
        email="test@example.com",
        password="pass123",
        tenant=tenant
    )


@pytest.mark.django_db
class TestGenerateArticleEmbedding:
    """Test embedding generation task."""

    def test_generate_embedding_success(self, tenant, user):
        """Test successful embedding generation."""
        category = HelpCategory.objects.create(tenant=tenant, name="Test", slug="test")
        article = HelpArticle.objects.create(
            tenant=tenant,
            title="Test",
            slug="test",
            content="Content here",
            category=category,
            created_by=user,
            last_updated_by=user
        )

        result = generate_article_embedding(article.id)

        assert result['success'] is True
        assert result['article_id'] == article.id

        article.refresh_from_db()
        assert article.embedding is not None

    def test_generate_embedding_article_not_found(self):
        """Test task handles missing article."""
        result = generate_article_embedding(99999)

        assert result['success'] is False
        assert 'not found' in result['error'].lower()


@pytest.mark.django_db
class TestAnalyzeTicketContentGap:
    """Test content gap analysis task."""

    def test_analyze_content_gap(self, tenant, user):
        """Test content gap analysis."""
        from apps.y_helpdesk.models import Ticket

        ticket = Ticket.objects.create(
            tenant=tenant,
            title="Test Issue",
            description="Description",
            created_by=user
        )

        correlation = HelpTicketCorrelation.create_from_ticket(ticket=ticket)

        result = analyze_ticket_content_gap(correlation.id)

        assert result['success'] is True
        assert 'content_gap' in result


@pytest.mark.django_db
class TestGenerateHelpAnalytics:
    """Test analytics generation task."""

    def test_generate_analytics(self, tenant):
        """Test analytics generation."""
        result = generate_help_analytics(tenant.id)

        assert result['success'] is True
        assert 'metrics' in result
