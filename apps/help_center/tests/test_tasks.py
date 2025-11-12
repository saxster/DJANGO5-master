"""
Celery Task Tests for Help Center.

Tests background task execution, retry logic, error handling.

Tasks tested:
- generate_article_embedding
- analyze_ticket_content_gap
- generate_help_analytics

Tests exception handling patterns:
- DATABASE_EXCEPTIONS (should retry)
- ValueError/TypeError/AttributeError (should return error dict)
- ObjectDoesNotExist (should return not found error)
"""

import pytest
from unittest.mock import patch, MagicMock
from django.db import OperationalError, IntegrityError
from celery.exceptions import Retry
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


# ===== Exception Handling Tests =====
# Tests for fixed duplicate exception handlers and proper retry logic


@pytest.mark.django_db
class TestEmbeddingExceptionHandling:
    """Test exception handling in generate_article_embedding task."""

    def test_handles_value_error(self, tenant, user):
        """Test task handles ValueError (not DATABASE_EXCEPTIONS)."""
        category = HelpCategory.objects.create(tenant=tenant, name="Test", slug="test")
        article = HelpArticle.objects.create(
            tenant=tenant,
            title="Test",
            slug="test",
            content="Content",
            category=category,
            created_by=user,
            last_updated_by=user
        )

        # Mock embedding function to raise ValueError
        with patch('apps.help_center.utils.embedding.text_to_embedding') as mock_embed:
            mock_embed.side_effect = ValueError("Invalid embedding input")

            result = generate_article_embedding(article.id)

            assert result['success'] is False
            assert 'error' in result
            assert 'Invalid embedding input' in result['error']

    def test_handles_type_error(self, tenant, user):
        """Test task handles TypeError (not DATABASE_EXCEPTIONS)."""
        category = HelpCategory.objects.create(tenant=tenant, name="Test", slug="test")
        article = HelpArticle.objects.create(
            tenant=tenant,
            title="Test",
            slug="test",
            content="Content",
            category=category,
            created_by=user,
            last_updated_by=user
        )

        with patch('apps.help_center.utils.embedding.text_to_embedding') as mock_embed:
            mock_embed.side_effect = TypeError("Invalid type")

            result = generate_article_embedding(article.id)

            assert result['success'] is False
            assert 'error' in result


@pytest.mark.django_db
class TestContentGapExceptionHandling:
    """Test exception handling in analyze_ticket_content_gap task."""

    def test_retries_on_database_error(self, tenant, user):
        """Test task retries on DATABASE_EXCEPTIONS."""
        from apps.y_helpdesk.models import Ticket

        ticket = Ticket.objects.create(
            tenant=tenant,
            title="Test",
            description="Desc",
            created_by=user
        )
        correlation = HelpTicketCorrelation.create_from_ticket(ticket=ticket)

        # Mock save to raise OperationalError
        with patch.object(HelpTicketCorrelation, 'save') as mock_save:
            mock_save.side_effect = OperationalError("Database locked")

            # Celery tasks retry by raising Retry exception
            # We need to catch it to verify retry happens
            task_obj = analyze_ticket_content_gap
            with patch.object(task_obj, 'retry', side_effect=Retry()) as mock_retry:
                with pytest.raises(Retry):
                    analyze_ticket_content_gap(correlation.id)

                # Verify retry was called
                mock_retry.assert_called_once()

    def test_handles_value_error_without_retry(self, tenant, user):
        """Test ValueError returns error dict without retry."""
        from apps.y_helpdesk.models import Ticket

        ticket = Ticket.objects.create(
            tenant=tenant,
            title="Test",
            description="Desc",
            created_by=user
        )
        correlation = HelpTicketCorrelation.create_from_ticket(ticket=ticket)

        # Mock service to raise ValueError
        with patch('apps.help_center.services.ticket_integration_service.TicketIntegrationService._find_relevant_article') as mock_find:
            mock_find.side_effect = ValueError("Invalid search query")

            result = analyze_ticket_content_gap(correlation.id)

            assert result['success'] is False
            assert 'error' in result
            assert 'Invalid search query' in result['error']


@pytest.mark.django_db
class TestAnalyticsExceptionHandling:
    """Test exception handling in generate_help_analytics task."""

    def test_retries_on_integrity_error(self, tenant):
        """Test task retries on IntegrityError (DATABASE_EXCEPTIONS)."""
        # Mock AnalyticsService to raise IntegrityError
        with patch('apps.help_center.services.analytics_service.AnalyticsService.get_effectiveness_dashboard') as mock_dashboard:
            mock_dashboard.side_effect = IntegrityError("Constraint violation")

            task_obj = generate_help_analytics
            with patch.object(task_obj, 'retry', side_effect=Retry()) as mock_retry:
                with pytest.raises(Retry):
                    generate_help_analytics(tenant.id)

                mock_retry.assert_called_once()

    def test_handles_attribute_error(self, tenant):
        """Test AttributeError returns error dict."""
        with patch('apps.help_center.services.analytics_service.AnalyticsService.get_effectiveness_dashboard') as mock_dashboard:
            mock_dashboard.side_effect = AttributeError("Missing attribute")

            result = generate_help_analytics(tenant.id)

            assert result['success'] is False
            assert 'error' in result
            assert 'Missing attribute' in result['error']

    def test_tenant_not_found(self):
        """Test task handles non-existent tenant."""
        result = generate_help_analytics(99999)

        assert result['success'] is False
        assert 'not found' in result['error'].lower()
