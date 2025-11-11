"""
Security Tests for AI Testing Views
Tests for CRLF injection, header injection, and file download security
"""

import pytest
from django.test import TestCase, Client, RequestFactory
from django.contrib.auth import get_user_model
from django.urls import reverse
from apps.ai_testing.models import TestCoverageGap
from apps.issue_tracker.models import AnomalySignature
from apps.tenants.models import Tenant
from apps.ai_testing import views

User = get_user_model()


@pytest.mark.django_db
class TestFileDownloadSecurity(TestCase):
    """Test security of file download functionality"""

    def setUp(self):
        """Set up test data"""
        # Create tenant (required for multi-tenant architecture)
        self.tenant = Tenant.objects.create(
            tenantname="Test Tenant",
            subdomain_prefix="test"
        )

        # Create staff user
        self.user = User.objects.create_user(
            loginid='testuser',
            password='testpass123',
            email='test@example.com',
            first_name='Test',
            last_name='User',
            is_staff=True,
            tenant=self.tenant
        )
        # Use RequestFactory to bypass middleware
        self.factory = RequestFactory()

        # Create anomaly signature (required FK for TestCoverageGap)
        self.anomaly = AnomalySignature.objects.create(
            signature_hash='test_hash_123',
            anomaly_type='error',
            severity='error',
            endpoint_pattern='/api/test/',
            pattern={'error_class': 'RuntimeError'},
            occurrence_count=5
        )

    def test_crlf_injection_prevented(self):
        """
        Test that CRLF characters in gap.title cannot inject HTTP headers

        Attack vector: gap.title with embedded \r\n should not create new headers
        Expected: Sanitized filename without CRLF characters
        """
        # Create gap with malicious title containing CRLF
        malicious_title = "legitimate_test\r\nX-Injected-Header: malicious\r\nContent-Type: text/html\r\n"

        gap = TestCoverageGap.objects.create(
            coverage_type='functional',
            title=malicious_title,
            description='Test gap for CRLF injection',
            anomaly_signature=self.anomaly,
            priority='high',
            confidence_score=0.9,
            impact_score=8.0,
            recommended_framework='junit',
            auto_generated_test_code='// Test code here'
        )

        # Create request and call view directly (bypassing middleware)
        request = self.factory.get(
            '/streamlab/ai/test-generation/download/',
            {'gap_id': str(gap.id), 'framework': 'junit'}
        )
        request.user = self.user

        # Call view directly
        response = views.download_generated_test(request)

        # Verify response is successful
        self.assertEqual(response.status_code, 200)

        # CRITICAL: Verify NO injected headers present
        # The key security check: X-Injected-Header should not be a separate header
        self.assertNotIn('X-Injected-Header', response)

        # Verify Content-Disposition header exists and is safe
        content_disposition = response.get('Content-Disposition', '')
        self.assertTrue(content_disposition.startswith('attachment; filename='))

        # CRITICAL SECURITY CHECK: Verify filename does NOT contain CRLF characters
        # CRLF removal prevents header injection attacks
        self.assertNotIn('\r', content_disposition)
        self.assertNotIn('\n', content_disposition)

        # Verify only ONE Content-Type header (not overridden by injection)
        self.assertEqual(response.get('Content-Type'), 'text/plain')

        # Verify serialized headers don't contain newlines (header injection prevention)
        headers_str = str(response.serialize_headers())
        # Should only contain protocol CRLF separators, not injected ones
        # Check that there's no double-CRLF or injected header names
        self.assertNotIn('X-Injected-Header:', headers_str.replace('\\r\\n', '\n'))

    def test_newline_variations_sanitized(self):
        """Test that all newline variations are sanitized"""
        test_cases = [
            ("test\rtitle", "Carriage return"),
            ("test\ntitle", "Line feed"),
            ("test\r\ntitle", "CRLF"),
            ("test\x00title", "Null byte"),
            ("test\ttitle", "Tab character"),
        ]

        for malicious_title, description in test_cases:
            with self.subTest(description=description):
                gap = TestCoverageGap.objects.create(
                    coverage_type='functional',
                    title=malicious_title,
                    description=f'Test gap for {description}',
                    anomaly_signature=self.anomaly,
                    priority='high',
                    confidence_score=0.9,
                    impact_score=8.0,
                    recommended_framework='junit',
                    auto_generated_test_code='// Test code'
                )

                request = self.factory.get(
                    '/streamlab/ai/test-generation/download/',
                    {'gap_id': str(gap.id), 'framework': 'junit'}
                )
                request.user = self.user
                response = views.download_generated_test(request)

                content_disposition = response.get('Content-Disposition', '')

                # Verify no control characters in filename
                self.assertNotIn('\r', content_disposition)
                self.assertNotIn('\n', content_disposition)
                self.assertNotIn('\x00', content_disposition)

    def test_quote_escaping_prevented(self):
        """Test that quote characters cannot break filename syntax"""
        malicious_titles = [
            'test"filename',
            "test'filename",
            'test\\"escaped',
            'test"; echo "hacked',
        ]

        for malicious_title in malicious_titles:
            with self.subTest(title=malicious_title):
                gap = TestCoverageGap.objects.create(
                    coverage_type='functional',
                    title=malicious_title,
                    description='Test gap for quote escaping',
                    anomaly_signature=self.anomaly,
                    priority='high',
                    confidence_score=0.9,
                    impact_score=8.0,
                    recommended_framework='junit',
                    auto_generated_test_code='// Test code'
                )

                request = self.factory.get(
                    '/streamlab/ai/test-generation/download/',
                    {'gap_id': str(gap.id), 'framework': 'junit'}
                )
                request.user = self.user
                response = views.download_generated_test(request)

                content_disposition = response.get('Content-Disposition', '')

                # Extract just the filename value (between quotes)
                filename_part = content_disposition.split('filename=')[1].strip('"')

                # Verify quotes from original malicious input are removed
                # (not talking about the protocol quotes around filename)
                self.assertNotIn('"', filename_part)  # No internal quotes
                self.assertNotIn("'", filename_part)  # No single quotes
                self.assertNotIn('\\"', content_disposition)  # No escaped quotes

    def test_path_traversal_prevented(self):
        """Test that path traversal attempts are sanitized"""
        malicious_titles = [
            '../../../etc/passwd',
            '..\\..\\..\\windows\\system32',
            'test/../../../sensitive',
            '....//....//....//etc',
        ]

        for malicious_title in malicious_titles:
            with self.subTest(title=malicious_title):
                gap = TestCoverageGap.objects.create(
                    coverage_type='functional',
                    title=malicious_title,
                    description='Test gap for path traversal',
                    anomaly_signature=self.anomaly,
                    priority='high',
                    confidence_score=0.9,
                    impact_score=8.0,
                    recommended_framework='junit',
                    auto_generated_test_code='// Test code'
                )

                request = self.factory.get(
                    '/streamlab/ai/test-generation/download/',
                    {'gap_id': str(gap.id), 'framework': 'junit'}
                )
                request.user = self.user
                response = views.download_generated_test(request)

                content_disposition = response.get('Content-Disposition', '')
                filename = content_disposition.split('filename=')[1].strip('"')

                # Verify no directory traversal sequences
                self.assertNotIn('..', filename)
                self.assertNotIn('/', filename)
                self.assertNotIn('\\', filename)

    def test_non_ascii_unicode_sanitized(self):
        """Test that non-ASCII and Unicode characters are handled safely"""
        test_titles = [
            'test_中文_title',  # Chinese characters
            'test_файл_title',  # Cyrillic
            'test_🔥_emoji',    # Emoji
            'test_\u202e_rtl',  # Right-to-left override (invisible char)
        ]

        for title in test_titles:
            with self.subTest(title=title):
                gap = TestCoverageGap.objects.create(
                    coverage_type='functional',
                    title=title,
                    description='Test gap for Unicode',
                    anomaly_signature=self.anomaly,
                    priority='high',
                    confidence_score=0.9,
                    impact_score=8.0,
                    recommended_framework='junit',
                    auto_generated_test_code='// Test code'
                )

                request = self.factory.get(
                    '/streamlab/ai/test-generation/download/',
                    {'gap_id': str(gap.id), 'framework': 'junit'}
                )
                request.user = self.user
                response = views.download_generated_test(request)

                content_disposition = response.get('Content-Disposition', '')
                filename = content_disposition.split('filename=')[1].strip('"')

                # Verify only ASCII characters remain
                self.assertTrue(all(ord(c) < 128 for c in filename))

    def test_legitimate_filenames_work(self):
        """Test that legitimate filenames are preserved correctly"""
        legitimate_titles = [
            'User Authentication Test',
            'API_Response_Validation',
            'network-timeout-handling',
            'Test123',
        ]

        for title in legitimate_titles:
            with self.subTest(title=title):
                gap = TestCoverageGap.objects.create(
                    coverage_type='functional',
                    title=title,
                    description='Legitimate test gap',
                    anomaly_signature=self.anomaly,
                    priority='high',
                    confidence_score=0.9,
                    impact_score=8.0,
                    recommended_framework='junit',
                    auto_generated_test_code='// Test code'
                )

                request = self.factory.get(
                    '/streamlab/ai/test-generation/download/',
                    {'gap_id': str(gap.id), 'framework': 'junit'}
                )
                request.user = self.user
                response = views.download_generated_test(request)

                self.assertEqual(response.status_code, 200)
                content_disposition = response.get('Content-Disposition', '')

                # Verify Content-Disposition header is properly formed
                self.assertTrue(content_disposition.startswith('attachment; filename='))
                self.assertIn('.kt', content_disposition)

    def test_empty_title_fallback(self):
        """Test that empty or whitespace-only titles get safe fallback"""
        test_titles = ['', '   ', '\t\t', '\n\n']

        for title in test_titles:
            with self.subTest(title=repr(title)):
                gap = TestCoverageGap.objects.create(
                    coverage_type='functional',
                    title=title,
                    description='Test gap with empty title',
                    anomaly_signature=self.anomaly,
                    priority='high',
                    confidence_score=0.9,
                    impact_score=8.0,
                    recommended_framework='junit',
                    auto_generated_test_code='// Test code'
                )

                request = self.factory.get(
                    '/streamlab/ai/test-generation/download/',
                    {'gap_id': str(gap.id), 'framework': 'junit'}
                )
                request.user = self.user
                response = views.download_generated_test(request)

                self.assertEqual(response.status_code, 200)
                content_disposition = response.get('Content-Disposition', '')

                # Should have valid filename (either test_functional_.kt or download.txt fallback)
                # The important thing is no crash and filename is safe
                self.assertTrue(content_disposition.startswith('attachment; filename='))
                self.assertNotIn('\r', content_disposition)
                self.assertNotIn('\n', content_disposition)

    def test_excessive_length_truncated(self):
        """Test that overly long filenames are truncated"""
        long_title = 'A' * 500  # 500 characters

        gap = TestCoverageGap.objects.create(
            coverage_type='functional',
            title=long_title,
            description='Test gap with long title',
            anomaly_signature=self.anomaly,
            priority='high',
            confidence_score=0.9,
            impact_score=8.0,
            recommended_framework='junit',
            auto_generated_test_code='// Test code'
        )

        request = self.factory.get(
            '/streamlab/ai/test-generation/download/',
            {'gap_id': str(gap.id), 'framework': 'junit'}
        )
        request.user = self.user
        response = views.download_generated_test(request)

        content_disposition = response.get('Content-Disposition', '')
        filename = content_disposition.split('filename=')[1].strip('"')

        # Verify filename is truncated to reasonable length (max 200 chars + extension)
        self.assertLess(len(filename), 250)

    def test_preview_endpoint_not_vulnerable(self):
        """
        Test that preview_generated_test() endpoint is not vulnerable
        (returns JSON, not Content-Disposition header)
        """
        malicious_title = "test\r\nX-Injected: malicious"

        gap = TestCoverageGap.objects.create(
            coverage_type='functional',
            title=malicious_title,
            description='Test gap for preview',
            anomaly_signature=self.anomaly,
            priority='high',
            confidence_score=0.9,
            impact_score=8.0,
            recommended_framework='junit',
            auto_generated_test_code='// Test code here'
        )

        request = self.factory.get(
            '/streamlab/ai/test-generation/preview/',
            {'gap_id': str(gap.id), 'framework': 'junit'}
        )
        request.user = self.user
        response = views.preview_generated_test(request)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get('Content-Type'), 'application/json')

        # Verify NO Content-Disposition header (JSON response)
        self.assertIsNone(response.get('Content-Disposition'))

        # Verify no injected headers
        self.assertNotIn('X-Injected', response)
