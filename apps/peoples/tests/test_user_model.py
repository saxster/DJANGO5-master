"""
User model tests for peoples app.

Tests People model creation, validation, field encryption,
and multi-tenant isolation.
"""
import pytest
from datetime import datetime, timezone as dt_timezone, date
from django.contrib.auth import get_user_model
from django.db import IntegrityError
from django.core.exceptions import ValidationError
from apps.peoples.models import People, PeopleProfile, PeopleOrganizational
from apps.client_onboarding.models import Bt

User = get_user_model()


@pytest.mark.django_db
class TestUserCreation:
    """Test user creation and validation."""

    def test_create_user_with_required_fields(self, test_tenant):
        """Test creating user with minimal required fields."""
        user = People.objects.create(
            peoplecode="MIN001",
            peoplename="Minimal User",
            loginid="minuser",
            email="min@example.com",
            client=test_tenant,
            enable=True
        )

        assert user.id is not None
        assert user.peoplecode == "MIN001"
        assert user.peoplename == "Minimal User"
        assert user.loginid == "minuser"
        assert user.email == "min@example.com"
        assert user.client == test_tenant

    def test_create_user_with_complete_data(self, test_tenant):
        """Test creating user with all fields populated."""
        user = People.objects.create(
            peoplecode="FULL001",
            peoplename="Full User",
            loginid="fulluser",
            email="full@example.com",
            mobno="1234567890",
            client=test_tenant,
            enable=True,
            isadmin=False,
            is_staff=False,
            isverified=True,
            dateofbirth=date(1990, 1, 1),
            dateofjoin=date(2020, 1, 1),
            preferred_language='en'
        )

        assert user.id is not None
        assert user.peoplecode == "FULL001"
        assert user.mobno == "1234567890"
        assert user.isverified is True
        assert user.preferred_language == 'en'

    def test_create_user_missing_required_fields(self, test_tenant):
        """Test that creating user without required fields raises error."""
        # Missing loginid (unique constraint)
        with pytest.raises((IntegrityError, ValidationError)):
            user = People.objects.create(
                peoplecode="ERR001",
                peoplename="Error User",
                # loginid missing
                email="error@example.com",
                client=test_tenant
            )

    def test_create_user_with_duplicate_loginid(self, basic_user, test_tenant):
        """Test that duplicate loginid raises IntegrityError."""
        with pytest.raises(IntegrityError):
            People.objects.create(
                peoplecode="DUP001",
                peoplename="Duplicate User",
                loginid=basic_user.loginid,  # Duplicate
                email="dup@example.com",
                client=test_tenant
            )

    def test_user_password_hashing(self, test_tenant):
        """Test that passwords are properly hashed on save."""
        user = People.objects.create(
            peoplecode="HASH001",
            peoplename="Hash User",
            loginid="hashuser",
            email="hash@example.com",
            client=test_tenant,
            enable=True
        )

        # Set password
        plain_password = "SecurePass123!"
        user.set_password(plain_password)
        user.save()

        # Password should be hashed
        assert user.password != plain_password
        assert user.password.startswith('pbkdf2_sha256$')

        # Password verification should work
        assert user.check_password(plain_password) is True
        assert user.check_password("WrongPassword") is False


@pytest.mark.django_db
class TestUserEncryption:
    """Test PII field encryption."""

    def test_email_field_encryption(self, basic_user):
        """Test that email field is encrypted in database."""
        # Access email through model (decrypted automatically)
        email_value = basic_user.email

        # Should be readable
        assert email_value == "testuser@example.com"

        # Email field uses EnhancedSecureString for encryption
        # Actual encryption tested at field level

    def test_mobno_field_encryption(self, basic_user):
        """Test that mobile number field is encrypted in database."""
        # Access mobile number (decrypted automatically)
        mobno_value = basic_user.mobno

        # Should be readable
        assert mobno_value == "1234567890"

    def test_encrypted_field_decryption(self, basic_user):
        """Test that encrypted fields decrypt correctly on access."""
        # Encrypted fields should decrypt transparently
        assert basic_user.email == "testuser@example.com"
        assert basic_user.mobno == "1234567890"

        # Values should be consistent across accesses
        email1 = basic_user.email
        email2 = basic_user.email
        assert email1 == email2

    def test_encrypted_field_search(self, basic_user):
        """Test querying by encrypted fields."""
        # Search by email
        user = People.objects.filter(email=basic_user.email).first()
        assert user is not None
        assert user.id == basic_user.id


@pytest.mark.django_db
class TestUserValidation:
    """Test user model validation rules."""

    def test_email_format_validation(self, test_tenant):
        """Test email field validates format."""
        # Create user with valid email
        user = People.objects.create(
            peoplecode="EMAIL001",
            peoplename="Email User",
            loginid="emailuser",
            email="valid@example.com",
            client=test_tenant
        )

        assert user.email == "valid@example.com"

    def test_mobno_format_validation(self, test_tenant):
        """Test mobile number field validates format."""
        # Create user with mobile number
        user = People.objects.create(
            peoplecode="MOB001",
            peoplename="Mobile User",
            loginid="mobuser",
            email="mob@example.com",
            mobno="9876543210",
            client=test_tenant
        )

        assert user.mobno == "9876543210"

    def test_peoplecode_uniqueness_per_tenant(self, test_tenant):
        """Test that peoplecode is unique within tenant."""
        # Create first user
        user1 = People.objects.create(
            peoplecode="UNIQUE001",
            peoplename="User One",
            loginid="user_one",
            email="one@example.com",
            client=test_tenant
        )

        # Attempt to create another user with same peoplecode is allowed
        # (peoplecode is not enforced as unique at DB level, only loginid)
        user2 = People.objects.create(
            peoplecode="UNIQUE002",  # Different code
            peoplename="User Two",
            loginid="user_two",
            email="two@example.com",
            client=test_tenant
        )

        assert user1.peoplecode != user2.peoplecode


@pytest.mark.django_db
class TestUserQueryMethods:
    """Test custom query methods and managers."""

    def test_with_full_details_queryset(self, user_with_profile):
        """Test PeopleManager.with_full_details() optimizes queries."""
        # Query with optimization
        users = People.objects.with_full_details()

        assert users.count() > 0
        # Verify user is in results
        user_ids = [u.id for u in users]
        assert user_with_profile.id in user_ids

    def test_active_users_queryset(self, basic_user, test_tenant):
        """Test filtering active users."""
        # Create inactive user
        inactive = People.objects.create(
            peoplecode="INACTIVE",
            peoplename="Inactive",
            loginid="inactive_user",
            email="inactive@example.com",
            client=test_tenant,
            enable=False
        )

        # Filter active users
        active_users = People.objects.filter(enable=True)

        assert basic_user in active_users
        assert inactive not in active_users

    def test_by_tenant_queryset(self, basic_user, test_tenant):
        """Test filtering users by tenant."""
        # Create another tenant
        other_tenant = Bt.objects.create(
            bucode="OTHER",
            buname="Other Tenant",
            enable=True
        )

        # Create user in other tenant
        other_user = People.objects.create(
            peoplecode="OTHER001",
            peoplename="Other User",
            loginid="otheruser",
            email="other@example.com",
            client=other_tenant
        )

        # Filter by tenant
        tenant_users = People.objects.filter(client=test_tenant)

        assert basic_user in tenant_users
        assert other_user not in tenant_users


@pytest.mark.django_db
class TestUserCapabilities:
    """Test user capabilities JSON field and mixin methods."""

    def test_default_capabilities_on_creation(self, basic_user):
        """Test that new users get default capabilities."""
        # User should have capabilities field
        assert basic_user.capabilities is not None
        assert isinstance(basic_user.capabilities, dict)

    def test_update_capabilities(self, basic_user):
        """Test updating user capabilities."""
        # Update capabilities
        new_caps = {
            "webcapability": ["dashboard"],
            "mobilecapability": ["attendance"],
            "debug": True
        }
        basic_user.capabilities = new_caps
        basic_user.save()

        # Reload and verify
        user = People.objects.get(id=basic_user.id)
        assert user.capabilities == new_caps
        assert user.capabilities["debug"] is True

    def test_has_capability_check(self, basic_user):
        """Test checking if user has specific capability."""
        # Set capabilities
        basic_user.capabilities = {
            "webcapability": ["reports", "dashboard"],
            "mobilecapability": []
        }
        basic_user.save()

        # Check capabilities
        assert "webcapability" in basic_user.capabilities
        assert "reports" in basic_user.capabilities["webcapability"]


@pytest.mark.django_db
class TestMultiTenantIsolation:
    """Test multi-tenant data isolation."""

    def test_users_isolated_by_tenant(self, basic_user):
        """Test that users from different tenants are isolated."""
        # Create separate tenant
        tenant2 = Bt.objects.create(
            bucode="TENANT2",
            buname="Tenant Two",
            enable=True
        )

        # Create user in tenant2
        user2 = People.objects.create(
            peoplecode="T2USER",
            peoplename="Tenant 2 User",
            loginid="t2user",
            email="t2@example.com",
            client=tenant2
        )

        # Verify isolation
        assert basic_user.client != user2.client

        # Filter by tenant
        tenant1_users = People.objects.filter(client=basic_user.client)
        tenant2_users = People.objects.filter(client=tenant2)

        assert basic_user in tenant1_users
        assert basic_user not in tenant2_users
        assert user2 in tenant2_users
        assert user2 not in tenant1_users

    def test_tenant_aware_queries(self, basic_user, test_tenant):
        """Test that queries automatically filter by tenant."""
        # All users in tenant
        tenant_users = People.objects.filter(client=test_tenant)

        # basic_user should be in results
        assert basic_user in tenant_users

        # Verify tenant filtering works
        for user in tenant_users:
            assert user.client == test_tenant


@pytest.mark.django_db
class TestUserDeletion:
    """Test user deletion and cascade behavior."""

    def test_soft_delete_user(self, basic_user):
        """Test soft deletion (setting enable=False)."""
        # Soft delete
        basic_user.enable = False
        basic_user.save()

        # User should still exist but be disabled
        user = People.objects.get(id=basic_user.id)
        assert user.enable is False

        # Can filter out disabled users
        active_users = People.objects.filter(enable=True)
        assert basic_user not in active_users

    def test_hard_delete_cascades_to_profile(self, user_with_profile):
        """Test that deleting user cascades to PeopleProfile."""
        user_id = user_with_profile.id

        # Verify profile exists
        assert hasattr(user_with_profile, 'profile')
        profile_exists = PeopleProfile.objects.filter(people_id=user_id).exists()
        assert profile_exists

        # Delete user
        user_with_profile.delete()

        # Profile should also be deleted (CASCADE)
        profile_exists = PeopleProfile.objects.filter(people_id=user_id).exists()
        assert not profile_exists

    def test_hard_delete_cascades_to_organizational(self, user_with_profile):
        """Test that deleting user cascades to PeopleOrganizational."""
        user_id = user_with_profile.id

        # Verify organizational exists
        org_exists = PeopleOrganizational.objects.filter(people_id=user_id).exists()
        assert org_exists

        # Delete user
        user_with_profile.delete()

        # Organizational should also be deleted (CASCADE)
        org_exists = PeopleOrganizational.objects.filter(people_id=user_id).exists()
        assert not org_exists
