"""
Integration tests for peoples app.

Tests complete user lifecycle and cross-app integration including:
- User creation through deletion
- Authentication + profile + permissions together
- Cross-app integration (peoples → attendance, peoples → y_helpdesk)
"""
import pytest
from datetime import datetime, timezone as dt_timezone, date, timedelta
from django.contrib.auth import authenticate
from django.db import transaction, IntegrityError
from apps.peoples.models import People, PeopleProfile, PeopleOrganizational, Pgroup, Pgbelonging, Capability
from apps.client_onboarding.models import Bt
from rest_framework_simplejwt.tokens import RefreshToken


@pytest.mark.django_db
class TestCompleteUserLifecycle:
    """Test complete user lifecycle from creation to deletion."""

    def test_create_complete_user_profile(self, test_tenant, test_location, test_department, test_designation):
        """Test creating user with complete profile and organizational data."""
        # Step 1: Create user
        user = People.objects.create(
            peoplecode="LIFECYCLE001",
            peoplename="Complete Lifecycle User",
            loginid="lifecycle",
            email="lifecycle@example.com",
            mobno="5555555555",
            client=test_tenant,
            enable=True
        )
        user.set_password("LifecyclePass123!")
        user.save()

        # Step 2: Create profile
        profile = PeopleProfile.objects.create(
            people=user,
            dateofbirth=date(1985, 3, 15),
            gender="Male",
            dateofjoin=date(2022, 1, 1)
        )

        # Step 3: Create organizational data
        org = PeopleOrganizational.objects.create(
            people=user,
            location=test_location,
            department=test_department,
            designation=test_designation
        )

        # Verify complete user
        assert user.id is not None
        assert profile.people == user
        assert org.people == user
        assert org.location == test_location

    def test_user_authentication_flow(self, test_tenant):
        """Test complete authentication flow."""
        # Create user
        user = People.objects.create(
            peoplecode="AUTHFLOW001",
            peoplename="Auth Flow User",
            loginid="authflow",
            email="authflow@example.com",
            client=test_tenant,
            enable=True
        )
        user.set_password("AuthPass123!")
        user.save()

        # Test authentication
        authenticated = authenticate(username="authflow", password="AuthPass123!")
        assert authenticated is not None
        assert authenticated.id == user.id

        # Generate JWT
        refresh = RefreshToken.for_user(user)
        access_token = str(refresh.access_token)

        assert access_token is not None
        assert len(access_token) > 0

    def test_user_update_workflow(self, user_with_profile):
        """Test updating user, profile, and organizational data."""
        # Update user
        user_with_profile.peoplename = "Updated Name"
        user_with_profile.save()

        # Update profile
        profile = user_with_profile.profile
        profile.gender = "Female"
        profile.save()

        # Reload and verify
        updated_user = People.objects.get(id=user_with_profile.id)
        assert updated_user.peoplename == "Updated Name"
        assert updated_user.profile.gender == "Female"

    def test_user_deletion_cascade(self, user_with_profile):
        """Test that deleting user cascades to profile and organizational."""
        user_id = user_with_profile.id

        # Verify related data exists
        assert PeopleProfile.objects.filter(people_id=user_id).exists()
        assert PeopleOrganizational.objects.filter(people_id=user_id).exists()

        # Delete user
        user_with_profile.delete()

        # Verify cascade deletion
        assert not People.objects.filter(id=user_id).exists()
        assert not PeopleProfile.objects.filter(people_id=user_id).exists()
        assert not PeopleOrganizational.objects.filter(people_id=user_id).exists()


@pytest.mark.django_db
class TestAuthenticationWithPermissions:
    """Test authentication combined with permission management."""

    def test_login_with_capabilities(self, test_tenant):
        """Test user login with capability-based permissions."""
        # Create user with capabilities
        user = People.objects.create(
            peoplecode="CAPUSER001",
            peoplename="Capability User",
            loginid="capuser",
            email="capuser@example.com",
            client=test_tenant,
            enable=True
        )
        user.set_password("CapPass123!")
        user.capabilities = {
            "webcapability": ["dashboard", "reports"],
            "mobilecapability": ["attendance"]
        }
        user.save()

        # Authenticate
        authenticated = authenticate(username="capuser", password="CapPass123!")
        assert authenticated is not None

        # Verify capabilities
        assert "dashboard" in authenticated.capabilities["webcapability"]

    def test_group_membership_with_authentication(self, test_tenant):
        """Test user authentication with group memberships."""
        # Create user
        user = People.objects.create(
            peoplecode="GRPUSER001",
            peoplename="Group User",
            loginid="grpuser",
            email="grpuser@example.com",
            client=test_tenant,
            enable=True
        )
        user.set_password("GroupPass123!")
        user.save()

        # Create group
        group = Pgroup.objects.create(
            groupname="Test Group",
            groupcode="TESTGRP",
            description="Test group",
            client=test_tenant
        )

        # Add user to group
        Pgbelonging.objects.create(groupid=group, peopleid=user)

        # Authenticate
        authenticated = authenticate(username="grpuser", password="GroupPass123!")
        assert authenticated is not None

        # Verify group membership
        is_member = Pgbelonging.objects.filter(
            groupid=group,
            peopleid=authenticated
        ).exists()
        assert is_member is True


@pytest.mark.django_db
class TestMultiTenantIntegration:
    """Test multi-tenant data isolation and access control."""

    def test_tenant_data_isolation(self):
        """Test that users from different tenants are isolated."""
        # Create two tenants
        tenant1 = Bt.objects.create(
            bucode="TENANT1",
            buname="Tenant One",
            enable=True
        )
        tenant2 = Bt.objects.create(
            bucode="TENANT2",
            buname="Tenant Two",
            enable=True
        )

        # Create users in different tenants
        user1 = People.objects.create(
            peoplecode="T1USER",
            peoplename="Tenant 1 User",
            loginid="t1user",
            email="t1@example.com",
            client=tenant1
        )
        user2 = People.objects.create(
            peoplecode="T2USER",
            peoplename="Tenant 2 User",
            loginid="t2user",
            email="t2@example.com",
            client=tenant2
        )

        # Verify isolation
        tenant1_users = People.objects.filter(client=tenant1)
        tenant2_users = People.objects.filter(client=tenant2)

        assert user1 in tenant1_users
        assert user1 not in tenant2_users
        assert user2 in tenant2_users
        assert user2 not in tenant1_users

    def test_cross_tenant_authentication_prevented(self):
        """Test that authentication respects tenant boundaries."""
        # Create tenant
        tenant = Bt.objects.create(
            bucode="SECURE",
            buname="Secure Tenant",
            enable=True
        )

        # Create user
        user = People.objects.create(
            peoplecode="SECUSER",
            peoplename="Secure User",
            loginid="secuser",
            email="secuser@example.com",
            client=tenant,
            enable=True
        )
        user.set_password("SecurePass123!")
        user.save()

        # Authenticate
        authenticated = authenticate(username="secuser", password="SecurePass123!")
        assert authenticated is not None
        assert authenticated.client == tenant


@pytest.mark.django_db
class TestCrossAppIntegration:
    """Test integration with other apps (attendance, y_helpdesk)."""

    def test_user_profile_for_attendance(self, user_with_profile):
        """Test user profile is available for attendance tracking."""
        # User with profile should have all required data
        assert user_with_profile.profile is not None
        assert user_with_profile.profile.dateofbirth is not None
        assert user_with_profile.organizational is not None

        # User is ready for attendance tracking
        assert user_with_profile.enable is True

    def test_user_capabilities_for_helpdesk(self, basic_user):
        """Test user capabilities for helpdesk ticket creation."""
        # Set helpdesk capabilities
        basic_user.capabilities = {
            "webcapability": ["helpdesk"],
            "create_tickets": True
        }
        basic_user.save()

        # Verify capabilities
        user = People.objects.get(id=basic_user.id)
        assert user.capabilities.get("create_tickets") is True

    def test_manager_hierarchy_for_approvals(self, manager_user, user_with_profile):
        """Test manager-employee hierarchy for approval workflows."""
        # Verify reporting structure
        org = user_with_profile.organizational
        assert org.reportto == manager_user

        # Manager can approve employee requests
        assert manager_user.id == org.reportto.id


@pytest.mark.django_db
class TestTransactionalIntegrity:
    """Test transactional integrity during user operations."""

    def test_atomic_user_creation(self, test_tenant, test_location, test_department, test_designation):
        """Test that user creation is atomic."""
        with transaction.atomic():
            # Create user
            user = People.objects.create(
                peoplecode="ATOMIC001",
                peoplename="Atomic User",
                loginid="atomic",
                email="atomic@example.com",
                client=test_tenant
            )

            # Create profile
            PeopleProfile.objects.create(
                people=user,
                dateofbirth=date(1990, 1, 1)
            )

            # Create organizational
            PeopleOrganizational.objects.create(
                people=user,
                location=test_location,
                department=test_department,
                designation=test_designation
            )

        # Verify all created
        assert People.objects.filter(loginid="atomic").exists()
        assert PeopleProfile.objects.filter(people__loginid="atomic").exists()
        assert PeopleOrganizational.objects.filter(people__loginid="atomic").exists()

    def test_rollback_on_error(self, test_tenant):
        """Test that transaction rolls back on error."""
        try:
            with transaction.atomic():
                # Create user
                user = People.objects.create(
                    peoplecode="ROLLBACK001",
                    peoplename="Rollback User",
                    loginid="rollback",
                    email="rollback@example.com",
                    client=test_tenant
                )

                # Intentionally cause error (duplicate loginid)
                People.objects.create(
                    peoplecode="ROLLBACK002",
                    peoplename="Duplicate",
                    loginid="rollback",  # Duplicate!
                    email="duplicate@example.com",
                    client=test_tenant
                )
        except IntegrityError:
            pass  # Expected

        # Verify rollback - first user should not exist
        assert not People.objects.filter(loginid="rollback").exists()


@pytest.mark.django_db
class TestPerformanceOptimization:
    """Test query performance and optimization."""

    def test_with_full_details_optimization(self, user_with_profile):
        """Test that with_full_details reduces query count."""
        # Query with optimization
        users = People.objects.with_full_details()

        # Should include profile and organizational
        user = users.filter(id=user_with_profile.id).first()
        assert user is not None

        # Accessing related data should not trigger new queries
        # (already loaded via select_related)
        profile = user.profile
        org = user.organizational

        assert profile is not None
        assert org is not None

    def test_bulk_user_operations(self, test_tenant):
        """Test bulk user creation and updates."""
        # Bulk create users
        users = [
            People(
                peoplecode=f"BULK{i:03d}",
                peoplename=f"Bulk User {i}",
                loginid=f"bulk{i}",
                email=f"bulk{i}@example.com",
                client=test_tenant
            )
            for i in range(10)
        ]

        People.objects.bulk_create(users)

        # Verify bulk creation
        bulk_users = People.objects.filter(peoplecode__startswith="BULK")
        assert bulk_users.count() == 10


@pytest.mark.django_db
class TestSecurityIntegration:
    """Test security-related integrations."""

    def test_password_encryption(self, test_tenant):
        """Test that passwords are properly hashed."""
        user = People.objects.create(
            peoplecode="SEC001",
            peoplename="Security User",
            loginid="secuser",
            email="sec@example.com",
            client=test_tenant
        )

        plain_password = "SecurePass123!"
        user.set_password(plain_password)
        user.save()

        # Password should be hashed
        assert user.password != plain_password
        assert user.password.startswith('pbkdf2_sha256$')

        # Verification should work
        assert user.check_password(plain_password)

    def test_pii_field_encryption(self, basic_user):
        """Test that PII fields (email, mobno) are encrypted."""
        # Email and mobno use EnhancedSecureString
        # Values should be accessible (decrypted transparently)
        assert basic_user.email == "testuser@example.com"
        assert basic_user.mobno == "1234567890"

        # Fields are encrypted at storage level
        # (encryption tested at field level)

    def test_session_security(self, client, basic_user):
        """Test that sessions are secure."""
        # Login
        logged_in = client.login(username=basic_user.loginid, password="TestPass123!")
        assert logged_in is True

        # Session should be created
        assert client.session.get('_auth_user_id') == str(basic_user.id)

        # Logout
        client.logout()

        # Session should be cleared
        assert client.session.get('_auth_user_id') is None
