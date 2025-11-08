"""Test suite for Activity Timeline functionality."""

import pytest
from datetime import date, timedelta
from django.utils import timezone
from apps.core.services.activity_timeline_service import ActivityTimelineService
from apps.y_helpdesk.models import Ticket
from apps.attendance.models import Attendance


@pytest.fixture
def person_with_activity(tenant, user):
    """Create a person with various activities."""
    # Create tickets
    Ticket.objects.create(
        tenant=tenant,
        cuser=user,
        ticketdesc="Created ticket",
        status="OPEN"
    )
    
    # Create attendance records
    Attendance.objects.create(
        tenant=tenant,
        people=user,
        attendance_date=timezone.now().date(),
        check_in=timezone.now()
    )
    
    return user


@pytest.mark.django_db
class TestTimeline:
    """Test activity timeline generation and filtering."""

    def test_person_timeline(self, person_with_activity):
        """Test person timeline generation."""
        service = ActivityTimelineService()
        events = service.get_person_timeline(person_with_activity)
        
        assert isinstance(events, list)
        assert len(events) > 0
        
        for event in events:
            assert 'timestamp' in event
            assert 'type' in event
            assert 'title' in event
            assert 'description' in event

    def test_timeline_filtering(self, person_with_activity):
        """Test timeline date filtering."""
        service = ActivityTimelineService()
        
        start_date = date(2025, 1, 1)
        end_date = date(2025, 12, 31)
        
        events = service.get_person_timeline(
            person_with_activity,
            start_date=start_date,
            end_date=end_date
        )
        
        for event in events:
            event_date = event['timestamp'].date() if hasattr(event['timestamp'], 'date') else event['timestamp']
            assert start_date <= event_date <= end_date

    def test_timeline_event_types(self, tenant, user):
        """Test different event types are captured."""
        service = ActivityTimelineService()
        
        # Create various activities
        ticket = Ticket.objects.create(
            tenant=tenant,
            cuser=user,
            ticketdesc="Test ticket",
            status="OPEN"
        )
        
        Attendance.objects.create(
            tenant=tenant,
            people=user,
            attendance_date=timezone.now().date(),
            check_in=timezone.now()
        )
        
        events = service.get_person_timeline(user)
        
        event_types = {event['type'] for event in events}
        assert len(event_types) > 0
        
        # Should include different activity types
        expected_types = {'ticket_created', 'attendance'}
        assert len(event_types.intersection(expected_types)) > 0

    def test_timeline_ordering(self, person_with_activity):
        """Test events are ordered by timestamp."""
        service = ActivityTimelineService()
        events = service.get_person_timeline(person_with_activity)
        
        if len(events) > 1:
            timestamps = [e['timestamp'] for e in events]
            # Should be in descending order (newest first)
            assert all(timestamps[i] >= timestamps[i+1] for i in range(len(timestamps)-1))

    def test_timeline_pagination(self, person_with_activity, tenant):
        """Test timeline pagination."""
        # Create many activities
        for i in range(30):
            Ticket.objects.create(
                tenant=tenant,
                cuser=person_with_activity,
                ticketdesc=f"Ticket {i}",
                status="OPEN"
            )
        
        service = ActivityTimelineService()
        
        # Get first page
        events_page1 = service.get_person_timeline(person_with_activity, limit=10, offset=0)
        assert len(events_page1) == 10
        
        # Get second page
        events_page2 = service.get_person_timeline(person_with_activity, limit=10, offset=10)
        assert len(events_page2) == 10
        
        # Pages should be different
        if events_page1 and events_page2:
            assert events_page1[0]['timestamp'] != events_page2[0]['timestamp']

    def test_empty_timeline(self, tenant, user):
        """Test timeline for user with no activity."""
        # Create new user with no activity
        from django.contrib.auth import get_user_model
        User = get_user_model()
        
        new_user = User.objects.create_user(
            username="newuser",
            email="new@test.com",
            tenant=tenant
        )
        
        service = ActivityTimelineService()
        events = service.get_person_timeline(new_user)
        
        assert isinstance(events, list)
        assert len(events) == 0

    def test_timeline_performance(self, person_with_activity, django_assert_max_num_queries):
        """Test timeline is performant with query optimization."""
        service = ActivityTimelineService()
        
        with django_assert_max_num_queries(20):  # Adjust based on optimization
            events = service.get_person_timeline(person_with_activity)
            assert len(events) >= 0

    def test_timeline_icons(self, person_with_activity):
        """Test timeline events have appropriate icons."""
        service = ActivityTimelineService()
        events = service.get_person_timeline(person_with_activity)
        
        for event in events:
            if 'icon' in event:
                assert isinstance(event['icon'], str)
                assert len(event['icon']) > 0

    def test_timeline_links(self, person_with_activity):
        """Test timeline events have navigation links."""
        service = ActivityTimelineService()
        events = service.get_person_timeline(person_with_activity)
        
        for event in events:
            if 'link' in event:
                assert event['link'].startswith('/') or event['link'].startswith('http')

    def test_timeline_grouping_by_date(self, person_with_activity):
        """Test timeline can be grouped by date."""
        service = ActivityTimelineService()
        grouped_events = service.get_person_timeline_grouped(person_with_activity)
        
        assert isinstance(grouped_events, dict)
        
        for date_key, events in grouped_events.items():
            assert isinstance(events, list)
            # All events in group should be from same date
            if events:
                event_dates = {e['timestamp'].date() for e in events}
                assert len(event_dates) == 1
