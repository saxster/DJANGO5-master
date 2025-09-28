"""
N+1 Query Remediation Tests.

Comprehensive test suite to validate that N+1 query patterns have been fixed
and to prevent regressions.
"""

import pytest
from django.test import TestCase, TransactionTestCase, Client, override_settings
from django.contrib.auth import get_user_model
from apps.core.testing import assert_max_queries, detect_n_plus_one, QueryCountAsserter
from apps.activity.models.attachment_model import Attachment
from apps.activity.models.question_model import Question, QuestionSet
from apps.activity.models.job_model import Jobneed, JobneedDetails
from apps.onboarding.models import BT, TypeAssist

People = get_user_model()


@pytest.mark.integration
@override_settings(DEBUG=True)
class AttachmentViewN1TestCase(TestCase):
    """
    Test cases to verify attachment_views.py N+1 fixes.
    Location: apps/activity/views/attachment_views.py:46
    """

    @classmethod
    def setUpTestData(cls):
        cls.bt = BT.objects.create(
            bucode="TEST_BT", buname="Test Business", enable=True
        )
        cls.user = People.objects.create_user(
            loginid="testuser", password="TestPass123!", peoplename="Test User",
            bt=cls.bt
        )
        cls.type_assist = TypeAssist.objects.get_or_create(
            taname="JOBNEED", tacode="JOBNEED"
        )[0]

        cls.attachment = Attachment.objects.create(
            filename="test.jpg", filepath="/test/path/",
            owner="test-uuid-123", ownername=cls.type_assist,
            bu=cls.bt, cuser=cls.user, muser=cls.user
        )

    def setUp(self):
        self.client = Client()
        self.client.force_login(self.user)

    @assert_max_queries(3)
    def test_attachment_delete_optimized(self):
        """
        Test that attachment delete operation doesn't cause N+1 queries.
        Should use optimized_delete_by_id() which preloads ownername and bu.
        Expected queries:
        1. SELECT attachment with select_related
        2. DELETE attachment
        3. Session update
        """
        response = self.client.get(
            '/activity/attachments/',
            {
                'action': 'delete_att',
                'id': self.attachment.id,
                'ownername': 'jobneed',
                'ownerid': 'test-uuid-123'
            }
        )
        self.assertEqual(response.status_code, 200)

    def test_attachment_delete_returns_404_for_nonexistent(self):
        """Test that delete returns 404 for nonexistent attachment."""
        response = self.client.get(
            '/activity/attachments/',
            {
                'action': 'delete_att',
                'id': 99999,
                'ownername': 'jobneed',
                'ownerid': 'test-uuid-123'
            }
        )
        self.assertEqual(response.status_code, 404)


@pytest.mark.integration
@override_settings(DEBUG=True)
class QuestionViewN1TestCase(TestCase):
    """
    Test cases to verify question_views.py N+1 fixes.
    Location: apps/activity/views/question_views.py:169
    """

    @classmethod
    def setUpTestData(cls):
        cls.bt = BT.objects.create(
            bucode="TEST_BT", buname="Test Business", enable=True
        )
        cls.user = People.objects.create_user(
            loginid="testuser", password="TestPass123!", peoplename="Test User",
            bt=cls.bt
        )
        cls.unit_ta = TypeAssist.objects.get_or_create(
            taname="Celsius", tacode="C"
        )[0]

    def setUp(self):
        self.client = Client()
        self.client.force_login(self.user)
        self.session = self.client.session
        self.session['bu_id'] = self.bt.id
        self.session['client_id'] = self.bt.id
        self.session.save()

    @assert_max_queries(8)
    def test_question_display_values_optimized(self):
        """
        Test that question values() query uses select_related('unit').
        Previously caused N+1 when accessing unit__tacode.
        """
        from apps.activity.forms.question_form import QuestionForm

        question_data = {
            'quesname': 'Test Temperature',
            'answertype': 'NUMERIC',
            'unit': self.unit_ta.id,
            'category': 1,
            'options': '',
            'min': 0,
            'max': 100,
            'alerton': '',
            'ctzoffset': 0
        }

        form = QuestionForm(data=question_data, request=type('Request', (), {'user': self.user, 'session': self.session})())
        self.assertTrue(form.is_valid())

        question = form.save()
        question.cuser = self.user
        question.muser = self.user
        question.save()

        row_data = Question.objects.optimized_filter_for_display(
            question.id, ['id', 'quesname', 'answertype', 'unit__tacode', 'isworkflow']
        )

        self.assertIsNotNone(row_data)
        self.assertEqual(row_data['quesname'], 'Test Temperature')


@pytest.mark.integration
@override_settings(DEBUG=True)
class JobneedViewN1TestCase(TestCase):
    """
    Test cases to verify job_views.py N+1 fixes.
    Location: apps/activity/views/job_views.py:74,83,211
    """

    @classmethod
    def setUpTestData(cls):
        from apps.activity.models.asset_model import Asset
        from apps.onboarding.models import Shift

        cls.bt = BT.objects.create(
            bucode="TEST_BT", buname="Test Business", enable=True
        )
        cls.user = People.objects.create_user(
            loginid="testuser", password="TestPass123!", peoplename="Test User",
            bt=cls.bt
        )
        cls.shift = Shift.objects.create(
            shiftname="Day Shift", starttime="09:00", endtime="17:00",
            client=cls.bt
        )
        cls.asset = Asset.objects.create(
            assetcode="ASSET001", assetname="Test Asset",
            identifier="ASSET", bu=cls.bt, client=cls.bt
        )
        cls.qset = QuestionSet.objects.create(
            qsetname="Test QSet", type="CHECKLIST",
            bu=cls.bt, client=cls.bt
        )
        cls.jobneed = Jobneed.objects.create(
            jobdesc="Test PPM Jobneed", identifier="PPM",
            asset=cls.asset, qset=cls.qset, bu=cls.bt,
            client=cls.bt, performedby=cls.user
        )

    def setUp(self):
        self.client = Client()
        self.client.force_login(self.user)

    @assert_max_queries(5)
    def test_jobneed_get_optimized(self):
        """
        Test that Jobneed.objects.get() uses optimized_get_with_relations().
        Should preload performedby, asset, bu, qset, job relationships.
        """
        jobneed = Jobneed.objects.optimized_get_with_relations(self.jobneed.id)

        self.assertEqual(jobneed.id, self.jobneed.id)
        _ = jobneed.performedby.peoplename
        _ = jobneed.asset.assetname
        _ = jobneed.bu.buname
        _ = jobneed.qset.qsetname


@pytest.mark.integration
@override_settings(DEBUG=True)
class TranscriptViewN1TestCase(TestCase):
    """
    Test cases to verify transcript_views.py N+1 fixes.
    Location: apps/activity/views/transcript_views.py:40,101
    """

    @classmethod
    def setUpTestData(cls):
        from apps.activity.models.asset_model import Asset

        cls.bt = BT.objects.create(
            bucode="TEST_BT", buname="Test Business", enable=True
        )
        cls.user = People.objects.create_user(
            loginid="testuser", password="TestPass123!", peoplename="Test User",
            bt=cls.bt
        )
        cls.asset = Asset.objects.create(
            assetcode="ASSET001", assetname="Test Asset",
            identifier="ASSET", bu=cls.bt, client=cls.bt
        )
        cls.qset = QuestionSet.objects.create(
            qsetname="Test QSet", type="CHECKLIST",
            bu=cls.bt, client=cls.bt
        )
        cls.jobneed = Jobneed.objects.create(
            jobdesc="Test Jobneed", identifier="TASK",
            asset=cls.asset, qset=cls.qset, bu=cls.bt,
            client=cls.bt, performedby=cls.user
        )
        cls.question = Question.objects.create(
            quesname="Test Question", answertype="TEXT",
            client=cls.bt
        )
        cls.jobneed_detail = JobneedDetails.objects.create(
            jobneed=cls.jobneed, question=cls.question,
            answertype="TEXT", answer="Test answer",
            bu=cls.bt, client=cls.bt
        )

    def setUp(self):
        self.client = Client()
        self.client.force_login(self.user)

    @assert_max_queries(4)
    def test_jobneed_detail_get_optimized(self):
        """
        Test that JobneedDetails.objects.get() uses optimized method.
        Should preload question, jobneed, cuser, muser relationships.
        """
        detail = JobneedDetails.objects.optimized_get_with_relations(
            self.jobneed_detail.id
        )

        self.assertEqual(detail.id, self.jobneed_detail.id)
        _ = detail.question.quesname
        _ = detail.jobneed.jobdesc


@pytest.mark.integration
@override_settings(DEBUG=True)
class ManagerOptimizationTestCase(TestCase):
    """
    Test cases to verify manager-level optimizations.
    """

    @classmethod
    def setUpTestData(cls):
        from apps.activity.models.asset_model import Asset

        cls.bt = BT.objects.create(
            bucode="TEST_BT", buname="Test Business", enable=True
        )
        cls.user = People.objects.create_user(
            loginid="testuser", password="TestPass123!", peoplename="Test User",
            bt=cls.bt
        )
        cls.type_assist = TypeAssist.objects.get_or_create(
            taname="JOBNEED", tacode="JOBNEED"
        )[0]

        for i in range(10):
            Attachment.objects.create(
                filename=f"test{i}.jpg", filepath=f"/test/path{i}/",
                owner=f"test-uuid-{i}", ownername=cls.type_assist,
                bu=cls.bt, cuser=cls.user, muser=cls.user
            )

        cls.unit_ta = TypeAssist.objects.get_or_create(
            taname="Celsius", tacode="C"
        )[0]

        for i in range(10):
            Question.objects.create(
                quesname=f"Test Question {i}", answertype="TEXT",
                client=cls.bt, unit=cls.unit_ta
            )

    @detect_n_plus_one(threshold=5)
    def test_attachment_manager_no_n_plus_one(self):
        """Test that attachment queries don't trigger N+1 patterns."""
        attachments = list(
            Attachment.objects.select_related('ownername', 'bu', 'cuser').all()[:10]
        )

        for att in attachments:
            _ = att.ownername.taname
            _ = att.bu.buname
            _ = att.cuser.peoplename

    @detect_n_plus_one(threshold=5)
    def test_question_manager_no_n_plus_one(self):
        """Test that question queries don't trigger N+1 patterns."""
        questions = list(
            Question.objects.select_related('unit', 'client').all()[:10]
        )

        for q in questions:
            _ = q.unit.tacode if q.unit else None
            _ = q.client.buname if q.client else None

    def test_query_count_asserter_context_manager(self):
        """Test QueryCountAsserter context manager utility."""
        with QueryCountAsserter(max_queries=3):
            list(Attachment.objects.select_related('bu', 'cuser').all()[:5])

    def test_query_count_asserter_exact(self):
        """Test QueryCountAsserter with exact query count."""
        with QueryCountAsserter(exact_queries=1):
            Attachment.objects.count()


@pytest.mark.performance
@override_settings(DEBUG=True)
class QueryOptimizationBenchmarkTestCase(TestCase):
    """
    Performance benchmarks comparing optimized vs unoptimized queries.
    """

    @classmethod
    def setUpTestData(cls):
        from apps.activity.models.asset_model import Asset

        cls.bt = BT.objects.create(
            bucode="BENCH_BT", buname="Benchmark Business", enable=True
        )
        cls.user = People.objects.create_user(
            loginid="benchuser", password="BenchPass123!",
            peoplename="Bench User", bt=cls.bt
        )

        cls.asset = Asset.objects.create(
            assetcode="ASSET001", assetname="Test Asset",
            identifier="ASSET", bu=cls.bt, client=cls.bt
        )
        cls.qset = QuestionSet.objects.create(
            qsetname="Bench QSet", type="CHECKLIST",
            bu=cls.bt, client=cls.bt
        )

        cls.jobneeds = []
        for i in range(20):
            jn = Jobneed.objects.create(
                jobdesc=f"Benchmark Jobneed {i}", identifier="TASK",
                asset=cls.asset, qset=cls.qset, bu=cls.bt,
                client=cls.bt, performedby=cls.user
            )
            cls.jobneeds.append(jn)

    def test_unoptimized_query_count(self):
        """Baseline: Count queries without optimization."""
        with QueryCountAsserter() as counter:
            for jn_id in [jn.id for jn in self.jobneeds[:10]]:
                jobneed = Jobneed.objects.get(id=jn_id)
                _ = jobneed.performedby.peoplename
                _ = jobneed.asset.assetname

        unoptimized_count = counter.get_query_count()
        self.assertGreater(unoptimized_count, 20)

    @assert_max_queries(12)
    def test_optimized_query_count(self):
        """
        Optimized: Count queries with select_related.
        Should be ~1 query for initial fetch + 1 per iteration with optimization.
        """
        jobneeds = list(
            Jobneed.objects.select_related(
                'performedby', 'asset', 'bu', 'qset'
            ).filter(id__in=[jn.id for jn in self.jobneeds[:10]])
        )

        for jobneed in jobneeds:
            _ = jobneed.performedby.peoplename
            _ = jobneed.asset.assetname


@pytest.mark.unit
class QueryOptimizationUtilityTestCase(TestCase):
    """Test the query optimization utility functions."""

    def test_assert_max_queries_decorator_passes(self):
        """Test that decorator passes when under limit."""
        @assert_max_queries(5)
        def test_function():
            Attachment.objects.count()
            return True

        result = test_function()
        self.assertTrue(result)

    def test_assert_max_queries_decorator_fails(self):
        """Test that decorator fails when over limit."""
        @assert_max_queries(1)
        def test_function():
            list(Attachment.objects.all()[:5])
            for _ in range(10):
                Attachment.objects.count()

        with self.assertRaises(AssertionError) as cm:
            test_function()

        self.assertIn("N+1 Query Pattern Detected", str(cm.exception))

    def test_query_count_asserter_max_passes(self):
        """Test QueryCountAsserter passes when under limit."""
        with QueryCountAsserter(max_queries=3):
            Attachment.objects.count()
            Question.objects.count()

    def test_query_count_asserter_max_fails(self):
        """Test QueryCountAsserter fails when over limit."""
        with self.assertRaises(AssertionError):
            with QueryCountAsserter(max_queries=1):
                Attachment.objects.count()
                Question.objects.count()
                Jobneed.objects.count()

    def test_query_count_asserter_exact_passes(self):
        """Test QueryCountAsserter passes with exact count."""
        with QueryCountAsserter(exact_queries=2):
            Attachment.objects.count()
            Question.objects.count()

    def test_query_count_asserter_exact_fails(self):
        """Test QueryCountAsserter fails when count doesn't match."""
        with self.assertRaises(AssertionError):
            with QueryCountAsserter(exact_queries=1):
                Attachment.objects.count()
                Question.objects.count()


@pytest.mark.integration
class IntegrationN1RegressionTestCase(TransactionTestCase):
    """
    Integration tests to prevent N+1 query regressions in common workflows.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        from apps.activity.models.asset_model import Asset

        cls.bt = BT.objects.create(
            bucode="INT_BT", buname="Integration Business", enable=True
        )
        cls.user = People.objects.create_user(
            loginid="intuser", password="IntPass123!",
            peoplename="Integration User", bt=cls.bt
        )

        cls.asset = Asset.objects.create(
            assetcode="ASSET001", assetname="Test Asset",
            identifier="ASSET", bu=cls.bt, client=cls.bt
        )
        cls.qset = QuestionSet.objects.create(
            qsetname="Integration QSet", type="CHECKLIST",
            bu=cls.bt, client=cls.bt
        )

    def setUp(self):
        self.client = Client()
        self.client.force_login(self.user)
        self.session = self.client.session
        self.session['bu_id'] = self.bt.id
        self.session['client_id'] = self.bt.id
        self.session['assignedsites'] = [self.bt.id]
        self.session.save()

    @assert_max_queries(15)
    def test_attachment_list_workflow(self):
        """Test complete attachment workflow stays within query limits."""
        type_assist = TypeAssist.objects.get_or_create(
            taname="JOBNEED", tacode="JOBNEED"
        )[0]

        for i in range(5):
            Attachment.objects.create(
                filename=f"workflow{i}.jpg", filepath=f"/workflow/path{i}/",
                owner="workflow-uuid", ownername=type_assist,
                bu=self.bt, cuser=self.user, muser=self.user
            )

        response = self.client.get(
            '/activity/attachments/',
            {'action': 'get_attachments_of_owner', 'owner': 'workflow-uuid'}
        )
        self.assertEqual(response.status_code, 200)

    @assert_max_queries(10)
    def test_question_list_with_filters(self):
        """Test question list view with filters stays optimized."""
        unit_ta = TypeAssist.objects.get_or_create(
            taname="Celsius", tacode="C"
        )[0]

        for i in range(5):
            Question.objects.create(
                quesname=f"Filter Test {i}", answertype="TEXT",
                client=self.bt, unit=unit_ta
            )

        questions = Question.objects.select_related('unit', 'client').filter(
            client=self.bt
        ).values('id', 'quesname', 'answertype', 'unit__tacode', 'isworkflow')

        question_list = list(questions)
        self.assertGreater(len(question_list), 0)