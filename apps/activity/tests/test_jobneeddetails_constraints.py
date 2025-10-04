"""
Comprehensive Tests for JobneedDetails Constraints

Tests the database-level unique constraints on JobneedDetails:
1. (jobneed, question) uniqueness
2. (jobneed, seqno) uniqueness

Follows .claude/rules.md:
- Rule #11: Specific exception handling
- Rule #17: Transaction management in tests
"""

import pytest
from django.db import IntegrityError, transaction
from django.test import TestCase, TransactionTestCase
from apps.activity.models import Job, Jobneed, JobneedDetails, Question, QuestionSet
from apps.onboarding.models import Bt
from apps.peoples.models import People
from datetime import datetime, timezone
from apps.core.utils_new.db_utils import get_current_db_name


class JobneedDetailsConstraintsTest(TransactionTestCase):
    """
    Test JobneedDetails unique constraints.

    Uses TransactionTestCase to properly test database constraints.
    """

    @classmethod
    def setUpClass(cls):
        """Set up test fixtures once for all tests."""
        super().setUpClass()

    def setUp(self):
        """Create test data for each test."""
        # Create business unit
        self.bu = Bt.objects.create(
            bucode="TEST001",
            buname="Test Business Unit",
            butype="CLIENT"
        )

        # Create user
        self.user = People.objects.create(
            peoplecode="TEST001",
            peoplename="Test User",
            loginid="testuser",
            email="test@example.com"
        )

        # Create question set
        self.qset = QuestionSet.objects.create(
            qsetname="Test Question Set",
            qsettype="CHECKLIST"
        )

        # Create questions
        self.question1 = Question.objects.create(
            quesname="Question 1",
            qset=self.qset,
            answertype="SINGLELINE"
        )
        self.question2 = Question.objects.create(
            quesname="Question 2",
            qset=self.qset,
            answertype="NUMERIC"
        )

        # Create job
        self.job = Job.objects.create(
            jobname="Test Job",
            jobdesc="Test Job Description",
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
            muser=self.user
        )

        # Create jobneed
        self.jobneed = Jobneed.objects.create(
            jobdesc="Test Jobneed",
            plandatetime=datetime(2025, 10, 3, 10, 0, tzinfo=timezone.utc),
            expirydatetime=datetime(2025, 10, 3, 12, 0, tzinfo=timezone.utc),
            gracetime=10,
            priority=Jobneed.Priority.MEDIUM,
            scantype=Jobneed.Scantype.QR,
            identifier=Jobneed.Identifier.TASK,
            jobstatus=Jobneed.JobStatus.ASSIGNED,
            jobtype=Jobneed.JobType.SCHEDULE,
            job=self.job,
            qset=self.qset,
            bu=self.bu,
            client=self.bu,
            seqno=1,
            cuser=self.user,
            muser=self.user
        )

    def test_unique_jobneed_question_constraint_creation(self):
        """Test that we can create a jobneeddetails record."""
        jnd = JobneedDetails.objects.create(
            jobneed=self.jobneed,
            question=self.question1,
            seqno=1,
            answertype="SINGLELINE",
            cuser=self.user,
            muser=self.user
        )

        self.assertIsNotNone(jnd.id)
        self.assertEqual(jnd.jobneed, self.jobneed)
        self.assertEqual(jnd.question, self.question1)

    def test_unique_jobneed_question_constraint_violation(self):
        """
        Test that duplicate (jobneed, question) raises IntegrityError.

        Expected behavior:
        - First insert succeeds
        - Second insert with same (jobneed, question) fails
        """
        # First insert should succeed
        JobneedDetails.objects.create(
            jobneed=self.jobneed,
            question=self.question1,
            seqno=1,
            answertype="SINGLELINE",
            cuser=self.user,
            muser=self.user
        )

        # Second insert with same (jobneed, question) should fail
        with self.assertRaises(IntegrityError) as context:
            with transaction.atomic(using=get_current_db_name()):
                JobneedDetails.objects.create(
                    jobneed=self.jobneed,
                    question=self.question1,  # Same question
                    seqno=2,  # Different seqno
                    answertype="SINGLELINE",
                    cuser=self.user,
                    muser=self.user
                )

        # Verify the error message contains constraint name
        self.assertIn('jobneeddetails_jobneed_question_uk', str(context.exception).lower())

    def test_unique_jobneed_seqno_constraint_violation(self):
        """
        Test that duplicate (jobneed, seqno) raises IntegrityError.

        Expected behavior:
        - First insert succeeds
        - Second insert with same (jobneed, seqno) fails
        """
        # First insert should succeed
        JobneedDetails.objects.create(
            jobneed=self.jobneed,
            question=self.question1,
            seqno=1,
            answertype="SINGLELINE",
            cuser=self.user,
            muser=self.user
        )

        # Second insert with same (jobneed, seqno) should fail
        with self.assertRaises(IntegrityError) as context:
            with transaction.atomic(using=get_current_db_name()):
                JobneedDetails.objects.create(
                    jobneed=self.jobneed,
                    question=self.question2,  # Different question
                    seqno=1,  # Same seqno
                    answertype="NUMERIC",
                    cuser=self.user,
                    muser=self.user
                )

        # Verify the error message contains constraint name
        self.assertIn('jobneeddetails_jobneed_seqno_uk', str(context.exception).lower())

    def test_different_jobneeds_allow_same_question(self):
        """
        Test that different jobneeds can have the same question.

        This should succeed - constraints are scoped to jobneed.
        """
        # Create second jobneed
        jobneed2 = Jobneed.objects.create(
            jobdesc="Test Jobneed 2",
            plandatetime=datetime(2025, 10, 4, 10, 0, tzinfo=timezone.utc),
            expirydatetime=datetime(2025, 10, 4, 12, 0, tzinfo=timezone.utc),
            gracetime=10,
            priority=Jobneed.Priority.MEDIUM,
            scantype=Jobneed.Scantype.QR,
            identifier=Jobneed.Identifier.TASK,
            jobstatus=Jobneed.JobStatus.ASSIGNED,
            jobtype=Jobneed.JobType.SCHEDULE,
            job=self.job,
            qset=self.qset,
            bu=self.bu,
            client=self.bu,
            seqno=2,
            cuser=self.user,
            muser=self.user
        )

        # Both jobneeds can have the same question
        jnd1 = JobneedDetails.objects.create(
            jobneed=self.jobneed,
            question=self.question1,
            seqno=1,
            answertype="SINGLELINE",
            cuser=self.user,
            muser=self.user
        )

        jnd2 = JobneedDetails.objects.create(
            jobneed=jobneed2,
            question=self.question1,  # Same question, different jobneed
            seqno=1,
            answertype="SINGLELINE",
            cuser=self.user,
            muser=self.user
        )

        self.assertIsNotNone(jnd1.id)
        self.assertIsNotNone(jnd2.id)
        self.assertNotEqual(jnd1.id, jnd2.id)

    def test_different_jobneeds_allow_same_seqno(self):
        """
        Test that different jobneeds can have the same seqno.

        This should succeed - constraints are scoped to jobneed.
        """
        # Create second jobneed
        jobneed2 = Jobneed.objects.create(
            jobdesc="Test Jobneed 2",
            plandatetime=datetime(2025, 10, 4, 10, 0, tzinfo=timezone.utc),
            expirydatetime=datetime(2025, 10, 4, 12, 0, tzinfo=timezone.utc),
            gracetime=10,
            priority=Jobneed.Priority.MEDIUM,
            scantype=Jobneed.Scantype.QR,
            identifier=Jobneed.Identifier.TASK,
            jobstatus=Jobneed.JobStatus.ASSIGNED,
            jobtype=Jobneed.JobType.SCHEDULE,
            job=self.job,
            qset=self.qset,
            bu=self.bu,
            client=self.bu,
            seqno=2,
            cuser=self.user,
            muser=self.user
        )

        # Both jobneeds can have seqno=1
        jnd1 = JobneedDetails.objects.create(
            jobneed=self.jobneed,
            question=self.question1,
            seqno=1,
            answertype="SINGLELINE",
            cuser=self.user,
            muser=self.user
        )

        jnd2 = JobneedDetails.objects.create(
            jobneed=jobneed2,
            question=self.question2,
            seqno=1,  # Same seqno, different jobneed
            answertype="NUMERIC",
            cuser=self.user,
            muser=self.user
        )

        self.assertIsNotNone(jnd1.id)
        self.assertIsNotNone(jnd2.id)
        self.assertNotEqual(jnd1.id, jnd2.id)

    def test_multiple_questions_different_seqno(self):
        """
        Test that a jobneed can have multiple questions with different seqno.

        This is the normal use case - should succeed.
        """
        jnd1 = JobneedDetails.objects.create(
            jobneed=self.jobneed,
            question=self.question1,
            seqno=1,
            answertype="SINGLELINE",
            cuser=self.user,
            muser=self.user
        )

        jnd2 = JobneedDetails.objects.create(
            jobneed=self.jobneed,
            question=self.question2,
            seqno=2,
            answertype="NUMERIC",
            cuser=self.user,
            muser=self.user
        )

        self.assertIsNotNone(jnd1.id)
        self.assertIsNotNone(jnd2.id)
        self.assertEqual(
            JobneedDetails.objects.filter(jobneed=self.jobneed).count(),
            2
        )

    def test_update_does_not_violate_constraint(self):
        """
        Test that updating a record doesn't violate constraints.

        Should be able to update answer without triggering constraint.
        """
        jnd = JobneedDetails.objects.create(
            jobneed=self.jobneed,
            question=self.question1,
            seqno=1,
            answertype="SINGLELINE",
            answer="Original answer",
            cuser=self.user,
            muser=self.user
        )

        # Update answer
        jnd.answer = "Updated answer"
        jnd.save()  # Should succeed

        jnd.refresh_from_db()
        self.assertEqual(jnd.answer, "Updated answer")

    def test_constraint_prevents_bulk_create_duplicates(self):
        """
        Test that constraints prevent duplicate creation even in bulk.
        """
        details = [
            JobneedDetails(
                jobneed=self.jobneed,
                question=self.question1,
                seqno=1,
                answertype="SINGLELINE",
                cuser=self.user,
                muser=self.user
            ),
            JobneedDetails(
                jobneed=self.jobneed,
                question=self.question1,  # Duplicate question
                seqno=2,
                answertype="SINGLELINE",
                cuser=self.user,
                muser=self.user
            ),
        ]

        with self.assertRaises(IntegrityError):
            with transaction.atomic(using=get_current_db_name()):
                JobneedDetails.objects.bulk_create(details)


class JobneedDetailsConstraintErrorHandlingTest(TestCase):
    """Test error handling for constraint violations in application logic."""

    def setUp(self):
        """Create minimal test data."""
        self.bu = Bt.objects.create(
            bucode="TEST001",
            buname="Test Business Unit",
            butype="CLIENT"
        )

        self.user = People.objects.create(
            peoplecode="TEST001",
            peoplename="Test User",
            loginid="testuser",
            email="test@example.com"
        )

        self.qset = QuestionSet.objects.create(
            qsetname="Test Question Set",
            qsettype="CHECKLIST"
        )

        self.question = Question.objects.create(
            quesname="Question 1",
            qset=self.qset,
            answertype="SINGLELINE"
        )

    def test_graceful_constraint_handling(self):
        """
        Test that application code can gracefully handle constraint violations.

        This is a template for how to handle IntegrityError in views/services.
        """
        from django.db import IntegrityError

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
            qset=self.qset,
            bu=self.bu,
            client=self.bu,
            seqno=1,
            cuser=self.user,
            muser=self.user
        )

        jobneed = Jobneed.objects.create(
            jobdesc="Test Jobneed",
            plandatetime=datetime(2025, 10, 3, 10, 0, tzinfo=timezone.utc),
            expirydatetime=datetime(2025, 10, 3, 12, 0, tzinfo=timezone.utc),
            gracetime=10,
            priority=Jobneed.Priority.MEDIUM,
            scantype=Jobneed.Scantype.QR,
            identifier=Jobneed.Identifier.TASK,
            jobstatus=Jobneed.JobStatus.ASSIGNED,
            jobtype=Jobneed.JobType.SCHEDULE,
            job=job,
            qset=self.qset,
            bu=self.bu,
            client=self.bu,
            seqno=1,
            cuser=self.user,
            muser=self.user
        )

        # Create first record
        JobneedDetails.objects.create(
            jobneed=jobneed,
            question=self.question,
            seqno=1,
            answertype="SINGLELINE",
            cuser=self.user,
            muser=self.user
        )

        # Try to create duplicate - should be caught and handled
        try:
            with transaction.atomic(using=get_current_db_name()):
                JobneedDetails.objects.create(
                    jobneed=jobneed,
                    question=self.question,
                    seqno=2,
                    answertype="SINGLELINE",
                    cuser=self.user,
                    muser=self.user
                )
            self.fail("Should have raised IntegrityError")
        except IntegrityError as e:
            # Application should catch this and return user-friendly error
            error_message = str(e).lower()
            self.assertIn('jobneeddetails_jobneed_question_uk', error_message)
            # In real code, return: {"error": "Question already exists in this checklist"}
