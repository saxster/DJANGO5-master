"""
Unit tests for refactored People model.

Tests the split model architecture to ensure:
- Core People model focuses on authentication
- Complexity reduction achieved
- Service delegation works correctly
- Capability management functions properly
"""

import pytest
from datetime import date
from apps.peoples.models import People, PeopleProfile, PeopleOrganizational


@pytest.mark.django_db
class TestPeopleModelComplexityReduction:
    """Test that People model complexity has been reduced."""

    def test_people_model_fields_count(self):
        """Test that People model has reduced number of direct fields."""
        people_fields = [f.name for f in People._meta.get_fields()]

        core_auth_fields = ['id', 'password', 'loginid', 'peoplecode', 'peoplename']
        for field in core_auth_fields:
            assert field in people_fields

        profile_fields = ['peopleimg', 'gender', 'dateofbirth', 'dateofjoin', 'dateofreport']
        for field in profile_fields:
            assert field not in [f.name for f in People._meta.fields]

    def test_people_model_has_related_models(self):
        """Test that People model has relationships to split models."""
        people = People.objects.create_user(
            loginid="test001",
            peoplecode="TEST001",
            peoplename="Test User",
            email="test@example.com"
        )

        people._temp_dateofbirth = date(1990, 1, 1)
        people.save()

        people.refresh_from_db()

        assert hasattr(people, 'profile')
        assert hasattr(people, 'organizational')
        assert isinstance(people.profile, PeopleProfile)
        assert isinstance(people.organizational, PeopleOrganizational)


@pytest.mark.django_db
class TestPeopleModelAuthentication:
    """Test that authentication functionality remains intact."""

    def test_create_user_with_password(self):
        """Test creating user with password hashing."""
        people = People.objects.create_user(
            loginid="auth001",
            peoplecode="AUTH001",
            peoplename="Auth User",
            email="auth@example.com",
            password="SecurePass123!"
        )

        people._temp_dateofbirth = date(1990, 1, 1)
        people.save()

        assert people.check_password("SecurePass123!")
        assert not people.check_password("WrongPassword")

    def test_authentication_fields_present(self):
        """Test that all authentication fields are present."""
        people = People.objects.create_user(
            loginid="auth002",
            peoplecode="AUTH002",
            peoplename="Auth User 2",
            email="auth2@example.com"
        )

        assert hasattr(people, 'loginid')
        assert hasattr(people, 'password')
        assert hasattr(people, 'is_staff')
        assert hasattr(people, 'is_superuser')
        assert hasattr(people, 'isadmin')
        assert hasattr(people, 'isverified')
        assert hasattr(people, 'enable')

    def test_username_field_configuration(self):
        """Test that USERNAME_FIELD is properly configured."""
        assert People.USERNAME_FIELD == "loginid"


@pytest.mark.django_db
class TestPeopleModelCapabilities:
    """Test capability management in refactored model."""

    def test_capabilities_field_exists(self):
        """Test that capabilities field exists on People model."""
        people = People.objects.create_user(
            loginid="cap001",
            peoplecode="CAP001",
            peoplename="Capability User",
            email="cap@example.com"
        )

        assert hasattr(people, 'capabilities')
        assert isinstance(people.capabilities, dict)

    def test_capability_management_methods(self):
        """Test that capability management methods work."""
        people = People.objects.create_user(
            loginid="cap002",
            peoplecode="CAP002",
            peoplename="Capability User 2",
            email="cap2@example.com"
        )

        people._temp_dateofbirth = date(1990, 1, 1)
        people.save()

        assert people.add_capability('test_cap', True)
        assert people.has_capability('test_cap')

        all_caps = people.get_all_capabilities()
        assert 'test_cap' in all_caps

        assert people.remove_capability('test_cap')
        assert not people.has_capability('test_cap')

    def test_ai_capabilities_setting(self):
        """Test AI capabilities setting."""
        people = People.objects.create_user(
            loginid="cap003",
            peoplecode="CAP003",
            peoplename="Capability User 3",
            email="cap3@example.com"
        )

        people._temp_dateofbirth = date(1990, 1, 1)
        people.save()

        assert people.set_ai_capabilities(
            can_approve=True,
            can_manage_kb=True,
            is_approver=True
        )

        assert people.has_capability('can_approve_ai_recommendations')
        assert people.has_capability('can_manage_knowledge_base')
        assert people.has_capability('ai_recommendation_approver')


@pytest.mark.django_db
class TestPeopleModelSaveMethod:
    """Test that save method has been simplified."""

    def test_save_initializes_capabilities(self):
        """Test that save initializes capabilities."""
        people = People.objects.create_user(
            loginid="save001",
            peoplecode="SAVE001",
            peoplename="Save Test User",
            email="save@example.com"
        )

        people._temp_dateofbirth = date(1990, 1, 1)
        people.save()

        assert people.capabilities is not None
        assert isinstance(people.capabilities, dict)

    def test_save_respects_update_fields(self):
        """Test that save respects update_fields parameter."""
        people = People.objects.create_user(
            loginid="save002",
            peoplecode="SAVE002",
            peoplename="Save Test User 2",
            email="save2@example.com"
        )

        people._temp_dateofbirth = date(1990, 1, 1)
        people.save()

        people.peoplename = "Updated Name"
        people.save(update_fields=['peoplename'])

        people.refresh_from_db()

        assert people.peoplename == "Updated Name"


@pytest.mark.django_db
class TestPeopleModelIndexes:
    """Test that People model has proper indexes."""

    def test_people_model_indexes(self):
        """Test that indexes are properly defined."""
        index_names = [index.name for index in People._meta.indexes]

        assert 'people_peoplecode_idx' in index_names
        assert 'people_loginid_idx' in index_names
        assert 'people_active_idx' in index_names
        assert 'people_email_idx' in index_names


@pytest.mark.unit
@pytest.mark.django_db
class TestPeopleModelMeta:
    """Test People model Meta configuration."""

    def test_model_meta_configuration(self):
        """Test that Meta is properly configured."""
        assert People._meta.db_table == "people"
        assert People._meta.verbose_name == "Person"
        assert People._meta.verbose_name_plural == "People"

    def test_required_fields(self):
        """Test REQUIRED_FIELDS configuration."""
        expected_required = ["peoplecode", "peoplename", "email"]
        assert People.REQUIRED_FIELDS == expected_required


@pytest.mark.django_db
class TestPeopleModelStringMethods:
    """Test People model string representation methods."""

    def test_str_representation(self):
        """Test __str__ method."""
        people = People.objects.create_user(
            loginid="str001",
            peoplecode="STR001",
            peoplename="String Test User",
            email="str@example.com"
        )

        assert str(people) == "String Test User (STR001)"

    def test_get_absolute_wizard_url(self):
        """Test get_absolute_wizard_url method."""
        people = People.objects.create_user(
            loginid="url001",
            peoplecode="URL001",
            peoplename="URL Test User",
            email="url@example.com"
        )

        people._temp_dateofbirth = date(1990, 1, 1)
        people.save()

        expected_url = f"/people/wizard/update/{people.pk}/"
        assert people.get_absolute_wizard_url() == expected_url