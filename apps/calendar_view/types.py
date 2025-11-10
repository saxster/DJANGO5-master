"""Typed objects shared across the calendar view service."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Mapping, Optional, Sequence

from .constants import (
    CalendarContextType,
    CalendarEntityType,
    CalendarEventStatus,
    CalendarEventType,
)


@dataclass(frozen=True)
class CalendarEvent:
    id: str
    event_type: CalendarEventType
    status: CalendarEventStatus
    title: str
    start: datetime
    end: Optional[datetime] = None
    subtitle: Optional[str] = None
    related_entity_type: CalendarEntityType = CalendarEntityType.JOBNEED
    related_entity_id: Optional[int] = None
    location: Optional[str] = None
    assigned_user_id: Optional[int] = None
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class CalendarContextFilter:
    people_id: Optional[int] = None
    site_id: Optional[int] = None
    asset_id: Optional[int] = None
    client_id: Optional[int] = None
    team_id: Optional[int] = None
    shift_id: Optional[int] = None


@dataclass(frozen=True)
class CalendarQueryParams:
    start: datetime
    end: datetime
    tenant_id: int
    user_id: int
    context_filter: CalendarContextFilter
    event_types: Sequence[CalendarEventType]
    statuses: Sequence[CalendarEventStatus]
    search: Optional[str] = None
    has_attachments: Optional[bool] = None
    min_attachment_count: Optional[int] = None


@dataclass(frozen=True)
class CalendarAggregationResult:
    events: Sequence[CalendarEvent]
    summary: Mapping[str, Mapping[str, int]]


__all__ = [
    "CalendarEvent",
    "CalendarContextFilter",
    "CalendarQueryParams",
    "CalendarAggregationResult",
]
