"""Base classes shared by calendar providers."""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Iterable, Sequence

from django.db.models import QuerySet

from ..constants import CalendarEventType
from ..exceptions import CalendarProviderError
from ..types import CalendarContextFilter, CalendarEvent, CalendarQueryParams

logger = logging.getLogger(__name__)


class BaseCalendarEventProvider(ABC):
    """Abstract provider definition."""

    event_types: Sequence[CalendarEventType] = ()
    name: str = "base"

    def supports(self, requested: Sequence[CalendarEventType]) -> bool:
        if not requested:
            return True
        return bool(set(requested).intersection(self.event_types))

    @abstractmethod
    def fetch(self, params: CalendarQueryParams) -> Sequence[CalendarEvent]:
        """Return events for the supplied query parameters."""

    def _apply_context_filters(
        self,
        queryset: QuerySet,
        context: CalendarContextFilter,
        mapping: dict[str, str],
    ) -> QuerySet:
        if context.people_id and (field := mapping.get("people_id")):
            queryset = queryset.filter(**{field: context.people_id})
        if context.site_id and (field := mapping.get("site_id")):
            queryset = queryset.filter(**{field: context.site_id})
        if context.asset_id and (field := mapping.get("asset_id")):
            queryset = queryset.filter(**{field: context.asset_id})
        if context.client_id and (field := mapping.get("client_id")):
            queryset = queryset.filter(**{field: context.client_id})
        if context.team_id and (field := mapping.get("team_id")):
            queryset = queryset.filter(**{field: context.team_id})
        if context.shift_id and (field := mapping.get("shift_id")):
            queryset = queryset.filter(**{field: context.shift_id})
        return queryset

    def _handle_provider_error(self, exc: Exception) -> None:
        logger.exception("Calendar provider '%s' failed", self.name, exc_info=exc)
        raise CalendarProviderError(self.name, str(exc)) from exc


def flatten_events(chunks: Iterable[Sequence[CalendarEvent]]) -> list[CalendarEvent]:
    events: list[CalendarEvent] = []
    for chunk in chunks:
        events.extend(chunk)
    return events


__all__ = ["BaseCalendarEventProvider", "flatten_events"]
