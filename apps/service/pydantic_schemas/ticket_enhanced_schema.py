"""
Enhanced Pydantic Schemas for Ticket Domain

Complete type-safe models for Kotlin/Swift codegen.
Mirrors apps/y_helpdesk/serializers/ticket_sync_serializers.py patterns.

Compliance with .claude/rules.md:
- Rule #7: Models < 150 lines
- Rule #10: Comprehensive validation
- Rule #13: Required validation patterns

For Kotlin Apollo codegen compatibility.
"""

from pydantic import BaseModel, Field, field_validator
from typing import Optional, List, Literal
from datetime import datetime
from uuid import UUID

from apps.core.validation_pydantic.pydantic_base import BusinessLogicModel, TenantAwareModel


# ============================================================================
# ENUMS FOR TYPE SAFETY
# ============================================================================

class TicketStatus(str):
    """Ticket status values (for Kotlin enum generation)."""
    NEW = "NEW"
    OPEN = "OPEN"
    INPROGRESS = "INPROGRESS"
    ONHOLD = "ONHOLD"
    RESOLVED = "RESOLVED"
    CLOSED = "CLOSED"
    CANCELLED = "CANCELLED"


class TicketPriority(str):
    """Ticket priority levels (for Kotlin enum generation)."""
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class TicketIdentifier(str):
    """Ticket type identifier (for Kotlin enum generation)."""
    REQUEST = "REQUEST"
    TICKET = "TICKET"


# ============================================================================
# TICKET MODELS
# ============================================================================

class TicketDetailSchema(BusinessLogicModel):
    """
    Complete Ticket schema for mobile sync.

    Mirrors apps/y_helpdesk/models.py Ticket model.
    Maps to Kotlin data class: TicketDetail
    """
    # Identity fields
    id: Optional[int] = Field(None, description="Server-assigned ID")
    uuid: Optional[UUID] = Field(None, description="Unique identifier (UUID)")
    mobile_id: Optional[UUID] = Field(None, description="Client-generated unique identifier")
    ticketno: Optional[str] = Field(None, max_length=50, description="Auto-generated ticket number")

    # Sync metadata
    version: Optional[int] = Field(None, ge=1, description="Version for conflict detection")
    sync_status: Optional[Literal['synced', 'pending_sync', 'sync_error', 'pending_delete']] = Field(
        None,
        description="Sync status"
    )
    last_sync_timestamp: Optional[datetime] = Field(None, description="Last sync timestamp")

    # Core ticket fields
    ticketdesc: str = Field(..., min_length=10, max_length=1000, description="Ticket description")
    status: TicketStatus = Field(default=TicketStatus.NEW, description="Ticket status")
    priority: Optional[TicketPriority] = Field(None, description="Ticket priority (HIGH/MEDIUM/LOW)")
    identifier: TicketIdentifier = Field(default=TicketIdentifier.TICKET, description="Ticket type (REQUEST/TICKET)")
    comments: Optional[str] = Field(None, max_length=2000, description="Additional comments")

    # Assignment
    assignedtopeople_id: Optional[int] = Field(None, description="Assigned to person ID")
    assignedtogroup_id: Optional[int] = Field(None, description="Assigned to group ID")

    # Multi-tenant fields
    bu_id: Optional[int] = Field(None, description="Business unit ID")
    client_id: Optional[int] = Field(None, description="Client ID")
    tenant_id: Optional[int] = Field(None, description="Tenant ID")

    # Audit fields
    cuser_id: Optional[int] = Field(None, description="Created by user ID")
    muser_id: Optional[int] = Field(None, description="Modified by user ID")
    created_at: Optional[datetime] = Field(None, description="Creation timestamp")
    updated_at: Optional[datetime] = Field(None, description="Last update timestamp")

    @field_validator('ticketdesc')
    @classmethod
    def validate_ticketdesc_content(cls, v: str) -> str:
        """Validate ticket description content."""
        v = v.strip()
        if len(v) < 10:
            raise ValueError("Ticket description must be at least 10 characters")
        if len(v) > 1000:
            raise ValueError("Ticket description cannot exceed 1000 characters")
        return v

    @field_validator('status')
    @classmethod
    def validate_status_value(cls, v: Optional[str]) -> str:
        """Validate and normalize status."""
        if v:
            v = v.upper()
            valid_statuses = [s.value for s in [TicketStatus.NEW, TicketStatus.OPEN, TicketStatus.INPROGRESS,
                                                  TicketStatus.ONHOLD, TicketStatus.RESOLVED, TicketStatus.CLOSED,
                                                  TicketStatus.CANCELLED]]
            if v not in valid_statuses:
                raise ValueError(f"Status must be one of: {', '.join(valid_statuses)}")
        return v or TicketStatus.NEW


class TicketListResponseSchema(BaseModel):
    """
    Response schema for ticket list operations.

    Maps to Kotlin: data class TicketListResponse
    """
    tickets: List[TicketDetailSchema] = Field(default_factory=list, description="List of tickets")
    total_count: int = Field(..., ge=0, description="Total number of tickets")
    page: Optional[int] = Field(None, ge=1, description="Current page number")
    page_size: Optional[int] = Field(None, ge=1, le=100, description="Items per page")
    has_next: bool = Field(default=False, description="Whether more pages exist")


class TicketSyncRequestSchema(TenantAwareModel):
    """
    Request schema for ticket sync operations.

    Maps to Kotlin: data class TicketSyncRequest
    """
    tickets: List[TicketDetailSchema] = Field(..., min_items=1, max_items=100, description="Tickets to sync (max 100)")
    device_id: str = Field(..., min_length=5, max_length=255, description="Device identifier")
    idempotency_key: str = Field(..., min_length=16, max_length=255, description="Idempotency key")
    full_sync: bool = Field(default=False, description="Whether this is a full sync")
    since_timestamp: Optional[datetime] = Field(None, description="Last sync timestamp (for delta sync)")


__all__ = [
    'TicketStatus',
    'TicketPriority',
    'TicketIdentifier',
    'TicketDetailSchema',
    'TicketListResponseSchema',
    'TicketSyncRequestSchema',
]
