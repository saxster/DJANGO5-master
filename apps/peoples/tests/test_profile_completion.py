"""Tests for PeopleProfile completion tracking."""
import pytest
from django.utils import timezone
from apps.peoples.models import People, PeopleProfile


class TestProfileCompletion:
    """Test profile completion calculation methods."""

    @pytest.mark.django_db
    def test_calculate_completion_zero_fields(self, basic_user):
        """Empty profile should return 0%."""
        profile = PeopleProfile.objects.create(
            people=basic_user,
            dateofbirth=timezone.now().date()  # Required field
        )

        percentage = profile.calculate_completion_percentage()
        assert percentage == 25  # Only dateofbirth filled (1/4 = 25%)

    @pytest.mark.django_db
    def test_calculate_completion_all_fields(self, basic_user):
        """Profile with 4/4 fields should return 100%."""
        profile = PeopleProfile.objects.create(
            people=basic_user,
            peopleimg='profiles/test.jpg',
            dateofbirth=timezone.now().date(),
            dateofjoin=timezone.now().date(),
            gender='M'
        )

        percentage = profile.calculate_completion_percentage()
        assert percentage == 100

    @pytest.mark.django_db
    def test_get_missing_fields_returns_subset(self, basic_user):
        """Partial profile should return only missing fields."""
        profile = PeopleProfile.objects.create(
            people=basic_user,
            gender='M',
            dateofbirth=timezone.now().date()
        )

        missing = profile.get_missing_profile_fields()
        assert len(missing) == 2
        assert {'field': 'peopleimg', 'display_name': 'Profile Image'} in missing
        assert {'field': 'dateofjoin', 'display_name': 'Date of Joining'} in missing

    @pytest.mark.django_db
    def test_is_profile_complete_false_by_default(self, basic_user):
        """Incomplete profile should return False."""
        profile = PeopleProfile.objects.create(
            people=basic_user,
            dateofbirth=timezone.now().date()
        )

        assert profile.is_profile_complete() is False

    @pytest.mark.django_db
    def test_is_profile_complete_true_when_100_percent(self, basic_user):
        """Complete profile should return True."""
        profile = PeopleProfile.objects.create(
            people=basic_user,
            peopleimg='profiles/test.jpg',
            dateofbirth=timezone.now().date(),
            dateofjoin=timezone.now().date(),
            gender='M',
            profile_completion_percentage=100
        )

        assert profile.is_profile_complete() is True
