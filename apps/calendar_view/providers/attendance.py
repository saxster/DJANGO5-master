"""Attendance provider for the calendar aggregation service."""

from __future__ import annotations

from datetime import datetime, time

from django.db.models import Q, Count
from django.utils import timezone

from apps.attendance.models import PeopleEventlog

from ..constants import CalendarEntityType, CalendarEventStatus, CalendarEventType
from ..types import CalendarEvent, CalendarQueryParams
from .base import BaseCalendarEventProvider


class AttendanceEventProvider(BaseCalendarEventProvider):
    event_types = (CalendarEventType.ATTENDANCE,)
    name = "attendance"

    def fetch(self, params: CalendarQueryParams):
        try:
            queryset = (
                PeopleEventlog.objects.filter(tenant_id=params.tenant_id)
                .filter(
                    Q(punchintime__range=(params.start, params.end))
                    | Q(punchouttime__range=(params.start, params.end))
                    | Q(datefor__range=(params.start.date(), params.end.date()))
                )
                .select_related("people", "bu", "client", "shift", "post", "geofence",
                                "checkin_photo", "checkout_photo")
                .annotate(
                    photo_count=Count('photos', filter=Q(photos__is_deleted=False), distinct=True)
                )
            )

            queryset = self._apply_context_filters(
                queryset,
                params.context_filter,
                mapping={
                    "people_id": "people_id",
                    "site_id": "bu_id",
                    "client_id": "client_id",
                    "shift_id": "shift_id",
                },
            )

            events = []
            now = timezone.now()
            for record in queryset.iterator():
                start = record.punchintime or _safe_datetime(record.datefor)
                if not start:
                    continue
                events.append(
                    CalendarEvent(
                        id=f"attendance:{record.pk}",
                        event_type=CalendarEventType.ATTENDANCE,
                        status=_attendance_status(record, now),
                        title=_attendance_title(record),
                        subtitle=_attendance_subtitle(record),
                        start=start,
                        end=record.punchouttime,
                        related_entity_type=CalendarEntityType.ATTENDANCE,
                        related_entity_id=record.pk,
                        location=_attendance_location(record),
                        assigned_user_id=record.people_id,
                        metadata={
                            "shift_id": record.shift_id,
                            "post_id": record.post_id,
                            "post_assignment_id": record.post_assignment_id,
                            "transport_modes": record.transportmodes or [],
                            "photo_count": getattr(record, 'photo_count', 0),
                            "has_checkin_photo": bool(record.checkin_photo_id),
                            "has_checkout_photo": bool(record.checkout_photo_id),
                            "has_attachments": getattr(record, 'photo_count', 0) > 0 or bool(record.checkin_photo_id) or bool(record.checkout_photo_id),
                        },
                    )
                )

            return events
        except Exception as exc:  # pragma: no cover - delegated handler
            self._handle_provider_error(exc)
        return []


def _safe_datetime(value):
    if value is None:
        return None
    if isinstance(value, datetime):
        return timezone.make_aware(value) if timezone.is_naive(value) else value
    return timezone.make_aware(datetime.combine(value, time.min))


def _attendance_status(record: PeopleEventlog, now) -> CalendarEventStatus:
    if record.punchintime and record.punchouttime:
        return CalendarEventStatus.COMPLETED
    if record.punchintime and not record.punchouttime:
        return CalendarEventStatus.IN_PROGRESS if record.punchintime <= now else CalendarEventStatus.SCHEDULED
    return CalendarEventStatus.SCHEDULED


def _attendance_title(record: PeopleEventlog) -> str:
    person = getattr(record.people, "peoplename", None)
    site = getattr(record.bu, "buname", None)
    if person and site:
        return f"{person} shift"
    if person:
        return f"Shift for {person}"
    return "Shift"


def _attendance_subtitle(record: PeopleEventlog):
    if record.post_id and record.post:
        return getattr(record.post, "postname", None)
    return getattr(record.bu, "buname", None)


def _attendance_location(record: PeopleEventlog):
    if record.geofence_id and record.geofence:
        return str(record.geofence)
    if record.otherlocation:
        return record.otherlocation
    return getattr(record.bu, "buname", None)


__all__ = ["AttendanceEventProvider"]
