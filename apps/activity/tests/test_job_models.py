"""
Model tests for refactored job models.

Tests Job, Jobneed, JobneedDetails models and enums from Phase 2 refactoring.
"""
import pytest
from datetime import timedelta
from apps.activity.models import Job, Jobneed, JobneedDetails
from apps.activity.models.job.enums import (
    JobIdentifier,
    JobneedIdentifier,
    Priority,
    ScanType,
    Frequency,
    JobStatus,
    JobType,
    AnswerType,
)


@pytest.mark.django_db
class TestJobModel:
    """Test Job model structure and behavior."""

    def test_job_model_creation(self, test_job):
        """Test Job model can be created."""
        assert test_job.id is not None
        assert isinstance(test_job, Job)

    def test_job_required_fields(self, test_job):
        """Test Job has all required fields."""
        assert test_job.jobname is not None
        assert test_job.fromdate is not None
        assert test_job.uptodate is not None
        assert test_job.cron is not None

    def test_job_string_representation(self, test_job):
        """Test Job __str__ method."""
        assert str(test_job) == test_job.jobname

    def test_job_enable_field(self, test_job):
        """Test Job enable field."""
        assert test_job.enable is True

        test_job.enable = False
        test_job.save()

        test_job.refresh_from_db()
        assert test_job.enable is False

    def test_job_version_field(self, test_job):
        """Test Job version field for optimistic locking."""
        assert test_job.version is not None

        original_version = test_job.version
        test_job.jobname = "Updated Job Name"
        test_job.save()

        assert test_job.version != original_version

    def test_job_constraints(self, test_job):
        """Test Job model constraints."""
        assert test_job.gracetime >= 0
        assert test_job.planduration >= 0
        assert test_job.expirytime >= 0


@pytest.mark.django_db
class TestJobneedModel:
    """Test Jobneed model structure and behavior."""

    def test_jobneed_model_creation(self, test_jobneed):
        """Test Jobneed model can be created."""
        assert test_jobneed.id is not None
        assert isinstance(test_jobneed, Jobneed)

    def test_jobneed_uuid_field(self, test_jobneed):
        """Test Jobneed has UUID field."""
        assert test_jobneed.uuid is not None

    def test_jobneed_job_relationship(self, test_jobneed):
        """Test Jobneed foreign key to Job."""
        assert test_jobneed.job is not None
        assert isinstance(test_jobneed.job, Job)

    def test_jobneed_status_field(self, test_jobneed):
        """Test Jobneed status field."""
        assert test_jobneed.jobstatus in JobStatus.values

    def test_jobneed_version_field(self, test_jobneed):
        """Test Jobneed version field for optimistic locking."""
        assert test_jobneed.version is not None

        original_version = test_jobneed.version
        test_jobneed.jobstatus = "INPROGRESS"
        test_jobneed.save()

        assert test_jobneed.version != original_version

    def test_jobneed_gracetime_constraint(self, test_jobneed):
        """Test Jobneed gracetime constraint."""
        assert test_jobneed.gracetime >= 0


@pytest.mark.django_db
class TestJobneedDetailsModel:
    """Test JobneedDetails model structure."""

    def test_jobneed_details_creation(self, test_jobneed):
        """Test JobneedDetails model can be created."""
        detail = JobneedDetails.objects.create(
            jobneed=test_jobneed,
            seqno=1,
            client=test_jobneed.client,
            bu=test_jobneed.bu,
            cdby=test_jobneed.cdby,
            mdby=test_jobneed.mdby
        )

        assert detail.id is not None
        assert detail.jobneed == test_jobneed

    def test_jobneed_details_seqno(self, test_jobneed):
        """Test JobneedDetails seqno ordering."""
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

    def test_jobneed_details_jobneed_relationship(self, test_jobneed):
        """Test JobneedDetails foreign key to Jobneed."""
        detail = JobneedDetails.objects.create(
            jobneed=test_jobneed,
            seqno=1,
            client=test_jobneed.client,
            bu=test_jobneed.bu,
            cdby=test_jobneed.cdby,
            mdby=test_jobneed.mdby
        )

        assert detail.jobneed == test_jobneed
        assert isinstance(detail.jobneed, Jobneed)


@pytest.mark.django_db
class TestJobEnums:
    """Test Job-related enums."""

    def test_job_identifier_enum(self):
        """Test JobIdentifier enum values."""
        assert "TASK" in JobIdentifier.values
        assert "PPM" in JobIdentifier.values
        assert "INTERNALTOUR" in JobIdentifier.values

    def test_priority_enum(self):
        """Test Priority enum values."""
        assert "HIGH" in Priority.values
        assert "MEDIUM" in Priority.values
        assert "LOW" in Priority.values

    def test_scan_type_enum(self):
        """Test ScanType enum values."""
        assert "QR" in ScanType.values
        assert "NFC" in ScanType.values
        assert "NONE" in ScanType.values

    def test_frequency_enum(self):
        """Test Frequency enum values."""
        assert "DAILY" in Frequency.values
        assert "WEEKLY" in Frequency.values
        assert "MONTHLY" in Frequency.values


@pytest.mark.django_db
class TestJobneedEnums:
    """Test Jobneed-related enums."""

    def test_jobneed_identifier_enum(self):
        """Test JobneedIdentifier enum values."""
        assert "TASK" in JobneedIdentifier.values
        assert "PPM" in JobneedIdentifier.values
        assert "POSTING_ORDER" in JobneedIdentifier.values

    def test_job_status_enum(self):
        """Test JobStatus enum values."""
        assert "ASSIGNED" in JobStatus.values
        assert "INPROGRESS" in JobStatus.values
        assert "COMPLETED" in JobStatus.values

    def test_job_type_enum(self):
        """Test JobType enum values."""
        assert "SCHEDULE" in JobType.values
        assert "ADHOC" in JobType.values

    def test_answer_type_enum(self):
        """Test AnswerType enum values."""
        assert "CHECKBOX" in AnswerType.values
        assert "NUMERIC" in AnswerType.values
        assert "DATE" in AnswerType.values


@pytest.mark.django_db
class TestJobRelationships:
    """Test relationships between Job models."""

    def test_job_to_jobneed_relationship(self, test_job, test_user):
        """Test one-to-many relationship from Job to Jobneed."""
        from django.utils import timezone

        jobneed1 = Jobneed.objects.create(
            jobname=f"{test_job.jobname} - 1",
            jobdesc=test_job.jobdesc,
            job=test_job,
            jobdate=timezone.now().date(),
            starttime=timezone.now(),
            endtime=timezone.now() + timedelta(hours=1),
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

        jobneed2 = Jobneed.objects.create(
            jobname=f"{test_job.jobname} - 2",
            jobdesc=test_job.jobdesc,
            job=test_job,
            jobdate=timezone.now().date(),
            starttime=timezone.now(),
            endtime=timezone.now() + timedelta(hours=1),
            jobstatus="ASSIGNED",
            priority=test_job.priority,
            scantype=test_job.scantype,
            gracetime=test_job.gracetime,
            seqno=2,
            client=test_job.client,
            bu=test_job.bu,
            cdby=test_user,
            mdby=test_user
        )

        jobneeds = Jobneed.objects.filter(job=test_job)
        assert jobneeds.count() == 2
        assert jobneed1 in jobneeds
        assert jobneed2 in jobneeds

    def test_jobneed_to_jobneed_details_relationship(self, test_jobneed):
        """Test one-to-many relationship from Jobneed to JobneedDetails."""
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

        details = JobneedDetails.objects.filter(jobneed=test_jobneed)
        assert details.count() == 2
        assert detail1 in details
        assert detail2 in details

    def test_job_parent_child_relationship(self, test_tour_job, checkpoint_job):
        """Test parent-child relationship for Jobs."""
        assert checkpoint_job.parent == test_tour_job
        assert test_tour_job.parent is None

        # Query children
        children = Job.objects.filter(parent=test_tour_job)
        assert checkpoint_job in children


@pytest.mark.django_db
class TestModelDefaults:
    """Test model default values."""

    def test_job_other_info_defaults(self, test_job):
        """Test Job other_info JSONField defaults."""
        assert "tour_frequency" in test_job.other_info
        assert "is_randomized" in test_job.other_info
        assert "breaktime" in test_job.other_info

    def test_job_enable_default(self, test_job):
        """Test Job enable default value."""
        assert test_job.enable is True

    def test_jobneed_other_info_defaults(self, test_jobneed):
        """Test Jobneed other_info JSONField defaults."""
        assert isinstance(test_jobneed.other_info, dict)
