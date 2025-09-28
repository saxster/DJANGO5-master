"""
Comprehensive Path Traversal Vulnerability Tests

Tests for CRITICAL vulnerabilities (CVSS 9.8):
1. upload_peopleimg() - File upload path traversal
2. write_file_to_dir() - Arbitrary file write
3. Download function - Arbitrary file read

These tests validate the security fixes and ensure no regressions.

Compliance: Validates Rule #14 from .claude/rules.md - File Upload Security
"""

import os
import tempfile
import pytest
from django.test import TestCase, override_settings
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, SuspiciousFileOperation
from django.http import Http404
from django.core.files.uploadedfile import SimpleUploadedFile
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

from apps.peoples.models import upload_peopleimg
from apps.service.utils import write_file_to_dir
from apps.core.services.secure_file_download_service import SecureFileDownloadService

User = get_user_model()


class PathTraversalUploadTests(TestCase):
    """Test suite for upload_peopleimg() path traversal prevention."""

    def setUp(self):
        """Set up test data."""
        from apps.onboarding.models import Bt

        self.user = User.objects.create(
            loginid='test_user',
            peoplecode='TEST001',
            peoplename='Test User',
            email='test@example.com',
            dateofbirth='1990-01-01'
        )

        # Create test client/business unit
        self.client_bu = Bt.objects.create(
            bucode='CLIENT001',
            buname='Test Client',
            butype='CLIENT'
        )

        self.user.client = self.client_bu
        self.user.save()

    def test_path_traversal_prevention_basic(self):
        """Test that basic path traversal attempts are blocked."""
        malicious_filenames = [
            '../../../etc/passwd',
            '..\\..\\..\\windows\\system32\\config\\sam',
            'file/../../etc/passwd',
            './../../sensitive_file.txt'
        ]

        for filename in malicious_filenames:
            result_path = upload_peopleimg(self.user, filename)

            # Should return safe path or default, NOT process traversal
            self.assertNotIn('..', result_path, f"Path traversal not prevented: {result_path}")
            self.assertNotIn('/etc/', result_path, f"Traversal to /etc/ allowed: {result_path}")
            self.assertNotIn('windows', result_path.lower(), f"Traversal to Windows dirs allowed: {result_path}")

    def test_path_traversal_encoded_attacks(self):
        """Test that URL-encoded traversal attempts are blocked."""
        encoded_filenames = [
            '%2e%2e%2f%2e%2e%2fetc%2fpasswd',  # ../../../etc/passwd
            '..%2f..%2f..%2fetc%2fpasswd',
            '..%252f..%252fetc%252fpasswd'  # Double-encoded
        ]

        for filename in encoded_filenames:
            result_path = upload_peopleimg(self.user, filename)

            # Should be sanitized
            self.assertNotIn('..', result_path)
            self.assertNotIn('/etc/', result_path)

    def test_null_byte_injection(self):
        """Test that null byte injection is prevented."""
        malicious_filenames = [
            'image.jpg\x00.php',
            'document\x00../../etc/passwd',
            'file.png\x00malicious'
        ]

        for filename in malicious_filenames:
            result_path = upload_peopleimg(self.user, filename)

            # Should strip null bytes
            self.assertNotIn('\x00', result_path)

    def test_absolute_path_rejection(self):
        """Test that absolute paths are rejected."""
        absolute_paths = [
            '/etc/passwd',
            '/var/www/html/shell.php',
            'C:\\Windows\\System32\\evil.exe',
            '//network/share/file.txt'
        ]

        for path in absolute_paths:
            result_path = upload_peopleimg(self.user, path)

            # Should not start with absolute path indicators
            self.assertFalse(result_path.startswith('/'), f"Absolute path allowed: {result_path}")
            self.assertFalse(result_path[1:3] == ':\\' if len(result_path) > 2 else False)

    def test_symlink_traversal_prevention(self):
        """Test that symlink traversal attempts don't work."""
        # Symlinks can't be created in filename itself, but test special names
        special_names = [
            'link',
            '~root',
            '~/../../../etc/passwd'
        ]

        for name in special_names:
            result_path = upload_peopleimg(self.user, name)

            # Should be sanitized
            self.assertNotIn('~', result_path)
            self.assertNotIn('..', result_path)

    def test_allowed_extensions_only(self):
        """Test that only allowed image extensions are accepted."""
        # Valid extensions
        valid_files = ['photo.jpg', 'image.png', 'graphic.gif', 'pic.webp', 'img.jpeg']
        for filename in valid_files:
            result_path = upload_peopleimg(self.user, filename)
            # Should return a valid path (not default)
            self.assertIn(os.path.splitext(filename)[1].lower(), result_path)

        # Invalid extensions should return default
        invalid_files = ['script.php', 'shell.sh', 'malware.exe', 'doc.pdf']
        for filename in invalid_files:
            result_path = upload_peopleimg(self.user, filename)
            # Should return default blank.png
            self.assertEqual(result_path, "master/people/blank.png")

    def test_filename_sanitization(self):
        """Test that filenames are properly sanitized."""
        unsafe_names = [
            'file with spaces.jpg',
            'file@#$%^&*.png',
            'file<script>.jpg',
            'file|pipe.png'
        ]

        for filename in unsafe_names:
            result_path = upload_peopleimg(self.user, filename)

            # Should not contain dangerous characters
            for char in ['<', '>', '|', '@', '#', '$', '%', '^', '&', '*']:
                self.assertNotIn(char, result_path, f"Unsafe character '{char}' in path: {result_path}")


class ArbitraryFileWriteTests(TestCase):
    """Test suite for write_file_to_dir() arbitrary file write prevention."""

    def setUp(self):
        """Set up test directory."""
        self.test_dir = tempfile.mkdtemp()

    def tearDown(self):
        """Clean up test directory."""
        import shutil
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)

    @override_settings(MEDIA_ROOT='/tmp/test_media')
    def test_path_traversal_write_prevention(self):
        """Test that path traversal in write operations is blocked."""
        malicious_paths = [
            '../../../etc/cron.d/malicious',
            '../../../../../../tmp/evil.sh',
            '../outside_media/bad_file.txt'
        ]

        test_content = b'malicious content'

        for path in malicious_paths:
            with self.assertRaises((ValueError, PermissionError, SuspiciousFileOperation)):
                write_file_to_dir(test_content, path)

    @override_settings(MEDIA_ROOT='/tmp/test_media')
    def test_absolute_path_write_prevention(self):
        """Test that absolute paths are blocked."""
        absolute_paths = [
            '/etc/passwd',
            '/var/www/html/shell.php',
            'C:\\Windows\\System32\\evil.exe'
        ]

        test_content = b'test content'

        for path in absolute_paths:
            with self.assertRaises((ValueError, PermissionError)):
                write_file_to_dir(test_content, path)

    @override_settings(MEDIA_ROOT='/tmp/test_media')
    def test_null_byte_write_prevention(self):
        """Test that null bytes in paths are handled."""
        paths_with_nulls = [
            'file.txt\x00.php',
            'doc\x00../../etc/passwd'
        ]

        test_content = b'test content'

        for path in paths_with_nulls:
            # Should either raise or strip null bytes
            try:
                result = write_file_to_dir(test_content, path)
                self.assertNotIn('\x00', result)
            except (ValueError, PermissionError):
                pass  # Also acceptable to reject

    @override_settings(MEDIA_ROOT='/tmp/test_media')
    def test_media_root_boundary_enforcement(self):
        """Test that files can only be written within MEDIA_ROOT."""
        from django.conf import settings
        import os

        # Create MEDIA_ROOT if it doesn't exist
        os.makedirs(settings.MEDIA_ROOT, exist_ok=True)

        safe_path = 'uploads/test_file.txt'
        test_content = b'safe content'

        try:
            result = write_file_to_dir(test_content, safe_path)

            # Verify result is within MEDIA_ROOT
            full_result_path = os.path.abspath(os.path.join(settings.MEDIA_ROOT, result))
            media_root_abs = os.path.abspath(settings.MEDIA_ROOT)

            self.assertTrue(
                full_result_path.startswith(media_root_abs),
                f"File written outside MEDIA_ROOT: {full_result_path}"
            )
        finally:
            # Cleanup
            try:
                os.remove(os.path.join(settings.MEDIA_ROOT, safe_path))
            except:
                pass

    @override_settings(MEDIA_ROOT='/tmp/test_media')
    def test_empty_filebuffer_rejection(self):
        """Test that empty file buffers are rejected."""
        empty_buffers = [b'', [], None]

        for buffer in empty_buffers:
            with self.assertRaises(ValueError):
                write_file_to_dir(buffer, 'test.txt')


class ArbitraryFileReadTests(TestCase):
    """Test suite for SecureFileDownloadService arbitrary file read prevention."""

    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create(
            loginid='test_download_user',
            peoplecode='DWLD001',
            peoplename='Download Test User',
            email='download@example.com',
            dateofbirth='1990-01-01'
        )

        # Create test file in temp directory
        self.test_dir = tempfile.mkdtemp()

    def tearDown(self):
        """Clean up test files."""
        import shutil
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)

    @override_settings(MEDIA_ROOT='/tmp/test_media_download')
    def test_path_traversal_read_prevention(self):
        """Test that path traversal in downloads is blocked."""
        from django.conf import settings

        # Create MEDIA_ROOT
        os.makedirs(settings.MEDIA_ROOT, exist_ok=True)

        malicious_paths = [
            '../../../etc/passwd',
            '../../../../../../var/log/syslog',
            '../outside_media/sensitive.txt'
        ]

        for path in malicious_paths:
            with self.assertRaises((Http404, SuspiciousFileOperation, PermissionDenied)):
                SecureFileDownloadService.validate_and_serve_file(
                    filepath=path,
                    filename='file.txt',
                    user=self.user
                )

    @override_settings(MEDIA_ROOT='/tmp/test_media_download')
    def test_absolute_path_read_prevention(self):
        """Test that absolute paths are blocked in downloads."""
        absolute_paths = [
            '/etc/passwd',
            '/var/www/html/config.php',
            'C:\\Windows\\System32\\config\\SAM'
        ]

        for path in absolute_paths:
            with self.assertRaises((Http404, SuspiciousFileOperation)):
                SecureFileDownloadService.validate_and_serve_file(
                    filepath=path,
                    filename='file.txt',
                    user=self.user
                )

    @override_settings(MEDIA_ROOT='/tmp/test_media_download')
    def test_symlink_attack_prevention(self):
        """Test that symlinks pointing outside MEDIA_ROOT are blocked."""
        from django.conf import settings

        # Create MEDIA_ROOT
        os.makedirs(settings.MEDIA_ROOT, exist_ok=True)

        # Create a symlink pointing outside MEDIA_ROOT
        symlink_path = os.path.join(settings.MEDIA_ROOT, 'malicious_link.txt')
        target_path = '/etc/passwd'

        try:
            # Only test on Unix-like systems
            if os.name != 'nt':
                try:
                    os.symlink(target_path, symlink_path)

                    with self.assertRaises((SuspiciousFileOperation, Http404)):
                        SecureFileDownloadService.validate_and_serve_file(
                            filepath='',
                            filename='malicious_link.txt',
                            user=self.user
                        )
                finally:
                    if os.path.exists(symlink_path):
                        os.unlink(symlink_path)
        except OSError:
            # Skip if symlink creation not supported
            pass

    @override_settings(MEDIA_ROOT='/tmp/test_media_download')
    def test_unauthenticated_download_blocked(self):
        """Test that unauthenticated users cannot download files."""
        with self.assertRaises(PermissionDenied):
            SecureFileDownloadService.validate_and_serve_file(
                filepath='uploads/test.txt',
                filename='test.txt',
                user=None
            )

    @override_settings(MEDIA_ROOT='/tmp/test_media_download')
    def test_disallowed_directory_access_blocked(self):
        """Test that access to non-whitelisted directories is blocked."""
        from django.conf import settings

        # Create MEDIA_ROOT and a disallowed directory
        os.makedirs(settings.MEDIA_ROOT, exist_ok=True)
        disallowed_dir = os.path.join(settings.MEDIA_ROOT, 'admin_only')
        os.makedirs(disallowed_dir, exist_ok=True)

        # Create a file in disallowed directory
        test_file = os.path.join(disallowed_dir, 'secret.txt')
        with open(test_file, 'w') as f:
            f.write('secret content')

        try:
            with self.assertRaises((SuspiciousFileOperation, Http404)):
                SecureFileDownloadService.validate_and_serve_file(
                    filepath='admin_only',
                    filename='secret.txt',
                    user=self.user
                )
        finally:
            # Cleanup
            if os.path.exists(test_file):
                os.remove(test_file)
            if os.path.exists(disallowed_dir):
                os.rmdir(disallowed_dir)


@pytest.mark.security
class IntegrationPathTraversalTests(TestCase):
    """Integration tests for end-to-end path traversal prevention."""

    def setUp(self):
        """Set up test environment."""
        from apps.onboarding.models import Bt

        self.user = User.objects.create(
            loginid='integration_user',
            peoplecode='INT001',
            peoplename='Integration User',
            email='integration@example.com',
            dateofbirth='1990-01-01'
        )

        self.client_bu = Bt.objects.create(
            bucode='INTCLIENT',
            buname='Integration Client',
            butype='CLIENT'
        )

        self.user.client = self.client_bu
        self.user.save()

    def test_upload_write_download_cycle_secure(self):
        """Test complete upload-write-download cycle is secure."""
        from django.conf import settings

        # Phase 1: Secure upload path generation
        safe_filename = 'test_image.jpg'
        upload_path = upload_peopleimg(self.user, safe_filename)

        # Verify upload path is safe
        self.assertNotIn('..', upload_path)
        self.assertTrue(upload_path.startswith('master/'))

        # Phase 2: Secure file write
        test_content = b'test image content'

        with override_settings(MEDIA_ROOT=tempfile.mkdtemp()):
            try:
                saved_path = write_file_to_dir(test_content, upload_path)

                # Verify write was within MEDIA_ROOT
                full_saved_path = os.path.join(settings.MEDIA_ROOT, saved_path)
                media_root_abs = os.path.abspath(settings.MEDIA_ROOT)

                self.assertTrue(
                    os.path.abspath(full_saved_path).startswith(media_root_abs),
                    "File written outside MEDIA_ROOT"
                )

                # Phase 3: Secure file download
                # Verify only authorized users can download
                filename_only = os.path.basename(upload_path)
                filepath_only = os.path.dirname(upload_path)

                # This should succeed for authenticated user
                try:
                    response = SecureFileDownloadService.validate_and_serve_file(
                        filepath=filepath_only,
                        filename=filename_only,
                        user=self.user
                    )
                    # If we get here, validation passed (file may not exist, but security checks passed)
                except Http404:
                    # File not found is acceptable - security validation succeeded
                    pass

            finally:
                # Cleanup
                import shutil
                if os.path.exists(settings.MEDIA_ROOT):
                    shutil.rmtree(settings.MEDIA_ROOT)

    def test_malicious_upload_attack_chain_blocked(self):
        """Test that a complete attack chain is blocked at each step."""
        malicious_filename = '../../../etc/cron.d/malicious_job'

        # Step 1: Upload path generation should sanitize
        upload_path = upload_peopleimg(self.user, malicious_filename)
        self.assertNotIn('..', upload_path)
        self.assertNotIn('/etc/', upload_path)

        # Step 2: Write should also block if attacker bypasses step 1
        with self.assertRaises((ValueError, PermissionError)):
            write_file_to_dir(b'* * * * * evil command', malicious_filename)

        # Step 3: Download should also block direct access attempts
        with self.assertRaises((SuspiciousFileOperation, Http404)):
            SecureFileDownloadService.validate_and_serve_file(
                filepath='../../etc/cron.d',
                filename='malicious_job',
                user=self.user
            )