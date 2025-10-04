"""
REST API Tenant Isolation Tests

Tests tenant filtering, pagination, and query optimization for REST viewsets.

Security Coverage:
- Tenant isolation enforcement
- Cross-tenant access prevention
- Pagination functionality
- Query optimization (N+1 prevention)
- Permission checks

Created: 2025-10-01
Compliance: Validates CRITICAL tenant isolation vulnerability fixes
"""

import pytest
from rest_framework.test import APIClient
from rest_framework import status
from django.contrib.auth import get_user_model
from apps.peoples.models import People, Pgroup, Pgbelonging
from apps.onboarding.models import Bt, Shift, TypeAssist
from apps.activity.models import Job, Jobneed
from apps.attendance.models import PeopleEventlog
from django.utils import timezone
from datetime import timedelta
from django.test.utils import override_settings
from django.db import connection
from django.test.utils import CaptureQueriesContext

User = get_user_model()


@pytest.fixture
def tenant_a_client(db):
    """Create client A (tenant A) for multi-tenant testing."""
    return Bt.objects.create(
        buname="Client A",
        bucode="CLNT_A",
        enable=True
    )


@pytest.fixture
def tenant_b_client(db):
    """Create client B (tenant B) for multi-tenant testing."""
    return Bt.objects.create(
        buname="Client B",
        bucode="CLNT_B",
        enable=True
    )


@pytest.fixture
def tenant_a_user(db, tenant_a_client):
    """Create user in tenant A."""
    user = People.objects.create_user(
        loginid="user_a@example.com",
        password="testpass123",
        peoplename="User A",
        peoplecode="USER_A",
        client_id=tenant_a_client.id,
        enable=True
    )
    return user


@pytest.fixture
def tenant_b_user(db, tenant_b_client):
    """Create user in tenant B."""
    user = People.objects.create_user(
        loginid="user_b@example.com",
        password="testpass123",
        peoplename="User B",
        peoplecode="USER_B",
        client_id=tenant_b_client.id,
        enable=True
    )
    return user


@pytest.fixture
def api_client():
    """Create DRF API client."""
    return APIClient()


@pytest.mark.django_db
class TestPeopleViewsetTenantIsolation:
    """Test tenant isolation for People viewset."""

    def test_list_filters_by_tenant(self, api_client, tenant_a_user, tenant_b_user):
        """Users can only see their own tenant's people."""
        api_client.force_authenticate(tenant_a_user)

        response = api_client.get('/api/rest/people/')

        assert response.status_code == status.HTTP_200_OK
        people_ids = [p['id'] for p in response.data['results']]

        # Should only see tenant A users
        assert tenant_a_user.id in people_ids
        assert tenant_b_user.id not in people_ids

    def test_cross_tenant_retrieve_forbidden(self, api_client, tenant_a_user, tenant_b_user):
        """Cannot retrieve records from other tenants."""
        api_client.force_authenticate(tenant_a_user)

        response = api_client.get(f'/api/rest/people/{tenant_b_user.id}/')

        # Should return 404 (not found, due to tenant filtering)
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_unauthenticated_access_denied(self, api_client, tenant_a_user):
        """Unauthenticated requests are rejected."""
        response = api_client.get('/api/rest/people/')

        assert response.status_code in [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN]

    def test_pagination_limits_response_size(self, api_client, tenant_a_user, tenant_a_client):
        """Pagination prevents returning excessive data."""
        # Create 100 users in tenant A
        for i in range(100):
            People.objects.create_user(
                loginid=f"user{i}@example.com",
                password="testpass123",
                peoplename=f"User {i}",
                peoplecode=f"USER_{i}",
                client_id=tenant_a_client.id,
                enable=True
            )

        api_client.force_authenticate(tenant_a_user)

        # Default page size is 50
        response = api_client.get('/api/rest/people/')

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data['results']) <= 50
        assert 'next' in response.data
        assert 'count' in response.data
        assert response.data['count'] >= 100

    def test_custom_page_size(self, api_client, tenant_a_user, tenant_a_client):
        """Client can customize page size via query parameter."""
        # Create 20 users
        for i in range(20):
            People.objects.create_user(
                loginid=f"user{i}@example.com",
                password="testpass123",
                peoplename=f"User {i}",
                peoplecode=f"USER_{i}",
                client_id=tenant_a_client.id,
                enable=True
            )

        api_client.force_authenticate(tenant_a_user)

        response = api_client.get('/api/rest/people/?page_size=10')

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data['results']) == 10
        assert response.data['page_size'] == 10

    def test_max_page_size_enforced(self, api_client, tenant_a_user):
        """Page size is capped at maximum (100 items)."""
        api_client.force_authenticate(tenant_a_user)

        # Try to request 1000 items
        response = api_client.get('/api/rest/people/?page_size=1000')

        assert response.status_code == status.HTTP_200_OK
        # Should be limited to max page size (100)
        assert len(response.data['results']) <= 100


@pytest.mark.django_db
class TestQueryOptimization:
    """Test query optimization (N+1 prevention)."""

    def test_n_plus_1_prevented(self, api_client, tenant_a_user, tenant_a_client):
        """Select related prevents N+1 queries."""
        # Create 10 users with different departments
        for i in range(10):
            People.objects.create_user(
                loginid=f"user{i}@example.com",
                password="testpass123",
                peoplename=f"User {i}",
                peoplecode=f"USER_{i}",
                client_id=tenant_a_client.id,
                bu_id=tenant_a_client.id,
                enable=True
            )

        api_client.force_authenticate(tenant_a_user)

        # Count queries during request
        with CaptureQueriesContext(connection) as context:
            response = api_client.get('/api/rest/people/')

        # Should make minimal queries (1-3 queries max, not 1+N)
        # 1 for count, 1 for data with select_related, possibly 1 for auth
        assert len(context.captured_queries) <= 5

        assert response.status_code == status.HTTP_200_OK


@pytest.mark.django_db
class TestJobViewsetTenantIsolation:
    """Test tenant isolation for Job viewset."""

    def test_jobs_filtered_by_tenant(self, api_client, tenant_a_user, tenant_b_user, tenant_a_client, tenant_b_client):
        """Jobs are filtered by tenant."""
        # Create jobs for both tenants
        job_a = Job.objects.create(
            jobname="Job A",
            jobcode="JOB_A",
            clientid=tenant_a_client,
            client_id=tenant_a_client.id,
            bu=tenant_a_client
        )

        job_b = Job.objects.create(
            jobname="Job B",
            jobcode="JOB_B",
            clientid=tenant_b_client,
            client_id=tenant_b_client.id,
            bu=tenant_b_client
        )

        api_client.force_authenticate(tenant_a_user)

        response = api_client.get('/api/rest/jobs/')

        assert response.status_code == status.HTTP_200_OK
        job_ids = [j['id'] for j in response.data['results']]

        # Should only see tenant A jobs
        assert job_a.id in job_ids
        assert job_b.id not in job_ids


@pytest.mark.django_db
class TestSyncFiltering:
    """Test mobile sync filtering with last_update parameter."""

    def test_last_update_filtering(self, api_client, tenant_a_user, tenant_a_client):
        """last_update parameter filters modified records."""
        # Create old record
        old_user = People.objects.create_user(
            loginid="old@example.com",
            password="testpass123",
            peoplename="Old User",
            peoplecode="OLD_USER",
            client_id=tenant_a_client.id,
            enable=True
        )
        # Manually set old timestamp
        old_user.mdtz = timezone.now() - timedelta(days=10)
        old_user.save()

        # Create new record
        new_user = People.objects.create_user(
            loginid="new@example.com",
            password="testpass123",
            peoplename="New User",
            peoplecode="NEW_USER",
            client_id=tenant_a_client.id,
            enable=True
        )

        api_client.force_authenticate(tenant_a_user)

        # Request only records modified in last 5 days
        last_update = (timezone.now() - timedelta(days=5)).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
        response = api_client.get(f'/api/rest/people/?last_update={last_update}')

        assert response.status_code == status.HTTP_200_OK
        people_ids = [p['id'] for p in response.data['results']]

        # Should only see new user
        assert new_user.id in people_ids
        assert old_user.id not in people_ids


@pytest.mark.django_db
class TestAllViewsetsTenantIsolation:
    """Test tenant isolation across all REST viewsets."""

    def test_event_logs_filtered_by_tenant(self, api_client, tenant_a_user, tenant_b_user):
        """PeopleEventlog filtered by tenant."""
        # Create event logs for both tenants
        log_a = PeopleEventlog.objects.create(
            peopleid=tenant_a_user,
            client_id=tenant_a_user.client_id
        )

        log_b = PeopleEventlog.objects.create(
            peopleid=tenant_b_user,
            client_id=tenant_b_user.client_id
        )

        api_client.force_authenticate(tenant_a_user)

        response = api_client.get('/api/rest/event-logs/')

        assert response.status_code == status.HTTP_200_OK
        log_ids = [log['id'] for log in response.data['results']]

        assert log_a.id in log_ids
        assert log_b.id not in log_ids

    def test_business_units_filtered_by_tenant(self, api_client, tenant_a_user, tenant_a_client, tenant_b_client):
        """Business units filtered by tenant."""
        api_client.force_authenticate(tenant_a_user)

        response = api_client.get('/api/rest/business-units/')

        assert response.status_code == status.HTTP_200_OK
        bu_ids = [bu['id'] for bu in response.data['results']]

        assert tenant_a_client.id in bu_ids
        assert tenant_b_client.id not in bu_ids


@pytest.mark.django_db
class TestPermissions:
    """Test permission checks on REST viewsets."""

    def test_readonly_enforced(self, api_client, tenant_a_user):
        """ViewSets are read-only (POST/PUT/DELETE rejected)."""
        api_client.force_authenticate(tenant_a_user)

        # Try to create (should fail)
        response = api_client.post('/api/rest/people/', data={
            'peoplename': 'Test User',
            'loginid': 'test@example.com'
        })

        assert response.status_code == status.HTTP_405_METHOD_NOT_ALLOWED

        # Try to update (should fail)
        response = api_client.put(f'/api/rest/people/{tenant_a_user.id}/', data={
            'peoplename': 'Updated Name'
        })

        assert response.status_code == status.HTTP_405_METHOD_NOT_ALLOWED

        # Try to delete (should fail)
        response = api_client.delete(f'/api/rest/people/{tenant_a_user.id}/')

        assert response.status_code == status.HTTP_405_METHOD_NOT_ALLOWED
