"""
Comprehensive tests for CSP Nonce Middleware security implementation.
Tests that CSPNonceMiddleware provides secure nonce-based Content Security Policy.
"""

import base64
from django.http import HttpResponse
from apps.core.middleware.csp_nonce import CSPNonceMiddleware, calculate_script_hash, calculate_style_hash


class CSPNonceMiddlewareTest(TestCase):
    """Test CSP Nonce Middleware functionality"""

    def setUp(self):
        """Set up test fixtures"""
        self.factory = RequestFactory()
        self.middleware = CSPNonceMiddleware(lambda request: HttpResponse())

    def test_middleware_initialization(self):
        """Test middleware initializes correctly"""
        middleware = CSPNonceMiddleware()
        self.assertIsNotNone(middleware)

    @override_settings(CSP_ENABLE_NONCE=True)
    def test_nonce_generation(self):
        """Test that nonces are generated correctly"""
        request = self.factory.get('/')

        # Process request to generate nonce
        self.middleware.process_request(request)

        # Verify nonce is generated and stored
        self.assertTrue(hasattr(request, 'csp_nonce'))
        self.assertIsNotNone(request.csp_nonce)
        self.assertGreater(len(request.csp_nonce), 0)

    @override_settings(CSP_ENABLE_NONCE=True, CSP_NONCE_LENGTH=32)
    def test_nonce_length(self):
        """Test nonce has correct length"""
        request = self.factory.get('/')
        self.middleware.process_request(request)

        # Base64 encoded 32 bytes should be 44 characters
        expected_length = 44  # base64 encoded 32 bytes
        self.assertEqual(len(request.csp_nonce), expected_length)

    @override_settings(CSP_ENABLE_NONCE=True)
    def test_nonce_uniqueness(self):
        """Test that generated nonces are unique"""
        nonces = set()

        for _ in range(100):  # Generate 100 nonces
            request = self.factory.get('/')
            self.middleware.process_request(request)
            nonces.add(request.csp_nonce)

        # All nonces should be unique
        self.assertEqual(len(nonces), 100)

    @override_settings(CSP_ENABLE_NONCE=True)
    def test_nonce_cryptographic_strength(self):
        """Test nonce is cryptographically strong"""
        request = self.factory.get('/')
        self.middleware.process_request(request)

        nonce = request.csp_nonce

        # Verify nonce is valid base64
        try:
            decoded = base64.b64decode(nonce)
            self.assertGreater(len(decoded), 0)
        except Exception:
            self.fail("Nonce should be valid base64")

        # Verify nonce has good entropy (not all same characters)
        unique_chars = len(set(nonce))
        self.assertGreater(unique_chars, 10, "Nonce should have good entropy")

    @override_settings(CSP_ENABLE_NONCE=False)
    def test_nonce_disabled(self):
        """Test middleware does nothing when nonce is disabled"""
        request = self.factory.get('/')
        self.middleware.process_request(request)

        # No nonce should be generated
        self.assertFalse(hasattr(request, 'csp_nonce'))

    @override_settings(CSP_ENABLE_NONCE=True)
    def test_csp_header_generation(self):
        """Test CSP header is generated with nonce"""
        request = self.factory.get('/')
        response = HttpResponse()

        # Generate nonce
        self.middleware.process_request(request)

        # Process response to add CSP header
        processed_response = self.middleware.process_response(request, response)

        # Verify CSP header is present
        self.assertIn('Content-Security-Policy', processed_response)

        csp_header = processed_response['Content-Security-Policy']

        # Verify nonce is in the CSP header
        nonce_pattern = f"'nonce-{request.csp_nonce}'"
        self.assertIn(nonce_pattern, csp_header)

    @override_settings(CSP_ENABLE_NONCE=True)
    def test_unsafe_inline_removed(self):
        """Test that unsafe-inline is not present in CSP with nonces"""
        request = self.factory.get('/')
        response = HttpResponse()

        self.middleware.process_request(request)
        processed_response = self.middleware.process_response(request, response)

        csp_header = processed_response.get('Content-Security-Policy', '')

        # unsafe-inline should NOT be present when using nonces
        self.assertNotIn("'unsafe-inline'", csp_header)

    @override_settings(CSP_ENABLE_NONCE=True)
    def test_script_src_directive(self):
        """Test script-src directive includes nonce"""
        request = self.factory.get('/')
        response = HttpResponse()

        self.middleware.process_request(request)
        processed_response = self.middleware.process_response(request, response)

        csp_header = processed_response.get('Content-Security-Policy', '')

        # Should contain script-src with nonce
        self.assertIn('script-src', csp_header)
        self.assertIn(f"'nonce-{request.csp_nonce}'", csp_header)

    @override_settings(CSP_ENABLE_NONCE=True)
    def test_style_src_directive(self):
        """Test style-src directive includes nonce"""
        request = self.factory.get('/')
        response = HttpResponse()

        self.middleware.process_request(request)
        processed_response = self.middleware.process_response(request, response)

        csp_header = processed_response.get('Content-Security-Policy', '')

        # Should contain style-src with nonce
        self.assertIn('style-src', csp_header)
        self.assertIn(f"'nonce-{request.csp_nonce}'", csp_header)

    @override_settings(CSP_ENABLE_NONCE=True)
    def test_static_files_excluded(self):
        """Test static files don't get CSP headers"""
        request = self.factory.get('/static/css/style.css')
        response = HttpResponse()

        self.middleware.process_request(request)
        processed_response = self.middleware.process_response(request, response)

        # Static files should not have CSP headers
        self.assertNotIn('Content-Security-Policy', processed_response)

    @override_settings(CSP_ENABLE_NONCE=True)
    def test_media_files_excluded(self):
        """Test media files don't get CSP headers"""
        request = self.factory.get('/media/uploads/image.jpg')
        response = HttpResponse()

        self.middleware.process_request(request)
        processed_response = self.middleware.process_response(request, response)

        # Media files should not have CSP headers
        self.assertNotIn('Content-Security-Policy', processed_response)

    @override_settings(CSP_ENABLE_NONCE=True)
    def test_default_csp_directives(self):
        """Test default CSP directives are secure"""
        request = self.factory.get('/')
        response = HttpResponse()

        self.middleware.process_request(request)
        processed_response = self.middleware.process_response(request, response)

        csp_header = processed_response.get('Content-Security-Policy', '')

        # Verify secure defaults
        expected_directives = [
            "default-src 'self'",
            "object-src 'none'",
            "frame-ancestors 'none'",
            "base-uri 'self'",
            "form-action 'self'",
        ]

        for directive in expected_directives:
            self.assertIn(directive, csp_header)

    @override_settings(
        CSP_ENABLE_NONCE=True,
        CSP_DIRECTIVES={
            'script-src': ["'self'", "https://trusted-cdn.com"]
        }
    )
    def test_custom_csp_directives_merge(self):
        """Test custom CSP directives are merged with defaults"""
        request = self.factory.get('/')
        response = HttpResponse()

        self.middleware.process_request(request)
        processed_response = self.middleware.process_response(request, response)

        csp_header = processed_response.get('Content-Security-Policy', '')

        # Should contain custom directive
        self.assertIn('https://trusted-cdn.com', csp_header)
        # Should still contain nonce
        self.assertIn(f"'nonce-{request.csp_nonce}'", csp_header)

    @override_settings(CSP_ENABLE_NONCE=True, CSP_REPORT_URI='/api/csp-report/')
    def test_csp_report_uri(self):
        """Test CSP report-uri directive is included"""
        request = self.factory.get('/')
        response = HttpResponse()

        self.middleware.process_request(request)
        processed_response = self.middleware.process_response(request, response)

        csp_header = processed_response.get('Content-Security-Policy', '')

        # Should contain report-uri
        self.assertIn('report-uri /api/csp-report/', csp_header)

    def test_hash_collection_initialization(self):
        """Test script and style hash collection is initialized"""
        request = self.factory.get('/')
        self.middleware.process_request(request)

        # Hash collections should be initialized
        self.assertTrue(hasattr(request, 'csp_script_hashes'))
        self.assertTrue(hasattr(request, 'csp_style_hashes'))
        self.assertIsInstance(request.csp_script_hashes, list)
        self.assertIsInstance(request.csp_style_hashes, list)


class CSPHashFunctionsTest(TestCase):
    """Test CSP hash calculation functions"""

    def test_calculate_script_hash(self):
        """Test script hash calculation"""
        script_content = "console.log('hello world');"
        hash_value = calculate_script_hash(script_content)

        # Hash should be base64 encoded
        self.assertIsInstance(hash_value, str)
        self.assertGreater(len(hash_value), 0)

        # Should be consistent
        hash_value2 = calculate_script_hash(script_content)
        self.assertEqual(hash_value, hash_value2)

    def test_calculate_style_hash(self):
        """Test style hash calculation"""
        style_content = "body { margin: 0; padding: 0; }"
        hash_value = calculate_style_hash(style_content)

        # Hash should be base64 encoded
        self.assertIsInstance(hash_value, str)
        self.assertGreater(len(hash_value), 0)

        # Should be consistent
        hash_value2 = calculate_style_hash(style_content)
        self.assertEqual(hash_value, hash_value2)

    def test_different_content_different_hash(self):
        """Test different content produces different hashes"""
        script1 = "console.log('hello');"
        script2 = "console.log('world');"

        hash1 = calculate_script_hash(script1)
        hash2 = calculate_script_hash(script2)

        self.assertNotEqual(hash1, hash2)

    def test_whitespace_handling(self):
        """Test hash calculation handles whitespace correctly"""
        script1 = "  console.log('test');  "
        script2 = "console.log('test');"

        hash1 = calculate_script_hash(script1)
        hash2 = calculate_script_hash(script2)

        # Different whitespace should produce same hash (stripped)
        self.assertEqual(hash1, hash2)

    def test_empty_content_hash(self):
        """Test hash calculation for empty content"""
        hash_value = calculate_script_hash("")
        self.assertIsInstance(hash_value, str)
        self.assertGreater(len(hash_value), 0)


class CSPSecurityTest(TestCase):
    """Security-focused tests for CSP implementation"""

    @override_settings(CSP_ENABLE_NONCE=True)
    def test_xss_prevention_script_nonce(self):
        """Test XSS prevention with script nonces"""
        request = self.factory.get('/')
        response = HttpResponse()

        self.middleware.process_request(request)
        processed_response = self.middleware.process_response(request, response)

        csp_header = processed_response.get('Content-Security-Policy', '')

        # Should not allow unsafe-inline
        self.assertNotIn("'unsafe-inline'", csp_header)

        # Should require nonce for inline scripts
        self.assertIn("'nonce-", csp_header)

    @override_settings(CSP_ENABLE_NONCE=True)
    def test_css_injection_prevention(self):
        """Test CSS injection prevention with style nonces"""
        request = self.factory.get('/')
        response = HttpResponse()

        self.middleware.process_request(request)
        processed_response = self.middleware.process_response(request, response)

        csp_header = processed_response.get('Content-Security-Policy', '')

        # Should prevent CSS injection
        self.assertIn('style-src', csp_header)
        self.assertNotIn("'unsafe-inline'", csp_header)

    @override_settings(CSP_ENABLE_NONCE=True)
    def test_object_embedding_prevention(self):
        """Test prevention of object/embed tags"""
        request = self.factory.get('/')
        response = HttpResponse()

        self.middleware.process_request(request)
        processed_response = self.middleware.process_response(request, response)

        csp_header = processed_response.get('Content-Security-Policy', '')

        # Should prevent object embedding
        self.assertIn("object-src 'none'", csp_header)

    @override_settings(CSP_ENABLE_NONCE=True)
    def test_clickjacking_prevention(self):
        """Test clickjacking prevention"""
        request = self.factory.get('/')
        response = HttpResponse()

        self.middleware.process_request(request)
        processed_response = self.middleware.process_response(request, response)

        csp_header = processed_response.get('Content-Security-Policy', '')

        # Should prevent framing
        self.assertIn("frame-ancestors 'none'", csp_header)

    @override_settings(CSP_ENABLE_NONCE=True)
    def test_form_submission_restriction(self):
        """Test form submission is restricted to same origin"""
        request = self.factory.get('/')
        response = HttpResponse()

        self.middleware.process_request(request)
        processed_response = self.middleware.process_response(request, response)

        csp_header = processed_response.get('Content-Security-Policy', '')

        # Should restrict form actions
        self.assertIn("form-action 'self'", csp_header)

    def test_middleware_performance(self):
        """Test middleware performance impact"""
        import time

        request = self.factory.get('/')
        response = HttpResponse()

        # Measure processing time
        start_time = time.time()
        for _ in range(1000):
            self.middleware.process_request(request)
            self.middleware.process_response(request, response)
        end_time = time.time()

        avg_time = (end_time - start_time) / 1000

        # Should be very fast (less than 1ms per request)
        self.assertLess(avg_time, 0.001)


class CSPIntegrationTest(TestCase):
    """Integration tests for CSP middleware in full application context"""

    def test_middleware_in_settings(self):
        """Test CSP middleware is properly configured"""
        from django.conf import settings

        # Should be in middleware stack
        self.assertIn(
            'apps.core.middleware.csp_nonce.CSPNonceMiddleware',
            settings.MIDDLEWARE
        )

    def test_csp_settings_configuration(self):
        """Test CSP settings are properly configured"""
        from django.conf import settings

        # Should have CSP settings
        self.assertTrue(hasattr(settings, 'CSP_ENABLE_NONCE'))
        self.assertTrue(settings.CSP_ENABLE_NONCE)

    @override_settings(CSP_ENABLE_NONCE=True)
    def test_template_nonce_usage(self):
        """Test nonce can be used in templates"""
        request = self.factory.get('/')
        self.middleware.process_request(request)

        # Nonce should be available for template use
        self.assertTrue(hasattr(request, 'csp_nonce'))

        # Mock template usage
        nonce = request.csp_nonce
        script_tag = f'<script nonce="{nonce}">console.log("safe");</script>'

        # Should be valid nonce format
        self.assertRegex(nonce, r'^[A-Za-z0-9+/]+=*$')  # Base64 pattern