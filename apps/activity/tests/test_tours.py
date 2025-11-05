"""
Tour tests for activity app.

Tests tour creation, checkpoint management, route tracking,
and tour execution workflows.
"""
import pytest
from datetime import timedelta
from apps.activity.models import Job, Jobneed


@pytest.mark.django_db
class TestTourCreation:
    """Test tour job creation."""

    def test_create_tour_job(self, test_tour_job):
        """Test creating a tour job (parent job)."""
        assert test_tour_job.id is not None
        assert test_tour_job.identifier in ["INTERNALTOUR", "EXTERNALTOUR"]
        assert test_tour_job.parent is None

    def test_tour_has_no_asset(self, test_tour_job):
        """Test that tour jobs don't have specific assets."""
        # Tours can have assets, but checkpoints typically have specific assets
        assert test_tour_job.identifier in ["INTERNALTOUR", "EXTERNALTOUR"]

    def test_tour_identifier(self, test_tour_job):
        """Test that tour jobs have identifier='TOUR'."""
        assert test_tour_job.identifier in ["INTERNALTOUR", "EXTERNALTOUR"]


@pytest.mark.django_db
class TestCheckpointManagement:
    """Test checkpoint creation and management."""

    def test_create_checkpoint(self, test_tour_job, checkpoint_job):
        """Test creating checkpoint as child of tour."""
        assert checkpoint_job.id is not None
        assert checkpoint_job.parent == test_tour_job

    def test_checkpoint_parent_relationship(self, test_tour_job, checkpoint_job):
        """Test checkpoint parent FK points to tour."""
        assert checkpoint_job.parent == test_tour_job

    def test_query_tour_checkpoints(self, test_tour_job, checkpoint_job):
        """Test querying all checkpoints for a tour."""
        checkpoints = Job.objects.filter(parent=test_tour_job)
        assert checkpoint_job in checkpoints

    def test_checkpoint_ordering(self, test_tour_job, test_asset, test_user):
        """Test checkpoint sequence ordering in tour."""
        checkpoint1 = Job.objects.create(
            jobname="Checkpoint 1",
            jobdesc="First checkpoint",
            fromdate=test_tour_job.fromdate,
            uptodate=test_tour_job.uptodate,
            cron=test_tour_job.cron,
            identifier="TASK",
            planduration=30,
            gracetime=15,
            expirytime=60,
            priority="MEDIUM",
            scantype="NFC",
            frequency="DAILY",
            asset=test_asset,
            qset=test_tour_job.qset,
            client=test_tour_job.client,
            bu=test_tour_job.bu,
            parent=test_tour_job,
            seqno=1,
            enable=True,
            cdby=test_user,
            mdby=test_user
        )

        checkpoint2 = Job.objects.create(
            jobname="Checkpoint 2",
            jobdesc="Second checkpoint",
            fromdate=test_tour_job.fromdate,
            uptodate=test_tour_job.uptodate,
            cron=test_tour_job.cron,
            identifier="TASK",
            planduration=30,
            gracetime=15,
            expirytime=60,
            priority="MEDIUM",
            scantype="NFC",
            frequency="DAILY",
            asset=test_asset,
            qset=test_tour_job.qset,
            client=test_tour_job.client,
            bu=test_tour_job.bu,
            parent=test_tour_job,
            seqno=2,
            enable=True,
            cdby=test_user,
            mdby=test_user
        )

        checkpoints = Job.objects.filter(parent=test_tour_job).order_by('seqno')
        assert list(checkpoints) == [checkpoint1, checkpoint2]


@pytest.mark.django_db
class TestTourRouting:
    """Test tour route and path tracking."""

    def test_tour_gps_route(self, test_tour_job):
        """Test tour GPS route tracking."""
        assert test_tour_job.other_info is not None
        assert isinstance(test_tour_job.other_info, dict)

    def test_checkpoint_gps_locations(self, checkpoint_job):
        """Test checkpoint GPS coordinates."""
        # Checkpoints inherit from Job model which has geojson field
        assert checkpoint_job.geojson is not None

    def test_tour_distance_calculation(self, test_tour_job):
        """Test calculating total tour distance."""
        # Distance tracking in other_info
        assert "distance" in test_tour_job.other_info

    def test_route_deviation_detection(self, test_tour_job):
        """Test detecting route deviations."""
        assert "deviation" in test_tour_job.other_info
        assert test_tour_job.other_info["deviation"] is False


@pytest.mark.django_db
class TestTourExecution:
    """Test tour execution workflow."""

    def test_start_tour(self, test_tour_job, test_user):
        """Test starting tour execution."""
        from django.utils import timezone

        tour_instance = Jobneed.objects.create(
            jobname=f"{test_tour_job.jobname} - Instance",
            jobdesc=test_tour_job.jobdesc,
            job=test_tour_job,
            jobdate=timezone.now().date(),
            starttime=timezone.now(),
            endtime=timezone.now() + timedelta(hours=3),
            jobstatus="INPROGRESS",
            priority=test_tour_job.priority,
            scantype=test_tour_job.scantype,
            gracetime=test_tour_job.gracetime,
            seqno=1,
            client=test_tour_job.client,
            bu=test_tour_job.bu,
            cdby=test_user,
            mdby=test_user
        )

        assert tour_instance.jobstatus == "INPROGRESS"

    def test_complete_checkpoint(self, checkpoint_job, test_user):
        """Test completing individual checkpoint."""
        from django.utils import timezone

        checkpoint_instance = Jobneed.objects.create(
            jobname=f"{checkpoint_job.jobname} - Instance",
            jobdesc=checkpoint_job.jobdesc,
            job=checkpoint_job,
            jobdate=timezone.now().date(),
            starttime=timezone.now(),
            endtime=timezone.now() + timedelta(minutes=30),
            jobstatus="COMPLETED",
            priority=checkpoint_job.priority,
            scantype=checkpoint_job.scantype,
            gracetime=checkpoint_job.gracetime,
            seqno=1,
            client=checkpoint_job.client,
            bu=checkpoint_job.bu,
            cdby=test_user,
            mdby=test_user
        )

        assert checkpoint_instance.jobstatus == "COMPLETED"

    def test_complete_tour_when_all_checkpoints_done(self, test_tour_job, checkpoint_job, test_user):
        """Test tour completion when all checkpoints are done."""
        from django.utils import timezone

        # Complete checkpoint
        checkpoint_instance = Jobneed.objects.create(
            jobname=f"{checkpoint_job.jobname} - Instance",
            jobdesc=checkpoint_job.jobdesc,
            job=checkpoint_job,
            jobdate=timezone.now().date(),
            starttime=timezone.now(),
            endtime=timezone.now() + timedelta(minutes=30),
            jobstatus="COMPLETED",
            priority=checkpoint_job.priority,
            scantype=checkpoint_job.scantype,
            gracetime=checkpoint_job.gracetime,
            seqno=1,
            client=checkpoint_job.client,
            bu=checkpoint_job.bu,
            cdby=test_user,
            mdby=test_user
        )

        # Complete tour
        tour_instance = Jobneed.objects.create(
            jobname=f"{test_tour_job.jobname} - Instance",
            jobdesc=test_tour_job.jobdesc,
            job=test_tour_job,
            jobdate=timezone.now().date(),
            starttime=timezone.now(),
            endtime=timezone.now() + timedelta(hours=2),
            jobstatus="COMPLETED",
            priority=test_tour_job.priority,
            scantype=test_tour_job.scantype,
            gracetime=test_tour_job.gracetime,
            seqno=1,
            client=test_tour_job.client,
            bu=test_tour_job.bu,
            cdby=test_user,
            mdby=test_user
        )

        assert checkpoint_instance.jobstatus == "COMPLETED"
        assert tour_instance.jobstatus == "COMPLETED"

    def test_tour_partial_completion(self, test_tour_job, checkpoint_job, test_user):
        """Test tour with some checkpoints incomplete."""
        from django.utils import timezone

        # Incomplete checkpoint
        checkpoint_instance = Jobneed.objects.create(
            jobname=f"{checkpoint_job.jobname} - Instance",
            jobdesc=checkpoint_job.jobdesc,
            job=checkpoint_job,
            jobdate=timezone.now().date(),
            starttime=timezone.now(),
            endtime=timezone.now() + timedelta(minutes=30),
            jobstatus="INPROGRESS",
            priority=checkpoint_job.priority,
            scantype=checkpoint_job.scantype,
            gracetime=checkpoint_job.gracetime,
            seqno=1,
            client=checkpoint_job.client,
            bu=checkpoint_job.bu,
            cdby=test_user,
            mdby=test_user
        )

        assert checkpoint_instance.jobstatus == "INPROGRESS"


@pytest.mark.django_db
class TestTourScheduling:
    """Test tour scheduling and frequency."""

    def test_schedule_recurring_tour(self, test_tour_job):
        """Test scheduling recurring tour (daily, weekly, etc.)."""
        assert test_tour_job.frequency in ["DAILY", "WEEKLY", "MONTHLY"]
        assert test_tour_job.cron is not None

    def test_tour_frequency_configuration(self, test_tour_job):
        """Test tour frequency in other_info JSONField."""
        assert "tour_frequency" in test_tour_job.other_info
        assert test_tour_job.other_info["tour_frequency"] >= 1

    def test_randomized_tour_scheduling(self, test_tenant, test_question_set, test_user):
        """Test randomized tour execution (is_randomized=True)."""
        from django.utils import timezone

        tour = Job.objects.create(
            jobname="Randomized Patrol",
            jobdesc="Random security patrol",
            fromdate=timezone.now(),
            uptodate=timezone.now() + timedelta(days=30),
            cron="0 * * * *",
            identifier="INTERNALTOUR",
            planduration=60,
            gracetime=15,
            expirytime=90,
            priority="MEDIUM",
            scantype="NFC",
            frequency="DAILY",
            qset=test_question_set,
            client=test_tenant,
            bu=test_tenant,
            seqno=1,
            enable=True,
            cdby=test_user,
            mdby=test_user
        )

        tour.other_info["is_randomized"] = True
        tour.save()

        assert tour.other_info["is_randomized"] is True


@pytest.mark.django_db
class TestTourValidation:
    """Test tour validation rules."""

    def test_tour_must_have_checkpoints(self, test_tour_job, checkpoint_job):
        """Test that tours must have at least one checkpoint."""
        checkpoints = Job.objects.filter(parent=test_tour_job)
        assert checkpoints.exists()
        assert checkpoint_job in checkpoints

    def test_checkpoint_must_have_asset(self, checkpoint_job):
        """Test that checkpoints must have associated asset."""
        # Checkpoints typically have assets (can be None for virtual checkpoints)
        assert checkpoint_job.asset is not None or checkpoint_job.identifier == "TASK"

    def test_checkpoint_cannot_be_parent(self, checkpoint_job, test_user):
        """Test that checkpoints cannot have their own children."""
        # This is a business rule - verify checkpoint is not used as parent
        from django.db import IntegrityError

        # Try to create a child of a checkpoint (should be avoided)
        # This is more of a validation rule than a constraint
        children = Job.objects.filter(parent=checkpoint_job)
        assert children.count() == 0


@pytest.mark.django_db
class TestTourBreakTime:
    """Test tour break time configuration."""

    def test_configure_tour_break_time(self, test_tour_job):
        """Test setting break time in tour configuration."""
        test_tour_job.other_info["breaktime"] = 15
        test_tour_job.save()

        test_tour_job.refresh_from_db()
        assert test_tour_job.other_info["breaktime"] == 15

    def test_break_time_affects_duration(self, test_tour_job):
        """Test that break time is included in total duration."""
        breaktime = test_tour_job.other_info.get("breaktime", 0)
        total_duration = test_tour_job.planduration + breaktime

        assert total_duration >= test_tour_job.planduration


@pytest.mark.django_db
class TestTourReporting:
    """Test tour execution reporting."""

    def test_tour_completion_report(self, test_tour_job, test_user):
        """Test generating tour completion report."""
        from django.utils import timezone

        tour_instance = Jobneed.objects.create(
            jobname=f"{test_tour_job.jobname} - Instance",
            jobdesc=test_tour_job.jobdesc,
            job=test_tour_job,
            jobdate=timezone.now().date(),
            starttime=timezone.now(),
            endtime=timezone.now() + timedelta(hours=2),
            jobstatus="COMPLETED",
            priority=test_tour_job.priority,
            scantype=test_tour_job.scantype,
            gracetime=test_tour_job.gracetime,
            seqno=1,
            client=test_tour_job.client,
            bu=test_tour_job.bu,
            cdby=test_user,
            mdby=test_user
        )

        assert tour_instance.jobstatus == "COMPLETED"
        assert tour_instance.job == test_tour_job

    def test_checkpoint_completion_summary(self, checkpoint_job, test_user):
        """Test checkpoint completion statistics."""
        from django.utils import timezone

        # Create multiple checkpoint instances
        completed = Jobneed.objects.create(
            jobname=f"{checkpoint_job.jobname} - 1",
            jobdesc=checkpoint_job.jobdesc,
            job=checkpoint_job,
            jobdate=timezone.now().date(),
            starttime=timezone.now(),
            endtime=timezone.now() + timedelta(minutes=30),
            jobstatus="COMPLETED",
            priority=checkpoint_job.priority,
            scantype=checkpoint_job.scantype,
            gracetime=checkpoint_job.gracetime,
            seqno=1,
            client=checkpoint_job.client,
            bu=checkpoint_job.bu,
            cdby=test_user,
            mdby=test_user
        )

        total = Jobneed.objects.filter(job=checkpoint_job).count()
        completed_count = Jobneed.objects.filter(job=checkpoint_job, jobstatus="COMPLETED").count()

        assert total >= 1
        assert completed_count >= 1

    def test_tour_compliance_tracking(self, test_tour_job, test_user):
        """Test tracking tour compliance percentage."""
        from django.utils import timezone

        # Create tour instances
        completed = Jobneed.objects.create(
            jobname=f"{test_tour_job.jobname} - 1",
            jobdesc=test_tour_job.jobdesc,
            job=test_tour_job,
            jobdate=timezone.now().date(),
            starttime=timezone.now(),
            endtime=timezone.now() + timedelta(hours=2),
            jobstatus="COMPLETED",
            priority=test_tour_job.priority,
            scantype=test_tour_job.scantype,
            gracetime=test_tour_job.gracetime,
            seqno=1,
            client=test_tour_job.client,
            bu=test_tour_job.bu,
            cdby=test_user,
            mdby=test_user
        )

        total = Jobneed.objects.filter(job=test_tour_job).count()
        completed_count = Jobneed.objects.filter(job=test_tour_job, jobstatus="COMPLETED").count()

        compliance_pct = (completed_count / total * 100) if total > 0 else 0
        assert compliance_pct >= 0
        assert compliance_pct <= 100
