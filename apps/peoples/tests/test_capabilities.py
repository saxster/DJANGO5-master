"""Tests for capability system."""
import pytest
from apps.peoples.constants import default_capabilities, get_admin_capabilities
from apps.peoples.models import People


class TestCapabilities:
    """Test capability defaults and admin capabilities."""

    def test_default_capabilities_has_13_keys(self):
        """Default capabilities should have all 13 keys."""
        caps = default_capabilities()
        assert len(caps) == 13

    def test_default_capabilities_onboarding_false(self):
        """Onboarding should default to False."""
        caps = default_capabilities()
        assert caps['canAccessOnboarding'] is False

    def test_default_capabilities_voice_false(self):
        """Voice features should default to False."""
        caps = default_capabilities()
        assert caps['canUseVoiceFeatures'] is False
        assert caps['canUseVoiceBiometrics'] is False

    def test_admin_capabilities_onboarding_true(self):
        """Admins should have onboarding enabled."""
        caps = get_admin_capabilities()
        assert caps['canAccessOnboarding'] is True

    def test_admin_capabilities_voice_true(self):
        """Admins should have voice features enabled."""
        caps = get_admin_capabilities()
        assert caps['canUseVoiceFeatures'] is True
        assert caps['canUseVoiceBiometrics'] is True

    @pytest.mark.django_db
    def test_user_get_all_capabilities_includes_defaults(self, basic_user):
        """get_all_capabilities should merge with defaults."""
        basic_user.capabilities = {}  # Empty capabilities
        basic_user.save()

        caps = basic_user.get_all_capabilities()
        assert 'canAccessOnboarding' in caps
        assert 'canUseVoiceFeatures' in caps
        assert 'canUseVoiceBiometrics' in caps
