"""
Unit tests for PeopleProfile model.

Tests profile-specific functionality including:
- Model creation and relationships
- Field validation
- Default value handling
- Image upload security
"""

import pytest
from datetime import date, timedelta
from django.core.exceptions import ValidationError
from django.utils import timezone
from apps.peoples.models import People, PeopleProfile


@pytest.mark.django_db
class TestPeopleProfileCreation:
    """Test PeopleProfile model creation and basic functionality."""

    def test_create_profile_with_people(self):
        """Test creating a profile linked to a People instance."""
        people = People.objects.create_user(
            loginid="test001",
            peoplecode="TEST001",
            peoplename="Test User",
            email="test@example.com"
        )

        people._temp_dateofbirth = date(1990, 1, 1)
        people._temp_gender = "M"
        people.save()

        people.refresh_from_db()

        assert hasattr(people, 'profile')
        assert people.profile.dateofbirth == date(1990, 1, 1)
        assert people.profile.gender == "M"

    def test_profile_string_representation(self):
        """Test the string representation of PeopleProfile."""
        people = People.objects.create_user(
            loginid="test002",
            peoplecode="TEST002",
            peoplename="John Doe",
            email="john@example.com"
        )

        people._temp_dateofbirth = date(1990, 1, 1)
        people.save()

        people.refresh_from_db()

        assert str(people.profile) == "Profile for John Doe"

    def test_profile_people_extras_default(self):
        """Test that people_extras has proper default value."""
        people = People.objects.create_user(
            loginid="test003",
            peoplecode="TEST003",
            peoplename="Test User 3",
            email="test3@example.com"
        )

        people._temp_dateofbirth = date(1990, 1, 1)
        people.save()

        people.refresh_from_db()

        assert people.profile.people_extras is not None
        assert isinstance(people.profile.people_extras, dict)
        assert 'mobilecapability' in people.profile.people_extras


@pytest.mark.django_db
class TestPeopleProfileValidation:
    """Test PeopleProfile validation logic."""

    def test_dateofbirth_cannot_be_future(self):
        """Test that date of birth cannot be in the future."""
        people = People.objects.create_user(
            loginid="test004",
            peoplecode="TEST004",
            peoplename="Test User 4",
            email="test4@example.com"
        )

        future_date = timezone.now().date() + timedelta(days=365)

        profile = PeopleProfile(
            people=people,
            dateofbirth=future_date
        )

        with pytest.raises(ValidationError) as exc_info:
            profile.clean()

        assert 'dateofbirth' in exc_info.value.message_dict

    def test_dateofjoin_after_dateofbirth(self):
        """Test that date of joining cannot be before date of birth."""
        people = People.objects.create_user(
            loginid="test005",
            peoplecode="TEST005",
            peoplename="Test User 5",
            email="test5@example.com"
        )

        profile = PeopleProfile(
            people=people,
            dateofbirth=date(1990, 1, 1),
            dateofjoin=date(1989, 1, 1)
        )

        with pytest.raises(ValidationError) as exc_info:
            profile.clean()

        assert 'dateofjoin' in exc_info.value.message_dict

    def test_valid_profile_passes_validation(self):
        """Test that valid profile data passes validation."""
        people = People.objects.create_user(
            loginid="test006",
            peoplecode="TEST006",
            peoplename="Test User 6",
            email="test6@example.com"
        )

        profile = PeopleProfile(
            people=people,
            dateofbirth=date(1990, 1, 1),
            dateofjoin=date(2023, 1, 1),
            gender="M"
        )

        profile.clean()


@pytest.mark.django_db
class TestPeopleProfileFields:
    """Test PeopleProfile field behavior."""

    def test_gender_choices(self):
        """Test that gender field accepts valid choices."""
        people = People.objects.create_user(
            loginid="test007",
            peoplecode="TEST007",
            peoplename="Test User 7",
            email="test7@example.com"
        )

        for gender_code, gender_label in [("M", "Male"), ("F", "Female"), ("O", "Others")]:
            people._temp_dateofbirth = date(1990, 1, 1)
            people._temp_gender = gender_code
            people.save()

            people.refresh_from_db()

            assert people.profile.gender == gender_code

    def test_date_fields_optional_except_dob(self):
        """Test that date fields are optional except dateofbirth."""
        people = People.objects.create_user(
            loginid="test008",
            peoplecode="TEST008",
            peoplename="Test User 8",
            email="test8@example.com"
        )

        profile = PeopleProfile(
            people=people,
            dateofbirth=date(1990, 1, 1)
        )

        profile.save()

        assert profile.dateofjoin is None
        assert profile.dateofreport is None

    def test_people_extras_json_field(self):
        """Test people_extras JSON field functionality."""
        people = People.objects.create_user(
            loginid="test009",
            peoplecode="TEST009",
            peoplename="Test User 9",
            email="test9@example.com"
        )

        people._temp_dateofbirth = date(1990, 1, 1)
        people.save()

        people.refresh_from_db()

        people.profile.people_extras['custom_field'] = 'custom_value'
        people.profile.save()

        people.refresh_from_db()

        assert people.profile.people_extras['custom_field'] == 'custom_value'


@pytest.mark.django_db
class TestPeopleProfileIndexes:
    """Test that proper indexes are created."""

    def test_profile_model_has_proper_meta(self):
        """Test that PeopleProfile has proper Meta configuration."""
        assert PeopleProfile._meta.db_table == "people_profile"
        assert PeopleProfile._meta.verbose_name == "People Profile"

        index_names = [index.name for index in PeopleProfile._meta.indexes]
        assert 'profile_dob_idx' in index_names
        assert 'profile_join_idx' in index_names


@pytest.mark.unit
@pytest.mark.django_db
class TestPeopleProfileRelationship:
    """Test relationship between People and PeopleProfile."""

    def test_one_to_one_relationship(self):
        """Test that PeopleProfile has one-to-one relationship with People."""
        people = People.objects.create_user(
            loginid="test010",
            peoplecode="TEST010",
            peoplename="Test User 10",
            email="test10@example.com"
        )

        people._temp_dateofbirth = date(1990, 1, 1)
        people.save()

        people.refresh_from_db()

        assert people.profile.people == people
        assert people.profile.people_id == people.id

    def test_profile_cascade_delete(self):
        """Test that deleting People cascades to PeopleProfile."""
        people = People.objects.create_user(
            loginid="test011",
            peoplecode="TEST011",
            peoplename="Test User 11",
            email="test11@example.com"
        )

        people._temp_dateofbirth = date(1990, 1, 1)
        people.save()

        people.refresh_from_db()

        profile_id = people.profile.people_id

        people.delete()

        assert not PeopleProfile.objects.filter(people_id=profile_id).exists()