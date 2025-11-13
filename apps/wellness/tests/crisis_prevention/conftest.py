"""
Pytest fixtures for crisis prevention system tests.

Provides reusable test data, mocks, and helper functions.
"""

import pytest
import os
import django
from django.apps import apps

# Ensure Django settings are configured before importing models
if not apps.ready:
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "intelliwiz_config.settings_test")
    django.setup()

from django.utils import timezone
from datetime import timedelta
from unittest.mock import MagicMock, patch
from apps.peoples.models import People, PeopleProfile
from apps.journal.models import JournalEntry, JournalPrivacySettings
from apps.wellness.models import (
    WellnessUserProgress,
    InterventionDeliveryLog,
    MentalHealthIntervention,
)
from apps.tenants.models import Tenant


@pytest.fixture
def tenant(db):
    """Create test tenant"""
    return Tenant.objects.create(
        tenantname='Test Tenant',
        subdomain_prefix='test-tenant'
    )


@pytest.fixture
def test_user(db, tenant):
    """Create test user with wellness profile"""
    user = People.objects.create(
        username='test_wellness_user',
        email='test@example.com',
        peoplename='Test User',
        isverified=True,
        tenant=tenant
    )

    # Create profile
    PeopleProfile.objects.create(
        people=user,
        gender='M',
        contact_number='555-0100'
    )

    # Create wellness progress
    WellnessUserProgress.objects.create(
        user=user,
        daily_tip_enabled=True,
        crisis_monitoring_enabled=True,
        intervention_consent=True
    )

    return user


@pytest.fixture
def test_user_no_consent(db, tenant):
    """Create test user WITHOUT crisis monitoring consent"""
    user = People.objects.create(
        username='test_no_consent',
        email='test_no_consent@example.com',
        peoplename='Test No Consent',
        isverified=True,
        tenant=tenant
    )

    WellnessUserProgress.objects.create(
        user=user,
        daily_tip_enabled=True,
        crisis_monitoring_enabled=False,  # Monitoring disabled
        intervention_consent=False
    )

    return user


@pytest.fixture
def crisis_journal_entry(test_user):
    """Create journal entry indicating crisis (mood=1, stress=5)"""
    return JournalEntry.objects.create(
        user=test_user,
        mood_rating=1,  # Severe low mood
        stress_level=5,  # Maximum stress
        energy_level=1,  # Minimum energy
        content="Feeling hopeless and overwhelmed. Nothing matters anymore.",
        entry_type='text',
        timestamp=timezone.now()
    )


@pytest.fixture
def moderate_risk_entry(test_user):
    """Create journal entry indicating moderate risk (mood=3, stress=3)"""
    return JournalEntry.objects.create(
        user=test_user,
        mood_rating=3,  # Low mood
        stress_level=3,  # Moderate stress
        energy_level=2,  # Low energy
        content="Feeling stressed and down today",
        entry_type='text',
        timestamp=timezone.now()
    )


@pytest.fixture
def low_risk_entry(test_user):
    """Create journal entry indicating low risk (mood=4, stress=2)"""
    return JournalEntry.objects.create(
        user=test_user,
        mood_rating=4,  # Good mood
        stress_level=2,  # Low stress
        energy_level=4,  # Good energy
        content="Feeling better today",
        entry_type='text',
        timestamp=timezone.now()
    )


@pytest.fixture
def consecutive_low_mood_entries(test_user):
    """Create 5 consecutive days of low mood entries"""
    entries = []
    for days_ago in range(5):
        entry = JournalEntry.objects.create(
            user=test_user,
            mood_rating=3,  # Consistently low
            stress_level=3,
            energy_level=2,
            content=f"Day {days_ago + 1} of feeling down",
            timestamp=timezone.now() - timedelta(days=days_ago)
        )
        entries.append(entry)
    return entries


@pytest.fixture
def rapid_mood_drop_entries(test_user):
    """Create entries showing rapid mood drop (5 → 1 in 24 hours)"""
    now = timezone.now()

    # Yesterday: Good mood
    entry1 = JournalEntry.objects.create(
        user=test_user,
        mood_rating=5,
        stress_level=1,
        energy_level=5,
        content="Feeling great!",
        timestamp=now - timedelta(hours=24)
    )

    # Today: Crisis mood
    entry2 = JournalEntry.objects.create(
        user=test_user,
        mood_rating=1,
        stress_level=5,
        energy_level=1,
        content="Everything collapsed",
        timestamp=now
    )

    return [entry1, entry2]


@pytest.fixture
def mock_notification_service(mocker):
    """Mock notification services to prevent actual sends during testing"""
    mock_email = mocker.patch('django.core.mail.send_mail')
    mock_email.return_value = 1  # Success

    # Mock SMS if implemented (update to new module path)
    mocker.patch('apps.wellness.services.crisis_prevention.crisis_notification_service.send_sms', return_value=True)

    # Mock webhook if implemented (update to new module path)
    mocker.patch('apps.wellness.services.crisis_prevention.crisis_notification_service.send_webhook', return_value=True)

    return {
        'email': mock_email,
        'sms': mocker.patch('apps.wellness.services.crisis_prevention.crisis_notification_service.send_sms'),
        'webhook': mocker.patch('apps.wellness.services.crisis_prevention.crisis_notification_service.send_webhook'),
    }


@pytest.fixture
def mock_escalation_engine(mocker):
    """Mock ProgressiveEscalationEngine for isolation testing"""
    mock = mocker.patch('apps.wellness.services.progressive_escalation_engine.ProgressiveEscalationEngine')
    mock_instance = MagicMock()
    mock.return_value = mock_instance

    # Default escalation response
    mock_instance.determine_optimal_escalation_level.return_value = {
        'recommended_escalation_level': 2,
        'interventions': ['self_help_content'],
        'notifications_sent': []
    }

    return mock_instance


def create_journal_entry(user, mood=3, stress=3, energy=3, content="Test entry", days_ago=0):
    """Helper function to create journal entry with specific metrics"""
    return JournalEntry.objects.create(
        user=user,
        mood_rating=mood,
        stress_level=stress,
        energy_level=energy,
        content=content,
        entry_type='text',
        timestamp=timezone.now() - timedelta(days=days_ago)
    )


def create_intervention_log(user, intervention_type='self_help', urgency='low', days_ago=0):
    """Helper function to create intervention delivery log"""
    return InterventionDeliveryLog.objects.create(
        user=user,
        intervention_type=intervention_type,
        urgency_level=urgency,
        delivery_context='crisis_prevention',
        delivered_at=timezone.now() - timedelta(days=days_ago),
        completion_status='delivered'
    )
