"""
Shared fixtures for peoples form tests
"""
import pytest
import uuid
from django.contrib.auth import get_user_model
from apps.onboarding.models import Bt, TypeAssist

People = get_user_model()


@pytest.fixture
def test_password():
    """Test password fixture"""
    return "TestPass123!"


@pytest.fixture
def bt_factory(db):
    """Factory for creating Bt instances"""
    def _create(**kwargs):
        defaults = {
            "bucode": f"BT_{uuid.uuid4().hex[:6]}",
            "buname": "Test BT",
        }
        defaults.update(kwargs)
        return Bt.objects.create(**defaults)
    return _create


@pytest.fixture
def client_bt(bt_factory):
    """Create a client BT instance"""
    client_type, _ = TypeAssist.objects.get_or_create(
        tacode="CLIENT",
        defaults={'taname': 'Client'}
    )
    bt = bt_factory(bucode="CLIENT_BT", buname="Client BT")
    bt.butype = client_type
    bt.save()
    return bt


@pytest.fixture
def bu_bt(bt_factory):
    """Create a BU BT instance"""
    bu_type, _ = TypeAssist.objects.get_or_create(
        tacode="BU",
        defaults={'taname': 'Business Unit'}
    )
    bt = bt_factory(bucode="BU_BT", buname="BU BT")
    bt.butype = bu_type
    bt.save()
    return bt


@pytest.fixture
def people_factory(db, client_bt, bu_bt):
    """Factory for creating People instances"""
    def _create(**kwargs):
        defaults = {
            "peoplecode": f"TEST{uuid.uuid4().hex[:3].upper()}",
            "peoplename": "Test Person",
            "loginid": f"testuser_{uuid.uuid4().hex[:6]}",
            "email": f"test_{uuid.uuid4().hex[:6]}@example.com",
            "mobno": "1234567890",
            "client": client_bt,
            "bu": bu_bt,
            "isverified": True,
            "enable": True,
            "dateofbirth": "1990-01-01",
            "dateofjoin": "2023-01-01",
            "gender": "M",
            "password": "TestPass123",
        }
        defaults.update(kwargs)

        # Extract password if provided
        password = defaults.pop('password', 'TestPass123')

        # Create the user
        user = People.objects.create(**defaults)
        user.set_password(password)
        user.save()

        return user
    return _create


@pytest.fixture
def authenticated_user(people_factory):
    """Create an authenticated user"""
    return people_factory(
        loginid="authuser",
        email="authuser@example.com",
        peoplecode="AUTH001"
    )


@pytest.fixture
def admin_user(people_factory):
    """Create an admin user"""
    return people_factory(
        loginid="adminuser",
        email="admin@example.com",
        peoplecode="ADMIN001",
        is_staff=True,
        is_superuser=True
    )