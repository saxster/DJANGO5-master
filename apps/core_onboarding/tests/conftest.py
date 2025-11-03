import pytest
from django.contrib.auth import get_user_model

People = get_user_model()


@pytest.fixture
def test_user(db):
    """Create test user"""
    return People.objects.create_user(
        peoplecode='TEST001',
        loginid='testuser',
        peoplename='Test User',
        email='test@example.com'
    )


@pytest.fixture
def test_client(db):
    """Create test client (will be in client_onboarding later)"""
    from apps.onboarding.models import Bt
    return Bt.objects.create(
        bucode='TESTCLIENT',
        buname='Test Client'
    )
