"""
Common test helper functions.

Provides reusable utility functions for test setup, data generation,
and common testing patterns across all apps.
"""
import uuid
from datetime import datetime, timezone as dt_timezone, timedelta
from typing import Dict, Any, Optional, List
from django.contrib.auth import get_user_model
from django.contrib.gis.geos import Point
from django.test import RequestFactory
from django.contrib.sessions.middleware import SessionMiddleware

User = get_user_model()


def create_test_request(user=None, method="GET", path="/", session_data=None):
    """
    Create a test HTTP request with optional authentication and session.

    Args:
        user: User instance to authenticate request with
        method: HTTP method (GET, POST, etc.)
        path: Request path
        session_data: Dict of session key-value pairs

    Returns:
        HttpRequest instance with session configured
    """
    factory = RequestFactory()
    request = getattr(factory, method.lower())(path)

    # Add session middleware
    middleware = SessionMiddleware(lambda req: None)
    middleware.process_request(request)
    request.session.save()

    # Set session data
    if session_data:
        for key, value in session_data.items():
            request.session[key] = value

    # Authenticate user
    if user:
        request.user = user
        request.session["user_id"] = user.id
    else:
        from django.contrib.auth.models import AnonymousUser
        request.user = AnonymousUser()

    return request


def generate_unique_code(prefix="TEST", length=6):
    """
    Generate a unique code with prefix for test data.

    Args:
        prefix: Code prefix (default: "TEST")
        length: Length of random suffix (default: 6)

    Returns:
        Unique code string (e.g., "TEST-ABC123")
    """
    return f"{prefix}-{uuid.uuid4().hex[:length].upper()}"


def generate_gps_location(lat=1.3521, lon=103.8198):
    """
    Generate a PostGIS Point for GPS coordinates.

    Args:
        lat: Latitude (default: Singapore)
        lon: Longitude (default: Singapore)

    Returns:
        Point instance with WGS84 coordinates
    """
    return Point(lon, lat, srid=4326)


def create_date_range(days_ahead=7, days_behind=0):
    """
    Create start and end dates for testing.

    Args:
        days_ahead: Days from now for end date
        days_behind: Days before now for start date

    Returns:
        Tuple of (start_date, end_date)
    """
    now = datetime.now(dt_timezone.utc)
    start_date = (now - timedelta(days=days_behind)).date()
    end_date = (now + timedelta(days=days_ahead)).date()
    return start_date, end_date


def create_datetime_range(hours_ahead=2, hours_behind=0):
    """
    Create start and end datetimes for testing.

    Args:
        hours_ahead: Hours from now for end datetime
        hours_behind: Hours before now for start datetime

    Returns:
        Tuple of (start_datetime, end_datetime)
    """
    now = datetime.now(dt_timezone.utc)
    start_datetime = now - timedelta(hours=hours_behind)
    end_datetime = now + timedelta(hours=hours_ahead)
    return start_datetime, end_datetime


def assert_queryset_equal(qs1, qs2, transform=None, ordered=False):
    """
    Assert that two querysets contain the same objects.

    Args:
        qs1: First queryset
        qs2: Second queryset
        transform: Optional function to transform objects before comparison
        ordered: Whether order matters (default: False)

    Raises:
        AssertionError: If querysets don't match
    """
    if transform:
        list1 = [transform(obj) for obj in qs1]
        list2 = [transform(obj) for obj in qs2]
    else:
        list1 = list(qs1)
        list2 = list(qs2)

    if ordered:
        assert list1 == list2, f"Querysets not equal (ordered): {list1} != {list2}"
    else:
        assert set(list1) == set(list2), f"Querysets not equal (unordered): {set(list1)} != {set(list2)}"


def assert_datetime_close(dt1, dt2, tolerance_seconds=5):
    """
    Assert that two datetimes are within tolerance of each other.

    Args:
        dt1: First datetime
        dt2: Second datetime
        tolerance_seconds: Maximum difference in seconds (default: 5)

    Raises:
        AssertionError: If datetimes differ by more than tolerance
    """
    diff = abs((dt1 - dt2).total_seconds())
    assert diff <= tolerance_seconds, f"Datetimes differ by {diff}s (tolerance: {tolerance_seconds}s)"


def assert_json_contains(json_data, expected_keys):
    """
    Assert that JSON data contains all expected keys.

    Args:
        json_data: Dict of JSON data
        expected_keys: List of keys that must be present

    Raises:
        AssertionError: If any expected key is missing
    """
    missing_keys = set(expected_keys) - set(json_data.keys())
    assert not missing_keys, f"Missing keys in JSON: {missing_keys}"


def get_or_create_test_tenant(code="TESTBASE", name="Test Base Tenant"):
    """
    Get or create a base test tenant for tests.

    Args:
        code: Tenant code
        name: Tenant name

    Returns:
        Bt (tenant) instance
    """
    from apps.client_onboarding.models import Bt

    tenant, _ = Bt.objects.get_or_create(
        bucode=code,
        defaults={"buname": name, "enable": True}
    )
    return tenant


def get_or_create_test_user(username="testuser", tenant=None):
    """
    Get or create a base test user for tests.

    Args:
        username: Username for test user
        tenant: Optional tenant to associate with

    Returns:
        People (user) instance
    """
    if tenant is None:
        tenant = get_or_create_test_tenant()

    user, created = User.objects.get_or_create(
        loginid=username,
        defaults={
            "peoplecode": generate_unique_code("USR"),
            "peoplename": username.title(),
            "email": f"{username}@test.example.com",
            "mobno": "1234567890",
            "client": tenant,
            "enable": True
        }
    )

    if created:
        user.set_password("TestPass123!")
        user.save()

    return user


def simulate_database_error(error_class):
    """
    Context manager to simulate database errors for testing.

    Args:
        error_class: Exception class to raise (e.g., IntegrityError)

    Example:
        with simulate_database_error(IntegrityError):
            # Code that should handle database error
            pass
    """
    from unittest.mock import patch
    return patch("django.db.models.Model.save", side_effect=error_class("Simulated error"))


def count_queries(func):
    """
    Decorator to count database queries executed by function.

    Returns:
        Tuple of (result, query_count)

    Example:
        result, count = count_queries(my_function)(args)
        assert count < 10, f"Too many queries: {count}"
    """
    from django.test.utils import override_settings
    from django.db import connection
    from django.test.utils import CaptureQueriesContext

    def wrapper(*args, **kwargs):
        with CaptureQueriesContext(connection) as context:
            result = func(*args, **kwargs)
        return result, len(context.captured_queries)

    return wrapper


def assert_no_n_plus_one(queryset, related_fields):
    """
    Assert that queryset properly prefetches related fields (no N+1 queries).

    Args:
        queryset: Queryset to check
        related_fields: List of related field names to access

    Raises:
        AssertionError: If N+1 query detected
    """
    from django.test.utils import CaptureQueriesContext
    from django.db import connection

    # Force evaluation
    list(queryset)

    # Access related fields and count queries
    with CaptureQueriesContext(connection) as context:
        for obj in queryset:
            for field in related_fields:
                getattr(obj, field)

    # Should be 0 additional queries if properly prefetched
    assert len(context.captured_queries) == 0, \
        f"N+1 query detected: {len(context.captured_queries)} queries for {related_fields}"


def cleanup_test_data(model_class, filters: Dict[str, Any]):
    """
    Clean up test data after tests.

    Args:
        model_class: Django model class
        filters: Dict of filter kwargs to identify test data

    Example:
        cleanup_test_data(User, {"loginid__startswith": "test_"})
    """
    model_class.objects.filter(**filters).delete()
