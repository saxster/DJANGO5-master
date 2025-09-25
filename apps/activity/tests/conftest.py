import pytest
from apps.onboarding.models import Bt
from apps.activity.models.asset_model import Asset
from apps.activity.models.deviceevent_log_model import DeviceEventlog
from apps.activity.models.job_model import Job, Jobneed
from apps.activity.models.location_model import Location
from apps.activity.models.question_model import (
    Question,
    QuestionSet,
    QuestionSetBelonging,
)
from apps.peoples.models import People
import uuid


@pytest.fixture
def client_bt(db):
    from apps.tenants.models import Tenant
    from apps.onboarding.models import TypeAssist

    # Create tenant and type for the client
    tenant, _ = Tenant.objects.get_or_create(
        subdomain_prefix="test_client",
        defaults={"tenantname": "Test Client Tenant"}
    )

    client_type, _ = TypeAssist.objects.get_or_create(
        tacode="CLIENT_TYPE",
        defaults={"taname": "Client Type", "tenant": tenant}
    )

    return Bt.objects.create(
        bucode="TESTCLIENT",
        buname="Testing Client",
        enable=True,
        tenant=tenant,
        butype=client_type
    )


@pytest.fixture
def bu_bt(db, client_bt):
    from apps.onboarding.models import TypeAssist

    bu_type, _ = TypeAssist.objects.get_or_create(
        tacode="BU_TYPE",
        defaults={"taname": "BU Type", "tenant": client_bt.tenant}
    )

    return Bt.objects.create(
        bucode="TESTBU",
        buname="Testing BU",
        enable=True,
        tenant=client_bt.tenant,
        butype=bu_type,
        parent=client_bt
    )


@pytest.fixture
def asset_factory(db, client_bt, bu_bt):
    def _create(**kwargs):
        default = {
            "assetcode": "A001",
            "assetname": "Test Asset",
            "enable": True,
            "iscritical": True,
            "identifier": "ASSET",
            "runningstatus": "WORKING",
            "capacity": 100.00,
            "gpslocation": "POINT(12.9716 77.5946)",
            "client": client_bt,
            "bu": bu_bt,
        }
        default.update(kwargs)
        return Asset.objects.create(**default)

    return _create


@pytest.fixture
def deviceeventlog_factory(db, client_bt, bu_bt):
    def _create(**kwargs):
        default = {
            "deviceid": "1234567890",
            "eventvalue": "stepcount",
            "bu": bu_bt,
            "client": client_bt,
        }
        default.update(kwargs)
        return DeviceEventlog.objects.create(**default)

    return _create


@pytest.fixture
def job_factory(db, client_bt, bu_bt):
    def _create(**kwargs):
        default = {
            "jobname": "Test Job",
            "gracetime": 5,
            "priority": "LOW",
            "scantype": "SKIP",
            "seqno": 1,
            "client": client_bt,
            "bu": bu_bt,
            "fromdate": "2023-05-22 09:30:00+00",
            "uptodate": "2023-05-22 09:30:00+00",
            "planduration": 10,
            "expirytime": 10,
            "identifier": "TASK",
        }
        default.update(kwargs)
        return Job.objects.create(**default)

    return _create


@pytest.fixture
def jobneed_factory(db, client_bt, bu_bt):
    def _create(**kwargs):
        default = {
            "jobdesc": "Test Job",
            "gracetime": 5,
            "receivedonserver": "2023-05-22 09:30:00+00",
            "priority": "LOW",
            "scantype": "SKIP",
            "seqno": 1,
            "client": client_bt,
            "bu": bu_bt,
        }
        default.update(kwargs)
        return Jobneed.objects.create(**default)

    return _create


@pytest.fixture
def location_factory(db, client_bt, bu_bt):
    def _create(**kwargs):
        default = {
            "loccode": "LOC001",
            "locname": "Test Location",
            "enable": True,
            "iscritical": True,
            "gpslocation": "POINT(12.9716 77.5946)",
            "client": client_bt,
            "bu": bu_bt,
        }
        default.update(kwargs)
        return Location.objects.create(**default)

    return _create


@pytest.fixture
def question_factory(db):
    def _create(**kwargs):
        default = {
            "quesname": "Test Question",
            "enable": True,
            "answertype": "NUMERIC",
            "isavpt": True,
        }
        default.update(kwargs)
        return Question.objects.create(**default)

    return _create


@pytest.fixture
def questionset_factory(db, client_bt, bu_bt):
    def _create(**kwargs):
        default = {
            "qsetname": "Test Question Set",
            "enable": True,
            "client": client_bt,
            "bu": bu_bt,
            "seqno": 1,
            "show_to_all_sites": True,
        }
        default.update(kwargs)
        return QuestionSet.objects.create(**default)

    return _create


@pytest.fixture
def questionsetbelonging_factory(db, client_bt, bu_bt):
    def _create(**kwargs):
        default = {
            "qset": QuestionSet.objects.create(
                qsetname="Test Question Set",
                enable=True,
                client=client_bt,
                bu=bu_bt,
                seqno=1,
                show_to_all_sites=True,
            ),
            "question": Question.objects.create(
                quesname="Test Question",
                enable=True,
                client=client_bt,
                bu=bu_bt,
                answertype="NUMERIC",
                isavpt="VIDEO",
            ),
            "enable": True,
            "client": client_bt,
            "bu": bu_bt,
            "seqno": 1,
            "isavpt": True,
            "avpttype": "VIDEO",
        }
        default.update(kwargs)
        return QuestionSetBelonging.objects.create(**default)

    return _create


@pytest.fixture
def people_factory(db, client_bt, bu_bt):
    def _create(**kwargs):
        default = {
            "peoplecode": f"P_{uuid.uuid4().hex[:6]}",
            "peoplename": "Test User",
            "bu": bu_bt,
            "client": client_bt,
            "email": "testpeople@gmail.com",
            "dateofbirth": "2023-05-22",
            "dateofjoin": "2023-05-22",
            "mobno": "+919876543210",
        }
        default.update(kwargs)
        return People.objects.create(**default)

    return _create
