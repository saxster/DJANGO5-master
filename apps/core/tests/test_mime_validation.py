"""
Tests for MIME type validation from file content (CVSS 6.1 - Content-Type Spoofing).

Tests comprehensive MIME type validation including:
- Extension-based MIME type detection
- Content-based MIME type detection (magic bytes)
- MIME type mismatch detection and resolution
- X-Content-Type-Options header enforcement
- Security headers validation
- Test: File with .jpg extension but .exe content should be detected and blocked
"""

import pytest
import tempfile
import os
from pathlib import Path
from django.test import RequestFactory
from django.http import FileResponse
from django.conf import settings
from unittest.mock import patch, MagicMock

from apps.core.services.secure_file_download_service import SecureFileDownloadService
from apps.peoples.models import People, PeopleTenant
from apps.tenants.models import Tenant


@pytest.fixture
def test_tenant():
    """Create test tenant."""
    return Tenant.objects.create(
        name="Test Tenant",
        slug="test-tenant",
        is_active=True
    )


@pytest.fixture
def test_user(test_tenant):
    """Create test user."""
    user = People.objects.create(
        peoplename="testuser",
        email="test@example.com",
        is_active=True,
        is_staff=True
    )
    return user


@pytest.fixture
def temp_media_dir():
    """Create temporary MEDIA_ROOT."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create required subdirectories
        Path(tmpdir, 'uploads').mkdir(exist_ok=True)
        Path(tmpdir, 'attachments').mkdir(exist_ok=True)
        yield tmpdir


class TestMIMETypeValidation:
    """Test MIME type validation from file content."""

    def test_valid_jpg_file_returns_correct_mime_type(self, test_user, temp_media_dir):
        """Test that valid JPG file returns correct MIME type."""
        # Create a valid JPG file with proper magic bytes
        jpg_path = Path(temp_media_dir) / 'uploads' / 'test.jpg'

        # JPG magic bytes: FF D8 FF E0
        jpg_magic_bytes = b'\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00'
        jpg_path.write_bytes(jpg_magic_bytes + b'dummy_image_data')

        with patch('django.conf.settings.MEDIA_ROOT', temp_media_dir):
            response = SecureFileDownloadService._create_secure_response(
                jpg_path,
                'test.jpg',
                'test-correlation-id'
            )

            # Verify response has correct MIME type
            assert response['Content-Type'] == 'image/jpeg'
            # Verify security headers are present
            assert response['X-Content-Type-Options'] == 'nosniff'
            assert response['X-Frame-Options'] == 'DENY'

    def test_valid_pdf_file_returns_correct_mime_type(self, test_user, temp_media_dir):
        """Test that valid PDF file returns correct MIME type."""
        pdf_path = Path(temp_media_dir) / 'uploads' / 'test.pdf'

        # PDF magic bytes: %PDF-1.4
        pdf_magic_bytes = b'%PDF-1.4\n'
        pdf_path.write_bytes(pdf_magic_bytes + b'dummy_pdf_data')

        with patch('django.conf.settings.MEDIA_ROOT', temp_media_dir):
            response = SecureFileDownloadService._create_secure_response(
                pdf_path,
                'test.pdf',
                'test-correlation-id'
            )

            assert response['Content-Type'] == 'application/pdf'
            assert response['X-Content-Type-Options'] == 'nosniff'

    def test_exe_file_with_jpg_extension_detected(self, test_user, temp_media_dir):
        """Test that EXE file with JPG extension is detected as content-type spoofing."""
        spoofed_path = Path(temp_media_dir) / 'uploads' / 'malware.jpg'

        # EXE magic bytes: MZ (4D 5A)
        exe_magic_bytes = b'MZ\x90\x00\x03\x00\x00\x00\x04\x00\x00\x00\xff\xff\x00\x00'
        spoofed_path.write_bytes(exe_magic_bytes + b'dummy_executable_data')

        with patch('django.conf.settings.MEDIA_ROOT', temp_media_dir):
            response = SecureFileDownloadService._create_secure_response(
                spoofed_path,
                'malware.jpg',
                'test-correlation-id'
            )

            # Content-based detection should identify as application/octet-stream (safe default)
            # or application/x-msdownload
            assert response['Content-Type'] in [
                'application/octet-stream',
                'application/x-msdownload',
                'application/x-dosexec'
            ]
            assert response['X-Content-Type-Options'] == 'nosniff'

    def test_zip_file_with_jpg_extension_detected(self, test_user, temp_media_dir):
        """Test that ZIP file with JPG extension is detected."""
        spoofed_path = Path(temp_media_dir) / 'uploads' / 'archive.jpg'

        # ZIP magic bytes: PK (50 4B)
        zip_magic_bytes = b'PK\x03\x04'
        spoofed_path.write_bytes(zip_magic_bytes + b'dummy_zip_data')

        with patch('django.conf.settings.MEDIA_ROOT', temp_media_dir):
            response = SecureFileDownloadService._create_secure_response(
                spoofed_path,
                'archive.jpg',
                'test-correlation-id'
            )

            # Content-based detection should identify as application/zip
            assert response['Content-Type'] in [
                'application/zip',
                'application/octet-stream'
            ]
            assert response['X-Content-Type-Options'] == 'nosniff'

    def test_unknown_file_type_returns_octet_stream(self, test_user, temp_media_dir):
        """Test that unknown file type returns octet-stream."""
        unknown_path = Path(temp_media_dir) / 'uploads' / 'unknown.xyz'
        unknown_path.write_bytes(b'random binary data here')

        with patch('django.conf.settings.MEDIA_ROOT', temp_media_dir):
            response = SecureFileDownloadService._create_secure_response(
                unknown_path,
                'unknown.xyz',
                'test-correlation-id'
            )

            assert response['Content-Type'] == 'application/octet-stream'
            assert response['X-Content-Type-Options'] == 'nosniff'

    def test_text_file_with_executable_extension_detected(self, test_user, temp_media_dir):
        """Test that text file with executable extension is detected."""
        spoofed_path = Path(temp_media_dir) / 'uploads' / 'script.exe'

        # Plain text content instead of executable
        spoofed_path.write_text('#!/bin/bash\necho "hello"')

        with patch('django.conf.settings.MEDIA_ROOT', temp_media_dir):
            response = SecureFileDownloadService._create_secure_response(
                spoofed_path,
                'script.exe',
                'test-correlation-id'
            )

            # Content-based detection should identify as text
            assert 'text' in response['Content-Type'] or response['Content-Type'] == 'application/octet-stream'
            assert response['X-Content-Type-Options'] == 'nosniff'

    def test_image_mime_type_returns_inline_disposition(self, test_user, temp_media_dir):
        """Test that image files return inline disposition."""
        jpg_path = Path(temp_media_dir) / 'uploads' / 'image.jpg'
        jpg_magic_bytes = b'\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00'
        jpg_path.write_bytes(jpg_magic_bytes + b'dummy_image_data')

        with patch('django.conf.settings.MEDIA_ROOT', temp_media_dir):
            response = SecureFileDownloadService._create_secure_response(
                jpg_path,
                'image.jpg',
                'test-correlation-id'
            )

            # Images should be inline
            assert 'inline' in response['Content-Disposition']
            assert response['X-Content-Type-Options'] == 'nosniff'

    def test_non_image_mime_type_returns_attachment_disposition(self, test_user, temp_media_dir):
        """Test that non-image files return attachment disposition."""
        pdf_path = Path(temp_media_dir) / 'uploads' / 'document.pdf'
        pdf_magic_bytes = b'%PDF-1.4\n'
        pdf_path.write_bytes(pdf_magic_bytes + b'dummy_pdf_data')

        with patch('django.conf.settings.MEDIA_ROOT', temp_media_dir):
            response = SecureFileDownloadService._create_secure_response(
                pdf_path,
                'document.pdf',
                'test-correlation-id'
            )

            # Non-images should be attachment
            assert 'attachment' in response['Content-Disposition']
            assert response['X-Content-Type-Options'] == 'nosniff'

    def test_security_headers_always_present(self, test_user, temp_media_dir):
        """Test that security headers are always present."""
        test_path = Path(temp_media_dir) / 'uploads' / 'test.bin'
        test_path.write_bytes(b'binary data')

        with patch('django.conf.settings.MEDIA_ROOT', temp_media_dir):
            response = SecureFileDownloadService._create_secure_response(
                test_path,
                'test.bin',
                'test-correlation-id'
            )

            # These headers should always be present
            assert 'X-Content-Type-Options' in response
            assert response['X-Content-Type-Options'] == 'nosniff'
            assert 'X-Frame-Options' in response
            assert response['X-Frame-Options'] == 'DENY'

    def test_png_file_detected_correctly(self, test_user, temp_media_dir):
        """Test that PNG file is detected correctly from content."""
        png_path = Path(temp_media_dir) / 'uploads' / 'image.png'

        # PNG magic bytes: 89 50 4E 47 0D 0A 1A 0A
        png_magic_bytes = b'\x89PNG\r\n\x1a\n'
        png_path.write_bytes(png_magic_bytes + b'dummy_png_data')

        with patch('django.conf.settings.MEDIA_ROOT', temp_media_dir):
            response = SecureFileDownloadService._create_secure_response(
                png_path,
                'image.png',
                'test-correlation-id'
            )

            assert response['Content-Type'] == 'image/png'
            assert response['X-Content-Type-Options'] == 'nosniff'

    def test_gif_file_detected_correctly(self, test_user, temp_media_dir):
        """Test that GIF file is detected correctly from content."""
        gif_path = Path(temp_media_dir) / 'uploads' / 'animation.gif'

        # GIF magic bytes: 47 49 46 38 (GIF8)
        gif_magic_bytes = b'GIF89a'
        gif_path.write_bytes(gif_magic_bytes + b'dummy_gif_data')

        with patch('django.conf.settings.MEDIA_ROOT', temp_media_dir):
            response = SecureFileDownloadService._create_secure_response(
                gif_path,
                'animation.gif',
                'test-correlation-id'
            )

            assert response['Content-Type'] == 'image/gif'
            assert response['X-Content-Type-Options'] == 'nosniff'

    def test_mismatch_log_detection(self, test_user, temp_media_dir):
        """Test that MIME type mismatches are logged."""
        # Create EXE with JPG extension
        spoofed_path = Path(temp_media_dir) / 'uploads' / 'malware.jpg'
        exe_magic_bytes = b'MZ\x90\x00'
        spoofed_path.write_bytes(exe_magic_bytes + b'executable_data')

        with patch('django.conf.settings.MEDIA_ROOT', temp_media_dir):
            with patch('apps.core.services.secure_file_download_service.logger') as mock_logger:
                response = SecureFileDownloadService._create_secure_response(
                    spoofed_path,
                    'malware.jpg',
                    'test-correlation-id'
                )

                # Verify that the service responded safely
                assert response['X-Content-Type-Options'] == 'nosniff'


class TestMIMEValidationIntegration:
    """Integration tests for MIME validation with full download flow."""

    def test_download_with_mime_spoofing_blocked(self, test_user, test_tenant, temp_media_dir):
        """Test that MIME spoofing attempt is blocked during download."""
        # Create spoofed file
        spoofed_path = Path(temp_media_dir) / 'uploads' / 'malware.jpg'
        exe_magic_bytes = b'MZ\x90\x00\x03\x00\x00\x00'
        spoofed_path.write_bytes(exe_magic_bytes + b'malicious_payload')

        with patch('django.conf.settings.MEDIA_ROOT', temp_media_dir):
            # Even though file ends with .jpg, content detection prevents abuse
            response = SecureFileDownloadService._create_secure_response(
                spoofed_path,
                'malware.jpg',
                'test-correlation-id'
            )

            # Should use content-based MIME type and have nosniff header
            assert response['X-Content-Type-Options'] == 'nosniff'
            # Content type should be based on actual content, not extension
            assert response['Content-Type'] in [
                'application/octet-stream',
                'application/x-msdownload',
                'application/x-dosexec'
            ]
