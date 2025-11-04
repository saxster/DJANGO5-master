"""
Pytest fixtures for Security Intelligence tests.
"""

import pytest
from datetime import datetime, timedelta
from django.utils import timezone
from django.contrib.gis.geos import Point


@pytest.fixture
def tenant(db):
    """Create test tenant."""
    from apps.tenants.models import Tenant
    return Tenant.objects.create(
        name='Test Tenant',
        schema_name='test_tenant',
        is_active=True
    )


@pytest.fixture
def client_bt(db, tenant):
    """Create test client business unit."""
    from apps.client_onboarding.models import Bt
    return Bt.objects.create(
        tenant=tenant,
        name='Test Client',
        bttype='CLIENT',
        enable=True
    )


@pytest.fixture
def site_bt(db, tenant, client_bt):
    """Create test site business unit."""
    from apps.client_onboarding.models import Bt
    return Bt.objects.create(
        tenant=tenant,
        name='Test Site',
        bttype='SITE',
        parent=client_bt,
        gpslocation=Point(77.5946, 12.9716),  # Bangalore coordinates
        enable=True
    )


@pytest.fixture
def test_person(db, tenant, site_bt):
    """Create test person."""
    from apps.peoples.models import People
    person = People.objects.create(
        tenant=tenant,
        loginid='testuser',
        peoplecode='TEST001',
        peoplename='Test User',
        email='test@example.com',
        isverified=True,
        enable=True
    )
    return person


@pytest.fixture
def other_person(db, tenant, site_bt):
    """Create another test person."""
    from apps.peoples.models import People
    person = People.objects.create(
        tenant=tenant,
        loginid='other',
        peoplecode='TEST002',
        peoplename='Other User',
        email='other@example.com',
        isverified=True,
        enable=True
    )
    return person


@pytest.fixture
def security_config(db, tenant, site_bt):
    """Create security anomaly configuration."""
    from apps.noc.security_intelligence.models import SecurityAnomalyConfig
    return SecurityAnomalyConfig.objects.create(
        tenant=tenant,
        scope='SITE',
        site=site_bt,
        is_active=True,
        max_continuous_work_hours=16,
        min_travel_time_minutes=30,
        max_travel_speed_kmh=150,
        unauthorized_access_severity='CRITICAL',
        inactivity_detection_enabled=True,
        inactivity_window_minutes=120,
        inactivity_score_threshold=0.8
    )


@pytest.fixture
def attendance_event(db, tenant, site_bt, test_person):
    """Create test attendance event."""
    from apps.attendance.models import PeopleEventlog
    return PeopleEventlog.objects.create(
        tenant=tenant,
        people=test_person,
        bu=site_bt,
        datefor=timezone.now().date(),
        punchintime=timezone.now(),
        startlocation=Point(77.5946, 12.9716)
    )