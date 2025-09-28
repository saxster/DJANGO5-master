"""
Core Serializer Utilities Module

Provides secure base serializers and validation mixins for REST Framework.

This module addresses Rule #13 violations (Form Validation Requirements)
by providing reusable validation infrastructure for all serializers.

Key Components:
- SecureSerializerMixin: Base mixin with common validation patterns
- ValidatedModelSerializer: Base class for all model serializers
- Field validators: Reusable validation functions

Compliance:
- Rule #13: All serializers must have explicit field lists and validation
- Rule #11: Specific exception handling (no generic Exception catching)
- Rule #15: No sensitive data in logs
"""

from .base_serializers import (
    SecureSerializerMixin,
    ValidatedModelSerializer,
    TenantAwareSerializer,
)
from .validators import (
    SerializerValidators,
    validate_code_field,
    validate_name_field,
    validate_email_field,
    validate_phone_field,
    validate_gps_field,
    validate_date_range,
)

__all__ = [
    'SecureSerializerMixin',
    'ValidatedModelSerializer',
    'TenantAwareSerializer',
    'SerializerValidators',
    'validate_code_field',
    'validate_name_field',
    'validate_email_field',
    'validate_phone_field',
    'validate_gps_field',
    'validate_date_range',
]