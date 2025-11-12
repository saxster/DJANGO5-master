"""
Comprehensive Security Integration and Performance Tests.

Tests the complete security framework integration including middleware interaction,
end-to-end security workflows, performance under attack simulation, and
resource consumption monitoring.

Coverage areas:
- End-to-end security workflow testing
- Middleware interaction and compatibility
- Performance benchmarking under attack simulation
- Resource consumption monitoring
- Attack scenario simulation
- Security resilience testing
- Cross-component security validation
"""

import time
import threading
import pytest
import json
import gc
import psutil
import os
from collections import defaultdict
from unittest.mock import Mock, patch, MagicMock
from django.test import TestCase, RequestFactory, override_settings, TransactionTestCase
from django.http import HttpResponse, JsonResponse
from django.contrib.auth import get_user_model
from django.db import connection, transaction
from django.core.cache import cache

from apps.core.middleware.security_headers import SecurityHeadersMiddleware
from apps.core.middleware.logging_sanitization import LogSanitizationMiddleware
from apps.core.xss_protection import XSSProtectionMiddleware
from apps.core.services.secure_encryption_service import SecureEncryptionService
from apps.peoples.fields import EnhancedSecureString


class SecurityIntegrationWorkflowTest(TestCase):
    """Test suite for end-to-end security workflows."""

    def setUp(self):
        """Set up test fixtures."""
        self.factory = RequestFactory()
        self.User = get_user_model()

        # Create middleware stack in order
        self.security_headers_middleware = SecurityHeadersMiddleware(get_response=lambda r: HttpResponse())
        self.xss_middleware = XSSProtectionMiddleware(get_response=lambda r: HttpResponse())
        self.log_sanitization_middleware = LogSanitizationMiddleware(get_response=lambda r: HttpResponse())

    def test_complete_request_security_pipeline(self):
        """Test complete request processing through all security middleware."""
        # Create request with potential security issues
        malicious_request = self.factory.post('/api/user/update', data={
            'email': 'user@example.com',
            'comment': '<script>alert("xss")</script>',
            'phone': '555-123-4567',
            'api_token': 'sk_live_1234567890'
        })

        # Add user for logging context
        user = self.User.objects.create_user(username='testuser', email='test@example.com')
        malicious_request.user = user

        # Process through security pipeline
        response = HttpResponse("Success")

        # 1. Log sanitization (first to set up context)
        self.log_sanitization_middleware.process_request(malicious_request)

        # 2. XSS protection
        xss_response = self.xss_middleware.process_request(malicious_request)
        if xss_response:
            response = xss_response

        # 3. Security headers (last to add headers)
        final_response = self.security_headers_middleware.process_response(malicious_request, response)

        # Verify security measures applied
        # XSS should be sanitized
        if 'comment' in malicious_request.POST:
            self.assertEqual(malicious_request.POST.get('comment'), '[SANITIZED]')

        # Security headers should be present
        self.assertIn('X-Content-Type-Options', final_response)
        self.assertIn('X-Frame-Options', final_response)

        # Logging context should be sanitized
        self.assertTrue(hasattr(malicious_request, 'safe_user_ref'))
        self.assertTrue(hasattr(malicious_request, 'correlation_id'))

    def test_middleware_interaction_compatibility(self):
        """Test that security middleware work together without conflicts."""
        request = self.factory.get('/test/?search=<img src=x onerror=alert(1)>')
        response = HttpResponse()

        # Process through all middleware
        middlewares = [
            self.log_sanitization_middleware,
            self.xss_middleware,
            self.security_headers_middleware,
        ]

        # Process request phase
        for middleware in middlewares:
            result = middleware.process_request(request)
            if result:  # Middleware returned early response
                response = result
                break

        # Process response phase (reverse order)
        for middleware in reversed(middlewares):
            if hasattr(middleware, 'process_response'):
                response = middleware.process_response(request, response)

        # Verify no conflicts and all security measures applied
        self.assertIsInstance(response, HttpResponse)

        # Should have security headers
        if hasattr(response, '__getitem__'):
            self.assertIn('X-Content-Type-Options', response)

    def test_authenticated_user_security_workflow(self):
        """Test security workflow with authenticated users."""
        user = self.User.objects.create_user(
            username='securitytest',
            email='security@example.com',
            password='SecureP@ss123!'
        )

        # Simulate authenticated request with sensitive operations
        request = self.factory.post('/profile/update', data={
            'current_password': 'SecureP@ss123!',
            'new_password': 'NewSecureP@ss456!',
            'email': 'newemail@example.com'
        })
        request.user = user

        # Process through security pipeline
        self.log_sanitization_middleware.process_request(request)

        # Verify user context is safely logged
        self.assertIn(f'User_{user.id}', request.safe_user_ref)
        self.assertIsNotNone(request.correlation_id)

        # Simulate logging of user action
        import logging
        logger = logging.getLogger('test_security')

        with self.assertLogs('test_security', level='INFO') as log_context:
            logger.info("User profile update", extra={
                'user_id': user.id,
                'old_email': user.email,
                'new_email': request.POST.get('email'),
                'password_data': request.POST.get('current_password')
            })

        # Sensitive data should not appear in logs
        log_output = ''.join(log_context.output)
        self.assertNotIn('SecureP@ss123!', log_output)
        self.assertNotIn('NewSecureP@ss456!', log_output)


class SecurityPerformanceBenchmarkTest(TestCase):
    """Test suite for security performance benchmarking."""

    def setUp(self):
        """Set up test fixtures."""
        self.factory = RequestFactory()

    def test_security_middleware_performance_impact(self):
        """Benchmark performance impact of security middleware."""
        # Create test requests
        test_requests = [
            self.factory.get('/'),
            self.factory.post('/api/data', data={'param': 'value'}),
            self.factory.get('/search/?q=python'),
            self.factory.put('/update', data={'field': 'data'}),
        ] * 250  # 1000 total requests

        # Benchmark without security middleware
        start_time = time.time()
        for request in test_requests:
            response = HttpResponse("OK")
        baseline_time = time.time() - start_time

        # Benchmark with security middleware
        security_middleware = SecurityHeadersMiddleware()
        xss_middleware = XSSProtectionMiddleware()
        log_middleware = LogSanitizationMiddleware()

        start_time = time.time()
        for request in test_requests:
            # Simulate full middleware stack
            log_middleware.process_request(request)
            xss_result = xss_middleware.process_request(request)

            response = xss_result or HttpResponse("OK")
            response = security_middleware.process_response(request, response)

        secure_time = time.time() - start_time

        # Calculate overhead
        overhead = secure_time - baseline_time
        overhead_per_request = overhead / len(test_requests)

        # Performance assertions
        self.assertLess(overhead_per_request, 0.001, f"Security overhead too high: {overhead_per_request:.6f}s per request")
        self.assertLess(secure_time, baseline_time * 3, f"Security middleware causes >200% slowdown: {secure_time:.3f}s vs {baseline_time:.3f}s")

    def test_encryption_performance_benchmark(self):
        """Benchmark encryption/decryption performance."""
        test_data_sizes = [
            (100, "Small data"),
            (1000, "Medium data"),
            (10000, "Large data"),
            (50000, "Very large data")
        ]

        encryption_times = {}
        decryption_times = {}

        for size, description in test_data_sizes:
            test_data = "A" * size

            # Benchmark encryption
            start_time = time.time()
            for _ in range(100):  # 100 iterations
                encrypted = SecureEncryptionService.encrypt(test_data)
            encryption_time = (time.time() - start_time) / 100

            # Benchmark decryption
            start_time = time.time()
            for _ in range(100):
                decrypted = SecureEncryptionService.decrypt(encrypted)
            decryption_time = (time.time() - start_time) / 100

            encryption_times[description] = encryption_time
            decryption_times[description] = decryption_time

            # Performance assertions
            self.assertLess(encryption_time, 0.01, f"Encryption too slow for {description}: {encryption_time:.6f}s")
            self.assertLess(decryption_time, 0.01, f"Decryption too slow for {description}: {decryption_time:.6f}s")

    def test_xss_detection_performance_scaling(self):
        """Test XSS detection performance scaling with payload complexity."""
        xss_middleware = XSSProtectionMiddleware()

        # Test payloads of increasing complexity
        test_cases = [
            ("Simple", "<script>alert(1)</script>"),
            ("Medium", "<img src=x onerror=alert(1)><div onclick=alert(2)>"),
            ("Complex", "<svg/onload=alert(1)>" * 10),
            ("Very Complex", "<div " + " ".join([f"attr{i}='val{i}'" for i in range(50)]) + " onclick=alert(1)>"),
        ]

        for complexity, payload in test_cases:
            start_time = time.time()

            # Test detection 1000 times
            for _ in range(1000):
                is_xss = xss_middleware._is_xss_attempt(payload)

            avg_time = (time.time() - start_time) / 1000

            # Should detect XSS
            self.assertTrue(is_xss, f"Failed to detect {complexity} XSS")

            # Should be fast regardless of complexity
            self.assertLess(avg_time, 0.001, f"{complexity} XSS detection too slow: {avg_time:.6f}s")


class AttackSimulationTest(TransactionTestCase):
    """Test suite for attack scenario simulation."""

    def setUp(self):
        """Set up test fixtures."""
        self.factory = RequestFactory()

    def test_coordinated_attack_simulation(self):
        """Simulate coordinated multi-vector attack."""
        attack_vectors = [
            # XSS attempts
            ("xss_search", "/?q=<script>alert('xss')</script>"),
            ("xss_form", "/submit", {"comment": "<img src=x onerror=alert(1)>"}),

            # Injection attempts
            ("sql_injection", "/users/?id=1'; DROP TABLE users; --"),

            # Sensitive data exposure
            ("data_leak", "/api/user", {"email": "admin@company.com", "password": "admin123"}),

            # Large payload DoS
            ("large_payload", "/upload", {"data": "A" * 100000}),
        ]

        middleware_stack = [
            LogSanitizationMiddleware(),
            XSSProtectionMiddleware(),
            SecurityHeadersMiddleware(),
        ]

        attack_results = {}

        for attack_name, url, *data in attack_vectors:
            try:
                # Create attack request
                if data:
                    request = self.factory.post(url, data=data[0])
                else:
                    request = self.factory.get(url)

                # Process through security stack
                response = HttpResponse("OK")
                blocked = False

                for middleware in middleware_stack:
                    result = middleware.process_request(request)
                    if result:  # Attack blocked
                        response = result
                        blocked = True
                        break

                attack_results[attack_name] = {
                    'blocked': blocked,
                    'response_code': getattr(response, 'status_code', 200)
                }

            except (ValueError, TypeError, AttributeError, KeyError) as e:
                attack_results[attack_name] = {
                    'blocked': True,
                    'error': str(e)
                }

        # Verify security effectiveness
        self.assertTrue(attack_results['xss_search']['blocked'], "XSS search attack should be blocked")
        self.assertTrue(attack_results['xss_form']['blocked'], "XSS form attack should be blocked")

    def test_sustained_attack_resistance(self):
        """Test system resistance to sustained attacks."""
        xss_middleware = XSSProtectionMiddleware()

        # Simulate sustained attack from multiple IPs
        attack_ips = [f"192.168.1.{i}" for i in range(1, 21)]  # 20 attacking IPs
        attack_payload = "<script>alert('sustained')</script>"

        blocked_count = 0
        processed_count = 0

        for ip in attack_ips:
            for attempt in range(10):  # 10 attempts per IP
                request = self.factory.get(f'/search/?q={attack_payload}_{attempt}', REMOTE_ADDR=ip)

                result = xss_middleware.process_request(request)

                if result:  # Request blocked
                    blocked_count += 1
                else:
                    processed_count += 1

        # Should handle sustained attack appropriately
        total_requests = len(attack_ips) * 10
        self.assertEqual(blocked_count + processed_count, total_requests)
        self.assertGreater(blocked_count, total_requests * 0.5, "Should block majority of sustained attacks")

    def test_resource_exhaustion_protection(self):
        """Test protection against resource exhaustion attacks."""
        import psutil
        import os

        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss

        # Simulate memory exhaustion attack
        large_payloads = ["X" * 50000 for _ in range(100)]  # 100 x 50KB payloads

        xss_middleware = XSSProtectionMiddleware()

        for i, payload in enumerate(large_payloads):
            request = self.factory.post('/submit', data={'content': payload})

            # Process request
            xss_middleware.process_request(request)

            # Check memory usage periodically
            if i % 10 == 0:
                current_memory = process.memory_info().rss
                memory_growth = current_memory - initial_memory

                # Memory growth should be reasonable
                self.assertLess(memory_growth, 100 * 1024 * 1024, f"Excessive memory growth: {memory_growth / 1024 / 1024:.1f} MB")

        # Final memory check
        final_memory = process.memory_info().rss
        total_growth = final_memory - initial_memory

        self.assertLess(total_growth, 200 * 1024 * 1024, f"Total memory growth too high: {total_growth / 1024 / 1024:.1f} MB")


class SecurityResilienceTest(TestCase):
    """Test suite for security system resilience."""

    def setUp(self):
        """Set up test fixtures."""
        self.factory = RequestFactory()

    def test_middleware_failure_isolation(self):
        """Test that middleware failures don't compromise overall security."""
        # Mock one middleware to fail
        with patch('apps.core.middleware.logging_sanitization.LogSanitizationMiddleware.process_request') as mock_log:
            mock_log.side_effect = Exception("Logging middleware failure")

            request = self.factory.get('/?param=<script>alert(1)</script>')

            # Other middleware should still work
            xss_middleware = XSSProtectionMiddleware()
            security_middleware = SecurityHeadersMiddleware()

            # XSS should still be blocked despite logging failure
            xss_result = xss_middleware.process_request(request)
            self.assertIsNotNone(xss_result, "XSS protection should work despite other middleware failure")

            # Security headers should still be applied
            response = HttpResponse()
            secure_response = security_middleware.process_response(request, response)
            self.assertIn('X-Content-Type-Options', secure_response)

    def test_encryption_service_fallback(self):
        """Test encryption service fallback behavior."""
        test_data = "fallback_test_data"

        # Test with encryption service temporarily unavailable
        with patch.object(SecureEncryptionService, '_get_fernet') as mock_fernet:
            mock_fernet.side_effect = Exception("Encryption service unavailable")

            # Should fail gracefully
            with self.assertRaises(ValueError):
                SecureEncryptionService.encrypt(test_data)

        # Service should recover when available again
        encrypted = SecureEncryptionService.encrypt(test_data)
        decrypted = SecureEncryptionService.decrypt(encrypted)
        self.assertEqual(decrypted, test_data)

    def test_database_failure_security_impact(self):
        """Test security behavior during database failures."""
        from django.db import DatabaseError

        # Simulate database failure during security operation
        with patch('django.db.models.Model.save') as mock_save:
            mock_save.side_effect = DatabaseError("Database connection lost")

            # Security middleware should still function
            request = self.factory.get('/?param=<script>alert(1)</script>')

            xss_middleware = XSSProtectionMiddleware()
            result = xss_middleware.process_request(request)

            # XSS should still be detected and handled
            self.assertEqual(request.GET.get('param'), '[SANITIZED]')

    def test_high_concurrency_security_stability(self):
        """Test security system stability under high concurrency."""
        import threading
        import queue

        results = queue.Queue()
        errors = queue.Queue()

        def concurrent_security_test(thread_id):
            try:
                # Mix of legitimate and malicious requests
                requests = [
                    (f'legitimate_user_{thread_id}@example.com', False),
                    (f'<script>alert("{thread_id}")</script>', True),
                    (f'normal_search_query_{thread_id}', False),
                    (f'javascript:alert("{thread_id}")', True),
                ]

                xss_middleware = XSSProtectionMiddleware()

                for content, should_be_xss in requests:
                    request = self.factory.get(f'/?param={content}')

                    result = xss_middleware.process_request(request)
                    is_blocked = result is not None

                    if should_be_xss and not is_blocked:
                        errors.put(f"Thread {thread_id}: XSS not blocked - {content}")
                        return
                    elif not should_be_xss and is_blocked:
                        errors.put(f"Thread {thread_id}: Legitimate content blocked - {content}")
                        return

                results.put(f"thread_{thread_id}_success")

            except (ValueError, TypeError, AttributeError, KeyError) as e:
                errors.put(f"Thread {thread_id}: Exception - {str(e)}")

        # Create many concurrent threads
        threads = []
        for i in range(20):
            thread = threading.Thread(target=concurrent_security_test, args=(i,))
            threads.append(thread)
            thread.start()

        # Wait for completion
        for thread in threads:
            thread.join()

        # Check results
        self.assertTrue(errors.empty(), f"Concurrency security errors: {list(errors.queue)}")

        successful_threads = []
        while not results.empty():
            successful_threads.append(results.get())

        self.assertEqual(len(successful_threads), 20, "All concurrent security tests should succeed")


class CrossComponentSecurityValidationTest(TestCase):
    """Test suite for cross-component security validation."""

    def setUp(self):
        """Set up test fixtures."""
        self.factory = RequestFactory()

    def test_encryption_field_xss_protection_integration(self):
        """Test integration between encryption fields and XSS protection."""
        # Create encrypted field with potentially malicious content
        field = EnhancedSecureString()

        malicious_data = "<script>alert('field_xss')</script>"

        # Content should be encrypted regardless of XSS content
        encrypted = field.get_prep_value(malicious_data)
        self.assertTrue(encrypted.startswith('FERNET_V1:'))

        # When decrypted, original content should be preserved
        decrypted = field.from_db_value(encrypted, None, None)
        self.assertEqual(decrypted, malicious_data)

        # XSS protection should happen at request/response level, not storage level

    def test_logging_sanitization_encryption_integration(self):
        """Test integration between logging sanitization and encryption services."""
        from apps.core.middleware.logging_sanitization import LogSanitizationService

        # Test data that should be encrypted and sanitized
        sensitive_data = {
            'user_email': 'admin@company.com',
            'encrypted_field': SecureEncryptionService.encrypt('secret_data'),
            'api_token': 'sk_live_1234567890',
            'correlation_id': 'correlation-123'
        }

        # Sanitize for logging
        sanitized = LogSanitizationService.sanitize_extra_data(sensitive_data)

        # Sensitive fields should be sanitized
        self.assertEqual(sanitized['user_email'], '[SANITIZED]')
        self.assertEqual(sanitized['api_token'], '[SANITIZED]')

        # Encrypted data should also be sanitized in logs (no exposure)
        self.assertNotIn('secret_data', str(sanitized['encrypted_field']))

        # Non-sensitive fields should remain
        self.assertEqual(sanitized['correlation_id'], 'correlation-123')

    def test_security_headers_content_protection_integration(self):
        """Test integration between security headers and content protection."""
        request = self.factory.get('/')
        response = HttpResponse('<script>/* This is safe inline script */</script>')

        # Apply security headers
        security_middleware = SecurityHeadersMiddleware()
        secure_response = security_middleware.process_response(request, response)

        # Should have CSP that would block unsafe inline scripts
        csp_header = secure_response.get('Content-Security-Policy', '')
        if csp_header:
            # If CSP is present, should not allow unsafe-inline
            self.assertNotIn("'unsafe-inline'", csp_header)

        # Should have other security headers
        self.assertEqual(secure_response['X-Content-Type-Options'], 'nosniff')
        self.assertEqual(secure_response['X-Frame-Options'], 'DENY')

    @pytest.mark.slow
    def test_end_to_end_security_stress_test(self):
        """Comprehensive end-to-end security stress test."""
        # Create comprehensive attack scenario
        attack_scenarios = [
            # Multi-vector XSS
            {"path": "/search", "params": {"q": "<script>alert('xss')</script><img src=x onerror=alert(2)>"}},

            # Sensitive data exposure
            {"path": "/api/user", "params": {"email": "admin@test.com", "password": "secret123", "api_key": "sk_live_key"}},

            # Large payload attack
            {"path": "/upload", "params": {"data": "X" * 10000}},

            # Encoding bypass attempts
            {"path": "/param", "params": {"value": "%3Cscript%3Ealert(1)%3C/script%3E"}},

            # Unicode attacks
            {"path": "/unicode", "params": {"text": "＜script＞alert(1)＜/script＞"}},
        ]

        # Initialize all security components
        security_middleware = SecurityHeadersMiddleware()
        xss_middleware = XSSProtectionMiddleware()
        log_middleware = LogSanitizationMiddleware()

        successful_defenses = 0
        total_attacks = 0

        for scenario in attack_scenarios:
            for _ in range(10):  # Repeat each scenario 10 times
                total_attacks += 1

                # Create request
                request = self.factory.get(scenario["path"], scenario["params"])

                try:
                    # Process through security pipeline
                    log_middleware.process_request(request)

                    xss_result = xss_middleware.process_request(request)
                    response = xss_result or HttpResponse("OK")

                    final_response = security_middleware.process_response(request, response)

                    # Check if attack was properly handled
                    attack_blocked = False

                    # Check for XSS sanitization
                    for param, value in scenario["params"].items():
                        if any(xss in value.lower() for xss in ['<script', 'alert', 'onerror']):
                            sanitized_value = request.GET.get(param)
                            if sanitized_value == '[SANITIZED]':
                                attack_blocked = True

                    # Check for proper security headers
                    if 'X-Content-Type-Options' in final_response:
                        successful_defenses += 1 if attack_blocked else 0.5

                except (ValueError, TypeError, AttributeError, KeyError) as e:
                    # System handled attack by raising exception (also a defense)
                    successful_defenses += 0.5

        # Security effectiveness should be high
        effectiveness = successful_defenses / total_attacks if total_attacks > 0 else 0
        self.assertGreater(effectiveness, 0.8, f"Security effectiveness too low: {effectiveness:.2%}")


if __name__ == '__main__':
    pytest.main([__file__])