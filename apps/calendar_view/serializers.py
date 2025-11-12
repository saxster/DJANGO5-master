"""Serializers for the calendar API."""

from __future__ import annotations

from datetime import timedelta

from rest_framework import serializers

from .constants import (
    CalendarContextType,
    CalendarEntityType,
    CalendarEventStatus,
    CalendarEventType,
    MAX_CALENDAR_RANGE_DAYS,
)
from .types import CalendarEvent


class CalendarEventSerializer(serializers.Serializer):
    id = serializers.CharField()
    event_type = serializers.ChoiceField(choices=[(item.value, item.name) for item in CalendarEventType])
    status = serializers.ChoiceField(choices=[(item.value, item.name) for item in CalendarEventStatus])
    title = serializers.CharField()
    subtitle = serializers.CharField(allow_null=True, required=False)
    start = serializers.DateTimeField()
    end = serializers.DateTimeField(allow_null=True, required=False)
    related_entity_type = serializers.ChoiceField(
        choices=[(item.value, item.name) for item in CalendarEntityType]
    )
    related_entity_id = serializers.IntegerField(allow_null=True, required=False)
    location = serializers.CharField(allow_null=True, required=False)
    assigned_user_id = serializers.IntegerField(allow_null=True, required=False)
    metadata = serializers.DictField(child=serializers.JSONField(), required=False)

    def to_representation(self, instance: CalendarEvent):  # type: ignore[override]
        return {
            "id": instance.id,
            "event_type": instance.event_type.value,
            "status": instance.status.value,
            "title": instance.title,
            "subtitle": instance.subtitle,
            "start": instance.start,
            "end": instance.end,
            "related_entity_type": instance.related_entity_type.value,
            "related_entity_id": instance.related_entity_id,
            "location": instance.location,
            "assigned_user_id": instance.assigned_user_id,
            "metadata": instance.metadata,
        }


class CalendarSummarySerializer(serializers.Serializer):
    by_type = serializers.DictField(child=serializers.IntegerField())
    by_status = serializers.DictField(child=serializers.IntegerField())


class CalendarQuerySerializer(serializers.Serializer):
    start = serializers.DateTimeField()
    end = serializers.DateTimeField()
    event_types = serializers.ListField(
        child=serializers.ChoiceField(choices=[(item.value, item.name) for item in CalendarEventType]),
        required=False,
    )
    statuses = serializers.ListField(
        child=serializers.ChoiceField(choices=[(item.value, item.name) for item in CalendarEventStatus]),
        required=False,
    )
    context_type = serializers.ChoiceField(
        choices=[(item.value, item.name) for item in CalendarContextType], allow_null=True, required=False
    )
    context_id = serializers.IntegerField(required=False)
    search = serializers.CharField(required=False, allow_blank=True)

    # Attachment filters
    has_attachments = serializers.BooleanField(required=False, help_text="Filter to events with/without attachments")
    min_attachment_count = serializers.IntegerField(
        required=False,
        min_value=1,
        help_text="Minimum number of attachments required"
    )

    def validate(self, attrs):
        start = attrs["start"]
        end = attrs["end"]
        if end <= start:
            raise serializers.ValidationError("end must be greater than start")

        max_window = timedelta(days=MAX_CALENDAR_RANGE_DAYS)
        if end - start > max_window:
            raise serializers.ValidationError(
                f"Requested window exceeds {MAX_CALENDAR_RANGE_DAYS} days"
            )
        return attrs


__all__ = [
    "CalendarEventSerializer",
    "CalendarSummarySerializer",
    "CalendarQuerySerializer",
]
