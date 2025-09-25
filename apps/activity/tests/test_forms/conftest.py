"""
Shared fixtures for activity form tests
"""
import pytest
import uuid
from apps.onboarding.models import Bt, TypeAssist
from apps.activity.models.asset_model import Asset
from apps.activity.models.location_model import Location


@pytest.fixture
def asset_type(db):
    """Create an asset type"""
    return TypeAssist.objects.create(
        tacode="ASSET_TYPE",
        taname="Asset Type"
    )


@pytest.fixture
def location_type(db):
    """Create a location type"""
    return TypeAssist.objects.create(
        tacode="LOC_TYPE",
        taname="Location Type"
    )


@pytest.fixture
def client_bt(db):
    """Create a client BT instance"""
    client_type, _ = TypeAssist.objects.get_or_create(
        tacode="CLIENT",
        defaults={'taname': 'Client'}
    )
    return Bt.objects.create(
        bucode="CLIENT_BT",
        buname="Client BT",
        butype=client_type
    )


@pytest.fixture
def bu_bt(db):
    """Create a BU BT instance"""
    bu_type, _ = TypeAssist.objects.get_or_create(
        tacode="BU",
        defaults={'taname': 'Business Unit'}
    )
    return Bt.objects.create(
        bucode="BU_BT",
        buname="BU BT",
        butype=bu_type
    )


@pytest.fixture
def test_asset(db, client_bt, bu_bt, asset_type):
    """Create a test asset"""
    return Asset.objects.create(
        assetcode=f"ASSET_{uuid.uuid4().hex[:6]}",
        assetname="Test Asset",
        client=client_bt,
        bu=bu_bt,
        type=asset_type,
        enable=True,
        iscritical=False
    )


@pytest.fixture
def test_location(db, client_bt, bu_bt, location_type):
    """Create a test location"""
    return Location.objects.create(
        loccode=f"LOC_{uuid.uuid4().hex[:6]}",
        locname="Test Location",
        client=client_bt,
        bu=bu_bt,
        type=location_type,
        enable=True
    )