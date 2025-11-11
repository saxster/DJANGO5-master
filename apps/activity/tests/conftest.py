"""
Test configuration and fixtures for activity app.

Provides reusable fixtures for testing tasks (Job/Jobneed), tours,
job assignments, assets, and location-based operations.
"""
import pytest
from datetime import datetime, timezone as dt_timezone, timedelta
from django.test import RequestFactory, Client
from django.contrib.auth import get_user_model
from django.contrib.gis.geos import Point, LineString
from apps.client_onboarding.models import Bt
from apps.core_onboarding.models import TypeAssist
from apps.activity.models import Location, Asset, QuestionSet

User = get_user_model()


@pytest.fixture
def rf():
    """Request factory for creating mock HTTP requests."""
    return RequestFactory()


@pytest.fixture
def client():
    """Django test client for integration tests."""
    return Client()


@pytest.fixture
def test_tenant():
    """Create a test tenant (business unit) for activity tests."""
    return Bt.objects.create(
        bucode="TESTACT",
        buname="Activity Test Tenant",
        enable=True
    )


@pytest.fixture
def test_location(test_tenant):
    """Create a test location for activities."""
    return Location.objects.create(
        site="ACT_SITE",
        location="Activity Test Location",
        client=test_tenant,
        bu=test_tenant,
        gpslocation=Point(103.8198, 1.3521)  # Singapore coordinates
    )


@pytest.fixture
def test_asset_type(test_tenant):
    """Create an asset type TypeAssist."""
    return TypeAssist.objects.create(
        typename="AssetType",
        typeval="HVAC System",
        client=test_tenant,
        enable=True
    )


@pytest.fixture
def test_asset_category(test_tenant):
    """Create an asset category TypeAssist."""
    return TypeAssist.objects.create(
        typename="AssetCategory",
        typeval="Mechanical",
        client=test_tenant,
        enable=True
    )


@pytest.fixture
def test_asset(test_tenant, test_location, test_asset_type, test_asset_category):
    """Create a test asset."""
    return Asset.objects.create(
        assetname="Test HVAC Unit",
        assetcode="HVAC001",
        location=test_location,
        client=test_tenant,
        bu=test_tenant,
        type=test_asset_type,
        category=test_asset_category,
        enable=True,
        gpslocation=Point(103.8198, 1.3521),
        runningstatus="WORKING",
        iscritical=False
    )


@pytest.fixture
def critical_asset(test_tenant, test_location, test_asset_type, test_asset_category):
    """Create a critical asset for priority testing."""
    return Asset.objects.create(
        assetname="Critical Fire Pump",
        assetcode="PUMP001",
        location=test_location,
        client=test_tenant,
        bu=test_tenant,
        type=test_asset_type,
        category=test_asset_category,
        enable=True,
        gpslocation=Point(103.8198, 1.3521),
        runningstatus="WORKING",
        iscritical=True
    )


@pytest.fixture
def test_question_set(test_tenant):
    """Create a test question set for job checklists."""
    return QuestionSet.objects.create(
        qsetname="Standard Inspection Checklist",
        client=test_tenant,
        bu=test_tenant,
        enable=True
    )


@pytest.fixture
def test_user(test_tenant):
    """Create a test user for activity operations."""
    user = User.objects.create(
        peoplecode="ACTUSER001",
        peoplename="Activity Test User",
        loginid="actuser",
        email="actuser@example.com",
        mobno="9999999999",
        client=test_tenant,
        enable=True
    )
    user.set_password("ActPass123!")
    user.save()
    return user


@pytest.fixture
def test_job(test_tenant, test_asset, test_question_set, test_user):
    """
    Create a basic job (task template) for testing.

    Job represents the template/definition of recurring work.
    """
    from apps.activity.models import Job
    from django.utils import timezone

    return Job.objects.create(
        jobname="Daily Inspection",
        jobdesc="Daily inspection task",
        fromdate=timezone.now(),
        uptodate=timezone.now() + timedelta(days=365),
        cron="0 8 * * *",
        identifier="TASK",
        planduration=60,
        gracetime=15,
        expirytime=120,
        priority="MEDIUM",
        scantype="QR",
        frequency="NONE",
        asset=test_asset,
        qset=test_question_set,
        client=test_tenant,
        bu=test_tenant,
        seqno=1,
        enable=True,
        cdby=test_user,
        mdby=test_user
    )


@pytest.fixture
def test_jobneed(test_job, test_user):
    """
    Create a jobneed (concrete job instance) for testing.

    Jobneed represents a scheduled execution of a job.
    """
    from apps.activity.models import Jobneed
    from django.utils import timezone

    return Jobneed.objects.create(
        jobname="Daily Inspection - 2025-11-04",
        jobdesc=test_job.jobdesc,
        job=test_job,
        jobdate=timezone.now().date(),
        starttime=timezone.now() + timedelta(hours=1),
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


@pytest.fixture
def completed_jobneed(test_job, test_user):
    """Create a completed jobneed for testing closure workflows."""
    from apps.activity.models import Jobneed
    from django.utils import timezone

    return Jobneed.objects.create(
        jobname="Completed Inspection",
        jobdesc=test_job.jobdesc,
        job=test_job,
        jobdate=timezone.now().date() - timedelta(days=1),
        starttime=timezone.now() - timedelta(hours=3),
        endtime=timezone.now() - timedelta(hours=2),
        jobstatus="COMPLETED",
        priority=test_job.priority,
        scantype=test_job.scantype,
        gracetime=test_job.gracetime,
        seqno=1,
        client=test_job.client,
        bu=test_job.bu,
        cdby=test_user,
        mdby=test_user
    )


@pytest.fixture
def test_tour_job(test_tenant, test_question_set, test_user):
    """
    Create a tour job (parent job with checkpoints).

    Tour jobs have parent=NULL and child checkpoint jobs.
    """
    from apps.activity.models import Job
    from django.utils import timezone

    return Job.objects.create(
        jobname="Building A Security Tour",
        jobdesc="Security patrol tour",
        fromdate=timezone.now(),
        uptodate=timezone.now() + timedelta(days=365),
        cron="0 8 * * *",
        identifier="INTERNALTOUR",
        planduration=120,
        gracetime=15,
        expirytime=180,
        priority="HIGH",
        scantype="NFC",
        frequency="DAILY",
        qset=test_question_set,
        client=test_tenant,
        bu=test_tenant,
        parent=None,  # Root tour
        seqno=1,
        enable=True,
        cdby=test_user,
        mdby=test_user
    )


@pytest.fixture
def checkpoint_job(test_tour_job, test_asset, test_user):
    """
    Create a checkpoint job (child of tour).

    Checkpoint jobs have parent=tour_job.
    """
    from apps.activity.models import Job

    return Job.objects.create(
        jobname="Floor 1 Checkpoint",
        jobdesc="Checkpoint inspection",
        fromdate=test_tour_job.fromdate,
        uptodate=test_tour_job.uptodate,
        cron=test_tour_job.cron,
        identifier="TASK",
        planduration=30,
        gracetime=test_tour_job.gracetime,
        expirytime=test_tour_job.expirytime,
        priority=test_tour_job.priority,
        scantype=test_tour_job.scantype,
        frequency=test_tour_job.frequency,
        asset=test_asset,
        qset=test_tour_job.qset,
        client=test_tour_job.client,
        bu=test_tour_job.bu,
        parent=test_tour_job,  # Child of tour
        seqno=1,
        enable=True,
        cdby=test_user,
        mdby=test_user
    )


@pytest.fixture
def authenticated_request(rf, test_user, test_tenant):
    """
    Create an authenticated HTTP request with session data.

    Includes user and tenant context for activity operations.
    """
    from django.contrib.sessions.middleware import SessionMiddleware

    request = rf.get("/")
    middleware = SessionMiddleware(lambda req: None)
    middleware.process_request(request)
    request.session.save()

    # Set session data
    request.session["client_id"] = test_tenant.id
    request.session["bu_id"] = test_tenant.id
    request.session["user_id"] = test_user.id
    request.user = test_user

    return request
