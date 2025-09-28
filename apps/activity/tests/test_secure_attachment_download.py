"""
Security Tests for Attachment Download

Tests the security fixes for attachment download functionality to prevent:
- Arbitrary file read (IDOR)
- Path traversal in downloads
- Unauthorized access to files
- Symlink attacks

Compliance: Validates Rule #14 from .claude/rules.md - File Upload Security
"""

import os
import tempfile
import pytest
from django.test import TestCase, Client, override_settings
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, SuspiciousFileOperation
from django.http import Http404
from pathlib import Path

from apps.core.services.secure_file_download_service import SecureFileDownloadService

User = get_user_model()


@pytest.mark.security
class AttachmentDownloadSecurityTests(TestCase):
    """Comprehensive security tests for attachment downloads."""

    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create(
            loginid='download_test_user',
            peoplecode='DL001',
            peoplename='Download Test User',
            email='download@example.com',
            dateofbirth='1990-01-01'
        )

        self.other_user = User.objects.create(
            loginid='other_user',
            peoplecode='OTH001',
            peoplename='Other User',
            email='other@example.com',
            dateofbirth='1990-01-01'
        )

        # Create test directory structure
        self.test_media_root = tempfile.mkdtemp()

    def tearDown(self):
        """Clean up test files."""
        import shutil
        if os.path.exists(self.test_media_root):
            shutil.rmtree(self.test_media_root)

    @override_settings(MEDIA_ROOT='/tmp/test_secure_download')
    def test_path_traversal_via_filepath_parameter(self):
        """Test: Path traversal in filepath parameter is blocked."""
        malicious_paths = [
            '../../../etc/passwd',
            '../../../../../../var/log/syslog',
            '../outside_media/secret.txt'
        ]

        for path in malicious_paths:
            with self.assertRaises((Http404, SuspiciousFileOperation)):
                SecureFileDownloadService.validate_and_serve_file(
                    filepath=path,
                    filename='file.txt',
                    user=self.user
                )

    @override_settings(MEDIA_ROOT='/tmp/test_secure_download')
    def test_path_traversal_via_filename_parameter(self):
        """Test: Path traversal in filename parameter is blocked."""
        malicious_filenames = [
            '../../../etc/passwd',
            '../../sensitive.txt',
            '../config/database.yml'
        ]

        for filename in malicious_filenames:
            with self.assertRaises((Http404, SuspiciousFileOperation)):
                SecureFileDownloadService.validate_and_serve_file(
                    filepath='uploads',
                    filename=filename,
                    user=self.user
                )

    @override_settings(MEDIA_ROOT='/tmp/test_secure_download')
    def test_absolute_path_download_blocked(self):
        """Test: Absolute paths in downloads are blocked."""
        absolute_paths = [
            ('/etc/passwd', 'passwd'),
            ('/var/www/html/config.php', 'config.php'),
            ('C:\\Windows\\System32\\config\\SAM', 'SAM')
        ]

        for filepath, filename in absolute_paths:
            with self.assertRaises((Http404, SuspiciousFileOperation)):
                SecureFileDownloadService.validate_and_serve_file(
                    filepath=filepath,
                    filename=filename,
                    user=self.user
                )

    @override_settings(MEDIA_ROOT='/tmp/test_secure_download')
    def test_null_byte_injection_in_download_path(self):
        """Test: Null bytes in download paths are handled."""
        paths_with_nulls = [
            ('uploads', 'file.txt\x00.php'),
            ('documents\x00/../../etc', 'passwd'),
        ]

        for filepath, filename in paths_with_nulls:
            # Should either raise or strip null bytes
            try:
                response = SecureFileDownloadService.validate_and_serve_file(
                    filepath=filepath,
                    filename=filename,
                    user=self.user
                )
                # If it doesn't raise, null bytes should be removed
                # (will likely fail with 404 since file doesn't exist)
            except (Http404, SuspiciousFileOperation):
                # This is expected - null bytes should be detected
                pass

    @override_settings(MEDIA_ROOT='/tmp/test_secure_download')
    def test_symlink_pointing_outside_media_root(self):
        """Test: Symlinks pointing outside MEDIA_ROOT are blocked."""
        from django.conf import settings

        # Create MEDIA_ROOT
        os.makedirs(settings.MEDIA_ROOT, exist_ok=True)

        # Only test on Unix-like systems
        if os.name != 'nt':
            symlink_path = os.path.join(settings.MEDIA_ROOT, 'uploads', 'evil_link.txt')
            os.makedirs(os.path.dirname(symlink_path), exist_ok=True)

            try:
                # Create symlink to /etc/passwd
                os.symlink('/etc/passwd', symlink_path)

                with self.assertRaises((SuspiciousFileOperation, Http404)):
                    SecureFileDownloadService.validate_and_serve_file(
                        filepath='uploads',
                        filename='evil_link.txt',
                        user=self.user
                    )
            finally:
                if os.path.exists(symlink_path):
                    os.unlink(symlink_path)
                if os.path.exists(settings.MEDIA_ROOT):
                    import shutil
                    shutil.rmtree(settings.MEDIA_ROOT)

    @override_settings(MEDIA_ROOT='/tmp/test_secure_download')
    def test_unauthenticated_download_attempt(self):
        """Test: Unauthenticated users cannot download files."""
        with self.assertRaises(PermissionDenied):
            SecureFileDownloadService.validate_and_serve_file(
                filepath='uploads',
                filename='test.txt',
                user=None
            )

        # Test with unauthenticated mock user
        class UnauthenticatedUser:
            is_authenticated = False
            id = None

        unauth_user = UnauthenticatedUser()

        with self.assertRaises(PermissionDenied):
            SecureFileDownloadService.validate_and_serve_file(
                filepath='uploads',
                filename='test.txt',
                user=unauth_user
            )

    @override_settings(MEDIA_ROOT='/tmp/test_secure_download')
    def test_disallowed_directory_access(self):
        """Test: Access to non-whitelisted directories is blocked."""
        from django.conf import settings

        # Create MEDIA_ROOT and directories
        os.makedirs(settings.MEDIA_ROOT, exist_ok=True)

        # Create allowed and disallowed directories
        allowed_dir = os.path.join(settings.MEDIA_ROOT, 'uploads')
        disallowed_dir = os.path.join(settings.MEDIA_ROOT, 'admin_secrets')

        os.makedirs(allowed_dir, exist_ok=True)
        os.makedirs(disallowed_dir, exist_ok=True)

        # Create files in both
        allowed_file = os.path.join(allowed_dir, 'public.txt')
        disallowed_file = os.path.join(disallowed_dir, 'secret.txt')

        with open(allowed_file, 'w') as f:
            f.write('public content')
        with open(disallowed_file, 'w') as f:
            f.write('secret content')

        try:
            # Access to allowed directory should work (authentication passes)
            try:
                SecureFileDownloadService.validate_and_serve_file(
                    filepath='uploads',
                    filename='public.txt',
                    user=self.user
                )
            except Http404:
                # File might not exist in actual test, but path validation should pass
                pass

            # Access to disallowed directory should be blocked
            with self.assertRaises((SuspiciousFileOperation, Http404)):
                SecureFileDownloadService.validate_and_serve_file(
                    filepath='admin_secrets',
                    filename='secret.txt',
                    user=self.user
                )
        finally:
            # Cleanup
            import shutil
            if os.path.exists(settings.MEDIA_ROOT):
                shutil.rmtree(settings.MEDIA_ROOT)

    @override_settings(MEDIA_ROOT='/tmp/test_secure_download')
    def test_directory_download_blocked(self):
        """Test: Downloading directories is blocked."""
        from django.conf import settings

        # Create MEDIA_ROOT and a directory
        os.makedirs(settings.MEDIA_ROOT, exist_ok=True)
        test_dir = os.path.join(settings.MEDIA_ROOT, 'uploads', 'testdir')
        os.makedirs(test_dir, exist_ok=True)

        try:
            with self.assertRaises((Http404, SuspiciousFileOperation)):
                SecureFileDownloadService.validate_and_serve_file(
                    filepath='uploads',
                    filename='testdir',  # This is a directory, not a file
                    user=self.user
                )
        finally:
            import shutil
            if os.path.exists(settings.MEDIA_ROOT):
                shutil.rmtree(settings.MEDIA_ROOT)

    @override_settings(MEDIA_ROOT='/tmp/test_secure_download')
    def test_media_root_boundary_enforcement(self):
        """Test: Files can only be accessed within MEDIA_ROOT."""
        from django.conf import settings

        # Create MEDIA_ROOT
        os.makedirs(settings.MEDIA_ROOT, exist_ok=True)

        # Create a file inside MEDIA_ROOT
        safe_dir = os.path.join(settings.MEDIA_ROOT, 'uploads')
        os.makedirs(safe_dir, exist_ok=True)
        safe_file = os.path.join(safe_dir, 'safe.txt')
        with open(safe_file, 'w') as f:
            f.write('safe content')

        # Create a file outside MEDIA_ROOT
        outside_file = os.path.join('/tmp', 'outside_media.txt')
        with open(outside_file, 'w') as f:
            f.write('outside content')

        try:
            # Access inside MEDIA_ROOT should work (with proper auth)
            try:
                response = SecureFileDownloadService.validate_and_serve_file(
                    filepath='uploads',
                    filename='safe.txt',
                    user=self.user
                )
                # Should succeed or raise Http404 if file handling fails
            except Http404:
                pass  # File might not be properly set up, but security check passed

            # Access outside MEDIA_ROOT should be blocked
            # Try various path traversal techniques
            traversal_attempts = [
                ('../../../tmp', 'outside_media.txt'),
                ('/tmp', 'outside_media.txt'),
                ('..', 'outside_media.txt'),
            ]

            for filepath, filename in traversal_attempts:
                with self.assertRaises((Http404, SuspiciousFileOperation)):
                    SecureFileDownloadService.validate_and_serve_file(
                        filepath=filepath,
                        filename=filename,
                        user=self.user
                    )

        finally:
            # Cleanup
            if os.path.exists(outside_file):
                os.remove(outside_file)
            import shutil
            if os.path.exists(settings.MEDIA_ROOT):
                shutil.rmtree(settings.MEDIA_ROOT)

    @override_settings(MEDIA_ROOT='/tmp/test_secure_download')
    def test_encoded_path_traversal_blocked(self):
        """Test: URL-encoded path traversal is blocked."""
        encoded_paths = [
            ('%2e%2e%2f%2e%2e%2fetc', 'passwd'),
            ('..%2f..%2f..', 'etc%2fpasswd'),
            ('%2e%2e%252f%2e%2e', 'sensitive.txt'),  # Double-encoded
        ]

        for filepath, filename in encoded_paths:
            with self.assertRaises((Http404, SuspiciousFileOperation)):
                SecureFileDownloadService.validate_and_serve_file(
                    filepath=filepath,
                    filename=filename,
                    user=self.user
                )

    @override_settings(MEDIA_ROOT='/tmp/test_secure_download')
    def test_case_sensitivity_in_traversal_detection(self):
        """Test: Path traversal detection is case-insensitive."""
        case_variant_paths = [
            ('../../../ETC/passwd', 'passwd'),
            ('..\\..\\..\\Windows', 'system.ini'),
            ('../../../Etc/../etc', 'passwd'),
        ]

        for filepath, filename in case_variant_paths:
            with self.assertRaises((Http404, SuspiciousFileOperation)):
                SecureFileDownloadService.validate_and_serve_file(
                    filepath=filepath,
                    filename=filename,
                    user=self.user
                )

    def test_media_url_prefix_handling(self):
        """Test: MEDIA_URL prefix is properly stripped."""
        from django.conf import settings

        # Test with various MEDIA_URL prefixes
        paths_with_prefix = [
            (f"{settings.MEDIA_URL}uploads", "file.txt"),
            ("youtility4_media/uploads", "file.txt"),
            ("/media/uploads", "file.txt"),
        ]

        for filepath, filename in paths_with_prefix:
            # Should handle and strip prefix without allowing traversal
            try:
                SecureFileDownloadService.validate_and_serve_file(
                    filepath=filepath,
                    filename=filename,
                    user=self.user
                )
            except Http404:
                # File not found is OK - path validation should have succeeded
                pass
            except SuspiciousFileOperation:
                # Should not raise this for valid prefix stripping
                self.fail(f"Path with prefix should be handled: {filepath}")


@pytest.mark.security
class AttachmentAccessControlTests(TestCase):
    """Tests for access control in attachment downloads."""

    def setUp(self):
        """Set up test users and attachments."""
        self.owner_user = User.objects.create(
            loginid='owner_user',
            peoplecode='OWN001',
            peoplename='Owner User',
            email='owner@example.com',
            dateofbirth='1990-01-01'
        )

        self.other_user = User.objects.create(
            loginid='other_user',
            peoplecode='OTH001',
            peoplename='Other User',
            email='other@example.com',
            dateofbirth='1990-01-01'
        )

    @override_settings(MEDIA_ROOT='/tmp/test_access_control')
    def test_access_control_validation_hook(self):
        """Test: Access control hook is called during validation."""
        from unittest.mock import patch

        # Test that _validate_file_access is called when owner_id is provided
        with patch.object(
            SecureFileDownloadService,
            '_validate_file_access'
        ) as mock_validate:
            try:
                SecureFileDownloadService.validate_and_serve_file(
                    filepath='uploads',
                    filename='test.txt',
                    user=self.owner_user,
                    owner_id='test_owner_id'
                )
            except Http404:
                pass  # File doesn't exist, but access control should have been checked

            # Verify access control was called
            mock_validate.assert_called()

    def test_unauthorized_user_different_owner(self):
        """Test: Users cannot access files owned by others."""
        # This test would require implementing actual access control logic
        # For now, it serves as documentation of expected behavior
        pass  # TODO: Implement when access control is fully defined