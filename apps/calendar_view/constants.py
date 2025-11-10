"""Shared enums and constants for calendar aggregation."""

from __future__ import annotations

from enum import Enum


class CalendarEventType(str, Enum):
    ATTENDANCE = "ATTENDANCE"
    TASK = "TASK"
    TOUR = "TOUR"
    INSPECTION = "INSPECTION"
    JOURNAL = "JOURNAL"
    TICKET = "TICKET"
    INCIDENT = "INCIDENT"
    MAINTENANCE = "MAINTENANCE"
    TRAINING = "TRAINING"


class CalendarEventStatus(str, Enum):
    SCHEDULED = "SCHEDULED"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    OVERDUE = "OVERDUE"
    CANCELLED = "CANCELLED"
    FAILED = "FAILED"


class CalendarEntityType(str, Enum):
    ATTENDANCE = "ATTENDANCE"
    JOBNEED = "JOBNEED"
    TICKET = "TICKET"
    JOURNAL_ENTRY = "JOURNAL_ENTRY"
    INCIDENT = "INCIDENT"
    ASSET = "ASSET"
    SHIFT = "SHIFT"
    PERSON = "PERSON"


class CalendarContextType(str, Enum):
    USER = "USER"
    SITE = "SITE"
    ASSET = "ASSET"
    TEAM = "TEAM"
    CLIENT = "CLIENT"
    SHIFT = "SHIFT"


DEFAULT_CALENDAR_CACHE_TTL = 60
MAX_CALENDAR_RANGE_DAYS = 31


__all__ = [
    "CalendarEventType",
    "CalendarEventStatus",
    "CalendarEntityType",
    "CalendarContextType",
    "DEFAULT_CALENDAR_CACHE_TTL",
    "MAX_CALENDAR_RANGE_DAYS",
]
