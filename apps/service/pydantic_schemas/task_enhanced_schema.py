"""
Enhanced Pydantic Schemas for Task/JobNeed Domain

Complete type-safe models for Kotlin/Swift codegen.
Mirrors apps/activity/serializers/task_sync_serializers.py patterns.

Compliance with .claude/rules.md:
- Rule #7: Models < 150 lines
- Rule #10: Comprehensive validation
- Rule #13: Required validation patterns

For Kotlin Apollo codegen compatibility.
"""

from pydantic import BaseModel, Field, field_validator
from typing import Optional, Literal, List
from datetime import datetime
from uuid import UUID
from decimal import Decimal

from apps.core.validation_pydantic.pydantic_base import BusinessLogicModel, TenantAwareModel


# ============================================================================
# ENUMS FOR TYPE SAFETY
# ============================================================================

class TaskPriority(str):
    """Task priority levels (for Kotlin enum generation)."""
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class TaskStatus(str):
    """Task status values (for Kotlin enum generation)."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    OVERDUE = "overdue"


class SyncStatus(str):
    """Sync status for mobile sync operations."""
    SYNCED = "synced"
    PENDING_SYNC = "pending_sync"
    SYNC_ERROR = "sync_error"
    PENDING_DELETE = "pending_delete"


# ============================================================================
# TASK MODELS
# ============================================================================

class TaskDetailSchema(BusinessLogicModel):
    """
    Complete Task (JobNeed) schema for mobile sync.

    Mirrors apps/activity/models/job_model.py Jobneed model.
    Maps to Kotlin data class: TaskDetail
    """
    # Identity fields
    id: Optional[int] = Field(None, description="Server-assigned ID")
    uuid: Optional[UUID] = Field(None, description="Unique identifier (UUID)")
    mobile_id: Optional[UUID] = Field(None, description="Client-generated unique identifier")

    # Sync metadata
    version: Optional[int] = Field(None, ge=1, description="Version for conflict detection")
    sync_status: Optional[SyncStatus] = Field(None, description="Sync status")
    last_sync_timestamp: Optional[datetime] = Field(None, description="Last sync timestamp")

    # Core task fields
    jobdesc: str = Field(..., min_length=3, max_length=200, description="Job description")
    plandatetime: datetime = Field(..., description="Planned start datetime (ISO 8601)")
    expirydatetime: Optional[datetime] = Field(None, description="Expiry datetime (ISO 8601)")
    gracetime: Optional[int] = Field(None, ge=0, description="Grace period in minutes")

    # Execution fields
    starttime: Optional[datetime] = Field(None, description="Actual start time")
    endtime: Optional[datetime] = Field(None, description="Actual end time")
    gpslocation: Optional[str] = Field(None, description="GPS location (GeoJSON Point)")
    remarks: Optional[str] = Field(None, max_length=500, description="Task remarks/notes")

    # Classification fields
    priority: Optional[TaskPriority] = Field(None, description="Task priority (HIGH/MEDIUM/LOW)")
    identifier: Optional[str] = Field(None, max_length=100, description="Custom identifier")
    jobstatus: Optional[TaskStatus] = Field(None, description="Task status")
    jobtype: Optional[str] = Field(None, max_length=50, description="Task type")
    scantype: Optional[str] = Field(None, max_length=50, description="Scan type (QR/NFC/etc.)")

    # Foreign key IDs (for Kotlin mobile_id references)
    job_id: Optional[int] = Field(None, description="Parent job template ID")
    location_id: Optional[int] = Field(None, description="Location ID")
    asset_id: Optional[int] = Field(None, description="Asset ID")
    qset_id: Optional[int] = Field(None, description="Question set ID")

    # Multi-tenant fields
    bu_id: Optional[int] = Field(None, description="Business unit ID")
    client_id: Optional[int] = Field(None, description="Client ID")
    tenant_id: Optional[int] = Field(None, description="Tenant ID")

    # Audit fields
    cuser_id: Optional[int] = Field(None, description="Created by user ID")
    muser_id: Optional[int] = Field(None, description="Modified by user ID")
    created_at: Optional[datetime] = Field(None, description="Creation timestamp")
    updated_at: Optional[datetime] = Field(None, description="Last update timestamp")

    @field_validator('plandatetime', 'expirydatetime', 'starttime', 'endtime')
    @classmethod
    def validate_timestamps(cls, v: Optional[datetime]) -> Optional[datetime]:
        """Ensure timestamps are timezone-aware."""
        if v and v.tzinfo is None:
            from django.utils import timezone
            v = timezone.make_aware(v)
        return v

    @field_validator('jobdesc')
    @classmethod
    def validate_jobdesc_content(cls, v: str) -> str:
        """Validate job description content."""
        v = v.strip()
        if len(v) < 3:
            raise ValueError("Job description must be at least 3 characters")
        if len(v) > 200:
            raise ValueError("Job description cannot exceed 200 characters")
        return v

    def validate_business_rules(self, context=None):
        """
        Validate business rules for tasks.

        Rules:
        - expirydatetime must be after plandatetime
        - endtime must be after starttime
        - priority must be valid enum value
        """
        from pydantic import ValidationError

        errors = []

        # Validate datetime ordering
        if self.plandatetime and self.expirydatetime:
            if self.expirydatetime < self.plandatetime:
                errors.append({
                    'loc': ['expirydatetime'],
                    'msg': 'Expiry datetime must be after plan datetime',
                    'type': 'business_rule_violation'
                })

        if self.starttime and self.endtime:
            if self.endtime < self.starttime:
                errors.append({
                    'loc': ['endtime'],
                    'msg': 'End time must be after start time',
                    'type': 'business_rule_violation'
                })

        # Validate priority if provided
        if self.priority and self.priority not in [TaskPriority.HIGH, TaskPriority.MEDIUM, TaskPriority.LOW]:
            errors.append({
                'loc': ['priority'],
                'msg': 'Priority must be HIGH, MEDIUM, or LOW',
                'type': 'value_error'
            })

        if errors:
            raise ValidationError(errors, self.__class__)


class TaskListResponseSchema(BaseModel):
    """
    Response schema for task list operations.

    Maps to Kotlin: data class TaskListResponse
    """
    tasks: List[TaskDetailSchema] = Field(default_factory=list, description="List of tasks")
    total_count: int = Field(..., ge=0, description="Total number of tasks")
    page: Optional[int] = Field(None, ge=1, description="Current page number")
    page_size: Optional[int] = Field(None, ge=1, le=100, description="Items per page")
    has_next: bool = Field(default=False, description="Whether more pages exist")


class TaskSyncRequestSchema(TenantAwareModel):
    """
    Request schema for task sync operations.

    Maps to Kotlin: data class TaskSyncRequest
    """
    tasks: List[TaskDetailSchema] = Field(..., min_items=1, max_items=100, description="Tasks to sync (max 100)")
    device_id: str = Field(..., min_length=5, max_length=255, description="Device identifier")
    idempotency_key: str = Field(..., min_length=16, max_length=255, description="Idempotency key")
    full_sync: bool = Field(default=False, description="Whether this is a full sync")
    since_timestamp: Optional[datetime] = Field(None, description="Last sync timestamp (for delta sync)")


__all__ = [
    'TaskPriority',
    'TaskStatus',
    'SyncStatus',
    'TaskDetailSchema',
    'TaskListResponseSchema',
    'TaskSyncRequestSchema',
]
