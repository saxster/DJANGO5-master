"""Ticket provider for calendar aggregation."""

from __future__ import annotations

from django.db.models import Count, Q

from apps.y_helpdesk.models import Ticket

from ..constants import CalendarEntityType, CalendarEventStatus, CalendarEventType
from ..types import CalendarEvent, CalendarQueryParams
from .base import BaseCalendarEventProvider


STATUS_MAP = {
    Ticket.Status.NEW.value: CalendarEventStatus.SCHEDULED,
    Ticket.Status.OPEN.value: CalendarEventStatus.IN_PROGRESS,
    Ticket.Status.ONHOLD.value: CalendarEventStatus.IN_PROGRESS,
    Ticket.Status.RESOLVED.value: CalendarEventStatus.COMPLETED,
    Ticket.Status.CLOSED.value: CalendarEventStatus.COMPLETED,
    Ticket.Status.CANCEL.value: CalendarEventStatus.CANCELLED,
}


class TicketEventProvider(BaseCalendarEventProvider):
    event_types = (CalendarEventType.TICKET,)
    name = "ticket"

    def fetch(self, params: CalendarQueryParams):
        try:
            queryset = (
                Ticket.objects.filter(tenant_id=params.tenant_id)
                .filter(cdtz__range=(params.start, params.end))
                .select_related("assignedtopeople", "assignedtogroup", "asset", "bu", "location")
                .annotate(
                    modern_attachment_count=Count('attachments', distinct=True),
                    photo_count=Count(
                        'attachments',
                        filter=Q(attachments__content_type__startswith='image/'),
                        distinct=True
                    ),
                    video_count=Count(
                        'attachments',
                        filter=Q(attachments__content_type__startswith='video/'),
                        distinct=True
                    )
                )
            )

            queryset = self._apply_context_filters(
                queryset,
                params.context_filter,
                mapping={
                    "people_id": "assignedtopeople_id",
                    "site_id": "bu_id",
                    "client_id": "client_id",
                    "asset_id": "asset_id",
                    "team_id": "assignedtogroup_id",
                },
            )

            events = []
            for ticket in queryset.iterator():
                title = ticket.ticketdesc[:140] if ticket.ticketdesc else "Ticket"
                events.append(
                    CalendarEvent(
                        id=f"ticket:{ticket.pk}",
                        event_type=CalendarEventType.TICKET,
                        status=STATUS_MAP.get(ticket.status, CalendarEventStatus.IN_PROGRESS),
                        title=title,
                        subtitle=_ticket_subtitle(ticket),
                        start=ticket.cdtz,
                        end=None,
                        related_entity_type=CalendarEntityType.TICKET,
                        related_entity_id=ticket.pk,
                        location=_ticket_location(ticket),
                        assigned_user_id=ticket.assignedtopeople_id,
                        metadata={
                            "priority": ticket.priority,
                            "ticket_number": ticket.ticketno,
                            "status": ticket.status,
                            "attachment_count": ticket.attachmentcount or 0,
                            "modern_attachment_count": getattr(ticket, 'modern_attachment_count', 0),
                            "photo_count": getattr(ticket, 'photo_count', 0),
                            "video_count": getattr(ticket, 'video_count', 0),
                            "has_attachments": ((ticket.attachmentcount or 0) > 0 or
                                                getattr(ticket, 'modern_attachment_count', 0) > 0),
                        },
                    )
                )

            return events
        except Exception as exc:  # pragma: no cover
            self._handle_provider_error(exc)
        return []


def _ticket_subtitle(ticket: Ticket):
    if ticket.asset_id and ticket.asset:
        return getattr(ticket.asset, "assetname", None)
    if ticket.bu_id and ticket.bu:
        return getattr(ticket.bu, "buname", None)
    return None


def _ticket_location(ticket: Ticket):
    if ticket.location_id and ticket.location:
        return str(ticket.location)
    return getattr(ticket.bu, "buname", None)


__all__ = ["TicketEventProvider"]
