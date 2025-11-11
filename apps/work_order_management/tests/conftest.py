"""
Test configuration and fixtures for work_order_management app.

Provides reusable fixtures for testing work orders, work permits,
vendors, approval workflows, and scheduling.
"""
import pytest
from datetime import datetime, timezone as dt_timezone, timedelta
from django.test import RequestFactory, Client
from django.contrib.auth import get_user_model
from django.contrib.gis.geos import Point
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
    """Create a test tenant (business unit) for work orders."""
    return Bt.objects.create(
        bucode="TESTWOM",
        buname="Work Order Test Tenant",
        enable=True
    )


@pytest.fixture
def test_location(test_tenant):
    """Create a test location for work orders."""
    return Location.objects.create(
        site="WO_SITE",
        location="Work Order Test Location",
        client=test_tenant,
        bu=test_tenant,
        gpslocation=Point(103.8198, 1.3521)  # Singapore coordinates
    )


@pytest.fixture
def test_asset(test_tenant, test_location):
    """Create a test asset for work order assignments."""
    return Asset.objects.create(
        assetname="Test HVAC Unit",
        assetcode="HVAC001",
        location=test_location,
        client=test_tenant,
        bu=test_tenant,
        enable=True
    )


@pytest.fixture
def test_vendor_type(test_tenant):
    """Create a vendor type TypeAssist."""
    return TypeAssist.objects.create(
        typename="VendorType",
        typeval="HVAC Contractor",
        client=test_tenant,
        enable=True
    )


@pytest.fixture
def test_vendor(test_tenant, test_vendor_type):
    """Create a test vendor for work order assignments."""
    from apps.work_order_management.models import Vendor

    return Vendor.objects.create(
        code="VENDOR001",
        name="Test HVAC Vendor",
        type=test_vendor_type,
        mobno="1234567890",
        email="vendor@example.com",
        client=test_tenant,
        bu=test_tenant,
        enable=True,
        gpslocation=Point(103.8198, 1.3521)
    )


@pytest.fixture
def test_question_set(test_tenant):
    """Create a test question set for work order checklist."""
    return QuestionSet.objects.create(
        qsetname="HVAC Maintenance Checklist",
        client=test_tenant,
        bu=test_tenant,
        enable=True
    )


@pytest.fixture
def test_user(test_tenant):
    """Create a test user for work order operations."""
    user = User.objects.create(
        peoplecode="WOUSER001",
        peoplename="WO Test User",
        loginid="wouser",
        email="wouser@example.com",
        mobno="9999999999",
        client=test_tenant,
        enable=True
    )
    user.set_password("WOPass123!")
    user.save()
    return user


@pytest.fixture
def test_approver(test_tenant):
    """Create a test approver user."""
    approver = User.objects.create(
        peoplecode="APPROVER001",
        peoplename="Test Approver",
        loginid="approver",
        email="approver@example.com",
        mobno="8888888888",
        client=test_tenant,
        enable=True
    )
    approver.set_password("ApproverPass123!")
    approver.save()
    return approver


@pytest.fixture
def test_verifier(test_tenant):
    """Create a test verifier user."""
    verifier = User.objects.create(
        peoplecode="VERIFIER001",
        peoplename="Test Verifier",
        loginid="verifier",
        email="verifier@example.com",
        mobno="7777777777",
        client=test_tenant,
        enable=True
    )
    verifier.set_password("VerifierPass123!")
    verifier.save()
    return verifier


@pytest.fixture
def basic_work_order(test_tenant, test_location, test_asset, test_vendor, test_question_set, test_user):
    """
    Create a basic work order with minimal configuration.

    Status: ASSIGNED
    Type: WO (work order, not work permit)
    """
    from apps.work_order_management.models import Wom

    return Wom.objects.create(
        name="Basic Test Work Order",
        workstatus="ASSIGNED",
        identifier="WO",
        asset=test_asset,
        location=test_location,
        qset=test_question_set,
        vendor=test_vendor,
        priority="MEDIUM",
        plandatetime=datetime.now(dt_timezone.utc) + timedelta(days=1),
        expirydatetime=datetime.now(dt_timezone.utc) + timedelta(days=7),
        client=test_tenant,
        bu=test_tenant,
        gpslocation=Point(103.8198, 1.3521),
        workpermit="NOT_REQUIRED",
        cdby=test_user,
        mdby=test_user
    )


@pytest.fixture
def work_permit_order(test_tenant, test_location, test_asset, test_vendor, test_question_set, test_user, test_approver, test_verifier):
    """
    Create a work order that requires work permit approval.

    Status: ASSIGNED
    Type: WP (work permit)
    Includes approvers and verifiers
    """
    from apps.work_order_management.models import Wom

    return Wom.objects.create(
        name="Test Work Permit Order",
        workstatus="ASSIGNED",
        identifier="WP",
        asset=test_asset,
        location=test_location,
        qset=test_question_set,
        vendor=test_vendor,
        priority="HIGH",
        plandatetime=datetime.now(dt_timezone.utc) + timedelta(days=1),
        expirydatetime=datetime.now(dt_timezone.utc) + timedelta(days=3),
        client=test_tenant,
        bu=test_tenant,
        gpslocation=Point(103.8198, 1.3521),
        workpermit="REQUIRED",
        approvers=[test_approver.id],
        verifiers=[test_verifier.id],
        cdby=test_user,
        mdby=test_user
    )


@pytest.fixture
def completed_work_order(basic_work_order, test_user):
    """
    Create a completed work order for testing closure workflow.

    Status: COMPLETED
    Ready for verification
    """
    basic_work_order.workstatus = "COMPLETED"
    basic_work_order.starttime = datetime.now(dt_timezone.utc) - timedelta(hours=2)
    basic_work_order.endtime = datetime.now(dt_timezone.utc)
    basic_work_order.save()
    return basic_work_order


@pytest.fixture
def overdue_work_order(test_tenant, test_location, test_asset, test_vendor, test_question_set, test_user):
    """
    Create an overdue work order for testing escalation logic.

    Status: ASSIGNED
    Expiry: 2 days ago
    """
    from apps.work_order_management.models import Wom

    return Wom.objects.create(
        name="Overdue Work Order",
        workstatus="ASSIGNED",
        identifier="WO",
        asset=test_asset,
        location=test_location,
        qset=test_question_set,
        vendor=test_vendor,
        priority="HIGH",
        plandatetime=datetime.now(dt_timezone.utc) - timedelta(days=5),
        expirydatetime=datetime.now(dt_timezone.utc) - timedelta(days=2),
        client=test_tenant,
        bu=test_tenant,
        workpermit="NOT_REQUIRED",
        cdby=test_user,
        mdby=test_user
    )


@pytest.fixture
def authenticated_request(rf, test_user, test_tenant):
    """
    Create an authenticated HTTP request with session data.

    Includes user and tenant context for work order operations.
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
