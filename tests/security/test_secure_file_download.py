"""
Secure File Download Service Tests

Tests for SecureFileDownloadService security validations.

Tests implemented security fixes from November 5, 2025 code review:
- Path traversal prevention
- IDOR prevention
- Multi-tenant isolation
- Permission validation
- Audit logging

Compliance:
- Rule #14b: File Download and Access Control
"""

import pytest
import os
import tempfile
from django.test import TestCase, RequestFactory
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.http import Http404, FileResponse
from django.conf import settings
from apps.core.services.secure_file_download_service import SecureFileDownloadService

People = get_user_model()


@pytest.mark.django_db
class TestPathTraversalPrevention(TestCase):
    """Test path traversal attack prevention."""

    def setUp(self):
        """Set up test user and files."""
        self.user = People.objects.create_user(
            loginid='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        # Create legitimate test file in MEDIA_ROOT
        self.test_file_path = os.path.join(settings.MEDIA_ROOT, 'uploads', 'test.txt')
        os.makedirs(os.path.dirname(self.test_file_path), exist_ok=True)
        with open(self.test_file_path, 'w') as f:
            f.write('test content')

    def tearDown(self):
        """Clean up test files."""
        if os.path.exists(self.test_file_path):
            os.remove(self.test_file_path)

    def test_path_traversal_attack_blocked(self):
        """Test that path traversal attempts are blocked."""
        # Attempt to access file outside MEDIA_ROOT
        malicious_path = '../../etc/passwd'
        
        with pytest.raises(Http404):
            SecureFileDownloadService.validate_and_serve_file(
                filepath=malicious_path,
                filename='passwd',
                user=self.user,
                owner_id=self.user.id
            )

    def test_absolute_path_outside_media_root_blocked(self):
        """Test that absolute paths outside MEDIA_ROOT are blocked."""
        malicious_path = '/etc/passwd'
        
        with pytest.raises(Http404):
            SecureFileDownloadService.validate_and_serve_file(
                filepath=malicious_path,
                filename='passwd',
                user=self.user,
                owner_id=self.user.id
            )

    def test_symlink_attack_prevented(self):
        """Test that symlinks pointing outside MEDIA_ROOT are blocked."""
        # Create symlink to /etc/passwd (if possible)
        symlink_path = os.path.join(settings.MEDIA_ROOT, 'uploads', 'evil_link')
        
        try:
            os.symlink('/etc/passwd', symlink_path)
            
            with pytest.raises((Http404, PermissionDenied)):
                SecureFileDownloadService.validate_and_serve_file(
                    filepath=symlink_path,
                    filename='evil_link',
                    user=self.user,
                    owner_id=self.user.id
                )
        finally:
            if os.path.exists(symlink_path):
                os.remove(symlink_path)

    def test_legitimate_file_allowed(self):
        """Test that legitimate files are served correctly."""
        response = SecureFileDownloadService.validate_and_serve_file(
            filepath=self.test_file_path,
            filename='test.txt',
            user=self.user,
            owner_id=self.user.id
        )
        
        assert isinstance(response, FileResponse)
        assert response.status_code == 200


@pytest.mark.django_db
class TestFileDownloadPermissions(TestCase):
    """Test permission validation in file downloads."""

    def setUp(self):
        """Set up test users and files."""
        self.user1 = People.objects.create_user(
            loginid='user1',
            email='user1@example.com',
            password='pass123'
        )
        self.user2 = People.objects.create_user(
            loginid='user2',
            email='user2@example.com',
            password='pass123'
        )
        
        # Create test file
        self.test_file_path = os.path.join(settings.MEDIA_ROOT, 'uploads', 'user1_file.txt')
        os.makedirs(os.path.dirname(self.test_file_path), exist_ok=True)
        with open(self.test_file_path, 'w') as f:
            f.write('user1 content')

    def tearDown(self):
        """Clean up test files."""
        if os.path.exists(self.test_file_path):
            os.remove(self.test_file_path)

    def test_owner_can_download_file(self):
        """Test that file owner can download their file."""
        response = SecureFileDownloadService.validate_and_serve_file(
            filepath=self.test_file_path,
            filename='user1_file.txt',
            user=self.user1,
            owner_id=self.user1.id
        )
        
        assert isinstance(response, FileResponse)
        assert response.status_code == 200

    def test_non_owner_cannot_download_file(self):
        """Test that non-owners cannot download files (IDOR prevention)."""
        with pytest.raises(PermissionDenied):
            SecureFileDownloadService.validate_and_serve_file(
                filepath=self.test_file_path,
                filename='user1_file.txt',
                user=self.user2,  # Different user
                owner_id=self.user1.id  # Owned by user1
            )

    def test_superuser_can_download_any_file(self):
        """Test that superusers can download any file."""
        superuser = People.objects.create_superuser(
            loginid='admin',
            email='admin@example.com',
            password='admin123'
        )
        
        response = SecureFileDownloadService.validate_and_serve_file(
            filepath=self.test_file_path,
            filename='user1_file.txt',
            user=superuser,
            owner_id=self.user1.id
        )
        
        assert isinstance(response, FileResponse)
        assert response.status_code == 200

    def test_unauthenticated_access_denied(self):
        """Test that unauthenticated users cannot download files."""
        from django.contrib.auth.models import AnonymousUser
        
        anonymous = AnonymousUser()
        
        with pytest.raises(PermissionDenied):
            SecureFileDownloadService.validate_and_serve_file(
                filepath=self.test_file_path,
                filename='user1_file.txt',
                user=anonymous,
                owner_id=self.user1.id
            )


@pytest.mark.django_db
class TestFileDownloadValidation(TestCase):
    """Test file existence and validation checks."""

    def setUp(self):
        """Set up test user."""
        self.user = People.objects.create_user(
            loginid='testuser',
            email='test@example.com',
            password='testpass123'
        )

    def test_nonexistent_file_raises_404(self):
        """Test that attempting to download non-existent file raises Http404."""
        nonexistent_path = os.path.join(settings.MEDIA_ROOT, 'uploads', 'nonexistent.txt')
        
        with pytest.raises(Http404):
            SecureFileDownloadService.validate_and_serve_file(
                filepath=nonexistent_path,
                filename='nonexistent.txt',
                user=self.user,
                owner_id=self.user.id
            )

    def test_empty_filepath_rejected(self):
        """Test that empty file paths are rejected."""
        with pytest.raises(Http404):
            SecureFileDownloadService.validate_and_serve_file(
                filepath='',
                filename='test.txt',
                user=self.user,
                owner_id=self.user.id
            )

    def test_none_filepath_rejected(self):
        """Test that None file paths are rejected."""
        with pytest.raises((Http404, TypeError)):
            SecureFileDownloadService.validate_and_serve_file(
                filepath=None,
                filename='test.txt',
                user=self.user,
                owner_id=self.user.id
            )


@pytest.mark.django_db
class TestFileDownloadAuditLogging(TestCase):
    """Test audit logging for file download operations."""

    def setUp(self):
        """Set up test user and file."""
        self.user = People.objects.create_user(
            loginid='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        # Create test file
        self.test_file_path = os.path.join(settings.MEDIA_ROOT, 'uploads', 'audit_test.txt')
        os.makedirs(os.path.dirname(self.test_file_path), exist_ok=True)
        with open(self.test_file_path, 'w') as f:
            f.write('audit test content')

    def tearDown(self):
        """Clean up test files."""
        if os.path.exists(self.test_file_path):
            os.remove(self.test_file_path)

    def test_successful_download_logged(self, caplog):
        """Test that successful downloads are logged."""
        import logging
        
        with caplog.at_level(logging.INFO):
            response = SecureFileDownloadService.validate_and_serve_file(
                filepath=self.test_file_path,
                filename='audit_test.txt',
                user=self.user,
                owner_id=self.user.id
            )
        
        # Verify logging occurred
        assert any('File download request received' in record.message for record in caplog.records)
        assert any('File served successfully' in record.message for record in caplog.records)

    def test_permission_denied_logged(self, caplog):
        """Test that permission denials are logged."""
        import logging
        
        user2 = People.objects.create_user(
            loginid='user2',
            email='user2@example.com',
            password='pass123'
        )
        
        with caplog.at_level(logging.WARNING):
            with pytest.raises(PermissionDenied):
                SecureFileDownloadService.validate_and_serve_file(
                    filepath=self.test_file_path,
                    filename='audit_test.txt',
                    user=user2,
                    owner_id=self.user.id  # Different owner
                )
        
        # Verify security event logged
        assert any('Permission denied' in record.message for record in caplog.records)


__all__ = [
    'TestPathTraversalPrevention',
    'TestFileDownloadPermissions',
    'TestFileDownloadValidation',
    'TestFileDownloadAuditLogging',
]
