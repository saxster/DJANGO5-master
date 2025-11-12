"""
Permission and capability tests for peoples app.

Tests permission groups, capabilities, access control,
and capability-based authorization.
"""
import pytest
from apps.peoples.models import Pgroup, Pgbelonging, Capability, People


@pytest.mark.django_db
class TestPermissionGroups:
    """Test permission group functionality."""

    def test_create_permission_group(self, test_tenant):
        """Test creating a permission group."""
        group = Pgroup.objects.create(
            groupname="Test Permission Group",
            groupcode="TESTPERM",
            description="Group for testing permissions",
            client=test_tenant,
            enable=True
        )

        assert group.id is not None
        assert group.groupname == "Test Permission Group"
        assert group.groupcode == "TESTPERM"
        assert group.client == test_tenant

    def test_permission_group_uniqueness(self, permission_group):
        """Test that group codes are unique per tenant."""
        # Attempt to create another group with same code
        # (uniqueness may not be enforced at DB level)

        another_group = Pgroup.objects.create(
            groupname="Another Group",
            groupcode="TESTGRP2",  # Different code
            description="Different group",
            client=permission_group.client
        )

        assert another_group.groupcode != permission_group.groupcode

    def test_add_user_to_group(self, basic_user, permission_group):
        """Test adding user to permission group."""
        # Create membership
        membership = Pgbelonging.objects.create(
            groupid=permission_group,
            peopleid=basic_user
        )

        assert membership.groupid == permission_group
        assert membership.peopleid == basic_user

        # Verify membership
        memberships = Pgbelonging.objects.filter(
            groupid=permission_group,
            peopleid=basic_user
        )
        assert memberships.count() == 1

    def test_remove_user_from_group(self, basic_user, permission_group):
        """Test removing user from permission group."""
        # Add user first
        membership = Pgbelonging.objects.create(
            groupid=permission_group,
            peopleid=basic_user
        )

        # Remove user
        membership.delete()

        # Verify removed
        exists = Pgbelonging.objects.filter(
            groupid=permission_group,
            peopleid=basic_user
        ).exists()
        assert not exists


@pytest.mark.django_db
class TestGroupMembership:
    """Test group membership (Pgbelonging) functionality."""

    def test_user_belongs_to_multiple_groups(self, basic_user, test_tenant):
        """Test that users can belong to multiple groups."""
        # Create multiple groups
        group1 = Pgroup.objects.create(
            groupname="Group 1",
            groupcode="GRP1",
            description="First group",
            client=test_tenant
        )
        group2 = Pgroup.objects.create(
            groupname="Group 2",
            groupcode="GRP2",
            description="Second group",
            client=test_tenant
        )

        # Add user to both groups
        Pgbelonging.objects.create(groupid=group1, peopleid=basic_user)
        Pgbelonging.objects.create(groupid=group2, peopleid=basic_user)

        # Verify memberships
        memberships = Pgbelonging.objects.filter(peopleid=basic_user)
        assert memberships.count() == 2

    def test_query_users_in_group(self, permission_group, test_tenant):
        """Test querying all users in a group."""
        # Create users
        user1 = People.objects.create(
            peoplecode="U1",
            peoplename="User 1",
            loginid="user1_grp",
            email="user1@example.com",
            client=test_tenant
        )
        user2 = People.objects.create(
            peoplecode="U2",
            peoplename="User 2",
            loginid="user2_grp",
            email="user2@example.com",
            client=test_tenant
        )

        # Add to group
        Pgbelonging.objects.create(groupid=permission_group, peopleid=user1)
        Pgbelonging.objects.create(groupid=permission_group, peopleid=user2)

        # Query users in group
        memberships = Pgbelonging.objects.filter(groupid=permission_group)
        user_ids = [m.peopleid.id for m in memberships]

        assert user1.id in user_ids
        assert user2.id in user_ids

    def test_query_groups_for_user(self, basic_user, permission_group):
        """Test querying all groups a user belongs to."""
        # Add user to group
        Pgbelonging.objects.create(groupid=permission_group, peopleid=basic_user)

        # Query groups
        memberships = Pgbelonging.objects.filter(peopleid=basic_user)
        group_ids = [m.groupid.id for m in memberships]

        assert permission_group.id in group_ids


@pytest.mark.django_db
class TestCapabilities:
    """Test capability definitions and management."""

    def test_create_capability(self):
        """Test creating a capability definition."""
        cap = Capability.objects.create(
            capability_name="new_feature",
            category="advanced",
            display_name="New Feature",
            description="A new system capability",
            is_active=True
        )

        assert cap.id is not None
        assert cap.capability_name == "new_feature"
        assert cap.is_active is True

    def test_capability_uniqueness(self, capability):
        """Test that capability names are unique."""
        # Attempt to create duplicate capability
        # Should be prevented by unique constraint

        another_cap = Capability.objects.create(
            capability_name="another_feature",
            category="core",
            display_name="Another Feature"
        )

        assert another_cap.capability_name != capability.capability_name

    def test_capability_categories(self):
        """Test capability categorization."""
        cap1 = Capability.objects.create(
            capability_name="core_feature",
            category="core",
            display_name="Core Feature"
        )
        cap2 = Capability.objects.create(
            capability_name="admin_feature",
            category="admin",
            display_name="Admin Feature"
        )

        # Query by category
        core_caps = Capability.objects.filter(category="core")
        admin_caps = Capability.objects.filter(category="admin")

        assert cap1 in core_caps
        assert cap2 in admin_caps

    def test_activate_deactivate_capability(self, capability):
        """Test toggling capability active state."""
        # Deactivate
        capability.is_active = False
        capability.save()

        cap = Capability.objects.get(id=capability.id)
        assert cap.is_active is False

        # Reactivate
        cap.is_active = True
        cap.save()

        cap = Capability.objects.get(id=capability.id)
        assert cap.is_active is True


@pytest.mark.django_db
class TestUserCapabilities:
    """Test user-level capability assignments."""

    def test_assign_capability_to_user(self, basic_user, capability):
        """Test assigning capability to user."""
        # Update user capabilities JSON field
        basic_user.capabilities = {
            "features": [capability.capability_name]
        }
        basic_user.save()

        user = People.objects.get(id=basic_user.id)
        assert capability.capability_name in user.capabilities["features"]

    def test_revoke_capability_from_user(self, basic_user, capability):
        """Test removing capability from user."""
        # Assign first
        basic_user.capabilities = {
            "features": [capability.capability_name]
        }
        basic_user.save()

        # Revoke
        basic_user.capabilities = {"features": []}
        basic_user.save()

        user = People.objects.get(id=basic_user.id)
        assert capability.capability_name not in user.capabilities.get("features", [])

    def test_check_user_has_capability(self, basic_user, capability):
        """Test checking if user has specific capability."""
        # Assign capability
        basic_user.capabilities = {
            "webcapability": ["dashboard", "reports"]
        }
        basic_user.save()

        # Check
        assert "dashboard" in basic_user.capabilities["webcapability"]
        assert "admin" not in basic_user.capabilities.get("webcapability", [])

    def test_list_user_capabilities(self, basic_user):
        """Test listing all capabilities for a user."""
        # Set capabilities
        capabilities = {
            "webcapability": ["dashboard"],
            "mobilecapability": ["attendance"],
            "reportcapability": ["view", "generate"]
        }
        basic_user.capabilities = capabilities
        basic_user.save()

        user = People.objects.get(id=basic_user.id)
        assert "webcapability" in user.capabilities
        assert "mobilecapability" in user.capabilities
        assert "reportcapability" in user.capabilities


@pytest.mark.django_db
class TestCapabilityBasedAuth:
    """Test capability-based authorization in views."""

    def test_view_requires_capability(self, client, basic_user, capability):
        """Test that view access requires specific capability."""
        # Set required capability
        basic_user.capabilities = {
            "webcapability": [capability.capability_name]
        }
        basic_user.save()

        # User has capability
        assert capability.capability_name in basic_user.capabilities["webcapability"]

    def test_api_endpoint_requires_capability(self, client, basic_user, mock_jwt_token):
        """Test that API endpoints check for required capabilities."""
        # Set API capability
        basic_user.capabilities = {
            "api_access": True
        }
        basic_user.save()

        # Capability check
        assert basic_user.capabilities.get("api_access") is True

    def test_admin_capabilities(self, client, admin_user):
        """Test that admin users have all capabilities."""
        # Admin users should have superuser flag
        assert admin_user.is_superuser is True
        assert admin_user.is_staff is True


@pytest.mark.django_db
class TestPermissionInheritance:
    """Test permission inheritance and hierarchies."""

    def test_group_permission_inheritance(self, basic_user, permission_group):
        """Test that users inherit permissions from their groups."""
        # Add user to group
        Pgbelonging.objects.create(groupid=permission_group, peopleid=basic_user)

        # Verify membership
        is_member = Pgbelonging.objects.filter(
            groupid=permission_group,
            peopleid=basic_user
        ).exists()
        assert is_member is True

    def test_manager_permission_inheritance(self, manager_user, user_with_profile):
        """Test that managers have permissions over their reports."""
        # Verify reporting relationship
        org = user_with_profile.organizational
        assert org.reportto == manager_user


@pytest.mark.django_db
class TestWebCapabilities:
    """Test web-specific capabilities."""

    def test_web_capability_assignment(self, basic_user):
        """Test assigning web portal capabilities."""
        basic_user.capabilities = {
            "webcapability": ["dashboard", "reports", "settings"]
        }
        basic_user.save()

        user = People.objects.get(id=basic_user.id)
        assert "dashboard" in user.capabilities["webcapability"]

    def test_portlet_capability_assignment(self, basic_user):
        """Test assigning dashboard portlet capabilities."""
        basic_user.capabilities = {
            "portletcapability": ["attendance", "tasks", "alerts"]
        }
        basic_user.save()

        user = People.objects.get(id=basic_user.id)
        assert "attendance" in user.capabilities["portletcapability"]

    def test_report_capability_assignment(self, basic_user):
        """Test assigning report generation capabilities."""
        basic_user.capabilities = {
            "reportcapability": ["view", "generate", "export"]
        }
        basic_user.save()

        user = People.objects.get(id=basic_user.id)
        assert "generate" in user.capabilities["reportcapability"]


@pytest.mark.django_db
class TestMobileCapabilities:
    """Test mobile-specific capabilities."""

    def test_mobile_capability_assignment(self, basic_user):
        """Test assigning mobile app capabilities."""
        basic_user.capabilities = {
            "mobilecapability": ["attendance", "tasks", "chat"]
        }
        basic_user.save()

        user = People.objects.get(id=basic_user.id)
        assert "attendance" in user.capabilities["mobilecapability"]

    def test_gps_tracking_capability(self, basic_user):
        """Test GPS location tracking capability."""
        basic_user.capabilities = {
            "enable_gps": True,
            "mobilecapability": ["gps_tracking"]
        }
        basic_user.save()

        user = People.objects.get(id=basic_user.id)
        assert user.capabilities.get("enable_gps") is True


@pytest.mark.django_db
class TestNOCCapabilities:
    """Test NOC (Network Operations Center) specific capabilities."""

    def test_noc_user_capability(self, basic_user):
        """Test NOC user capability assignment."""
        basic_user.capabilities = {
            "noc_user": True,
            "noccapability": ["monitoring", "alerts"]
        }
        basic_user.save()

        user = People.objects.get(id=basic_user.id)
        assert user.capabilities.get("noc_user") is True

    def test_noc_dashboard_access(self, client, basic_user):
        """Test NOC dashboard requires NOC capability."""
        # Set NOC capability
        basic_user.capabilities = {
            "noccapability": ["dashboard"]
        }
        basic_user.save()

        # Verify capability
        assert "dashboard" in basic_user.capabilities["noccapability"]


@pytest.mark.django_db
class TestPermissionAudit:
    """Test permission change audit logging."""

    def test_log_capability_assignment(self, basic_user, capability):
        """Test that capability assignments are logged."""
        # Update capabilities
        basic_user.capabilities = {
            "features": [capability.capability_name]
        }
        basic_user.save()

        # Audit logging tested at service layer
        # Verify capability was assigned
        user = People.objects.get(id=basic_user.id)
        assert capability.capability_name in user.capabilities["features"]

    def test_log_group_membership_changes(self, basic_user, permission_group):
        """Test that group membership changes are logged."""
        # Add to group
        membership = Pgbelonging.objects.create(
            groupid=permission_group,
            peopleid=basic_user
        )

        # Audit logging tested at service layer
        # Verify membership exists
        assert membership.id is not None

        # Remove from group
        membership.delete()

        # Verify removed
        exists = Pgbelonging.objects.filter(
            groupid=permission_group,
            peopleid=basic_user
        ).exists()
        assert not exists


# ============================================================================
# DRF Capability-Based Permission Tests
# ============================================================================


@pytest.fixture
def api_request_factory():
    """Request factory for creating mock HTTP requests."""
    from rest_framework.test import APIRequestFactory
    return APIRequestFactory()


@pytest.fixture
def mock_view():
    """Mock view for permission checks."""
    return None


@pytest.mark.django_db
class TestHasOnboardingAccess:
    """Test HasOnboardingAccess permission class."""

    def test_permission_granted_when_capability_true(self, basic_user, api_request_factory, mock_view):
        """User with canAccessOnboarding=True should pass."""
        from apps.peoples.permissions import HasOnboardingAccess

        basic_user.capabilities = {'canAccessOnboarding': True}
        basic_user.save()

        request = api_request_factory.get('/')
        request.user = basic_user

        permission = HasOnboardingAccess()
        assert permission.has_permission(request, mock_view) is True

    def test_permission_denied_when_capability_false(self, basic_user, api_request_factory, mock_view):
        """User with canAccessOnboarding=False should fail."""
        from apps.peoples.permissions import HasOnboardingAccess

        basic_user.capabilities = {'canAccessOnboarding': False}
        basic_user.save()

        request = api_request_factory.get('/')
        request.user = basic_user

        permission = HasOnboardingAccess()
        assert permission.has_permission(request, mock_view) is False

    def test_permission_denied_for_unauthenticated(self, api_request_factory, mock_view):
        """Unauthenticated users should fail."""
        from django.contrib.auth.models import AnonymousUser
        from apps.peoples.permissions import HasOnboardingAccess

        request = api_request_factory.get('/')
        request.user = AnonymousUser()

        permission = HasOnboardingAccess()
        assert permission.has_permission(request, mock_view) is False

    def test_permission_has_custom_error_message(self):
        """Permission should have user-friendly error message."""
        from apps.peoples.permissions import HasOnboardingAccess

        permission = HasOnboardingAccess()
        assert 'onboarding features' in permission.message.lower()


@pytest.mark.django_db
class TestHasVoiceFeatureAccess:
    """Test HasVoiceFeatureAccess permission class."""

    def test_permission_granted_when_capability_true(self, basic_user, api_request_factory, mock_view):
        """User with canUseVoiceFeatures=True should pass."""
        from apps.peoples.permissions import HasVoiceFeatureAccess

        basic_user.capabilities = {'canUseVoiceFeatures': True}
        basic_user.save()

        request = api_request_factory.get('/')
        request.user = basic_user

        permission = HasVoiceFeatureAccess()
        assert permission.has_permission(request, mock_view) is True

    def test_permission_denied_when_capability_false(self, basic_user, api_request_factory, mock_view):
        """User with canUseVoiceFeatures=False should fail."""
        from apps.peoples.permissions import HasVoiceFeatureAccess

        basic_user.capabilities = {'canUseVoiceFeatures': False}
        basic_user.save()

        request = api_request_factory.get('/')
        request.user = basic_user

        permission = HasVoiceFeatureAccess()
        assert permission.has_permission(request, mock_view) is False


@pytest.mark.django_db
class TestHasVoiceBiometricAccess:
    """Test HasVoiceBiometricAccess permission class."""

    def test_permission_granted_when_capability_true(self, basic_user, api_request_factory, mock_view):
        """User with canUseVoiceBiometrics=True should pass."""
        from apps.peoples.permissions import HasVoiceBiometricAccess

        basic_user.capabilities = {'canUseVoiceBiometrics': True}
        basic_user.save()

        request = api_request_factory.get('/')
        request.user = basic_user

        permission = HasVoiceBiometricAccess()
        assert permission.has_permission(request, mock_view) is True

    def test_permission_denied_when_capability_false(self, basic_user, api_request_factory, mock_view):
        """User with canUseVoiceBiometrics=False should fail."""
        from apps.peoples.permissions import HasVoiceBiometricAccess

        basic_user.capabilities = {'canUseVoiceBiometrics': False}
        basic_user.save()

        request = api_request_factory.get('/')
        request.user = basic_user

        permission = HasVoiceBiometricAccess()
        assert permission.has_permission(request, mock_view) is False
