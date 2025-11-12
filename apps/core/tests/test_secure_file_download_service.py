"""
Tests for SecureFileDownloadService

Tests comprehensive security validation including:
- Tenant isolation
- Ownership validation
- Path traversal prevention
- Permission checks
- Audit logging
"""

import pytest
from django.test import RequestFactory
from django.core.files.uploadedfile import SimpleUploadedFile
from django.conf import settings
from pathlib import Path
import tempfile
import os

from apps.core.services.secure_file_download_service import SecureFileDownloadService
from apps.core.models import Attachment
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
def other_tenant():
    """Create another tenant for cross-tenant tests."""
    return Tenant.objects.create(
        name="Other Tenant",
        slug="other-tenant",
        is_active=True
    )


@pytest.fixture
def test_user(test_tenant):
    """Create test user."""
    user = People.objects.create(
        peoplename="testuser",
        peopleemail="test@example.com",
        peoplerole="user"
    )
    PeopleTenant.objects.create(
        people=user,
        tenant=test_tenant,
        is_primary=True
    )
    return user


@pytest.fixture
def other_user(other_tenant):
    """Create user in different tenant."""
    user = People.objects.create(
        peoplename="otheruser",
        peopleemail="other@example.com",
        peoplerole="user"
    )
    PeopleTenant.objects.create(
        people=user,
        tenant=other_tenant,
        is_primary=True
    )
    return user


@pytest.fixture
def test_file():
    """Create temporary test file."""
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as f:
        f.write("Test file content")
        temp_path = f.name
    
    yield temp_path
    
    # Cleanup
    if os.path.exists(temp_path):
        os.unlink(temp_path)


@pytest.fixture
def test_attachment(test_user, test_tenant, test_file):
    """Create test attachment."""
    # Create within MEDIA_ROOT
    media_path = Path(settings.MEDIA_ROOT) / 'uploads' / 'test.txt'
    media_path.parent.mkdir(parents=True, exist_ok=True)
    media_path.write_text("Test file content")
    
    attachment = Attachment.objects.create(
        owner=test_user.id,
        filepath=str(media_path),
        filename='test.txt',
        mimetype='text/plain',
        filesize=len("Test file content"),
        tenant=test_tenant
    )
    
    yield attachment
    
    # Cleanup
    if media_path.exists():
        media_path.unlink()


@pytest.mark.django_db
class TestValidateAttachmentAccess:
    """Test attachment access validation."""
    
    def test_success_owner_access(self, test_attachment, test_user):
        """Test successful access by owner."""
        result = SecureFileDownloadService.validate_attachment_access(
            attachment_id=test_attachment.id,
            user=test_user
        )
        
        assert result == test_attachment
        assert result.owner == test_user.id
    
    def test_blocked_cross_tenant_access(self, test_attachment, other_user):
        """Test cross-tenant access is blocked (IDOR prevention)."""
        with pytest.raises(PermissionError, match="not authorized"):
            SecureFileDownloadService.validate_attachment_access(
                attachment_id=test_attachment.id,
                user=other_user
            )
    
    def test_blocked_unauthorized_user(self, test_attachment, test_tenant):
        """Test access denied for user without ownership."""
        # Create new user in same tenant but not owner
        unauthorized_user = People.objects.create(
            peoplename="unauthorized",
            peopleemail="unauth@example.com",
            peoplerole="user"
        )
        PeopleTenant.objects.create(
            people=unauthorized_user,
            tenant=test_tenant,
            is_primary=True
        )
        
        with pytest.raises(PermissionError, match="not authorized"):
            SecureFileDownloadService.validate_attachment_access(
                attachment_id=test_attachment.id,
                user=unauthorized_user
            )
    
    def test_invalid_attachment_id(self, test_user):
        """Test handling of non-existent attachment."""
        with pytest.raises(ValueError, match="not found"):
            SecureFileDownloadService.validate_attachment_access(
                attachment_id=99999,
                user=test_user
            )


@pytest.mark.django_db
class TestValidateAndServeFile:
    """Test secure file serving with path validation."""
    
    def test_success_serve_file(self, test_attachment, test_user):
        """Test successful file serving."""
        response = SecureFileDownloadService.validate_and_serve_file(
            filepath=test_attachment.filepath,
            filename=test_attachment.filename,
            user=test_user,
            owner_id=test_attachment.owner
        )
        
        assert response.status_code == 200
        assert response['Content-Type'] == 'text/plain'
        assert 'Content-Disposition' in response
        assert test_attachment.filename in response['Content-Disposition']
    
    def test_blocked_path_traversal_attack(self, test_user):
        """Test path traversal attack is blocked."""
        malicious_path = "../../etc/passwd"
        
        with pytest.raises(ValueError, match="Path traversal"):
            SecureFileDownloadService.validate_and_serve_file(
                filepath=malicious_path,
                filename="passwd",
                user=test_user,
                owner_id=test_user.id
            )
    
    def test_blocked_outside_media_root(self, test_user):
        """Test file outside MEDIA_ROOT is blocked."""
        outside_path = "/tmp/malicious_file.txt"
        
        with pytest.raises(ValueError, match="outside MEDIA_ROOT"):
            SecureFileDownloadService.validate_and_serve_file(
                filepath=outside_path,
                filename="malicious_file.txt",
                user=test_user,
                owner_id=test_user.id
            )
    
    def test_missing_file_handled(self, test_user):
        """Test handling of missing file."""
        missing_path = Path(settings.MEDIA_ROOT) / 'nonexistent.txt'
        
        with pytest.raises(FileNotFoundError):
            SecureFileDownloadService.validate_and_serve_file(
                filepath=str(missing_path),
                filename="nonexistent.txt",
                user=test_user,
                owner_id=test_user.id
            )
    
    def test_ownership_validation(self, test_attachment, test_user, other_user):
        """Test ownership validation is enforced."""
        # Try to access file with different owner_id
        with pytest.raises(PermissionError, match="not authorized"):
            SecureFileDownloadService.validate_and_serve_file(
                filepath=test_attachment.filepath,
                filename=test_attachment.filename,
                user=test_user,
                owner_id=other_user.id  # Different owner
            )


@pytest.mark.django_db
class TestAuditLogging:
    """Test audit logging for file access."""
    
    def test_audit_log_created_on_access(self, test_attachment, test_user, caplog):
        """Test that file access is logged."""
        import logging
        caplog.set_level(logging.INFO)
        
        SecureFileDownloadService.validate_attachment_access(
            attachment_id=test_attachment.id,
            user=test_user
        )
        
        # Check audit log was created
        assert any('File access validation' in record.message for record in caplog.records)
    
    def test_audit_log_on_failure(self, test_attachment, other_user, caplog):
        """Test that failed access attempts are logged."""
        import logging
        caplog.set_level(logging.WARNING)
        
        with pytest.raises(PermissionError):
            SecureFileDownloadService.validate_attachment_access(
                attachment_id=test_attachment.id,
                user=other_user
            )
        
        # Check security warning was logged
        assert any('Unauthorized file access' in record.message for record in caplog.records)


@pytest.mark.django_db
class TestTenantIsolation:
    """Test multi-tenant isolation enforcement."""
    
    def test_tenant_context_validated(self, test_attachment, test_user, other_tenant):
        """Test tenant context is validated."""
        # Change user's tenant to other_tenant
        PeopleTenant.objects.filter(people=test_user).update(tenant=other_tenant)
        
        with pytest.raises(PermissionError):
            SecureFileDownloadService.validate_attachment_access(
                attachment_id=test_attachment.id,
                user=test_user
            )
    
    def test_cross_tenant_access_blocked(self, test_attachment, other_user):
        """Test users from different tenants cannot access files."""
        with pytest.raises(PermissionError, match="not authorized"):
            SecureFileDownloadService.validate_attachment_access(
                attachment_id=test_attachment.id,
                user=other_user
            )
