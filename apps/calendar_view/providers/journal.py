"""Journal provider for calendar aggregation."""

from __future__ import annotations

from django.db.models import Count, Q

from apps.journal.models.entry import JournalEntry

from ..constants import CalendarEntityType, CalendarEventStatus, CalendarEventType
from ..types import CalendarEvent, CalendarQueryParams
from .base import BaseCalendarEventProvider


class JournalEventProvider(BaseCalendarEventProvider):
    event_types = (CalendarEventType.JOURNAL,)
    name = "journal"

    def fetch(self, params: CalendarQueryParams):
        try:
            queryset = (
                JournalEntry.objects.filter(tenant_id=params.tenant_id)
                .filter(timestamp__range=(params.start, params.end))
                .select_related("user")
                .annotate(
                    media_count=Count('media_attachments', distinct=True),
                    photo_count=Count(
                        'media_attachments',
                        filter=Q(media_attachments__media_type='PHOTO',
                                 media_attachments__is_deleted=False),
                        distinct=True
                    ),
                    video_count=Count(
                        'media_attachments',
                        filter=Q(media_attachments__media_type='VIDEO',
                                 media_attachments__is_deleted=False),
                        distinct=True
                    )
                )
            )

            queryset = self._apply_context_filters(
                queryset,
                params.context_filter,
                mapping={
                    "people_id": "user_id",
                    "client_id": "tenant_id",
                },
            )

            events = []
            for entry in queryset.iterator():
                # Privacy-aware photo counts
                photo_count = _get_photo_count_respecting_privacy(entry, params.user_id)
                video_count = _get_video_count_respecting_privacy(entry, params.user_id)
                media_count = _get_media_count_respecting_privacy(entry, params.user_id)

                events.append(
                    CalendarEvent(
                        id=f"journal:{entry.pk}",
                        event_type=CalendarEventType.JOURNAL,
                        status=CalendarEventStatus.COMPLETED,
                        title=entry.title or "Journal Entry",
                        subtitle=entry.subtitle or entry.entry_type,
                        start=entry.timestamp,
                        end=None,
                        related_entity_type=CalendarEntityType.JOURNAL_ENTRY,
                        related_entity_id=entry.pk,
                        location=entry.location_site_name or entry.location_address,
                        assigned_user_id=entry.user_id,
                        metadata={
                            "privacy_scope": entry.privacy_scope,
                            "mood": entry.mood_rating,
                            "stress": entry.stress_level,
                            "photo_count": photo_count,
                            "video_count": video_count,
                            "media_count": media_count,
                            "has_attachments": media_count > 0,
                        },
                    )
                )

            return events
        except Exception as exc:  # pragma: no cover
            self._handle_provider_error(exc)
        return []


def _get_photo_count_respecting_privacy(entry: JournalEntry, requesting_user_id: int) -> int:
    """
    Return photo count only if user has permission to view journal entry media.

    Privacy rules:
    - PRIVATE: Only owner sees count
    - AGGREGATE_ONLY: No individual counts exposed
    - Other scopes: Count visible to all
    """
    # Owner always sees their own counts
    if entry.user_id == requesting_user_id:
        return getattr(entry, 'photo_count', 0)

    # PRIVATE or AGGREGATE_ONLY: hide counts from non-owners
    if entry.privacy_scope in ('PRIVATE', 'AGGREGATE_ONLY'):
        return 0

    # Other privacy scopes (SHARED, MANAGER, TEAM): show counts
    return getattr(entry, 'photo_count', 0)


def _get_video_count_respecting_privacy(entry: JournalEntry, requesting_user_id: int) -> int:
    """Return video count respecting privacy scope."""
    if entry.user_id == requesting_user_id:
        return getattr(entry, 'video_count', 0)

    if entry.privacy_scope in ('PRIVATE', 'AGGREGATE_ONLY'):
        return 0

    return getattr(entry, 'video_count', 0)


def _get_media_count_respecting_privacy(entry: JournalEntry, requesting_user_id: int) -> int:
    """Return total media count respecting privacy scope."""
    if entry.user_id == requesting_user_id:
        return getattr(entry, 'media_count', 0)

    if entry.privacy_scope in ('PRIVATE', 'AGGREGATE_ONLY'):
        return 0

    return getattr(entry, 'media_count', 0)


__all__ = ["JournalEventProvider"]
