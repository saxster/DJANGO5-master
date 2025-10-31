"""
Validation Package

Contains Pydantic-based validation models and utilities for type-safe
API contracts and business logic validation.

IMPORTANT: This package coexists with apps/core/validation.py module.
- validation.py: Contains XSSPrevention, InputValidator, SecureFormMixin, etc.
- validation/: Contains Pydantic-based models (pydantic_base, json_field_models)

Modules:
- pydantic_base: Base Pydantic models for Django integration
- json_field_models: Pydantic models for JSON field validation
"""

# Import from the validation/ package
from .pydantic_base import BaseDjangoModel, BusinessLogicModel

__all__ = [
    'BaseDjangoModel',
    'BusinessLogicModel',
]
