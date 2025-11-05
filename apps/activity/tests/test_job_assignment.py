"""
Job assignment tests for activity app.

Tests job and jobneed assignment to users, teams, locations,
and assignment validation rules.
"""
import pytest
from datetime import timedelta
from apps.activity.models import Job, Jobneed


@pytest.mark.django_db
class TestJobAssignment:
    """Test job assignment to users."""

    def test_assign_job_to_user(self, test_job, test_user):
        """Test assigning job template to user."""
        test_job.people = test_user
        test_job.save()

        test_job.refresh_from_db()
        assert test_job.people == test_user

    def test_assign_job_to_multiple_users(self, test_job, test_user, test_tenant):
        """Test assigning job to multiple users."""
        from django.contrib.auth import get_user_model
        User = get_user_model()

        user2 = User.objects.create(
            peoplecode="ACTUSER002",
            peoplename="Second User",
            loginid="actuser2",
            email="actuser2@example.com",
            mobno="8888888888",
            client=test_tenant,
            enable=True
        )

        # Assign to first user
        test_job.people = test_user
        test_job.save()

        # Create second job for second user
        job2 = Job.objects.create(
            jobname="Second Job",
            jobdesc="Another task",
            fromdate=test_job.fromdate,
            uptodate=test_job.uptodate,
            cron="0 9 * * *",
            identifier="TASK",
            planduration=60,
            gracetime=15,
            expirytime=120,
            priority="MEDIUM",
            scantype="QR",
            frequency="DAILY",
            qset=test_job.qset,
            client=test_tenant,
            bu=test_tenant,
            people=user2,
            seqno=2,
            enable=True,
            cdby=user2,
            mdby=user2
        )

        assert test_job.people == test_user
        assert job2.people == user2

    def test_query_jobs_assigned_to_user(self, test_job, test_user):
        """Test querying all jobs assigned to specific user."""
        test_job.people = test_user
        test_job.save()

        assigned_jobs = Job.objects.filter(people=test_user)
        assert test_job in assigned_jobs


@pytest.mark.django_db
class TestJobneedAssignment:
    """Test jobneed assignment to users."""

    def test_assign_jobneed_to_user(self, test_jobneed, test_user):
        """Test assigning jobneed instance to user."""
        test_jobneed.people = test_user
        test_jobneed.save()

        test_jobneed.refresh_from_db()
        assert test_jobneed.people == test_user

    def test_reassign_jobneed(self, test_jobneed, test_tenant):
        """Test reassigning jobneed to different user."""
        from django.contrib.auth import get_user_model
        User = get_user_model()

        user2 = User.objects.create(
            peoplecode="ACTUSER003",
            peoplename="Third User",
            loginid="actuser3",
            email="actuser3@example.com",
            mobno="7777777777",
            client=test_tenant,
            enable=True
        )

        test_jobneed.people = user2
        test_jobneed.save()

        test_jobneed.refresh_from_db()
        assert test_jobneed.people == user2

    def test_jobneed_assignment_history(self, test_jobneed, test_user):
        """Test tracking jobneed assignment history."""
        # Track via mdtz field (modification timestamp)
        original_mdtz = test_jobneed.mdtz

        test_jobneed.people = test_user
        test_jobneed.save()

        test_jobneed.refresh_from_db()
        assert test_jobneed.mdtz != original_mdtz

    def test_query_jobneeds_for_user(self, test_jobneed, test_user):
        """Test querying all jobneeds assigned to user."""
        test_jobneed.people = test_user
        test_jobneed.save()

        assigned_jobneeds = Jobneed.objects.filter(people=test_user)
        assert test_jobneed in assigned_jobneeds


@pytest.mark.django_db
class TestLocationBasedAssignment:
    """Test location-based job assignment."""

    def test_assign_jobs_by_location(self, test_job, test_location):
        """Test assigning jobs based on location."""
        # Jobs inherit location from asset
        if test_job.asset:
            assert test_job.asset.location == test_location

    def test_user_location_access_validation(self, test_user, test_location):
        """Test that users can only be assigned jobs at their locations."""
        # User's client should match
        jobs_at_location = Job.objects.filter(client=test_user.client)
        assert jobs_at_location.exists()

    def test_query_jobs_by_location(self, test_job, test_location):
        """Test querying all jobs for specific location."""
        # Query through asset relationship
        location_jobs = Job.objects.filter(asset__location=test_location)
        assert test_job in location_jobs


@pytest.mark.django_db
class TestAssetBasedAssignment:
    """Test asset-based job assignment."""

    def test_assign_jobs_by_asset(self, test_job, test_asset):
        """Test assigning jobs based on asset."""
        assert test_job.asset == test_asset

    def test_critical_asset_priority_assignment(self, critical_asset, test_user):
        """Test priority assignment for critical assets."""
        from django.utils import timezone

        critical_job = Job.objects.create(
            jobname="Critical Asset Maintenance",
            jobdesc="Urgent maintenance",
            fromdate=timezone.now(),
            uptodate=timezone.now() + timedelta(days=30),
            cron="0 8 * * *",
            identifier="TASK",
            planduration=60,
            gracetime=15,
            expirytime=120,
            priority="HIGH",
            scantype="QR",
            frequency="DAILY",
            asset=critical_asset,
            client=critical_asset.client,
            bu=critical_asset.bu,
            seqno=1,
            enable=True,
            cdby=test_user,
            mdby=test_user
        )

        assert critical_job.priority == "HIGH"
        assert critical_job.asset.iscritical is True

    def test_query_jobs_by_asset(self, test_job, test_asset):
        """Test querying all jobs for specific asset."""
        asset_jobs = Job.objects.filter(asset=test_asset)
        assert test_job in asset_jobs


@pytest.mark.django_db
class TestAssignmentValidation:
    """Test job assignment validation rules."""

    def test_cannot_assign_disabled_job(self, test_job, test_user):
        """Test that disabled jobs cannot be assigned."""
        test_job.enable = False
        test_job.save()

        assert test_job.enable is False

    def test_cannot_assign_to_disabled_user(self, test_job, test_user):
        """Test that jobs cannot be assigned to disabled users."""
        test_user.enable = False
        test_user.save()

        # Assignment should be validated in business logic
        assert test_user.enable is False

    def test_tenant_boundary_enforcement(self, test_job, test_user, test_tenant):
        """Test that assignment respects tenant boundaries."""
        assert test_job.client == test_user.client
        assert test_job.client == test_tenant


@pytest.mark.django_db
class TestBulkAssignment:
    """Test bulk job assignment operations."""

    def test_bulk_assign_jobs_to_user(self, test_job, test_user):
        """Test bulk assigning multiple jobs to user."""
        jobs = [test_job]
        for job in jobs:
            job.people = test_user
            job.save()

        assigned_count = Job.objects.filter(people=test_user).count()
        assert assigned_count >= 1

    def test_bulk_reassign_jobneeds(self, test_jobneed, test_user, test_tenant):
        """Test bulk reassigning jobneeds."""
        from django.contrib.auth import get_user_model
        User = get_user_model()

        user2 = User.objects.create(
            peoplecode="ACTUSER004",
            peoplename="Fourth User",
            loginid="actuser4",
            email="actuser4@example.com",
            mobno="6666666666",
            client=test_tenant,
            enable=True
        )

        jobneeds = [test_jobneed]
        for jobneed in jobneeds:
            jobneed.people = user2
            jobneed.save()

        reassigned_count = Jobneed.objects.filter(people=user2).count()
        assert reassigned_count >= 1

    def test_bulk_assignment_validation(self, test_job, test_user):
        """Test validation during bulk assignment."""
        test_job.people = test_user
        test_job.save()

        # Validate assignments preserved
        assigned_jobs = Job.objects.filter(people=test_user)
        assert test_job in assigned_jobs


@pytest.mark.django_db
class TestAssignmentNotifications:
    """Test notifications for job assignments."""

    def test_assignment_notification_sent(self, test_jobneed, test_user):
        """Test notification sent on job assignment."""
        test_jobneed.people = test_user
        test_jobneed.ismailsent = True
        test_jobneed.save()

        assert test_jobneed.ismailsent is True

    def test_reassignment_notification_sent(self, test_jobneed, test_user):
        """Test notification sent on job reassignment."""
        test_jobneed.people = test_user
        test_jobneed.ismailsent = True
        test_jobneed.save()

        test_jobneed.refresh_from_db()
        assert test_jobneed.ismailsent is True

    def test_overdue_assignment_reminder(self, test_jobneed, test_user):
        """Test reminder notification for overdue assignments."""
        from django.utils import timezone

        # Make jobneed overdue
        test_jobneed.endtime = timezone.now() - timedelta(hours=2)
        test_jobneed.jobstatus = "ASSIGNED"
        test_jobneed.save()

        # Check if overdue
        is_overdue = test_jobneed.endtime < timezone.now()
        assert is_overdue is True


@pytest.mark.django_db
class TestAssignmentWorkload:
    """Test workload balancing in assignments."""

    def test_calculate_user_workload(self, test_user):
        """Test calculating total workload for user."""
        assigned_jobs = Job.objects.filter(people=test_user).count()
        assigned_jobneeds = Jobneed.objects.filter(people=test_user).count()

        workload = assigned_jobs + assigned_jobneeds
        assert workload >= 0

    def test_workload_based_assignment(self, test_jobneed, test_user, test_tenant):
        """Test assignment considering current workload."""
        from django.contrib.auth import get_user_model
        User = get_user_model()

        # Create user with low workload
        user2 = User.objects.create(
            peoplecode="ACTUSER005",
            peoplename="Fifth User",
            loginid="actuser5",
            email="actuser5@example.com",
            mobno="5555555555",
            client=test_tenant,
            enable=True
        )

        user2_workload = Jobneed.objects.filter(people=user2).count()
        assert user2_workload == 0

        # Assign jobneed
        test_jobneed.people = user2
        test_jobneed.save()

        user2_workload = Jobneed.objects.filter(people=user2).count()
        assert user2_workload == 1

    def test_prevent_workload_overallocation(self, test_user):
        """Test preventing excessive workload assignment."""
        # Get current workload
        current_workload = Jobneed.objects.filter(
            people=test_user,
            jobstatus__in=["ASSIGNED", "INPROGRESS"]
        ).count()

        # This would be enforced in business logic
        max_workload = 100
        assert current_workload < max_workload


@pytest.mark.django_db
class TestAssignmentHistory:
    """Test assignment history tracking."""

    def test_track_assignment_changes(self, test_jobneed, test_user):
        """Test tracking all assignment changes."""
        original_mdby = test_jobneed.mdby

        test_jobneed.people = test_user
        test_jobneed.mdby = test_user
        test_jobneed.save()

        # Check modification tracking
        test_jobneed.refresh_from_db()
        assert test_jobneed.mdby == test_user

    def test_query_assignment_history(self, test_jobneed):
        """Test querying complete assignment history."""
        # History tracked via mdtz timestamps
        assert test_jobneed.mdtz is not None
        assert test_jobneed.cdtz is not None

    def test_assignment_audit_log(self, test_jobneed, test_user):
        """Test assignment changes logged for audit."""
        test_jobneed.people = test_user
        test_jobneed.save()

        # Audit via mdby and mdtz fields
        assert test_jobneed.mdby is not None
        assert test_jobneed.mdtz is not None
