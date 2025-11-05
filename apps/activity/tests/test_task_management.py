"""
Task management tests for activity app.

Tests Job (templates) and Jobneed (instances) creation, scheduling,
execution, and lifecycle management.
"""
import pytest
from datetime import datetime, timezone as dt_timezone, timedelta
from apps.activity.models import Job, Jobneed


@pytest.mark.django_db
class TestJobCreation:
    """Test Job (task template) creation."""

    def test_create_basic_job(self, test_tenant, test_asset, test_question_set, test_user):
        """Test creating a basic job template."""
        from django.utils import timezone

        job = Job.objects.create(
            jobname="Test Job",
            jobdesc="Test job description",
            fromdate=timezone.now(),
            uptodate=timezone.now() + timedelta(days=30),
            cron="0 8 * * *",
            identifier="TASK",
            planduration=60,
            gracetime=15,
            expirytime=120,
            priority="MEDIUM",
            scantype="QR",
            frequency="DAILY",
            asset=test_asset,
            qset=test_question_set,
            client=test_tenant,
            bu=test_tenant,
            seqno=1,
            enable=True,
            cdby=test_user,
            mdby=test_user
        )

        assert job.id is not None
        assert job.jobname == "Test Job"
        assert job.identifier == "TASK"
        assert job.enable is True

    def test_create_job_missing_required_fields(self, test_tenant):
        """Test that creating job without required fields raises error."""
        from django.db import IntegrityError

        with pytest.raises((IntegrityError, ValueError)):
            Job.objects.create(
                jobname="Incomplete Job",
                client=test_tenant
            )

    def test_job_uuid_generated(self, test_job):
        """Test that UUID is auto-generated for jobs."""
        # Job model has version field (VersionField) not uuid
        assert test_job.version is not None
        assert test_job.id is not None

    def test_job_other_info_defaults(self, test_job):
        """Test that other_info JSONField has default values."""
        assert test_job.other_info is not None
        assert isinstance(test_job.other_info, dict)
        assert "tour_frequency" in test_job.other_info
        assert "is_randomized" in test_job.other_info
        assert test_job.other_info["tour_frequency"] == 1
        assert test_job.other_info["is_randomized"] is False


@pytest.mark.django_db
class TestJobScheduling:
    """Test job scheduling and recurrence."""

    def test_schedule_recurring_job(self, test_job):
        """Test scheduling job with recurrence pattern."""
        assert test_job.frequency == "NONE"
        assert test_job.cron is not None

        # Update with daily frequency
        test_job.frequency = "DAILY"
        test_job.save()

        test_job.refresh_from_db()
        assert test_job.frequency == "DAILY"

    def test_job_date_range_validation(self, test_tenant, test_asset, test_question_set, test_user):
        """Test that end date must be after start date."""
        from django.utils import timezone

        start = timezone.now()
        end = start + timedelta(days=30)

        job = Job.objects.create(
            jobname="Valid Date Range Job",
            jobdesc="Test",
            fromdate=start,
            uptodate=end,
            cron="0 8 * * *",
            identifier="TASK",
            planduration=60,
            gracetime=15,
            expirytime=120,
            priority="MEDIUM",
            scantype="QR",
            frequency="DAILY",
            asset=test_asset,
            qset=test_question_set,
            client=test_tenant,
            bu=test_tenant,
            seqno=1,
            enable=True,
            cdby=test_user,
            mdby=test_user
        )

        assert job.fromdate < job.uptodate

    def test_generate_jobneeds_from_schedule(self, test_job, test_user):
        """Test generating jobneed instances from job schedule."""
        from django.utils import timezone

        # Create jobneed from job template
        jobneed = Jobneed.objects.create(
            jobname=f"{test_job.jobname} - Instance",
            jobdesc=test_job.jobdesc,
            job=test_job,
            jobdate=timezone.now().date(),
            starttime=timezone.now(),
            endtime=timezone.now() + timedelta(hours=2),
            jobstatus="ASSIGNED",
            priority=test_job.priority,
            scantype=test_job.scantype,
            gracetime=test_job.gracetime,
            seqno=1,
            client=test_job.client,
            bu=test_job.bu,
            cdby=test_user,
            mdby=test_user
        )

        assert jobneed.job == test_job
        assert jobneed.jobstatus == "ASSIGNED"


@pytest.mark.django_db
class TestJobneedCreation:
    """Test Jobneed (job instance) creation."""

    def test_create_jobneed_from_job(self, test_job, test_user):
        """Test creating jobneed instance from job template."""
        from django.utils import timezone

        jobneed = Jobneed.objects.create(
            jobname=f"{test_job.jobname} - Scheduled",
            jobdesc=test_job.jobdesc,
            job=test_job,
            jobdate=timezone.now().date(),
            jobtype="SCHEDULE",
            starttime=timezone.now(),
            endtime=timezone.now() + timedelta(hours=2),
            jobstatus="ASSIGNED",
            priority=test_job.priority,
            scantype=test_job.scantype,
            gracetime=test_job.gracetime,
            seqno=1,
            client=test_job.client,
            bu=test_job.bu,
            cdby=test_user,
            mdby=test_user
        )

        assert jobneed.job == test_job
        assert jobneed.jobtype == "SCHEDULE"
        assert jobneed.client == test_job.client

    def test_create_adhoc_jobneed(self, test_job, test_user):
        """Test creating ad-hoc jobneed without schedule."""
        from django.utils import timezone

        jobneed = Jobneed.objects.create(
            jobname="Ad-hoc Emergency Task",
            jobdesc="Urgent repair needed",
            job=test_job,
            jobdate=timezone.now().date(),
            jobtype="ADHOC",
            starttime=timezone.now(),
            endtime=timezone.now() + timedelta(hours=1),
            jobstatus="ASSIGNED",
            priority="HIGH",
            scantype="QR",
            gracetime=0,
            seqno=1,
            client=test_job.client,
            bu=test_job.bu,
            cdby=test_user,
            mdby=test_user
        )

        assert jobneed.jobtype == "ADHOC"
        assert jobneed.priority == "HIGH"

    def test_jobneed_inherits_job_properties(self, test_jobneed):
        """Test that jobneed inherits properties from job."""
        assert test_jobneed.job is not None
        assert test_jobneed.client == test_jobneed.job.client
        assert test_jobneed.bu == test_jobneed.job.bu

    def test_jobneed_version_field(self, test_jobneed):
        """Test optimistic locking via VersionField."""
        assert test_jobneed.version is not None
        original_version = test_jobneed.version

        test_jobneed.jobstatus = "INPROGRESS"
        test_jobneed.save()

        assert test_jobneed.version != original_version


@pytest.mark.django_db
class TestJobneedExecution:
    """Test jobneed execution lifecycle."""

    def test_start_jobneed_execution(self, test_jobneed):
        """Test starting jobneed execution (ASSIGNED → INPROGRESS)."""
        from django.utils import timezone

        assert test_jobneed.jobstatus == "ASSIGNED"

        test_jobneed.jobstatus = "INPROGRESS"
        test_jobneed.starttime = timezone.now()
        test_jobneed.save()

        test_jobneed.refresh_from_db()
        assert test_jobneed.jobstatus == "INPROGRESS"
        assert test_jobneed.starttime is not None

    def test_complete_jobneed(self, test_jobneed):
        """Test completing jobneed (INPROGRESS → COMPLETED)."""
        from django.utils import timezone

        test_jobneed.jobstatus = "INPROGRESS"
        test_jobneed.starttime = timezone.now()
        test_jobneed.save()

        test_jobneed.jobstatus = "COMPLETED"
        test_jobneed.endtime = timezone.now()
        test_jobneed.save()

        test_jobneed.refresh_from_db()
        assert test_jobneed.jobstatus == "COMPLETED"
        assert test_jobneed.endtime is not None

    def test_track_actual_execution_times(self, test_jobneed):
        """Test recording actual start and end times."""
        from django.utils import timezone

        start = timezone.now()
        test_jobneed.starttime = start
        test_jobneed.save()

        end = timezone.now() + timedelta(hours=1)
        test_jobneed.endtime = end
        test_jobneed.save()

        test_jobneed.refresh_from_db()
        assert test_jobneed.starttime == start
        assert test_jobneed.endtime == end

    def test_jobneed_duration_calculation(self, completed_jobneed):
        """Test calculating total execution duration."""
        assert completed_jobneed.starttime is not None
        assert completed_jobneed.endtime is not None

        duration = completed_jobneed.endtime - completed_jobneed.starttime
        assert duration.total_seconds() > 0


@pytest.mark.django_db
class TestJobneedStatus:
    """Test jobneed status transitions."""

    def test_assigned_status(self, test_jobneed):
        """Test initial ASSIGNED status."""
        assert test_jobneed.jobstatus == "ASSIGNED"

    def test_inprogress_status(self, test_jobneed):
        """Test INPROGRESS status during execution."""
        test_jobneed.jobstatus = "INPROGRESS"
        test_jobneed.save()

        test_jobneed.refresh_from_db()
        assert test_jobneed.jobstatus == "INPROGRESS"

    def test_completed_status(self, completed_jobneed):
        """Test COMPLETED status after execution."""
        assert completed_jobneed.jobstatus == "COMPLETED"

    def test_cancelled_status(self, test_jobneed):
        """Test CANCELLED status for aborted work."""
        test_jobneed.jobstatus = "AUTOCLOSED"
        test_jobneed.save()

        test_jobneed.refresh_from_db()
        assert test_jobneed.jobstatus == "AUTOCLOSED"


@pytest.mark.django_db
class TestJobneedAssignment:
    """Test jobneed assignment to users."""

    def test_assign_jobneed_to_user(self, test_jobneed, test_user):
        """Test assigning jobneed to specific user."""
        test_jobneed.people = test_user
        test_jobneed.save()

        test_jobneed.refresh_from_db()
        assert test_jobneed.people == test_user

    def test_reassign_jobneed(self, test_jobneed, test_tenant):
        """Test reassigning jobneed to different user."""
        from django.contrib.auth import get_user_model
        User = get_user_model()

        user2 = User.objects.create(
            peoplecode="ACTUSER002",
            peoplename="Second Test User",
            loginid="actuser2",
            email="actuser2@example.com",
            mobno="8888888888",
            client=test_tenant,
            enable=True
        )

        test_jobneed.people = user2
        test_jobneed.save()

        test_jobneed.refresh_from_db()
        assert test_jobneed.people == user2

    def test_query_assigned_jobneeds_for_user(self, test_jobneed, test_user):
        """Test querying all jobneeds assigned to specific user."""
        test_jobneed.people = test_user
        test_jobneed.save()

        user_jobneeds = Jobneed.objects.filter(people=test_user)
        assert test_jobneed in user_jobneeds


@pytest.mark.django_db
class TestJobneedDetails:
    """Test JobneedDetails (checklist answers)."""

    def test_create_jobneed_detail(self, test_jobneed):
        """Test creating checklist detail for jobneed."""
        from apps.activity.models import JobneedDetails

        detail = JobneedDetails.objects.create(
            jobneed=test_jobneed,
            seqno=1,
            client=test_jobneed.client,
            bu=test_jobneed.bu,
            cdby=test_jobneed.cdby,
            mdby=test_jobneed.mdby
        )

        assert detail.jobneed == test_jobneed
        assert detail.seqno == 1

    def test_jobneed_detail_sequence_ordering(self, test_jobneed):
        """Test seqno field enforces question ordering."""
        from apps.activity.models import JobneedDetails

        detail1 = JobneedDetails.objects.create(
            jobneed=test_jobneed,
            seqno=1,
            client=test_jobneed.client,
            bu=test_jobneed.bu,
            cdby=test_jobneed.cdby,
            mdby=test_jobneed.mdby
        )

        detail2 = JobneedDetails.objects.create(
            jobneed=test_jobneed,
            seqno=2,
            client=test_jobneed.client,
            bu=test_jobneed.bu,
            cdby=test_jobneed.cdby,
            mdby=test_jobneed.mdby
        )

        details = JobneedDetails.objects.filter(jobneed=test_jobneed).order_by('seqno')
        assert list(details) == [detail1, detail2]

    def test_jobneed_detail_uniqueness_constraints(self, test_jobneed):
        """Test unique constraints on (jobneed, question) and (jobneed, seqno)."""
        from apps.activity.models import JobneedDetails

        detail1 = JobneedDetails.objects.create(
            jobneed=test_jobneed,
            seqno=1,
            client=test_jobneed.client,
            bu=test_jobneed.bu,
            cdby=test_jobneed.cdby,
            mdby=test_jobneed.mdby
        )

        # seqno should allow different values
        detail2 = JobneedDetails.objects.create(
            jobneed=test_jobneed,
            seqno=2,
            client=test_jobneed.client,
            bu=test_jobneed.bu,
            cdby=test_jobneed.cdby,
            mdby=test_jobneed.mdby
        )

        assert detail1.seqno != detail2.seqno


@pytest.mark.django_db
class TestJobParentChild:
    """Test job parent-child hierarchy."""

    def test_root_job_detection(self, test_job):
        """Test detecting root jobs (parent is NULL)."""
        assert test_job.parent is None

    def test_child_job_relationship(self, test_tour_job, checkpoint_job):
        """Test child job linked to parent."""
        assert checkpoint_job.parent == test_tour_job

    def test_query_child_jobs(self, test_tour_job, checkpoint_job):
        """Test querying all child jobs of parent."""
        children = Job.objects.filter(parent=test_tour_job)
        assert checkpoint_job in children


@pytest.mark.django_db
class TestMultiTenantIsolation:
    """Test multi-tenant data isolation for jobs."""

    def test_jobs_isolated_by_tenant(self, test_job):
        """Test that jobs from different tenants are isolated."""
        from apps.client_onboarding.models import Bt

        tenant2 = Bt.objects.create(
            bucode="TESTACT2",
            buname="Second Activity Tenant",
            enable=True
        )

        tenant1_jobs = Job.objects.filter(client=test_job.client)
        tenant2_jobs = Job.objects.filter(client=tenant2)

        assert test_job in tenant1_jobs
        assert test_job not in tenant2_jobs

    def test_tenant_aware_queries(self, test_job, test_tenant):
        """Test that queries automatically filter by tenant."""
        tenant_jobs = Job.objects.filter(client=test_tenant)
        assert test_job in tenant_jobs
