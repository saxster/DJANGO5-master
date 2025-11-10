"""Tests for calendar aggregation service."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone

from django.test import SimpleTestCase

from apps.calendar_view.constants import CalendarEventStatus, CalendarEventType
from apps.calendar_view.services import CalendarAggregationService
from apps.calendar_view.types import (
    CalendarContextFilter,
    CalendarEvent,
    CalendarQueryParams,
)
from apps.calendar_view.providers.base import BaseCalendarEventProvider


class _StubProvider(BaseCalendarEventProvider):
    event_types = (CalendarEventType.TASK,)
    name = "stub"

    def __init__(self, events):
        self._events = events

    def fetch(self, params):  # noqa: D401 - simple stub
        return self._events


class CalendarAggregationServiceTests(SimpleTestCase):
    def setUp(self):
        self.start = datetime(2025, 11, 9, tzinfo=timezone.utc)
        self.end = self.start + timedelta(days=1)
        self.params = CalendarQueryParams(
            start=self.start,
            end=self.end,
            tenant_id=1,
            user_id=1,
            context_filter=CalendarContextFilter(people_id=1),
            event_types=[],
            statuses=[],
        )

    def test_aggregates_and_sorts_events(self):
        events = [
            CalendarEvent(
                id="b",
                event_type=CalendarEventType.TASK,
                status=CalendarEventStatus.IN_PROGRESS,
                title="Later",
                start=self.start + timedelta(hours=2),
            ),
            CalendarEvent(
                id="a",
                event_type=CalendarEventType.TASK,
                status=CalendarEventStatus.SCHEDULED,
                title="Earlier",
                start=self.start + timedelta(hours=1),
            ),
        ]
        service = CalendarAggregationService(providers=[_StubProvider(events)], cache_alias="select2")
        result = service.get_events(self.params)
        self.assertEqual([event.id for event in result.events], ["a", "b"])
        self.assertEqual(result.summary["by_type"]["TASK"], 2)

    def test_status_filter_is_applied(self):
        events = [
            CalendarEvent(
                id="1",
                event_type=CalendarEventType.TASK,
                status=CalendarEventStatus.COMPLETED,
                title="Complete",
                start=self.start,
            ),
            CalendarEvent(
                id="2",
                event_type=CalendarEventType.TASK,
                status=CalendarEventStatus.IN_PROGRESS,
                title="WIP",
                start=self.start + timedelta(hours=1),
            ),
        ]
        params = replace(self.params, statuses=[CalendarEventStatus.IN_PROGRESS])
        service = CalendarAggregationService(providers=[_StubProvider(events)], cache_alias="select2")
        result = service.get_events(params)
        self.assertEqual(len(result.events), 1)
        self.assertEqual(result.events[0].id, "2")
