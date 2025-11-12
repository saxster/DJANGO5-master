"""Pytest configuration shared across the IntelliWiz test suites."""

from __future__ import annotations

import os
from typing import Generator

import pytest

# Ensure pytest-django boots with the dedicated test settings module.
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "intelliwiz_config.settings_test")


# Temporarily disabled due to scope mismatch with pytest-django settings fixture
# @pytest.fixture(scope="session", autouse=True)
# def configure_django_settings(settings) -> Generator[None, None, None]:
#     """Apply global tweaks for the test environment."""
#
#     settings.TIME_ZONE = "UTC"
#     settings.USE_TZ = True
#
#     yield


@pytest.fixture
def api_client():
    """Return a REST framework API client for request-driven tests."""

    from rest_framework.test import APIClient

    return APIClient()


# Admin Enhancement Test Fixtures

@pytest.fixture
def tenant():
    """Create a test tenant."""
    from apps.tenants.models import Tenant
    return Tenant.objects.create(name="Test Tenant")


@pytest.fixture
def user(tenant):
    """Create a test user."""
    from django.contrib.auth import get_user_model
    User = get_user_model()
    return User.objects.create_user(
        username="testuser",
        email="test@test.com",
        tenant=tenant,
        firstname="Test",
        lastname="User"
    )


@pytest.fixture
def ticket(tenant, user):
    """Create a test ticket."""
    from apps.y_helpdesk.models import Ticket
    return Ticket.objects.create(
        tenant=tenant,
        cuser=user,
        ticketdesc="Test ticket",
        priority="HIGH",
        status="OPEN"
    )


@pytest.fixture
def person_with_activity(tenant, user):
    """Create a person with various activities for timeline testing."""
    from apps.y_helpdesk.models import Ticket
    from apps.attendance.models import Attendance
    from django.utils import timezone
    
    # Create tickets
    Ticket.objects.create(
        tenant=tenant,
        cuser=user,
        ticketdesc="Created ticket",
        status="OPEN"
    )
    
    # Create attendance records
    Attendance.objects.create(
        tenant=tenant,
        people=user,
        attendance_date=timezone.now().date(),
        check_in=timezone.now()
    )
    
    return user

