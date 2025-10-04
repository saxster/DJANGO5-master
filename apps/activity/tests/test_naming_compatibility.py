"""
Naming Compatibility Tests for Job Models

Tests backward compatibility aliases for Jobneed naming.
- Jobneed (correct, lowercase 'n')
- JobNeed (deprecated alias, uppercase 'N')

Follows .claude/rules.md:
- Rule #11: Specific exception handling
"""

import pytest
from django.test import TestCase
from datetime import datetime, timezone


class NamingCompatibilityTest(TestCase):
    """
    Test backward compatibility aliases for model naming.

    These aliases prevent import errors during migration period.
    """

    def test_jobneed_import_correct_name(self):
        """
        Test importing Jobneed with correct naming (lowercase 'n').
        """
        from apps.activity.models import Jobneed

        self.assertIsNotNone(Jobneed)
        self.assertEqual(Jobneed.__name__, 'Jobneed')

    def test_jobneed_import_legacy_alias(self):
        """
        Test importing JobNeed (uppercase 'N') via backward compatibility alias.

        This should work but is deprecated.
        """
        from apps.activity.models import JobNeed

        self.assertIsNotNone(JobNeed)

        # Verify it's an alias to Jobneed
        from apps.activity.models import Jobneed
        self.assertIs(JobNeed, Jobneed, "JobNeed should be alias to Jobneed")

    def test_jobneeddetails_import_correct_name(self):
        """
        Test importing JobneedDetails with correct naming (lowercase 'n').
        """
        from apps.activity.models import JobneedDetails

        self.assertIsNotNone(JobneedDetails)
        self.assertEqual(JobneedDetails.__name__, 'JobneedDetails')

    def test_jobneeddetails_import_legacy_alias(self):
        """
        Test importing JobNeedDetails (uppercase 'N') via backward compatibility alias.

        This should work but is deprecated.
        """
        from apps.activity.models import JobNeedDetails

        self.assertIsNotNone(JobNeedDetails)

        # Verify it's an alias
        from apps.activity.models import JobneedDetails
        self.assertIs(JobNeedDetails, JobneedDetails, "JobNeedDetails should be alias")

    def test_model_creation_with_correct_name(self):
        """
        Test creating instances using correct model name.
        """
        from apps.activity.models import Jobneed, Job, JobneedDetails
        from apps.onboarding.models import Bt
        from apps.peoples.models import People
        from apps.activity.models.question_model import QuestionSet, Question

        # Setup minimal data
        bu = Bt.objects.create(bucode="T001", buname="Test", butype="CLIENT")
        user = People.objects.create(
            peoplecode="T001",
            peoplename="Test",
            loginid="test",
            email="test@example.com"
        )
        qset = QuestionSet.objects.create(qsetname="Test", qsettype="CHECKLIST")

        job = Job.objects.create(
            jobname="Test Job",
            jobdesc="Test",
            fromdate=datetime(2025, 1, 1, tzinfo=timezone.utc),
            uptodate=datetime(2025, 12, 31, tzinfo=timezone.utc),
            planduration=60,
            gracetime=10,
            expirytime=30,
            priority=Job.Priority.MEDIUM,
            scantype=Job.Scantype.QR,
            identifier=Job.Identifier.TASK,
            qset=qset,
            bu=bu,
            client=bu,
            seqno=1,
            cuser=user,
            muser=user
        )

        # Create using correct name
        jobneed = Jobneed.objects.create(
            job=job,
            jobdesc="Test Jobneed",
            plandatetime=datetime(2025, 10, 3, 10, 0, tzinfo=timezone.utc),
            expirydatetime=datetime(2025, 10, 3, 11, 30, tzinfo=timezone.utc),
            gracetime=10,
            priority=Jobneed.Priority.MEDIUM,
            scantype=Jobneed.Scantype.QR,
            identifier=Jobneed.Identifier.TASK,
            jobstatus=Jobneed.JobStatus.ASSIGNED,
            jobtype=Jobneed.JobType.SCHEDULE,
            qset=qset,
            bu=bu,
            client=bu,
            seqno=1,
            cuser=user,
            muser=user
        )

        self.assertIsNotNone(jobneed.id)
        self.assertEqual(jobneed.__class__.__name__, 'Jobneed')

    def test_model_creation_with_legacy_alias(self):
        """
        Test creating instances using legacy alias (should work).
        """
        from apps.activity.models import JobNeed, Job, JobNeedDetails
        from apps.onboarding.models import Bt
        from apps.peoples.models import People
        from apps.activity.models.question_model import QuestionSet, Question

        # Setup minimal data
        bu = Bt.objects.create(bucode="T002", buname="Test2", butype="CLIENT")
        user = People.objects.create(
            peoplecode="T002",
            peoplename="Test2",
            loginid="test2",
            email="test2@example.com"
        )
        qset = QuestionSet.objects.create(qsetname="Test2", qsettype="CHECKLIST")

        job = Job.objects.create(
            jobname="Test Job 2",
            jobdesc="Test",
            fromdate=datetime(2025, 1, 1, tzinfo=timezone.utc),
            uptodate=datetime(2025, 12, 31, tzinfo=timezone.utc),
            planduration=60,
            gracetime=10,
            expirytime=30,
            priority=Job.Priority.MEDIUM,
            scantype=Job.Scantype.QR,
            identifier=Job.Identifier.TASK,
            qset=qset,
            bu=bu,
            client=bu,
            seqno=1,
            cuser=user,
            muser=user
        )

        # Create using legacy alias (should work via alias)
        jobneed = JobNeed.objects.create(
            job=job,
            jobdesc="Test Jobneed (via alias)",
            plandatetime=datetime(2025, 10, 3, 10, 0, tzinfo=timezone.utc),
            expirydatetime=datetime(2025, 10, 3, 11, 30, tzinfo=timezone.utc),
            gracetime=10,
            priority=JobNeed.Priority.MEDIUM,
            scantype=JobNeed.Scantype.QR,
            identifier=JobNeed.Identifier.TASK,
            jobstatus=JobNeed.JobStatus.ASSIGNED,
            jobtype=JobNeed.JobType.SCHEDULE,
            qset=qset,
            bu=bu,
            client=bu,
            seqno=1,
            cuser=user,
            muser=user
        )

        self.assertIsNotNone(jobneed.id)

        # Verify it's actually a Jobneed instance
        self.assertEqual(jobneed.__class__.__name__, 'Jobneed')

    def test_model_all_exports(self):
        """
        Test that __all__ exports both correct names and aliases.
        """
        from apps.activity.models import job_model

        # Check __all__ is defined
        self.assertIsNotNone(job_model.__all__)

        # Should include correct names
        self.assertIn('Job', job_model.__all__)
        self.assertIn('Jobneed', job_model.__all__)
        self.assertIn('JobneedDetails', job_model.__all__)

        # Should include legacy aliases
        self.assertIn('JobNeed', job_model.__all__)
        self.assertIn('JobNeedDetails', job_model.__all__)

    def test_import_star_includes_aliases(self):
        """
        Test that 'from models import *' includes aliases.
        """
        # This simulates: from apps.activity.models.job_model import *
        import apps.activity.models.job_model as job_model

        namespace = {name: getattr(job_model, name) for name in job_model.__all__}

        # Check correct names exist
        self.assertIn('Jobneed', namespace)
        self.assertIn('JobneedDetails', namespace)

        # Check aliases exist
        self.assertIn('JobNeed', namespace)
        self.assertIn('JobNeedDetails', namespace)

        # Verify aliases point to correct classes
        self.assertIs(namespace['JobNeed'], namespace['Jobneed'])
        self.assertIs(namespace['JobNeedDetails'], namespace['JobneedDetails'])

    def test_mixed_import_styles(self):
        """
        Test that different import styles all work.

        This ensures backward compatibility for existing code.
        """
        # Style 1: Correct name
        from apps.activity.models import Jobneed as Jobneed1

        # Style 2: Legacy alias
        from apps.activity.models import JobNeed as Jobneed2

        # Style 3: Via models module
        from apps.activity import models
        Jobneed3 = models.Jobneed
        Jobneed4 = models.JobNeed

        # All should reference the same class
        self.assertIs(Jobneed1, Jobneed2)
        self.assertIs(Jobneed1, Jobneed3)
        self.assertIs(Jobneed1, Jobneed4)

    def test_isinstance_checks_work_with_aliases(self):
        """
        Test that isinstance() works with both names and aliases.
        """
        from apps.activity.models import Jobneed, JobNeed
        from apps.onboarding.models import Bt
        from apps.peoples.models import People
        from apps.activity.models.question_model import QuestionSet

        bu = Bt.objects.create(bucode="T003", buname="Test3", butype="CLIENT")
        user = People.objects.create(
            peoplecode="T003",
            peoplename="Test3",
            loginid="test3",
            email="test3@example.com"
        )
        qset = QuestionSet.objects.create(qsetname="Test3", qsettype="CHECKLIST")

        from apps.activity.models import Job
        job = Job.objects.create(
            jobname="Test Job 3",
            jobdesc="Test",
            fromdate=datetime(2025, 1, 1, tzinfo=timezone.utc),
            uptodate=datetime(2025, 12, 31, tzinfo=timezone.utc),
            planduration=60,
            gracetime=10,
            expirytime=30,
            priority=Job.Priority.MEDIUM,
            scantype=Job.Scantype.QR,
            identifier=Job.Identifier.TASK,
            qset=qset,
            bu=bu,
            client=bu,
            seqno=1,
            cuser=user,
            muser=user
        )

        jobneed = Jobneed.objects.create(
            job=job,
            jobdesc="Test",
            plandatetime=datetime(2025, 10, 3, 10, 0, tzinfo=timezone.utc),
            expirydatetime=datetime(2025, 10, 3, 11, 30, tzinfo=timezone.utc),
            gracetime=10,
            priority=Jobneed.Priority.MEDIUM,
            scantype=Jobneed.Scantype.QR,
            identifier=Jobneed.Identifier.TASK,
            jobstatus=Jobneed.JobStatus.ASSIGNED,
            jobtype=Jobneed.JobType.SCHEDULE,
            qset=qset,
            bu=bu,
            client=bu,
            seqno=1,
            cuser=user,
            muser=user
        )

        # isinstance should work with both
        self.assertIsInstance(jobneed, Jobneed)
        self.assertIsInstance(jobneed, JobNeed)  # Via alias

    def test_queryset_model_matches_both_names(self):
        """
        Test that QuerySet.model works with both names.
        """
        from apps.activity.models import Jobneed, JobNeed

        # Get queryset
        queryset = Jobneed.objects.all()

        # Verify model attribute
        self.assertEqual(queryset.model, Jobneed)
        self.assertEqual(queryset.model, JobNeed)  # Via alias
        self.assertIs(Jobneed, JobNeed)
