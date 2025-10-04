"""
NOC Overview View Tests.

Tests for dashboard overview API endpoint.
"""

import pytest
from rest_framework.test import APIClient
from rest_framework import status
from django.urls import reverse


@pytest.mark.django_db
class TestNOCOverviewView:
    """Tests for NOC Overview API endpoint."""

    def test_overview_requires_authentication(self):
        """Test overview endpoint requires authentication."""
        client = APIClient()
        url = reverse('noc:overview')
        response = client.get(url)

        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_overview_requires_noc_capability(self, client_with_user_no_capability):
        """Test overview requires noc:view capability."""
        url = reverse('noc:overview')
        response = client_with_user_no_capability.get(url)

        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_overview_with_valid_capability(self, client_with_noc_capability, sample_metrics):
        """Test overview returns data with valid capability."""
        url = reverse('noc:overview')
        response = client_with_noc_capability.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert 'data' in response.data
        assert 'tickets_open' in response.data['data']
        assert 'active_alerts' in response.data['data']

    def test_overview_filters_by_client(self, client_with_noc_capability, sample_metrics, sample_client):
        """Test overview can filter by client_ids."""
        url = reverse('noc:overview')
        response = client_with_noc_capability.get(url, {'client_ids': str(sample_client.id)})

        assert response.status_code == status.HTTP_200_OK

    def test_overview_time_range_parameter(self, client_with_noc_capability, sample_metrics):
        """Test overview accepts time_range parameter."""
        url = reverse('noc:overview')
        response = client_with_noc_capability.get(url, {'time_range': '48'})

        assert response.status_code == status.HTTP_200_OK
        assert response.data['data']['time_range_hours'] == 48

    def test_overview_pii_masking(self, client_with_noc_capability_no_pii, sample_metrics):
        """Test overview applies PII masking for users without permission."""
        url = reverse('noc:overview')
        response = client_with_noc_capability_no_pii.get(url)

        assert response.status_code == status.HTTP_200_OK


@pytest.mark.django_db
class TestNOCOverviewRBAC:
    """Tests for RBAC enforcement in overview endpoint."""

    def test_view_all_clients_capability(self, client_with_view_all_clients, multiple_clients):
        """Test user with view_all_clients sees all clients."""
        url = reverse('noc:overview')
        response = client_with_view_all_clients.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert response.data['data']['clients_count'] >= 2

    def test_view_single_client_capability(self, client_with_single_client_view, multiple_clients):
        """Test user with view_client sees only their client."""
        url = reverse('noc:overview')
        response = client_with_single_client_view.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert response.data['data']['clients_count'] == 1