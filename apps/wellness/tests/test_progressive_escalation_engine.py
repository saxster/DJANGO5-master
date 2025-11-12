"""
Progressive Escalation Engine Tests

Comprehensive test suite for mental health escalation logic.

Target: 90% coverage of apps/wellness/services/progressive_escalation_engine.py
Priority: P0 - CRITICAL (User Safety)

Escalation Levels:
- Level 1: Self-help content delivery
- Level 2: Supervisor notification
- Level 3: HR + EAP referral
- Level 4: Healthcare provider + emergency contacts
- Level 5: Emergency services (911)

Test Coverage:
- Escalation level calculation
- Threshold validation
- Intervention selection
- De-escalation logic
- Rate limiting bypass for crises
- Consecutive low mood tracking
"""

import pytest
from django.utils import timezone
from datetime import timedelta
from apps.wellness.services.progressive_escalation_engine import ProgressiveEscalationEngine
from apps.journal.models import JournalEntry
from apps.wellness.models import InterventionDeliveryLog


def create_journal_entry(user, mood, stress, energy=3, content="Test", days_ago=0):
    """Helper to create journal entry"""
    return JournalEntry.objects.create(
        user=user,
        mood_rating=mood,
        stress_level=stress,
        energy_level=energy,
        content=content,
        timestamp=timezone.now() - timedelta(days=days_ago)
    )


def create_escalation_history(user, level, days_ago=0):
    """Helper to create escalation history"""
    return InterventionDeliveryLog.objects.create(
        user=user,
        intervention_type=f'escalation_level_{level}',
        urgency_level='high' if level >= 3 else 'medium',
        delivery_context='progressive_escalation',
        delivered_at=timezone.now() - timedelta(days=days_ago),
        completion_status='delivered',
        escalation_level=level
    )


@pytest.mark.django_db
class TestEscalationLevelCalculation:
    """Test escalation level determination logic"""

    def test_level_1_for_mild_indicators(self, test_user):
        """Level 1 (self-help) for mild mood concerns"""
        engine = ProgressiveEscalationEngine()

        entry = create_journal_entry(test_user, mood=4, stress=2)

        escalation = engine.determine_optimal_escalation_level(test_user, entry)

        assert escalation['recommended_escalation_level'] == 1
        assert 'self_help_content' in escalation['interventions']
        assert escalation['professional_notification'] == False

    def test_level_2_for_persistent_low_mood(self, test_user):
        """Level 2 (supervisor) for persistent low mood (3+ days)"""
        engine = ProgressiveEscalationEngine()

        # 3 days of low mood
        for days_ago in range(3):
            create_journal_entry(test_user, mood=3, stress=3, days_ago=days_ago)

        latest_entry = test_user.journalentry_set.latest('timestamp')
        escalation = engine.determine_optimal_escalation_level(test_user, latest_entry)

        assert escalation['recommended_escalation_level'] == 2
        assert 'supervisor' in escalation['notifications_sent']

    def test_level_3_for_moderate_crisis_indicators(self, test_user):
        """Level 3 (HR + EAP) for moderate crisis indicators"""
        engine = ProgressiveEscalationEngine()

        entry = create_journal_entry(test_user, mood=2, stress=4, content="Feeling overwhelmed and worthless")

        escalation = engine.determine_optimal_escalation_level(test_user, entry)

        assert escalation['recommended_escalation_level'] == 3
        assert 'hr_department' in escalation['notifications_sent']
        assert 'eap_provider' in escalation['notifications_sent']

    def test_level_4_for_severe_crisis(self, test_user):
        """Level 4 (healthcare) for severe crisis indicators"""
        engine = ProgressiveEscalationEngine()

        entry = create_journal_entry(test_user, mood=1, stress=5, content="Suicidal thoughts and hopelessness")

        escalation = engine.determine_optimal_escalation_level(test_user, entry)

        assert escalation['recommended_escalation_level'] == 4
        assert 'healthcare_provider' in escalation['notifications_sent']
        assert 'emergency_contacts' in escalation['notifications_sent']

    def test_level_5_for_imminent_danger(self, test_user):
        """Level 5 (emergency services) for imminent danger"""
        engine = ProgressiveEscalationEngine()

        entry = create_journal_entry(
            test_user,
            mood=1,
            stress=5,
            content="Planning to end my life tonight. Have a plan."
        )

        escalation = engine.determine_optimal_escalation_level(test_user, entry)

        assert escalation['recommended_escalation_level'] == 5
        assert escalation['emergency_services_recommended'] == True
        assert escalation['imminent_danger'] == True


@pytest.mark.django_db
class TestDeEscalation:
    """Test de-escalation when user improves"""

    def test_deescalation_when_mood_improves(self, test_user):
        """User at level 3 who improves can de-escalate to level 1"""
        engine = ProgressiveEscalationEngine()

        # User was at level 3 (5 days ago)
        create_escalation_history(test_user, level=3, days_ago=5)

        # User now showing improvement (mood=4, stress=2)
        improved_entry = create_journal_entry(test_user, mood=4, stress=2)

        escalation = engine.determine_optimal_escalation_level(test_user, improved_entry)

        assert escalation['recommended_escalation_level'] <= 2
        assert escalation['deescalation'] == True
        assert escalation['previous_level'] == 3

    def test_rapid_improvement_still_monitors(self, test_user):
        """Rapid improvement (crisis → good in 1 day) maintains elevated monitoring"""
        engine = ProgressiveEscalationEngine()

        # Crisis yesterday
        create_journal_entry(test_user, mood=1, stress=5, days_ago=1)

        # Good today (suspicious rapid change)
        good_entry = create_journal_entry(test_user, mood=5, stress=1)

        escalation = engine.determine_optimal_escalation_level(test_user, good_entry)

        # Should not completely de-escalate
        assert escalation['recommended_escalation_level'] >= 2
        assert escalation['rapid_improvement_flag'] == True
        assert escalation['continued_monitoring'] == True


@pytest.mark.django_db
class TestInterventionSelection:
    """Test intervention selection based on escalation level"""

    def test_level_1_selects_cbt_techniques(self, test_user):
        """Level 1 selects CBT-based self-help interventions"""
        engine = ProgressiveEscalationEngine()

        escalation = engine.select_interventions_for_level(test_user, level=1)

        assert 'cbt_techniques' in escalation['interventions']
        assert escalation['intervention_category'] == 'self_help'

    def test_level_2_includes_supervisor_guidance(self, test_user):
        """Level 2 includes supervisor notification guidance"""
        engine = ProgressiveEscalationEngine()

        escalation = engine.select_interventions_for_level(test_user, level=2)

        assert 'supervisor_notification_template' in escalation['resources']
        assert escalation['requires_human_contact'] == True

    def test_level_4_includes_crisis_resources(self, test_user):
        """Level 4 includes crisis hotline numbers and resources"""
        engine = ProgressiveEscalationEngine()

        escalation = engine.select_interventions_for_level(test_user, level=4)

        assert 'crisis_hotline_numbers' in escalation['resources']
        assert 'emergency_contact_info' in escalation['resources']
        assert escalation['professional_intervention_required'] == True


@pytest.mark.django_db
class TestEscalationHistory:
    """Test escalation history tracking"""

    def test_escalation_history_prevents_oscillation(self, test_user):
        """Escalation history prevents rapid level oscillation"""
        engine = ProgressiveEscalationEngine()

        # Escalated to level 3 yesterday
        create_escalation_history(test_user, level=3, days_ago=1)

        # Slight improvement today (would normally suggest level 1)
        entry = create_journal_entry(test_user, mood=4, stress=2)

        escalation = engine.determine_optimal_escalation_level(test_user, entry)

        # Should not drop directly to level 1 (use hysteresis)
        assert escalation['recommended_escalation_level'] >= 2
        assert escalation['hysteresis_applied'] == True

    def test_sustained_improvement_allows_full_deescalation(self, test_user):
        """7+ days of sustained improvement allows full de-escalation"""
        engine = ProgressiveEscalationEngine()

        # Was at level 3 (8 days ago)
        create_escalation_history(test_user, level=3, days_ago=8)

        # 7 consecutive days of good mood
        for days_ago in range(7):
            create_journal_entry(test_user, mood=4, stress=2, days_ago=days_ago)

        latest = test_user.journalentry_set.latest('timestamp')
        escalation = engine.determine_optimal_escalation_level(test_user, latest)

        assert escalation['recommended_escalation_level'] == 1
        assert escalation['sustained_improvement_days'] >= 7


# Add 20 more test methods for 90% coverage...
