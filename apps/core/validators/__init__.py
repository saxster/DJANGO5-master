"""
Centralized Validation Module

Consolidates common validation patterns from across the codebase
to eliminate duplication and provide consistent validation behavior.

Following .claude/rules.md:
- Rule #11: Specific exception handling
- Rule #13: Comprehensive input validation
"""

from .field_validators import (
    validate_email_exists,
    validate_mobile_exists,
    validate_positive_integer,
    validate_percentage,
    validate_json_structure,
    validate_uuid_format
)
from .business_validators import (
    validate_tenant_access,
    validate_user_permissions,
    validate_date_range,
    validate_business_hours
)
from .serializer_mixins import (
    ValidationMixin,
    TenantValidationMixin,
    TimestampValidationMixin
)

__all__ = [
    'validate_email_exists',
    'validate_mobile_exists',
    'validate_positive_integer',
    'validate_percentage',
    'validate_json_structure',
    'validate_uuid_format',
    'validate_tenant_access',
    'validate_user_permissions',
    'validate_date_range',
    'validate_business_hours',
    'ValidationMixin',
    'TenantValidationMixin',
    'TimestampValidationMixin'
]