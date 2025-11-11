"""
Comprehensive Test Suite for Shift Assignment Validation Service

Tests all validation scenarios including:
- Site assignment validation
- Shift assignment and time window validation
- Rest period compliance
- Duplicate check-in detection
- Edge cases (overnight shifts, grace periods, timezone boundaries)

Author: Claude Code
Created: 2025-11-03
"""

import pytest
from datetime import datetime, time, timedelta
from django.utils import timezone
from django.contrib.gis.geos import Point

from apps.attendance.services.shift_validation_service import (
    ShiftAssignmentValidationService,
    ValidationResult
)
from apps.peoples.models import People
from apps.peoples.models.membership_model import Pgbelonging
from apps.activity.models import Jobneed
from apps.client_onboarding.models import Shift, Bt
from apps.attendance.models import PeopleEventlog
from apps.core.constants.datetime_constants import SECONDS_IN_HOUR


@pytest.fixture
def validation_service():
    """Create validation service instance for tests"""
    return ShiftAssignmentValidationService()


@pytest.fixture
def test_worker(db):
    """Create test worker"""
    return People.objects.create(
        username='test_worker',
        email='test@example.com',
        client_id=1,
        bu_id=1
    )


@pytest.fixture
def test_site(db):
    """Create test site"""
    return Bt.objects.create(
        buname='Test Site',
        bucode='TEST001',
        client_id=1,
        bupreferences={'posted_people': []}
    )


@pytest.fixture
def test_shift(db, test_site):
    """Create test shift (9 AM - 5 PM)"""
    return Shift.objects.create(
        shiftname='Morning Shift',
        bu=test_site,
        starttime=time(9, 0),
        endtime=time(17, 0),
        client_id=1
    )


@pytest.fixture
def overnight_shift(db, test_site):
    """Create overnight shift (10 PM - 6 AM)"""
    return Shift.objects.create(
        shiftname='Night Shift',
        bu=test_site,
        starttime=time(22, 0),
        endtime=time(6, 0),
        client_id=1
    )


class TestValidationResult:
    """Test ValidationResult helper class"""

    def test_validation_result_success(self):
        """Test successful validation result"""
        result = ValidationResult(valid=True, message='Success')
        assert result.valid is True
        assert result.reason is None
        assert result.message == 'Success'

    def test_validation_result_failure(self):
        """Test failed validation result with details"""
        result = ValidationResult(
            valid=False,
            reason='NOT_ASSIGNED_TO_SITE',
            site_id=123,
            worker_id=456
        )
        assert result.valid is False
        assert result.reason == 'NOT_ASSIGNED_TO_SITE'
        assert result.details['site_id'] == 123
        assert result.details['worker_id'] == 456

    def test_validation_result_to_dict(self):
        """Test conversion to dictionary"""
        result = ValidationResult(
            valid=False,
            reason='OUTSIDE_SHIFT_WINDOW',
            current_time='14:00',
            shift_window='09:00-17:00'
        )
        result_dict = result.to_dict()
        assert result_dict['valid'] is False
        assert result_dict['reason'] == 'OUTSIDE_SHIFT_WINDOW'
        assert result_dict['current_time'] == '14:00'
        assert result_dict['shift_window'] == '09:00-17:00'

    def test_user_friendly_messages(self):
        """Test user-friendly message generation"""
        result = ValidationResult(
            valid=False,
            reason='NOT_ASSIGNED_TO_SITE'
        )
        message = result.get_user_friendly_message()
        assert 'not assigned to this site' in message.lower()
        assert 'supervisor' in message.lower()


class TestSiteAssignmentValidation:
    """Test site assignment validation"""

    def test_worker_assigned_via_pgbelonging(self, validation_service, test_worker, test_site):
        """Test valid site assignment via Pgbelonging"""
        # Create assignment
        Pgbelonging.objects.create(
            people=test_worker,
            assignsites=test_site,
            client_id=1
        )

        result = validation_service._validate_site_assignment(test_worker.id, test_site.id)
        assert result.valid is True

    def test_worker_assigned_via_bupreferences(self, validation_service, test_worker, test_site):
        """Test valid site assignment via Bt.bupreferences (fallback)"""
        # Add worker to bupreferences
        test_site.bupreferences = {'posted_people': [test_worker.id]}
        test_site.save()

        result = validation_service._validate_site_assignment(test_worker.id, test_site.id)
        assert result.valid is True

    def test_worker_not_assigned_to_site(self, validation_service, test_worker, test_site):
        """Test site assignment failure when worker not assigned"""
        result = validation_service._validate_site_assignment(test_worker.id, test_site.id)
        assert result.valid is False
        assert result.reason == 'NOT_ASSIGNED_TO_SITE'
        assert result.details['requires_approval'] is True

    def test_bupreferences_handles_string_ids(self, validation_service, test_worker, test_site):
        """Test that bupreferences handles both string and int IDs"""
        # Use string ID in bupreferences
        test_site.bupreferences = {'posted_people': [str(test_worker.id)]}
        test_site.save()

        result = validation_service._validate_site_assignment(test_worker.id, test_site.id)
        assert result.valid is True


class TestShiftAssignmentValidation:
    """Test shift assignment and time window validation"""

    def test_valid_shift_assignment_within_window(self, validation_service, test_worker, test_site, test_shift):
        """Test valid shift assignment during shift hours"""
        # Create Jobneed
        today = timezone.now().date()
        Jobneed.objects.create(
            performedby=test_worker,
            bu=test_site,
            shift=test_shift,
            plandatetime=datetime.combine(today, time(9, 0)),
            jobstatus='ASSIGNED',
            client_id=1
        )

        # Check in at 9:15 AM (within grace period)
        check_in_time = datetime.combine(today, time(9, 15))
        check_in_time = timezone.make_aware(check_in_time)

        result = validation_service._validate_shift_assignment(
            test_worker.id,
            test_site.id,
            check_in_time
        )
        assert result.valid is True
        assert result.details['shift'] == test_shift

    def test_no_shift_assigned(self, validation_service, test_worker, test_site):
        """Test failure when no Jobneed exists"""
        check_in_time = timezone.now()
        result = validation_service._validate_shift_assignment(
            test_worker.id,
            test_site.id,
            check_in_time
        )
        assert result.valid is False
        assert result.reason == 'NO_SHIFT_ASSIGNED'

    def test_shift_not_specified_in_jobneed(self, validation_service, test_worker, test_site):
        """Test failure when Jobneed has no shift"""
        today = timezone.now().date()
        Jobneed.objects.create(
            performedby=test_worker,
            bu=test_site,
            shift=None,  # No shift specified
            plandatetime=datetime.combine(today, time(9, 0)),
            jobstatus='ASSIGNED',
            client_id=1
        )

        check_in_time = timezone.now()
        result = validation_service._validate_shift_assignment(
            test_worker.id,
            test_site.id,
            check_in_time
        )
        assert result.valid is False
        assert result.reason == 'NO_SHIFT_SPECIFIED'

    def test_outside_shift_window_too_early(self, validation_service, test_worker, test_site, test_shift):
        """Test failure when checking in too early (outside grace period)"""
        today = timezone.now().date()
        Jobneed.objects.create(
            performedby=test_worker,
            bu=test_site,
            shift=test_shift,  # 9 AM - 5 PM
            plandatetime=datetime.combine(today, time(9, 0)),
            jobstatus='ASSIGNED',
            client_id=1
        )

        # Check in at 8:30 AM (30 min early, outside 15 min grace period)
        check_in_time = datetime.combine(today, time(8, 30))
        check_in_time = timezone.make_aware(check_in_time)

        result = validation_service._validate_shift_assignment(
            test_worker.id,
            test_site.id,
            check_in_time
        )
        assert result.valid is False
        assert result.reason == 'OUTSIDE_SHIFT_WINDOW'

    def test_outside_shift_window_too_late(self, validation_service, test_worker, test_site, test_shift):
        """Test failure when checking in too late (outside grace period)"""
        today = timezone.now().date()
        Jobneed.objects.create(
            performedby=test_worker,
            bu=test_site,
            shift=test_shift,  # 9 AM - 5 PM
            plandatetime=datetime.combine(today, time(9, 0)),
            jobstatus='ASSIGNED',
            client_id=1
        )

        # Check in at 5:30 PM (30 min late, outside 15 min grace period)
        check_in_time = datetime.combine(today, time(17, 30))
        check_in_time = timezone.make_aware(check_in_time)

        result = validation_service._validate_shift_assignment(
            test_worker.id,
            test_site.id,
            check_in_time
        )
        assert result.valid is False
        assert result.reason == 'OUTSIDE_SHIFT_WINDOW'

    def test_grace_period_early_checkin(self, validation_service, test_worker, test_site, test_shift):
        """Test that 15-minute early check-in is allowed"""
        today = timezone.now().date()
        Jobneed.objects.create(
            performedby=test_worker,
            bu=test_site,
            shift=test_shift,  # 9 AM - 5 PM
            plandatetime=datetime.combine(today, time(9, 0)),
            jobstatus='ASSIGNED',
            client_id=1
        )

        # Check in at 8:50 AM (10 min early, within 15 min grace period)
        check_in_time = datetime.combine(today, time(8, 50))
        check_in_time = timezone.make_aware(check_in_time)

        result = validation_service._validate_shift_assignment(
            test_worker.id,
            test_site.id,
            check_in_time
        )
        assert result.valid is True

    def test_grace_period_late_checkin(self, validation_service, test_worker, test_site, test_shift):
        """Test that 15-minute late check-in is allowed"""
        today = timezone.now().date()
        Jobneed.objects.create(
            performedby=test_worker,
            bu=test_site,
            shift=test_shift,  # 9 AM - 5 PM
            plandatetime=datetime.combine(today, time(9, 0)),
            jobstatus='ASSIGNED',
            client_id=1
        )

        # Check in at 5:10 PM (10 min late, within 15 min grace period)
        check_in_time = datetime.combine(today, time(17, 10))
        check_in_time = timezone.make_aware(check_in_time)

        result = validation_service._validate_shift_assignment(
            test_worker.id,
            test_site.id,
            check_in_time
        )
        assert result.valid is True

    def test_overnight_shift_before_midnight(self, validation_service, test_worker, test_site, overnight_shift):
        """Test overnight shift check-in before midnight"""
        today = timezone.now().date()
        Jobneed.objects.create(
            performedby=test_worker,
            bu=test_site,
            shift=overnight_shift,  # 10 PM - 6 AM
            plandatetime=datetime.combine(today, time(22, 0)),
            jobstatus='ASSIGNED',
            client_id=1
        )

        # Check in at 10:15 PM
        check_in_time = datetime.combine(today, time(22, 15))
        check_in_time = timezone.make_aware(check_in_time)

        result = validation_service._validate_shift_assignment(
            test_worker.id,
            test_site.id,
            check_in_time
        )
        assert result.valid is True

    def test_overnight_shift_after_midnight(self, validation_service, test_worker, test_site, overnight_shift):
        """Test overnight shift check-in after midnight"""
        today = timezone.now().date()
        Jobneed.objects.create(
            performedby=test_worker,
            bu=test_site,
            shift=overnight_shift,  # 10 PM - 6 AM
            plandatetime=datetime.combine(today, time(22, 0)),
            jobstatus='ASSIGNED',
            client_id=1
        )

        # Check in at 2:00 AM next day
        tomorrow = today + timedelta(days=1)
        check_in_time = datetime.combine(tomorrow, time(2, 0))
        check_in_time = timezone.make_aware(check_in_time)

        result = validation_service._validate_shift_assignment(
            test_worker.id,
            test_site.id,
            check_in_time
        )
        # This should still work as it's within the overnight shift window
        assert result.valid is True


class TestRestPeriodValidation:
    """Test rest period compliance validation"""

    def test_sufficient_rest_period(self, validation_service, test_worker):
        """Test validation passes with sufficient rest (12 hours)"""
        # Create previous checkout 12 hours ago
        checkout_time = timezone.now() - timedelta(hours=12)
        PeopleEventlog.objects.create(
            people=test_worker,
            punchouttime=checkout_time,
            datefor=checkout_time.date(),
            client_id=1
        )

        check_in_time = timezone.now()
        result = validation_service._validate_rest_period(test_worker.id, check_in_time)
        assert result.valid is True

    def test_insufficient_rest_period(self, validation_service, test_worker):
        """Test validation fails with insufficient rest (8 hours < 10 hour minimum)"""
        # Create previous checkout 8 hours ago
        checkout_time = timezone.now() - timedelta(hours=8)
        PeopleEventlog.objects.create(
            people=test_worker,
            punchouttime=checkout_time,
            datefor=checkout_time.date(),
            client_id=1
        )

        check_in_time = timezone.now()
        result = validation_service._validate_rest_period(test_worker.id, check_in_time)
        assert result.valid is False
        assert result.reason == 'INSUFFICIENT_REST_PERIOD'
        assert result.details['rest_hours'] < 10
        assert result.details['minimum_required'] == 10
        assert result.details['requires_approval'] is True  # Can override for emergencies

    def test_no_previous_checkout(self, validation_service, test_worker):
        """Test validation passes when no previous checkout exists (first shift)"""
        check_in_time = timezone.now()
        result = validation_service._validate_rest_period(test_worker.id, check_in_time)
        assert result.valid is True

    def test_exactly_minimum_rest_period(self, validation_service, test_worker):
        """Test validation passes with exactly 10 hours rest"""
        # Create previous checkout exactly 10 hours ago
        checkout_time = timezone.now() - timedelta(hours=10)
        PeopleEventlog.objects.create(
            people=test_worker,
            punchouttime=checkout_time,
            datefor=checkout_time.date(),
            client_id=1
        )

        check_in_time = timezone.now()
        result = validation_service._validate_rest_period(test_worker.id, check_in_time)
        assert result.valid is True


class TestDuplicateCheckInDetection:
    """Test duplicate check-in detection"""

    def test_no_duplicate_checkin(self, validation_service, test_worker):
        """Test validation passes when no active check-in exists"""
        today = timezone.now().date()
        result = validation_service._validate_no_duplicate_checkin(test_worker.id, today)
        assert result.valid is True

    def test_duplicate_checkin_detected(self, validation_service, test_worker):
        """Test validation fails when active check-in exists"""
        today = timezone.now().date()
        # Create existing check-in without checkout
        PeopleEventlog.objects.create(
            people=test_worker,
            punchintime=timezone.now() - timedelta(hours=2),
            punchouttime=None,  # Still checked in
            datefor=today,
            client_id=1
        )

        result = validation_service._validate_no_duplicate_checkin(test_worker.id, today)
        assert result.valid is False
        assert result.reason == 'DUPLICATE_CHECKIN'
        assert result.details['requires_approval'] is False  # Hard block

    def test_previous_checkout_completed(self, validation_service, test_worker):
        """Test validation passes when previous check-in has checkout"""
        today = timezone.now().date()
        # Create completed check-in/checkout from earlier
        PeopleEventlog.objects.create(
            people=test_worker,
            punchintime=timezone.now() - timedelta(hours=10),
            punchouttime=timezone.now() - timedelta(hours=2),  # Checked out
            datefor=today,
            client_id=1
        )

        result = validation_service._validate_no_duplicate_checkin(test_worker.id, today)
        assert result.valid is True


class TestComprehensiveValidation:
    """Test comprehensive check-in validation (all layers)"""

    def test_successful_checkin_validation(self, validation_service, test_worker, test_site, test_shift):
        """Test all validation layers pass for valid check-in"""
        # Setup: assign worker to site
        Pgbelonging.objects.create(
            people=test_worker,
            assignsites=test_site,
            client_id=1
        )

        # Setup: create shift assignment
        today = timezone.now().date()
        Jobneed.objects.create(
            performedby=test_worker,
            bu=test_site,
            shift=test_shift,
            plandatetime=datetime.combine(today, time(9, 0)),
            jobstatus='ASSIGNED',
            client_id=1
        )

        # Check in at 9:00 AM
        check_in_time = datetime.combine(today, time(9, 0))
        check_in_time = timezone.make_aware(check_in_time)

        result = validation_service.validate_checkin(
            worker_id=test_worker.id,
            site_id=test_site.id,
            timestamp=check_in_time
        )

        assert result.valid is True
        assert result.details['shift'] == test_shift
        assert 'jobneed' in result.details

    def test_validation_fails_at_first_layer(self, validation_service, test_worker, test_site):
        """Test validation fails at site assignment (first layer)"""
        # No site assignment created
        check_in_time = timezone.now()

        result = validation_service.validate_checkin(
            worker_id=test_worker.id,
            site_id=test_site.id,
            timestamp=check_in_time
        )

        assert result.valid is False
        assert result.reason == 'NOT_ASSIGNED_TO_SITE'

    def test_validation_fails_at_second_layer(self, validation_service, test_worker, test_site):
        """Test validation fails at shift assignment (second layer)"""
        # Setup site assignment only
        Pgbelonging.objects.create(
            people=test_worker,
            assignsites=test_site,
            client_id=1
        )
        # No shift assignment

        check_in_time = timezone.now()

        result = validation_service.validate_checkin(
            worker_id=test_worker.id,
            site_id=test_site.id,
            timestamp=check_in_time
        )

        assert result.valid is False
        assert result.reason == 'NO_SHIFT_ASSIGNED'

    def test_validation_handles_exceptions(self, validation_service):
        """Test validation service handles exceptions gracefully"""
        # Invalid worker ID
        result = validation_service.validate_checkin(
            worker_id=99999,
            site_id=99999,
            timestamp=timezone.now()
        )

        assert result.valid is False
        assert result.reason == 'VALIDATION_ERROR'
        assert 'error' in result.details


@pytest.mark.django_db
class TestPerformance:
    """Test query performance with validation indexes"""

    def test_shift_assignment_query_performance(self, validation_service, test_worker, test_site, test_shift):
        """Test shift assignment query is optimized"""
        # Create test data
        today = timezone.now().date()
        Jobneed.objects.create(
            performedby=test_worker,
            bu=test_site,
            shift=test_shift,
            plandatetime=datetime.combine(today, time(9, 0)),
            jobstatus='ASSIGNED',
            client_id=1
        )

        check_in_time = datetime.combine(today, time(9, 0))
        check_in_time = timezone.make_aware(check_in_time)

        # This query should use pel_validation_lookup_idx
        from django.test.utils import CaptureQueriesContext
        from django.db import connection

        with CaptureQueriesContext(connection) as context:
            result = validation_service._validate_shift_assignment(
                test_worker.id,
                test_site.id,
                check_in_time
            )

        # Should only execute 1 query (no N+1)
        assert len(context.captured_queries) <= 2  # Main query + select_related

    def test_rest_period_query_performance(self, validation_service, test_worker):
        """Test rest period query is optimized"""
        # Create test data
        checkout_time = timezone.now() - timedelta(hours=12)
        PeopleEventlog.objects.create(
            people=test_worker,
            punchouttime=checkout_time,
            datefor=checkout_time.date(),
            client_id=1
        )

        check_in_time = timezone.now()

        # This query should use pel_rest_period_idx
        from django.test.utils import CaptureQueriesContext
        from django.db import connection

        with CaptureQueriesContext(connection) as context:
            result = validation_service._validate_rest_period(test_worker.id, check_in_time)

        # Should only execute 1 query
        assert len(context.captured_queries) == 1
