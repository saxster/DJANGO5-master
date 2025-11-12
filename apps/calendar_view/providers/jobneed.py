"""Calendar provider for Jobneed-derived operations."""

from __future__ import annotations

from typing import Dict, Optional

from django.db.models import Q

from apps.activity.models.job.jobneed import Jobneed

from ..constants import CalendarEntityType, CalendarEventStatus, CalendarEventType
from ..types import CalendarEvent, CalendarQueryParams
from .base import BaseCalendarEventProvider


IDENTIFIER_TO_EVENT_TYPE: Dict[str, CalendarEventType] = {
    Jobneed.Identifier.TASK.value: CalendarEventType.TASK,
    Jobneed.Identifier.INTERNALTOUR.value: CalendarEventType.TOUR,
    Jobneed.Identifier.EXTERNALTOUR.value: CalendarEventType.TOUR,
    Jobneed.Identifier.PPM.value: CalendarEventType.INSPECTION,
    Jobneed.Identifier.SITEREPORT.value: CalendarEventType.INCIDENT,
    Jobneed.Identifier.INCIDENTREPORT.value: CalendarEventType.INCIDENT,
    Jobneed.Identifier.ASSETMAINTENANCE.value: CalendarEventType.MAINTENANCE,
    Jobneed.Identifier.ASSETLOG.value: CalendarEventType.MAINTENANCE,
}

STATUS_MAP: Dict[str, CalendarEventStatus] = {
    Jobneed.JobStatus.ASSIGNED.value: CalendarEventStatus.SCHEDULED,
    Jobneed.JobStatus.STANDBY.value: CalendarEventStatus.SCHEDULED,
    Jobneed.JobStatus.INPROGRESS.value: CalendarEventStatus.IN_PROGRESS,
    Jobneed.JobStatus.WORKING.value: CalendarEventStatus.IN_PROGRESS,
    Jobneed.JobStatus.PARTIALLYCOMPLETED.value: CalendarEventStatus.IN_PROGRESS,
    Jobneed.JobStatus.MAINTENANCE.value: CalendarEventStatus.IN_PROGRESS,
    Jobneed.JobStatus.AUTOCLOSED.value: CalendarEventStatus.COMPLETED,
    Jobneed.JobStatus.COMPLETED.value: CalendarEventStatus.COMPLETED,
}


class JobneedEventProvider(BaseCalendarEventProvider):
    event_types = (
        CalendarEventType.TASK,
        CalendarEventType.TOUR,
        CalendarEventType.INSPECTION,
        CalendarEventType.INCIDENT,
        CalendarEventType.MAINTENANCE,
    )
    name = "jobneed"

    def fetch(self, params: CalendarQueryParams):
        try:
            queryset = (
                Jobneed.objects.filter(tenant_id=params.tenant_id)
                .filter(
                    Q(plandatetime__range=(params.start, params.end))
                    | Q(expirydatetime__range=(params.start, params.end))
                    | Q(
                        plandatetime__lte=params.start,
                        expirydatetime__gte=params.end,
                    )
                )
                .exclude(identifier__isnull=True)
                .select_related("asset", "asset__location", "bu", "people", "ticket")
            )

            queryset = self._apply_context_filters(
                queryset,
                params.context_filter,
                mapping={
                    "people_id": "people_id",
                    "site_id": "bu_id",
                    "client_id": "client_id",
                    "asset_id": "asset_id",
                    "team_id": "pgroup_id",
                },
            )

            events = []
            for jobneed in queryset.iterator():
                event_type = IDENTIFIER_TO_EVENT_TYPE.get(jobneed.identifier, CalendarEventType.TASK)
                if params.event_types and event_type not in params.event_types:
                    continue

                start = jobneed.plandatetime or jobneed.starttime
                if not start:
                    continue
                events.append(
                    CalendarEvent(
                        id=f"jobneed:{jobneed.pk}",
                        event_type=event_type,
                        status=STATUS_MAP.get(jobneed.jobstatus, CalendarEventStatus.SCHEDULED),
                        title=jobneed.jobdesc,
                        subtitle=_jobneed_subtitle(jobneed),
                        start=start,
                        end=jobneed.expirydatetime or jobneed.endtime,
                        related_entity_type=CalendarEntityType.JOBNEED,
                        related_entity_id=jobneed.pk,
                        location=_jobneed_location(jobneed),
                        assigned_user_id=jobneed.people_id,
                        metadata={
                            "job_id": jobneed.job_id,
                            "priority": jobneed.priority,
                            "ticket_id": jobneed.ticket_id,
                            "identifier": jobneed.identifier,
                            "attachment_count": jobneed.attachmentcount or 0,
                            "has_attachments": (jobneed.attachmentcount or 0) > 0,
                        },
                    )
                )

            return events
        except Exception as exc:  # pragma: no cover
            self._handle_provider_error(exc)
        return []


def _jobneed_subtitle(jobneed: Jobneed) -> Optional[str]:
    if jobneed.asset_id and jobneed.asset:
        return getattr(jobneed.asset, "assetname", None)
    if jobneed.bu_id and jobneed.bu:
        return getattr(jobneed.bu, "buname", None)
    return None


def _jobneed_location(jobneed: Jobneed) -> Optional[str]:
    if jobneed.asset_id and jobneed.asset:
        location = getattr(jobneed.asset, "location", None)
        if location:
            return getattr(location, "locname", str(location))
    if jobneed.bu_id and jobneed.bu:
        return getattr(jobneed.bu, "buname", None)
    return None


__all__ = ["JobneedEventProvider"]
