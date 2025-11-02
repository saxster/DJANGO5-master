"""Pytest configuration shared across the IntelliWiz test suites."""

from __future__ import annotations

import os
from typing import Generator

import pytest

# Ensure pytest-django boots with the dedicated test settings module.
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "intelliwiz_config.settings_test")


@pytest.fixture(scope="session", autouse=True)
def configure_django_settings(django_settings) -> Generator[None, None, None]:
    """Apply global tweaks for the test environment."""

    django_settings.TIME_ZONE = "UTC"
    django_settings.USE_TZ = True

    yield


@pytest.fixture
def api_client():
    """Return a REST framework API client for request-driven tests."""

    from rest_framework.test import APIClient

    return APIClient()

