"""
Comprehensive Tests for SecureFileDownloadService

Priority 1 - Security Critical
Tests all security layers:
- Authentication validation
- Path traversal prevention  
- Tenant isolation
- Ownership validation
- Permission checks
- Symlink attack prevention
- Audit logging

Run: pytest apps/core/tests/test_services/test_secure_file_download_service.py -v --cov=apps.core.services.secure_file_download_service
"""
import pytest
import os
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from django.test import TestCase, override_settings
from django.core.exceptions import PermissionDenied, SuspiciousFileOperation
from django.http import Http404, FileResponse
from django.conf import settings
from django.contrib.auth import get_user_model

from apps.core.services.secure_file_download_service import SecureFileDownloadService

User = get_user_model()


@pytest.fixture
def temp_media_root(tmp_path):
    """Create temporary MEDIA_ROOT with test files"""
    media_root = tmp_path / "media"
    media_root.mkdir()
    
    # Create allowed directories
    (media_root / "uploads").mkdir()
    (media_root / "attachments").mkdir()
    (media_root / "reports").mkdir()
    
    # Create test files
    test_file = media_root / "uploads" / "test.txt"
    test_file.write_text("Test content")
    
    image_file = media_root / "uploads" / "test.png"
    image_file.write_bytes(b'\x89PNG\r\n\x1a\n')
    
    return media_root


@pytest.fixture
def test_tenant(db):
    """Create test tenant"""
    from apps.client_onboarding.models import Bt
    return Bt.objects.create(
        bucode="TESTFILE",
        buname="File Test Tenant",
        enable=True
    )


@pytest.fixture
def test_user(db, test_tenant):
    """Create authenticated test user"""
    user = User.objects.create(
        peoplecode="FILEUSER001",
        peoplename="File Test User",
        loginid="fileuser",
        email="fileuser@example.com",
        mobno="1111111111",
        client=test_tenant,
        enable=True,
        is_staff=False
    )
    user.set_password("TestPass123!")
    user.save()
    return user


@pytest.fixture
def staff_user(db, test_tenant):
    """Create staff user"""
    user = User.objects.create(
        peoplecode="STAFF001",
        peoplename="Staff User",
        loginid="staffuser",
        email="staff@example.com",
        mobno="2222222222",
        client=test_tenant,
        enable=True,
        is_staff=True
    )
    user.set_password("StaffPass123!")
    user.save()
    return user


@pytest.fixture
def superuser(db, test_tenant):
    """Create superuser"""
    user = User.objects.create(
        peoplecode="SUPER001",
        peoplename="Super User",
        loginid="superuser",
        email="super@example.com",
        mobno="3333333333",
        client=test_tenant,
        enable=True,
        is_staff=True,
        is_superuser=True
    )
    user.set_password("SuperPass123!")
    user.save()
    return user


@pytest.fixture
def other_tenant(db):
    """Create different tenant for cross-tenant tests"""
    from apps.client_onboarding.models import Bt
    return Bt.objects.create(
        bucode="OTHERTENANT",
        buname="Other Tenant",
        enable=True
    )


@pytest.fixture
def other_tenant_user(db, other_tenant):
    """Create user from different tenant"""
    user = User.objects.create(
        peoplecode="OTHERUSER001",
        peoplename="Other Tenant User",
        loginid="otheruser",
        email="other@example.com",
        mobno="4444444444",
        client=other_tenant,
        enable=True
    )
    user.set_password("OtherPass123!")
    user.save()
    return user


@pytest.fixture
def test_attachment(db, test_tenant, test_user, temp_media_root):
    """Create test attachment"""
    from apps.activity.models import Attachment
    
    # Create file in temp media root
    filepath = temp_media_root / "attachments" / "test_attachment.pdf"
    filepath.write_bytes(b'%PDF-1.4 test content')
    
    return Attachment.objects.create(
        filepath=str(filepath.relative_to(temp_media_root)),
        filename="test_attachment.pdf",
        filetype="application/pdf",
        client=test_tenant,
        bu=test_tenant,
        tenant=test_tenant,
        cuser=test_user,
        enable=True
    )


@pytest.mark.django_db
class TestAuthenticationValidation(TestCase):
    """Test authentication requirements"""
    
    @patch('apps.core.services.secure_file_download_service.settings.MEDIA_ROOT', '/tmp/media')
    def test_unauthenticated_user_denied(self, temp_media_root):
        """Unauthenticated users should be denied"""
        user = Mock(spec=User)
        user.is_authenticated = False
        
        with pytest.raises(PermissionDenied, match="Authentication required"):
            SecureFileDownloadService.validate_and_serve_file(
                filepath="uploads/test.txt",
                filename="test.txt",
                user=user
            )
    
    def test_none_user_denied(self):
        """None user should be denied"""
        with pytest.raises(PermissionDenied, match="Authentication required"):
            SecureFileDownloadService.validate_and_serve_file(
                filepath="uploads/test.txt",
                filename="test.txt",
                user=None
            )


@pytest.mark.django_db
class TestPathTraversalPrevention(TestCase):
    """Test path traversal attack prevention"""
    
    def test_parent_directory_traversal_blocked(self, test_user, temp_media_root):
        """Block ../ path traversal attempts"""
        with override_settings(MEDIA_ROOT=str(temp_media_root)):
            with pytest.raises(SuspiciousFileOperation, match="path traversal"):
                SecureFileDownloadService.validate_and_serve_file(
                    filepath="../../../etc/passwd",
                    filename="passwd",
                    user=test_user
                )
    
    def test_filename_traversal_blocked(self, test_user, temp_media_root):
        """Block path traversal in filename"""
        with override_settings(MEDIA_ROOT=str(temp_media_root)):
            with pytest.raises(SuspiciousFileOperation, match="path traversal"):
                SecureFileDownloadService.validate_and_serve_file(
                    filepath="uploads",
                    filename="../../../etc/passwd",
                    user=test_user
                )
    
    def test_null_byte_injection_blocked(self, test_user, temp_media_root):
        """Block null byte injection attacks"""
        with override_settings(MEDIA_ROOT=str(temp_media_root)):
            with pytest.raises(SuspiciousFileOperation, match="path traversal"):
                SecureFileDownloadService.validate_and_serve_file(
                    filepath="uploads\x00malicious",
                    filename="test.txt",
                    user=test_user
                )
    
    def test_path_outside_media_root_blocked(self, test_user, temp_media_root):
        """Block access to files outside MEDIA_ROOT"""
        # Create file outside MEDIA_ROOT
        external_file = temp_media_root.parent / "external.txt"
        external_file.write_text("External content")
        
        with override_settings(MEDIA_ROOT=str(temp_media_root)):
            with pytest.raises(SuspiciousFileOperation, match="outside allowed directory"):
                SecureFileDownloadService.validate_and_serve_file(
                    filepath=str(external_file),
                    filename="external.txt",
                    user=test_user
                )
    
    def test_disallowed_directory_blocked(self, test_user, temp_media_root):
        """Block access to disallowed directories"""
        # Create file in disallowed directory
        disallowed = temp_media_root / "forbidden"
        disallowed.mkdir()
        test_file = disallowed / "secret.txt"
        test_file.write_text("Secret content")
        
        with override_settings(MEDIA_ROOT=str(temp_media_root)):
            with pytest.raises(SuspiciousFileOperation, match="not allowed"):
                SecureFileDownloadService.validate_and_serve_file(
                    filepath="forbidden/secret.txt",
                    filename="secret.txt",
                    user=test_user
                )


@pytest.mark.django_db
class TestTenantIsolation(TestCase):
    """Test tenant isolation (critical security)"""
    
    @patch('apps.core.services.secure_file_download_service.settings.MEDIA_ROOT')
    def test_cross_tenant_access_blocked(self, mock_media_root, test_user, other_tenant_user, 
                                         test_attachment, temp_media_root):
        """Users cannot access attachments from other tenants"""
        mock_media_root.return_value = str(temp_media_root)
        
        # Other tenant user tries to access test_user's attachment
        with pytest.raises(PermissionDenied, match="Cross-tenant access denied"):
            SecureFileDownloadService.validate_and_serve_file(
                filepath=test_attachment.filepath,
                filename=test_attachment.filename,
                user=other_tenant_user,
                owner_id=test_attachment.owner
            )
    
    def test_same_tenant_access_allowed(self, test_user, test_attachment, temp_media_root):
        """Users can access files from same tenant if they own them"""
        with override_settings(MEDIA_ROOT=str(temp_media_root)):
            # Owner should have access
            response = SecureFileDownloadService.validate_and_serve_file(
                filepath=test_attachment.filepath,
                filename=test_attachment.filename,
                user=test_user,
                owner_id=test_attachment.owner
            )
            
            assert isinstance(response, FileResponse)


@pytest.mark.django_db
class TestOwnershipValidation(TestCase):
    """Test ownership-based access control"""
    
    def test_owner_can_access_file(self, test_user, test_attachment, temp_media_root):
        """File owner should have access"""
        with override_settings(MEDIA_ROOT=str(temp_media_root)):
            response = SecureFileDownloadService.validate_and_serve_file(
                filepath=test_attachment.filepath,
                filename=test_attachment.filename,
                user=test_user,
                owner_id=test_attachment.owner
            )
            
            assert isinstance(response, FileResponse)
    
    def test_non_owner_same_tenant_denied(self, test_user, test_tenant, 
                                          test_attachment, temp_media_root):
        """Non-owner in same tenant denied without permissions"""
        # Create another user in same tenant
        other_user = User.objects.create(
            peoplecode="OTHER002",
            peoplename="Other User",
            loginid="otheruser2",
            email="other2@example.com",
            mobno="5555555555",
            client=test_tenant,
            enable=True
        )
        
        with override_settings(MEDIA_ROOT=str(temp_media_root)):
            with pytest.raises(PermissionDenied):
                SecureFileDownloadService.validate_and_serve_file(
                    filepath=test_attachment.filepath,
                    filename=test_attachment.filename,
                    user=other_user,
                    owner_id=test_attachment.owner
                )


@pytest.mark.django_db
class TestPermissionChecks(TestCase):
    """Test permission-based access control"""
    
    def test_superuser_bypasses_all_checks(self, superuser, test_attachment, temp_media_root):
        """Superuser should access any file"""
        with override_settings(MEDIA_ROOT=str(temp_media_root)):
            response = SecureFileDownloadService.validate_and_serve_file(
                filepath=test_attachment.filepath,
                filename=test_attachment.filename,
                user=superuser,
                owner_id=test_attachment.owner
            )
            
            assert isinstance(response, FileResponse)
    
    def test_staff_user_same_tenant_allowed(self, staff_user, test_attachment, temp_media_root):
        """Staff users can access files in their tenant"""
        # Update staff user to same tenant
        staff_user.client = test_attachment.client
        staff_user.save()
        
        # Grant permission
        from django.contrib.contenttypes.models import ContentType
        from django.contrib.auth.models import Permission
        
        ct = ContentType.objects.get_for_model(test_attachment.__class__)
        permission = Permission.objects.get(
            codename='view_attachment',
            content_type=ct
        )
        staff_user.user_permissions.add(permission)
        
        with override_settings(MEDIA_ROOT=str(temp_media_root)):
            response = SecureFileDownloadService.validate_and_serve_file(
                filepath=test_attachment.filepath,
                filename=test_attachment.filename,
                user=staff_user,
                owner_id=test_attachment.owner
            )
            
            assert isinstance(response, FileResponse)
    
    def test_non_staff_direct_file_access_denied(self, test_user, temp_media_root):
        """Non-staff users cannot access files directly without owner_id"""
        with override_settings(MEDIA_ROOT=str(temp_media_root)):
            with pytest.raises(PermissionDenied, match="Direct file access not permitted"):
                SecureFileDownloadService.validate_and_serve_file(
                    filepath="uploads/test.txt",
                    filename="test.txt",
                    user=test_user,
                    owner_id=None  # No owner_id
                )
    
    def test_staff_direct_file_access_allowed(self, staff_user, temp_media_root):
        """Staff users can access files directly"""
        with override_settings(MEDIA_ROOT=str(temp_media_root)):
            response = SecureFileDownloadService.validate_and_serve_file(
                filepath="uploads/test.txt",
                filename="test.txt",
                user=staff_user,
                owner_id=None
            )
            
            assert isinstance(response, FileResponse)


@pytest.mark.django_db
class TestSymlinkAttackPrevention(TestCase):
    """Test symlink attack prevention"""
    
    def test_symlink_outside_media_root_blocked(self, test_user, temp_media_root):
        """Block symlinks pointing outside MEDIA_ROOT"""
        # Create external file
        external = temp_media_root.parent / "external_secret.txt"
        external.write_text("Secret data")
        
        # Create symlink inside MEDIA_ROOT pointing outside
        symlink = temp_media_root / "uploads" / "sneaky_link.txt"
        symlink.symlink_to(external)
        
        with override_settings(MEDIA_ROOT=str(temp_media_root)):
            with pytest.raises(SuspiciousFileOperation, match="Symlink to unauthorized location"):
                SecureFileDownloadService.validate_and_serve_file(
                    filepath="uploads/sneaky_link.txt",
                    filename="sneaky_link.txt",
                    user=test_user,
                    owner_id=None
                )


@pytest.mark.django_db
class TestFileValidation(TestCase):
    """Test file existence and type validation"""
    
    def test_nonexistent_file_returns_404(self, test_user, temp_media_root):
        """Non-existent files should return 404"""
        with override_settings(MEDIA_ROOT=str(temp_media_root)):
            with pytest.raises(Http404, match="File not found"):
                SecureFileDownloadService.validate_and_serve_file(
                    filepath="uploads/nonexistent.txt",
                    filename="nonexistent.txt",
                    user=test_user,
                    owner_id=None
                )
    
    def test_directory_access_blocked(self, test_user, temp_media_root):
        """Cannot download directories"""
        with override_settings(MEDIA_ROOT=str(temp_media_root)):
            with pytest.raises(Http404, match="Invalid file type"):
                SecureFileDownloadService.validate_and_serve_file(
                    filepath="uploads",
                    filename="uploads",
                    user=test_user,
                    owner_id=None
                )


@pytest.mark.django_db
class TestSecureResponse(TestCase):
    """Test secure file response generation"""
    
    def test_image_response_inline_disposition(self, staff_user, temp_media_root):
        """Images should use inline disposition"""
        with override_settings(MEDIA_ROOT=str(temp_media_root)):
            response = SecureFileDownloadService.validate_and_serve_file(
                filepath="uploads/test.png",
                filename="test.png",
                user=staff_user,
                owner_id=None
            )
            
            assert isinstance(response, FileResponse)
            assert 'inline' in response['Content-Disposition']
            assert 'test.png' in response['Content-Disposition']
            assert response['Content-Type'].startswith('image/')
    
    def test_non_image_response_attachment_disposition(self, staff_user, temp_media_root):
        """Non-images should use attachment disposition"""
        with override_settings(MEDIA_ROOT=str(temp_media_root)):
            response = SecureFileDownloadService.validate_and_serve_file(
                filepath="uploads/test.txt",
                filename="test.txt",
                user=staff_user,
                owner_id=None
            )
            
            assert isinstance(response, FileResponse)
            assert 'attachment' in response['Content-Disposition']
            assert 'test.txt' in response['Content-Disposition']
    
    def test_security_headers_present(self, staff_user, temp_media_root):
        """Security headers should be set"""
        with override_settings(MEDIA_ROOT=str(temp_media_root)):
            response = SecureFileDownloadService.validate_and_serve_file(
                filepath="uploads/test.txt",
                filename="test.txt",
                user=staff_user,
                owner_id=None
            )
            
            assert response['X-Content-Type-Options'] == 'nosniff'
            assert response['X-Frame-Options'] == 'DENY'


@pytest.mark.django_db
class TestAttachmentAccessValidation(TestCase):
    """Test validate_attachment_access method"""
    
    def test_owner_can_access_attachment(self, test_user, test_attachment):
        """Attachment owner should have access"""
        attachment = SecureFileDownloadService.validate_attachment_access(
            attachment_id=test_attachment.id,
            user=test_user
        )
        
        assert attachment.id == test_attachment.id
    
    def test_superuser_can_access_any_attachment(self, superuser, test_attachment):
        """Superuser should access any attachment"""
        attachment = SecureFileDownloadService.validate_attachment_access(
            attachment_id=test_attachment.id,
            user=superuser
        )
        
        assert attachment.id == test_attachment.id
    
    def test_cross_tenant_attachment_access_denied(self, other_tenant_user, test_attachment):
        """Cross-tenant attachment access should be denied"""
        with pytest.raises(PermissionDenied, match="Cross-tenant access denied"):
            SecureFileDownloadService.validate_attachment_access(
                attachment_id=test_attachment.id,
                user=other_tenant_user
            )
    
    def test_nonexistent_attachment_returns_404(self, test_user):
        """Non-existent attachment should return 404"""
        with pytest.raises(Http404, match="Attachment not found"):
            SecureFileDownloadService.validate_attachment_access(
                attachment_id=999999,
                user=test_user
            )


@pytest.mark.django_db
class TestAuditLogging(TestCase):
    """Test audit logging for security events"""
    
    @patch('apps.core.services.secure_file_download_service.logger')
    def test_successful_download_logged(self, mock_logger, staff_user, temp_media_root):
        """Successful downloads should be logged"""
        with override_settings(MEDIA_ROOT=str(temp_media_root)):
            SecureFileDownloadService.validate_and_serve_file(
                filepath="uploads/test.txt",
                filename="test.txt",
                user=staff_user,
                owner_id=None
            )
            
            # Check info log was called for success
            assert any(
                'File download successful' in str(call)
                for call in mock_logger.info.call_args_list
            )
    
    @patch('apps.core.services.secure_file_download_service.logger')
    def test_path_traversal_attempt_logged(self, mock_logger, test_user, temp_media_root):
        """Path traversal attempts should be logged"""
        with override_settings(MEDIA_ROOT=str(temp_media_root)):
            with pytest.raises(SuspiciousFileOperation):
                SecureFileDownloadService.validate_and_serve_file(
                    filepath="../../../etc/passwd",
                    filename="passwd",
                    user=test_user
                )
            
            # Check error log was called
            assert any(
                'Path traversal attempt detected' in str(call)
                for call in mock_logger.error.call_args_list
            )
    
    @patch('apps.core.services.secure_file_download_service.logger')
    def test_cross_tenant_attempt_logged(self, mock_logger, other_tenant_user, 
                                         test_attachment, temp_media_root):
        """Cross-tenant access attempts should be logged"""
        with override_settings(MEDIA_ROOT=str(temp_media_root)):
            with pytest.raises(PermissionDenied):
                SecureFileDownloadService.validate_and_serve_file(
                    filepath=test_attachment.filepath,
                    filename=test_attachment.filename,
                    user=other_tenant_user,
                    owner_id=test_attachment.owner
                )
            
            # Check security violation was logged
            assert any(
                'SECURITY VIOLATION' in str(call) or 'Cross-tenant' in str(call)
                for call in mock_logger.error.call_args_list
            )
