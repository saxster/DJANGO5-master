"""
Comprehensive Test Suite for Post Models (Phase 2-3)

Tests for:
- Post model (duty stations)
- PostAssignment model (roster)
- PostOrderAcknowledgement model (compliance)

Author: Claude Code
Created: 2025-11-03
"""

import pytest
from datetime import datetime, time, date, timedelta
from django.utils import timezone
from django.contrib.gis.geos import Point
from django.core.exceptions import ValidationError
from django.db import IntegrityError

from apps.attendance.models import Post, PostAssignment, PostOrderAcknowledgement
from apps.onboarding.models import Shift, Bt, OnboardingZone
from apps.peoples.models import People


# ==================== FIXTURES ====================

@pytest.fixture
def test_site(db):
    """Create test site"""
    return Bt.objects.create(
        buname='Test Security Site',
        bucode='TSS001',
        gpslocation=Point(77.2090, 28.6139, srid=4326),
        client_id=1,
        tenant='default'
    )


@pytest.fixture
def test_shift(db, test_site):
    """Create test shift"""
    return Shift.objects.create(
        shiftname='Morning Shift',
        bu=test_site,
        starttime=time(9, 0),
        endtime=time(17, 0),
        client_id=1,
        tenant='default'
    )


@pytest.fixture
def test_worker(db, test_site):
    """Create test worker"""
    return People.objects.create(
        username='test_guard',
        email='guard@test.com',
        first_name='John',
        last_name='Doe',
        client_id=1,
        bu=test_site,
        tenant='default'
    )


@pytest.fixture
def test_zone(db, test_site):
    """Create test zone"""
    return OnboardingZone.objects.create(
        zone_name='Main Gate',
        zone_type='GATE',
        site=test_site,
        gps_coordinates=Point(77.2090, 28.6139, srid=4326),
        coverage_required=True,
        importance_level='high',
        risk_level='high',
        tenant='default'
    )


@pytest.fixture
def test_post(db, test_site, test_shift, test_zone):
    """Create test post"""
    return Post.objects.create(
        post_code='GATE-A-MORNING',
        post_name='Main Gate - Morning Shift',
        post_type='GATE',
        site=test_site,
        zone=test_zone,
        shift=test_shift,
        gps_coordinates=Point(77.2090, 28.6139, srid=4326),
        geofence_radius=50,
        required_guard_count=1,
        armed_required=False,
        post_orders='Guard the main gate. Check all IDs.',
        post_orders_version=1,
        risk_level='HIGH',
        active=True,
        coverage_required=True,
        tenant='default',
        client=test_site
    )


@pytest.fixture
def test_assignment(db, test_worker, test_post, test_shift, test_site):
    """Create test post assignment"""
    return PostAssignment.objects.create(
        worker=test_worker,
        post=test_post,
        shift=test_shift,
        site=test_site,
        assignment_date=date.today(),
        start_time=time(9, 0),
        end_time=time(17, 0),
        status='SCHEDULED',
        tenant='default',
        client=test_site
    )


# ==================== POST MODEL TESTS ====================

class TestPostModel:
    """Test Post model functionality"""

    def test_post_creation(self, test_post):
        """Test basic post creation"""
        assert test_post.id is not None
        assert test_post.post_code == 'GATE-A-MORNING'
        assert test_post.post_name == 'Main Gate - Morning Shift'
        assert test_post.post_type == 'GATE'
        assert test_post.risk_level == 'HIGH'
        assert test_post.active is True

    def test_post_str_representation(self, test_post):
        """Test __str__ method"""
        expected = f"{test_post.post_code} - {test_post.post_name} ({test_post.site.buname})"
        assert str(test_post) == expected

    def test_post_unique_constraint_post_code(self, test_site, test_shift):
        """Test unique constraint on (site, post_code, tenant)"""
        # Create first post
        Post.objects.create(
            post_code='GATE-001',
            post_name='Gate 1',
            post_type='GATE',
            site=test_site,
            shift=test_shift,
            tenant='default',
            client=test_site
        )

        # Try to create duplicate
        with pytest.raises(IntegrityError):
            Post.objects.create(
                post_code='GATE-001',  # Same code
                post_name='Gate 2',     # Different name
                post_type='GATE',
                site=test_site,
                shift=test_shift,
                tenant='default',
                client=test_site
            )

    def test_post_orders_version_auto_increment(self, test_post):
        """Test post_orders_version auto-increments on save"""
        original_version = test_post.post_orders_version

        # Update post orders
        test_post.post_orders = "Updated instructions"
        test_post.save()

        assert test_post.post_orders_version == original_version + 1

    def test_get_required_certifications_list(self, test_post):
        """Test getting required certifications"""
        certs = test_post.get_required_certifications_list()
        assert isinstance(certs, list)

    def test_is_coverage_met_true(self, test_post, test_assignment):
        """Test coverage met when assigned >= required"""
        is_met, assigned, required = test_post.is_coverage_met()
        assert is_met is True
        assert assigned == 1
        assert required == 1

    def test_is_coverage_met_false(self, test_post):
        """Test coverage not met when assigned < required"""
        test_post.required_guard_count = 2
        test_post.save()

        is_met, assigned, required = test_post.is_coverage_met()
        assert is_met is False
        assert assigned == 0  # No assignments yet
        assert required == 2

    def test_is_coverage_met_not_required(self, test_post):
        """Test coverage check when coverage not required"""
        test_post.coverage_required = False
        test_post.save()

        is_met, assigned, required = test_post.is_coverage_met()
        assert is_met is True
        assert assigned == 0
        assert required == 0

    def test_get_current_assignments(self, test_post, test_assignment):
        """Test getting current assignments"""
        assignments = test_post.get_current_assignments()
        assert assignments.count() == 1
        assert assignments.first() == test_assignment

    def test_get_post_orders_dict(self, test_post):
        """Test post orders dictionary generation"""
        orders_dict = test_post.get_post_orders_dict()
        assert orders_dict['post_code'] == test_post.post_code
        assert orders_dict['version'] == test_post.post_orders_version
        assert 'orders' in orders_dict
        assert 'duties' in orders_dict


# ==================== POST ASSIGNMENT MODEL TESTS ====================

class TestPostAssignmentModel:
    """Test PostAssignment model functionality"""

    def test_assignment_creation(self, test_assignment):
        """Test basic assignment creation"""
        assert test_assignment.id is not None
        assert test_assignment.status == 'SCHEDULED'
        assert test_assignment.worker is not None
        assert test_assignment.post is not None

    def test_assignment_str_representation(self, test_assignment):
        """Test __str__ method"""
        result = str(test_assignment)
        assert test_assignment.post.post_code in result
        assert str(test_assignment.assignment_date) in result

    def test_unique_constraint_worker_post_date(self, test_worker, test_post, test_shift, test_site):
        """Test unique constraint prevents duplicate assignments"""
        assignment_date = date.today()

        # Create first assignment
        PostAssignment.objects.create(
            worker=test_worker,
            post=test_post,
            shift=test_shift,
            site=test_site,
            assignment_date=assignment_date,
            start_time=time(9, 0),
            end_time=time(17, 0),
            tenant='default',
            client=test_site
        )

        # Try to create duplicate
        with pytest.raises(IntegrityError):
            PostAssignment.objects.create(
                worker=test_worker,
                post=test_post,
                shift=test_shift,
                site=test_site,
                assignment_date=assignment_date,
                start_time=time(9, 0),
                end_time=time(17, 0),
                tenant='default',
                client=test_site
            )

    def test_auto_populate_site_from_post(self, test_worker, test_post, test_shift):
        """Test site auto-populated from post on save"""
        assignment = PostAssignment(
            worker=test_worker,
            post=test_post,
            shift=test_shift,
            # site NOT provided
            assignment_date=date.today(),
            tenant='default',
            client=test_post.site
        )
        assignment.save()

        assert assignment.site == test_post.site

    def test_auto_populate_times_from_shift(self, test_worker, test_post, test_shift, test_site):
        """Test start/end times auto-populated from shift"""
        assignment = PostAssignment(
            worker=test_worker,
            post=test_post,
            shift=test_shift,
            site=test_site,
            assignment_date=date.today(),
            # start_time and end_time NOT provided
            tenant='default',
            client=test_site
        )
        assignment.save()

        assert assignment.start_time == test_shift.starttime
        assert assignment.end_time == test_shift.endtime

    def test_mark_confirmed(self, test_assignment):
        """Test marking assignment as confirmed"""
        test_assignment.mark_confirmed()

        assert test_assignment.status == 'CONFIRMED'
        assert test_assignment.confirmed_at is not None

    def test_mark_checked_in(self, test_assignment):
        """Test marking assignment as checked in"""
        test_assignment.mark_checked_in()

        assert test_assignment.status == 'IN_PROGRESS'
        assert test_assignment.checked_in_at is not None
        assert test_assignment.late_minutes is not None

    def test_mark_checked_out(self, test_assignment):
        """Test marking assignment as checked out with hours calculation"""
        # First check in
        test_assignment.mark_checked_in()

        # Wait a bit (simulate)
        import time as time_module
        time_module.sleep(0.1)

        # Then check out
        test_assignment.mark_checked_out()

        assert test_assignment.status == 'COMPLETED'
        assert test_assignment.checked_out_at is not None
        assert test_assignment.hours_worked is not None
        assert test_assignment.hours_worked > 0

    def test_mark_no_show(self, test_assignment):
        """Test marking assignment as no-show"""
        test_assignment.mark_no_show()
        assert test_assignment.status == 'NO_SHOW'

    def test_can_check_in_scheduled(self, test_assignment):
        """Test can_check_in returns True for SCHEDULED status"""
        assert test_assignment.can_check_in() is True

    def test_can_check_in_in_progress(self, test_assignment):
        """Test can_check_in returns False for IN_PROGRESS status"""
        test_assignment.mark_checked_in()
        assert test_assignment.can_check_in() is False

    def test_can_check_out_in_progress(self, test_assignment):
        """Test can_check_out returns True for IN_PROGRESS status"""
        test_assignment.mark_checked_in()
        assert test_assignment.can_check_out() is True

    def test_can_check_out_scheduled(self, test_assignment):
        """Test can_check_out returns False for SCHEDULED status"""
        assert test_assignment.can_check_out() is False

    def test_acknowledge_post_orders(self, test_assignment):
        """Test acknowledging post orders"""
        test_assignment.acknowledge_post_orders(version=1)

        assert test_assignment.post_orders_acknowledged is True
        assert test_assignment.post_orders_version_acknowledged == 1
        assert test_assignment.post_orders_acknowledged_at is not None

    def test_clean_validation_override_requires_reason(self, test_worker, test_post, test_shift, test_site):
        """Test validation error when override without reason"""
        assignment = PostAssignment(
            worker=test_worker,
            post=test_post,
            shift=test_shift,
            site=test_site,
            assignment_date=date.today(),
            is_override=True,
            override_reason='',  # Missing reason
            tenant='default',
            client=test_site
        )

        with pytest.raises(ValidationError) as exc:
            assignment.clean()

        assert 'override_reason' in exc.value.message_dict

    def test_to_dict_method(self, test_assignment):
        """Test to_dict serialization"""
        result = test_assignment.to_dict()

        assert result['id'] == test_assignment.id
        assert 'worker' in result
        assert 'post' in result
        assert 'site' in result
        assert 'shift' in result
        assert result['status'] == 'SCHEDULED'


# ==================== POST ORDER ACKNOWLEDGEMENT TESTS ====================

class TestPostOrderAcknowledgementModel:
    """Test PostOrderAcknowledgement model functionality"""

    def test_acknowledgement_creation(self, test_worker, test_post):
        """Test basic acknowledgement creation"""
        ack = PostOrderAcknowledgement.objects.create(
            worker=test_worker,
            post=test_post,
            post_orders_version=1,
            device_id='device-123',
            acknowledgement_method='mobile_app',
            tenant='default',
            client=test_post.site
        )

        assert ack.id is not None
        assert ack.worker == test_worker
        assert ack.post == test_post
        assert ack.is_valid is True

    def test_acknowledgement_str_representation(self, test_worker, test_post):
        """Test __str__ method"""
        ack = PostOrderAcknowledgement.objects.create(
            worker=test_worker,
            post=test_post,
            post_orders_version=1,
            tenant='default',
            client=test_post.site
        )

        result = str(ack)
        assert test_post.post_code in result
        assert 'v1' in result

    def test_unique_constraint(self, test_worker, test_post):
        """Test unique constraint on (worker, post, version, date, tenant)"""
        today = date.today()

        # Create first acknowledgement
        PostOrderAcknowledgement.objects.create(
            worker=test_worker,
            post=test_post,
            post_orders_version=1,
            acknowledgement_date=today,
            tenant='default',
            client=test_post.site
        )

        # Try to create duplicate
        with pytest.raises(IntegrityError):
            PostOrderAcknowledgement.objects.create(
                worker=test_worker,
                post=test_post,
                post_orders_version=1,  # Same version
                acknowledgement_date=today,  # Same date
                tenant='default',
                client=test_post.site
            )

    def test_auto_populate_acknowledgement_date(self, test_worker, test_post):
        """Test acknowledgement_date auto-populated from acknowledged_at"""
        ack_time = timezone.now()
        ack = PostOrderAcknowledgement.objects.create(
            worker=test_worker,
            post=test_post,
            post_orders_version=1,
            acknowledged_at=ack_time,
            tenant='default',
            client=test_post.site
        )

        assert ack.acknowledgement_date == ack_time.date()

    def test_content_hash_generation(self, test_worker, test_post):
        """Test content hash auto-generated on save"""
        ack = PostOrderAcknowledgement.objects.create(
            worker=test_worker,
            post=test_post,
            post_orders_version=1,
            tenant='default',
            client=test_post.site
        )

        assert ack.post_orders_content_hash is not None
        assert len(ack.post_orders_content_hash) == 64  # SHA-256

    def test_verify_integrity_true(self, test_worker, test_post):
        """Test integrity verification when post orders unchanged"""
        ack = PostOrderAcknowledgement.objects.create(
            worker=test_worker,
            post=test_post,
            post_orders_version=1,
            tenant='default',
            client=test_post.site
        )

        # Post orders unchanged
        assert ack.verify_integrity() is True

    def test_verify_integrity_false(self, test_worker, test_post):
        """Test integrity verification when post orders changed"""
        ack = PostOrderAcknowledgement.objects.create(
            worker=test_worker,
            post=test_post,
            post_orders_version=1,
            tenant='default',
            client=test_post.site
        )

        # Change post orders after acknowledgement
        test_post.post_orders = "COMPLETELY DIFFERENT ORDERS"
        test_post.save()

        # Integrity should fail
        assert ack.verify_integrity() is False

    def test_is_expired_false(self, test_worker, test_post):
        """Test is_expired returns False when no expiration set"""
        ack = PostOrderAcknowledgement.objects.create(
            worker=test_worker,
            post=test_post,
            post_orders_version=1,
            valid_until=None,  # No expiration
            tenant='default',
            client=test_post.site
        )

        assert ack.is_expired() is False

    def test_is_expired_true(self, test_worker, test_post):
        """Test is_expired returns True when expired"""
        ack = PostOrderAcknowledgement.objects.create(
            worker=test_worker,
            post=test_post,
            post_orders_version=1,
            valid_until=timezone.now() - timedelta(days=1),  # Expired yesterday
            tenant='default',
            client=test_post.site
        )

        assert ack.is_expired() is True

    def test_invalidate_acknowledgement(self, test_worker, test_post):
        """Test invalidating acknowledgement"""
        ack = PostOrderAcknowledgement.objects.create(
            worker=test_worker,
            post=test_post,
            post_orders_version=1,
            tenant='default',
            client=test_post.site
        )

        assert ack.is_valid is True

        ack.invalidate(reason="Post orders updated")

        assert ack.is_valid is False
        assert 'invalidation_reason' in ack.acknowledgement_metadata

    def test_verify_by_supervisor(self, test_worker, test_post):
        """Test supervisor verification"""
        ack = PostOrderAcknowledgement.objects.create(
            worker=test_worker,
            post=test_post,
            post_orders_version=1,
            tenant='default',
            client=test_post.site
        )

        supervisor = People.objects.create(
            username='supervisor',
            email='supervisor@test.com',
            client_id=1,
            tenant='default'
        )

        ack.verify_by_supervisor(supervisor)

        assert ack.supervisor_verified is True
        assert ack.verified_by == supervisor
        assert ack.verified_at is not None

    def test_has_valid_acknowledgement_class_method(self, test_worker, test_post):
        """Test has_valid_acknowledgement class method"""
        today = date.today()

        # No acknowledgement yet
        assert PostOrderAcknowledgement.has_valid_acknowledgement(
            worker=test_worker,
            post=test_post,
            date=today
        ) is False

        # Create acknowledgement
        PostOrderAcknowledgement.objects.create(
            worker=test_worker,
            post=test_post,
            post_orders_version=1,
            acknowledgement_date=today,
            is_valid=True,
            tenant='default',
            client=test_post.site
        )

        # Now should return True
        assert PostOrderAcknowledgement.has_valid_acknowledgement(
            worker=test_worker,
            post=test_post,
            date=today
        ) is True

    def test_get_latest_acknowledgement(self, test_worker, test_post):
        """Test getting latest acknowledgement"""
        # Create multiple acknowledgements
        ack1 = PostOrderAcknowledgement.objects.create(
            worker=test_worker,
            post=test_post,
            post_orders_version=1,
            acknowledged_at=timezone.now() - timedelta(days=2),
            tenant='default',
            client=test_post.site
        )

        ack2 = PostOrderAcknowledgement.objects.create(
            worker=test_worker,
            post=test_post,
            post_orders_version=2,
            acknowledged_at=timezone.now(),
            tenant='default',
            client=test_post.site
        )

        latest = PostOrderAcknowledgement.get_latest_acknowledgement(
            worker=test_worker,
            post=test_post
        )

        assert latest == ack2

    def test_bulk_invalidate_for_post(self, test_worker, test_post):
        """Test bulk invalidation when post orders updated"""
        # Create acknowledgements
        ack1 = PostOrderAcknowledgement.objects.create(
            worker=test_worker,
            post=test_post,
            post_orders_version=1,
            is_valid=True,
            tenant='default',
            client=test_post.site
        )

        worker2 = People.objects.create(
            username='worker2',
            email='worker2@test.com',
            client_id=1,
            tenant='default'
        )

        ack2 = PostOrderAcknowledgement.objects.create(
            worker=worker2,
            post=test_post,
            post_orders_version=1,
            is_valid=True,
            tenant='default',
            client=test_post.site
        )

        # Bulk invalidate
        PostOrderAcknowledgement.bulk_invalidate_for_post(
            post=test_post,
            reason="Post orders updated to v2"
        )

        # Refresh from database
        ack1.refresh_from_db()
        ack2.refresh_from_db()

        assert ack1.is_valid is False
        assert ack2.is_valid is False

    def test_to_dict_method(self, test_worker, test_post):
        """Test to_dict serialization"""
        ack = PostOrderAcknowledgement.objects.create(
            worker=test_worker,
            post=test_post,
            post_orders_version=1,
            quiz_taken=True,
            quiz_score=85,
            tenant='default',
            client=test_post.site
        )

        result = ack.to_dict()

        assert result['id'] == ack.id
        assert 'worker' in result
        assert 'post' in result
        assert result['post_orders_version'] == 1
        assert result['quiz_passed'] is True  # 85 >= 70


# ==================== INTEGRATION TESTS ====================

class TestPostAssignmentIntegration:
    """Test integration between models"""

    def test_assignment_links_to_attendance_record(self, test_assignment):
        """Test assignment can link to attendance record"""
        from apps.attendance.models import PeopleEventlog

        attendance = PeopleEventlog.objects.create(
            people=test_assignment.worker,
            bu=test_assignment.site,
            shift=test_assignment.shift,
            post=test_assignment.post,
            post_assignment=test_assignment,
            punchintime=timezone.now(),
            datefor=date.today(),
            tenant='default'
        )

        test_assignment.attendance_record = attendance
        test_assignment.save()

        assert test_assignment.attendance_record == attendance

    def test_post_orders_workflow(self, test_worker, test_post, test_assignment):
        """Test complete post orders workflow"""
        # 1. Worker gets assignment
        assert test_assignment.post_orders_acknowledged is False

        # 2. Worker views post orders
        post_orders = test_post.get_post_orders_dict()
        assert post_orders['version'] == 1

        # 3. Worker acknowledges
        ack = PostOrderAcknowledgement.objects.create(
            worker=test_worker,
            post=test_post,
            post_assignment=test_assignment,
            post_orders_version=test_post.post_orders_version,
            tenant='default',
            client=test_post.site
        )

        # 4. Update assignment
        test_assignment.acknowledge_post_orders(version=1)
        assert test_assignment.post_orders_acknowledged is True

        # 5. Post orders updated (version incremented)
        test_post.post_orders = "Updated orders"
        test_post.save()
        assert test_post.post_orders_version == 2

        # 6. Acknowledgement invalidated
        PostOrderAcknowledgement.bulk_invalidate_for_post(test_post)
        ack.refresh_from_db()
        assert ack.is_valid is False

    def test_coverage_monitoring(self, test_post, test_worker, test_shift, test_site):
        """Test coverage requirement monitoring"""
        # Set requirement to 3 guards
        test_post.required_guard_count = 3
        test_post.save()

        # No assignments - gap exists
        is_met, assigned, required = test_post.is_coverage_met()
        assert is_met is False
        assert required == 3
        assert assigned == 0

        # Add 1 assignment - still gap
        PostAssignment.objects.create(
            worker=test_worker,
            post=test_post,
            shift=test_shift,
            site=test_site,
            assignment_date=date.today(),
            tenant='default',
            client=test_site
        )

        is_met, assigned, required = test_post.is_coverage_met()
        assert is_met is False
        assert assigned == 1

        # Add 2 more workers
        for i in range(2, 4):
            worker = People.objects.create(
                username=f'guard{i}',
                email=f'guard{i}@test.com',
                client_id=1,
                tenant='default'
            )
            PostAssignment.objects.create(
                worker=worker,
                post=test_post,
                shift=test_shift,
                site=test_site,
                assignment_date=date.today(),
                tenant='default',
                client=test_site
            )

        # Now coverage met
        is_met, assigned, required = test_post.is_coverage_met()
        assert is_met is True
        assert assigned == 3
        assert required == 3


# ==================== EDGE CASE TESTS ====================

class TestEdgeCases:
    """Test edge cases and boundary conditions"""

    def test_post_with_no_geofence(self, test_site, test_shift):
        """Test post without geofence defined"""
        post = Post.objects.create(
            post_code='NO-GF-POST',
            post_name='Post Without Geofence',
            post_type='OTHER',
            site=test_site,
            shift=test_shift,
            gps_coordinates=None,  # No GPS
            geofence=None,  # No geofence
            tenant='default',
            client=test_site
        )

        assert post.id is not None
        # Should not crash

    def test_assignment_without_post_orders_acknowledgement(self, test_assignment):
        """Test assignment can exist without acknowledgement"""
        assert test_assignment.post_orders_acknowledged is False
        test_assignment.mark_checked_in()  # Should not fail
        assert test_assignment.status == 'IN_PROGRESS'

    def test_temporary_post_date_range(self, test_site, test_shift):
        """Test temporary post with date range"""
        post = Post.objects.create(
            post_code='TEMP-001',
            post_name='Temporary Event Post',
            post_type='OTHER',
            site=test_site,
            shift=test_shift,
            temporary=True,
            temporary_start_date=date.today(),
            temporary_end_date=date.today() + timedelta(days=7),
            tenant='default',
            client=test_site
        )

        assert post.temporary is True
        assert post.temporary_start_date is not None
        assert post.temporary_end_date is not None

    def test_acknowledgement_with_quiz(self, test_worker, test_post):
        """Test acknowledgement with quiz/comprehension"""
        ack = PostOrderAcknowledgement.objects.create(
            worker=test_worker,
            post=test_post,
            post_orders_version=1,
            quiz_taken=True,
            quiz_score=85,
            quiz_results={'q1': 'correct', 'q2': 'correct', 'q3': 'incorrect'},
            tenant='default',
            client=test_post.site
        )

        # Quiz should be marked as passed (85 >= 70)
        result = ack.to_dict()
        assert result['quiz_passed'] is True

    def test_acknowledgement_with_low_quiz_score(self, test_worker, test_post):
        """Test acknowledgement with failing quiz score"""
        ack = PostOrderAcknowledgement.objects.create(
            worker=test_worker,
            post=test_post,
            post_orders_version=1,
            quiz_taken=True,
            quiz_score=50,  # Below 70%
            tenant='default',
            client=test_post.site
        )

        result = ack.to_dict()
        assert result['quiz_passed'] is False


# ==================== PERFORMANCE TESTS ====================

@pytest.mark.django_db
class TestPerformance:
    """Test query performance with indexes"""

    def test_post_assignment_lookup_performance(self, test_worker, test_post, test_shift, test_site):
        """Test post assignment lookup uses indexes efficiently"""
        # Create test data
        assignment = PostAssignment.objects.create(
            worker=test_worker,
            post=test_post,
            shift=test_shift,
            site=test_site,
            assignment_date=date.today(),
            start_time=time(9, 0),
            end_time=time(17, 0),
            tenant='default',
            client=test_site
        )

        from django.test.utils import CaptureQueriesContext
        from django.db import connection

        with CaptureQueriesContext(connection) as context:
            result = PostAssignment.objects.filter(
                worker=test_worker,
                assignment_date=date.today(),
                status__in=['SCHEDULED', 'CONFIRMED']
            ).select_related('post', 'shift').first()

        # Should use pa_worker_date_idx index
        # Should execute minimal queries with select_related
        assert len(context.captured_queries) <= 2  # Main query + select_related
        assert result == assignment

    def test_acknowledgement_validity_check_performance(self, test_worker, test_post):
        """Test acknowledgement validity check uses indexes"""
        # Create test data
        PostOrderAcknowledgement.objects.create(
            worker=test_worker,
            post=test_post,
            post_orders_version=1,
            acknowledgement_date=date.today(),
            is_valid=True,
            tenant='default',
            client=test_post.site
        )

        from django.test.utils import CaptureQueriesContext
        from django.db import connection

        with CaptureQueriesContext(connection) as context:
            has_valid = PostOrderAcknowledgement.has_valid_acknowledgement(
                worker=test_worker,
                post=test_post,
                date=date.today()
            )

        # Should use poa_date_valid_idx index
        assert len(context.captured_queries) == 1
        assert has_valid is True
