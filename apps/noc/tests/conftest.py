"""
NOC Tests Configuration and Fixtures.

Pytest fixtures for NOC module testing.
"""

import pytest
from datetime import timedelta
from django.utils import timezone
from rest_framework.test import APIClient
from apps.tenants.models import Tenant
from apps.peoples.models import People
from apps.onboarding.models import Bt, Tacode
from apps.noc.models import NOCAlertEvent, NOCIncident, NOCMetricSnapshot


@pytest.fixture
def tenant():
    """Create test tenant."""
    return Tenant.objects.create(
        domain_url='test.example.com',
        schema_name='public',
        name='Test Tenant'
    )


@pytest.fixture
def mock_user(tenant, db):
    """Create mock user with basic NOC capability."""
    user = People.objects.create_user(
        loginid='testuser',
        email='test@example.com',
        peoplename='Test User',
        tenant=tenant
    )
    user.capabilities = {'noc:view': True}
    user.save()
    return user


@pytest.fixture
def admin_user(tenant, db):
    """Create admin user with all permissions."""
    user = People.objects.create_superuser(
        loginid='admin',
        email='admin@example.com',
        peoplename='Admin User',
        tenant=tenant
    )
    user.capabilities = {'noc:view': True, 'noc:view_pii': True, 'noc:view_all_clients': True}
    user.save()
    return user


@pytest.fixture
def user_without_pii_permission(tenant, db):
    """Create user without PII view permission."""
    user = People.objects.create_user(
        loginid='nopii',
        email='nopii@example.com',
        peoplename='No PII User',
        tenant=tenant
    )
    user.capabilities = {'noc:view': True}
    user.save()
    return user


@pytest.fixture
def client_tacode(db):
    """Create CLIENT tacode."""
    return Tacode.objects.get_or_create(
        tacode='CLIENT',
        defaults={'taname': 'Client'}
    )[0]


@pytest.fixture
def sample_client(tenant, client_tacode, db):
    """Create sample client business unit."""
    return Bt.objects.create(
        tenant=tenant,
        bucode='TEST001',
        buname='Test Client',
        identifier=client_tacode
    )


@pytest.fixture
def sample_site(tenant, sample_client, db):
    """Create sample site business unit."""
    return Bt.objects.create(
        tenant=tenant,
        bucode='SITE001',
        buname='Test Site',
        parent=sample_client
    )


@pytest.fixture
def sample_alert(tenant, sample_client, sample_site, db):
    """Create sample alert event."""
    return NOCAlertEvent.objects.create(
        tenant=tenant,
        client=sample_client,
        bu=sample_site,
        alert_type='SLA_BREACH',
        severity='HIGH',
        status='NEW',
        dedup_key='test_alert_001',
        message='Test SLA breach alert',
        entity_type='ticket',
        entity_id=1,
        metadata={}
    )


@pytest.fixture
def sample_alert_with_assignee(sample_alert, mock_user, db):
    """Create alert with assigned user."""
    sample_alert.acknowledged_by = mock_user
    sample_alert.acknowledged_at = timezone.now()
    sample_alert.save()
    return sample_alert


@pytest.fixture
def multiple_alerts(tenant, sample_client, sample_site, db):
    """Create multiple alerts."""
    alerts = []
    for i in range(5):
        alert = NOCAlertEvent.objects.create(
            tenant=tenant,
            client=sample_client,
            bu=sample_site,
            alert_type='DEVICE_OFFLINE' if i % 2 == 0 else 'SLA_BREACH',
            severity='CRITICAL' if i < 2 else 'MEDIUM',
            status='NEW',
            dedup_key=f'alert_{i}',
            message=f'Test alert {i}',
            entity_type='device',
            entity_id=i,
            metadata={}
        )
        alerts.append(alert)
    return alerts


@pytest.fixture
def sample_metrics(tenant, sample_client, sample_site, db):
    """Create sample metric snapshot."""
    return NOCMetricSnapshot.objects.create(
        tenant=tenant,
        client=sample_client,
        bu=sample_site,
        window_start=timezone.now() - timedelta(hours=1),
        window_end=timezone.now(),
        tickets_open=10,
        tickets_overdue=2,
        work_orders_pending=5,
        attendance_present=50,
        attendance_expected=60,
        device_health_online=95,
        device_health_offline=5
    )


@pytest.fixture
def client_with_noc_capability(mock_user):
    """Create API client with NOC capability."""
    client = APIClient()
    client.force_authenticate(user=mock_user)
    return client


@pytest.fixture
def client_with_ack_permission(tenant, db):
    """Create API client with acknowledgment permission."""
    user = People.objects.create_user(
        loginid='ackuser',
        email='ack@example.com',
        peoplename='Ack User',
        tenant=tenant
    )
    user.capabilities = {'noc:view': True, 'noc:ack_alerts': True}
    user.save()

    client = APIClient()
    client.force_authenticate(user=user)
    return client


@pytest.fixture
def client_with_user_no_capability(tenant, db):
    """Create API client without NOC capabilities."""
    user = People.objects.create_user(
        loginid='nocap',
        email='nocap@example.com',
        peoplename='No Cap User',
        tenant=tenant
    )
    client = APIClient()
    client.force_authenticate(user=user)
    return client


@pytest.fixture
def noc_alert_event(tenant, sample_client, sample_site, db):
    """
    Create NOC alert event for testing.

    Added for TASK 11: Consolidated event feed tests.
    """
    return NOCAlertEvent.objects.create(
        tenant=tenant,
        client=sample_client,
        bu=sample_site,
        alert_type='FRAUD_ALERT',
        severity='HIGH',
        status='NEW',
        dedup_key='fraud_alert_001',
        message='High fraud probability detected',
        entity_type='attendance',
        entity_id=123,
        metadata={
            'fraud_score': 0.85,
            'detection_method': 'ML_PREDICTION'
        }
    )