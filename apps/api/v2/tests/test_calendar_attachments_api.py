"""Integration tests for calendar event attachments endpoint."""

from __future__ import annotations

import uuid
from datetime import timedelta
from unittest.mock import Mock, patch

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from apps.client_onboarding.models import Bt
from apps.peoples.models import People
from apps.tenants.models import Tenant


class CalendarEventAttachmentsAPITests(TestCase):
    """Test /api/v2/calendar/events/{event_id}/attachments/ endpoint."""

    def setUp(self):
        """Set up test tenant, client, and user."""
        self.tenant = Tenant.objects.create(name="Test Tenant", schema_name="test")
        self.client_bt = Bt.objects.create(
            tenant=self.tenant,
            buname="Test Client",
            client_id=self.tenant.id
        )
        self.user = People.objects.create_user(
            username="testuser",
            email="test@example.com",
            peoplename="Test User",
            tenant=self.tenant,
            client=self.client_bt,
            bu=self.client_bt,
        )

        self.api_client = APIClient()
        self.api_client.force_authenticate(user=self.user)

    def test_get_jobneed_attachments_success(self):
        """Test fetching attachments for a jobneed event."""
        event_id = "jobneed:123"

        # Mock the attachment fetching
        mock_attachments = [
            {
                "id": 1,
                "uuid": str(uuid.uuid4()),
                "filename": "inspection_photo.jpg",
                "url": "/media/attachments/inspection_photo.jpg",
                "thumbnail_url": "/media/attachments/inspection_photo.jpg",
                "file_type": "photo",
                "file_size": 1024000,
                "created_at": timezone.now().isoformat(),
                "metadata": {"attachment_type": "ATTACHMENT"},
            }
        ]

        url = reverse('api_v2:calendar:event_attachments', kwargs={'event_id': event_id})

        with patch.object(
            self.api_client.handler._force_user.__class__,
            'tenant_id',
            self.tenant.id
        ), patch(
            'apps.api.v2.views.calendar_views.CalendarEventAttachmentsView._get_jobneed_attachments',
            return_value=mock_attachments
        ):
            response = self.api_client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()

        self.assertTrue(data["success"])
        self.assertEqual(data["data"]["event_id"], event_id)
        self.assertEqual(data["data"]["count"], 1)
        self.assertEqual(len(data["data"]["attachments"]), 1)

        attachment = data["data"]["attachments"][0]
        self.assertEqual(attachment["filename"], "inspection_photo.jpg")
        self.assertEqual(attachment["file_type"], "photo")
        self.assertIn("correlation_id", data["meta"])

    def test_invalid_event_id_format_returns_400(self):
        """Test that malformed event ID returns 400 Bad Request."""
        invalid_event_ids = [
            "invalid",  # No colon
            "jobneed:",  # Missing ID
            ":123",  # Missing provider
            "jobneed:abc",  # Non-numeric ID
        ]

        for event_id in invalid_event_ids:
            url = reverse('api_v2:calendar:event_attachments', kwargs={'event_id': event_id})
            response = self.api_client.get(url)

            self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
            data = response.json()
            self.assertFalse(data["success"])
            self.assertIn("Invalid event_id format", data["error"]["message"])

    def test_unknown_provider_returns_404(self):
        """Test that unknown provider returns 404 Not Found."""
        event_id = "unknown_provider:123"

        with patch.object(
            self.api_client.handler._force_user.__class__,
            'tenant_id',
            self.tenant.id
        ):
            url = reverse('api_v2:calendar:event_attachments', kwargs={'event_id': event_id})
            response = self.api_client.get(url)

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        data = response.json()
        self.assertFalse(data["success"])
        self.assertIn("Event not found", data["error"]["message"])

    def test_private_journal_attachments_return_403_for_non_owner(self):
        """Test that private journal attachments return 403 for non-owners."""
        event_id = "journal:456"

        with patch.object(
            self.api_client.handler._force_user.__class__,
            'tenant_id',
            self.tenant.id
        ), patch(
            'apps.api.v2.views.calendar_views.CalendarEventAttachmentsView._get_journal_attachments',
            side_effect=PermissionError("Cannot view private journal entry attachments")
        ):
            url = reverse('api_v2:calendar:event_attachments', kwargs={'event_id': event_id})
            response = self.api_client.get(url)

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        data = response.json()
        self.assertFalse(data["success"])
        self.assertIn("Cannot view private", data["error"]["message"])

    def test_attendance_photos_serialization(self):
        """Test that attendance photos are serialized with metadata."""
        event_id = "attendance:789"

        mock_attachments = [
            {
                "id": 1,
                "uuid": str(uuid.uuid4()),
                "filename": "checkin.jpg",
                "url": "/media/attendance_photos/checkin.jpg",
                "thumbnail_url": "/media/attendance_photos/thumbnails/checkin.jpg",
                "file_type": "photo",
                "file_size": 850000,
                "created_at": timezone.now().isoformat(),
                "metadata": {
                    "photo_type": "Check-in Photo",
                    "face_detected": True,
                    "face_count": 1,
                    "quality_score": 0.92,
                    "quality_rating": "GOOD",
                    "is_blurry": False,
                    "is_dark": False,
                    "width": 1920,
                    "height": 1080,
                },
            }
        ]

        with patch.object(
            self.api_client.handler._force_user.__class__,
            'tenant_id',
            self.tenant.id
        ), patch(
            'apps.api.v2.views.calendar_views.CalendarEventAttachmentsView._get_attendance_attachments',
            return_value=mock_attachments
        ):
            url = reverse('api_v2:calendar:event_attachments', kwargs={'event_id': event_id})
            response = self.api_client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()

        attachment = data["data"]["attachments"][0]
        self.assertEqual(attachment["file_type"], "photo")
        self.assertIn("face_detected", attachment["metadata"])
        self.assertTrue(attachment["metadata"]["face_detected"])
        self.assertIn("quality_score", attachment["metadata"])
        self.assertEqual(attachment["metadata"]["quality_score"], 0.92)

    def test_empty_attachments_returns_zero_count(self):
        """Test that events with no attachments return empty list."""
        event_id = "task:999"

        with patch.object(
            self.api_client.handler._force_user.__class__,
            'tenant_id',
            self.tenant.id
        ), patch(
            'apps.api.v2.views.calendar_views.CalendarEventAttachmentsView._get_jobneed_attachments',
            return_value=[]  # No attachments
        ):
            url = reverse('api_v2:calendar:event_attachments', kwargs={'event_id': event_id})
            response = self.api_client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()

        self.assertEqual(data["data"]["count"], 0)
        self.assertEqual(len(data["data"]["attachments"]), 0)

    def test_unauthenticated_request_returns_401(self):
        """Test that unauthenticated requests are rejected."""
        unauth_client = APIClient()  # No authentication
        event_id = "jobneed:123"

        url = reverse('api_v2:calendar:event_attachments', kwargs={'event_id': event_id})
        response = unauth_client.get(url)

        self.assertIn(response.status_code, [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN])

    def test_correlation_id_in_response(self):
        """Verify correlation_id is included in all responses."""
        event_id = "ticket:111"

        with patch.object(
            self.api_client.handler._force_user.__class__,
            'tenant_id',
            self.tenant.id
        ), patch(
            'apps.api.v2.views.calendar_views.CalendarEventAttachmentsView._get_ticket_attachments',
            return_value=[]
        ):
            url = reverse('api_v2:calendar:event_attachments', kwargs={'event_id': event_id})
            response = self.api_client.get(url)

        data = response.json()
        self.assertIn("meta", data)
        self.assertIn("correlation_id", data["meta"])
        # Verify it's a valid UUID
        correlation_uuid = uuid.UUID(data["meta"]["correlation_id"])
        self.assertIsInstance(correlation_uuid, uuid.UUID)
