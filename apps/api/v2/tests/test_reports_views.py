"""
Test V2 Reports API Endpoints

Tests for report generation with V2 enhancements:
- Standardized response envelope with correlation_id
- Async generation with Celery
- Secure file download

Following TDD: Tests written BEFORE implementation.
"""

import pytest
from django.urls import reverse
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status
from unittest.mock import patch, MagicMock

People = get_user_model()


@pytest.mark.django_db
class TestReportGenerateView:
    """Test POST /api/v2/reports/generate/ endpoint."""

    @patch('background_tasks.report_tasks.generate_report_task.delay')
    def test_authenticated_user_can_queue_report_generation(self, mock_task):
        """
        Test that authenticated user can queue report generation.

        V2 Response format:
        {
            "success": true,
            "data": {
                "report_id": "uuid-here",
                "status": "queued",
                "status_url": "/api/v2/reports/{id}/status/"
            },
            "meta": {
                "correlation_id": "uuid-here",
                "timestamp": "2025-11-07T..."
            }
        }
        """
        # Arrange: Create user
        user = People.objects.create_user(
            username='test@example.com',
            password='password123'
        )

        # Login
        client = APIClient()
        login_url = reverse('api_v2:auth-login')
        login_response = client.post(login_url, {
            'username': 'test@example.com',
            'password': 'password123'
        }, format='json')
        access_token = login_response.data['data']['access']

        # Act: Request report generation
        client.credentials(HTTP_AUTHORIZATION=f'Bearer {access_token}')
        url = reverse('api_v2:reports-generate')
        response = client.post(url, {
            'report_type': 'attendance_summary',
            'format': 'pdf',
            'date_from': '2025-10-01T00:00:00Z',
            'date_to': '2025-10-31T23:59:59Z'
        }, format='json')

        # Assert: Verify response
        assert response.status_code == status.HTTP_202_ACCEPTED
        assert response.data['success'] is True
        assert 'data' in response.data

        # Report ID and status returned
        data = response.data['data']
        assert 'report_id' in data
        assert data['status'] == 'queued'
        assert 'status_url' in data

        # Meta contains correlation_id
        assert 'correlation_id' in response.data['meta']

        # Celery task was called
        assert mock_task.called

    def test_missing_report_type_returns_400(self):
        """Test that missing report_type returns 400."""
        # Arrange: Create user and login
        user = People.objects.create_user(
            username='test@example.com',
            password='password123'
        )

        client = APIClient()
        login_url = reverse('api_v2:auth-login')
        login_response = client.post(login_url, {
            'username': 'test@example.com',
            'password': 'password123'
        }, format='json')
        access_token = login_response.data['data']['access']

        # Act: Request without report_type
        client.credentials(HTTP_AUTHORIZATION=f'Bearer {access_token}')
        url = reverse('api_v2:reports-generate')
        response = client.post(url, {
            'format': 'pdf'
        }, format='json')

        # Assert
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.data['success'] is False
        assert response.data['error']['code'] == 'VALIDATION_ERROR'

    def test_unauthenticated_request_returns_401(self):
        """Test that unauthenticated request returns 401."""
        client = APIClient()
        url = reverse('api_v2:reports-generate')

        # Act: Request without authentication
        response = client.post(url, {
            'report_type': 'test',
            'format': 'pdf'
        }, format='json')

        # Assert
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
class TestReportStatusView:
    """Test GET /api/v2/reports/{id}/status/ endpoint."""

    @patch('django.core.cache.cache.get')
    def test_get_report_status_returns_current_state(self, mock_cache):
        """Test that report status endpoint returns generation state."""
        # Arrange: Mock cache to return status
        mock_cache.return_value = {
            'status': 'completed',
            'progress': 100,
            'file_size': 1024000
        }

        # Create user and login
        user = People.objects.create_user(
            username='test@example.com',
            password='password123'
        )

        client = APIClient()
        login_url = reverse('api_v2:auth-login')
        login_response = client.post(login_url, {
            'username': 'test@example.com',
            'password': 'password123'
        }, format='json')
        access_token = login_response.data['data']['access']

        # Act: Get report status
        client.credentials(HTTP_AUTHORIZATION=f'Bearer {access_token}')
        report_id = 'test-report-123'
        url = reverse('api_v2:reports-status', kwargs={'report_id': report_id})
        response = client.get(url, format='json')

        # Assert: Verify response
        assert response.status_code == status.HTTP_200_OK
        assert response.data['success'] is True

        # Status data returned
        data = response.data['data']
        assert data['status'] == 'completed'
        assert data['progress'] == 100

    @patch('django.core.cache.cache.get')
    def test_nonexistent_report_returns_404(self, mock_cache):
        """Test that non-existent report returns 404."""
        # Arrange: Mock cache to return None
        mock_cache.return_value = None

        user = People.objects.create_user(
            username='test@example.com',
            password='password123'
        )

        client = APIClient()
        login_url = reverse('api_v2:auth-login')
        login_response = client.post(login_url, {
            'username': 'test@example.com',
            'password': 'password123'
        }, format='json')
        access_token = login_response.data['data']['access']

        # Act: Get non-existent report
        client.credentials(HTTP_AUTHORIZATION=f'Bearer {access_token}')
        url = reverse('api_v2:reports-status', kwargs={'report_id': 'nonexistent'})
        response = client.get(url, format='json')

        # Assert
        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert response.data['success'] is False
        assert response.data['error']['code'] == 'REPORT_NOT_FOUND'


@pytest.mark.django_db
class TestReportDownloadView:
    """Test GET /api/v2/reports/{id}/download/ endpoint."""

    @patch('django.core.cache.cache.get')
    @patch('apps.core.services.secure_file_download_service.SecureFileDownloadService.validate_and_serve_file')
    def test_download_completed_report(self, mock_serve, mock_cache):
        """Test that completed report can be downloaded."""
        # Arrange: Mock cache and file service
        mock_cache.return_value = '/path/to/report.pdf'
        mock_serve.return_value = MagicMock(status_code=200)

        user = People.objects.create_user(
            username='test@example.com',
            password='password123'
        )

        client = APIClient()
        login_url = reverse('api_v2:auth-login')
        login_response = client.post(login_url, {
            'username': 'test@example.com',
            'password': 'password123'
        }, format='json')
        access_token = login_response.data['data']['access']

        # Act: Download report
        client.credentials(HTTP_AUTHORIZATION=f'Bearer {access_token}')
        report_id = 'test-report-123'
        url = reverse('api_v2:reports-download', kwargs={'report_id': report_id})
        response = client.get(url, format='json')

        # Assert: File service was called
        assert mock_serve.called

    @patch('django.core.cache.cache.get')
    def test_download_nonexistent_report_returns_404(self, mock_cache):
        """Test that downloading non-existent report returns 404."""
        # Arrange: Mock cache to return None
        mock_cache.return_value = None

        user = People.objects.create_user(
            username='test@example.com',
            password='password123'
        )

        client = APIClient()
        login_url = reverse('api_v2:auth-login')
        login_response = client.post(login_url, {
            'username': 'test@example.com',
            'password': 'password123'
        }, format='json')
        access_token = login_response.data['data']['access']

        # Act: Download non-existent report
        client.credentials(HTTP_AUTHORIZATION=f'Bearer {access_token}')
        url = reverse('api_v2:reports-download', kwargs={'report_id': 'nonexistent'})
        response = client.get(url, format='json')

        # Assert
        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert response.data['success'] is False
        assert response.data['error']['code'] == 'REPORT_NOT_FOUND'
