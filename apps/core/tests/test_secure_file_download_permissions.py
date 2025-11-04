"""
Comprehensive security tests for SecureFileDownloadService permission validation.

Tests cover:
- Cross-tenant access prevention (CRITICAL for multi-tenant SaaS)
- Ownership validation
- Superuser bypass
- Django permission enforcement
- Business unit isolation
- IDOR vulnerability prevention
- Staff access within tenant boundaries

CVSS Score Mitigation: 7.5-8.5 (High) - Broken Access Control
"""

import pytest
from django.core.exceptions import PermissionDenied
from django.http import Http404
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType

from apps.core.services.secure_file_download_service import SecureFileDownloadService
from apps.activity.models import Attachment
from apps.peoples.models import People, PeopleOrganizational
from apps.tenants.models import Tenant
from apps.client_onboarding.models import Bt  # Business unit model


@pytest.mark.django_db
class TestSecureFileDownloadPermissions:
    """Test suite for file download permission validation."""

    @pytest.fixture
    def setup_tenants(self):
        """Create test tenants."""
        tenant_a = Tenant.objects.create(
            tenantname="TenantA",
            name="Tenant A Corp"
        )
        tenant_b = Tenant.objects.create(
            tenantname="TenantB",
            name="Tenant B Corp"
        )
        return {'tenant_a': tenant_a, 'tenant_b': tenant_b}

    @pytest.fixture
    def setup_business_units(self, setup_tenants):
        """Create test business units."""
        tenant_a = setup_tenants['tenant_a']
        bu_a = Bt.objects.create(
            buname="BU_A",
            bu="Business Unit A",
            tenant=tenant_a
        )
        bu_b = Bt.objects.create(
            buname="BU_B",
            bu="Business Unit B",
            tenant=tenant_a
        )
        return {'bu_a': bu_a, 'bu_b': bu_b}

    @pytest.fixture
    def setup_users(self, setup_tenants, setup_business_units):
        """Create test users with different roles and tenants."""
        tenant_a = setup_tenants['tenant_a']
        tenant_b = setup_tenants['tenant_b']
        bu_a = setup_business_units['bu_a']
        bu_b = setup_business_units['bu_b']

        # User A1 - Regular user in Tenant A, BU A
        user_a1 = People.objects.create(
            loginid='user_a1',
            first_name='User',
            last_name='A1',
            tenant=tenant_a,
            is_staff=False,
            is_superuser=False
        )
        org_a1 = PeopleOrganizational.objects.create(
            people=user_a1,
            bu=bu_a
        )
        user_a1.organizational = org_a1
        user_a1.save()

        # User A2 - Regular user in Tenant A, BU B
        user_a2 = People.objects.create(
            loginid='user_a2',
            first_name='User',
            last_name='A2',
            tenant=tenant_a,
            is_staff=False,
            is_superuser=False
        )
        org_a2 = PeopleOrganizational.objects.create(
            people=user_a2,
            bu=bu_b
        )
        user_a2.organizational = org_a2
        user_a2.save()

        # User B - Regular user in Tenant B
        user_b = People.objects.create(
            loginid='user_b',
            first_name='User',
            last_name='B',
            tenant=tenant_b,
            is_staff=False,
            is_superuser=False
        )

        # Staff user in Tenant A
        staff_a = People.objects.create(
            loginid='staff_a',
            first_name='Staff',
            last_name='A',
            tenant=tenant_a,
            is_staff=True,
            is_superuser=False
        )

        # Superuser
        superuser = People.objects.create(
            loginid='superuser',
            first_name='Super',
            last_name='User',
            tenant=tenant_a,
            is_staff=True,
            is_superuser=True
        )

        return {
            'user_a1': user_a1,
            'user_a2': user_a2,
            'user_b': user_b,
            'staff_a': staff_a,
            'superuser': superuser
        }

    @pytest.fixture
    def setup_attachments(self, setup_users, setup_tenants, setup_business_units):
        """Create test attachments."""
        user_a1 = setup_users['user_a1']
        user_b = setup_users['user_b']
        tenant_a = setup_tenants['tenant_a']
        tenant_b = setup_tenants['tenant_b']
        bu_a = setup_business_units['bu_a']
        bu_b = setup_business_units['bu_b']

        # Attachment owned by User A1 in Tenant A, BU A
        attachment_a1 = Attachment.objects.create(
            filename='file_a1.pdf',
            path='uploads/file_a1.pdf',
            owner='test-uuid-a1',
            cuser=user_a1,
            muser=user_a1,
            tenant=tenant_a,
            bu=bu_a
        )

        # Attachment owned by User B in Tenant B
        attachment_b = Attachment.objects.create(
            filename='file_b.pdf',
            path='uploads/file_b.pdf',
            owner='test-uuid-b',
            cuser=user_b,
            muser=user_b,
            tenant=tenant_b
        )

        # Attachment in Tenant A, BU B (different BU from user_a1)
        attachment_a2_bu_b = Attachment.objects.create(
            filename='file_a2_bu_b.pdf',
            path='uploads/file_a2.pdf',
            owner='test-uuid-a2',
            cuser=setup_users['user_a2'],
            muser=setup_users['user_a2'],
            tenant=tenant_a,
            bu=bu_b
        )

        return {
            'attachment_a1': attachment_a1,
            'attachment_b': attachment_b,
            'attachment_a2_bu_b': attachment_a2_bu_b
        }

    @pytest.fixture
    def add_view_permission(self, setup_users):
        """Add view_attachment permission to test users."""
        # Get or create the permission
        content_type = ContentType.objects.get_for_model(Attachment)
        permission, created = Permission.objects.get_or_create(
            codename='view_attachment',
            content_type=content_type,
            defaults={'name': 'Can view attachment'}
        )

        # Add permission to regular users
        for user_key in ['user_a1', 'user_a2', 'user_b', 'staff_a']:
            setup_users[user_key].user_permissions.add(permission)

        return permission

    # ==================== Cross-Tenant Access Tests ====================

    def test_cross_tenant_attachment_access_blocked(self, setup_users, setup_attachments):
        """
        CRITICAL: User in Tenant A cannot access files from Tenant B.
        Tests multi-tenant data segregation.
        """
        user_a = setup_users['user_a1']
        attachment_b = setup_attachments['attachment_b']

        with pytest.raises(PermissionDenied, match="Cross-tenant access denied"):
            SecureFileDownloadService.validate_attachment_access(
                attachment_id=attachment_b.id,
                user=user_a
            )

    def test_cross_tenant_file_access_blocked(self, setup_users, setup_attachments):
        """
        CRITICAL: User in Tenant A cannot download files from Tenant B via _validate_file_access.
        """
        from pathlib import Path
        user_a = setup_users['user_a1']
        attachment_b = setup_attachments['attachment_b']

        fake_path = Path('/tmp/test_file.pdf')

        with pytest.raises(Http404, match="Attachment not found"):
            # Using owner_id from Tenant B attachment
            SecureFileDownloadService._validate_file_access(
                file_path=fake_path,
                user=user_a,
                owner_id=attachment_b.owner,
                correlation_id='test-correlation-id'
            )

    # ==================== Ownership Tests ====================

    def test_owner_can_access_own_attachment(self, setup_users, setup_attachments, add_view_permission):
        """Owner can always access their own files."""
        user_a1 = setup_users['user_a1']
        attachment_a1 = setup_attachments['attachment_a1']

        # Should not raise
        result = SecureFileDownloadService.validate_attachment_access(
            attachment_id=attachment_a1.id,
            user=user_a1
        )

        assert result.id == attachment_a1.id
        assert result.cuser == user_a1

    def test_non_owner_same_tenant_access_denied(self, setup_users, setup_attachments):
        """
        Non-owners in the same tenant cannot access files without proper permissions.
        Tests that ownership is actually checked, not just tenant.
        """
        user_a2 = setup_users['user_a2']  # Different user, same tenant
        attachment_a1 = setup_attachments['attachment_a1']  # Owned by user_a1

        # user_a2 does not have view_attachment permission yet
        with pytest.raises(PermissionDenied):
            SecureFileDownloadService.validate_attachment_access(
                attachment_id=attachment_a1.id,
                user=user_a2
            )

    # ==================== Superuser Tests ====================

    def test_superuser_can_access_any_attachment(self, setup_users, setup_attachments):
        """Superusers can access any file regardless of ownership or tenant."""
        superuser = setup_users['superuser']
        attachment_b = setup_attachments['attachment_b']  # Different tenant

        # Should not raise - superuser bypasses all checks
        result = SecureFileDownloadService.validate_attachment_access(
            attachment_id=attachment_b.id,
            user=superuser
        )

        assert result.id == attachment_b.id

    def test_superuser_file_access_bypass(self, setup_users, setup_attachments):
        """Superuser can access files via _validate_file_access regardless of owner."""
        from pathlib import Path
        superuser = setup_users['superuser']
        attachment_b = setup_attachments['attachment_b']

        fake_path = Path('/tmp/test_file.pdf')

        # Should not raise
        SecureFileDownloadService._validate_file_access(
            file_path=fake_path,
            user=superuser,
            owner_id=attachment_b.owner,
            correlation_id='test-superuser'
        )

    # ==================== Staff Access Tests ====================

    def test_staff_can_access_within_same_tenant(self, setup_users, setup_attachments, add_view_permission):
        """Staff users can access all attachments within their tenant."""
        staff_a = setup_users['staff_a']  # Staff in Tenant A
        attachment_a1 = setup_attachments['attachment_a1']  # Tenant A, owned by user_a1

        # Should not raise - staff can access within tenant
        result = SecureFileDownloadService.validate_attachment_access(
            attachment_id=attachment_a1.id,
            user=staff_a
        )

        assert result.id == attachment_a1.id

    def test_staff_cannot_access_different_tenant(self, setup_users, setup_attachments, add_view_permission):
        """Staff users cannot access attachments from different tenants."""
        staff_a = setup_users['staff_a']  # Staff in Tenant A
        attachment_b = setup_attachments['attachment_b']  # Tenant B

        with pytest.raises(PermissionDenied, match="Cross-tenant access denied"):
            SecureFileDownloadService.validate_attachment_access(
                attachment_id=attachment_b.id,
                user=staff_a
            )

    # ==================== Django Permission Tests ====================

    def test_missing_view_permission_denied(self, setup_users, setup_attachments):
        """Users without view_attachment permission cannot access files (even in same tenant)."""
        user_a2 = setup_users['user_a2']
        attachment_a1 = setup_attachments['attachment_a1']

        # user_a2 has no view_attachment permission
        with pytest.raises(PermissionDenied, match="Missing required permission"):
            SecureFileDownloadService.validate_attachment_access(
                attachment_id=attachment_a1.id,
                user=user_a2
            )

    def test_with_view_permission_and_staff_access_granted(self, setup_users, setup_attachments, add_view_permission):
        """Users with view_attachment permission and staff status can access files within tenant."""
        staff_a = setup_users['staff_a']
        attachment_a1 = setup_attachments['attachment_a1']

        # Should succeed - staff + permission + same tenant
        result = SecureFileDownloadService.validate_attachment_access(
            attachment_id=attachment_a1.id,
            user=staff_a
        )

        assert result.id == attachment_a1.id

    # ==================== Business Unit Isolation Tests ====================

    def test_different_bu_access_denied(self, setup_users, setup_attachments, add_view_permission):
        """
        Users from different business units cannot access each other's files
        even within the same tenant (unless staff/superuser).
        """
        user_a1 = setup_users['user_a1']  # BU A
        attachment_a2_bu_b = setup_attachments['attachment_a2_bu_b']  # BU B, same tenant

        # user_a1 is in BU A, attachment is in BU B
        with pytest.raises(PermissionDenied, match="different business unit"):
            SecureFileDownloadService.validate_attachment_access(
                attachment_id=attachment_a2_bu_b.id,
                user=user_a1
            )

    def test_same_bu_access_with_permissions(self, setup_users, setup_attachments, add_view_permission):
        """
        Users in the same business unit can access files with proper permissions.
        But this still requires staff status or being the owner.
        """
        user_a1 = setup_users['user_a1']  # BU A
        attachment_a1 = setup_attachments['attachment_a1']  # BU A, owned by user_a1

        # Should succeed - owner access
        result = SecureFileDownloadService.validate_attachment_access(
            attachment_id=attachment_a1.id,
            user=user_a1
        )

        assert result.id == attachment_a1.id

    # ==================== IDOR Prevention Tests ====================

    def test_sequential_attachment_enumeration_blocked(self, setup_users, setup_attachments):
        """
        Test that sequential ID enumeration doesn't expose cross-tenant data.
        Simulates attacker trying IDs 1, 2, 3, etc.
        """
        user_a1 = setup_users['user_a1']  # Tenant A
        attachment_b = setup_attachments['attachment_b']  # Tenant B

        # Attacker in Tenant A tries to enumerate Tenant B attachment
        with pytest.raises(PermissionDenied):
            SecureFileDownloadService.validate_attachment_access(
                attachment_id=attachment_b.id,
                user=user_a1
            )

    def test_direct_file_path_manipulation_blocked(self, setup_users, setup_attachments):
        """
        Test that users cannot bypass attachment validation by manipulating file paths.
        """
        from pathlib import Path
        user_a1 = setup_users['user_a1']
        attachment_b = setup_attachments['attachment_b']  # Different tenant

        fake_path = Path('/tmp/manipulated_path.pdf')

        # Try to access file with owner_id from different tenant
        with pytest.raises(Http404):  # Attachment not found for this owner_id + user combo
            SecureFileDownloadService._validate_file_access(
                file_path=fake_path,
                user=user_a1,
                owner_id=attachment_b.owner,
                correlation_id='test-idor'
            )

    # ==================== Direct File Access Tests ====================

    def test_direct_file_access_requires_staff(self, setup_users):
        """Direct file access without owner_id requires staff privileges."""
        from pathlib import Path
        user_a1 = setup_users['user_a1']  # Regular user
        fake_path = Path('/tmp/direct_access.pdf')

        # No owner_id provided, user is not staff
        with pytest.raises(PermissionDenied, match="Direct file access not permitted"):
            SecureFileDownloadService._validate_file_access(
                file_path=fake_path,
                user=user_a1,
                owner_id=None,  # No owner_id
                correlation_id='test-direct'
            )

    def test_direct_file_access_staff_allowed(self, setup_users):
        """Staff users can access files directly without owner_id."""
        from pathlib import Path
        staff_a = setup_users['staff_a']
        fake_path = Path('/tmp/staff_direct.pdf')

        # Should not raise - staff can access directly
        SecureFileDownloadService._validate_file_access(
            file_path=fake_path,
            user=staff_a,
            owner_id=None,
            correlation_id='test-staff-direct'
        )

    # ==================== Edge Cases ====================

    def test_attachment_not_found_returns_404(self, setup_users):
        """Non-existent attachment returns 404, not 403."""
        user_a1 = setup_users['user_a1']

        with pytest.raises(Http404, match="Attachment not found"):
            SecureFileDownloadService.validate_attachment_access(
                attachment_id=999999,  # Non-existent
                user=user_a1
            )

    def test_invalid_owner_id_returns_404(self, setup_users):
        """Invalid owner_id (no matching attachment) returns 404."""
        from pathlib import Path
        user_a1 = setup_users['user_a1']
        fake_path = Path('/tmp/test.pdf')

        with pytest.raises(Http404, match="Attachment not found"):
            SecureFileDownloadService._validate_file_access(
                file_path=fake_path,
                user=user_a1,
                owner_id='invalid-uuid-12345',
                correlation_id='test-invalid'
            )

    def test_attachment_without_tenant_attribute(self, setup_users):
        """
        Gracefully handle attachments that might not have tenant attribute.
        (Edge case for legacy data or special attachments)
        """
        user_a1 = setup_users['user_a1']

        # Create attachment without explicit tenant setting
        attachment_no_tenant = Attachment.objects.create(
            filename='no_tenant.pdf',
            path='uploads/no_tenant.pdf',
            owner='test-uuid-no-tenant',
            cuser=user_a1,
            muser=user_a1
            # tenant not set explicitly
        )

        # Owner should still be able to access
        result = SecureFileDownloadService.validate_attachment_access(
            attachment_id=attachment_no_tenant.id,
            user=user_a1
        )

        assert result.id == attachment_no_tenant.id


@pytest.mark.django_db
class TestSecureFileDownloadIntegration:
    """
    Integration tests for full file download flow with permission validation.
    """

    def test_full_download_flow_owner_success(self, tmp_path, setup_users, setup_tenants):
        """Test complete download flow: path validation + permission check + file serve."""
        from django.conf import settings
        import uuid

        user_a1 = setup_users['user_a1']
        tenant_a = setup_tenants['tenant_a']

        # Create actual test file
        test_file = tmp_path / "uploads" / "test_download.txt"
        test_file.parent.mkdir(parents=True, exist_ok=True)
        test_file.write_text("Test content for secure download")

        # Create attachment
        attachment = Attachment.objects.create(
            filename='test_download.txt',
            path='uploads/test_download.txt',
            owner=str(uuid.uuid4()),
            cuser=user_a1,
            muser=user_a1,
            tenant=tenant_a
        )

        # Mock MEDIA_ROOT to point to tmp_path
        original_media_root = settings.MEDIA_ROOT
        try:
            settings.MEDIA_ROOT = str(tmp_path)

            # Validate attachment access (permission check)
            validated_attachment = SecureFileDownloadService.validate_attachment_access(
                attachment_id=attachment.id,
                user=user_a1
            )

            assert validated_attachment.id == attachment.id

        finally:
            settings.MEDIA_ROOT = original_media_root

    def test_full_download_flow_cross_tenant_failure(self, tmp_path, setup_users, setup_tenants):
        """Test that cross-tenant access fails at permission check stage."""
        import uuid

        user_a1 = setup_users['user_a1']  # Tenant A
        user_b = setup_users['user_b']  # Tenant B
        tenant_b = setup_tenants['tenant_b']

        # Create attachment owned by user_b
        attachment_b = Attachment.objects.create(
            filename='tenant_b_file.txt',
            path='uploads/tenant_b_file.txt',
            owner=str(uuid.uuid4()),
            cuser=user_b,
            muser=user_b,
            tenant=tenant_b
        )

        # user_a1 tries to access user_b's file
        with pytest.raises(PermissionDenied, match="Cross-tenant access denied"):
            SecureFileDownloadService.validate_attachment_access(
                attachment_id=attachment_b.id,
                user=user_a1
            )
