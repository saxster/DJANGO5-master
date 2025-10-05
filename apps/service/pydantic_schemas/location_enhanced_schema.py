"""
Enhanced Pydantic Schemas for Location Domain

Complete type-safe models for Kotlin/Swift codegen.
Mirrors apps/activity/serializers.py LocationSerializer patterns.

Compliance with .claude/rules.md:
- Rule #7: Models < 150 lines
- Rule #10: Comprehensive validation
- Rule #13: Required validation patterns

For Kotlin Apollo codegen compatibility.
"""

from pydantic import BaseModel, Field, field_validator
from typing import Optional, List
from datetime import datetime
from uuid import UUID

from apps.core.validation.pydantic_base import BusinessLogicModel, TenantAwareModel


# ============================================================================
# LOCATION MODELS
# ============================================================================

class LocationDetailSchema(BusinessLogicModel):
    """
    Complete Location schema for mobile operations.

    Mirrors apps/activity/models/location_model.py Location model.
    Maps to Kotlin data class: LocationDetail
    """
    # Identity fields
    id: Optional[int] = Field(None, description="Server-assigned ID")
    loccode: str = Field(..., min_length=1, max_length=50, description="Unique location code")
    locname: str = Field(..., min_length=2, max_length=200, description="Location name")

    # Status & classification
    locstatus: Optional[str] = Field(None, max_length=50, description="Location status")
    type: Optional[str] = Field(None, max_length=50, description="Location type")

    # Hierarchy
    parent_id: Optional[int] = Field(None, description="Parent location ID")

    # Geographic
    gpslocation: Optional[str] = Field(None, description="GPS location (GeoJSON Point)")

    # Flags
    iscritical: bool = Field(default=False, description="Whether location is critical")
    enable: bool = Field(default=True, description="Whether location is active")

    # Multi-tenant fields
    bu_id: Optional[int] = Field(None, description="Business unit ID")
    client_id: Optional[int] = Field(None, description="Client ID")

    # Audit fields
    ctzoffset: Optional[int] = Field(None, description="Client timezone offset (minutes)")
    created_at: Optional[datetime] = Field(None, description="Creation timestamp")
    updated_at: Optional[datetime] = Field(None, description="Last update timestamp")

    @field_validator('loccode')
    @classmethod
    def validate_loccode_format(cls, v: str) -> str:
        """Validate location code format (uppercase alphanumeric)."""
        v = v.upper().strip()
        import re
        if not re.match(r'^[A-Z0-9_-]+$', v):
            raise ValueError("Location code must contain only uppercase letters, numbers, hyphens, and underscores")
        return v

    @field_validator('locname')
    @classmethod
    def validate_locname_content(cls, v: str) -> str:
        """Validate location name."""
        v = v.strip()
        if len(v) < 2:
            raise ValueError("Location name must be at least 2 characters")
        if len(v) > 200:
            raise ValueError("Location name cannot exceed 200 characters")
        return v


class LocationListResponseSchema(BaseModel):
    """
    Response schema for location list operations.

    Maps to Kotlin: data class LocationListResponse
    """
    locations: List[LocationDetailSchema] = Field(default_factory=list, description="List of locations")
    total_count: int = Field(..., ge=0, description="Total number of locations")
    page: Optional[int] = Field(None, ge=1, description="Current page number")
    page_size: Optional[int] = Field(None, ge=1, le=100, description="Items per page")
    has_next: bool = Field(default=False, description="Whether more pages exist")


class LocationSyncRequestSchema(TenantAwareModel):
    """
    Request schema for location sync operations.

    Maps to Kotlin: data class LocationSyncRequest
    """
    locations: List[LocationDetailSchema] = Field(..., min_items=1, max_items=100, description="Locations to sync")
    device_id: str = Field(..., min_length=5, max_length=255, description="Device identifier")
    idempotency_key: str = Field(..., min_length=16, max_length=255, description="Idempotency key")
    full_sync: bool = Field(default=False, description="Whether this is a full sync")
    since_timestamp: Optional[datetime] = Field(None, description="Last sync timestamp (for delta sync)")


__all__ = [
    'LocationDetailSchema',
    'LocationListResponseSchema',
    'LocationSyncRequestSchema',
]
