"""Tests for People onboarding tracking methods."""
import pytest
from django.utils import timezone
from apps.peoples.models import People


class TestOnboardingTracking:
    """Test onboarding tracking methods on People model."""

    @pytest.mark.django_db
    def test_has_completed_onboarding_false_by_default(self, basic_user):
        """New users should not have completed onboarding."""
        assert basic_user.has_completed_onboarding() is False

    @pytest.mark.django_db
    def test_has_completed_onboarding_true_when_completed(self, basic_user):
        """Users with completion timestamp should return True."""
        basic_user.onboarding_completed_at = timezone.now()
        basic_user.save()
        assert basic_user.has_completed_onboarding() is True

    @pytest.mark.django_db
    def test_has_completed_onboarding_true_when_skipped(self, basic_user):
        """Users who skipped should return True."""
        basic_user.onboarding_skipped = True
        basic_user.save()
        assert basic_user.has_completed_onboarding() is True

    @pytest.mark.django_db
    def test_can_access_onboarding_true_with_capability(self, basic_user):
        """Users with capability should return True."""
        basic_user.capabilities = {'canAccessOnboarding': True}
        basic_user.save()
        assert basic_user.can_access_onboarding() is True

    @pytest.mark.django_db
    def test_can_access_onboarding_false_without_capability(self, basic_user):
        """Users without capability should return False."""
        basic_user.capabilities = {'canAccessOnboarding': False}
        basic_user.save()
        assert basic_user.can_access_onboarding() is False
