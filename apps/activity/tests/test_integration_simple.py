"""
Simplified integration tests for Activity app
Tests basic model creation and relationships without complex dependencies
"""
import pytest
from django.utils import timezone
from datetime import date, timedelta
from apps.peoples.models import People
from apps.activity.models.job_model import Job, Jobneed
from apps.activity.models.asset_model import Asset


@pytest.mark.django_db
class TestSimpleJobWorkflow:
    """Test basic job workflow without complex dependencies"""

    def test_create_simple_job(self):
        """Test creating a basic job"""
        # Create a user
        user = People.objects.create_user(
            loginid='testuser',
            peoplecode='TEST001',
            peoplename='Test User',
            email='test@example.com',
            dateofbirth=date(1990, 1, 1),
            password='TestPass123!'
        )

        # Create a job
        job = Job.objects.create(
            jobname="Test Job",
            jobdesc="A test job description",
            fromdate=timezone.now(),
            uptodate=timezone.now() + timedelta(days=1),
            planduration=60,
            gracetime=30,
            expirytime=120,
            seqno=1
        )

        assert job.id is not None
        assert job.jobname == "Test Job"

    def test_create_jobneed(self):
        """Test creating a jobneed (task instance)"""
        # Create a user
        user = People.objects.create_user(
            loginid='testuser2',
            peoplecode='TEST002',
            peoplename='Test User 2',
            email='test2@example.com',
            dateofbirth=date(1990, 1, 1),
            password='TestPass123!'
        )

        # Create a job
        job = Job.objects.create(
            jobname="Test Job 2",
            jobdesc="Another test job",
            fromdate=timezone.now(),
            uptodate=timezone.now() + timedelta(days=1),
            planduration=60,
            gracetime=30,
            expirytime=120,
            seqno=1
        )

        # Create a jobneed
        jobneed = Jobneed.objects.create(
            jobdesc=job.jobdesc,
            plandatetime=timezone.now() + timedelta(hours=1),
            expirydatetime=timezone.now() + timedelta(hours=2),
            gracetime=30,
            job=job,
            jobstatus="ASSIGNED",
            jobtype="ADHOC",
            priority="MEDIUM",
            people=user,
            seqno=1
        )

        assert jobneed.id is not None
        assert jobneed.jobstatus == "ASSIGNED"
        assert jobneed.people == user

    def test_job_status_changes(self):
        """Test changing job status through workflow"""
        # Create a user
        user = People.objects.create_user(
            loginid='testuser3',
            peoplecode='TEST003',
            peoplename='Test User 3',
            email='test3@example.com',
            dateofbirth=date(1990, 1, 1),
            password='TestPass123!'
        )

        # Create a job
        job = Job.objects.create(
            jobname="Status Test Job",
            jobdesc="Testing status changes",
            fromdate=timezone.now(),
            uptodate=timezone.now() + timedelta(days=1),
            planduration=60,
            gracetime=30,
            expirytime=120,
            seqno=1
        )

        # Create a jobneed
        jobneed = Jobneed.objects.create(
            jobdesc=job.jobdesc,
            plandatetime=timezone.now() + timedelta(hours=1),
            expirydatetime=timezone.now() + timedelta(hours=2),
            gracetime=30,
            job=job,
            jobstatus="ASSIGNED",
            jobtype="ADHOC",
            priority="HIGH",
            people=user,
            seqno=1
        )

        # Test status progression
        assert jobneed.jobstatus == "ASSIGNED"

        # Start the job
        jobneed.jobstatus = "INPROGRESS"
        jobneed.starttime = timezone.now()
        jobneed.save()

        jobneed.refresh_from_db()
        assert jobneed.jobstatus == "INPROGRESS"
        assert jobneed.starttime is not None

        # Complete the job
        jobneed.jobstatus = "COMPLETED"
        jobneed.endtime = timezone.now()
        jobneed.save()

        jobneed.refresh_from_db()
        assert jobneed.jobstatus == "COMPLETED"
        assert jobneed.endtime is not None


@pytest.mark.django_db
class TestSimpleAssetWorkflow:
    """Test basic asset operations"""

    def test_create_asset(self):
        """Test creating a basic asset"""
        asset = Asset.objects.create(
            assetcode="ASSET001",
            assetname="Test Asset",
            iscritical=True,
            enable=True
        )

        assert asset.id is not None
        assert asset.assetcode == "ASSET001"
        assert asset.iscritical is True

    def test_asset_hierarchy(self):
        """Test asset parent-child relationships"""
        # Create parent asset
        parent = Asset.objects.create(
            assetcode="PARENT001",
            assetname="Parent Asset",
            iscritical=True
        )

        # Create child asset
        child = Asset.objects.create(
            assetcode="CHILD001",
            assetname="Child Asset",
            parent=parent,
            iscritical=False
        )

        assert child.parent == parent
        assert child.parent.assetcode == "PARENT001"

    def test_asset_status_changes(self):
        """Test asset running status changes"""
        asset = Asset.objects.create(
            assetcode="STATUS001",
            assetname="Status Test Asset",
            iscritical=True,
            runningstatus="WORKING"
        )

        assert asset.runningstatus == "WORKING"

        # Change to maintenance
        asset.runningstatus = "MAINTENANCE"
        asset.save()

        asset.refresh_from_db()
        assert asset.runningstatus == "MAINTENANCE"