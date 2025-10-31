"""
Alert Inbox API Serializers
============================
Pydantic models for unified alert inbox responses.

Follows .claude/rules.md:
- Rule #6: Serializer < 100 lines
- Type-safe API contracts
"""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class AlertAction(BaseModel):
    """Action available for an alert"""
    type: str = Field(..., description="Action type (acknowledge, escalate, etc.)")
    label: str = Field(..., description="Display label for action")
    url: Optional[str] = Field(None, description="Optional direct URL for action")


class UnifiedAlert(BaseModel):
    """
    Unified alert from any source (NOC, tasks, SOS, SLA, work orders).
    """
    id: str = Field(..., description="Alert ID with source prefix (e.g., 'noc-123')")
    type: str = Field(..., description="Alert type (NOC_ALERT, TASK_OVERDUE, etc.)")
    severity: str = Field(..., description="Severity level", pattern="^(CRITICAL|HIGH|MEDIUM|LOW)$")
    message: str = Field(..., description="Alert message")
    site_name: Optional[str] = Field(None, description="Site/BU name")
    site_id: Optional[int] = Field(None, description="Site/BU ID")
    created_at: str = Field(..., description="ISO timestamp")
    timestamp_unix: float = Field(..., description="Unix timestamp for sorting")
    is_read: bool = Field(default=False, description="Read status")
    actions: List[AlertAction] = Field(default_factory=list, description="Available actions")
    entity_type: str = Field(..., description="Source entity type")
    entity_id: int = Field(..., description="Source entity ID")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")

    class Config:
        json_schema_extra = {
            "example": {
                "id": "noc-123",
                "type": "NOC_ALERT",
                "severity": "CRITICAL",
                "message": "SOS Alert - Guard A at Site E",
                "site_name": "Site E",
                "site_id": 15,
                "created_at": "2025-10-11T14:30:00+05:30",
                "timestamp_unix": 1728645600.0,
                "is_read": False,
                "actions": [
                    {"type": "acknowledge", "label": "Acknowledge"},
                    {"type": "escalate", "label": "Escalate"}
                ],
                "entity_type": "noc_alert",
                "entity_id": 123
            }
        }


class AlertInboxResponse(BaseModel):
    """Response for alert inbox endpoint"""
    alerts: List[UnifiedAlert]
    unread_count: int = Field(..., description="Number of unread alerts")
    total_count: int = Field(..., description="Total alerts (before filtering)")
    scope: Dict[str, Any] = Field(..., description="Applied scope filters")


class MarkAlertReadRequest(BaseModel):
    """Request to mark alert as read"""
    alert_id: str = Field(..., description="Alert ID to mark as read")


class MarkAlertReadResponse(BaseModel):
    """Response after marking alert as read"""
    success: bool
    message: str
    unread_count: int = Field(..., description="Updated unread count")


__all__ = [
    "AlertAction",
    "UnifiedAlert",
    "AlertInboxResponse",
    "MarkAlertReadRequest",
    "MarkAlertReadResponse",
]
