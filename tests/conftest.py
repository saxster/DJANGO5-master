"""
Simplified test fixtures for YOUTILITY5
Provides basic fixtures without complex factory dependencies
"""
import pytest
from django.test import RequestFactory, Client
from django.contrib.auth import get_user_model
from django.contrib.sessions.middleware import SessionMiddleware
from datetime import date

User = get_user_model()


@pytest.fixture
def rf():
    """Request factory for creating mock requests"""
    return RequestFactory()


@pytest.fixture
def client():
    """Django test client"""
    return Client()


@pytest.fixture
def regular_user(db):
    """Create a regular test user"""
    from apps.peoples.models import People

    user = People.objects.create_user(
        loginid='testuser',
        peoplecode='TEST001',
        peoplename='Test User',
        email='test@example.com',
        dateofbirth=date(1990, 1, 1),
        password='TestPass123!'
    )
    user.isverified = True
    user.people_extras = {"userfor": "Web"}
    user.save()
    return user


@pytest.fixture
def admin_user(db):
    """Create an admin test user"""
    from apps.peoples.models import People

    user = People.objects.create_user(
        loginid='adminuser',
        peoplecode='ADMIN001',
        peoplename='Admin User',
        email='admin@example.com',
        dateofbirth=date(1980, 1, 1),
        password='AdminPass123!',
        is_staff=True,
        is_superuser=True
    )
    user.isverified = True
    user.isadmin = True
    user.people_extras = {"userfor": "Web"}
    user.save()
    return user


@pytest.fixture
def authenticated_client(client, regular_user):
    """Client authenticated with regular user"""
    client.force_login(regular_user)
    return client


@pytest.fixture
def admin_client(client, admin_user):
    """Client authenticated with admin user"""
    client.force_login(admin_user)
    return client


@pytest.fixture
def mock_request(rf, regular_user):
    """Mock request with authenticated user and session"""
    request = rf.get('/')
    request.user = regular_user

    # Add session middleware
    middleware = SessionMiddleware(lambda req: None)
    middleware.process_request(request)
    request.session.save()

    # Add session data
    request.session['user_id'] = regular_user.id
    request.session['session_key'] = 'test_session_key'

    return request


@pytest.fixture
def client_type_assist(db):
    """Create TypeAssist instance for CLIENT type"""
    from apps.onboarding.models import TypeAssist
    return TypeAssist.objects.create(
        tacode='CLIENT',
        taname='Client'
    )


@pytest.fixture
def bu_type_assist(db):
    """Create TypeAssist instance for BU type"""
    from apps.onboarding.models import TypeAssist
    return TypeAssist.objects.create(
        tacode='BU',
        taname='Business Unit'
    )


@pytest.fixture
def department_type_assist(db):
    """Create TypeAssist instance for DEPARTMENT type"""
    from apps.onboarding.models import TypeAssist
    return TypeAssist.objects.create(
        tacode='DEPARTMENT',
        taname='Department'
    )


@pytest.fixture
def designation_type_assist(db):
    """Create TypeAssist instance for DESIGNATION type"""
    from apps.onboarding.models import TypeAssist
    return TypeAssist.objects.create(
        tacode='DESIGNATION',
        taname='Designation'
    )


@pytest.fixture
def test_client_org(db, client_type_assist):
    """Create a test client organization"""
    from apps.onboarding.models import Bt

    return Bt.objects.create(
        bucode='TESTCLIENT',
        buname='Test Client',
        butype=client_type_assist
    )


@pytest.fixture
def test_bu(db, test_client_org, bu_type_assist):
    """Create a test business unit"""
    from apps.onboarding.models import Bt

    return Bt.objects.create(
        bucode='TESTBU',
        buname='Test Business Unit',
        butype=bu_type_assist,
        parent=test_client_org
    )


@pytest.fixture
def test_tenant(db):
    """Create a test tenant"""
    from apps.tenants.models import Tenant
    return Tenant.objects.create(
        tenantname='Test Tenant',
        subdomain_prefix='test'
    )


@pytest.fixture
def client_bt(db, client_type_assist, test_tenant):
    """Alias for test_client_org with tenant support for form tests"""
    from apps.onboarding.models import Bt
    return Bt.objects.create(
        bucode='TESTCLIENT',
        buname='Test Client',
        butype=client_type_assist,
        tenant=test_tenant
    )


@pytest.fixture
def bu_bt(db, client_bt, bu_type_assist, test_tenant):
    """Alias for test_bu with tenant support for form tests"""
    from apps.onboarding.models import Bt
    return Bt.objects.create(
        bucode='TESTBU',
        buname='Test Business Unit',
        butype=bu_type_assist,
        parent=client_bt,
        tenant=test_tenant
    )


# Pytest configuration
def pytest_configure(config):
    """Configure pytest with custom marks"""
    config.addinivalue_line("markers", "unit: mark test as unit test")
    config.addinivalue_line("markers", "integration: mark test as integration test")
    config.addinivalue_line("markers", "security: mark test as security test")
    config.addinivalue_line("markers", "performance: mark test as performance test")
    config.addinivalue_line("markers", "slow: mark test as slow running")


@pytest.fixture(autouse=True)
def enable_db_access_for_all_tests(db):
    """
    Enable database access for all tests.
    This fixture is automatically used for all tests.
    """
    pass