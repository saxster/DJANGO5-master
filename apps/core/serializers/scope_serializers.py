"""
Scope API Serializers
=====================
Pydantic models for type-safe scope and saved views APIs.

Follows .claude/rules.md:
- Rule #6: Serializer < 100 lines
- Type-safe API contracts for Kotlin/Swift codegen
"""

from datetime import date
from typing import List, Optional
from pydantic import BaseModel, Field, validator


class ScopeConfig(BaseModel):
    """
    User scope configuration for filtering data across the platform.
    """
    tenant_id: int = Field(..., description="Tenant ID", ge=1)
    client_ids: List[int] = Field(
        default_factory=list,
        description="Selected client IDs for multi-site view"
    )
    bu_ids: List[int] = Field(
        default_factory=list,
        description="Selected site/BU IDs for filtering"
    )
    time_range: str = Field(
        default="TODAY",
        description="Time range selector",
        pattern="^(TODAY|24H|7D|30D|CUSTOM)$"
    )
    date_from: Optional[date] = Field(
        None,
        description="Custom range start date (ISO format)"
    )
    date_to: Optional[date] = Field(
        None,
        description="Custom range end date (ISO format)"
    )
    shift_id: Optional[int] = Field(
        None,
        description="Filter by shift ID (null = all shifts)"
    )
    tz: str = Field(
        default="Asia/Kolkata",
        description="Timezone for date/time calculations"
    )

    @validator("date_to")
    def validate_date_range(cls, v, values):
        """Ensure date_to >= date_from"""
        if v and "date_from" in values and values["date_from"]:
            if v < values["date_from"]:
                raise ValueError("date_to must be >= date_from")
        return v

    class Config:
        json_schema_extra = {
            "example": {
                "tenant_id": 1,
                "client_ids": [2, 3],
                "bu_ids": [10, 11, 12],
                "time_range": "7D",
                "shift_id": 5,
                "tz": "Asia/Kolkata"
            }
        }


class ScopeUpdateRequest(BaseModel):
    """Request to update user scope"""
    scope: ScopeConfig = Field(..., description="New scope configuration")


class ScopeResponse(BaseModel):
    """Response with current scope"""
    scope: ScopeConfig
    user_id: int
    last_updated: str  # ISO datetime


class SavedViewCreate(BaseModel):
    """Request to create a saved view"""
    name: str = Field(..., min_length=1, max_length=200, description="View name")
    description: Optional[str] = Field("", description="Optional description")
    view_type: str = Field(
        default="CUSTOM",
        description="View type category"
    )
    scope_config: ScopeConfig = Field(..., description="Scope configuration")
    filters: dict = Field(default_factory=dict, description="Domain-specific filters")
    visible_panels: List[str] = Field(default_factory=list, description="Panel IDs to show")
    sort_order: List[dict] = Field(default_factory=list, description="Sort configuration")
    sharing_level: str = Field(
        default="PRIVATE",
        description="Who can access this view"
    )
    page_url: str = Field(..., max_length=500, description="Page URL")


class SavedViewResponse(BaseModel):
    """Saved view data"""
    id: int
    name: str
    description: str
    view_type: str
    scope_config: ScopeConfig
    filters: dict
    visible_panels: List[str]
    sort_order: List[dict]
    sharing_level: str
    is_default: bool
    view_count: int
    created_by_username: str
    created_at: str
    last_accessed_at: Optional[str]


class SavedViewListResponse(BaseModel):
    """List of saved views"""
    views: List[SavedViewResponse]
    count: int


__all__ = [
    "ScopeConfig",
    "ScopeUpdateRequest",
    "ScopeResponse",
    "SavedViewCreate",
    "SavedViewResponse",
    "SavedViewListResponse",
]
