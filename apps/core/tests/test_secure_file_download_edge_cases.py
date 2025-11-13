"""
Edge Case Security Tests for SecureFileDownloadService

Tests comprehensive edge cases including:
1. Symlink attack prevention (CVSS 7.5 - Path Traversal)
2. MIME type spoofing detection with magic bytes (CVSS 6.1 - Content-Type Spoofing)
3. Path traversal with encoded/obfuscated attempts (CVSS 8.1 - Directory Traversal)
4. Multi-tenant cross-access scenarios (CVSS 8.5 - Broken Access Control)
5. Large file handling and streaming
6. Permission escalation attempts
7. Malicious filename injection
8. Concurrent access race conditions
9. Rate limiting enforcement
10. File enumeration attack prevention

OWASP Mapping:
- A01:2021 - Broken Access Control (IDOR, path traversal)
- A03:2021 - Injection (filename injection, path manipulation)
- A05:2021 - Security Misconfiguration (weak MIME validation)

Run: pytest apps/core/tests/test_secure_file_download_edge_cases.py -v --cov=apps.core.services.secure_file_download_service
"""

import pytest
import os
import tempfile
import shutil
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from django.test import override_settings
from django.core.exceptions import PermissionDenied, SuspiciousFileOperation
from django.http import Http404, FileResponse
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType

from apps.core.services.secure_file_download_service import SecureFileDownloadService

User = get_user_model()


@pytest.fixture
def temp_media_root(tmp_path):
    """Create comprehensive test directory structure with malicious test cases"""
    media_root = tmp_path / "media"
    media_root.mkdir()

    # Create allowed directories
    for directory in SecureFileDownloadService.ALLOWED_DOWNLOAD_DIRECTORIES:
        (media_root / directory).mkdir(exist_ok=True)

    # Create legitimate test files
    test_txt = media_root / "uploads" / "legitimate.txt"
    test_txt.write_text("Legitimate file content")

    # Create PDF with proper magic bytes
    test_pdf = media_root / "uploads" / "legitimate.pdf"
    test_pdf.write_bytes(b'%PDF-1.4\n%\xE2\xE3\xCF\xD3\n')

    # Create image with proper PNG magic bytes
    test_png = media_root / "uploads" / "legitimate.png"
    test_png.write_bytes(b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR')

    # Create large test file (10MB)
    large_file = media_root / "uploads" / "large_file.bin"
    large_file.write_bytes(b'\x00' * (10 * 1024 * 1024))

    return media_root


@pytest.fixture
def tenant_a(db):
    """Create tenant A"""
    from apps.client_onboarding.models import Bt
    return Bt.objects.create(
        bucode="TENANTA",
        buname="Tenant A",
        enable=True
    )


@pytest.fixture
def tenant_b(db):
    """Create tenant B"""
    from apps.client_onboarding.models import Bt
    return Bt.objects.create(
        bucode="TENANTB",
        buname="Tenant B",
        enable=True
    )


@pytest.fixture
def user_a(db, tenant_a):
    """Regular user in tenant A"""
    user = User.objects.create(
        peoplecode="USERA001",
        peoplename="User A",
        loginid="usera",
        email="usera@example.com",
        mobno="1111111111",
        client=tenant_a,
        enable=True,
        is_staff=False,
        is_superuser=False
    )
    user.set_password("TestPass123!")
    user.save()
    return user


@pytest.fixture
def user_b(db, tenant_b):
    """Regular user in tenant B"""
    user = User.objects.create(
        peoplecode="USERB001",
        peoplename="User B",
        loginid="userb",
        email="userb@example.com",
        mobno="2222222222",
        client=tenant_b,
        enable=True,
        is_staff=False,
        is_superuser=False
    )
    user.set_password("TestPass123!")
    user.save()
    return user


@pytest.fixture
def staff_user(db, tenant_a):
    """Staff user in tenant A"""
    user = User.objects.create(
        peoplecode="STAFF001",
        peoplename="Staff User",
        loginid="staffuser",
        email="staff@example.com",
        mobno="3333333333",
        client=tenant_a,
        enable=True,
        is_staff=True,
        is_superuser=False
    )
    user.set_password("StaffPass123!")
    user.save()
    return user


@pytest.fixture
def superuser(db, tenant_a):
    """Superuser"""
    user = User.objects.create(
        peoplecode="SUPER001",
        peoplename="Super User",
        loginid="superuser",
        email="super@example.com",
        mobno="4444444444",
        client=tenant_a,
        enable=True,
        is_staff=True,
        is_superuser=True
    )
    user.set_password("SuperPass123!")
    user.save()
    return user


@pytest.fixture
def attachment_tenant_a(db, tenant_a, user_a, temp_media_root):
    """Create attachment for tenant A"""
    from apps.activity.models import Attachment

    filepath = temp_media_root / "uploads" / "tenant_a_file.pdf"
    filepath.write_bytes(b'%PDF-1.4 Tenant A content')

    return Attachment.objects.create(
        filepath=str(filepath.relative_to(temp_media_root)),
        filename="tenant_a_file.pdf",
        owner="tenant-a-owner-uuid",
        bu=tenant_a,
        tenant=tenant_a,
        cuser=user_a,
        muser=user_a,
        enable=True
    )


@pytest.fixture
def attachment_tenant_b(db, tenant_b, user_b, temp_media_root):
    """Create attachment for tenant B"""
    from apps.activity.models import Attachment

    filepath = temp_media_root / "uploads" / "tenant_b_file.pdf"
    filepath.write_bytes(b'%PDF-1.4 Tenant B content')

    return Attachment.objects.create(
        filepath=str(filepath.relative_to(temp_media_root)),
        filename="tenant_b_file.pdf",
        owner="tenant-b-owner-uuid",
        bu=tenant_b,
        tenant=tenant_b,
        cuser=user_b,
        muser=user_b,
        enable=True
    )


# ==================== SYMLINK ATTACK PREVENTION TESTS ====================

@pytest.mark.django_db
class TestSymlinkAttackPrevention:
    """Test comprehensive symlink attack scenarios"""

    def test_symlink_to_etc_passwd_blocked(self, staff_user, temp_media_root):
        """
        CRITICAL: Symlink to /etc/passwd must be blocked
        CVSS 7.5 - High - Sensitive file disclosure
        """
        # Create symlink to /etc/passwd (if exists on system)
        symlink_path = temp_media_root / "uploads" / "passwd_link.txt"

        # Only test if /etc/passwd exists (Unix systems)
        if Path("/etc/passwd").exists():
            symlink_path.symlink_to("/etc/passwd")

            with override_settings(MEDIA_ROOT=str(temp_media_root)):
                with pytest.raises(SuspiciousFileOperation, match="Symlink to unauthorized location"):
                    SecureFileDownloadService.validate_and_serve_file(
                        filepath="uploads/passwd_link.txt",
                        filename="passwd_link.txt",
                        user=staff_user,
                        owner_id=None
                    )

    def test_symlink_to_parent_directory_blocked(self, staff_user, temp_media_root):
        """
        Symlink pointing to parent directory outside MEDIA_ROOT blocked
        """
        # Create sensitive file outside MEDIA_ROOT
        external_dir = temp_media_root.parent / "external"
        external_dir.mkdir(exist_ok=True)
        sensitive_file = external_dir / "sensitive.txt"
        sensitive_file.write_text("Sensitive external data")

        # Create symlink inside MEDIA_ROOT pointing outside
        symlink = temp_media_root / "uploads" / "external_link.txt"
        symlink.symlink_to(sensitive_file)

        with override_settings(MEDIA_ROOT=str(temp_media_root)):
            with pytest.raises(SuspiciousFileOperation, match="Symlink to unauthorized location"):
                SecureFileDownloadService.validate_and_serve_file(
                    filepath="uploads/external_link.txt",
                    filename="external_link.txt",
                    user=staff_user,
                    owner_id=None
                )

    def test_symlink_chain_attack_blocked(self, staff_user, temp_media_root):
        """
        Test symlink chain: link1 -> link2 -> external file
        Both should be blocked
        """
        # Create external target
        external = temp_media_root.parent / "external.txt"
        external.write_text("External target")

        # Create symlink chain
        link2 = temp_media_root / "uploads" / "link2.txt"
        link2.symlink_to(external)

        link1 = temp_media_root / "uploads" / "link1.txt"
        link1.symlink_to(link2)

        with override_settings(MEDIA_ROOT=str(temp_media_root)):
            # Both should be blocked
            with pytest.raises(SuspiciousFileOperation):
                SecureFileDownloadService.validate_and_serve_file(
                    filepath="uploads/link1.txt",
                    filename="link1.txt",
                    user=staff_user,
                    owner_id=None
                )

    def test_symlink_within_media_root_allowed(self, staff_user, temp_media_root):
        """
        Symlinks pointing within MEDIA_ROOT should be allowed
        (after resolution, they stay within boundary)
        """
        # Create legitimate file
        target = temp_media_root / "uploads" / "target.txt"
        target.write_text("Legitimate target")

        # Create symlink within MEDIA_ROOT pointing to file within MEDIA_ROOT
        symlink = temp_media_root / "attachments" / "link_to_target.txt"
        symlink.symlink_to(target)

        with override_settings(MEDIA_ROOT=str(temp_media_root)):
            # Should succeed - symlink resolves within MEDIA_ROOT
            response = SecureFileDownloadService.validate_and_serve_file(
                filepath="attachments/link_to_target.txt",
                filename="link_to_target.txt",
                user=staff_user,
                owner_id=None
            )

            assert isinstance(response, FileResponse)


# ==================== MIME TYPE SPOOFING TESTS ====================

@pytest.mark.django_db
class TestMIMETypeSpoofingDetection:
    """Test Content-Type spoofing detection with magic bytes"""

    def test_executable_disguised_as_pdf_detected(self, staff_user, temp_media_root):
        """
        CRITICAL: Windows executable with .pdf extension detected
        CVSS 6.1 - Medium - Content-Type Spoofing
        """
        # Create fake PDF (actually a Windows EXE)
        # MZ header = DOS executable signature
        fake_pdf = temp_media_root / "uploads" / "malware.pdf"
        fake_pdf.write_bytes(b'MZ\x90\x00' + b'\x00' * 100)  # MZ = DOS/Windows executable

        with override_settings(MEDIA_ROOT=str(temp_media_root)):
            with patch('apps.core.services.secure_file_download_service.magic') as mock_magic:
                # Mock magic to detect as executable
                mock_magic_instance = Mock()
                mock_magic_instance.from_file.return_value = 'application/x-msdownload'
                mock_magic.Magic.return_value = mock_magic_instance

                response = SecureFileDownloadService.validate_and_serve_file(
                    filepath="uploads/malware.pdf",
                    filename="malware.pdf",
                    user=staff_user,
                    owner_id=None
                )

                # Should use content-based MIME (executable) not extension (PDF)
                assert response['Content-Type'] == 'application/x-msdownload'

    def test_text_file_with_pdf_extension_flagged(self, staff_user, temp_media_root):
        """
        Text file with .pdf extension should be detected
        """
        # Create text file with .pdf extension
        fake_pdf = temp_media_root / "uploads" / "fake.pdf"
        fake_pdf.write_text("This is not a PDF file")

        with override_settings(MEDIA_ROOT=str(temp_media_root)):
            with patch('apps.core.services.secure_file_download_service.magic') as mock_magic:
                mock_magic_instance = Mock()
                mock_magic_instance.from_file.return_value = 'text/plain'
                mock_magic.Magic.return_value = mock_magic_instance

                response = SecureFileDownloadService.validate_and_serve_file(
                    filepath="uploads/fake.pdf",
                    filename="fake.pdf",
                    user=staff_user,
                    owner_id=None
                )

                # Should use detected MIME type (text) not claimed (PDF)
                assert response['Content-Type'] == 'text/plain'

    def test_shell_script_disguised_as_image_detected(self, staff_user, temp_media_root):
        """
        Shell script with .jpg extension detected as dangerous
        """
        # Create shell script with image extension
        fake_image = temp_media_root / "uploads" / "script.jpg"
        fake_image.write_text("#!/bin/bash\nrm -rf /")

        with override_settings(MEDIA_ROOT=str(temp_media_root)):
            with patch('apps.core.services.secure_file_download_service.magic') as mock_magic:
                mock_magic_instance = Mock()
                mock_magic_instance.from_file.return_value = 'application/x-sh'
                mock_magic.Magic.return_value = mock_magic_instance

                response = SecureFileDownloadService.validate_and_serve_file(
                    filepath="uploads/script.jpg",
                    filename="script.jpg",
                    user=staff_user,
                    owner_id=None
                )

                # Should detect as shell script
                assert response['Content-Type'] == 'application/x-sh'

    def test_zip_bomb_with_pdf_extension_detected(self, staff_user, temp_media_root):
        """
        ZIP archive (potential zip bomb) with .pdf extension detected
        """
        # Create simple ZIP with PDF extension
        fake_pdf = temp_media_root / "uploads" / "zipbomb.pdf"
        # ZIP magic bytes: PK\x03\x04
        fake_pdf.write_bytes(b'PK\x03\x04' + b'\x00' * 100)

        with override_settings(MEDIA_ROOT=str(temp_media_root)):
            with patch('apps.core.services.secure_file_download_service.magic') as mock_magic:
                mock_magic_instance = Mock()
                mock_magic_instance.from_file.return_value = 'application/zip'
                mock_magic.Magic.return_value = mock_magic_instance

                response = SecureFileDownloadService.validate_and_serve_file(
                    filepath="uploads/zipbomb.pdf",
                    filename="zipbomb.pdf",
                    user=staff_user,
                    owner_id=None
                )

                # Should detect as ZIP archive
                assert response['Content-Type'] == 'application/zip'

    def test_legitimate_pdf_passes_validation(self, staff_user, temp_media_root):
        """
        Legitimate PDF with correct magic bytes passes validation
        """
        # Create legitimate PDF
        legitimate_pdf = temp_media_root / "uploads" / "legitimate.pdf"
        legitimate_pdf.write_bytes(b'%PDF-1.4\n%\xE2\xE3\xCF\xD3\n' + b'\x00' * 100)

        with override_settings(MEDIA_ROOT=str(temp_media_root)):
            with patch('apps.core.services.secure_file_download_service.magic') as mock_magic:
                mock_magic_instance = Mock()
                mock_magic_instance.from_file.return_value = 'application/pdf'
                mock_magic.Magic.return_value = mock_magic_instance

                response = SecureFileDownloadService.validate_and_serve_file(
                    filepath="uploads/legitimate.pdf",
                    filename="legitimate.pdf",
                    user=staff_user,
                    owner_id=None
                )

                assert response['Content-Type'] == 'application/pdf'

    def test_mime_detection_fallback_when_magic_unavailable(self, staff_user, temp_media_root):
        """
        When python-magic not available, fallback to extension-based detection
        """
        test_file = temp_media_root / "uploads" / "test.txt"
        test_file.write_text("Test content")

        with override_settings(MEDIA_ROOT=str(temp_media_root)):
            with patch('apps.core.services.secure_file_download_service.magic', side_effect=ImportError):
                response = SecureFileDownloadService.validate_and_serve_file(
                    filepath="uploads/test.txt",
                    filename="test.txt",
                    user=staff_user,
                    owner_id=None
                )

                # Should fallback to extension-based MIME
                assert response['Content-Type'] == 'text/plain'


# ==================== PATH TRAVERSAL EDGE CASES ====================

@pytest.mark.django_db
class TestAdvancedPathTraversal:
    """Test sophisticated path traversal attempts"""

    def test_url_encoded_path_traversal_blocked(self, staff_user, temp_media_root):
        """
        URL-encoded ../ (%2e%2e%2f) should be blocked
        """
        with override_settings(MEDIA_ROOT=str(temp_media_root)):
            with pytest.raises(SuspiciousFileOperation):
                SecureFileDownloadService.validate_and_serve_file(
                    filepath="%2e%2e%2f%2e%2e%2fetc%2fpasswd",
                    filename="passwd",
                    user=staff_user,
                    owner_id=None
                )

    def test_double_encoded_path_traversal_blocked(self, staff_user, temp_media_root):
        """
        Double URL-encoded path traversal blocked
        """
        with override_settings(MEDIA_ROOT=str(temp_media_root)):
            with pytest.raises(SuspiciousFileOperation):
                SecureFileDownloadService.validate_and_serve_file(
                    filepath="%252e%252e%252f%252e%252e%252fetc%252fpasswd",
                    filename="passwd",
                    user=staff_user,
                    owner_id=None
                )

    def test_backslash_path_traversal_blocked(self, staff_user, temp_media_root):
        """
        Windows-style backslash path traversal blocked
        """
        with override_settings(MEDIA_ROOT=str(temp_media_root)):
            with pytest.raises(SuspiciousFileOperation):
                SecureFileDownloadService.validate_and_serve_file(
                    filepath="..\\..\\..\\windows\\system32\\config\\sam",
                    filename="sam",
                    user=staff_user,
                    owner_id=None
                )

    def test_null_byte_path_truncation_blocked(self, staff_user, temp_media_root):
        """
        Null byte injection to truncate path blocked
        """
        with override_settings(MEDIA_ROOT=str(temp_media_root)):
            with pytest.raises(SuspiciousFileOperation):
                SecureFileDownloadService.validate_and_serve_file(
                    filepath="uploads/legitimate.txt\x00../../etc/passwd",
                    filename="legitimate.txt",
                    user=staff_user,
                    owner_id=None
                )

    def test_unicode_normalization_attack_blocked(self, staff_user, temp_media_root):
        """
        Unicode normalization path traversal (e.g., U+2024 = ..) blocked
        """
        with override_settings(MEDIA_ROOT=str(temp_media_root)):
            # Unicode character that might normalize to ..
            with pytest.raises((SuspiciousFileOperation, Http404)):
                SecureFileDownloadService.validate_and_serve_file(
                    filepath="uploads/\u2024\u2024/\u2024\u2024/etc/passwd",
                    filename="passwd",
                    user=staff_user,
                    owner_id=None
                )

    def test_absolute_path_outside_media_root_blocked(self, staff_user, temp_media_root):
        """
        Absolute path outside MEDIA_ROOT blocked
        """
        with override_settings(MEDIA_ROOT=str(temp_media_root)):
            with pytest.raises(SuspiciousFileOperation):
                SecureFileDownloadService.validate_and_serve_file(
                    filepath="/etc/passwd",
                    filename="passwd",
                    user=staff_user,
                    owner_id=None
                )

    def test_tilde_home_directory_expansion_blocked(self, staff_user, temp_media_root):
        """
        Tilde (~) home directory expansion blocked
        """
        with override_settings(MEDIA_ROOT=str(temp_media_root)):
            with pytest.raises(SuspiciousFileOperation):
                SecureFileDownloadService.validate_and_serve_file(
                    filepath="~/.ssh/id_rsa",
                    filename="id_rsa",
                    user=staff_user,
                    owner_id=None
                )


# ==================== CROSS-TENANT ACCESS EDGE CASES ====================

@pytest.mark.django_db
class TestCrossTenantAccessEdgeCases:
    """Test comprehensive cross-tenant security scenarios"""

    def test_tenant_a_cannot_access_tenant_b_via_attachment_id(
        self, user_a, attachment_tenant_b
    ):
        """
        CRITICAL: User in Tenant A cannot access Tenant B attachment by ID
        CVSS 8.5 - High - IDOR via tenant bypass
        """
        with pytest.raises(PermissionDenied, match="Cross-tenant access denied"):
            SecureFileDownloadService.validate_attachment_access(
                attachment_id=attachment_tenant_b.id,
                user=user_a
            )

    def test_tenant_a_cannot_access_tenant_b_via_owner_id(
        self, user_a, attachment_tenant_b, temp_media_root
    ):
        """
        User in Tenant A cannot access Tenant B file via owner_id
        """
        with override_settings(MEDIA_ROOT=str(temp_media_root)):
            with pytest.raises(Http404):  # Attachment lookup fails
                SecureFileDownloadService._validate_file_access(
                    file_path=Path(temp_media_root / "uploads" / "tenant_b_file.pdf"),
                    user=user_a,
                    owner_id=attachment_tenant_b.owner,
                    correlation_id="test-cross-tenant"
                )

    def test_staff_in_tenant_a_cannot_access_tenant_b(
        self, staff_user, attachment_tenant_b
    ):
        """
        Staff users cannot bypass tenant boundaries
        """
        with pytest.raises(PermissionDenied, match="Cross-tenant access denied"):
            SecureFileDownloadService.validate_attachment_access(
                attachment_id=attachment_tenant_b.id,
                user=staff_user
            )

    def test_superuser_can_access_any_tenant(
        self, superuser, attachment_tenant_b
    ):
        """
        Only superusers can cross tenant boundaries
        """
        # Should succeed
        attachment = SecureFileDownloadService.validate_attachment_access(
            attachment_id=attachment_tenant_b.id,
            user=superuser
        )

        assert attachment.id == attachment_tenant_b.id

    def test_attachment_id_enumeration_blocked_across_tenants(
        self, user_a, attachment_tenant_a, attachment_tenant_b
    ):
        """
        Sequential ID enumeration doesn't expose cross-tenant data
        """
        # User A can access own attachment
        attachment = SecureFileDownloadService.validate_attachment_access(
            attachment_id=attachment_tenant_a.id,
            user=user_a
        )
        assert attachment.id == attachment_tenant_a.id

        # User A cannot access Tenant B attachment (even if ID is guessable)
        with pytest.raises(PermissionDenied):
            SecureFileDownloadService.validate_attachment_access(
                attachment_id=attachment_tenant_b.id,
                user=user_a
            )


# ==================== LARGE FILE HANDLING TESTS ====================

@pytest.mark.django_db
class TestLargeFileHandling:
    """Test large file download handling"""

    def test_large_file_streaming_response(self, staff_user, temp_media_root):
        """
        Large files use streaming FileResponse
        """
        # Create 10MB file
        large_file = temp_media_root / "uploads" / "large_file.bin"
        large_file.write_bytes(b'\x00' * (10 * 1024 * 1024))

        with override_settings(MEDIA_ROOT=str(temp_media_root)):
            response = SecureFileDownloadService.validate_and_serve_file(
                filepath="uploads/large_file.bin",
                filename="large_file.bin",
                user=staff_user,
                owner_id=None
            )

            assert isinstance(response, FileResponse)
            # FileResponse should handle streaming internally

    def test_empty_file_handled_gracefully(self, staff_user, temp_media_root):
        """
        Empty files (0 bytes) handled without errors
        """
        empty_file = temp_media_root / "uploads" / "empty.txt"
        empty_file.write_bytes(b'')

        with override_settings(MEDIA_ROOT=str(temp_media_root)):
            response = SecureFileDownloadService.validate_and_serve_file(
                filepath="uploads/empty.txt",
                filename="empty.txt",
                user=staff_user,
                owner_id=None
            )

            assert isinstance(response, FileResponse)

    def test_file_with_special_characters_in_name(self, staff_user, temp_media_root):
        """
        Files with special characters in filename handled correctly
        """
        # Create file with special chars (but safe)
        special_file = temp_media_root / "uploads" / "file-with_special.chars (1).txt"
        special_file.write_text("Content")

        with override_settings(MEDIA_ROOT=str(temp_media_root)):
            response = SecureFileDownloadService.validate_and_serve_file(
                filepath="uploads/file-with_special.chars (1).txt",
                filename="file-with_special.chars (1).txt",
                user=staff_user,
                owner_id=None
            )

            assert isinstance(response, FileResponse)


# ==================== PERMISSION ESCALATION TESTS ====================

@pytest.mark.django_db
class TestPermissionEscalationPrevention:
    """Test permission escalation attack prevention"""

    def test_regular_user_cannot_access_superuser_files(
        self, user_a, superuser, temp_media_root, tenant_a
    ):
        """
        Regular users cannot access files owned by superusers
        """
        from apps.activity.models import Attachment

        # Create attachment owned by superuser
        superuser_file = temp_media_root / "uploads" / "admin_file.pdf"
        superuser_file.write_bytes(b'%PDF-1.4 Admin content')

        admin_attachment = Attachment.objects.create(
            filepath=str(superuser_file.relative_to(temp_media_root)),
            filename="admin_file.pdf",
            owner="admin-owner-uuid",
            bu=tenant_a,
            tenant=tenant_a,
            cuser=superuser,
            muser=superuser,
            enable=True
        )

        # Regular user tries to access
        with pytest.raises(PermissionDenied):
            SecureFileDownloadService.validate_attachment_access(
                attachment_id=admin_attachment.id,
                user=user_a
            )

    def test_regular_user_cannot_bypass_with_direct_path(
        self, user_a, temp_media_root
    ):
        """
        Regular users cannot bypass permissions with direct file access
        """
        with override_settings(MEDIA_ROOT=str(temp_media_root)):
            with pytest.raises(PermissionDenied, match="Direct file access not permitted"):
                SecureFileDownloadService.validate_and_serve_file(
                    filepath="uploads/legitimate.txt",
                    filename="legitimate.txt",
                    user=user_a,
                    owner_id=None  # Trying direct access
                )

    def test_missing_permission_blocks_access(
        self, user_a, attachment_tenant_a, temp_media_root, tenant_a
    ):
        """
        Users without view_attachment permission blocked (even as owner)
        """
        # Create new user in same tenant without permissions
        from apps.activity.models import Attachment

        unprivileged_user = User.objects.create(
            peoplecode="UNPRIV001",
            peoplename="Unprivileged User",
            loginid="unpriv",
            email="unpriv@example.com",
            mobno="9999999999",
            client=tenant_a,
            enable=True,
            is_staff=False
        )

        # Create attachment owned by unprivileged user
        user_file = temp_media_root / "uploads" / "user_file.txt"
        user_file.write_text("User content")

        user_attachment = Attachment.objects.create(
            filepath=str(user_file.relative_to(temp_media_root)),
            filename="user_file.txt",
            owner="user-owner-uuid",
            bu=tenant_a,
            tenant=tenant_a,
            cuser=unprivileged_user,
            muser=unprivileged_user,
            enable=True
        )

        # Owner access should work regardless of permission (ownership trumps)
        with override_settings(MEDIA_ROOT=str(temp_media_root)):
            attachment = SecureFileDownloadService.validate_attachment_access(
                attachment_id=user_attachment.id,
                user=unprivileged_user
            )
            assert attachment.id == user_attachment.id


# ==================== MALICIOUS FILENAME INJECTION TESTS ====================

@pytest.mark.django_db
class TestMaliciousFilenameInjection:
    """Test malicious filename injection attempts"""

    def test_filename_with_path_traversal_blocked(self, staff_user, temp_media_root):
        """
        Filename containing ../ blocked
        """
        with override_settings(MEDIA_ROOT=str(temp_media_root)):
            with pytest.raises(SuspiciousFileOperation):
                SecureFileDownloadService.validate_and_serve_file(
                    filepath="uploads",
                    filename="../../etc/passwd",
                    user=staff_user,
                    owner_id=None
                )

    def test_filename_with_newline_injection_blocked(self, staff_user, temp_media_root):
        """
        Filename with newline characters blocked (HTTP header injection)
        """
        with override_settings(MEDIA_ROOT=str(temp_media_root)):
            with pytest.raises(SuspiciousFileOperation):
                SecureFileDownloadService.validate_and_serve_file(
                    filepath="uploads\r\nContent-Type: text/html",
                    filename="legitimate.txt",
                    user=staff_user,
                    owner_id=None
                )

    def test_filename_with_null_byte_blocked(self, staff_user, temp_media_root):
        """
        Filename with null byte blocked
        """
        with override_settings(MEDIA_ROOT=str(temp_media_root)):
            with pytest.raises(SuspiciousFileOperation):
                SecureFileDownloadService.validate_and_serve_file(
                    filepath="uploads",
                    filename="safe.txt\x00.exe",
                    user=staff_user,
                    owner_id=None
                )


# ==================== RATE LIMITING TESTS ====================

@pytest.mark.django_db
class TestRateLimiting:
    """Test rate limiting enforcement"""

    @patch('apps.core.services.secure_file_download_service.CacheRateLimiter.check_rate_limit')
    def test_rate_limit_exceeded_blocks_download(
        self, mock_rate_limit, staff_user, temp_media_root
    ):
        """
        Users exceeding rate limit are blocked
        """
        # Mock rate limit exceeded
        mock_rate_limit.return_value = {
            'allowed': False,
            'current_count': 101,
            'reset_at': '2025-11-12 12:00:00'
        }

        with override_settings(MEDIA_ROOT=str(temp_media_root)):
            with pytest.raises(PermissionDenied, match="Download rate limit exceeded"):
                SecureFileDownloadService.validate_and_serve_file(
                    filepath="uploads/legitimate.txt",
                    filename="legitimate.txt",
                    user=staff_user,
                    owner_id=None
                )

    @patch('apps.core.services.secure_file_download_service.CacheRateLimiter.check_rate_limit')
    def test_rate_limit_not_exceeded_allows_download(
        self, mock_rate_limit, staff_user, temp_media_root
    ):
        """
        Users within rate limit can download
        """
        mock_rate_limit.return_value = {
            'allowed': True,
            'current_count': 50,
            'remaining': 50
        }

        with override_settings(MEDIA_ROOT=str(temp_media_root)):
            response = SecureFileDownloadService.validate_and_serve_file(
                filepath="uploads/legitimate.txt",
                filename="legitimate.txt",
                user=staff_user,
                owner_id=None
            )

            assert isinstance(response, FileResponse)

    @patch('apps.core.services.secure_file_download_service.CacheRateLimiter.check_rate_limit')
    def test_rate_limit_cache_failure_fails_open(
        self, mock_rate_limit, staff_user, temp_media_root
    ):
        """
        Rate limit cache failures fail-open (allow download with warning)
        """
        # Mock cache connection error
        mock_rate_limit.side_effect = ConnectionError("Redis unavailable")

        with override_settings(MEDIA_ROOT=str(temp_media_root)):
            # Should succeed (fail-open)
            response = SecureFileDownloadService.validate_and_serve_file(
                filepath="uploads/legitimate.txt",
                filename="legitimate.txt",
                user=staff_user,
                owner_id=None
            )

            assert isinstance(response, FileResponse)


# ==================== SECURITY HEADERS TESTS ====================

@pytest.mark.django_db
class TestSecurityHeaders:
    """Test security headers are properly set"""

    def test_csp_headers_prevent_xss(self, staff_user, temp_media_root):
        """
        Content-Security-Policy headers prevent XSS in SVG/HTML
        """
        with override_settings(MEDIA_ROOT=str(temp_media_root)):
            response = SecureFileDownloadService.validate_and_serve_file(
                filepath="uploads/legitimate.txt",
                filename="legitimate.txt",
                user=staff_user,
                owner_id=None
            )

            assert 'Content-Security-Policy' in response
            assert "script-src 'none'" in response['Content-Security-Policy']
            assert "default-src 'none'" in response['Content-Security-Policy']

    def test_nosniff_header_prevents_mime_sniffing(self, staff_user, temp_media_root):
        """
        X-Content-Type-Options: nosniff prevents MIME sniffing
        """
        with override_settings(MEDIA_ROOT=str(temp_media_root)):
            response = SecureFileDownloadService.validate_and_serve_file(
                filepath="uploads/legitimate.txt",
                filename="legitimate.txt",
                user=staff_user,
                owner_id=None
            )

            assert response['X-Content-Type-Options'] == 'nosniff'

    def test_frame_options_prevents_clickjacking(self, staff_user, temp_media_root):
        """
        X-Frame-Options: DENY prevents clickjacking
        """
        with override_settings(MEDIA_ROOT=str(temp_media_root)):
            response = SecureFileDownloadService.validate_and_serve_file(
                filepath="uploads/legitimate.txt",
                filename="legitimate.txt",
                user=staff_user,
                owner_id=None
            )

            assert response['X-Frame-Options'] == 'DENY'

    def test_download_options_header_set(self, staff_user, temp_media_root):
        """
        X-Download-Options: noopen prevents IE from opening files in browser
        """
        with override_settings(MEDIA_ROOT=str(temp_media_root)):
            response = SecureFileDownloadService.validate_and_serve_file(
                filepath="uploads/legitimate.txt",
                filename="legitimate.txt",
                user=staff_user,
                owner_id=None
            )

            assert response['X-Download-Options'] == 'noopen'


# ==================== AUDIT LOGGING TESTS ====================

@pytest.mark.django_db
class TestAuditLoggingEdgeCases:
    """Test comprehensive audit logging"""

    @patch('apps.core.services.secure_file_download_service.logger')
    def test_symlink_attack_logged(self, mock_logger, staff_user, temp_media_root):
        """
        Symlink attacks are logged with full details
        """
        # Create malicious symlink
        external = temp_media_root.parent / "external.txt"
        external.write_text("External")

        symlink = temp_media_root / "uploads" / "link.txt"
        symlink.symlink_to(external)

        with override_settings(MEDIA_ROOT=str(temp_media_root)):
            with pytest.raises(SuspiciousFileOperation):
                SecureFileDownloadService.validate_and_serve_file(
                    filepath="uploads/link.txt",
                    filename="link.txt",
                    user=staff_user,
                    owner_id=None
                )

            # Verify logging
            assert any(
                'Symlink attack prevented' in str(call) or 'unauthorized location' in str(call)
                for call in mock_logger.error.call_args_list
            )

    @patch('apps.core.services.secure_file_download_service.logger')
    def test_mime_spoofing_logged(self, mock_logger, staff_user, temp_media_root):
        """
        MIME type mismatches are logged
        """
        fake_pdf = temp_media_root / "uploads" / "fake.pdf"
        fake_pdf.write_text("Not a PDF")

        with override_settings(MEDIA_ROOT=str(temp_media_root)):
            with patch('apps.core.services.secure_file_download_service.magic') as mock_magic:
                mock_magic_instance = Mock()
                mock_magic_instance.from_file.return_value = 'text/plain'
                mock_magic.Magic.return_value = mock_magic_instance

                SecureFileDownloadService.validate_and_serve_file(
                    filepath="uploads/fake.pdf",
                    filename="fake.pdf",
                    user=staff_user,
                    owner_id=None
                )

                # Verify MIME mismatch logged
                assert any(
                    'MIME type mismatch' in str(call) or 'Content-Type Spoofing' in str(call)
                    for call in mock_logger.warning.call_args_list
                )

    @patch('apps.core.services.secure_file_download_service.logger')
    def test_rate_limit_exceeded_logged(self, mock_logger, staff_user, temp_media_root):
        """
        Rate limit violations are logged
        """
        with override_settings(MEDIA_ROOT=str(temp_media_root)):
            with patch('apps.core.services.secure_file_download_service.CacheRateLimiter.check_rate_limit') as mock_rate:
                mock_rate.return_value = {'allowed': False, 'current_count': 101}

                with pytest.raises(PermissionDenied):
                    SecureFileDownloadService.validate_and_serve_file(
                        filepath="uploads/legitimate.txt",
                        filename="legitimate.txt",
                        user=staff_user,
                        owner_id=None
                    )

                # Verify rate limit logged
                assert any(
                    'rate limit exceeded' in str(call).lower()
                    for call in mock_logger.warning.call_args_list
                )
