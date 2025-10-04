"""
Integration Tests for Global Search

Tests complete search flow from API to adapters

Complies with Rule #7: < 150 lines per test class
"""

import pytest
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient
from apps.peoples.models import People
from apps.tenants.models import Tenant
from apps.y_helpdesk.models import Ticket
from apps.work_order_management.models import WOM


@pytest.mark.django_db
class TestGlobalSearchIntegration:
    """Integration tests for global search API"""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test data"""
        self.client = APIClient()

        self.tenant = Tenant.objects.create(
            tenantname='TestTenant',
            tenantcode='TEST001'
        )

        self.user = People.objects.create_user(
            loginid='testuser',
            peoplename='Test User',
            email='test@example.com',
            tenant=self.tenant
        )

        self.client.force_authenticate(user=self.user)

    def test_search_api_requires_authentication(self):
        """Test that search API requires authentication"""

        client = APIClient()

        response = client.post(
            reverse('search:global-search'),
            {'query': 'test'}
        )

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_search_with_valid_query(self):
        """Test search with valid query returns results"""

        response = self.client.post(
            reverse('search:global-search'),
            {'query': 'test query', 'limit': 10},
            format='json'
        )

        assert response.status_code == status.HTTP_200_OK
        assert 'results' in response.data
        assert 'total_results' in response.data
        assert 'response_time_ms' in response.data
        assert 'query_id' in response.data

    def test_search_validates_query_length(self):
        """Test search validates minimum query length"""

        response = self.client.post(
            reverse('search:global-search'),
            {'query': 'a'},
            format='json'
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_search_filters_by_entity_type(self):
        """Test search respects entity type filters"""

        response = self.client.post(
            reverse('search:global-search'),
            {
                'query': 'test',
                'entities': ['people', 'ticket']
            },
            format='json'
        )

        assert response.status_code == status.HTTP_200_OK

    def test_tenant_isolation_in_search(self):
        """Test that search results are tenant-isolated"""

        other_tenant = Tenant.objects.create(
            tenantname='OtherTenant',
            tenantcode='OTHER001'
        )

        other_user = People.objects.create_user(
            loginid='otheruser',
            peoplename='Other User',
            email='other@example.com',
            tenant=other_tenant
        )

        response = self.client.post(
            reverse('search:global-search'),
            {'query': 'Other User'},
            format='json'
        )

        assert response.status_code == status.HTTP_200_OK
        results = response.data.get('results', [])

        for result in results:
            assert result.get('id') != str(other_user.uuid)


@pytest.mark.django_db
class TestSavedSearchAPI:
    """Tests for saved search functionality"""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test data"""
        self.client = APIClient()

        self.tenant = Tenant.objects.create(
            tenantname='TestTenant',
            tenantcode='TEST001'
        )

        self.user = People.objects.create_user(
            loginid='testuser',
            peoplename='Test User',
            email='test@example.com',
            tenant=self.tenant
        )

        self.client.force_authenticate(user=self.user)

    def test_create_saved_search(self):
        """Test creating a saved search"""

        response = self.client.post(
            reverse('search:saved-search-list'),
            {
                'name': 'Overdue Tickets',
                'query': 'overdue',
                'entities': ['ticket'],
                'is_alert_enabled': True,
                'alert_frequency': 'daily'
            },
            format='json'
        )

        assert response.status_code == status.HTTP_201_CREATED
        assert 'id' in response.data

    def test_list_saved_searches(self):
        """Test listing user's saved searches"""

        from apps.search.models import SavedSearch

        SavedSearch.objects.create(
            tenant=self.tenant,
            user=self.user,
            name='Test Search',
            query='test query'
        )

        response = self.client.get(
            reverse('search:saved-search-list')
        )

        assert response.status_code == status.HTTP_200_OK
        assert 'saved_searches' in response.data
        assert len(response.data['saved_searches']) > 0