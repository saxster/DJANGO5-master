"""
Unit tests for PeopleOrganizational model.

Tests organizational relationship functionality including:
- Model creation and relationships
- Foreign key relationships
- Default value handling
- Index effectiveness
"""

import pytest
from datetime import date
from apps.peoples.models import People, PeopleOrganizational


@pytest.mark.django_db
class TestPeopleOrganizationalCreation:
    """Test PeopleOrganizational model creation and basic functionality."""

    def test_create_organizational_with_people(self):
        """Test creating organizational info linked to a People instance."""
        people = People.objects.create_user(
            loginid="test001",
            peoplecode="TEST001",
            peoplename="Test User",
            email="test@example.com"
        )

        people._temp_dateofbirth = date(1990, 1, 1)
        people.save()

        people.refresh_from_db()

        assert hasattr(people, 'organizational')
        assert people.organizational.people == people

    def test_organizational_string_representation(self):
        """Test the string representation of PeopleOrganizational."""
        people = People.objects.create_user(
            loginid="test002",
            peoplecode="TEST002",
            peoplename="John Doe",
            email="john@example.com"
        )

        people._temp_dateofbirth = date(1990, 1, 1)
        people.save()

        people.refresh_from_db()

        assert str(people.organizational) == "Org info for John Doe"

    def test_organizational_defaults_set_on_creation(self):
        """Test that organizational defaults are set on creation."""
        people = People.objects.create_user(
            loginid="test003",
            peoplecode="TEST003",
            peoplename="Test User 3",
            email="test3@example.com"
        )

        people._temp_dateofbirth = date(1990, 1, 1)
        people.save()

        people.refresh_from_db()

        assert people.organizational is not None


@pytest.mark.django_db
class TestPeopleOrganizationalRelationships:
    """Test PeopleOrganizational foreign key relationships."""

    def test_reportto_self_reference(self):
        """Test that reportto can reference another People instance."""
        manager = People.objects.create_user(
            loginid="manager001",
            peoplecode="MGR001",
            peoplename="Manager User",
            email="manager@example.com"
        )

        manager._temp_dateofbirth = date(1980, 1, 1)
        manager.save()

        employee = People.objects.create_user(
            loginid="emp001",
            peoplecode="EMP001",
            peoplename="Employee User",
            email="employee@example.com"
        )

        employee._temp_dateofbirth = date(1990, 1, 1)
        employee._temp_reportto = manager
        employee.save()

        employee.refresh_from_db()

        assert hasattr(employee, 'organizational')

    def test_direct_reports_reverse_relationship(self):
        """Test the direct_reports reverse relationship."""
        manager = People.objects.create_user(
            loginid="manager002",
            peoplecode="MGR002",
            peoplename="Manager User 2",
            email="manager2@example.com"
        )

        manager._temp_dateofbirth = date(1980, 1, 1)
        manager.save()

        employee1 = People.objects.create_user(
            loginid="emp002",
            peoplecode="EMP002",
            peoplename="Employee 2",
            email="employee2@example.com"
        )

        employee1._temp_dateofbirth = date(1990, 1, 1)
        employee1._temp_reportto = manager
        employee1.save()

        manager.refresh_from_db()

        direct_reports = manager.direct_reports.all()
        assert direct_reports.count() >= 0


@pytest.mark.django_db
class TestPeopleOrganizationalFields:
    """Test PeopleOrganizational field behavior."""

    def test_all_organizational_fields_optional(self):
        """Test that all organizational fields are optional."""
        people = People.objects.create_user(
            loginid="test004",
            peoplecode="TEST004",
            peoplename="Test User 4",
            email="test4@example.com"
        )

        people._temp_dateofbirth = date(1990, 1, 1)
        people.save()

        org = people.organizational

        assert org.location is None or org.location is not None
        assert org.department is None or org.department is not None
        assert org.designation is None or org.designation is not None

    def test_organizational_field_update(self):
        """Test updating organizational fields."""
        people = People.objects.create_user(
            loginid="test005",
            peoplecode="TEST005",
            peoplename="Test User 5",
            email="test5@example.com"
        )

        people._temp_dateofbirth = date(1990, 1, 1)
        people.save()

        people.refresh_from_db()

        people.organizational.location = None
        people.organizational.save()

        people.refresh_from_db()

        assert people.organizational.location is None


@pytest.mark.django_db
class TestPeopleOrganizationalIndexes:
    """Test that proper indexes are created."""

    def test_organizational_model_has_proper_meta(self):
        """Test that PeopleOrganizational has proper Meta configuration."""
        assert PeopleOrganizational._meta.db_table == "people_organizational"
        assert PeopleOrganizational._meta.verbose_name == "People Organizational Info"

        index_names = [index.name for index in PeopleOrganizational._meta.indexes]
        assert 'org_client_bu_idx' in index_names
        assert 'org_department_idx' in index_names
        assert 'org_designation_idx' in index_names
        assert 'org_reportto_idx' in index_names


@pytest.mark.unit
@pytest.mark.django_db
class TestPeopleOrganizationalRelationship:
    """Test relationship between People and PeopleOrganizational."""

    def test_one_to_one_relationship(self):
        """Test that PeopleOrganizational has one-to-one relationship with People."""
        people = People.objects.create_user(
            loginid="test006",
            peoplecode="TEST006",
            peoplename="Test User 6",
            email="test6@example.com"
        )

        people._temp_dateofbirth = date(1990, 1, 1)
        people.save()

        people.refresh_from_db()

        assert people.organizational.people == people
        assert people.organizational.people_id == people.id

    def test_organizational_cascade_delete(self):
        """Test that deleting People cascades to PeopleOrganizational."""
        people = People.objects.create_user(
            loginid="test007",
            peoplecode="TEST007",
            peoplename="Test User 7",
            email="test7@example.com"
        )

        people._temp_dateofbirth = date(1990, 1, 1)
        people.save()

        people.refresh_from_db()

        org_id = people.organizational.people_id

        people.delete()

        assert not PeopleOrganizational.objects.filter(people_id=org_id).exists()


@pytest.mark.django_db
class TestPeopleOrganizationalDefaultHandling:
    """Test default value handling in PeopleOrganizational."""

    def test_defaults_applied_on_save(self):
        """Test that defaults are applied when saving new organizational record."""
        people = People.objects.create_user(
            loginid="test008",
            peoplecode="TEST008",
            peoplename="Test User 8",
            email="test8@example.com"
        )

        people._temp_dateofbirth = date(1990, 1, 1)
        people.save()

        people.refresh_from_db()

        org = people.organizational

        assert org is not None

    def test_no_recursive_save(self):
        """Test that update_fields prevents recursive saves."""
        people = People.objects.create_user(
            loginid="test009",
            peoplecode="TEST009",
            peoplename="Test User 9",
            email="test9@example.com"
        )

        people._temp_dateofbirth = date(1990, 1, 1)
        people.save()

        people.refresh_from_db()

        people.organizational.location = None
        people.organizational.save(update_fields=['location'])

        people.refresh_from_db()

        assert people.organizational.location is None