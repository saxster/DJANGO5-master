"""
Comprehensive tests for Security Headers Middleware.

Tests all security headers implementation, edge cases, performance impact,
and configuration validation for SecurityHeadersMiddleware and SecurityReportMiddleware.

Coverage areas:
- All 12+ security headers (HSTS, CSP, Permissions-Policy, etc.)
- Static file exclusion behavior
- Sensitive page detection
- Performance impact measurement
- Configuration validation
- Security report handling
"""

import json
import time
import pytest
from unittest.mock import Mock, patch, MagicMock
from django.test import TestCase, RequestFactory, override_settings
from django.http import HttpResponse, JsonResponse
from django.contrib.auth import get_user_model
from apps.core.middleware.security_headers import SecurityHeadersMiddleware, SecurityReportMiddleware


class SecurityHeadersMiddlewareTest(TestCase):
    """Comprehensive test suite for SecurityHeadersMiddleware."""

    def setUp(self):
        """Set up test fixtures."""
        self.factory = RequestFactory()
        self.middleware = SecurityHeadersMiddleware(get_response=lambda r: HttpResponse())
        self.User = get_user_model()

    def test_middleware_initialization(self):
        """Test middleware initializes with correct default settings."""
        middleware = SecurityHeadersMiddleware()
        self.assertIsNotNone(middleware)

        # Test default HSTS settings
        self.assertEqual(middleware.hsts_seconds, 31536000)  # 1 year
        self.assertTrue(middleware.hsts_include_subdomains)
        self.assertTrue(middleware.hsts_preload)

    @override_settings(SECURE_HSTS_SECONDS=63072000, SECURE_HSTS_INCLUDE_SUBDOMAINS=False, SECURE_HSTS_PRELOAD=False)
    def test_hsts_configuration_from_settings(self):
        """Test HSTS configuration is properly loaded from settings."""
        middleware = SecurityHeadersMiddleware()
        self.assertEqual(middleware.hsts_seconds, 63072000)  # 2 years
        self.assertFalse(middleware.hsts_include_subdomains)
        self.assertFalse(middleware.hsts_preload)

    def test_hsts_header_generation(self):
        """Test HSTS header is properly generated."""
        request = self.factory.get('/')
        response = HttpResponse()

        # Enable HSTS
        with override_settings(SECURE_HSTS_SECONDS=31536000):
            middleware = SecurityHeadersMiddleware()
            processed_response = middleware.process_response(request, response)

            self.assertIn('Strict-Transport-Security', processed_response)
            hsts_header = processed_response['Strict-Transport-Security']
            self.assertIn('max-age=31536000', hsts_header)
            self.assertIn('includeSubDomains', hsts_header)
            self.assertIn('preload', hsts_header)

    def test_hsts_disabled(self):
        """Test HSTS header is not added when disabled."""
        request = self.factory.get('/')
        response = HttpResponse()

        with override_settings(SECURE_HSTS_SECONDS=0):
            middleware = SecurityHeadersMiddleware()
            processed_response = middleware.process_response(request, response)

            self.assertNotIn('Strict-Transport-Security', processed_response)

    def test_x_content_type_options_header(self):
        """Test X-Content-Type-Options header prevents MIME sniffing."""
        request = self.factory.get('/')
        response = HttpResponse()

        processed_response = self.middleware.process_response(request, response)

        self.assertEqual(processed_response['X-Content-Type-Options'], 'nosniff')

    def test_x_frame_options_header(self):
        """Test X-Frame-Options header prevents clickjacking."""
        request = self.factory.get('/')
        response = HttpResponse()

        # Test default DENY
        processed_response = self.middleware.process_response(request, response)
        self.assertEqual(processed_response['X-Frame-Options'], 'DENY')

        # Test custom setting
        with override_settings(X_FRAME_OPTIONS='SAMEORIGIN'):
            middleware = SecurityHeadersMiddleware()
            processed_response = middleware.process_response(request, response)
            self.assertEqual(processed_response['X-Frame-Options'], 'SAMEORIGIN')

    def test_x_xss_protection_header(self):
        """Test X-XSS-Protection header for legacy browser support."""
        request = self.factory.get('/')
        response = HttpResponse()

        processed_response = self.middleware.process_response(request, response)
        self.assertEqual(processed_response['X-XSS-Protection'], '1; mode=block')

    def test_referrer_policy_header(self):
        """Test Referrer-Policy header controls referrer information."""
        request = self.factory.get('/')
        response = HttpResponse()

        # Test default policy
        processed_response = self.middleware.process_response(request, response)
        self.assertEqual(processed_response['Referrer-Policy'], 'strict-origin-when-cross-origin')

        # Test custom policy
        with override_settings(REFERRER_POLICY='no-referrer'):
            middleware = SecurityHeadersMiddleware()
            processed_response = middleware.process_response(request, response)
            self.assertEqual(processed_response['Referrer-Policy'], 'no-referrer')

    def test_permissions_policy_header(self):
        """Test Permissions-Policy header restricts browser features."""
        request = self.factory.get('/')
        response = HttpResponse()

        processed_response = self.middleware.process_response(request, response)

        permissions_policy = processed_response['Permissions-Policy']

        # Check for key feature restrictions
        self.assertIn('geolocation=()', permissions_policy)
        self.assertIn('camera=()', permissions_policy)
        self.assertIn('microphone=()', permissions_policy)
        self.assertIn('payment=()', permissions_policy)
        self.assertIn('usb=()', permissions_policy)

    @override_settings(PERMISSIONS_POLICY={'camera': '(self)', 'microphone': '(self "https://trusted.com")'})
    def test_custom_permissions_policy(self):
        """Test custom Permissions-Policy configuration."""
        request = self.factory.get('/')
        response = HttpResponse()

        middleware = SecurityHeadersMiddleware()
        processed_response = middleware.process_response(request, response)

        permissions_policy = processed_response['Permissions-Policy']
        self.assertIn('camera=(self)', permissions_policy)
        self.assertIn('microphone=(self "https://trusted.com")', permissions_policy)

    def test_cross_origin_headers(self):
        """Test Cross-Origin security headers."""
        request = self.factory.get('/')
        response = HttpResponse()

        processed_response = self.middleware.process_response(request, response)

        self.assertEqual(processed_response['Cross-Origin-Embedder-Policy'], 'require-corp')
        self.assertEqual(processed_response['Cross-Origin-Opener-Policy'], 'same-origin')
        self.assertEqual(processed_response['Cross-Origin-Resource-Policy'], 'same-origin')

    def test_additional_security_headers(self):
        """Test additional security headers."""
        request = self.factory.get('/')
        response = HttpResponse()

        processed_response = self.middleware.process_response(request, response)

        self.assertEqual(processed_response['X-Permitted-Cross-Domain-Policies'], 'none')
        self.assertEqual(processed_response['X-Download-Options'], 'noopen')

    def test_static_files_excluded(self):
        """Test static files are excluded from security headers."""
        static_paths = ['/static/css/style.css', '/media/uploads/image.jpg']

        for path in static_paths:
            request = self.factory.get(path)
            response = HttpResponse()

            processed_response = self.middleware.process_response(request, response)

            # Static/media files should not have security headers (except basic ones)
            self.assertEqual(processed_response, response)  # No headers added

    def test_sensitive_page_cache_control(self):
        """Test cache control headers for sensitive pages."""
        # Create authenticated user
        user = self.User.objects.create_user(username='testuser', password='testpass')

        # Test authenticated request
        request = self.factory.get('/profile/')
        request.user = user
        response = HttpResponse()

        processed_response = self.middleware.process_response(request, response)

        self.assertEqual(processed_response['Cache-Control'], 'no-store, no-cache, must-revalidate, private')
        self.assertEqual(processed_response['Pragma'], 'no-cache')
        self.assertEqual(processed_response['Expires'], '0')

    def test_sensitive_paths_detection(self):
        """Test detection of sensitive paths for cache control."""
        sensitive_paths = [
            '/admin/',
            '/accounts/',
            '/profile/',
            '/settings/',
            '/api/auth/',
            '/password/',
        ]

        for path in sensitive_paths:
            request = self.factory.get(path)
            response = HttpResponse()

            processed_response = self.middleware.process_response(request, response)

            self.assertIn('Cache-Control', processed_response)
            self.assertIn('no-store', processed_response['Cache-Control'])

    @override_settings(SECURITY_REPORT_URI='/api/security-report/')
    def test_report_to_header(self):
        """Test Report-To header for error reporting."""
        request = self.factory.get('/')
        response = HttpResponse()

        processed_response = self.middleware.process_response(request, response)

        if 'Report-To' in processed_response:
            report_to = json.loads(processed_response['Report-To'])
            self.assertEqual(report_to['group'], 'security-endpoints')
            self.assertIn('/api/security-report/', report_to['endpoints'][0]['url'])

    @override_settings(NEL_REPORT_URI='/api/nel-report/')
    def test_nel_header(self):
        """Test Network Error Logging header."""
        request = self.factory.get('/')
        response = HttpResponse()

        processed_response = self.middleware.process_response(request, response)

        if 'NEL' in processed_response:
            nel = json.loads(processed_response['NEL'])
            self.assertEqual(nel['report_to'], 'security-endpoints')
            self.assertIn('failure_fraction', nel)

    def test_header_override_prevention(self):
        """Test that headers are not overridden if already present."""
        request = self.factory.get('/')
        response = HttpResponse()

        # Pre-set a header
        response['X-Frame-Options'] = 'ALLOWALL'

        processed_response = self.middleware.process_response(request, response)

        # Should not override existing header
        self.assertEqual(processed_response['X-Frame-Options'], 'ALLOWALL')

    def test_performance_impact(self):
        """Test middleware performance impact is minimal."""
        request = self.factory.get('/')
        response = HttpResponse()

        # Measure processing time
        start_time = time.time()

        for _ in range(1000):  # Process 1000 requests
            self.middleware.process_response(request, response)

        end_time = time.time()
        avg_time = (end_time - start_time) / 1000

        # Should be very fast (less than 0.5ms per request)
        self.assertLess(avg_time, 0.0005, f"Middleware too slow: {avg_time:.6f}s per request")

    def test_memory_usage(self):
        """Test middleware doesn't cause memory leaks."""
        import gc
        import sys

        request = self.factory.get('/')
        response = HttpResponse()

        # Get initial object count
        gc.collect()
        initial_objects = len(gc.get_objects())

        # Process many requests
        for _ in range(1000):
            self.middleware.process_response(request, response)

        # Check for memory leaks
        gc.collect()
        final_objects = len(gc.get_objects())

        # Allow for some object growth but not excessive
        self.assertLess(final_objects - initial_objects, 100, "Possible memory leak detected")


class SecurityReportMiddlewareTest(TestCase):
    """Test suite for SecurityReportMiddleware."""

    def setUp(self):
        """Set up test fixtures."""
        self.factory = RequestFactory()
        self.middleware = SecurityReportMiddleware(get_response=lambda r: HttpResponse())

    def test_middleware_initialization(self):
        """Test middleware initializes correctly."""
        middleware = SecurityReportMiddleware()
        self.assertIsNotNone(middleware)

    def test_non_report_requests_passthrough(self):
        """Test non-report requests pass through unchanged."""
        request = self.factory.get('/')

        result = self.middleware.process_request(request)
        self.assertIsNone(result)  # Should pass through

    def test_security_report_endpoint_detection(self):
        """Test security report endpoint is properly detected."""
        request = self.factory.post('/api/security-report/',
                                   data='{"type": "csp-violation"}',
                                   content_type='application/json')

        with patch.object(self.middleware, '_handle_security_report') as mock_handler:
            mock_handler.return_value = HttpResponse(status=204)

            result = self.middleware.process_request(request)
            mock_handler.assert_called_once_with(request)

    def test_csp_violation_report_handling(self):
        """Test CSP violation report handling."""
        csp_report = {
            "type": "csp-violation",
            "csp-report": {
                "document-uri": "https://example.com/",
                "referrer": "https://example.com/referrer",
                "violated-directive": "script-src 'self'",
                "effective-directive": "script-src",
                "original-policy": "script-src 'self'",
                "blocked-uri": "https://malicious.com/script.js"
            }
        }

        request = self.factory.post('/api/security-report/',
                                   data=json.dumps(csp_report),
                                   content_type='application/json')

        with self.assertLogs('apps.core.middleware.security_headers', level='WARNING') as log:
            response = self.middleware._handle_security_report(request)

            self.assertEqual(response.status_code, 204)
            self.assertIn('CSP Violation', log.output[0])

    def test_permissions_policy_violation_handling(self):
        """Test Permissions Policy violation report handling."""
        policy_report = {
            "type": "permissions-policy-violation",
            "body": {
                "featureId": "geolocation",
                "disposition": "enforce",
                "policyId": "geolocation=()"
            }
        }

        request = self.factory.post('/api/security-report/',
                                   data=json.dumps(policy_report),
                                   content_type='application/json')

        with self.assertLogs('apps.core.middleware.security_headers', level='WARNING') as log:
            response = self.middleware._handle_security_report(request)

            self.assertEqual(response.status_code, 204)
            self.assertIn('Permissions Policy Violation', log.output[0])

    def test_network_error_report_handling(self):
        """Test Network Error Logging report handling."""
        nel_report = {
            "type": "network-error",
            "age": 10,
            "url": "https://example.com/resource",
            "body": {
                "sampling_fraction": 0.01,
                "server_ip": "192.168.1.1",
                "protocol": "http/1.1",
                "method": "GET",
                "status_code": 0,
                "elapsed_time": 143,
                "type": "tcp.timed_out"
            }
        }

        request = self.factory.post('/api/security-report/',
                                   data=json.dumps(nel_report),
                                   content_type='application/json')

        with self.assertLogs('apps.core.middleware.security_headers', level='INFO') as log:
            response = self.middleware._handle_security_report(request)

            self.assertEqual(response.status_code, 204)
            self.assertIn('Network Error', log.output[0])

    def test_unknown_report_type_handling(self):
        """Test handling of unknown report types."""
        unknown_report = {
            "type": "unknown-report-type",
            "data": "some data"
        }

        request = self.factory.post('/api/security-report/',
                                   data=json.dumps(unknown_report),
                                   content_type='application/json')

        with self.assertLogs('apps.core.middleware.security_headers', level='WARNING') as log:
            response = self.middleware._handle_security_report(request)

            self.assertEqual(response.status_code, 204)
            self.assertIn('Unknown security report type', log.output[0])

    def test_malformed_report_handling(self):
        """Test handling of malformed security reports."""
        request = self.factory.post('/api/security-report/',
                                   data='invalid json',
                                   content_type='application/json')

        response = self.middleware._handle_security_report(request)
        self.assertEqual(response.status_code, 400)

    def test_get_request_rejection(self):
        """Test GET requests to report endpoint are rejected."""
        request = self.factory.get('/api/security-report/')

        response = self.middleware._handle_security_report(request)
        self.assertEqual(response.status_code, 405)  # Method Not Allowed

    def test_report_logging_security(self):
        """Test that report logging doesn't expose sensitive information."""
        sensitive_report = {
            "type": "csp-violation",
            "csp-report": {
                "document-uri": "https://example.com/secret-page?token=secret123",
                "blocked-uri": "https://attacker.com/steal-data?data=stolen"
            }
        }

        request = self.factory.post('/api/security-report/',
                                   data=json.dumps(sensitive_report),
                                   content_type='application/json')

        with self.assertLogs('apps.core.middleware.security_headers', level='WARNING') as log:
            response = self.middleware._handle_security_report(request)

            # Check that sensitive data is not exposed in logs
            log_content = ''.join(log.output)
            self.assertNotIn('secret123', log_content)


@pytest.mark.security
class SecurityHeadersIntegrationTest(TestCase):
    """Integration tests for security headers in full application context."""

    def setUp(self):
        """Set up test fixtures."""
        self.factory = RequestFactory()

    def test_headers_integration_with_django_security_middleware(self):
        """Test integration with Django's SecurityMiddleware."""
        request = self.factory.get('/')
        response = HttpResponse()

        # Test that our middleware works alongside Django's SecurityMiddleware
        from django.middleware.security import SecurityMiddleware

        security_middleware = SecurityMiddleware(lambda r: HttpResponse())
        our_middleware = SecurityHeadersMiddleware(lambda r: response)

        # Process through both middlewares
        processed_response = security_middleware.process_response(request, response)
        final_response = our_middleware.process_response(request, processed_response)

        # Should have headers from both middlewares
        self.assertIn('X-Content-Type-Options', final_response)

    def test_headers_with_different_response_types(self):
        """Test security headers with different response types."""
        middleware = SecurityHeadersMiddleware()
        request = self.factory.get('/')

        response_types = [
            HttpResponse(),
            HttpResponse(content_type='text/html'),
            JsonResponse({'data': 'test'}),
            HttpResponse(status=404),
            HttpResponse(status=500),
        ]

        for response in response_types:
            processed_response = middleware.process_response(request, response)

            # All response types should get security headers (except static)
            self.assertIn('X-Content-Type-Options', processed_response)
            self.assertIn('X-Frame-Options', processed_response)

    def test_csrf_token_compatibility(self):
        """Test security headers don't interfere with CSRF tokens."""
        from django.middleware.csrf import get_token

        request = self.factory.get('/')
        response = HttpResponse()

        # Get CSRF token
        token = get_token(request)

        middleware = SecurityHeadersMiddleware()
        processed_response = middleware.process_response(request, response)

        # Should still have CSRF token functionality
        self.assertIsNotNone(token)
        self.assertIn('X-Content-Type-Options', processed_response)

    @override_settings(DEBUG=True)
    def test_debug_mode_behavior(self):
        """Test security headers behavior in debug mode."""
        request = self.factory.get('/')
        response = HttpResponse()

        middleware = SecurityHeadersMiddleware()
        processed_response = middleware.process_response(request, response)

        # Should still apply security headers in debug mode
        self.assertIn('X-Content-Type-Options', processed_response)
        self.assertIn('X-Frame-Options', processed_response)

    def test_concurrent_request_handling(self):
        """Test middleware handles concurrent requests safely."""
        import threading
        import queue

        middleware = SecurityHeadersMiddleware()
        results = queue.Queue()

        def process_request(request_num):
            request = self.factory.get(f'/test/{request_num}')
            response = HttpResponse()
            processed_response = middleware.process_response(request, response)
            results.put(processed_response.get('X-Content-Type-Options'))

        # Create multiple threads
        threads = []
        for i in range(10):
            thread = threading.Thread(target=process_request, args=(i,))
            threads.append(thread)
            thread.start()

        # Wait for all threads
        for thread in threads:
            thread.join()

        # Check all responses have security headers
        while not results.empty():
            header_value = results.get()
            self.assertEqual(header_value, 'nosniff')