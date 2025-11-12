"""
API Tests for Help Center.

Tests all REST API endpoints, permissions, serialization.

Target Coverage: 80%+

Endpoints tested:
- Article list/detail/search/vote
- Category list/detail
- Analytics event/dashboard
"""

import pytest
import uuid
from rest_framework.test import APIClient
from rest_framework import status
from django.urls import reverse
from apps.help_center.models import HelpArticle, HelpCategory


@pytest.fixture
def api_client():
    """Create API client."""
    return APIClient()


@pytest.fixture
def tenant(db):
    """Create test tenant."""
    from apps.tenants.models import Tenant
    return Tenant.objects.create(tenantname="Test Tenant", subdomain_prefix="test")


@pytest.fixture
def user(db, tenant):
    """Create authenticated user."""
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
def authenticated_client(api_client, user):
    """Create authenticated API client."""
    api_client.force_authenticate(user=user)
    return api_client


@pytest.fixture
def help_article(db, tenant, user):
    """Create test article."""
    category = HelpCategory.objects.create(tenant=tenant, name="Test", slug="test")

    return HelpArticle.objects.create(
        tenant=tenant,
        title="Test Article",
        slug="test-article",
        summary="Summary",
        content="Content here",
        category=category,
        created_by=user,
        last_updated_by=user,
        status="PUBLISHED",
        target_roles=["all"]
    )


@pytest.mark.django_db
class TestHelpArticleAPI:
    """Test Article API endpoints."""

    def test_list_articles_unauthenticated(self, api_client):
        """Test list requires authentication."""
        response = api_client.get('/api/v2/help-center/articles/')

        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_list_articles_authenticated(self, authenticated_client, help_article):
        """Test article list."""
        response = authenticated_client.get('/api/v2/help-center/articles/')

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) >= 1

    def test_retrieve_article(self, authenticated_client, help_article):
        """Test article detail retrieval."""
        response = authenticated_client.get(f'/api/v2/help-center/articles/{help_article.id}/')

        assert response.status_code == status.HTTP_200_OK
        assert response.data['title'] == help_article.title
        assert response.data['content'] == help_article.content

    def test_search_articles(self, authenticated_client, help_article):
        """Test search endpoint."""
        response = authenticated_client.post(
            '/api/v2/help-center/articles/search/',
            data={'query': 'test', 'limit': 10},
            format='json'
        )

        assert response.status_code == status.HTTP_200_OK
        assert 'results' in response.data
        assert 'total' in response.data
        assert 'search_id' in response.data

    def test_search_validation(self, authenticated_client):
        """Test search input validation."""
        # Query too short
        response = authenticated_client.post(
            '/api/v2/help-center/articles/search/',
            data={'query': 'a'},  # Only 1 character
            format='json'
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_vote_helpful(self, authenticated_client, help_article):
        """Test helpful vote."""
        initial_helpful = help_article.helpful_count

        response = authenticated_client.post(
            f'/api/v2/help-center/articles/{help_article.id}/vote/',
            data={'is_helpful': True, 'comment': 'Great article!'},
            format='json'
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.data['success'] is True

        help_article.refresh_from_db()
        assert help_article.helpful_count == initial_helpful + 1

    def test_vote_not_helpful(self, authenticated_client, help_article):
        """Test not helpful vote."""
        initial_not_helpful = help_article.not_helpful_count

        response = authenticated_client.post(
            f'/api/v2/help-center/articles/{help_article.id}/vote/',
            data={'is_helpful': False, 'comment': 'Needs improvement'},
            format='json'
        )

        assert response.status_code == status.HTTP_200_OK

        help_article.refresh_from_db()
        assert help_article.not_helpful_count == initial_not_helpful + 1


@pytest.mark.django_db
class TestHelpCategoryAPI:
    """Test Category API endpoints."""

    def test_list_categories(self, authenticated_client, tenant):
        """Test category list."""
        category = HelpCategory.objects.create(
            tenant=tenant,
            name="Operations",
            slug="operations",
            is_active=True
        )

        response = authenticated_client.get('/api/v2/help-center/categories/')

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) >= 1


@pytest.mark.django_db
class TestHelpAnalyticsAPI:
    """Test Analytics API endpoints."""

    def test_track_event(self, authenticated_client, help_article):
        """Test event tracking."""
        session_id = uuid.uuid4()

        response = authenticated_client.post(
            '/api/v2/help-center/analytics/event/',
            data={
                'event_type': 'article_view',
                'article_id': help_article.id,
                'session_id': str(session_id),
                'time_spent_seconds': 45
            },
            format='json'
        )

        assert response.status_code == status.HTTP_201_CREATED
        assert response.data['success'] is True

    def test_analytics_dashboard(self, authenticated_client):
        """Test analytics dashboard."""
        response = authenticated_client.get('/api/v2/help-center/analytics/dashboard/')

        assert response.status_code == status.HTTP_200_OK
        assert 'usage' in response.data
        assert 'effectiveness' in response.data
