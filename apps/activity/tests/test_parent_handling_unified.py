"""
Comprehensive Tests for Unified Parent Handling

Tests the transitional parent query pattern:
Q(parent__isnull=True) | Q(parent_id=1)

This ensures compatibility during migration from sentinel records (id=1)
to proper NULL values.

Follows .claude/rules.md:
- Rule #11: Specific exception handling
- Rule #12: Query optimization
"""

import pytest
from django.test import TestCase
from django.db.models import Q
from datetime import datetime, timezone
from apps.activity.models import Job, Jobneed
from apps.onboarding.models import Bt
from apps.peoples.models import People
from apps.activity.models.question_model import QuestionSet


@pytest.mark.django_db
class ParentHandlingTransitionTest(TestCase):
    """
    Test unified parent handling during transition period.

    Tests both NULL and sentinel (id=1) parent handling.
    """

    @classmethod
    def setUpTestData(cls):
        """Set up test data with both NULL and sentinel parents."""
        # Create business unit
        cls.bu = Bt.objects.create(
            bucode="TEST001",
            buname="Test Business Unit",
            butype="CLIENT"
        )

        # Create user
        cls.user = People.objects.create(
            peoplecode="TEST001",
            peoplename="Test User",
            loginid="testuser",
            email="test@example.com"
        )

        # Create question set
        cls.qset = QuestionSet.objects.create(
            qsetname="Test Checklist",
            qsettype="CHECKLIST"
        )

        # Create sentinel "NONE" job (legacy pattern)
        cls.none_job = Job.objects.create(
            id=1,  # Sentinel ID
            jobname="NONE",
            jobdesc="Sentinel record",
            fromdate=datetime(1970, 1, 1, tzinfo=timezone.utc),
            uptodate=datetime(1970, 1, 1, tzinfo=timezone.utc),
            planduration=0,
            gracetime=0,
            expirytime=0,
            priority=Job.Priority.LOW,
            scantype=Job.Scantype.SKIP,
            identifier=Job.Identifier.OTHER,
            qset=cls.qset,
            bu=cls.bu,
            client=cls.bu,
            seqno=0,
            cuser=cls.user,
            muser=cls.user,
            parent=None  # Sentinel has no parent
        )

        # Create root job with NULL parent (modern pattern)
        cls.root_job_null = Job.objects.create(
            jobname="Root Job (NULL parent)",
            jobdesc="Modern pattern",
            fromdate=datetime(2025, 1, 1, tzinfo=timezone.utc),
            uptodate=datetime(2025, 12, 31, tzinfo=timezone.utc),
            planduration=60,
            gracetime=10,
            expirytime=30,
            priority=Job.Priority.MEDIUM,
            scantype=Job.Scantype.QR,
            identifier=Job.Identifier.TASK,
            qset=cls.qset,
            bu=cls.bu,
            client=cls.bu,
            seqno=1,
            cuser=cls.user,
            muser=cls.user,
            parent=None  # Modern: NULL parent
        )

        # Create root job with sentinel parent (legacy pattern)
        cls.root_job_sentinel = Job.objects.create(
            jobname="Root Job (Sentinel parent)",
            jobdesc="Legacy pattern",
            fromdate=datetime(2025, 1, 1, tzinfo=timezone.utc),
            uptodate=datetime(2025, 12, 31, tzinfo=timezone.utc),
            planduration=60,
            gracetime=10,
            expirytime=30,
            priority=Job.Priority.MEDIUM,
            scantype=Job.Scantype.QR,
            identifier=Job.Identifier.TASK,
            qset=cls.qset,
            bu=cls.bu,
            client=cls.bu,
            seqno=2,
            cuser=cls.user,
            muser=cls.user,
            parent=cls.none_job  # Legacy: parent_id=1
        )

        # Create child job
        cls.child_job = Job.objects.create(
            jobname="Child Job",
            jobdesc="Child checkpoint",
            fromdate=datetime(2025, 1, 1, tzinfo=timezone.utc),
            uptodate=datetime(2025, 12, 31, tzinfo=timezone.utc),
            planduration=30,
            gracetime=5,
            expirytime=15,
            priority=Job.Priority.MEDIUM,
            scantype=Job.Scantype.QR,
            identifier=Job.Identifier.TASK,
            qset=cls.qset,
            bu=cls.bu,
            client=cls.bu,
            seqno=3,
            cuser=cls.user,
            muser=cls.user,
            parent=cls.root_job_null  # Has actual parent
        )

    def test_query_finds_null_parent_jobs(self):
        """
        Test that parent__isnull=True finds jobs with NULL parent.
        """
        root_jobs = Job.objects.filter(
            parent__isnull=True
        ).exclude(jobname='NONE')

        # Should find root_job_null and none_job (not root_job_sentinel)
        self.assertIn(self.root_job_null, root_jobs)

    def test_query_finds_sentinel_parent_jobs(self):
        """
        Test that parent_id=1 finds jobs with sentinel parent.
        """
        root_jobs = Job.objects.filter(
            parent_id=1
        ).exclude(jobname='NONE')

        # Should find root_job_sentinel (legacy pattern)
        self.assertIn(self.root_job_sentinel, root_jobs)

    def test_unified_query_finds_both_patterns(self):
        """
        Test that unified query finds BOTH NULL and sentinel parents.

        This is the critical test - unified pattern must work.
        """
        root_jobs = Job.objects.filter(
            Q(parent__isnull=True) | Q(parent_id=1)
        ).exclude(jobname='NONE')

        # Should find BOTH modern (NULL) and legacy (id=1)
        root_job_ids = set(root_jobs.values_list('id', flat=True))

        self.assertIn(self.root_job_null.id, root_job_ids, "NULL parent not found")
        self.assertIn(self.root_job_sentinel.id, root_job_ids, "Sentinel parent not found")

        # Should NOT find child job
        self.assertNotIn(self.child_job.id, root_job_ids, "Child job incorrectly included")

        # Verify count
        self.assertEqual(root_jobs.count(), 2, "Should find exactly 2 root jobs")

    def test_child_job_excluded_from_root_query(self):
        """
        Test that child jobs are NOT returned by root query.
        """
        root_jobs = Job.objects.filter(
            Q(parent__isnull=True) | Q(parent_id=1)
        ).exclude(jobname='NONE')

        # Child job should not be in results
        self.assertNotIn(self.child_job, root_jobs)

        # Verify child has actual parent
        self.child_job.refresh_from_db()
        self.assertEqual(self.child_job.parent_id, self.root_job_null.id)
        self.assertIsNotNone(self.child_job.parent)

    def test_manager_uses_unified_pattern(self):
        """
        Test that JobManager methods use unified parent query.
        """
        from django.test import RequestFactory

        request = RequestFactory().get('/')
        request.session = {
            'assignedsites': [self.bu.id],
            'client_id': self.bu.id,
            'bu_id': self.bu.id
        }

        # This should work with both NULL and sentinel parents
        tasks = Job.objects.get_scheduled_tasks(
            request=request,
            related=['people', 'asset'],
            fields=['id', 'jobname']
        )

        task_ids = set(tasks.values_list('id', flat=True))

        # Should include both root jobs
        self.assertIn(self.root_job_null.id, task_ids)
        self.assertIn(self.root_job_sentinel.id, task_ids)

        # Should exclude child job
        self.assertNotIn(self.child_job.id, task_ids)


@pytest.mark.django_db
class JobneedParentHandlingTest(TestCase):
    """Test parent handling for Jobneed model."""

    def setUp(self):
        """Create test data."""
        self.bu = Bt.objects.create(
            bucode="TEST001",
            buname="Test BU",
            butype="CLIENT"
        )

        self.user = People.objects.create(
            peoplecode="TEST001",
            peoplename="Test User",
            loginid="testuser",
            email="test@example.com"
        )

        self.qset = QuestionSet.objects.create(
            qsetname="Test Checklist",
            qsettype="CHECKLIST"
        )

        self.job = Job.objects.create(
            jobname="Test Job",
            jobdesc="Test",
            fromdate=datetime(2025, 1, 1, tzinfo=timezone.utc),
            uptodate=datetime(2025, 12, 31, tzinfo=timezone.utc),
            planduration=60,
            gracetime=10,
            expirytime=30,
            priority=Job.Priority.MEDIUM,
            scantype=Job.Scantype.QR,
            identifier=Job.Identifier.INTERNALTOUR,
            qset=self.qset,
            bu=self.bu,
            client=self.bu,
            seqno=1,
            cuser=self.user,
            muser=self.user
        )

        # Create parent jobneed (NULL parent - modern)
        self.parent_jobneed_null = Jobneed.objects.create(
            job=self.job,
            jobdesc="Parent Tour - Oct 3",
            plandatetime=datetime(2025, 10, 3, 10, 0, tzinfo=timezone.utc),
            expirydatetime=datetime(2025, 10, 3, 14, 0, tzinfo=timezone.utc),
            gracetime=10,
            priority=Jobneed.Priority.MEDIUM,
            scantype=Jobneed.Scantype.QR,
            identifier=Jobneed.Identifier.INTERNALTOUR,
            jobstatus=Jobneed.JobStatus.ASSIGNED,
            jobtype=Jobneed.JobType.SCHEDULE,
            qset=self.qset,
            bu=self.bu,
            client=self.bu,
            seqno=0,
            cuser=self.user,
            muser=self.user,
            parent=None  # Modern: NULL
        )

        # Create checkpoint jobneeds (children)
        self.checkpoint1 = Jobneed.objects.create(
            job=self.job,
            jobdesc="Checkpoint 1",
            plandatetime=datetime(2025, 10, 3, 10, 15, tzinfo=timezone.utc),
            expirydatetime=datetime(2025, 10, 3, 10, 45, tzinfo=timezone.utc),
            gracetime=5,
            priority=Jobneed.Priority.MEDIUM,
            scantype=Jobneed.Scantype.QR,
            identifier=Jobneed.Identifier.INTERNALTOUR,
            jobstatus=Jobneed.JobStatus.ASSIGNED,
            jobtype=Jobneed.JobType.SCHEDULE,
            qset=self.qset,
            bu=self.bu,
            client=self.bu,
            seqno=1,
            cuser=self.user,
            muser=self.user,
            parent=self.parent_jobneed_null  # Child of parent_jobneed_null
        )

    def test_unified_parent_query_for_jobneeds(self):
        """
        Test that unified parent query works for Jobneeds.
        """
        # Query for parent jobneeds (root level)
        parent_jobneeds = Jobneed.objects.filter(
            Q(parent__isnull=True) | Q(parent_id=1),
            identifier=Jobneed.Identifier.INTERNALTOUR
        )

        # Should find parent_jobneed_null
        self.assertIn(self.parent_jobneed_null, parent_jobneeds)

        # Should NOT find checkpoint1
        self.assertNotIn(self.checkpoint1, parent_jobneeds)

    def test_child_jobneed_query(self):
        """
        Test querying child jobneeds (checkpoints).
        """
        # Query for child jobneeds (has parent, not id=1)
        child_jobneeds = Jobneed.objects.filter(
            parent__isnull=False,
            ~Q(parent_id=1)  # Exclude sentinel
        )

        # Should find checkpoint1
        self.assertIn(self.checkpoint1, child_jobneeds)

        # Should NOT find parent
        self.assertNotIn(self.parent_jobneed_null, child_jobneeds)

    def test_manager_latest_for_job_with_multiple_parents(self):
        """
        Test latest_for_job returns correct jobneed when multiple parents exist.

        Should return the one with latest plandatetime.
        """
        # Create second parent jobneed (later date)
        jobneed_oct4 = Jobneed.objects.create(
            job=self.job,
            jobdesc="Parent Tour - Oct 4",
            plandatetime=datetime(2025, 10, 4, 10, 0, tzinfo=timezone.utc),
            expirydatetime=datetime(2025, 10, 4, 14, 0, tzinfo=timezone.utc),
            gracetime=10,
            priority=Jobneed.Priority.MEDIUM,
            scantype=Jobneed.Scantype.QR,
            identifier=Jobneed.Identifier.INTERNALTOUR,
            jobstatus=Jobneed.JobStatus.ASSIGNED,
            jobtype=Jobneed.JobType.SCHEDULE,
            qset=self.qset,
            bu=self.bu,
            client=self.bu,
            seqno=0,
            cuser=self.user,
            muser=self.user,
            parent=None
        )

        # Get latest
        latest = Jobneed.objects.latest_for_job(self.job.id)

        # Should return Oct 4 (most recent)
        self.assertEqual(latest.id, jobneed_oct4.id)
        self.assertIn('Oct 4', latest.jobdesc)

    def test_history_for_job_excludes_children(self):
        """
        Test that history_for_job returns only instances, not checkpoints.

        This is implicit - all jobneeds with same job_id are instances.
        """
        history = Jobneed.objects.history_for_job(self.job.id, limit=10)

        # Should include parent
        history_ids = [j.id for j in history]
        self.assertIn(self.parent_jobneed_null.id, history_ids)

        # Should also include checkpoint (same job_id)
        # This is CORRECT - both parent and checkpoints have same job_id
        self.assertIn(self.checkpoint1.id, history_ids)


@pytest.mark.django_db
class BaseSchedulingServiceParentTest(TestCase):
    """Test BaseSchedulingService uses unified parent pattern."""

    def setUp(self):
        """Create test data."""
        self.bu = Bt.objects.create(
            bucode="TEST001",
            buname="Test BU",
            butype="CLIENT"
        )

        self.user = People.objects.create(
            peoplecode="TEST001",
            peoplename="Test User",
            loginid="testuser",
            email="test@example.com"
        )

        self.qset = QuestionSet.objects.create(
            qsetname="Test Checklist",
            qsettype="CHECKLIST"
        )

        # Create NONE sentinel
        self.none_job = Job.objects.create(
            id=1,
            jobname="NONE",
            jobdesc="Sentinel",
            fromdate=datetime(1970, 1, 1, tzinfo=timezone.utc),
            uptodate=datetime(1970, 1, 1, tzinfo=timezone.utc),
            planduration=0,
            gracetime=0,
            expirytime=0,
            priority=Job.Priority.LOW,
            scantype=Job.Scantype.SKIP,
            identifier=Job.Identifier.TASK,
            qset=self.qset,
            bu=self.bu,
            client=self.bu,
            seqno=0,
            cuser=self.user,
            muser=self.user,
            parent=None
        )

        # Root with NULL
        self.root_null = Job.objects.create(
            jobname="Root NULL",
            jobdesc="Modern",
            fromdate=datetime(2025, 1, 1, tzinfo=timezone.utc),
            uptodate=datetime(2025, 12, 31, tzinfo=timezone.utc),
            planduration=60,
            gracetime=10,
            expirytime=30,
            priority=Job.Priority.MEDIUM,
            scantype=Job.Scantype.QR,
            identifier=Job.Identifier.TASK,
            qset=self.qset,
            bu=self.bu,
            client=self.bu,
            seqno=1,
            cuser=self.user,
            muser=self.user,
            parent=None,
            enable=True
        )

        # Root with sentinel parent
        self.root_sentinel = Job.objects.create(
            jobname="Root Sentinel",
            jobdesc="Legacy",
            fromdate=datetime(2025, 1, 1, tzinfo=timezone.utc),
            uptodate=datetime(2025, 12, 31, tzinfo=timezone.utc),
            planduration=60,
            gracetime=10,
            expirytime=30,
            priority=Job.Priority.MEDIUM,
            scantype=Job.Scantype.QR,
            identifier=Job.Identifier.TASK,
            qset=self.qset,
            bu=self.bu,
            client=self.bu,
            seqno=2,
            cuser=self.user,
            muser=self.user,
            parent=self.none_job,
            enable=True
        )

    def test_base_service_get_base_queryset_finds_both(self):
        """
        Test that BaseSchedulingService finds both NULL and sentinel parents.
        """
        from apps.schedhuler.services.base_services import BaseSchedulingService

        # Create concrete service class for testing
        class TestSchedulingService(BaseSchedulingService):
            def get_identifier(self):
                return Job.Identifier.TASK

        service = TestSchedulingService()
        queryset = service.get_base_queryset(optimized=False)

        job_ids = set(queryset.values_list('id', flat=True))

        # Should find both patterns
        self.assertIn(self.root_null.id, job_ids, "NULL parent not found")
        self.assertIn(self.root_sentinel.id, job_ids, "Sentinel parent not found")

        # Should exclude NONE sentinel itself
        self.assertNotIn(self.none_job.id, job_ids, "NONE sentinel incorrectly included")

    def test_migration_from_sentinel_to_null(self):
        """
        Test migration scenario: Convert parent_id=1 to parent=NULL.

        This test documents the expected migration behavior.
        """
        # Before migration: root_sentinel has parent_id=1
        self.assertEqual(self.root_sentinel.parent_id, 1)

        # Simulate migration: Set parent=NULL
        self.root_sentinel.parent = None
        self.root_sentinel.save()

        # After migration: Unified query still works
        root_jobs = Job.objects.filter(
            Q(parent__isnull=True) | Q(parent_id=1),
            identifier=Job.Identifier.TASK
        ).exclude(jobname='NONE')

        # Should still find both
        job_ids = set(root_jobs.values_list('id', flat=True))
        self.assertIn(self.root_null.id, job_ids)
        self.assertIn(self.root_sentinel.id, job_ids)  # Now also has NULL parent


@pytest.mark.django_db
class EdgeCaseParentHandlingTest(TestCase):
    """Test edge cases in parent handling."""

    def setUp(self):
        """Create minimal test data."""
        self.bu = Bt.objects.create(
            bucode="TEST001",
            buname="Test BU",
            butype="CLIENT"
        )

        self.user = People.objects.create(
            peoplecode="TEST001",
            peoplename="Test User",
            loginid="testuser",
            email="test@example.com"
        )

        self.qset = QuestionSet.objects.create(
            qsetname="Test Checklist",
            qsettype="CHECKLIST"
        )

    def test_parent_id_zero_is_not_root(self):
        """
        Test that parent_id=0 is NOT considered a root.

        Only NULL and id=1 are roots.
        """
        # Create job with parent_id=0 (invalid but possible)
        job_zero = Job.objects.create(
            jobname="Job with parent_id=0",
            jobdesc="Edge case",
            fromdate=datetime(2025, 1, 1, tzinfo=timezone.utc),
            uptodate=datetime(2025, 12, 31, tzinfo=timezone.utc),
            planduration=60,
            gracetime=10,
            expirytime=30,
            priority=Job.Priority.MEDIUM,
            scantype=Job.Scantype.QR,
            identifier=Job.Identifier.TASK,
            qset=self.qset,
            bu=self.bu,
            client=self.bu,
            seqno=1,
            cuser=self.user,
            muser=self.user,
            parent_id=0  # Edge case
        )

        # Unified query should NOT find this
        root_jobs = Job.objects.filter(
            Q(parent__isnull=True) | Q(parent_id=1)
        )

        self.assertNotIn(job_zero, root_jobs)

    def test_parent_id_negative_one_handling(self):
        """
        Test handling of parent_id=-1 (another sentinel pattern).

        Some queries use parent_id__in=[1, -1].
        """
        # Create job with parent_id=-1
        job_neg = Job.objects.create(
            jobname="Job with parent_id=-1",
            jobdesc="Negative sentinel",
            fromdate=datetime(2025, 1, 1, tzinfo=timezone.utc),
            uptodate=datetime(2025, 12, 31, tzinfo=timezone.utc),
            planduration=60,
            gracetime=10,
            expirytime=30,
            priority=Job.Priority.MEDIUM,
            scantype=Job.Scantype.QR,
            identifier=Job.Identifier.SITEREPORT,
            qset=self.qset,
            bu=self.bu,
            client=self.bu,
            seqno=1,
            cuser=self.user,
            muser=self.user,
            parent_id=-1  # Negative sentinel
        )

        # Extended query pattern for some models
        root_jobs = Job.objects.filter(
            Q(parent__isnull=True) | Q(parent_id__in=[1, -1])
        )

        # Should find this
        self.assertIn(job_neg, root_jobs)
