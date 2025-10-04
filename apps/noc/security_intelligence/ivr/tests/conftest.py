"""
Pytest fixtures for IVR tests.
"""

import pytest
from decimal import Decimal


@pytest.fixture
def ivr_provider_config(db, tenant):
    """Create mock IVR provider config."""
    from apps.noc.security_intelligence.ivr.models import IVRProviderConfig

    return IVRProviderConfig.objects.create(
        tenant=tenant,
        provider_type='MOCK',
        is_active=True,
        is_primary=True,
        priority=1,
        credentials={},
        rate_limit_per_hour=100,
        max_daily_calls=500,
        monthly_budget=Decimal('5000.00'),
        cost_per_call=Decimal('0.00'),
    )


@pytest.fixture
def voice_script_template(db, tenant):
    """Create test voice script template."""
    from apps.noc.security_intelligence.ivr.models import VoiceScriptTemplate

    return VoiceScriptTemplate.objects.create(
        tenant=tenant,
        name='Test Inactivity Script',
        anomaly_type='GUARD_INACTIVITY',
        language='en',
        script_text="Hello {guard_name}, security check. Press 1 to confirm.",
        expected_responses={'1': 'confirmed', '2': 'assistance'},
        escalation_triggers=['3'],
        version='1.0',
    )


@pytest.fixture
def ivr_call_log(db, tenant, test_person, site_bt, ivr_provider_config):
    """Create test IVR call log."""
    from apps.noc.security_intelligence.ivr.models import IVRCallLog

    return IVRCallLog.objects.create(
        tenant=tenant,
        person=test_person,
        site=site_bt,
        provider='MOCK',
        call_sid='MOCK_TEST_123',
        phone_number_masked='****1234',
        call_status='QUEUED',
    )