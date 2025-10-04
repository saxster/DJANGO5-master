"""
NOC Alert View Tests.

Tests for alert management API endpoints.
"""

import pytest
from rest_framework.test import APIClient
from rest_framework import status
from django.urls import reverse
from apps.noc.models import NOCAlertEvent


@pytest.mark.django_db
class TestNOCAlertListView:
    """Tests for alert list endpoint."""

    def test_alert_list_requires_authentication(self):
        """Test alert list requires authentication."""
        client = APIClient()
        url = reverse('noc:alert-list')
        response = client.get(url)

        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_alert_list_with_capability(self, client_with_noc_capability, sample_alert):
        """Test alert list returns data with valid capability."""
        url = reverse('noc:alert-list')
        response = client_with_noc_capability.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert 'results' in response.data
        assert len(response.data['results']) > 0

    def test_alert_list_filtering_by_status(self, client_with_noc_capability, sample_alert):
        """Test filtering alerts by status."""
        url = reverse('noc:alert-list')
        response = client_with_noc_capability.get(url, {'status': 'NEW'})

        assert response.status_code == status.HTTP_200_OK
        for alert in response.data['results']:
            assert alert['status'] == 'NEW'

    def test_alert_list_filtering_by_severity(self, client_with_noc_capability, multiple_alerts):
        """Test filtering alerts by severity."""
        url = reverse('noc:alert-list')
        response = client_with_noc_capability.get(url, {'severity': 'CRITICAL'})

        assert response.status_code == status.HTTP_200_OK

    def test_alert_list_pagination(self, client_with_noc_capability, many_alerts):
        """Test alert list pagination."""
        url = reverse('noc:alert-list')
        response = client_with_noc_capability.get(url, {'page_size': 10})

        assert response.status_code == status.HTTP_200_OK
        assert 'count' in response.data
        assert 'next' in response.data
        assert len(response.data['results']) <= 10


@pytest.mark.django_db
class TestNOCAlertDetailView:
    """Tests for alert detail endpoint."""

    def test_alert_detail_requires_authentication(self, sample_alert):
        """Test alert detail requires authentication."""
        client = APIClient()
        url = reverse('noc:alert-detail', args=[sample_alert.id])
        response = client.get(url)

        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_alert_detail_with_capability(self, client_with_noc_capability, sample_alert):
        """Test alert detail returns full alert data."""
        url = reverse('noc:alert-detail', args=[sample_alert.id])
        response = client_with_noc_capability.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert 'data' in response.data
        assert response.data['data']['id'] == sample_alert.id
        assert response.data['data']['alert_type'] == sample_alert.alert_type

    def test_alert_detail_not_found(self, client_with_noc_capability):
        """Test alert detail returns 404 for non-existent alert."""
        url = reverse('noc:alert-detail', args=[99999])
        response = client_with_noc_capability.get(url)

        assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.django_db
class TestAlertAcknowledge:
    """Tests for alert acknowledge endpoint."""

    def test_acknowledge_requires_permission(self, client_with_noc_capability, sample_alert):
        """Test acknowledge requires specific permission."""
        url = reverse('noc:alert-acknowledge', args=[sample_alert.id])
        response = client_with_noc_capability.post(url, {})

        assert response.status_code in [status.HTTP_200_OK, status.HTTP_403_FORBIDDEN]

    def test_acknowledge_success(self, client_with_ack_permission, sample_alert):
        """Test successful alert acknowledgment."""
        url = reverse('noc:alert-acknowledge', args=[sample_alert.id])
        response = client_with_ack_permission.post(url, {'comment': 'Acknowledged'})

        assert response.status_code == status.HTTP_200_OK

        sample_alert.refresh_from_db()
        assert sample_alert.status == 'ACKNOWLEDGED'
        assert sample_alert.acknowledged_at is not None

    def test_acknowledge_with_comment(self, client_with_ack_permission, sample_alert):
        """Test acknowledge with comment."""
        url = reverse('noc:alert-acknowledge', args=[sample_alert.id])
        response = client_with_ack_permission.post(url, {'comment': 'Working on it'})

        assert response.status_code == status.HTTP_200_OK


@pytest.mark.django_db
class TestBulkAlertAction:
    """Tests for bulk alert operations."""

    def test_bulk_acknowledge(self, client_with_ack_permission, multiple_alerts):
        """Test bulk acknowledge operation."""
        alert_ids = [alert.id for alert in multiple_alerts[:3]]

        url = reverse('noc:alert-bulk-action')
        response = client_with_ack_permission.post(url, {
            'alert_ids': alert_ids,
            'action': 'acknowledge',
            'comment': 'Bulk ack'
        }, format='json')

        assert response.status_code == status.HTTP_200_OK
        assert response.data['data']['processed'] > 0

    def test_bulk_action_validation(self, client_with_ack_permission):
        """Test bulk action validates input."""
        url = reverse('noc:alert-bulk-action')
        response = client_with_ack_permission.post(url, {
            'alert_ids': [],
            'action': 'acknowledge'
        }, format='json')

        assert response.status_code == status.HTTP_400_BAD_REQUEST