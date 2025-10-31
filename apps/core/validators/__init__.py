"""
Centralized Validation Module

Consolidates common validation patterns from across the codebase
to eliminate duplication and provide consistent validation behavior.

Following .claude/rules.md:
- Rule #11: Specific exception handling
- Rule #13: Comprehensive input validation

Ontology: validation_rules=True, business_logic=True, cross_cutting=True
Category: validators, business_rules, input_validation
Domain: field_validation, tenant_validation, business_hours, date_ranges
Responsibility: Reusable validation functions and mixins for serializers/forms
Dependencies: Field validators, business validators, serializer mixins
Security: Email/mobile existence checks, UUID format, JSON structure validation
Validation Patterns:
  - Field validators: Email, mobile, positive integers, percentages, UUID, JSON
  - Business validators: Tenant access, permissions, date ranges, business hours
  - Serializer mixins: Validation, tenant validation, timestamp validation
Use Case: DRY principle for validation logic across serializers/forms/views
Import: Used by serializers in activity, attendance, onboarding, peoples apps
"""

from .field_validators import (
    validate_email_exists,
    validate_mobile_exists,
    validate_positive_integer,
    validate_percentage,
    validate_json_structure,
    validate_uuid_format,
    validate_sync_status,
    validate_version_number,
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
    'validate_sync_status',
    'validate_version_number',
    'validate_tenant_access',
    'validate_user_permissions',
    'validate_date_range',
    'validate_business_hours',
    'ValidationMixin',
    'TenantValidationMixin',
    'TimestampValidationMixin'
]