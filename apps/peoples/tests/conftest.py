"""
Test configuration and fixtures for peoples app.

Provides reusable fixtures for testing authentication, user models,
profiles, and organizational structures.
"""
import pytest
from datetime import datetime, timezone as dt_timezone
from django.test import RequestFactory, Client
from django.contrib.auth import get_user_model
from django.contrib.sessions.middleware import SessionMiddleware
from apps.client_onboarding.models import Bt
from apps.core_onboarding.models import TypeAssist
from apps.activity.models import Location

User = get_user_model()


@pytest.fixture
def rf():
    """Request factory for creating mock HTTP requests."""
    return RequestFactory()


@pytest.fixture
def client():
    """Django test client for integration tests."""
    return Client()


@pytest.fixture
def test_tenant():
    """Create a test tenant (business unit)."""
    return Bt.objects.create(
        bucode="TESTPEOPLE",
        buname="People Test Tenant",
        enable=True
    )


@pytest.fixture
def test_location(test_tenant):
    """Create a test location for organizational testing."""
    return Location.objects.create(
        site="TEST_SITE",
        location="Test Location",
        client=test_tenant,
        bu=test_tenant
    )


@pytest.fixture
def test_department(test_tenant):
    """Create a test department TypeAssist."""
    return TypeAssist.objects.create(
        typename="Department",
        typeval="Engineering",
        client=test_tenant,
        enable=True
    )


@pytest.fixture
def test_designation(test_tenant):
    """Create a test designation TypeAssist."""
    return TypeAssist.objects.create(
        typename="Designation",
        typeval="Software Engineer",
        client=test_tenant,
        enable=True
    )


@pytest.fixture
def basic_user(test_tenant):
    """
    Create a basic test user with minimal required fields.

    Returns People instance with:
    - Basic authentication fields
    - No profile or organizational data
    - Active status
    """
    from apps.peoples.models import People

    user = People.objects.create(
        peoplecode="TEST001",
        peoplename="Test User",
        loginid="testuser",
        email="testuser@example.com",
        mobno="1234567890",
        client=test_tenant,
        enable=True
    )
    user.set_password("TestPass123!")
    user.save()
    return user


@pytest.fixture
def user_with_profile(test_tenant, test_location, test_department, test_designation):
    """
    Create a test user with complete profile and organizational data.

    Returns People instance with:
    - PeopleProfile (gender, DOB, join date, image)
    - PeopleOrganizational (location, department, designation)
    - Active status
    """
    from apps.peoples.models import People, PeopleProfile, PeopleOrganizational

    user = People.objects.create(
        peoplecode="TEST002",
        peoplename="Test User With Profile",
        loginid="profileuser",
        email="profileuser@example.com",
        mobno="9876543210",
        client=test_tenant,
        enable=True
    )
    user.set_password("ProfilePass123!")
    user.save()

    # Create profile
    PeopleProfile.objects.create(
        people=user,
        gender="Male",
        dateofbirth=datetime(1990, 1, 1, tzinfo=dt_timezone.utc).date(),
        dateofjoin=datetime(2020, 1, 1, tzinfo=dt_timezone.utc).date()
    )

    # Create organizational data
    PeopleOrganizational.objects.create(
        people=user,
        location=test_location,
        department=test_department,
        designation=test_designation
    )

    return user


@pytest.fixture
def admin_user(test_tenant):
    """
    Create an admin/superuser for testing administrative operations.

    Returns People instance with:
    - Superuser privileges
    - Staff status
    - All permissions
    """
    from apps.peoples.models import People

    admin = People.objects.create(
        peoplecode="ADMIN001",
        peoplename="Admin User",
        loginid="admin",
        email="admin@example.com",
        mobno="5555555555",
        client=test_tenant,
        enable=True,
        is_staff=True,
        is_superuser=True
    )
    admin.set_password("AdminPass123!")
    admin.save()
    return admin


@pytest.fixture
def manager_user(test_tenant, user_with_profile):
    """
    Create a manager user who supervises other users.

    Returns People instance with:
    - Complete profile
    - Organizational data
    - Direct reports (user_with_profile reports to this manager)
    """
    from apps.peoples.models import People, PeopleProfile, PeopleOrganizational

    manager = People.objects.create(
        peoplecode="MGR001",
        peoplename="Manager User",
        loginid="manager",
        email="manager@example.com",
        mobno="4444444444",
        client=test_tenant,
        enable=True
    )
    manager.set_password("ManagerPass123!")
    manager.save()

    # Create profile
    PeopleProfile.objects.create(
        people=manager,
        gender="Female",
        dateofbirth=datetime(1985, 1, 1, tzinfo=dt_timezone.utc).date(),
        dateofjoin=datetime(2015, 1, 1, tzinfo=dt_timezone.utc).date()
    )

    # Set up reporting relationship
    org = user_with_profile.organizational
    org.reportto = manager
    org.save()

    return manager


@pytest.fixture
def authenticated_request(rf, basic_user, test_tenant):
    """
    Create an authenticated HTTP request with session data.

    Includes:
    - Session middleware
    - User authentication
    - Tenant context (client_id, bu_id)
    """
    request = rf.get("/")
    middleware = SessionMiddleware(lambda req: None)
    middleware.process_request(request)
    request.session.save()

    # Set session data
    request.session["client_id"] = test_tenant.id
    request.session["bu_id"] = test_tenant.id
    request.session["user_id"] = basic_user.id
    request.user = basic_user

    return request


@pytest.fixture
def permission_group(test_tenant):
    """Create a test permission group."""
    from apps.peoples.models import Pgroup

    return Pgroup.objects.create(
        groupname="Test Group",
        groupcode="TESTGRP",
        description="Test permission group",
        client=test_tenant
    )


@pytest.fixture
def capability():
    """Create a test capability."""
    from apps.peoples.models import Capability

    return Capability.objects.create(
        capability_name="test_feature",
        category="testing",
        display_name="Test Feature"
    )


@pytest.fixture
def mock_jwt_token(basic_user):
    """
    Generate a mock JWT token for testing API authentication.

    Returns a valid JWT token string for the basic_user.
    """
    from rest_framework_simplejwt.tokens import RefreshToken

    refresh = RefreshToken.for_user(basic_user)
    return str(refresh.access_token)
