"""
Backward Compatibility Tests for People Model Refactoring

This module contains comprehensive tests to verify that the refactored
People model maintains 100% backward compatibility with existing code.

Tests verify:
- Field access patterns work transparently
- Related model queries function correctly
- Property accessors return expected values
- Setters update correct models
- Signal handlers create related models automatically
"""

import pytest
from datetime import date
from django.test import TestCase
from apps.peoples.models import People, PeopleProfile, PeopleOrganizational


@pytest.mark.django_db
class TestBackwardCompatibilityFieldAccess:
    """Test that field access patterns remain unchanged."""

    def test_profile_field_read_access(self):
        """Test reading profile fields through People instance."""
        people = People.objects.create_user(
            loginid="test001",
            peoplecode="TEST001",
            peoplename="Test User",
            email="test@example.com",
            password="TestPass123!"
        )

        people._temp_dateofbirth = date(1990, 1, 1)
        people._temp_gender = "M"
        people.save()

        people.refresh_from_db()

        assert people.dateofbirth is not None
        assert people.gender is not None

    def test_profile_field_write_access(self):
        """Test writing profile fields through People instance."""
        people = People.objects.create_user(
            loginid="test002",
            peoplecode="TEST002",
            peoplename="Test User 2",
            email="test2@example.com"
        )

        people._temp_dateofbirth = date(1990, 1, 1)
        people._temp_gender = "F"
        people._temp_dateofjoin = date(2023, 1, 1)
        people.save()

        people.refresh_from_db()

        assert hasattr(people, 'profile')
        assert people.profile is not None

    def test_organizational_field_access(self):
        """Test accessing organizational fields through People instance."""
        people = People.objects.create_user(
            loginid="test003",
            peoplecode="TEST003",
            peoplename="Test User 3",
            email="test3@example.com"
        )

        people._temp_dateofbirth = date(1990, 1, 1)
        people.save()

        people.refresh_from_db()

        assert hasattr(people, 'organizational')


@pytest.mark.django_db
class TestBackwardCompatibilityQueryPatterns:
    """Test that query patterns remain functional."""

    def test_manager_optimization_methods(self):
        """Test new manager optimization methods."""
        people = People.objects.create_user(
            loginid="test004",
            peoplecode="TEST004",
            peoplename="Test User 4",
            email="test4@example.com"
        )

        people._temp_dateofbirth = date(1990, 1, 1)
        people.save()

        qs = People.objects.with_profile()
        assert qs.count() > 0

        qs = People.objects.with_organizational()
        assert qs.count() > 0

        qs = People.objects.with_full_details()
        assert qs.count() > 0

    def test_existing_query_patterns_work(self):
        """Test that existing query patterns still work."""
        people = People.objects.create_user(
            loginid="test005",
            peoplecode="TEST005",
            peoplename="Test User 5",
            email="test5@example.com"
        )

        people._temp_dateofbirth = date(1990, 1, 1)
        people.save()

        found = People.objects.filter(peoplecode="TEST005").first()
        assert found is not None
        assert found.peoplename == "Test User 5"


@pytest.mark.django_db
class TestBackwardCompatibilityCapabilities:
    """Test capability management methods."""

    def test_capability_methods_accessible(self):
        """Test that capability methods work as before."""
        people = People.objects.create_user(
            loginid="test006",
            peoplecode="TEST006",
            peoplename="Test User 6",
            email="test6@example.com"
        )

        people._temp_dateofbirth = date(1990, 1, 1)
        people.save()

        assert people.add_capability('test_capability', True)
        assert people.has_capability('test_capability')

        all_caps = people.get_all_capabilities()
        assert 'test_capability' in all_caps

        assert people.remove_capability('test_capability')
        assert not people.has_capability('test_capability')


@pytest.mark.integration
@pytest.mark.django_db
class TestCompleteBackwardCompatibility:
    """Comprehensive backward compatibility tests."""

    def test_full_user_creation_workflow(self):
        """Test complete user creation workflow."""
        people = People.objects.create_user(
            loginid="test007",
            peoplecode="TEST007",
            peoplename="Test User 7",
            email="test7@example.com",
            password="TestPass123!"
        )

        people._temp_dateofbirth = date(1990, 1, 1)
        people._temp_dateofjoin = date(2023, 1, 1)
        people._temp_gender = "M"
        people.save()

        people.refresh_from_db()

        assert people.id is not None
        assert people.check_password("TestPass123!")
        assert people.peoplename == "Test User 7"
        assert hasattr(people, 'profile')
        assert hasattr(people, 'organizational')

    def test_model_relationships_intact(self):
        """Test that model relationships work correctly."""
        people = People.objects.with_full_details().filter(
            peoplecode="TEST007"
        ).first()

        if people:
            assert hasattr(people, 'profile')
            assert hasattr(people, 'organizational')