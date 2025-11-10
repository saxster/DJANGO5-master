"""Tests for calendar event attachment integration."""

from __future__ import annotations

from datetime import datetime, timedelta
from unittest.mock import Mock, patch

from django.test import TestCase
from django.utils import timezone

from apps.calendar_view.constants import CalendarEventType
from apps.calendar_view.providers.attendance import AttendanceEventProvider
from apps.calendar_view.providers.jobneed import JobneedEventProvider
from apps.calendar_view.providers.journal import JournalEventProvider
from apps.calendar_view.providers.ticket import TicketEventProvider
from apps.calendar_view.types import CalendarContextFilter, CalendarQueryParams


class AttendanceProviderAttachmentTests(TestCase):
    """Test attachment counts in AttendanceEventProvider."""

    def test_photo_count_included_in_metadata(self):
        """Verify photo_count appears in event metadata."""
        # Create mock attendance record with photo annotation
        mock_record = Mock()
        mock_record.pk = 123
        mock_record.tenant_id = 1
        mock_record.people_id = 456
        mock_record.punchintime = timezone.now()
        mock_record.punchouttime = None
        mock_record.datefor = timezone.now().date()
        mock_record.shift_id = 789
        mock_record.post_id = 101
        mock_record.post_assignment_id = 202
        mock_record.transportmodes = []
        mock_record.checkin_photo_id = 111
        mock_record.checkout_photo_id = None
        mock_record.photo_count = 3  # Annotated count
        mock_record.people = Mock(peoplename="John Doe")
        mock_record.bu = Mock(buname="Site A")
        mock_record.post = Mock(postname="Main Gate")
        mock_record.geofence = None
        mock_record.otherlocation = None

        params = CalendarQueryParams(
            start=timezone.now() - timedelta(days=1),
            end=timezone.now() + timedelta(days=1),
            tenant_id=1,
            user_id=456,
            context_filter=CalendarContextFilter(),
            event_types=[CalendarEventType.ATTENDANCE],
            statuses=[],
            search=None,
        )

        provider = AttendanceEventProvider()

        with patch.object(
            provider, '_apply_context_filters', return_value=Mock(iterator=lambda: [mock_record])
        ):
            events = provider.fetch(params)

        self.assertEqual(len(events), 1)
        event = events[0]

        # Verify attachment metadata
        self.assertIn("photo_count", event.metadata)
        self.assertEqual(event.metadata["photo_count"], 3)
        self.assertIn("has_checkin_photo", event.metadata)
        self.assertTrue(event.metadata["has_checkin_photo"])
        self.assertIn("has_checkout_photo", event.metadata)
        self.assertFalse(event.metadata["has_checkout_photo"])
        self.assertIn("has_attachments", event.metadata)
        self.assertTrue(event.metadata["has_attachments"])

    def test_has_attachments_true_when_photos_exist(self):
        """Verify has_attachments=True when any photos exist."""
        mock_record = Mock()
        mock_record.pk = 123
        mock_record.tenant_id = 1
        mock_record.people_id = 456
        mock_record.punchintime = timezone.now()
        mock_record.punchouttime = None
        mock_record.datefor = timezone.now().date()
        mock_record.shift_id = None
        mock_record.post_id = None
        mock_record.post_assignment_id = None
        mock_record.transportmodes = []
        mock_record.checkin_photo_id = None
        mock_record.checkout_photo_id = 222  # Checkout photo exists
        mock_record.photo_count = 0
        mock_record.people = Mock(peoplename="Jane Smith")
        mock_record.bu = Mock(buname="Site B")
        mock_record.post = None
        mock_record.geofence = None
        mock_record.otherlocation = None

        params = CalendarQueryParams(
            start=timezone.now() - timedelta(days=1),
            end=timezone.now() + timedelta(days=1),
            tenant_id=1,
            user_id=456,
            context_filter=CalendarContextFilter(),
            event_types=[CalendarEventType.ATTENDANCE],
            statuses=[],
        )

        provider = AttendanceEventProvider()

        with patch.object(
            provider, '_apply_context_filters', return_value=Mock(iterator=lambda: [mock_record])
        ):
            events = provider.fetch(params)

        event = events[0]
        self.assertTrue(event.metadata["has_attachments"])
        self.assertFalse(event.metadata["has_checkin_photo"])
        self.assertTrue(event.metadata["has_checkout_photo"])


class JobneedProviderAttachmentTests(TestCase):
    """Test attachment counts in JobneedEventProvider."""

    def test_attachment_count_from_denormalized_field(self):
        """Verify attachment_count uses denormalized field."""
        mock_jobneed = Mock()
        mock_jobneed.pk = 555
        mock_jobneed.tenant_id = 1
        mock_jobneed.identifier = "TASK"
        mock_jobneed.jobstatus = "ASSIGNED"
        mock_jobneed.jobdesc = "Security Check"
        mock_jobneed.plandatetime = timezone.now()
        mock_jobneed.expirydatetime = timezone.now() + timedelta(hours=2)
        mock_jobneed.starttime = None
        mock_jobneed.endtime = None
        mock_jobneed.job_id = 100
        mock_jobneed.people_id = 200
        mock_jobneed.priority = "HIGH"
        mock_jobneed.ticket_id = None
        mock_jobneed.attachmentcount = 5  # Denormalized count
        mock_jobneed.asset_id = None
        mock_jobneed.asset = None
        mock_jobneed.bu_id = 10
        mock_jobneed.bu = Mock(buname="Facility X")

        params = CalendarQueryParams(
            start=timezone.now() - timedelta(days=1),
            end=timezone.now() + timedelta(days=1),
            tenant_id=1,
            user_id=200,
            context_filter=CalendarContextFilter(),
            event_types=[CalendarEventType.TASK],
            statuses=[],
        )

        provider = JobneedEventProvider()

        with patch.object(
            provider, '_apply_context_filters', return_value=Mock(iterator=lambda: [mock_jobneed])
        ):
            events = provider.fetch(params)

        self.assertEqual(len(events), 1)
        event = events[0]

        # Verify attachment metadata
        self.assertIn("attachment_count", event.metadata)
        self.assertEqual(event.metadata["attachment_count"], 5)
        self.assertIn("has_attachments", event.metadata)
        self.assertTrue(event.metadata["has_attachments"])

    def test_has_attachments_false_when_zero_count(self):
        """Verify has_attachments=False when count is zero."""
        mock_jobneed = Mock()
        mock_jobneed.pk = 666
        mock_jobneed.tenant_id = 1
        mock_jobneed.identifier = "PPM"
        mock_jobneed.jobstatus = "COMPLETED"
        mock_jobneed.jobdesc = "Inspection"
        mock_jobneed.plandatetime = timezone.now()
        mock_jobneed.expirydatetime = None
        mock_jobneed.starttime = None
        mock_jobneed.endtime = None
        mock_jobneed.job_id = 300
        mock_jobneed.people_id = 400
        mock_jobneed.priority = None
        mock_jobneed.ticket_id = None
        mock_jobneed.attachmentcount = 0  # Zero attachments
        mock_jobneed.asset_id = None
        mock_jobneed.asset = None
        mock_jobneed.bu_id = None
        mock_jobneed.bu = None

        params = CalendarQueryParams(
            start=timezone.now() - timedelta(days=1),
            end=timezone.now() + timedelta(days=1),
            tenant_id=1,
            user_id=400,
            context_filter=CalendarContextFilter(),
            event_types=[CalendarEventType.INSPECTION],
            statuses=[],
        )

        provider = JobneedEventProvider()

        with patch.object(
            provider, '_apply_context_filters', return_value=Mock(iterator=lambda: [mock_jobneed])
        ):
            events = provider.fetch(params)

        event = events[0]
        self.assertEqual(event.metadata["attachment_count"], 0)
        self.assertFalse(event.metadata["has_attachments"])


class TicketProviderAttachmentTests(TestCase):
    """Test attachment counts in TicketEventProvider."""

    def test_dual_attachment_system_counts(self):
        """Verify both legacy and modern attachment counts are included."""
        mock_ticket = Mock()
        mock_ticket.pk = 888
        mock_ticket.tenant_id = 1
        mock_ticket.ticketno = "TKT-001"
        mock_ticket.ticketdesc = "Broken window"
        mock_ticket.status = "OPEN"
        mock_ticket.priority = "HIGH"
        mock_ticket.cdtz = timezone.now()
        mock_ticket.assignedtopeople_id = 500
        mock_ticket.assignedtogroup_id = None
        mock_ticket.asset_id = None
        mock_ticket.bu_id = None
        mock_ticket.location_id = None
        mock_ticket.attachmentcount = 2  # Legacy count
        mock_ticket.modern_attachment_count = 3  # Modern count (annotation)
        mock_ticket.photo_count = 2  # Photo-only count
        mock_ticket.video_count = 1  # Video count
        mock_ticket.assignedtopeople = None
        mock_ticket.assignedtogroup = None
        mock_ticket.asset = None
        mock_ticket.bu = None
        mock_ticket.location = None

        params = CalendarQueryParams(
            start=timezone.now() - timedelta(days=1),
            end=timezone.now() + timedelta(days=1),
            tenant_id=1,
            user_id=500,
            context_filter=CalendarContextFilter(),
            event_types=[CalendarEventType.TICKET],
            statuses=[],
        )

        provider = TicketEventProvider()

        with patch.object(
            provider, '_apply_context_filters', return_value=Mock(iterator=lambda: [mock_ticket])
        ):
            events = provider.fetch(params)

        event = events[0]

        # Verify dual system counts
        self.assertEqual(event.metadata["attachment_count"], 2)
        self.assertEqual(event.metadata["modern_attachment_count"], 3)
        self.assertEqual(event.metadata["photo_count"], 2)
        self.assertEqual(event.metadata["video_count"], 1)
        self.assertTrue(event.metadata["has_attachments"])


class JournalProviderPrivacyTests(TestCase):
    """Test privacy-aware attachment counts in JournalEventProvider."""

    def test_private_entry_hides_counts_from_non_owner(self):
        """Verify PRIVATE journal entries hide photo counts from non-owners."""
        mock_entry = Mock()
        mock_entry.pk = 999
        mock_entry.tenant_id = 1
        mock_entry.user_id = 100  # Owner
        mock_entry.title = "Private Reflection"
        mock_entry.subtitle = None
        mock_entry.entry_type = "MOOD_CHECK_IN"
        mock_entry.timestamp = timezone.now()
        mock_entry.privacy_scope = "PRIVATE"
        mock_entry.mood_rating = "GOOD"
        mock_entry.stress_level = 3
        mock_entry.location_site_name = None
        mock_entry.location_address = None
        mock_entry.media_count = 5  # Has media
        mock_entry.photo_count = 4  # Has photos
        mock_entry.video_count = 1  # Has video
        mock_entry.user = Mock()

        params = CalendarQueryParams(
            start=timezone.now() - timedelta(days=1),
            end=timezone.now() + timedelta(days=1),
            tenant_id=1,
            user_id=200,  # Different user (not owner)
            context_filter=CalendarContextFilter(),
            event_types=[CalendarEventType.JOURNAL],
            statuses=[],
        )

        provider = JournalEventProvider()

        with patch.object(
            provider, '_apply_context_filters', return_value=Mock(iterator=lambda: [mock_entry])
        ):
            events = provider.fetch(params)

        event = events[0]

        # Verify counts are HIDDEN from non-owner
        self.assertEqual(event.metadata["photo_count"], 0)
        self.assertEqual(event.metadata["video_count"], 0)
        self.assertEqual(event.metadata["media_count"], 0)
        self.assertFalse(event.metadata["has_attachments"])

    def test_private_entry_shows_counts_to_owner(self):
        """Verify PRIVATE journal entries show photo counts to owner."""
        mock_entry = Mock()
        mock_entry.pk = 1000
        mock_entry.tenant_id = 1
        mock_entry.user_id = 100  # Owner
        mock_entry.title = "My Private Thoughts"
        mock_entry.subtitle = None
        mock_entry.entry_type = "PERSONAL_REFLECTION"
        mock_entry.timestamp = timezone.now()
        mock_entry.privacy_scope = "PRIVATE"
        mock_entry.mood_rating = "ANXIOUS"
        mock_entry.stress_level = 7
        mock_entry.location_site_name = None
        mock_entry.location_address = None
        mock_entry.media_count = 3
        mock_entry.photo_count = 2
        mock_entry.video_count = 1
        mock_entry.user = Mock()

        params = CalendarQueryParams(
            start=timezone.now() - timedelta(days=1),
            end=timezone.now() + timedelta(days=1),
            tenant_id=1,
            user_id=100,  # Same user (owner)
            context_filter=CalendarContextFilter(),
            event_types=[CalendarEventType.JOURNAL],
            statuses=[],
        )

        provider = JournalEventProvider()

        with patch.object(
            provider, '_apply_context_filters', return_value=Mock(iterator=lambda: [mock_entry])
        ):
            events = provider.fetch(params)

        event = events[0]

        # Verify counts are VISIBLE to owner
        self.assertEqual(event.metadata["photo_count"], 2)
        self.assertEqual(event.metadata["video_count"], 1)
        self.assertEqual(event.metadata["media_count"], 3)
        self.assertTrue(event.metadata["has_attachments"])

    def test_shared_entry_shows_counts_to_all(self):
        """Verify SHARED journal entries show counts to all users."""
        mock_entry = Mock()
        mock_entry.pk = 1001
        mock_entry.tenant_id = 1
        mock_entry.user_id = 100
        mock_entry.title = "Team Update"
        mock_entry.subtitle = None
        mock_entry.entry_type = "TEAM_REFLECTION"
        mock_entry.timestamp = timezone.now()
        mock_entry.privacy_scope = "SHARED"  # Not private
        mock_entry.mood_rating = None
        mock_entry.stress_level = None
        mock_entry.location_site_name = None
        mock_entry.location_address = None
        mock_entry.media_count = 2
        mock_entry.photo_count = 2
        mock_entry.video_count = 0
        mock_entry.user = Mock()

        params = CalendarQueryParams(
            start=timezone.now() - timedelta(days=1),
            end=timezone.now() + timedelta(days=1),
            tenant_id=1,
            user_id=999,  # Different user
            context_filter=CalendarContextFilter(),
            event_types=[CalendarEventType.JOURNAL],
            statuses=[],
        )

        provider = JournalEventProvider()

        with patch.object(
            provider, '_apply_context_filters', return_value=Mock(iterator=lambda: [mock_entry])
        ):
            events = provider.fetch(params)

        event = events[0]

        # Verify counts are VISIBLE to non-owner (shared scope)
        self.assertEqual(event.metadata["photo_count"], 2)
        self.assertEqual(event.metadata["video_count"], 0)
        self.assertEqual(event.metadata["media_count"], 2)
        self.assertTrue(event.metadata["has_attachments"])


class AttachmentFilteringTests(TestCase):
    """Test attachment-based filtering in aggregation service."""

    def test_filter_events_with_attachments(self):
        """Verify has_attachments=true filter works."""
        from apps.calendar_view.services import CalendarAggregationService
        from apps.calendar_view.types import CalendarEvent, CalendarEventStatus

        # Create test events
        event_with_photos = CalendarEvent(
            id="test:1",
            event_type=CalendarEventType.TASK,
            status=CalendarEventStatus.COMPLETED,
            title="Task with photos",
            start=timezone.now(),
            metadata={"attachment_count": 3, "has_attachments": True},
        )

        event_without_photos = CalendarEvent(
            id="test:2",
            event_type=CalendarEventType.TASK,
            status=CalendarEventStatus.COMPLETED,
            title="Task without photos",
            start=timezone.now() + timedelta(hours=1),
            metadata={"attachment_count": 0, "has_attachments": False},
        )

        params = CalendarQueryParams(
            start=timezone.now() - timedelta(days=1),
            end=timezone.now() + timedelta(days=1),
            tenant_id=1,
            user_id=100,
            context_filter=CalendarContextFilter(),
            event_types=[],
            statuses=[],
            has_attachments=True,  # Filter to events with attachments
        )

        service = CalendarAggregationService(providers=[])
        filtered = service._post_process([event_with_photos, event_without_photos], params)

        # Only event with attachments should be included
        self.assertEqual(len(filtered), 1)
        self.assertEqual(filtered[0].id, "test:1")

    def test_filter_minimum_attachment_count(self):
        """Verify min_attachment_count filter works."""
        from apps.calendar_view.services import CalendarAggregationService
        from apps.calendar_view.types import CalendarEvent, CalendarEventStatus

        event1 = CalendarEvent(
            id="test:1",
            event_type=CalendarEventType.INSPECTION,
            status=CalendarEventStatus.COMPLETED,
            title="Inspection with 5 photos",
            start=timezone.now(),
            metadata={"attachment_count": 5, "has_attachments": True},
        )

        event2 = CalendarEvent(
            id="test:2",
            event_type=CalendarEventType.INSPECTION,
            status=CalendarEventStatus.COMPLETED,
            title="Inspection with 2 photos",
            start=timezone.now() + timedelta(hours=1),
            metadata={"attachment_count": 2, "has_attachments": True},
        )

        event3 = CalendarEvent(
            id="test:3",
            event_type=CalendarEventType.INSPECTION,
            status=CalendarEventStatus.COMPLETED,
            title="Inspection with 0 photos",
            start=timezone.now() + timedelta(hours=2),
            metadata={"attachment_count": 0, "has_attachments": False},
        )

        params = CalendarQueryParams(
            start=timezone.now() - timedelta(days=1),
            end=timezone.now() + timedelta(days=1),
            tenant_id=1,
            user_id=100,
            context_filter=CalendarContextFilter(),
            event_types=[],
            statuses=[],
            min_attachment_count=3,  # Minimum 3 attachments
        )

        service = CalendarAggregationService(providers=[])
        filtered = service._post_process([event1, event2, event3], params)

        # Only event with >=3 attachments
        self.assertEqual(len(filtered), 1)
        self.assertEqual(filtered[0].id, "test:1")
        self.assertEqual(filtered[0].metadata["attachment_count"], 5)
