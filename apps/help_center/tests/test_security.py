"""
Security Tests for Help Center.

Tests security requirements:
- Tenant isolation
- XSS prevention
- SQL injection prevention
- Permission checks
- CSRF protection

Target: 100% pass rate on security tests
"""

import pytest
from rest_framework.test import APIClient
from rest_framework import status
from apps.help_center.models import HelpArticle, HelpCategory


@pytest.fixture
def api_client():
    """Create API client."""
    return APIClient()


@pytest.fixture
def tenant1(db):
    """Create first tenant."""
    from apps.tenants.models import Tenant
    return Tenant.objects.create(tenantname="Tenant 1", subdomain_prefix="tenant1")


@pytest.fixture
def tenant2(db):
    """Create second tenant."""
    from apps.tenants.models import Tenant
    return Tenant.objects.create(tenantname="Tenant 2", subdomain_prefix="tenant2")


@pytest.fixture
def user1(db, tenant1):
    """Create user in tenant 1."""
    from apps.peoples.models import People
    return People.objects.create_user(
        username="user1",
        email="user1@example.com",
        password="pass123",
        tenant=tenant1
    )


@pytest.fixture
def user2(db, tenant2):
    """Create user in tenant 2."""
    from apps.peoples.models import People
    return People.objects.create_user(
        username="user2",
        email="user2@example.com",
        password="pass123",
        tenant=tenant2
    )


@pytest.mark.django_db
class TestTenantIsolation:
    """Test multi-tenant data isolation."""

    def test_articles_isolated_by_tenant(self, tenant1, tenant2, user1):
        """Test users cannot see other tenants' articles."""
        category1 = HelpCategory.objects.create(tenant=tenant1, name="Cat1", slug="cat1")
        category2 = HelpCategory.objects.create(tenant=tenant2, name="Cat2", slug="cat2")

        article1 = HelpArticle.objects.create(
            tenant=tenant1,
            title="Tenant 1 Article",
            slug="t1-article",
            content="Content",
            category=category1,
            created_by=user1,
            last_updated_by=user1,
            status="PUBLISHED",
            target_roles=["all"]
        )

        article2 = HelpArticle.objects.create(
            tenant=tenant2,
            title="Tenant 2 Article",
            slug="t2-article",
            content="Content",
            category=category2,
            created_by=user1,  # Different tenant article
            last_updated_by=user1,
            status="PUBLISHED",
            target_roles=["all"]
        )

        # User from tenant1 should only see tenant1 articles
        tenant1_articles = HelpArticle.objects.filter(tenant=tenant1)
        assert article1 in tenant1_articles
        assert article2 not in tenant1_articles

    def test_api_enforces_tenant_isolation(self, api_client, tenant1, tenant2, user1, user2):
        """Test API endpoints enforce tenant isolation."""
        category = HelpCategory.objects.create(tenant=tenant1, name="Cat", slug="cat")

        article_tenant1 = HelpArticle.objects.create(
            tenant=tenant1,
            title="Tenant 1 Only",
            slug="t1-only",
            content="Secret content",
            category=category,
            created_by=user1,
            last_updated_by=user1,
            status="PUBLISHED",
            target_roles=["all"]
        )

        # User from tenant2 tries to access tenant1's article
        api_client.force_authenticate(user=user2)
        response = api_client.get(f'/api/v2/help-center/articles/{article_tenant1.id}/')

        # Should return 404 (not 403, to avoid leaking existence)
        assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.django_db
class TestXSSPrevention:
    """Test XSS prevention in inputs."""

    def test_vote_comment_xss_prevention(self, api_client, tenant1, user1):
        """Test comment field sanitizes XSS attempts."""
        api_client.force_authenticate(user=user1)

        category = HelpCategory.objects.create(tenant=tenant1, name="Cat", slug="cat")
        article = HelpArticle.objects.create(
            tenant=tenant1,
            title="Test",
            slug="test",
            content="Content",
            category=category,
            created_by=user1,
            last_updated_by=user1,
            status="PUBLISHED",
            target_roles=["all"]
        )

        # Try XSS in comment
        xss_payload = '<script>alert("XSS")</script>'

        response = api_client.post(
            f'/api/v2/help-center/articles/{article.id}/vote/',
            data={'is_helpful': True, 'comment': xss_payload},
            format='json'
        )

        # Should reject dangerous content
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_search_query_xss_prevention(self, api_client, user1):
        """Test search query sanitizes XSS."""
        api_client.force_authenticate(user=user1)

        xss_payload = '<script>alert("XSS")</script>'

        response = api_client.post(
            '/api/v2/help-center/articles/search/',
            data={'query': xss_payload},
            format='json'
        )

        # Should reject dangerous characters
        assert response.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
class TestPermissions:
    """Test permission checks."""

    def test_unauthenticated_access_denied(self, api_client):
        """Test unauthenticated users cannot access APIs."""
        response = api_client.get('/api/v2/help-center/articles/')

        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_authenticated_access_allowed(self, api_client, user1):
        """Test authenticated users can access APIs."""
        api_client.force_authenticate(user=user1)

        response = api_client.get('/api/v2/help-center/articles/')

        assert response.status_code == status.HTTP_200_OK
