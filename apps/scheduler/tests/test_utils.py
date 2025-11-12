from django.test import TestCase, TransactionTestCase
from django.utils import timezone
from datetime import datetime, timedelta
import pytest
from unittest.mock import Mock, patch

from apps.scheduler import utils as sutils
from apps.activity.models.asset_model import Asset
from apps.activity.models.question_model import QuestionSet
from apps.peoples.models import People, Pgroup
from apps.client_onboarding.models import Bt

# Removed 4 skipped test classes (lines 13-326):
# - CreateJobTestCase - Tests refer to non-existent functions: filter_jobs, process_job
# - FilterJobsTestCase - Tests refer to non-existent function: filter_jobs
# - ProcessJobTestCase - Tests refer to non-existent function: process_job
# - InsertIntoJnAndJndTestCase - Tests refer to non-existent utils.Asset
# These functions were refactored/removed and tests were never updated
class JobFieldsTestCase(TestCase):
    def test_job_fields_internal_tour(self):
        job = {
            "id": 1,
            "jobname": "Test Job",
            "cron": "0 8 * * *",
            "identifier": "INTERNALTOUR",
            "priority": "HIGH",
            "pgroup_id": 1,
            "geofence_id": 1,
            "ticketcategory_id": 1,
            "fromdate": datetime(2024, 1, 1),
            "uptodate": datetime(2024, 12, 31),
            "planduration": 60,
            "gracetime": 5,
            "frequency": "DAILY",
            "people_id": 1,
            "scantype": "QR",
            "ctzoffset": 330,
            "bu_id": 1,
            "client_id": 1,
            "lastgeneratedon": datetime(2024, 1, 1),
        }

        checkpoint = {
            "expirytime": 10,
            "qsetname": "Test QSet",
            "qsetid": 1,
            "assetid": 1,
            "seqno": 1,
            "starttime": "08:00",
            "endtime": "17:00",
        }

        result = sutils.job_fields(job, checkpoint)

        self.assertIn("jobname", result)
        self.assertIn("jobdesc", result)
        self.assertIn("expirytime", result)
        self.assertEqual(result["expirytime"], 10)

    def test_job_fields_external_tour(self):
        job = {
            "id": 1,
            "jobname": "Test Job",
            "cron": "0 8 * * *",
            "identifier": "EXTERNALTOUR",
            "priority": "HIGH",
            "pgroup_id": 1,
            "geofence_id": 1,
            "ticketcategory_id": 1,
            "fromdate": datetime(2024, 1, 1),
            "uptodate": datetime(2024, 12, 31),
            "planduration": 60,
            "gracetime": 5,
            "frequency": "DAILY",
            "people_id": 1,
            "scantype": "QR",
            "ctzoffset": 330,
            "bu_id": 1,
            "client_id": 1,
            "lastgeneratedon": datetime(2024, 1, 1),
            "other_info": {
                "istimebound": True,
                "is_randomized": False,
                "tour_frequency": 1,
            },
        }

        checkpoint = {
            "expirytime": 10,
            "qsetname": "Test QSet",
            "qsetid": 1,
            "assetid": 1,
            "seqno": 1,
            "starttime": "08:00",
            "endtime": "17:00",
            "bu__buname": "Test Site",
            "distance": 5.5,
            "breaktime": 15,
        }

        result = sutils.job_fields(job, checkpoint, external=True)

        self.assertIn("other_info", result)
        self.assertIn("distance", result["other_info"])
        self.assertIn("breaktime", result["other_info"])


class DeleteFromJobTestCase(TestCase):
    def setUp(self):
        self.people = People.objects.create(
            peoplename="Test Person",
            email="test@example.com",
            peoplecode="TEST001",
            dateofbirth="1990-01-01",
        )

        self.asset = Asset.objects.create(
            assetcode="TESTASSET001", assetname="Test Asset", iscritical=False
        )

        self.questionset = QuestionSet.objects.create(qsetname="Test Questionset")

        self.parent_job = Job.objects.create(
            jobname="Parent Job",
            jobdesc="Parent Description",
            people=self.people,
            fromdate=timezone.now(),
            uptodate=timezone.now() + timedelta(days=30),
            planduration=60,
            gracetime=15,
            expirytime=120,
            priority=Job.Priority.MEDIUM,
            seqno=1,
            scantype=Job.Scantype.SKIP,
        )

        self.child_job = Job.objects.create(
            jobname="Child Job",
            jobdesc="Child Description",
            people=self.people,
            parent=self.parent_job,
            asset=self.asset,
            qset=self.questionset,
            fromdate=timezone.now(),
            uptodate=timezone.now() + timedelta(days=30),
            planduration=60,
            gracetime=15,
            expirytime=120,
            priority=Job.Priority.MEDIUM,
            seqno=2,
            scantype=Job.Scantype.SKIP,
        )

    def test_delete_from_job_success(self):
        sutils.delete_from_job(self.parent_job.id, self.asset.id, self.questionset.id)

        self.assertFalse(Job.objects.filter(id=self.child_job.id).exists())

    def test_delete_from_job_not_found(self):
        with self.assertRaises(Job.DoesNotExist):
            sutils.delete_from_job(999, 999, 999)


class DeleteFromJobneedTestCase(TransactionTestCase):
    def setUp(self):
        self.people = People.objects.create(
            peoplename="Test Person",
            email="test@example.com",
            peoplecode="TEST001",
            dateofbirth="1990-01-01",
        )

        self.asset = Asset.objects.create(
            assetcode="TESTASSET001", assetname="Test Asset", iscritical=False
        )

        self.questionset = QuestionSet.objects.create(qsetname="Test Questionset")

        self.job = Job.objects.create(
            jobname="Test Job",
            jobdesc="Test Description",
            people=self.people,
            fromdate=timezone.now(),
            uptodate=timezone.now() + timedelta(days=30),
            planduration=60,
            gracetime=15,
            expirytime=120,
            priority=Job.Priority.MEDIUM,
            seqno=1,
            scantype=Job.Scantype.SKIP,
        )

        self.parent_jobneed = Jobneed.objects.create(
            jobdesc="Parent Jobneed",
            job=self.job,
            people=self.people,
            asset=self.asset,
            qset=self.questionset,
            gracetime=15,
            priority=Jobneed.Priority.MEDIUM,
            seqno=1,
        )

        self.child_jobneed = Jobneed.objects.create(
            jobdesc="Child Jobneed",
            job=self.job,
            people=self.people,
            parent=self.parent_jobneed,
            asset=self.asset,
            qset=self.questionset,
            gracetime=15,
            priority=Jobneed.Priority.MEDIUM,
            seqno=2,
        )

    def test_delete_from_jobneed_success(self):
        sutils.delete_from_jobneed(
            self.parent_jobneed.id, self.asset.id, self.questionset.id
        )

        self.assertFalse(Jobneed.objects.filter(id=self.child_jobneed.id).exists())

    def test_delete_from_jobneed_not_found(self):
        with self.assertRaises(Jobneed.DoesNotExist):
            sutils.delete_from_jobneed(999, 999, 999)


class UpdateLastGeneratedonTestCase(TestCase):
    def setUp(self):
        self.people = People.objects.create(
            peoplename="Test Person",
            email="test@example.com",
            peoplecode="TEST001",
            dateofbirth="1990-01-01",
        )

        self.job = Job.objects.create(
            jobname="Test Job",
            jobdesc="Test Description",
            people=self.people,
            fromdate=timezone.now(),
            uptodate=timezone.now() + timedelta(days=30),
            planduration=60,
            gracetime=15,
            expirytime=120,
            priority=Job.Priority.MEDIUM,
            seqno=1,
            scantype=Job.Scantype.SKIP,
        )

    def test_update_lastgeneratedon_success(self):
        new_date = timezone.now()
        job_data = {"id": self.job.id}

        sutils.update_lastgeneratedon(job_data, new_date)

        self.job.refresh_from_db()
        self.assertIsNotNone(self.job.lastgeneratedon)

    def test_update_lastgeneratedon_job_not_found(self):
        new_date = timezone.now()
        job_data = {"id": 999}

        # The function doesn't raise an error, it just logs a warning
        sutils.update_lastgeneratedon(job_data, new_date)

        # Verify the job doesn't exist
        self.assertFalse(Job.objects.filter(id=999).exists())


class ToLocalTestCase(TestCase):
    def test_to_local_conversion(self):
        from django.utils import timezone as django_timezone

        utc_time = django_timezone.now()

        # Don't mock get_current_timezone, let it return the actual timezone
        result = sutils.to_local(utc_time)

        self.assertIsInstance(result, str)
        self.assertRegex(result, r"\d{2}-\w{3}-\d{4} \d{2}:\d{2}")


class GetReadableDatesTestCase(TestCase):
    def test_get_readable_dates_list(self):
        dt_list = [datetime(2024, 1, 1, 8, 0), datetime(2024, 1, 2, 8, 0)]

        result = sutils.get_readable_dates(dt_list)

        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0], "01-Jan-2024 08:00")

    def test_get_readable_dates_not_list(self):
        dt = datetime(2024, 1, 1, 8, 0)

        result = sutils.get_readable_dates(dt)

        self.assertIsNone(result)
