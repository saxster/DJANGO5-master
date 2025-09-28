"""
CSRF Protection Tests for Admin Mutation Endpoints

Tests the CSRF protection and rate limiting on admin endpoints that modify
system state. These endpoints were previously vulnerable with @csrf_exempt.

Test Coverage:
1. TaskManagementAPIView (admin_task_dashboard.py:537)
2. TaskCancellationAPIView (async_monitoring_views.py:423)
3. RecommendationInteractionView (recommendation_views.py:99)

Security Compliance:
- Rule #3: Mandatory CSRF Protection (.claude/rules.md)
- CVSS 8.1 vulnerability remediation
- Zero tolerance for CSRF exemptions on mutation endpoints

Author: Security Remediation Team
Date: 2025-09-27
"""

import pytest
import json
from unittest.mock import Mock, patch, MagicMock

from django.test import TestCase, Client, RequestFactory
from django.contrib.auth import get_user_model
from django.middleware.csrf import get_token
from django.core.cache import cache
from django.utils import timezone

from apps.peoples.models import People
from apps.core.decorators import csrf_protect_ajax, rate_limit

User = get_user_model()


@pytest.mark.security
class TaskManagementAPIViewCSRFTest(TestCase):
    """
    Test CSRF protection on TaskManagementAPIView.

    Endpoint: apps/core/views/admin_task_dashboard.py:537
    Operations: cancel_task, restart_workers, purge_queue, clear_cache
    """

    def setUp(self):
        self.factory = RequestFactory()
        self.client = Client(enforce_csrf_checks=True)

        self.staff_user = People.objects.create_user(
            loginid='admin_user',
            email='admin@example.com',
            password='admin123secure',
            firstname='Admin',
            lastname='User'
        )
        self.staff_user.is_staff = True
        self.staff_user.is_superuser = True
        self.staff_user.save()

        self.client.login(username='admin_user', password='admin123secure')
        cache.clear()

    def tearDown(self):
        cache.clear()

    def test_cancel_task_rejects_without_csrf_token(self):
        """
        Test that cancel_task operation rejects requests without CSRF token.
        """
        payload = {
            'operation': 'cancel_task',
            'task_id': 'test-task-123'
        }

        response = self.client.post(
            '/admin/tasks/api/',
            data=json.dumps(payload),
            content_type='application/json'
        )

        self.assertEqual(response.status_code, 403)
        response_data = response.json()
        self.assertEqual(response_data['code'], 'CSRF_TOKEN_REQUIRED')

    def test_cancel_task_accepts_with_csrf_token_in_header(self):
        """
        Test that cancel_task operation accepts requests with CSRF token in header.
        """
        response = self.client.get('/admin/tasks/')
        csrf_token = get_token(response.wsgi_request)

        payload = {
            'operation': 'cancel_task',
            'task_id': 'test-task-123'
        }

        with patch('celery.current_app.control.revoke') as mock_revoke:
            response = self.client.post(
                '/admin/tasks/api/',
                data=json.dumps(payload),
                content_type='application/json',
                HTTP_X_CSRFTOKEN=csrf_token
            )

            self.assertNotEqual(response.status_code, 403)

    def test_purge_queue_rejects_without_csrf_token(self):
        """
        Test that purge_queue operation rejects requests without CSRF token.
        """
        payload = {
            'operation': 'purge_queue',
            'queue_name': 'default'
        }

        response = self.client.post(
            '/admin/tasks/api/',
            data=json.dumps(payload),
            content_type='application/json'
        )

        self.assertEqual(response.status_code, 403)

    def test_clear_cache_enforces_rate_limiting(self):
        """
        Test that clear_cache operation enforces rate limiting (20 requests per 5 min).
        """
        response = self.client.get('/admin/tasks/')
        csrf_token = get_token(response.wsgi_request)

        payload = {'operation': 'clear_cache'}

        for i in range(20):
            response = self.client.post(
                '/admin/tasks/api/',
                data=json.dumps(payload),
                content_type='application/json',
                HTTP_X_CSRFTOKEN=csrf_token
            )

        response = self.client.post(
            '/admin/tasks/api/',
            data=json.dumps(payload),
            content_type='application/json',
            HTTP_X_CSRFTOKEN=csrf_token
        )

        self.assertEqual(response.status_code, 429)
        response_data = response.json()
        self.assertEqual(response_data['code'], 'RATE_LIMIT_EXCEEDED')

    def test_restart_workers_requires_staff_access(self):
        """
        Test that restart_workers operation requires staff access.
        """
        regular_user = People.objects.create_user(
            loginid='regular_user',
            email='user@example.com',
            password='user123',
            firstname='Regular',
            lastname='User'
        )
        regular_user.is_staff = False
        regular_user.save()

        client = Client(enforce_csrf_checks=True)
        client.login(username='regular_user', password='user123')

        response = client.get('/admin/tasks/')
        csrf_token = get_token(response.wsgi_request)

        payload = {'operation': 'restart_workers'}

        response = client.post(
            '/admin/tasks/api/',
            data=json.dumps(payload),
            content_type='application/json',
            HTTP_X_CSRFTOKEN=csrf_token
        )

        self.assertIn(response.status_code, [403, 302])


@pytest.mark.security
class TaskCancellationAPIViewCSRFTest(TestCase):
    """
    Test CSRF protection on TaskCancellationAPIView.

    Endpoint: apps/core/views/async_monitoring_views.py:423
    Operation: Cancel async tasks
    """

    def setUp(self):
        self.client = Client(enforce_csrf_checks=True)

        self.user = People.objects.create_user(
            loginid='test_user',
            email='test@example.com',
            password='test123',
            firstname='Test',
            lastname='User'
        )
        self.user.save()

        self.client.login(username='test_user', password='test123')
        cache.clear()

    def tearDown(self):
        cache.clear()

    def test_cancel_task_rejects_without_csrf_token(self):
        """
        Test that task cancellation rejects requests without CSRF token.
        """
        task_id = 'test-task-456'

        response = self.client.post(f'/admin/async/cancel-task/{task_id}/')

        self.assertEqual(response.status_code, 403)
        response_data = response.json()
        self.assertEqual(response_data['code'], 'CSRF_TOKEN_REQUIRED')

    def test_cancel_task_accepts_with_csrf_token(self):
        """
        Test that task cancellation accepts requests with valid CSRF token.
        """
        response = self.client.get('/admin/async/monitoring/')
        csrf_token = get_token(response.wsgi_request)

        task_id = 'test-task-456'

        with patch('apps.core.services.async_pdf_service.AsyncPDFGenerationService.get_task_status') as mock_status:
            mock_status.return_value = {'status': 'processing', 'progress': 50}

            with patch('celery.current_app.control.revoke') as mock_revoke:
                response = self.client.post(
                    f'/admin/async/cancel-task/{task_id}/',
                    HTTP_X_CSRFTOKEN=csrf_token
                )

                self.assertNotEqual(response.status_code, 403)

    def test_cancel_task_enforces_rate_limiting(self):
        """
        Test that task cancellation enforces rate limiting (30 requests per 5 min).
        """
        response = self.client.get('/admin/async/monitoring/')
        csrf_token = get_token(response.wsgi_request)

        task_id = 'test-task-789'

        with patch('apps.core.services.async_pdf_service.AsyncPDFGenerationService.get_task_status'):
            with patch('apps.core.services.async_api_service.AsyncExternalAPIService.cancel_task'):
                for i in range(30):
                    self.client.post(
                        f'/admin/async/cancel-task/{task_id}/',
                        HTTP_X_CSRFTOKEN=csrf_token
                    )

                response = self.client.post(
                    f'/admin/async/cancel-task/{task_id}/',
                    HTTP_X_CSRFTOKEN=csrf_token
                )

                self.assertEqual(response.status_code, 429)

    def test_cancel_task_requires_authentication(self):
        """
        Test that task cancellation requires user authentication.
        """
        client = Client(enforce_csrf_checks=True)
        task_id = 'test-task-999'

        response = client.post(f'/admin/async/cancel-task/{task_id}/')

        self.assertIn(response.status_code, [302, 403])


@pytest.mark.security
class RecommendationInteractionViewCSRFTest(TestCase):
    """
    Test CSRF protection on RecommendationInteractionView.

    Endpoint: apps/core/views/recommendation_views.py:99
    Operations: Record clicks, dismissals, feedback
    """

    def setUp(self):
        self.client = Client(enforce_csrf_checks=True)

        self.user = People.objects.create_user(
            loginid='rec_user',
            email='recommendations@example.com',
            password='rec123',
            firstname='Rec',
            lastname='User'
        )
        self.user.save()

        self.client.login(username='rec_user', password='rec123')
        cache.clear()

    def tearDown(self):
        cache.clear()

    def test_click_interaction_rejects_without_csrf_token(self):
        """
        Test that recommendation click tracking rejects requests without CSRF token.
        """
        payload = {
            'type': 'click',
            'rec_id': 1,
            'rec_type': 'content'
        }

        response = self.client.post(
            '/recommendations/interact/',
            data=json.dumps(payload),
            content_type='application/json'
        )

        self.assertEqual(response.status_code, 403)
        response_data = response.json()
        self.assertEqual(response_data['code'], 'CSRF_TOKEN_REQUIRED')

    def test_dismiss_interaction_accepts_with_csrf_token(self):
        """
        Test that recommendation dismissal accepts requests with valid CSRF token.
        """
        response = self.client.get('/recommendations/')
        csrf_token = get_token(response.wsgi_request)

        payload = {
            'type': 'dismiss',
            'rec_id': 1,
            'rec_type': 'content'
        }

        with patch('apps.core.models.recommendation.ContentRecommendation.objects.get') as mock_get:
            mock_rec = Mock()
            mock_rec.mark_dismissed = Mock()
            mock_get.return_value = mock_rec

            response = self.client.post(
                '/recommendations/interact/',
                data=json.dumps(payload),
                content_type='application/json',
                HTTP_X_CSRFTOKEN=csrf_token
            )

            self.assertNotEqual(response.status_code, 403)

    def test_feedback_interaction_enforces_rate_limiting(self):
        """
        Test that recommendation feedback enforces rate limiting (100 requests per 5 min).
        """
        response = self.client.get('/recommendations/')
        csrf_token = get_token(response.wsgi_request)

        payload = {
            'type': 'click',
            'rec_id': 1,
            'rec_type': 'content'
        }

        with patch('apps.core.models.recommendation.ContentRecommendation.objects.get') as mock_get:
            mock_rec = Mock()
            mock_rec.mark_clicked = Mock()
            mock_get.return_value = mock_rec

            for i in range(100):
                self.client.post(
                    '/recommendations/interact/',
                    data=json.dumps(payload),
                    content_type='application/json',
                    HTTP_X_CSRFTOKEN=csrf_token
                )

            response = self.client.post(
                '/recommendations/interact/',
                data=json.dumps(payload),
                content_type='application/json',
                HTTP_X_CSRFTOKEN=csrf_token
            )

            self.assertEqual(response.status_code, 429)
            response_data = response.json()
            self.assertEqual(response_data['code'], 'RATE_LIMIT_EXCEEDED')

    def test_feedback_with_invalid_json_returns_400(self):
        """
        Test that invalid JSON payload returns 400 Bad Request.
        """
        response = self.client.get('/recommendations/')
        csrf_token = get_token(response.wsgi_request)

        response = self.client.post(
            '/recommendations/interact/',
            data='invalid json',
            content_type='application/json',
            HTTP_X_CSRFTOKEN=csrf_token
        )

        self.assertEqual(response.status_code, 400)
        response_data = response.json()
        self.assertIn('error', response_data)


@pytest.mark.security
class CSRFAdminEndpointIntegrationTest(TestCase):
    """
    Integration tests for CSRF protection across all admin endpoints.

    Validates that the complete flow works correctly with proper authentication,
    CSRF validation, and rate limiting.
    """

    def setUp(self):
        self.client = Client(enforce_csrf_checks=True)

        self.staff_user = People.objects.create_user(
            loginid='integration_admin',
            email='integration@example.com',
            password='integration123',
            firstname='Integration',
            lastname='Admin'
        )
        self.staff_user.is_staff = True
        self.staff_user.is_superuser = True
        self.staff_user.save()

        self.client.login(username='integration_admin', password='integration123')
        cache.clear()

    def tearDown(self):
        cache.clear()

    def test_multiple_admin_operations_with_csrf_protection(self):
        """
        Test multiple admin operations in sequence with CSRF protection.

        Validates:
        1. CSRF token retrieved successfully
        2. Multiple operations work with same token
        3. Rate limiting tracks across operations
        """
        response = self.client.get('/admin/tasks/')
        csrf_token = get_token(response.wsgi_request)

        operations = [
            {'operation': 'cancel_task', 'task_id': 'task-1'},
            {'operation': 'clear_cache'},
            {'operation': 'purge_queue', 'queue_name': 'default'},
        ]

        with patch('celery.current_app.control.revoke'):
            with patch('celery.current_app.control.purge'):
                with patch('django.core.cache.cache.clear'):
                    for operation_data in operations:
                        response = self.client.post(
                            '/admin/tasks/api/',
                            data=json.dumps(operation_data),
                            content_type='application/json',
                            HTTP_X_CSRFTOKEN=csrf_token
                        )

                        self.assertNotEqual(
                            response.status_code, 403,
                            f"Operation {operation_data['operation']} failed CSRF validation"
                        )

    def test_csrf_protection_across_different_admin_endpoints(self):
        """
        Test CSRF protection works consistently across different admin endpoints.
        """
        response = self.client.get('/admin/tasks/')
        csrf_token = get_token(response.wsgi_request)

        task_management_payload = {
            'operation': 'cancel_task',
            'task_id': 'test-task-abc'
        }

        with patch('celery.current_app.control.revoke'):
            response1 = self.client.post(
                '/admin/tasks/api/',
                data=json.dumps(task_management_payload),
                content_type='application/json',
                HTTP_X_CSRFTOKEN=csrf_token
            )

            self.assertNotEqual(response1.status_code, 403)

        task_id = 'test-task-xyz'

        with patch('apps.core.services.async_pdf_service.AsyncPDFGenerationService.get_task_status') as mock_status:
            mock_status.return_value = {'status': 'processing'}

            with patch('celery.current_app.control.revoke'):
                response2 = self.client.post(
                    f'/admin/async/cancel-task/{task_id}/',
                    HTTP_X_CSRFTOKEN=csrf_token
                )

                self.assertNotEqual(response2.status_code, 403)

        rec_payload = {
            'type': 'click',
            'rec_id': 1,
            'rec_type': 'content'
        }

        with patch('apps.core.models.recommendation.ContentRecommendation.objects.get') as mock_get:
            mock_rec = Mock()
            mock_rec.mark_clicked = Mock()
            mock_get.return_value = mock_rec

            response3 = self.client.post(
                '/recommendations/interact/',
                data=json.dumps(rec_payload),
                content_type='application/json',
                HTTP_X_CSRFTOKEN=csrf_token
            )

            self.assertNotEqual(response3.status_code, 403)

    def test_non_staff_user_cannot_access_task_management(self):
        """
        Test that non-staff users cannot access TaskManagementAPIView.
        """
        regular_user = People.objects.create_user(
            loginid='regular_test_user',
            email='regular@example.com',
            password='regular123',
            firstname='Regular',
            lastname='User'
        )
        regular_user.is_staff = False
        regular_user.save()

        client = Client(enforce_csrf_checks=True)
        client.login(username='regular_test_user', password='regular123')

        response = client.get('/admin/tasks/')
        csrf_token = get_token(response.wsgi_request)

        payload = {'operation': 'clear_cache'}

        response = client.post(
            '/admin/tasks/api/',
            data=json.dumps(payload),
            content_type='application/json',
            HTTP_X_CSRFTOKEN=csrf_token
        )

        self.assertIn(response.status_code, [403, 302])


if __name__ == '__main__':
    pytest.main([__file__, '-v'])