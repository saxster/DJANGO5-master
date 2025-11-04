"""
Custom assertion helpers for testing.

Provides domain-specific assertions for common testing patterns
across the facility management platform.
"""
from datetime import datetime, timezone as dt_timezone
from typing import Any, Dict, List, Optional
from django.db import models
from django.http import HttpResponse, JsonResponse
from django.core.exceptions import ValidationError


def assert_model_fields_equal(obj1, obj2, fields: List[str], exclude_fields: Optional[List[str]] = None):
    """
    Assert that two model instances have equal values for specified fields.

    Args:
        obj1: First model instance
        obj2: Second model instance
        fields: List of field names to compare
        exclude_fields: Optional list of fields to exclude from comparison

    Raises:
        AssertionError: If any field values differ
    """
    exclude_fields = exclude_fields or []
    fields_to_check = [f for f in fields if f not in exclude_fields]

    for field in fields_to_check:
        val1 = getattr(obj1, field)
        val2 = getattr(obj2, field)
        assert val1 == val2, f"Field '{field}' differs: {val1} != {val2}"


def assert_model_saved(model_instance):
    """
    Assert that model instance has been saved to database.

    Args:
        model_instance: Django model instance

    Raises:
        AssertionError: If instance has not been saved (pk is None)
    """
    assert model_instance.pk is not None, "Model instance has not been saved (pk is None)"


def assert_model_not_saved(model_instance):
    """
    Assert that model instance has not been saved to database.

    Args:
        model_instance: Django model instance

    Raises:
        AssertionError: If instance has been saved (pk is not None)
    """
    assert model_instance.pk is None, f"Model instance has been saved (pk={model_instance.pk})"


def assert_validation_error(func, *args, **kwargs):
    """
    Assert that function raises ValidationError.

    Args:
        func: Function to call
        *args: Positional arguments for function
        **kwargs: Keyword arguments for function

    Raises:
        AssertionError: If ValidationError is not raised
    """
    try:
        func(*args, **kwargs)
        raise AssertionError("Expected ValidationError was not raised")
    except ValidationError:
        pass  # Expected


def assert_response_status(response: HttpResponse, expected_status: int):
    """
    Assert HTTP response has expected status code.

    Args:
        response: HttpResponse instance
        expected_status: Expected HTTP status code

    Raises:
        AssertionError: If status code doesn't match
    """
    assert response.status_code == expected_status, \
        f"Response status {response.status_code} != expected {expected_status}"


def assert_response_contains(response: HttpResponse, text: str):
    """
    Assert HTTP response contains specific text.

    Args:
        response: HttpResponse instance
        text: Text that should be in response

    Raises:
        AssertionError: If text not found in response
    """
    content = response.content.decode("utf-8")
    assert text in content, f"Response does not contain '{text}'"


def assert_json_response(response: HttpResponse, expected_data: Dict[str, Any]):
    """
    Assert JSON response contains expected data.

    Args:
        response: HttpResponse instance
        expected_data: Dict of expected JSON fields

    Raises:
        AssertionError: If response is not JSON or data doesn't match
    """
    assert isinstance(response, JsonResponse) or \
           response.get("Content-Type") == "application/json", \
           "Response is not JSON"

    import json
    actual_data = json.loads(response.content)

    for key, expected_value in expected_data.items():
        assert key in actual_data, f"Key '{key}' not in JSON response"
        assert actual_data[key] == expected_value, \
            f"JSON field '{key}': {actual_data[key]} != {expected_value}"


def assert_tenant_isolated(queryset, tenant):
    """
    Assert that queryset only contains objects from specified tenant.

    Args:
        queryset: Django queryset
        tenant: Tenant instance (Bt model)

    Raises:
        AssertionError: If any objects from other tenants found
    """
    other_tenant_count = queryset.exclude(tenant=tenant).count()
    assert other_tenant_count == 0, \
        f"Found {other_tenant_count} objects from other tenants (should be 0)"


def assert_gps_location_valid(location):
    """
    Assert GPS location (Point) is valid.

    Args:
        location: PostGIS Point instance

    Raises:
        AssertionError: If location is invalid
    """
    from django.contrib.gis.geos import Point

    assert isinstance(location, Point), f"Location is not a Point: {type(location)}"
    assert location.srid == 4326, f"Location SRID {location.srid} != 4326 (WGS84)"
    assert -90 <= location.y <= 90, f"Latitude {location.y} out of range"
    assert -180 <= location.x <= 180, f"Longitude {location.x} out of range"


def assert_datetime_in_range(dt, start, end):
    """
    Assert datetime is within specified range.

    Args:
        dt: Datetime to check
        start: Start of range (inclusive)
        end: End of range (inclusive)

    Raises:
        AssertionError: If datetime outside range
    """
    assert start <= dt <= end, \
        f"Datetime {dt} not in range [{start}, {end}]"


def assert_datetime_future(dt, reference=None):
    """
    Assert datetime is in the future.

    Args:
        dt: Datetime to check
        reference: Reference datetime (default: now)

    Raises:
        AssertionError: If datetime is not in future
    """
    reference = reference or datetime.now(dt_timezone.utc)
    assert dt > reference, f"Datetime {dt} is not after {reference}"


def assert_datetime_past(dt, reference=None):
    """
    Assert datetime is in the past.

    Args:
        dt: Datetime to check
        reference: Reference datetime (default: now)

    Raises:
        AssertionError: If datetime is not in past
    """
    reference = reference or datetime.now(dt_timezone.utc)
    assert dt < reference, f"Datetime {dt} is not before {reference}"


def assert_audit_fields_set(model_instance):
    """
    Assert that audit fields (cdby, cdon, mdby, mdon) are set.

    Args:
        model_instance: Django model instance with BaseModel fields

    Raises:
        AssertionError: If any audit field is missing
    """
    assert hasattr(model_instance, "cdby") and model_instance.cdby is not None, \
        "cdby (created by) field not set"
    assert hasattr(model_instance, "cdon") and model_instance.cdon is not None, \
        "cdon (created on) field not set"
    assert hasattr(model_instance, "mdby") and model_instance.mdby is not None, \
        "mdby (modified by) field not set"
    assert hasattr(model_instance, "mdon") and model_instance.mdon is not None, \
        "mdon (modified on) field not set"


def assert_encrypted_field(model_instance, field_name, expected_plaintext=None):
    """
    Assert that field is encrypted (EnhancedSecureString).

    Args:
        model_instance: Django model instance
        field_name: Name of encrypted field
        expected_plaintext: Optional plaintext value to verify decryption

    Raises:
        AssertionError: If field is not encrypted properly
    """
    from apps.peoples.fields import EnhancedSecureString

    field = model_instance._meta.get_field(field_name)
    assert isinstance(field, EnhancedSecureString), \
        f"Field '{field_name}' is not EnhancedSecureString"

    if expected_plaintext:
        actual_value = getattr(model_instance, field_name)
        assert actual_value == expected_plaintext, \
            f"Decrypted value '{actual_value}' != expected '{expected_plaintext}'"


def assert_unique_constraint_violated(model_class, **fields):
    """
    Assert that creating object with fields violates unique constraint.

    Args:
        model_class: Django model class
        **fields: Field values for model creation

    Raises:
        AssertionError: If no unique constraint violation occurs
    """
    from django.db import IntegrityError

    try:
        model_class.objects.create(**fields)
        raise AssertionError("Expected IntegrityError (unique constraint) was not raised")
    except IntegrityError as e:
        assert "unique" in str(e).lower(), \
            f"IntegrityError raised but not due to unique constraint: {e}"


def assert_query_count(queryset, expected_count):
    """
    Assert that queryset returns expected number of objects.

    Args:
        queryset: Django queryset
        expected_count: Expected number of objects

    Raises:
        AssertionError: If count doesn't match
    """
    actual_count = queryset.count()
    assert actual_count == expected_count, \
        f"Queryset count {actual_count} != expected {expected_count}"


def assert_file_exists(file_field):
    """
    Assert that FileField/ImageField has an associated file.

    Args:
        file_field: Django FileField or ImageField instance

    Raises:
        AssertionError: If file does not exist
    """
    assert file_field and file_field.name, "File field is empty"
    assert file_field.storage.exists(file_field.name), \
        f"File does not exist: {file_field.name}"


def assert_permission_denied(func, *args, **kwargs):
    """
    Assert that function raises PermissionDenied exception.

    Args:
        func: Function to call
        *args: Positional arguments
        **kwargs: Keyword arguments

    Raises:
        AssertionError: If PermissionDenied not raised
    """
    from django.core.exceptions import PermissionDenied

    try:
        func(*args, **kwargs)
        raise AssertionError("Expected PermissionDenied was not raised")
    except PermissionDenied:
        pass  # Expected


def assert_contains_correlation_id(response: HttpResponse):
    """
    Assert that HTTP response contains X-Correlation-ID header.

    Args:
        response: HttpResponse instance

    Raises:
        AssertionError: If correlation ID header missing
    """
    assert "X-Correlation-ID" in response, \
        "Response missing X-Correlation-ID header"

    correlation_id = response["X-Correlation-ID"]
    assert correlation_id, "X-Correlation-ID header is empty"
