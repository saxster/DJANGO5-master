"""
Service Tests for Help Center.

Tests all service layer business logic.

Target Coverage: 85%+

Services tested:
- KnowledgeService (CRUD operations)
- SearchService (hybrid search)
- AnalyticsService (metrics calculation)
- TicketIntegrationService (correlation)
"""

import pytest
import uuid
from datetime import timedelta
from django.utils import timezone
from django.core.exceptions import ValidationError
from apps.help_center.services.knowledge_service import KnowledgeService
from apps.help_center.services.search_service import SearchService
from apps.help_center.services.analytics_service import AnalyticsService
from apps.help_center.services.ticket_integration_service import TicketIntegrationService
from apps.help_center.models import (
    HelpCategory,
    HelpArticle,
    HelpSearchHistory,
    HelpArticleInteraction,
    HelpTicketCorrelation,
)


@pytest.fixture
def tenant(db):
    """Create test tenant."""
    from apps.tenants.models import Tenant
    return Tenant.objects.create(tenantname="Test Tenant", subdomain_prefix="test")


@pytest.fixture
def user(db, tenant):
    """Create test user with supervisor role."""
    from apps.peoples.models import People
    from django.contrib.auth.models import Group

    user = People.objects.create_user(
        username="testuser",
        email="test@example.com",
        password="testpass123",
        tenant=tenant
    )

    group = Group.objects.create(name="Supervisor")
    user.groups.add(group)

    return user


@pytest.fixture
def help_category(db, tenant):
    """Create test category."""
    return HelpCategory.objects.create(
        tenant=tenant,
        name="Operations",
        slug="operations"
    )


@pytest.mark.django_db
class TestKnowledgeService:
    """Test KnowledgeService."""

    def test_create_article(self, tenant, user, help_category):
        """Test article creation."""
        article = KnowledgeService.create_article(
            tenant=tenant,
            title="Test Article",
            content="Test content here",
            category_id=help_category.id,
            created_by=user,
            summary="Test summary",
            difficulty_level="BEGINNER",
            target_roles=["all"]
        )

        assert article.id is not None
        assert article.title == "Test Article"
        assert article.slug == "test-article"
        assert article.status == "DRAFT"
        assert article.version == 1

    def test_create_article_unique_slug(self, tenant, user, help_category):
        """Test unique slug generation."""
        article1 = KnowledgeService.create_article(
            tenant=tenant,
            title="Same Title",
            content="Content 1",
            category_id=help_category.id,
            created_by=user
        )

        article2 = KnowledgeService.create_article(
            tenant=tenant,
            title="Same Title",
            content="Content 2",
            category_id=help_category.id,
            created_by=user
        )

        assert article1.slug == "same-title"
        assert article2.slug.startswith("same-title-")
        assert article1.slug != article2.slug

    def test_create_article_invalid_category(self, tenant, user):
        """Test article creation with invalid category."""
        with pytest.raises(ValidationError, match="Category .* not found"):
            KnowledgeService.create_article(
                tenant=tenant,
                title="Test",
                content="Content",
                category_id=99999,  # Non-existent
                created_by=user
            )

    def test_update_article(self, tenant, user, help_category):
        """Test article update."""
        article = KnowledgeService.create_article(
            tenant=tenant,
            title="Original Title",
            content="Original content",
            category_id=help_category.id,
            created_by=user
        )

        updated = KnowledgeService.update_article(
            article_id=article.id,
            updated_by=user,
            title="Updated Title",
            content="Updated content"
        )

        assert updated.title == "Updated Title"
        assert updated.content == "Updated content"
        assert updated.version == 2  # Version incremented due to content change

    def test_publish_article(self, tenant, user, help_category):
        """Test article publishing."""
        article = KnowledgeService.create_article(
            tenant=tenant,
            title="Test",
            content="Content",
            category_id=help_category.id,
            created_by=user,
            target_roles=["all"]
        )

        published = KnowledgeService.publish_article(
            article_id=article.id,
            published_by=user
        )

        assert published.status == "PUBLISHED"
        assert published.published_date is not None

    def test_publish_article_validation(self, tenant, user, help_category):
        """Test publish validation."""
        # Article without target_roles
        article = KnowledgeService.create_article(
            tenant=tenant,
            title="Test",
            content="Content",
            category_id=help_category.id,
            created_by=user,
            target_roles=[]  # Empty
        )

        with pytest.raises(ValidationError, match="without target roles"):
            KnowledgeService.publish_article(
                article_id=article.id,
                published_by=user
            )


@pytest.mark.django_db
class TestSearchService:
    """Test SearchService."""

    def test_hybrid_search(self, tenant, user, help_category):
        """Test hybrid search."""
        # Create test articles
        article1 = HelpArticle.objects.create(
            tenant=tenant,
            title="How to Create Work Order",
            slug="create-work-order",
            summary="Guide to creating work orders",
            content="Step by step instructions...",
            category=help_category,
            created_by=user,
            last_updated_by=user,
            status="PUBLISHED",
            target_roles=["all"]
        )

        article2 = HelpArticle.objects.create(
            tenant=tenant,
            title="Work Order Approval Process",
            slug="work-order-approval",
            summary="How to approve work orders",
            content="Approval workflow...",
            category=help_category,
            created_by=user,
            last_updated_by=user,
            status="PUBLISHED",
            target_roles=["all"]
        )

        results = SearchService.hybrid_search(
            tenant=tenant,
            user=user,
            query="work order",
            limit=10
        )

        assert results['total'] >= 2
        assert len(results['results']) >= 2
        assert results['search_id'] is not None

    def test_record_click(self, tenant, user, help_category):
        """Test click tracking."""
        article = HelpArticle.objects.create(
            tenant=tenant,
            title="Test Article",
            slug="test",
            content="Content",
            category=help_category,
            created_by=user,
            last_updated_by=user,
            status="PUBLISHED",
            target_roles=["all"]
        )

        # Create search history
        search_history = HelpSearchHistory.objects.create(
            tenant=tenant,
            user=user,
            query="test",
            results_count=1
        )

        initial_view_count = article.view_count

        SearchService.record_click(
            search_id=search_history.id,
            article_id=article.id,
            position=1
        )

        search_history.refresh_from_db()
        article.refresh_from_db()

        assert search_history.clicked_article == article
        assert search_history.click_position == 1
        assert article.view_count == initial_view_count + 1


@pytest.mark.django_db
class TestAnalyticsService:
    """Test AnalyticsService."""

    def test_get_effectiveness_dashboard(self, tenant, user):
        """Test analytics dashboard generation."""
        date_from = timezone.now() - timedelta(days=30)
        date_to = timezone.now()

        metrics = AnalyticsService.get_effectiveness_dashboard(
            tenant=tenant,
            date_from=date_from,
            date_to=date_to
        )

        assert 'usage' in metrics
        assert 'effectiveness' in metrics
        assert 'content_performance' in metrics

        assert 'daily_active_users' in metrics['usage']
        assert 'total_article_views' in metrics['usage']
        assert 'total_searches' in metrics['usage']

    def test_calculate_usage_metrics(self, tenant, user, help_category):
        """Test usage metrics calculation."""
        # Create test data
        article = HelpArticle.objects.create(
            tenant=tenant,
            title="Test",
            slug="test",
            content="Content",
            category=help_category,
            created_by=user,
            last_updated_by=user,
            status="PUBLISHED",
            target_roles=["all"]
        )

        session_id = uuid.uuid4()
        HelpArticleInteraction.record_view(
            article=article,
            user=user,
            session_id=session_id
        )

        HelpSearchHistory.objects.create(
            tenant=tenant,
            user=user,
            query="test",
            results_count=1
        )

        date_from = timezone.now() - timedelta(days=1)
        date_to = timezone.now() + timedelta(days=1)

        metrics = AnalyticsService._calculate_usage_metrics(tenant, date_from, date_to)

        assert metrics['daily_active_users'] >= 1
        assert metrics['total_article_views'] >= 1
        assert metrics['total_searches'] >= 1


@pytest.mark.django_db
class TestTicketIntegrationService:
    """Test TicketIntegrationService."""

    def test_analyze_ticket_help_usage_no_help(self, tenant, user):
        """Test analysis when user didn't view help."""
        from apps.y_helpdesk.models import Ticket

        ticket = Ticket.objects.create(
            tenant=tenant,
            title="Test Ticket",
            description="Issue description",
            created_by=user
        )

        correlation = TicketIntegrationService.analyze_ticket_help_usage(ticket)

        assert correlation.ticket == ticket
        assert correlation.help_attempted is False

    def test_analyze_ticket_help_usage_with_help(self, tenant, user, help_category):
        """Test analysis when user viewed help articles."""
        from apps.y_helpdesk.models import Ticket

        # User views help article
        article = HelpArticle.objects.create(
            tenant=tenant,
            title="Test Help",
            slug="test-help",
            content="Help content",
            category=help_category,
            created_by=user,
            last_updated_by=user,
            status="PUBLISHED",
            target_roles=["all"]
        )

        session_id = uuid.uuid4()
        HelpArticleInteraction.record_view(
            article=article,
            user=user,
            session_id=session_id
        )

        # Create ticket within 30 minutes
        ticket = Ticket.objects.create(
            tenant=tenant,
            title="Test Ticket",
            description="Issue",
            created_by=user
        )

        correlation = TicketIntegrationService.analyze_ticket_help_usage(ticket)

        assert correlation.help_attempted is True
        assert article in correlation.articles_viewed.all()
