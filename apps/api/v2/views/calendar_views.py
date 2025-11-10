"""V2 Calendar aggregation views."""

from __future__ import annotations

import logging
import uuid

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import UserRateThrottle
from rest_framework.views import APIView

from apps.api.pagination import StandardPageNumberPagination
from apps.api.permissions import TenantIsolationPermission
from apps.core.exceptions.patterns import DATABASE_EXCEPTIONS
from apps.calendar_view.constants import (
    CalendarContextType,
    CalendarEventStatus,
    CalendarEventType,
)
from apps.calendar_view.filters import build_context_filter
from apps.calendar_view.serializers import (
    CalendarEventSerializer,
    CalendarQuerySerializer,
)
from apps.calendar_view.services import CalendarAggregationService
from apps.calendar_view.types import CalendarQueryParams

logger = logging.getLogger(__name__)


class CalendarAttachmentThrottle(UserRateThrottle):
    """
    Rate limiting for calendar attachment requests.

    Prevents abuse of photo/video download endpoint.
    Limit: 100 requests per hour per authenticated user.
    """
    rate = '100/hour'


class CalendarEventListView(APIView):
    """Aggregate calendar events across modules."""

    permission_classes = [IsAuthenticated, TenantIsolationPermission]
    pagination_class = StandardPageNumberPagination
    service_class = CalendarAggregationService

    def get(self, request):
        correlation_id = str(uuid.uuid4())
        serializer = CalendarQuerySerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        event_types = [CalendarEventType(value) for value in data.get("event_types", [])]
        statuses = [CalendarEventStatus(value) for value in data.get("statuses", [])]
        context_type = data.get("context_type")
        context_enum = CalendarContextType(context_type) if context_type else None
        context_id = data.get("context_id")
        user = request.user

        context_filter = build_context_filter(
            context_type=context_enum,
            context_id=context_id,
            user_id=user.id,
            default_client_id=getattr(user, "client_id", None),
            default_site_id=getattr(user, "bu_id", None),
        )

        params = CalendarQueryParams(
            start=data["start"],
            end=data["end"],
            tenant_id=user.tenant_id,
            user_id=user.id,
            context_filter=context_filter,
            event_types=event_types,
            statuses=statuses,
            search=data.get("search"),
            has_attachments=data.get("has_attachments"),
            min_attachment_count=data.get("min_attachment_count"),
        )

        service = self.service_class()
        result = service.get_events(params)

        paginator = self.pagination_class()
        page = paginator.paginate_queryset(result.events, request, view=self)
        serialized = CalendarEventSerializer(page, many=True).data
        pagination_payload = paginator.get_paginated_response(serialized).data
        pagination_payload["summary"] = result.summary

        response_payload = {
            "success": True,
            "data": pagination_payload,
            "meta": {
                "correlation_id": correlation_id,
            },
        }
        logger.info("Calendar events fetched", extra={"correlation_id": correlation_id, "user_id": user.id})
        return Response(response_payload, status=status.HTTP_200_OK)


class CalendarEventAttachmentsView(APIView):
    """
    Retrieve photos, videos, and documents for a specific calendar event.

    GET /api/v2/calendar/events/{event_id}/attachments/

    Returns all attachments for the event, respecting privacy and tenant isolation.

    Rate Limiting: 100 requests/hour per user (prevents abuse)
    """

    permission_classes = [IsAuthenticated, TenantIsolationPermission]
    throttle_classes = [CalendarAttachmentThrottle]

    def get(self, request, event_id):
        """
        Get all attachments for a calendar event.

        Args:
            event_id: Composite event ID in format "provider:entity_pk"
                     e.g., "jobneed:123", "ticket:456", "journal:789"

        Returns:
            Response with attachment list including URLs, thumbnails, and metadata
        """
        correlation_id = str(uuid.uuid4())

        try:
            # Parse composite event ID
            provider_name, entity_id = event_id.split(":")
            entity_id = int(entity_id)
        except (ValueError, AttributeError):
            return Response(
                {
                    "success": False,
                    "error": {
                        "message": "Invalid event_id format",
                        "details": "Expected format: 'provider:id' (e.g., 'jobneed:123')",
                    },
                    "meta": {"correlation_id": correlation_id},
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Fetch attachments based on provider type
        try:
            attachments_data = self._get_attachments_for_provider(
                provider_name=provider_name,
                entity_id=entity_id,
                user=request.user,
                correlation_id=correlation_id,
            )

            logger.info(
                f"Calendar event attachments fetched: {event_id}",
                extra={
                    "correlation_id": correlation_id,
                    "user_id": request.user.id,
                    "event_id": event_id,
                    "attachment_count": len(attachments_data),
                },
            )

            return Response(
                {
                    "success": True,
                    "data": {
                        "event_id": event_id,
                        "count": len(attachments_data),
                        "attachments": attachments_data,
                    },
                    "meta": {"correlation_id": correlation_id},
                },
                status=status.HTTP_200_OK,
            )

        except PermissionError as e:
            logger.warning(
                f"Permission denied for calendar event attachments: {e}",
                extra={"correlation_id": correlation_id, "user_id": request.user.id, "event_id": event_id},
            )
            return Response(
                {
                    "success": False,
                    "error": {"message": str(e)},
                    "meta": {"correlation_id": correlation_id},
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        except ValueError as e:
            logger.error(
                f"Invalid provider or entity: {e}",
                extra={"correlation_id": correlation_id, "event_id": event_id},
            )
            return Response(
                {
                    "success": False,
                    "error": {"message": "Event not found", "details": str(e)},
                    "meta": {"correlation_id": correlation_id},
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        except DATABASE_EXCEPTIONS as e:
            logger.exception(
                f"Database error fetching calendar event attachments: {e}",
                extra={"correlation_id": correlation_id, "event_id": event_id},
            )
            return Response(
                {
                    "success": False,
                    "error": {"message": "Database error occurred"},
                    "meta": {"correlation_id": correlation_id},
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        except Exception as e:
            # Last resort handler for unexpected errors
            # Only reached if error is not PermissionError, ValueError, or DATABASE_EXCEPTIONS
            logger.critical(
                f"UNEXPECTED error in calendar attachment endpoint - type: {type(e).__name__}: {e}",
                extra={"correlation_id": correlation_id, "event_id": event_id},
                exc_info=True,
            )
            return Response(
                {
                    "success": False,
                    "error": {"message": "Internal server error"},
                    "meta": {"correlation_id": correlation_id},
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def _get_attachments_for_provider(self, provider_name, entity_id, user, correlation_id):
        """
        Fetch attachments for a specific provider and entity.

        Args:
            provider_name: Provider type (jobneed, attendance, ticket, journal)
            entity_id: Primary key of the entity
            user: Requesting user for permission checks
            correlation_id: Request correlation ID for logging

        Returns:
            List of serialized attachment dictionaries

        Raises:
            PermissionError: If user doesn't have access to entity or attachments
            ValueError: If entity not found or unknown provider
        """
        tenant_id = user.tenant_id

        if provider_name == "jobneed":
            return self._get_jobneed_attachments(entity_id, tenant_id, user)

        elif provider_name == "attendance":
            return self._get_attendance_attachments(entity_id, tenant_id, user)

        elif provider_name == "ticket":
            return self._get_ticket_attachments(entity_id, tenant_id, user)

        elif provider_name == "journal":
            return self._get_journal_attachments(entity_id, tenant_id, user)

        else:
            raise ValueError(f"Unknown provider: {provider_name}")

    def _get_jobneed_attachments(self, entity_id, tenant_id, user):
        """Get attachments for a Jobneed entity."""
        from apps.activity.models.job.jobneed import Jobneed
        from apps.activity.models import Attachment

        try:
            jobneed = Jobneed.objects.select_related('bu', 'people').get(
                id=entity_id,
                tenant_id=tenant_id
            )
        except Jobneed.DoesNotExist:
            raise PermissionError("Jobneed not found or access denied")

        # Get attachments via polymorphic owner field
        from apps.core_onboarding.models import TypeAssist

        try:
            jobneed_type = TypeAssist.objects.get(tacode="JOBNEED")
            attachments = Attachment.objects.filter(
                owner=str(jobneed.uuid),
                ownername=jobneed_type,
                tenant_id=tenant_id
            ).order_by('-datetime')

            return [self._serialize_attachment(att) for att in attachments]

        except TypeAssist.DoesNotExist:
            logger.warning("TypeAssist for JOBNEED not found")
            return []

    def _get_attendance_attachments(self, entity_id, tenant_id, user):
        """Get attendance photos for a PeopleEventlog record."""
        from apps.attendance.models import PeopleEventlog, AttendancePhoto

        try:
            record = PeopleEventlog.objects.select_related(
                'people', 'checkin_photo', 'checkout_photo'
            ).get(
                id=entity_id,
                tenant_id=tenant_id
            )
        except PeopleEventlog.DoesNotExist:
            raise PermissionError("Attendance record not found or access denied")

        attachments = []

        # Check-in photo
        if record.checkin_photo:
            attachments.append(self._serialize_attendance_photo(record.checkin_photo, "Check-in Photo"))

        # Check-out photo
        if record.checkout_photo:
            attachments.append(self._serialize_attendance_photo(record.checkout_photo, "Check-out Photo"))

        # Additional photos via reverse relation
        for photo in record.photos.filter(is_deleted=False).order_by('captured_at'):
            attachments.append(self._serialize_attendance_photo(photo, photo.photo_type))

        return attachments

    def _get_ticket_attachments(self, entity_id, tenant_id, user):
        """Get ticket attachments (both modern and legacy systems)."""
        from apps.y_helpdesk.models import Ticket, TicketAttachment
        from apps.activity.models import Attachment
        from apps.core_onboarding.models import TypeAssist

        try:
            ticket = Ticket.objects.get(id=entity_id, tenant_id=tenant_id)
        except Ticket.DoesNotExist:
            raise PermissionError("Ticket not found or access denied")

        attachments = []

        # Modern attachment system (TicketAttachment)
        for att in ticket.attachments.filter(is_scanned=True).order_by('-uploaded_at'):
            attachments.append(self._serialize_ticket_attachment(att))

        # Legacy attachment system (polymorphic)
        try:
            ticket_type = TypeAssist.objects.get(tacode="TICKET")
            legacy_attachments = Attachment.objects.filter(
                owner=str(ticket.uuid),
                ownername=ticket_type,
                tenant_id=tenant_id
            ).order_by('-datetime')

            for att in legacy_attachments:
                attachments.append(self._serialize_attachment(att))

        except TypeAssist.DoesNotExist:
            pass  # Legacy system not configured

        return attachments

    def _get_journal_attachments(self, entity_id, tenant_id, user):
        """Get journal media attachments (privacy-aware)."""
        from apps.journal.models.entry import JournalEntry
        from apps.journal.models.media import JournalMediaAttachment

        try:
            entry = JournalEntry.objects.get(id=entity_id, tenant_id=tenant_id)
        except JournalEntry.DoesNotExist:
            raise PermissionError("Journal entry not found or access denied")

        # Privacy check
        if entry.privacy_scope in ('PRIVATE', 'AGGREGATE_ONLY'):
            if entry.user_id != user.id:
                raise PermissionError("Cannot view private journal entry attachments")

        # Get media attachments
        media = entry.media_attachments.filter(
            is_deleted=False
        ).order_by('display_order', 'id')

        return [self._serialize_journal_media(m) for m in media]

    def _serialize_attachment(self, att):
        """Serialize legacy Attachment model."""
        return {
            "id": att.id,
            "uuid": str(att.uuid),
            "filename": str(att.filename),
            "url": att.filename.url if att.filename else None,
            "thumbnail_url": att.filename.url if att.filename else None,  # No thumbnail in legacy
            "file_type": self._detect_file_type(str(att.filename)),
            "file_size": att.size,
            "created_at": att.datetime.isoformat() if att.datetime else None,
            "uploaded_by": att.bu.buname if att.bu else None,
            "metadata": {
                "gps_lat": att.gpslocation.y if att.gpslocation else None,
                "gps_lon": att.gpslocation.x if att.gpslocation else None,
                "attachment_type": att.attachmenttype,
            },
        }

    def _serialize_attendance_photo(self, photo, photo_label):
        """Serialize AttendancePhoto model."""
        return {
            "id": photo.id,
            "uuid": str(photo.uuid),
            "filename": photo.image.name.split('/')[-1] if photo.image else "unknown",
            "url": photo.image.url if photo.image else None,
            "thumbnail_url": photo.thumbnail.url if photo.thumbnail else (photo.image.url if photo.image else None),
            "file_type": "photo",
            "file_size": photo.file_size_bytes,
            "created_at": photo.captured_at.isoformat(),
            "uploaded_by": photo.employee.peoplename if hasattr(photo.employee, 'peoplename') else None,
            "metadata": {
                "photo_type": photo_label,
                "face_detected": photo.face_detected,
                "face_count": photo.face_count,
                "quality_score": photo.quality_score,
                "quality_rating": photo.quality_rating,
                "is_blurry": photo.is_blurry,
                "is_dark": photo.is_dark,
                "width": photo.width,
                "height": photo.height,
            },
        }

    def _serialize_ticket_attachment(self, att):
        """Serialize modern TicketAttachment model."""
        return {
            "id": att.id,
            "uuid": str(att.uuid),
            "filename": att.filename,
            "url": att.file.url if att.file else None,
            "thumbnail_url": att.file.url if att.file else None,  # TODO: Add thumbnail generation
            "file_type": self._detect_file_type_from_mime(att.content_type),
            "file_size": att.file_size,
            "created_at": att.uploaded_at.isoformat(),
            "uploaded_by": att.uploaded_by.peoplename if att.uploaded_by and hasattr(att.uploaded_by, 'peoplename') else None,
            "metadata": {
                "scan_status": att.scan_status,
                "download_count": att.download_count,
            },
        }

    def _serialize_journal_media(self, media):
        """Serialize JournalMediaAttachment model."""
        return {
            "id": str(media.id),
            "uuid": str(media.id),
            "filename": media.original_filename,
            "url": media.file.url if media.file else None,
            "thumbnail_url": media.file.url if media.file else None,  # TODO: Add thumbnail
            "file_type": media.media_type.lower() if media.media_type else "unknown",
            "file_size": media.file_size,
            "created_at": media.created_at.isoformat() if hasattr(media, 'created_at') else None,
            "metadata": {
                "caption": media.caption,
                "display_order": media.display_order,
                "is_hero_image": media.is_hero_image,
                "mime_type": media.mime_type,
            },
        }

    def _detect_file_type(self, filename):
        """Detect file type from filename extension."""
        if not filename:
            return "unknown"

        filename_lower = filename.lower()
        if any(filename_lower.endswith(ext) for ext in ['.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp']):
            return "photo"
        elif any(filename_lower.endswith(ext) for ext in ['.mp4', '.mov', '.avi', '.webm', '.3gp', '.mkv']):
            return "video"
        elif any(filename_lower.endswith(ext) for ext in ['.pdf', '.doc', '.docx', '.xls', '.xlsx']):
            return "document"
        else:
            return "file"

    def _detect_file_type_from_mime(self, mime_type):
        """Detect file type from MIME type."""
        if not mime_type:
            return "unknown"

        if mime_type.startswith('image/'):
            return "photo"
        elif mime_type.startswith('video/'):
            return "video"
        elif mime_type.startswith('audio/'):
            return "audio"
        elif 'pdf' in mime_type or 'document' in mime_type or 'word' in mime_type:
            return "document"
        else:
            return "file"
