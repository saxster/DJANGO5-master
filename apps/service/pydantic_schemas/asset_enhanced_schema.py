"""
Enhanced Pydantic Schemas for Asset Domain

Complete type-safe models for Kotlin/Swift codegen.
Mirrors apps/activity/serializers.py AssetSerializer patterns.

Compliance with .claude/rules.md:
- Rule #7: Models < 150 lines
- Rule #10: Comprehensive validation
- Rule #13: Required validation patterns

For Kotlin Apollo codegen compatibility.
"""

from pydantic import BaseModel, Field, field_validator
from typing import Optional, List, Dict, Any
from datetime import datetime
from uuid import UUID
from decimal import Decimal

from apps.core.validation_pydantic.pydantic_base import BusinessLogicModel, TenantAwareModel


# ============================================================================
# ASSET MODELS
# ============================================================================

class AssetDetailSchema(BusinessLogicModel):
    """
    Complete Asset schema for mobile operations.

    Mirrors apps/activity/models/asset_model.py Asset model.
    Maps to Kotlin data class: AssetDetail
    """
    # Identity fields
    id: Optional[int] = Field(None, description="Server-assigned ID")
    assetcode: str = Field(..., min_length=1, max_length=50, description="Unique asset code")
    assetname: str = Field(..., min_length=2, max_length=200, description="Asset name")

    # Status & classification
    runningstatus: Optional[str] = Field(None, max_length=50, description="Running status")
    type: Optional[str] = Field(None, max_length=50, description="Asset type")
    category: Optional[str] = Field(None, max_length=50, description="Asset category")
    subcategory: Optional[str] = Field(None, max_length=50, description="Asset subcategory")
    brand: Optional[str] = Field(None, max_length=100, description="Brand/manufacturer")
    unit: Optional[str] = Field(None, max_length=50, description="Unit of measurement")
    capacity: Optional[Decimal] = Field(None, ge=0, description="Capacity/rating")

    # Hierarchy & location
    identifier: Optional[str] = Field(None, max_length=100, description="Custom identifier")
    parent_id: Optional[int] = Field(None, description="Parent asset ID")
    servprov_id: Optional[int] = Field(None, description="Service provider ID")
    location_id: Optional[int] = Field(None, description="Location ID")
    gpslocation: Optional[str] = Field(None, description="GPS location (GeoJSON Point)")

    # Flags
    iscritical: bool = Field(default=False, description="Whether asset is critical")
    enable: bool = Field(default=True, description="Whether asset is active")

    # Metadata
    asset_extras: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Additional metadata (JSON)")

    # Multi-tenant fields
    bu_id: Optional[int] = Field(None, description="Business unit ID")
    client_id: Optional[int] = Field(None, description="Client ID")

    # Audit fields
    ctzoffset: Optional[int] = Field(None, description="Client timezone offset (minutes)")
    created_at: Optional[datetime] = Field(None, description="Creation timestamp")
    updated_at: Optional[datetime] = Field(None, description="Last update timestamp")

    @field_validator('assetcode')
    @classmethod
    def validate_assetcode_format(cls, v: str) -> str:
        """Validate asset code format (uppercase alphanumeric)."""
        v = v.upper().strip()
        import re
        if not re.match(r'^[A-Z0-9_-]+$', v):
            raise ValueError("Asset code must contain only uppercase letters, numbers, hyphens, and underscores")
        return v

    @field_validator('assetname')
    @classmethod
    def validate_assetname_content(cls, v: str) -> str:
        """Validate asset name."""
        v = v.strip()
        if len(v) < 2:
            raise ValueError("Asset name must be at least 2 characters")
        if len(v) > 200:
            raise ValueError("Asset name cannot exceed 200 characters")
        return v

    @field_validator('capacity')
    @classmethod
    def validate_capacity_positive(cls, v: Optional[Decimal]) -> Optional[Decimal]:
        """Validate capacity is positive."""
        if v is not None and v < 0:
            raise ValueError("Capacity must be positive")
        return v


class AssetListResponseSchema(BaseModel):
    """
    Response schema for asset list operations.

    Maps to Kotlin: data class AssetListResponse
    """
    assets: List[AssetDetailSchema] = Field(default_factory=list, description="List of assets")
    total_count: int = Field(..., ge=0, description="Total number of assets")
    page: Optional[int] = Field(None, ge=1, description="Current page number")
    page_size: Optional[int] = Field(None, ge=1, le=100, description="Items per page")
    has_next: bool = Field(default=False, description="Whether more pages exist")


class AssetSyncRequestSchema(TenantAwareModel):
    """
    Request schema for asset sync operations.

    Maps to Kotlin: data class AssetSyncRequest
    """
    assets: List[AssetDetailSchema] = Field(..., min_items=1, max_items=100, description="Assets to sync (max 100)")
    device_id: str = Field(..., min_length=5, max_length=255, description="Device identifier")
    idempotency_key: str = Field(..., min_length=16, max_length=255, description="Idempotency key")
    full_sync: bool = Field(default=False, description="Whether this is a full sync")
    since_timestamp: Optional[datetime] = Field(None, description="Last sync timestamp (for delta sync)")


__all__ = [
    'AssetDetailSchema',
    'AssetListResponseSchema',
    'AssetSyncRequestSchema',
]
