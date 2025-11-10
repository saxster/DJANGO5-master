"""Calendar aggregation orchestration service."""

from __future__ import annotations

import hashlib
import json
from typing import Mapping, Sequence

from django.core.cache import caches

from .constants import DEFAULT_CALENDAR_CACHE_TTL
from .providers.attendance import AttendanceEventProvider
from .providers.base import BaseCalendarEventProvider, flatten_events
from .providers.jobneed import JobneedEventProvider
from .providers.journal import JournalEventProvider
from .providers.ticket import TicketEventProvider
from .types import CalendarAggregationResult, CalendarEvent, CalendarQueryParams


class CalendarAggregationService:
    """Fetch and aggregate events from all registered providers."""

    def __init__(
        self,
        providers: Sequence[BaseCalendarEventProvider] | None = None,
        cache_alias: str = "default",
        cache_ttl: int = DEFAULT_CALENDAR_CACHE_TTL,
    ) -> None:
        self.providers = list(providers or self._default_providers())
        self.cache = caches[cache_alias]
        self.cache_ttl = cache_ttl

    def get_events(self, params: CalendarQueryParams) -> CalendarAggregationResult:
        cache_key = self._build_cache_key(params)
        cached = self.cache.get(cache_key)
        if isinstance(cached, CalendarAggregationResult):
            return cached

        chunks = []
        for provider in self.providers:
            if provider.supports(params.event_types):
                chunks.append(provider.fetch(params))

        events = self._post_process(flatten_events(chunks), params)
        summary = self._build_summary(events)
        result = CalendarAggregationResult(events=events, summary=summary)
        self.cache.set(cache_key, result, self.cache_ttl)
        return result

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _post_process(self, events: list[CalendarEvent], params: CalendarQueryParams) -> list[CalendarEvent]:
        filtered = events

        # Status filtering
        if params.statuses:
            allowed = set(params.statuses)
            filtered = [event for event in filtered if event.status in allowed]

        # Search filtering
        if params.search:
            needle = params.search.casefold()
            filtered = [event for event in filtered if _matches_search(event, needle)]

        # Attachment presence filtering
        if params.has_attachments is not None:
            filtered = [
                event for event in filtered
                if event.metadata.get("has_attachments", False) == params.has_attachments
            ]

        # Minimum attachment count filtering
        if params.min_attachment_count is not None:
            filtered = [
                event for event in filtered
                if _get_total_attachment_count(event) >= params.min_attachment_count
            ]

        filtered.sort(key=lambda event: event.start)
        return filtered

    def _build_summary(self, events: Sequence[CalendarEvent]) -> Mapping[str, Mapping[str, int]]:
        by_type: dict[str, int] = {}
        by_status: dict[str, int] = {}
        for event in events:
            by_type[event.event_type.value] = by_type.get(event.event_type.value, 0) + 1
            by_status[event.status.value] = by_status.get(event.status.value, 0) + 1
        return {"by_type": by_type, "by_status": by_status}

    def _build_cache_key(self, params: CalendarQueryParams) -> str:
        """
        Build cache key from query parameters.

        SECURITY NOTE: Cache key includes tenant_id + user_id but NOT user role/permissions.
        This is SAFE because:
        1. Each user_id is unique within a tenant
        2. Role-based filtering happens at provider level (JobneedEventProvider, etc.)
        3. Providers use permission checks on QuerySets before returning events

        If role-based filtering were NOT applied at provider level, this would create
        a cache poisoning vulnerability where users with different roles but same user_id
        could share cached results. Current implementation is secure.

        Future Enhancement: If CalendarQueryParams gains a user_role field, add it here:
        "user_role": getattr(params, 'user_role', None)
        """
        payload = {
            "tenant": params.tenant_id,
            "user": params.user_id,
            "start": params.start.isoformat(),
            "end": params.end.isoformat(),
            "event_types": [et.value for et in params.event_types],
            "statuses": [st.value for st in params.statuses],
            "search": params.search,
            "has_attachments": params.has_attachments,
            "min_attachment_count": params.min_attachment_count,
            "context": {
                "people_id": params.context_filter.people_id,
                "site_id": params.context_filter.site_id,
                "asset_id": params.context_filter.asset_id,
                "client_id": params.context_filter.client_id,
                "team_id": params.context_filter.team_id,
                "shift_id": params.context_filter.shift_id,
            },
        }
        digest = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
        return f"calendar-events:{digest}"

    @staticmethod
    def _default_providers() -> Sequence[BaseCalendarEventProvider]:
        return (
            AttendanceEventProvider(),
            JobneedEventProvider(),
            TicketEventProvider(),
            JournalEventProvider(),
        )


def _matches_search(event: CalendarEvent, needle: str) -> bool:
    haystacks = [value for value in (event.title, event.subtitle, event.location) if value]
    for metadata_value in event.metadata.values():
        if isinstance(metadata_value, str):
            haystacks.append(metadata_value)
    return any(needle in hay.casefold() for hay in haystacks)


def _get_total_attachment_count(event: CalendarEvent) -> int:
    """
    Get total attachment count from event metadata.

    Handles multiple attachment count fields across different providers:
    - photo_count, video_count, media_count (journal)
    - attachment_count (jobneed, ticket)
    - photo_count + has_checkin_photo + has_checkout_photo (attendance)
    """
    metadata = event.metadata

    # Try direct attachment_count field first (jobneed, ticket)
    if "attachment_count" in metadata:
        return metadata["attachment_count"]

    # Try media_count for journal entries
    if "media_count" in metadata:
        return metadata["media_count"]

    # Try photo_count (attendance, journal privacy-filtered)
    if "photo_count" in metadata:
        return metadata["photo_count"]

    # Fallback to summing all known count fields
    total = 0
    for key in ["photo_count", "video_count", "attachment_count", "media_count"]:
        total += metadata.get(key, 0)

    return total


__all__ = ["CalendarAggregationService"]
