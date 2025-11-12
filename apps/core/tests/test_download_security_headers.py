"""
Tests for Content-Security-Policy and other security headers in file downloads.

This test suite verifies that CSP and related security headers are properly set
on file download responses to prevent XSS vulnerabilities in SVG/HTML files.

Coverage areas:
- Content-Security-Policy header correctness
- X-Download-Options: noopen header
- X-Permitted-Cross-Domain-Policies: none header
- X-Content-Type-Options: nosniff header
- X-Frame-Options: DENY header
- Headers on different file types (images, documents, SVG, HTML)
"""

import pytest
from pathlib import Path
from django.conf import settings
from django.test import RequestFactory
from django.http import FileResponse
from unittest.mock import Mock, patch, MagicMock

from apps.core.services.secure_file_download_service import SecureFileDownloadService


@pytest.mark.django_db
class TestCSPHeadersOnDownload:
    """Test Content-Security-Policy headers on file downloads."""

    def test_csp_header_present_on_response(self):
        """Test CSP header is present in file download response."""
        # Create a temporary SVG file with XSS vulnerability
        svg_content = '''<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="100" height="100">
    <script>alert('XSS')</script>
    <rect width="100" height="100" fill="red"/>
</svg>'''

        media_path = Path(settings.MEDIA_ROOT) / 'uploads' / 'test_csp.svg'
        media_path.parent.mkdir(parents=True, exist_ok=True)
        media_path.write_text(svg_content)

        try:
            # Create mock user
            user = Mock()
            user.id = 1
            user.is_authenticated = True
            user.is_staff = True

            # Call the secure response creation directly
            response = SecureFileDownloadService._create_secure_response(
                file_path=media_path,
                original_filename='test.svg',
                correlation_id='test-123'
            )

            # Verify CSP header is present
            assert 'Content-Security-Policy' in response
            csp = response['Content-Security-Policy']
            assert csp is not None
            assert len(csp) > 0

        finally:
            if media_path.exists():
                media_path.unlink()

    def test_csp_header_disables_scripts(self):
        """Test CSP header disables script execution."""
        html_content = '''<!DOCTYPE html>
<html>
<head><title>Test</title></head>
<body>
    <script>alert('XSS')</script>
    <h1>Test</h1>
</body>
</html>'''

        media_path = Path(settings.MEDIA_ROOT) / 'uploads' / 'test_html.html'
        media_path.parent.mkdir(parents=True, exist_ok=True)
        media_path.write_text(html_content)

        try:
            response = SecureFileDownloadService._create_secure_response(
                file_path=media_path,
                original_filename='test.html',
                correlation_id='test-123'
            )

            csp = response['Content-Security-Policy']
            # Should contain script-src 'none' or similar restrictive directive
            assert 'script-src' in csp.lower(), "CSP should disable script execution"
            assert "'none'" in csp.lower(), "Script src should be 'none'"

        finally:
            if media_path.exists():
                media_path.unlink()

    def test_csp_header_comprehensive_directives(self):
        """Test CSP includes multiple security directives."""
        text_content = "Plain text file"

        media_path = Path(settings.MEDIA_ROOT) / 'uploads' / 'test_txt.txt'
        media_path.parent.mkdir(parents=True, exist_ok=True)
        media_path.write_text(text_content)

        try:
            response = SecureFileDownloadService._create_secure_response(
                file_path=media_path,
                original_filename='test.txt',
                correlation_id='test-123'
            )

            csp = response['Content-Security-Policy']
            csp_lower = csp.lower()

            # Verify multiple directives are present
            expected_directives = [
                'default-src',
                'script-src',
                'style-src',
                'img-src',
                'font-src',
                'connect-src',
                'media-src',
                'object-src',
                'frame-ancestors',
            ]

            # At least some of these directives should be present
            found_directives = [d for d in expected_directives if d in csp_lower]
            assert len(found_directives) > 5, \
                f"Expected multiple security directives, found {len(found_directives)}: {found_directives}"

        finally:
            if media_path.exists():
                media_path.unlink()


@pytest.mark.django_db
class TestAdditionalSecurityHeaders:
    """Test other security headers preventing file-based XSS."""

    def test_x_download_options_header(self):
        """Test X-Download-Options: noopen header prevents IE file opening."""
        html_content = "<html><body><script>alert('XSS')</script></body></html>"

        media_path = Path(settings.MEDIA_ROOT) / 'uploads' / 'test_xdo.html'
        media_path.parent.mkdir(parents=True, exist_ok=True)
        media_path.write_text(html_content)

        try:
            response = SecureFileDownloadService._create_secure_response(
                file_path=media_path,
                original_filename='test.html',
                correlation_id='test-123'
            )

            assert 'X-Download-Options' in response
            assert response['X-Download-Options'] == 'noopen'

        finally:
            if media_path.exists():
                media_path.unlink()

    def test_x_permitted_cross_domain_policies_header(self):
        """Test X-Permitted-Cross-Domain-Policies: none header."""
        svg_content = '<svg><script>alert("XSS")</script></svg>'

        media_path = Path(settings.MEDIA_ROOT) / 'uploads' / 'test_xpcdp.svg'
        media_path.parent.mkdir(parents=True, exist_ok=True)
        media_path.write_text(svg_content)

        try:
            response = SecureFileDownloadService._create_secure_response(
                file_path=media_path,
                original_filename='test.svg',
                correlation_id='test-123'
            )

            assert 'X-Permitted-Cross-Domain-Policies' in response
            assert response['X-Permitted-Cross-Domain-Policies'] == 'none'

        finally:
            if media_path.exists():
                media_path.unlink()

    def test_x_content_type_options_header_present(self):
        """Test X-Content-Type-Options: nosniff header prevents MIME sniffing."""
        # Create minimal valid PDF structure
        pdf_content = b'''%PDF-1.4
1 0 obj
<< /Type /Catalog /Pages 2 0 R >>
endobj
xref
0 1
0000000000 65535 f
trailer
<< /Size 1 /Root 1 0 R >>
startxref
44
%%EOF'''

        media_path = Path(settings.MEDIA_ROOT) / 'uploads' / 'test_xcto.pdf'
        media_path.parent.mkdir(parents=True, exist_ok=True)
        media_path.write_bytes(pdf_content)

        try:
            response = SecureFileDownloadService._create_secure_response(
                file_path=media_path,
                original_filename='test.pdf',
                correlation_id='test-123'
            )

            assert 'X-Content-Type-Options' in response
            assert response['X-Content-Type-Options'] == 'nosniff'

        finally:
            if media_path.exists():
                media_path.unlink()

    def test_x_frame_options_header_present(self):
        """Test X-Frame-Options: DENY header prevents clickjacking."""
        # Create minimal valid PNG file (1x1 pixel transparent)
        png_data = b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82'

        media_path = Path(settings.MEDIA_ROOT) / 'uploads' / 'test_xfo.png'
        media_path.parent.mkdir(parents=True, exist_ok=True)
        media_path.write_bytes(png_data)

        try:
            response = SecureFileDownloadService._create_secure_response(
                file_path=media_path,
                original_filename='test.png',
                correlation_id='test-123'
            )

            assert 'X-Frame-Options' in response
            assert response['X-Frame-Options'] == 'DENY'

        finally:
            if media_path.exists():
                media_path.unlink()

    def test_all_security_headers_together(self):
        """Test all security headers are present together."""
        svg_content = '<svg><rect/></svg>'

        media_path = Path(settings.MEDIA_ROOT) / 'uploads' / 'test_all_headers.svg'
        media_path.parent.mkdir(parents=True, exist_ok=True)
        media_path.write_text(svg_content)

        try:
            response = SecureFileDownloadService._create_secure_response(
                file_path=media_path,
                original_filename='test.svg',
                correlation_id='test-123'
            )

            # Verify all security headers
            required_headers = {
                'Content-Security-Policy': str,
                'X-Download-Options': 'noopen',
                'X-Permitted-Cross-Domain-Policies': 'none',
                'X-Content-Type-Options': 'nosniff',
                'X-Frame-Options': 'DENY',
            }

            for header_name, expected_value in required_headers.items():
                assert header_name in response, f"Missing header: {header_name}"

                if expected_value != str:
                    assert response[header_name] == expected_value, \
                        f"Header {header_name} has unexpected value: {response[header_name]}"

        finally:
            if media_path.exists():
                media_path.unlink()


@pytest.mark.django_db
class TestCSPPreventionEffectiveness:
    """Test that CSP headers effectively prevent common XSS attacks in files."""

    def test_svg_script_blocked_by_csp(self):
        """Test that SVG with embedded script is blocked by CSP."""
        svg_content = '''<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" onload="alert('XSS')">
    <script>var x = 1;</script>
    <rect width="100" height="100" fill="red"/>
</svg>'''

        media_path = Path(settings.MEDIA_ROOT) / 'uploads' / 'test_svg_xss.svg'
        media_path.parent.mkdir(parents=True, exist_ok=True)
        media_path.write_text(svg_content)

        try:
            response = SecureFileDownloadService._create_secure_response(
                file_path=media_path,
                original_filename='test.svg',
                correlation_id='test-123'
            )

            # The response should have CSP that disables scripts
            csp = response['Content-Security-Policy']
            assert 'script-src' in csp.lower(), "CSP should restrict script-src"

        finally:
            if media_path.exists():
                media_path.unlink()

    def test_html_script_blocked_by_csp(self):
        """Test that HTML with embedded script is blocked by CSP."""
        html_content = '''<!DOCTYPE html>
<html>
<head><title>Test</title></head>
<body onload="alert('XSS')">
    <script src="http://evil.com/malware.js"></script>
    <h1>Test</h1>
</body>
</html>'''

        media_path = Path(settings.MEDIA_ROOT) / 'uploads' / 'test_html_xss.html'
        media_path.parent.mkdir(parents=True, exist_ok=True)
        media_path.write_text(html_content)

        try:
            response = SecureFileDownloadService._create_secure_response(
                file_path=media_path,
                original_filename='test.html',
                correlation_id='test-123'
            )

            # The response should have CSP that disables scripts
            csp = response['Content-Security-Policy']
            assert 'script-src' in csp.lower(), "CSP should restrict script-src"

        finally:
            if media_path.exists():
                media_path.unlink()

    def test_csp_prevents_external_resource_loading(self):
        """Test CSP prevents loading external resources."""
        html_content = '''<!DOCTYPE html>
<html>
<head>
    <link rel="stylesheet" href="http://evil.com/malicious.css"/>
    <script src="http://evil.com/malware.js"></script>
</head>
<body>
    <img src="http://evil.com/track.gif"/>
</body>
</html>'''

        media_path = Path(settings.MEDIA_ROOT) / 'uploads' / 'test_external.html'
        media_path.parent.mkdir(parents=True, exist_ok=True)
        media_path.write_text(html_content)

        try:
            response = SecureFileDownloadService._create_secure_response(
                file_path=media_path,
                original_filename='test.html',
                correlation_id='test-123'
            )

            csp = response['Content-Security-Policy']
            csp_lower = csp.lower()

            # Should have restrictive directives
            assert any(d in csp_lower for d in ['connect-src', 'style-src', 'font-src', 'default-src']), \
                "CSP should restrict external resource loading"

        finally:
            if media_path.exists():
                media_path.unlink()
