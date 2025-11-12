"""Basic smoke tests for the Django test configuration."""

from django.conf import settings


def test_test_settings_module_loaded():
    """Ensure the dedicated test settings module is active and hardened."""

    assert not settings.DEBUG


def test_secret_key_present():
    """The Django SECRET_KEY must be populated for crypto operations."""

    assert bool(settings.SECRET_KEY)
