"""
Advanced XSS Protection Edge Case Tests.

Tests sophisticated XSS attack vectors, edge cases, and performance characteristics
that go beyond basic pattern detection to ensure comprehensive protection.

Coverage areas:
- Rate limiting edge cases and bypass attempts
- Advanced obfuscation and encoding techniques
- Browser-specific attack vectors
- Performance under attack load
- Content-Type confusion attacks
- Unicode normalization vulnerabilities
- Polyglot and mutation XSS
- DOM-based XSS patterns
"""

import time
import pytest
import json
import urllib.parse
from unittest.mock import Mock, patch, MagicMock
from django.test import TestCase, RequestFactory, override_settings
from django.http import HttpResponse, HttpResponseBadRequest, QueryDict
from django.contrib.auth import get_user_model

from apps.core.xss_protection import XSSProtectionMiddleware
from apps.core.validation import XSSPrevention


class XSSRateLimitingEdgeCaseTest(TestCase):
    """Test suite for XSS rate limiting edge cases and bypass attempts."""

    def setUp(self):
        """Set up test fixtures."""
        self.factory = RequestFactory()
        self.middleware = XSSProtectionMiddleware(get_response=lambda r: HttpResponse())

    def test_ip_spoofing_rate_limit_bypass_attempt(self):
        """Test rate limiting works against IP spoofing attempts."""
        xss_payload = "<script>alert('xss')</script>"

        # Try to bypass rate limiting by spoofing different IPs
        spoofed_headers = [
            {'HTTP_X_FORWARDED_FOR': '1.1.1.1, 192.168.1.100'},
            {'HTTP_X_FORWARDED_FOR': '2.2.2.2'},
            {'HTTP_X_REAL_IP': '3.3.3.3'},
            {'HTTP_CLIENT_IP': '4.4.4.4'},
            {'REMOTE_ADDR': '5.5.5.5'},
        ]

        # First, trigger rate limit with genuine IP
        for i in range(6):  # Exceed the default limit of 5
            request = self.factory.get(f'/?param={xss_payload}_{i}', REMOTE_ADDR='192.168.1.100')
            response = self.middleware.process_request(request)

        # Should be rate limited
        self.assertIsInstance(response, HttpResponseBadRequest)

        # Try bypass with spoofed headers (should still be limited by real IP)
        for headers in spoofed_headers:
            request = self.factory.get(f'/?param={xss_payload}_spoofed',
                                     REMOTE_ADDR='192.168.1.100', **headers)
            response = self.middleware.process_request(request)

            # Should still be rate limited despite spoofed headers
            self.assertIsInstance(response, HttpResponseBadRequest)

    def test_distributed_xss_attack_simulation(self):
        """Test handling of distributed XSS attacks from multiple IPs."""
        xss_payload = "<script>alert('distributed')</script>"

        # Simulate attacks from different legitimate IPs
        attack_ips = [f'10.0.1.{i}' for i in range(1, 21)]  # 20 different IPs

        successful_requests = 0
        rate_limited_requests = 0

        for ip in attack_ips:
            # Each IP gets its own rate limit allowance
            for attempt in range(3):  # 3 attempts per IP
                request = self.factory.get(f'/?attack={xss_payload}_{attempt}', REMOTE_ADDR=ip)
                response = self.middleware.process_request(request)

                if response is None:  # Request processed normally
                    successful_requests += 1
                elif isinstance(response, HttpResponseBadRequest):
                    rate_limited_requests += 1

        # Should handle distributed attack properly
        self.assertGreater(successful_requests, 0)  # Some requests should be processed
        self.assertEqual(successful_requests + rate_limited_requests, 60)  # All 60 requests accounted for

    def test_rate_limit_window_expiration(self):
        """Test rate limit window expiration and reset."""
        xss_payload = "<script>alert('window_test')</script>"
        client_ip = '192.168.1.200'

        # Override rate limiting settings for faster testing
        with override_settings(XSS_RATE_LIMIT_WINDOW=1, XSS_MAX_ATTEMPTS=2):  # 1 second window, 2 attempts
            middleware = XSSProtectionMiddleware()

            # Make requests to trigger rate limiting
            for i in range(3):  # Exceed limit of 2
                request = self.factory.get(f'/?param={xss_payload}_{i}', REMOTE_ADDR=client_ip)
                response = middleware.process_request(request)

            # Should be rate limited
            self.assertIsInstance(response, HttpResponseBadRequest)

            # Wait for window to expire
            time.sleep(1.1)

            # Should be able to make requests again
            request = self.factory.get(f'/?param={xss_payload}_after_reset', REMOTE_ADDR=client_ip)
            response = middleware.process_request(request)

            # Should not be rate limited anymore
            self.assertIsNone(response)  # Normal processing

    def test_concurrent_rate_limiting(self):
        """Test rate limiting under concurrent requests."""
        import threading
        import queue

        xss_payload = "<script>alert('concurrent')</script>"
        client_ip = '192.168.1.300'

        responses = queue.Queue()

        def make_concurrent_request(request_id):
            request = self.factory.get(f'/?param={xss_payload}_{request_id}', REMOTE_ADDR=client_ip)
            response = self.middleware.process_request(request)
            responses.put(response)

        # Create multiple concurrent threads
        threads = []
        for i in range(10):
            thread = threading.Thread(target=make_concurrent_request, args=(i,))
            threads.append(thread)
            thread.start()

        # Wait for all threads
        for thread in threads:
            thread.join()

        # Analyze responses
        none_responses = 0
        bad_request_responses = 0

        while not responses.empty():
            response = responses.get()
            if response is None:
                none_responses += 1
            elif isinstance(response, HttpResponseBadRequest):
                bad_request_responses += 1

        # Should have some requests processed and some rate limited
        self.assertEqual(none_responses + bad_request_responses, 10)
        self.assertGreater(bad_request_responses, 0)  # Some should be rate limited


class AdvancedObfuscationTest(TestCase):
    """Test suite for advanced XSS obfuscation techniques."""

    def setUp(self):
        """Set up test fixtures."""
        self.middleware = XSSProtectionMiddleware()

    def test_unicode_normalization_attacks(self):
        """Test detection of Unicode normalization-based XSS attacks."""
        # Unicode normalization attacks that might bypass simple filters
        unicode_attacks = [
            # Normalization forms that might create script tags
            "＜script＞alert(1)＜/script＞",  # Fullwidth characters
            "<\u0073cript>alert(1)</script>",  # Unicode 's'
            "<scr\u0131pt>alert(1)</script>",  # Dotless i
            "<scr\u0130pt>alert(1)</script>",  # Capital I with dot

            # Homograph attacks
            "<ѕсrірt>alert(1)</ѕсrірt>",  # Cyrillic characters that look like Latin

            # Zero-width characters
            "<sc\u200Bript>alert(1)</script>",  # Zero-width space
            "<sc\u200Cript>alert(1)</script>",  # Zero-width non-joiner
            "<sc\uFEFFript>alert(1)</script>",  # Zero-width no-break space

            # Combining characters
            "<s\u0300cript>alert(1)</script>",  # Combining grave accent
        ]

        for attack in unicode_attacks:
            with self.subTest(attack=attack):
                is_xss = self.middleware._is_xss_attempt(attack)
                self.assertTrue(is_xss, f"Failed to detect Unicode obfuscated XSS: {repr(attack)}")

    def test_polyglot_xss_attacks(self):
        """Test detection of polyglot XSS that works in multiple contexts."""
        polyglot_attacks = [
            # JavaScript polyglot
            "javascript:/*--></title></style></textarea></script></xmp>"
            "<svg/onload='+/\"/+/onmouseover=1/+/[*/[]/+alert(1)//'>",

            # HTML/JavaScript/CSS polyglot
            "\"><img src=x onerror=alert(1)>//",

            # JSON/HTML polyglot
            "\"},alert(1),{\"a\":\"",

            # URL/HTML polyglot
            "javascript:alert(1)//\"><img src=x onerror=alert(2)>",

            # Multiple context breaks
            "'><script>alert(1)</script><style>*{color:red}</style><!--",

            # PHP/HTML polyglot (for environments that process PHP)
            "<?php echo 'XSS'; ?><script>alert(1)</script>",
        ]

        for attack in polyglot_attacks:
            with self.subTest(attack=attack):
                is_xss = self.middleware._is_xss_attempt(attack)
                self.assertTrue(is_xss, f"Failed to detect polyglot XSS: {repr(attack)}")

    def test_mutation_xss_patterns(self):
        """Test detection of mutation XSS that changes after parsing."""
        mutation_attacks = [
            # HTML entity mutations
            "&lt;img src=x onerror=alert(1)&gt;",
            "&#60;script&#62;alert(1)&#60;/script&#62;",

            # Mislabeled encoding
            "%253Cscript%253Ealert(1)%253C/script%253E",  # Double URL encoding

            # Charset confusion
            "\xc2\xbc\x73\x63\x72\x69\x70\x74\xc2\xbe",  # UTF-8 angle brackets

            # HTML5 entity without semicolon
            "&ltscript&gtalert(1)&lt/script&gt",

            # Backtick-based mutations
            "`<script>alert(1)</script>`",

            # Template literal confusion
            "${alert(1)}",
            "#{alert(1)}",
        ]

        for attack in mutation_attacks:
            with self.subTest(attack=attack):
                is_xss = self.middleware._is_xss_attempt(attack)
                self.assertTrue(is_xss, f"Failed to detect mutation XSS: {repr(attack)}")

    def test_encoding_layer_attacks(self):
        """Test attacks using multiple encoding layers."""
        # Base attack
        base_attack = "<script>alert(1)</script>"

        # Multiple encoding layers
        encoding_attacks = []

        # URL encode
        url_encoded = urllib.parse.quote(base_attack)
        encoding_attacks.append(url_encoded)

        # Double URL encode
        double_url_encoded = urllib.parse.quote(url_encoded)
        encoding_attacks.append(double_url_encoded)

        # HTML entity encode
        html_encoded = base_attack.replace('<', '&lt;').replace('>', '&gt;')
        encoding_attacks.append(html_encoded)

        # Base64 encode
        import base64
        base64_encoded = base64.b64encode(base_attack.encode()).decode()
        encoding_attacks.append(f"base64:{base64_encoded}")

        # Hex encode
        hex_encoded = base_attack.encode().hex()
        encoding_attacks.append(f"hex:{hex_encoded}")

        for attack in encoding_attacks:
            with self.subTest(attack=attack):
                # Some encodings might be detected, others might not
                # The key is that they should be handled gracefully
                try:
                    is_xss = self.middleware._is_xss_attempt(attack)
                    # Either detected as XSS or handled safely
                    self.assertIsInstance(is_xss, bool)
                except (ValueError, TypeError, AttributeError, KeyError) as e:
                    self.fail(f"Encoding attack caused exception: {e}")


class BrowserSpecificVectorTest(TestCase):
    """Test suite for browser-specific XSS attack vectors."""

    def setUp(self):
        """Set up test fixtures."""
        self.middleware = XSSProtectionMiddleware()

    def test_internet_explorer_specific_vectors(self):
        """Test IE-specific XSS vectors."""
        ie_vectors = [
            # IE conditional comments
            "<!--[if IE]><script>alert(1)</script><![endif]-->",

            # IE VBScript
            "<script language=vbscript>msgbox 1</script>",

            # IE expression() in CSS
            "<div style='background:expression(alert(1))'>",

            # IE HTC behaviors
            "<div style='behavior:url(javascript:alert(1))'>",

            # IE data: protocol variations
            "<iframe src='data:text/html,<script>alert(1)</script>'>",

            # IE XML data islands
            "<xml><i><b>&lt;img src=x onerror=alert(1)&gt;</b></i></xml>",
        ]

        for vector in ie_vectors:
            with self.subTest(vector=vector):
                is_xss = self.middleware._is_xss_attempt(vector)
                self.assertTrue(is_xss, f"Failed to detect IE-specific XSS: {repr(vector)}")

    def test_chrome_safari_specific_vectors(self):
        """Test Chrome/Safari-specific XSS vectors."""
        webkit_vectors = [
            # WebKit-specific CSS
            "<div style='-webkit-binding:url(javascript:alert(1))'>",

            # WebKit CSS animations
            "<style>@keyframes x{0%{color:red}} div{animation:x 1s}</style>",

            # Chrome extension protocol
            "chrome-extension://anything/script.js",

            # Safari-specific protocols
            "x-webkit-any-link:javascript:alert(1)",

            # WebKit CSS filters
            "<div style='filter:url(javascript:alert(1))'>",
        ]

        for vector in webkit_vectors:
            with self.subTest(vector=vector):
                is_xss = self.middleware._is_xss_attempt(vector)
                # Some might be detected, some might not - test graceful handling
                self.assertIsInstance(is_xss, bool)

    def test_firefox_specific_vectors(self):
        """Test Firefox-specific XSS vectors."""
        firefox_vectors = [
            # Mozilla bindings
            "<div style='-moz-binding:url(javascript:alert(1))'>",

            # XUL injection
            "<xul:script>alert(1)</xul:script>",

            # Firefox XBL
            "<?xml-stylesheet href='javascript:alert(1)'?>",

            # Mozilla-specific CSS
            "<div style='-moz-appearance:textfield;-moz-binding:url(data:text/xml,alert(1))'>",
        ]

        for vector in firefox_vectors:
            with self.subTest(vector=vector):
                is_xss = self.middleware._is_xss_attempt(vector)
                self.assertTrue(is_xss, f"Failed to detect Firefox-specific XSS: {repr(vector)}")


class ContentTypeConfusionTest(TestCase):
    """Test suite for Content-Type confusion attacks."""

    def setUp(self):
        """Set up test fixtures."""
        self.factory = RequestFactory()
        self.middleware = XSSProtectionMiddleware()

    def test_json_content_type_xss(self):
        """Test XSS in JSON content type requests."""
        json_payloads = [
            '{"data": "<script>alert(1)</script>"}',
            '{"callback": "javascript:alert(1)"}',
            '{"html": "<img src=x onerror=alert(1)>"}',
            '["<script>alert(1)</script>"]',
            '{"nested": {"xss": "<svg onload=alert(1)>"}}',
        ]

        for payload in json_payloads:
            request = self.factory.post('/api/data',
                                      data=payload,
                                      content_type='application/json')

            # Create QueryDict from JSON for testing
            import json as json_module
            try:
                json_data = json_module.loads(payload)
                # Simulate processing of JSON data as parameters
                if isinstance(json_data, dict):
                    for key, value in json_data.items():
                        if isinstance(value, str):
                            is_xss = self.middleware._is_xss_attempt(value)
                            if any(pattern in value.lower() for pattern in ['<script', 'javascript:', 'onerror']):
                                self.assertTrue(is_xss, f"Failed to detect XSS in JSON: {value}")
            except json_module.JSONDecodeError:
                pass  # Invalid JSON is handled elsewhere

    def test_xml_content_type_xss(self):
        """Test XSS in XML content type requests."""
        xml_payloads = [
            '<data><![CDATA[<script>alert(1)</script>]]></data>',
            '<payload>javascript:alert(1)</payload>',
            '<img src="x" onerror="alert(1)"/>',
            '<?xml version="1.0"?><script>alert(1)</script>',
            '<svg><script>alert(1)</script></svg>',
        ]

        for payload in xml_payloads:
            request = self.factory.post('/api/xml',
                                      data=payload,
                                      content_type='application/xml')

            # Test XSS detection in XML content
            is_xss = self.middleware._is_xss_attempt(payload)
            if any(pattern in payload.lower() for pattern in ['<script', 'javascript:', 'onerror']):
                self.assertTrue(is_xss, f"Failed to detect XSS in XML: {payload}")

    def test_multipart_boundary_confusion(self):
        """Test XSS in multipart form boundary manipulation."""
        # Simulate multipart data with potential XSS in boundaries
        multipart_data = (
            '--boundary<script>alert(1)</script>\r\n'
            'Content-Disposition: form-data; name="field"\r\n\r\n'
            'value\r\n'
            '--boundary<script>alert(1)</script>--\r\n'
        )

        request = self.factory.post('/upload',
                                  data=multipart_data,
                                  content_type='multipart/form-data; boundary=boundary<script>alert(1)</script>')

        # Test boundary XSS detection
        content_type = request.META.get('CONTENT_TYPE', '')
        is_xss = self.middleware._is_xss_attempt(content_type)
        self.assertTrue(is_xss, "Failed to detect XSS in multipart boundary")


class PerformanceUnderAttackTest(TestCase):
    """Test suite for performance characteristics under XSS attack load."""

    def setUp(self):
        """Set up test fixtures."""
        self.factory = RequestFactory()
        self.middleware = XSSProtectionMiddleware()

    def test_large_payload_performance(self):
        """Test performance with large XSS payloads."""
        # Create progressively larger payloads
        base_payload = "<script>alert('xss')</script>"

        payload_sizes = [1000, 10000, 50000, 100000]  # Up to 100KB

        for size in payload_sizes:
            # Create large payload by repeating base payload
            large_payload = base_payload * (size // len(base_payload))

            start_time = time.time()

            # Test XSS detection performance
            is_xss = self.middleware._is_xss_attempt(large_payload)

            processing_time = time.time() - start_time

            # Should detect XSS
            self.assertTrue(is_xss, f"Failed to detect XSS in large payload ({size} bytes)")

            # Should complete within reasonable time (not cause DoS)
            self.assertLess(processing_time, 1.0, f"XSS detection too slow for {size} bytes: {processing_time:.3f}s")

    def test_complex_pattern_performance(self):
        """Test performance with complex XSS patterns."""
        complex_patterns = [
            # Nested patterns
            "<script><script><script>alert(1)</script></script></script>",

            # Multiple attack vectors
            "<img src=x onerror=alert(1)><svg onload=alert(2)><iframe src=javascript:alert(3)>",

            # Long attribute chains
            "<div " + " ".join([f"attr{i}='value{i}'" for i in range(100)]) + " onload=alert(1)>",

            # Deep HTML nesting
            "<div>" * 50 + "<script>alert(1)</script>" + "</div>" * 50,

            # Complex encoding chains
            "%253C%2573%2563%2572%2569%2570%2574%253E%2561%256C%2565%2572%2574%2528%2531%2529%253C%252F%2573%2563%2572%2569%2570%2574%253E",
        ]

        for pattern in complex_patterns:
            start_time = time.time()

            is_xss = self.middleware._is_xss_attempt(pattern)

            processing_time = time.time() - start_time

            # Should detect XSS
            self.assertTrue(is_xss, f"Failed to detect complex XSS pattern: {pattern[:100]}...")

            # Should complete quickly
            self.assertLess(processing_time, 0.1, f"Complex pattern detection too slow: {processing_time:.3f}s")

    def test_memory_usage_under_attack(self):
        """Test memory usage during sustained XSS attacks."""
        import gc

        # Get initial memory state
        gc.collect()
        initial_objects = len(gc.get_objects())

        # Simulate sustained attack with various payloads
        attack_payloads = [
            "<script>alert(1)</script>",
            "<img src=x onerror=alert(1)>",
            "javascript:alert(1)",
            "<svg onload=alert(1)>",
            "<iframe src=javascript:alert(1)>",
        ]

        # Process many attack attempts
        for i in range(1000):
            payload = attack_payloads[i % len(attack_payloads)] + f"_{i}"

            request = self.factory.get(f'/?param={payload}')
            self.middleware.process_request(request)

        # Check memory growth
        gc.collect()
        final_objects = len(gc.get_objects())
        memory_growth = final_objects - initial_objects

        # Memory growth should be reasonable
        self.assertLess(memory_growth, 5000, f"Excessive memory growth under attack: {memory_growth} objects")

    def test_regex_catastrophic_backtracking_prevention(self):
        """Test prevention of ReDoS (Regular Expression Denial of Service)."""
        # Payloads designed to trigger catastrophic backtracking in poorly written regex
        redos_payloads = [
            # Alternation with repetition
            "a" * 50 + "X",

            # Nested quantifiers
            "(" + "a" * 30 + ")*",

            # Exponential blowup patterns
            "a" * 25 + "b",
            "x" * 40 + "y",

            # Complex nested groups
            "((a+)+)+b",
        ]

        for payload in redos_payloads:
            start_time = time.time()

            # Wrap in potential XSS context
            xss_payload = f"<script>{payload}</script>"

            try:
                is_xss = self.middleware._is_xss_attempt(xss_payload)
                processing_time = time.time() - start_time

                # Should complete quickly regardless of regex complexity
                self.assertLess(processing_time, 0.5, f"Potential ReDoS detected: {processing_time:.3f}s for {payload[:20]}...")

            except (ValueError, TypeError, AttributeError, KeyError) as e:
                self.fail(f"Exception during ReDoS test: {e}")


class DOMBasedXSSTest(TestCase):
    """Test suite for DOM-based XSS pattern detection."""

    def setUp(self):
        """Set up test fixtures."""
        self.middleware = XSSProtectionMiddleware()

    def test_dom_sink_detection(self):
        """Test detection of DOM XSS sinks."""
        dom_sinks = [
            # Common DOM sinks
            "document.write('user_input')",
            "element.innerHTML = user_data",
            "element.outerHTML = payload",
            "eval(user_input)",
            "setTimeout(user_code, 1000)",
            "setInterval(malicious_code, 500)",

            # jQuery sinks
            "$('#element').html(user_input)",
            "$('.class').append(payload)",

            # Location manipulation
            "window.location = user_url",
            "location.href = user_input",
            "location.replace(payload)",

            # Dynamic script creation
            "document.createElement('script').src = user_url",
            "script.text = user_code",
        ]

        for sink in dom_sinks:
            is_xss = self.middleware._is_xss_attempt(sink)
            # Should detect DOM manipulation patterns
            if any(pattern in sink.lower() for pattern in ['document.write', 'innerhtml', 'eval', 'settimeout']):
                self.assertTrue(is_xss, f"Failed to detect DOM XSS sink: {sink}")

    def test_dom_source_detection(self):
        """Test detection of DOM XSS sources."""
        dom_sources = [
            # URL-based sources
            "window.location.hash",
            "document.location.search",
            "location.pathname",
            "document.URL",
            "document.referrer",

            # Form-based sources
            "document.forms[0].elements[0].value",
            "input.value",

            # Storage sources
            "localStorage.getItem('key')",
            "sessionStorage.getItem('data')",

            # Message sources
            "event.data",
            "message.origin",
        ]

        for source in dom_sources:
            # Sources themselves aren't necessarily XSS, but should be recognized
            is_source = any(pattern in source.lower() for pattern in
                          ['location', 'document.', 'localstorage', 'sessionstorage'])
            self.assertTrue(is_source, f"Failed to recognize DOM source: {source}")


@pytest.mark.security
class XSSProtectionIntegrationTest(TestCase):
    """Integration tests for complete XSS protection system."""

    def setUp(self):
        """Set up test fixtures."""
        self.factory = RequestFactory()
        self.middleware = XSSProtectionMiddleware()

    def test_end_to_end_xss_protection(self):
        """Test complete end-to-end XSS protection workflow."""
        # Simulate real-world attack scenario
        attack_vectors = [
            ("search", "<script>alert('search_xss')</script>"),
            ("comment", "<img src=x onerror=alert('comment_xss')>"),
            ("username", "javascript:alert('username_xss')"),
            ("url", "data:text/html,<script>alert('url_xss')</script>"),
        ]

        for param_name, attack_payload in attack_vectors:
            # Create request with XSS payload
            request = self.factory.get(f'/?{param_name}={attack_payload}')

            # Process through XSS middleware
            response = self.middleware.process_request(request)

            # Verify XSS was detected and sanitized
            sanitized_value = request.GET.get(param_name)
            self.assertEqual(sanitized_value, '[SANITIZED]')

    def test_xss_protection_with_legitimate_content(self):
        """Test that legitimate content passes through XSS protection."""
        legitimate_inputs = [
            ("search", "python programming tutorial"),
            ("email", "user@example.com"),
            ("comment", "This is a great article! Thanks for sharing."),
            ("code", "function add(a, b) { return a + b; }"),  # Legitimate JavaScript code
            ("html", "<p>This is <strong>bold</strong> text.</p>"),  # Safe HTML
        ]

        for param_name, legitimate_content in legitimate_inputs:
            request = self.factory.get(f'/?{param_name}={legitimate_content}')

            response = self.middleware.process_request(request)

            # Should pass through without modification
            self.assertIsNone(response)  # No blocking response
            self.assertEqual(request.GET.get(param_name), legitimate_content)

    def test_xss_protection_performance_benchmark(self):
        """Benchmark XSS protection performance."""
        # Mix of legitimate and malicious payloads
        test_payloads = [
            "legitimate content",
            "<script>alert('xss')</script>",
            "user@example.com",
            "<img src=x onerror=alert(1)>",
            "normal search query",
            "javascript:alert(1)",
        ] * 100  # 600 total requests

        start_time = time.time()

        for i, payload in enumerate(test_payloads):
            request = self.factory.get(f'/?param{i % 10}={payload}')
            self.middleware.process_request(request)

        total_time = time.time() - start_time
        avg_time = total_time / len(test_payloads)

        # Performance should be reasonable
        self.assertLess(avg_time, 0.01, f"XSS protection too slow: {avg_time:.6f}s per request")
        self.assertLess(total_time, 5.0, f"Total processing time too long: {total_time:.3f}s")

    def test_xss_protection_under_concurrent_load(self):
        """Test XSS protection under concurrent request load."""
        import threading
        import queue

        results = queue.Queue()
        errors = queue.Queue()

        def concurrent_xss_test(thread_id):
            try:
                payloads = [
                    f"legitimate_content_{thread_id}",
                    f"<script>alert('xss_{thread_id}')</script>",
                    f"<img src=x onerror=alert('{thread_id}')>",
                    f"user{thread_id}@example.com",
                ]

                for i, payload in enumerate(payloads):
                    request = self.factory.get(f'/?param={payload}')
                    response = self.middleware.process_request(request)

                    # Verify appropriate handling
                    if any(xss in payload.lower() for xss in ['<script', '<img', 'onerror']):
                        # Should be sanitized
                        sanitized = request.GET.get('param')
                        if sanitized != '[SANITIZED]':
                            errors.put(f"Thread {thread_id}: XSS not sanitized: {payload}")
                            return

                results.put(f"thread_{thread_id}_success")

            except (ValueError, TypeError, AttributeError, KeyError) as e:
                errors.put(f"Thread {thread_id}: {str(e)}")

        # Create multiple concurrent threads
        threads = []
        for i in range(5):
            thread = threading.Thread(target=concurrent_xss_test, args=(i,))
            threads.append(thread)
            thread.start()

        for thread in threads:
            thread.join()

        # Check results
        self.assertTrue(errors.empty(), f"Concurrent XSS protection errors: {list(errors.queue)}")

        successful_threads = []
        while not results.empty():
            successful_threads.append(results.get())

        self.assertEqual(len(successful_threads), 5, "All concurrent XSS tests should succeed")