"""Pydantic validation schemas for People REST endpoints."""

from apps.peoples.pydantic_schemas.person_schemas import (
    CreatePersonSchema,
    UpdatePersonSchema,
    CapabilitiesSchema,
)

__all__ = [
    'CreatePersonSchema',
    'UpdatePersonSchema',
    'CapabilitiesSchema',
]
