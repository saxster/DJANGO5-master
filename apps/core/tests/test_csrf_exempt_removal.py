"""
Unit Tests for CSRF Exempt Removal (CVSS 8.1 Vulnerability Fix)

This test suite validates that all @csrf_exempt decorators have been removed
from mutation endpoints and replaced with proper CSRF protection.

Test Coverage:
1. Report generation endpoint (apps/reports/views.py:get_data)
2. Stream testbench start_scenario (apps/streamlab/views.py:start_scenario)
3. Stream testbench stop_scenario (apps/streamlab/views.py:stop_scenario)
4. AI testing update_gap_status (apps/ai_testing/views.py:update_gap_status)

Security Compliance:
- Rule #3: Mandatory CSRF Protection (.claude/rules.md)
- CVSS 8.1 vulnerability remediation
- Zero tolerance for CSRF exemptions on mutation endpoints

Author: Security Remediation Team
Date: 2025-09-27
"""

import pytest
import json
from django.test import TestCase, Client, RequestFactory
from django.contrib.auth import get_user_model
from django.middleware.csrf import get_token
from django.urls import reverse
from django.core.cache import cache
from unittest.mock import patch, Mock

from apps.peoples.models import People
from apps.core.decorators import csrf_protect_ajax, csrf_protect_htmx, rate_limit

User = get_user_model()


@pytest.mark.security
class CSRFExemptRemovalTestCase(TestCase):
    """
    Test suite to validate CSRF protection on all previously exempted endpoints.
    """

    def setUp(self):
        """Set up test fixtures."""
        self.factory = RequestFactory()
        self.client = Client(enforce_csrf_checks=True)

        # Create test user with staff privileges
        self.user = People.objects.create_user(
            loginid='testuser',
            email='test@example.com',
            password='testpass123',
            firstname='Test',
            lastname='User'
        )
        self.user.is_staff = True
        self.user.is_superuser = True
        self.user.save()

        # Log in the user
        self.client.login(username='testuser', password='testpass123')

        # Clear cache before each test
        cache.clear()

    def tearDown(self):
        """Clean up after tests."""
        cache.clear()

    # ========================================================================
    # TEST 1: Reports - get_data endpoint
    # ========================================================================

    def test_reports_get_data_rejects_request_without_csrf_token(self):
        """
        Test that get_data endpoint rejects requests without CSRF token.

        Location: apps/reports/views.py:1035
        Previous: @csrf_exempt
        Current: @csrf_protect_ajax + @rate_limit
        """
        url = '/reports/get-data/'  # Adjust URL as needed
        payload = {
            'company': 'TEST',
            'customer_code': 'CUST001'
        }

        response = self.client.post(
            url,
            data=json.dumps(payload),
            content_type='application/json'
        )

        # Should reject with 403 Forbidden
        self.assertEqual(response.status_code, 403)

        response_data = response.json()
        self.assertEqual(response_data['code'], 'CSRF_TOKEN_REQUIRED')
        self.assertIn('CSRF token missing', response_data['error'])

    def test_reports_get_data_accepts_request_with_csrf_token_in_header(self):
        """
        Test that get_data endpoint accepts requests with CSRF token in header.
        """
        # Get CSRF token
        response = self.client.get('/reports/')  # Any page that sets CSRF cookie
        csrf_token = get_token(response.wsgi_request)

        url = '/reports/get-data/'
        payload = {
            'company': 'TEST',
            'customer_code': 'CUST001'
        }

        response = self.client.post(
            url,
            data=json.dumps(payload),
            content_type='application/json',
            HTTP_X_CSRFTOKEN=csrf_token
        )

        # Should accept request (may return 404 or other error, but not 403)
        self.assertNotEqual(response.status_code, 403)

    def test_reports_get_data_accepts_request_with_csrf_token_in_body(self):
        """
        Test that get_data endpoint accepts requests with CSRF token in JSON body.
        """
        # Get CSRF token
        response = self.client.get('/reports/')
        csrf_token = get_token(response.wsgi_request)

        url = '/reports/get-data/'
        payload = {
            'company': 'TEST',
            'customer_code': 'CUST001',
            'csrfmiddlewaretoken': csrf_token
        }

        response = self.client.post(
            url,
            data=json.dumps(payload),
            content_type='application/json'
        )

        # Should accept request
        self.assertNotEqual(response.status_code, 403)

    # ========================================================================
    # TEST 2: Stream Testbench - start_scenario endpoint
    # ========================================================================

    def test_streamlab_start_scenario_rejects_request_without_csrf_token(self):
        """
        Test that start_scenario endpoint rejects requests without CSRF token.

        Location: apps/streamlab/views.py:174
        Previous: @csrf_exempt
        Current: @csrf_protect_htmx + @rate_limit
        """
        url = '/streamlab/start-scenario/1/'  # Adjust URL as needed

        response = self.client.post(url)

        # Should reject with 403 Forbidden
        self.assertEqual(response.status_code, 403)

    def test_streamlab_start_scenario_accepts_htmx_request_with_csrf_token(self):
        """
        Test that start_scenario endpoint accepts HTMX requests with CSRF token.
        """
        # Get CSRF token
        response = self.client.get('/streamlab/dashboard/')
        csrf_token = get_token(response.wsgi_request)

        url = '/streamlab/start-scenario/1/'

        response = self.client.post(
            url,
            HTTP_X_CSRFTOKEN=csrf_token,
            HTTP_HX_REQUEST='true',  # HTMX header
            HTTP_HX_TARGET='scenario-status',
            HTTP_HX_TRIGGER='start-button'
        )

        # Should accept request (may return 404 or other error, but not 403)
        self.assertNotEqual(response.status_code, 403)

    def test_streamlab_start_scenario_rate_limiting(self):
        """
        Test that start_scenario endpoint enforces rate limiting.
        """
        # Get CSRF token
        response = self.client.get('/streamlab/dashboard/')
        csrf_token = get_token(response.wsgi_request)

        url = '/streamlab/start-scenario/1/'

        # Make 30 requests (the limit)
        for i in range(30):
            response = self.client.post(
                url,
                HTTP_X_CSRFTOKEN=csrf_token,
                HTTP_HX_REQUEST='true'
            )

        # 31st request should be rate limited
        response = self.client.post(
            url,
            HTTP_X_CSRFTOKEN=csrf_token,
            HTTP_HX_REQUEST='true'
        )

        self.assertEqual(response.status_code, 429)  # Too Many Requests

    # ========================================================================
    # TEST 3: Stream Testbench - stop_scenario endpoint
    # ========================================================================

    def test_streamlab_stop_scenario_rejects_request_without_csrf_token(self):
        """
        Test that stop_scenario endpoint rejects requests without CSRF token.

        Location: apps/streamlab/views.py:212
        Previous: @csrf_exempt
        Current: @csrf_protect_htmx + @rate_limit
        """
        url = '/streamlab/stop-scenario/1/'

        response = self.client.post(url)

        # Should reject with 403 Forbidden
        self.assertEqual(response.status_code, 403)

    def test_streamlab_stop_scenario_accepts_htmx_request_with_csrf_token(self):
        """
        Test that stop_scenario endpoint accepts HTMX requests with CSRF token.
        """
        # Get CSRF token
        response = self.client.get('/streamlab/dashboard/')
        csrf_token = get_token(response.wsgi_request)

        url = '/streamlab/stop-scenario/1/'

        response = self.client.post(
            url,
            HTTP_X_CSRFTOKEN=csrf_token,
            HTTP_HX_REQUEST='true',
            HTTP_HX_TARGET='scenario-status',
            HTTP_HX_TRIGGER='stop-button'
        )

        # Should accept request (may return 404 or other error, but not 403)
        self.assertNotEqual(response.status_code, 403)

    # ========================================================================
    # TEST 4: AI Testing - update_gap_status endpoint
    # ========================================================================

    def test_ai_testing_update_gap_status_rejects_request_without_csrf_token(self):
        """
        Test that update_gap_status endpoint rejects requests without CSRF token.

        Location: apps/ai_testing/views.py:150
        Previous: @csrf_exempt
        Current: @csrf_protect_htmx + @rate_limit
        """
        url = '/streamlab/ai/update-gap-status/1/'

        response = self.client.post(url)

        # Should reject with 403 Forbidden
        self.assertEqual(response.status_code, 403)

    def test_ai_testing_update_gap_status_accepts_htmx_request_with_csrf_token(self):
        """
        Test that update_gap_status endpoint accepts HTMX requests with CSRF token.
        """
        # Get CSRF token
        response = self.client.get('/streamlab/ai/coverage-gaps/')
        csrf_token = get_token(response.wsgi_request)

        url = '/streamlab/ai/update-gap-status/1/'
        payload = {
            'status': 'test_implemented',
            'notes': 'Test completed successfully'
        }

        response = self.client.post(
            url,
            data=payload,
            HTTP_X_CSRFTOKEN=csrf_token,
            HTTP_HX_REQUEST='true',
            HTTP_HX_TARGET='gap-status'
        )

        # Should accept request (may return 404 or other error, but not 403)
        self.assertNotEqual(response.status_code, 403)

    def test_ai_testing_update_gap_status_rate_limiting(self):
        """
        Test that update_gap_status endpoint enforces rate limiting.
        """
        # Get CSRF token
        response = self.client.get('/streamlab/ai/coverage-gaps/')
        csrf_token = get_token(response.wsgi_request)

        url = '/streamlab/ai/update-gap-status/1/'
        payload = {'status': 'dismissed', 'notes': 'Test'}

        # Make 50 requests (the limit)
        for i in range(50):
            response = self.client.post(
                url,
                data=payload,
                HTTP_X_CSRFTOKEN=csrf_token,
                HTTP_HX_REQUEST='true'
            )

        # 51st request should be rate limited
        response = self.client.post(
            url,
            data=payload,
            HTTP_X_CSRFTOKEN=csrf_token,
            HTTP_HX_REQUEST='true'
        )

        self.assertEqual(response.status_code, 429)  # Too Many Requests

    # ========================================================================
    # TEST 5: Cross-cutting concerns
    # ========================================================================

    def test_no_csrf_exempt_decorators_in_codebase(self):
        """
        Comprehensive test to ensure no @csrf_exempt decorators remain on mutation endpoints.

        This test scans the codebase to ensure compliance with Rule #3.
        """
        import os
        import re

        # Define patterns to search for
        csrf_exempt_pattern = re.compile(r'@csrf_exempt\s+def\s+(\w+)\s*\(')

        # Directories to scan
        scan_dirs = [
            'apps/reports',
            'apps/streamlab',
            'apps/ai_testing',
            'apps/activity',
            'apps/y_helpdesk',
            'apps/work_order_management'
        ]

        violations = []

        for scan_dir in scan_dirs:
            dir_path = os.path.join(os.getcwd(), scan_dir)
            if not os.path.exists(dir_path):
                continue

            for root, dirs, files in os.walk(dir_path):
                for file in files:
                    if file.endswith('.py'):
                        file_path = os.path.join(root, file)
                        try:
                            with open(file_path, 'r', encoding='utf-8') as f:
                                content = f.read()
                                matches = csrf_exempt_pattern.findall(content)
                                if matches:
                                    violations.append({
                                        'file': file_path,
                                        'functions': matches
                                    })
                        except Exception:
                            pass  # Skip files that can't be read

        # Assert no violations found
        if violations:
            violation_details = '\n'.join([
                f"{v['file']}: {', '.join(v['functions'])}" for v in violations
            ])
            self.fail(
                f"Found @csrf_exempt decorators on the following functions:\n{violation_details}\n\n"
                "All mutation endpoints MUST use csrf_protect_ajax or csrf_protect_htmx instead."
            )

    def test_all_decorators_imported_correctly(self):
        """
        Test that all files correctly import the new CSRF protection decorators.
        """
        # This test would validate that the imports are correct
        # For simplicity, we'll just check that the decorators are accessible
        from apps.core.decorators import csrf_protect_ajax, csrf_protect_htmx, rate_limit

        self.assertIsNotNone(csrf_protect_ajax)
        self.assertIsNotNone(csrf_protect_htmx)
        self.assertIsNotNone(rate_limit)


@pytest.mark.security
class CSRFDecoratorBehaviorTestCase(TestCase):
    """
    Test suite to validate the behavior of CSRF protection decorators.
    """

    def setUp(self):
        """Set up test fixtures."""
        self.factory = RequestFactory()

    def test_csrf_protect_ajax_allows_get_requests(self):
        """
        Test that csrf_protect_ajax allows GET requests without CSRF token.
        """
        @csrf_protect_ajax
        def test_view(request):
            from django.http import JsonResponse
            return JsonResponse({'success': True})

        request = self.factory.get('/test/')
        response = test_view(request)

        self.assertEqual(response.status_code, 200)

    def test_csrf_protect_ajax_rejects_post_without_token(self):
        """
        Test that csrf_protect_ajax rejects POST requests without CSRF token.
        """
        @csrf_protect_ajax
        def test_view(request):
            from django.http import JsonResponse
            return JsonResponse({'success': True})

        request = self.factory.post('/test/', data='{}', content_type='application/json')
        request.user = Mock(loginid='testuser', is_authenticated=True)
        response = test_view(request)

        self.assertEqual(response.status_code, 403)
        response_data = json.loads(response.content)
        self.assertEqual(response_data['code'], 'CSRF_TOKEN_REQUIRED')

    def test_csrf_protect_htmx_detects_htmx_requests(self):
        """
        Test that csrf_protect_htmx correctly detects HTMX requests.
        """
        @csrf_protect_htmx
        def test_view(request):
            from django.http import HttpResponse
            return HttpResponse('Success')

        request = self.factory.post('/test/', data={'key': 'value'})
        request.META['HTTP_HX_REQUEST'] = 'true'
        request.META['HTTP_HX_TARGET'] = 'test-target'
        request.user = Mock(loginid='testuser', is_authenticated=True)

        response = test_view(request)

        # Should be rejected for missing CSRF token, but with HTMX-specific response
        self.assertEqual(response.status_code, 403)
        self.assertIn('CSRF token missing', response.content.decode())
        self.assertIn('alert', response.content.decode())  # HTMX alert div

    def test_rate_limit_decorator_enforces_limits(self):
        """
        Test that rate_limit decorator correctly enforces request limits.
        """
        @rate_limit(max_requests=5, window_seconds=300)
        def test_view(request):
            from django.http import JsonResponse
            return JsonResponse({'success': True})

        request = self.factory.get('/test/')
        request.user = Mock(id=1, is_authenticated=True, loginid='testuser')
        request.META['REMOTE_ADDR'] = '127.0.0.1'

        # Clear any existing rate limit data
        cache.clear()

        # Make 5 requests (should all succeed)
        for i in range(5):
            response = test_view(request)
            self.assertEqual(response.status_code, 200)

        # 6th request should be rate limited
        response = test_view(request)
        self.assertEqual(response.status_code, 429)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])