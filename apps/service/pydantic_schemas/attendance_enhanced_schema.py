"""
Enhanced Pydantic Schemas for Attendance/Tracking Domain

Complete type-safe models for Kotlin/Swift codegen.
Mirrors apps/attendance/serializers/attendance_sync_serializers.py patterns.

Compliance with .claude/rules.md:
- Rule #7: Models < 150 lines
- Rule #10: Comprehensive validation
- Rule #13: Required validation patterns

For Kotlin Apollo codegen compatibility.
"""

from pydantic import BaseModel, Field, field_validator
from typing import Optional, List, Literal
from datetime import datetime, date
from uuid import UUID

from apps.core.validation.pydantic_base import BusinessLogicModel, TenantAwareModel


# ============================================================================
# ATTENDANCE MODELS
# ============================================================================

class AttendanceDetailSchema(BusinessLogicModel):
    """
    Complete Attendance (Tracking) schema for mobile sync.

    Mirrors apps/attendance/models.py Tracking model.
    Maps to Kotlin data class: AttendanceDetail
    """
    # Identity fields
    id: Optional[int] = Field(None, description="Server-assigned ID")
    uuid: Optional[UUID] = Field(None, description="Unique identifier (UUID)")
    mobile_id: Optional[UUID] = Field(None, description="Client-generated unique identifier")

    # Sync metadata
    version: Optional[int] = Field(None, ge=1, description="Version for conflict detection")
    sync_status: Optional[Literal['synced', 'pending_sync', 'sync_error', 'pending_delete']] = Field(
        None,
        description="Sync status"
    )
    last_sync_timestamp: Optional[datetime] = Field(None, description="Last sync timestamp")

    # Core attendance fields
    deviceid: str = Field(..., min_length=1, max_length=255, description="Device identifier")
    gpslocation: Optional[str] = Field(None, description="GPS location (GeoJSON Point)")
    receiveddate: datetime = Field(..., description="When tracking record was received")

    # Person tracking
    peopleid: Optional[int] = Field(None, description="Person ID being tracked")

    # Multi-tenant fields
    bu_id: Optional[int] = Field(None, description="Business unit ID")
    client_id: Optional[int] = Field(None, description="Client ID")
    tenant_id: Optional[int] = Field(None, description="Tenant ID")

    # Audit fields
    created_at: Optional[datetime] = Field(None, description="Creation timestamp")
    updated_at: Optional[datetime] = Field(None, description="Last update timestamp")

    @field_validator('deviceid')
    @classmethod
    def validate_deviceid_format(cls, v: str) -> str:
        """Validate device ID format."""
        v = v.strip()
        if len(v) < 1:
            raise ValueError("Device ID cannot be empty")
        import re
        if not re.match(r'^[a-zA-Z0-9_-]+$', v):
            raise ValueError("Device ID must contain only alphanumeric characters, hyphens, and underscores")
        return v


class PeopleEventLogSchema(BusinessLogicModel):
    """
    Enhanced PeopleEventLog schema for attendance events.

    Mirrors apps/attendance/models.py PeopleEventlog model.
    Maps to Kotlin data class: PeopleEventLog
    """
    # Identity
    id: Optional[int] = Field(None, description="Server-assigned ID")
    uuid: Optional[UUID] = Field(None, description="Unique identifier")

    # Event details
    peventtype_id: Optional[int] = Field(None, description="Event type ID")
    comments: Optional[str] = Field(None, max_length=500, description="Event comments")

    # Location tracking
    startlocation: Optional[str] = Field(None, description="Start location (GeoJSON Point)")
    endlocation: Optional[str] = Field(None, description="End location (GeoJSON Point)")
    journeypath: Optional[str] = Field(None, description="Journey path (GeoJSON LineString)")

    # Timing
    starttime: Optional[datetime] = Field(None, description="Event start time")
    endtime: Optional[datetime] = Field(None, description="Event end time")
    duration: Optional[int] = Field(None, ge=0, description="Duration in seconds")

    # Person
    peopleid: int = Field(..., description="Person ID")

    # Multi-tenant
    client_id: Optional[int] = Field(None, description="Client ID")
    bu_id: Optional[int] = Field(None, description="Business unit ID")

    # Audit
    created_at: Optional[datetime] = Field(None, description="Creation timestamp")

    def validate_business_rules(self, context=None):
        """Validate business rules for attendance events."""
        from pydantic import ValidationError

        errors = []

        if self.starttime and self.endtime:
            if self.endtime < self.starttime:
                errors.append({
                    'loc': ['endtime'],
                    'msg': 'End time must be after start time',
                    'type': 'business_rule_violation'
                })

        if errors:
            raise ValidationError(errors, self.__class__)


class AttendanceListResponseSchema(BaseModel):
    """
    Response schema for attendance list operations.

    Maps to Kotlin: data class AttendanceListResponse
    """
    records: List[AttendanceDetailSchema] = Field(default_factory=list, description="List of attendance records")
    total_count: int = Field(..., ge=0, description="Total number of records")
    page: Optional[int] = Field(None, ge=1, description="Current page number")
    page_size: Optional[int] = Field(None, ge=1, le=100, description="Items per page")
    has_next: bool = Field(default=False, description="Whether more pages exist")


class AttendanceSyncRequestSchema(TenantAwareModel):
    """
    Request schema for attendance sync operations.

    Maps to Kotlin: data class AttendanceSyncRequest
    """
    records: List[AttendanceDetailSchema] = Field(..., min_items=1, max_items=100, description="Attendance records to sync")
    device_id: str = Field(..., min_length=5, max_length=255, description="Device identifier")
    idempotency_key: str = Field(..., min_length=16, max_length=255, description="Idempotency key")
    full_sync: bool = Field(default=False, description="Whether this is a full sync")
    since_timestamp: Optional[datetime] = Field(None, description="Last sync timestamp (for delta sync)")


__all__ = [
    'AttendanceDetailSchema',
    'PeopleEventLogSchema',
    'AttendanceListResponseSchema',
    'AttendanceSyncRequestSchema',
]
