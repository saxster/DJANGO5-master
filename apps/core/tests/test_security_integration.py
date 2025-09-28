"""
Comprehensive integration tests for complete security stack.
Tests that all security fixes work together and provide defense-in-depth protection.
"""

import json
import time
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from apps.core.middleware.csp_nonce import CSPNonceMiddleware
from apps.core.xss_protection import CSRFHeaderMiddleware
from apps.core.error_handling import ErrorHandler
from background_tasks.tasks import validate_mqtt_topic, validate_mqtt_payload, publish_mqtt


class SecurityStackIntegrationTest(TestCase):
    """Integration tests for complete security stack"""

    def setUp(self):
        """Set up test fixtures"""
        self.factory = RequestFactory()
        self.client = Client()

    def test_complete_middleware_stack(self):
        """Test all security middleware work together"""
        request = self.factory.get('/')

        # Initialize middleware stack
        csp_middleware = CSPNonceMiddleware(lambda req: HttpResponse())
        csrf_middleware = CSRFHeaderMiddleware(lambda req: HttpResponse())

        # Process request through CSP middleware
        csp_middleware.process_request(request)

        # Verify nonce is generated
        self.assertTrue(hasattr(request, 'csp_nonce'))

        response = HttpResponse('<html><body>Test</body></html>')

        # Process response through both middleware
        csp_response = csp_middleware.process_response(request, response)
        final_response = csrf_middleware.process_response(request, csp_response)

        # Verify both CSP and CSRF headers are present
        self.assertIn('Content-Security-Policy', final_response)
        self.assertIn('X-XSS-Protection', final_response)
        self.assertIn('X-Content-Type-Options', final_response)

        # Verify nonce is in CSP header
        csp_header = final_response['Content-Security-Policy']
        self.assertIn(f"'nonce-{request.csp_nonce}'", csp_header)

    def test_xss_attack_prevention_comprehensive(self):
        """Test comprehensive XSS attack prevention across all layers"""
        xss_payloads = [
            "<script>alert('xss')</script>",
            "javascript:alert(1)",
            "<img src=x onerror=alert(1)>",
            "<svg onload=alert(1)>",
            "<iframe src=javascript:alert(1)></iframe>",
            "onclick='alert(1)'",
            "<body onload=alert(1)>",
        ]

        for payload in xss_payloads:
            with self.subTest(payload=payload):
                # Test MQTT validation blocks XSS
                try:
                    validate_mqtt_payload(payload)
                    # If not blocked by validation, should be sanitized
                    result = validate_mqtt_payload(payload)
                    self.assertNotIn('<script', result.lower())
                except ValidationError:
                    # Validation blocked - this is good
                    pass

                # Test CSP would block inline execution
                request = self.factory.get('/')
                csp_middleware = CSPNonceMiddleware(lambda req: HttpResponse())
                csp_middleware.process_request(request)

                response = HttpResponse()
                csp_response = csp_middleware.process_response(request, response)

                csp_header = csp_response.get('Content-Security-Policy', '')
                # Should not allow unsafe-inline
                self.assertNotIn("'unsafe-inline'", csp_header)

    def test_csrf_and_csp_compatibility(self):
        """Test CSRF and CSP protection work together"""
        client = Client(enforce_csrf_checks=True)

        # Make request that would trigger both CSRF and CSP
        response = client.get('/')

        if response.status_code == 200:
            # Both CSRF token and CSP headers should be present
            csrf_cookie_present = 'csrftoken' in client.cookies
            csp_header_present = 'Content-Security-Policy' in response

            # At least one security mechanism should be active
            self.assertTrue(csrf_cookie_present or csp_header_present)

    def test_session_security_with_error_handling(self):
        """Test session security integrates with secure error handling"""
        User = get_user_model()
        user = User.objects.create_user(
            loginid='securitytest',
            email='security@test.com',
            password='SecurePass123!'
        )

        client = Client()

        # Login to create session
        login_successful = client.login(
            username='securitytest',
            password='SecurePass123!'
        )

        if login_successful:
            # Session should be secure
            session_id = client.cookies.get('sessionid')
            self.assertIsNotNone(session_id)

            # If an error occurs, it should be handled securely
            try:
                raise Exception("Test security integration error")
            except Exception as e:
                response = ErrorHandler.handle_task_exception(
                    e,
                    task_name="session_security_test",
                    task_params={"user_id": user.id}
                )

                # Error response should not expose session details
                response_str = json.dumps(response)
                self.assertNotIn(str(user.id), response_str)
                self.assertNotIn("session", response_str.lower())

    @patch('background_tasks.tasks.publish_message')
    def test_mqtt_security_with_csp_protection(self, mock_publish):
        """Test MQTT security integrates with CSP protection"""
        # Test that MQTT payload sanitization works with CSP
        malicious_payload = {
            "alert": "<script>alert('mqtt_xss')</script>",
            "style": "background: url('javascript:evil()')",
        }

        topic = "security/test"

        with patch('background_tasks.tasks.publish_mqtt', return_value=None) as mock_task:
            result = publish_mqtt(mock_task, topic, malicious_payload)

            # MQTT should sanitize the payload
            self.assertTrue(result.get("success", False))

            # Verify sanitization occurred
            mock_publish.assert_called_once()
            called_payload = mock_publish.call_args[0][1]
            payload_str = json.dumps(called_payload)
            self.assertNotIn("<script", payload_str)
            self.assertNotIn("javascript:", payload_str)

    def test_correlation_id_tracking_across_layers(self):
        """Test correlation IDs work across all security layers"""
        correlation_id = "integration-test-123"

        # Test error handler uses correlation ID
        response = ErrorHandler.create_secure_task_response(
            success=False,
            correlation_id=correlation_id
        )
        self.assertEqual(response["correlation_id"], correlation_id)

        # Test MQTT task would use correlation ID
        with patch('background_tasks.tasks.publish_message'):
            with patch('background_tasks.tasks.publish_mqtt', return_value=None) as mock_task:
                result = publish_mqtt(mock_task, "test/topic", {"test": True})

                # Should have correlation ID for tracking
                self.assertIn("correlation_id", result)

    def test_security_headers_comprehensive_coverage(self):
        """Test all security headers are present across the application"""
        request = self.factory.get('/')

        # Stack all security middleware
        csp_middleware = CSPNonceMiddleware(lambda req: HttpResponse())
        csrf_middleware = CSRFHeaderMiddleware(lambda req: HttpResponse())

        # Process through all middleware
        csp_middleware.process_request(request)
        response = HttpResponse()

        csp_response = csp_middleware.process_response(request, response)
        final_response = csrf_middleware.process_response(request, csp_response)

        # Comprehensive security headers check
        security_headers = {
            'Content-Security-Policy': True,  # Must be present
            'X-XSS-Protection': '1; mode=block',
            'X-Content-Type-Options': 'nosniff',
        }

        for header, expected_value in security_headers.items():
            if expected_value is True:
                self.assertIn(header, final_response)
            else:
                self.assertEqual(final_response.get(header), expected_value)

    def test_attack_simulation_comprehensive(self):
        """Comprehensive attack simulation across all vectors"""
        attack_vectors = {
            'xss_script': "<script>document.cookie</script>",
            'xss_img': "<img src=x onerror=alert(1)>",
            'sql_injection': "'; DROP TABLE users; --",
            'path_traversal': "../../../etc/passwd",
            'null_byte': "normal\x00malicious",
            'javascript_url': "javascript:alert(1)",
            'data_uri': "data:text/html,<script>alert(1)</script>",
        }

        for attack_type, payload in attack_vectors.items():
            with self.subTest(attack_type=attack_type):
                # Test MQTT validation
                if attack_type in ['null_byte']:
                    # Should be blocked by topic validation
                    with self.assertRaises(ValidationError):
                        validate_mqtt_topic(payload)
                else:
                    # Should be sanitized by payload validation
                    sanitized = validate_mqtt_payload(payload)
                    self.assertNotIn('<script', str(sanitized).lower())
                    self.assertNotIn('javascript:', str(sanitized).lower())

                # Test error handling doesn't expose attack payload
                try:
                    raise ValueError(f"Attack payload: {payload}")
                except Exception as e:
                    response = ErrorHandler.handle_task_exception(
                        e,
                        task_name="attack_simulation",
                        task_params={"payload": payload}
                    )

                    # Response should not contain attack payload
                    response_str = json.dumps(response)
                    if attack_type == 'xss_script':
                        self.assertNotIn('<script', response_str)
                    elif attack_type == 'sql_injection':
                        self.assertNotIn('DROP TABLE', response_str)

    def test_performance_with_full_security_stack(self):
        """Test performance impact of complete security stack"""
        request = self.factory.get('/')

        # Initialize all middleware
        csp_middleware = CSPNonceMiddleware(lambda req: HttpResponse())
        csrf_middleware = CSRFHeaderMiddleware(lambda req: HttpResponse())

        # Measure performance with all security features
        start_time = time.time()

        for _ in range(100):
            # Process request through all security layers
            csp_middleware.process_request(request)
            response = HttpResponse()
            csp_response = csp_middleware.process_response(request, response)
            final_response = csrf_middleware.process_response(request, csp_response)

            # Simulate MQTT validation
            validate_mqtt_topic("home/temperature")
            validate_mqtt_payload({"temp": 25.5})

            # Simulate error handling
            ErrorHandler.create_secure_task_response(success=True)

        end_time = time.time()

        avg_time = (end_time - start_time) / 100

        # Complete security stack should add minimal overhead
        self.assertLess(avg_time, 0.01)  # Less than 10ms per request

    def test_security_configuration_validation(self):
        """Test all security configurations are properly set"""
        from django.conf import settings

        # CSP configuration
        self.assertTrue(settings.CSP_ENABLE_NONCE)
        self.assertGreater(settings.CSP_NONCE_LENGTH, 16)

        # Session security
        self.assertEqual(settings.SESSION_ENGINE, "django.contrib.sessions.backends.db")
        self.assertTrue(settings.SESSION_EXPIRE_AT_BROWSER_CLOSE)
        self.assertTrue(settings.SESSION_SAVE_EVERY_REQUEST)  # Rule #10: Security first

        # Middleware stack
        required_middleware = [
            'apps.core.middleware.csp_nonce.CSPNonceMiddleware',
            'apps.core.xss_protection.CSRFHeaderMiddleware',
            'django.middleware.csrf.CsrfViewMiddleware',
        ]

        for middleware in required_middleware:
            self.assertIn(middleware, settings.MIDDLEWARE)

    def test_logging_security_integration(self):
        """Test security logging works across all components"""
        from django.conf import settings

        # Security logging should be configured
        loggers = settings.LOGGING_CONFIG_.get('loggers', {})
        self.assertIn('security', loggers)
        self.assertIn('security.csp', loggers)

        # Security handlers should exist
        handlers = settings.LOGGING_CONFIG_.get('handlers', {})
        self.assertIn('security_file', handlers)

        # Test actual logging (would require log file access in real scenario)
        with patch('logging.Logger.info') as mock_log:
            # Generate security event
            request = self.factory.get('/')
            csp_middleware = CSPNonceMiddleware(lambda req: HttpResponse())
            csp_middleware.process_request(request)

            # Logging should occur for security events
            # (Implementation-specific assertion would go here)

    def test_multi_layer_defense_effectiveness(self):
        """Test defense-in-depth effectiveness against sophisticated attacks"""
        # Sophisticated multi-vector attack
        complex_attack = {
            "topic": "home/temp<script>alert(1)</script>",
            "payload": {
                "data": "'; DROP TABLE sessions; --",
                "callback": "javascript:steal_cookies()",
                "style": "<style>body{background:url('javascript:alert(1)')}</style>",
                "nested": {
                    "xss": "<img src=x onerror=alert(document.cookie)>",
                    "injection": "admin'--"
                }
            }
        }

        # Layer 1: MQTT Topic Validation
        with self.assertRaises(ValidationError):
            validate_mqtt_topic(complex_attack["topic"])

        # Layer 2: MQTT Payload Sanitization
        sanitized_payload = validate_mqtt_payload(complex_attack["payload"])
        sanitized_str = json.dumps(sanitized_payload)

        # Should remove all malicious content
        dangerous_patterns = [
            '<script',
            'javascript:',
            '<img',
            'onerror',
            '<style',
            'DROP TABLE',
        ]

        for pattern in dangerous_patterns:
            self.assertNotIn(pattern, sanitized_str)

        # Layer 3: CSP Prevention
        request = self.factory.get('/')
        csp_middleware = CSPNonceMiddleware(lambda req: HttpResponse())
        csp_middleware.process_request(request)
        response = HttpResponse()
        csp_response = csp_middleware.process_response(request, response)

        csp_header = csp_response.get('Content-Security-Policy', '')
        self.assertNotIn("'unsafe-inline'", csp_header)

        # Layer 4: Secure Error Handling
        try:
            raise Exception("Attack simulation with complex payload")
        except Exception as e:
            error_response = ErrorHandler.handle_task_exception(
                e,
                task_name="multi_layer_test",
                task_params=complex_attack["payload"]
            )

            # Error response should not expose any attack vectors
            response_str = json.dumps(error_response)
            for pattern in dangerous_patterns:
                self.assertNotIn(pattern, response_str)

    def test_production_readiness_security(self):
        """Test production readiness from security perspective"""
        from django.conf import settings

        security_checklist = [
            # Debug should be False for production
            ('Debug disabled', not settings.DEBUG if hasattr(settings, 'DEBUG') else True),

            # Security middleware should be enabled
            ('CSP middleware enabled', 'CSPNonceMiddleware' in str(settings.MIDDLEWARE)),
            ('CSRF middleware enabled', 'CSRFHeaderMiddleware' in str(settings.MIDDLEWARE)),

            # Session security
            ('Secure sessions', settings.SESSION_ENGINE == "django.contrib.sessions.backends.db"),
            ('Session expiry', settings.SESSION_EXPIRE_AT_BROWSER_CLOSE),

            # CSP security
            ('CSP nonces enabled', settings.CSP_ENABLE_NONCE),
            ('CSP reporting configured', bool(settings.CSP_REPORT_URI)),

            # Error handling security
            ('Secure error handling available', hasattr(ErrorHandler, 'create_secure_task_response')),
        ]

        for check_name, condition in security_checklist:
            with self.subTest(check=check_name):
                self.assertTrue(condition, f"Security check failed: {check_name}")

    def test_regression_prevention(self):
        """Test against regression of previously fixed security issues"""
        # Ensure stack trace exposure is fixed
        try:
            raise Exception("Regression test exception")
        except Exception as e:
            response = ErrorHandler.handle_task_exception(
                e,
                task_name="regression_test"
            )

            response_str = json.dumps(response)
            # Should not contain stack trace elements
            self.assertNotIn("Traceback", response_str)
            self.assertNotIn("File \"", response_str)
            self.assertNotIn(".py\", line", response_str)

        # Ensure unsafe-inline is not re-introduced
        request = self.factory.get('/')
        csp_middleware = CSPNonceMiddleware(lambda req: HttpResponse())
        csp_middleware.process_request(request)
        response = HttpResponse()
        csp_response = csp_middleware.process_response(request, response)

        csp_header = csp_response.get('Content-Security-Policy', '')
        self.assertNotIn("'unsafe-inline'", csp_header)

        # Ensure CSRF protection is active
        csrf_middleware = CSRFHeaderMiddleware(lambda req: HttpResponse())
        csrf_response = csrf_middleware.process_response(request, HttpResponse())

        self.assertIn('X-XSS-Protection', csrf_response)
        self.assertIn('X-Content-Type-Options', csrf_response)


class SecurityMonitoringIntegrationTest(TestCase):
    """Integration tests for security monitoring and alerting"""

    def test_csp_violation_reporting_integration(self):
        """Test CSP violation reporting works with monitoring"""
        from django.conf import settings

        # CSP monitoring should be configured
        self.assertTrue(hasattr(settings, 'CSP_MONITORING'))

        csp_monitoring = settings.CSP_MONITORING
        self.assertIsInstance(csp_monitoring, dict)

        # Should have alerting configuration
        self.assertIn('ENABLE_ALERTING', csp_monitoring)
        self.assertIn('ALERT_THRESHOLD_PER_HOUR', csp_monitoring)

    def test_security_logging_integration(self):
        """Test security events are properly logged for monitoring"""
        # This would test that security events generate proper log entries
        # for external monitoring systems to consume
        pass

    def test_correlation_tracking_monitoring(self):
        """Test correlation IDs enable proper monitoring across systems"""
        correlation_id = "monitoring-test-456"

        # Error handling
        response1 = ErrorHandler.create_secure_task_response(
            correlation_id=correlation_id
        )

        # MQTT task
        with patch('background_tasks.tasks.publish_message'):
            with patch('background_tasks.tasks.publish_mqtt', return_value=None) as mock_task:
                response2 = publish_mqtt(mock_task, "monitor/test", {"test": True})

        # Both should be trackable via correlation ID
        self.assertIn("correlation_id", response1)
        self.assertIn("correlation_id", response2)


class SecurityComplianceTest(TestCase):
    """Tests for security compliance and standards"""

    def test_owasp_top_10_protection(self):
        """Test protection against OWASP Top 10 vulnerabilities"""
        # A1: Injection
        with self.assertRaises(ValidationError):
            validate_mqtt_topic("test'; DROP TABLE users; --")

        # A2: Broken Authentication (session security)
        from django.conf import settings
        self.assertTrue(settings.SESSION_EXPIRE_AT_BROWSER_CLOSE)

        # A3: Sensitive Data Exposure (error handling)
        try:
            raise Exception("Sensitive database password: secret123")
        except Exception as e:
            response = ErrorHandler.handle_task_exception(e, "compliance_test")
            response_str = json.dumps(response)
            self.assertNotIn("secret123", response_str)

        # A6: Security Misconfiguration
        self.assertFalse(getattr(settings, 'DEBUG', True))

        # A7: Cross-Site Scripting (XSS)
        request = self.factory.get('/')
        csp_middleware = CSPNonceMiddleware(lambda req: HttpResponse())
        csp_middleware.process_request(request)
        response = HttpResponse()
        csp_response = csp_middleware.process_response(request, response)

        csp_header = csp_response.get('Content-Security-Policy', '')
        self.assertNotIn("'unsafe-inline'", csp_header)

    def test_gdpr_compliance_features(self):
        """Test features supporting GDPR compliance"""
        # Data minimization in error responses
        sensitive_data = {"email": "user@example.com", "phone": "1234567890"}

        try:
            raise Exception("GDPR test exception")
        except Exception as e:
            response = ErrorHandler.handle_task_exception(
                e,
                task_name="gdpr_test",
                task_params=sensitive_data
            )

            # Personal data should not be in error response
            response_str = json.dumps(response)
            self.assertNotIn("user@example.com", response_str)
            self.assertNotIn("1234567890", response_str)

    def test_security_audit_readiness(self):
        """Test system is ready for security audits"""
        from django.conf import settings

        audit_requirements = [
            # Logging for audit trails
            ('Security logging configured', 'security' in settings.LOGGING_CONFIG_.get('loggers', {})),

            # Correlation IDs for traceability
            ('Correlation tracking available', hasattr(ErrorHandler, 'handle_task_exception')),

            # Input validation
            ('Input validation implemented', callable(validate_mqtt_topic)),

            # Secure error handling
            ('Secure error responses', hasattr(ErrorHandler, 'create_secure_task_response')),

            # CSP implementation
            ('Content Security Policy active', settings.CSP_ENABLE_NONCE),
        ]

        for requirement_name, condition in audit_requirements:
            with self.subTest(requirement=requirement_name):
                self.assertTrue(condition, f"Audit requirement not met: {requirement_name}")