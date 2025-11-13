"""
Crisis Detection Tests

Comprehensive test suite for crisis detection accuracy, thresholds, and safety validation.

Target: 100% coverage of crisis detection logic in CrisisPreventionSystem
Priority: P0 - CRITICAL (User Safety)

Test Coverage:
- Urgency score thresholds (≥6 triggers crisis)
- Mood rating thresholds (≤2 triggers high-urgency)
- Stress level thresholds (≥4 combined with low mood)
- Crisis keyword detection (suicidal ideation, hopelessness)
- Consecutive low mood days pattern (3+ days)
- Rapid mood drop detection (3+ points in 24h)
- Missing data handling and imputation
- False positive/negative rate validation
- Edge cases and boundary conditions
"""

import pytest
from django.utils import timezone
from datetime import timedelta
from apps.wellness.services.crisis_prevention import CrisisPreventionSystem
from apps.journal.models import JournalEntry
from .conftest import create_journal_entry, create_intervention_log


@pytest.mark.django_db
class TestCrisisDetectionThresholds:
    """Test crisis detection threshold accuracy"""

    def test_urgency_score_6_triggers_crisis_intervention(self, test_user, mock_notification_service):
        """
        CRITICAL: Urgency score ≥6 MUST trigger crisis intervention.

        WHO Guideline: High-urgency indicators require immediate response
        """
        crisis_system = CrisisPreventionSystem()

        analysis = {
            'urgency_score': 6,
            'crisis_indicators': ['severe_mood_drop'],
            'mood_rating': 2,
            'stress_level': 4,
            'risk_level': 'high'
        }

        result = crisis_system.assess_crisis_risk(test_user, analysis)

        assert result['crisis_detected'] == True, "Urgency ≥6 must detect crisis"
        assert result['intervention_triggered'] == True
        assert result['urgency_level'] in ['high', 'critical']
        assert result['immediate_action'] == True

    def test_urgency_score_5_triggers_elevated_monitoring(self, test_user):
        """Urgency score 5 triggers elevated monitoring (not full crisis)"""
        crisis_system = CrisisPreventionSystem()

        analysis = {
            'urgency_score': 5,
            'mood_rating': 3,
            'stress_level': 3
        }

        result = crisis_system.assess_crisis_risk(test_user, analysis)

        assert result['crisis_detected'] == False
        assert result['elevated_monitoring'] == True
        assert result['urgency_level'] == 'medium'

    def test_urgency_score_below_5_normal_monitoring(self, test_user):
        """Urgency score <5 maintains normal monitoring"""
        crisis_system = CrisisPreventionSystem()

        analysis = {
            'urgency_score': 3,
            'mood_rating': 4,
            'stress_level': 2
        }

        result = crisis_system.assess_crisis_risk(test_user, analysis)

        assert result['crisis_detected'] == False
        assert result['elevated_monitoring'] == False
        assert result['urgency_level'] == 'low'

    def test_mood_rating_1_triggers_critical_urgency(self, test_user):
        """
        CRITICAL: Mood rating = 1 (severe low) MUST trigger critical urgency.

        This is the most severe mood state and requires immediate intervention.
        """
        crisis_system = CrisisPreventionSystem()

        entry = create_journal_entry(test_user, mood=1, stress=4, energy=1)

        result = crisis_system.assess_crisis_risk(test_user, entry)

        assert result['urgency_level'] == 'critical'
        assert result['crisis_detected'] == True
        assert result['immediate_action'] == True

    def test_mood_rating_2_triggers_high_urgency(self, test_user):
        """Mood rating ≤2 MUST trigger high-urgency intervention"""
        crisis_system = CrisisPreventionSystem()

        entry = create_journal_entry(test_user, mood=2, stress=3, energy=2)

        result = crisis_system.assess_crisis_risk(test_user, entry)

        assert result['urgency_level'] in ['high', 'critical']
        assert result['intervention_triggered'] == True

    def test_stress_level_5_with_low_mood_triggers_crisis(self, test_user):
        """Maximum stress (5) combined with low mood (≤3) triggers crisis"""
        crisis_system = CrisisPreventionSystem()

        entry = create_journal_entry(test_user, mood=3, stress=5, energy=2)

        result = crisis_system.assess_crisis_risk(test_user, entry)

        assert result['crisis_detected'] == True
        assert result['contributing_factors'] == ['maximum_stress', 'low_mood']


@pytest.mark.django_db
class TestCrisisKeywordDetection:
    """Test crisis keyword detection (suicidal ideation, hopelessness)"""

    def test_suicidal_keyword_triggers_immediate_action(self, test_user, mock_notification_service):
        """
        CRITICAL: Suicidal ideation keywords MUST trigger immediate crisis response.

        Keywords: 'suicidal', 'kill myself', 'want to die', 'end it all'
        """
        crisis_system = CrisisPreventionSystem()

        entry = JournalEntry.objects.create(
            user=test_user,
            mood_rating=2,
            content="Having suicidal thoughts today",  # CRITICAL KEYWORD
            timestamp=timezone.now()
        )

        result = crisis_system.assess_crisis_risk(test_user, entry)

        assert result['crisis_detected'] == True
        assert result['immediate_action'] == True
        assert 'suicidal_ideation' in result['crisis_indicators']
        assert result['urgency_level'] == 'critical'

    def test_hopelessness_keyword_triggers_crisis(self, test_user):
        """Hopelessness keywords trigger crisis intervention"""
        crisis_system = CrisisPreventionSystem()

        entry = JournalEntry.objects.create(
            user=test_user,
            mood_rating=2,
            content="Feeling completely hopeless. No point in anything.",
            timestamp=timezone.now()
        )

        result = crisis_system.assess_crisis_risk(test_user, entry)

        assert result['crisis_detected'] == True
        assert 'hopelessness' in result['crisis_indicators']

    def test_multiple_crisis_keywords_increases_urgency(self, test_user):
        """Multiple crisis keywords increase urgency score"""
        crisis_system = CrisisPreventionSystem()

        entry = JournalEntry.objects.create(
            user=test_user,
            mood_rating=2,
            content="Feeling hopeless, worthless, and like a burden on everyone",
            timestamp=timezone.now()
        )

        result = crisis_system.assess_crisis_risk(test_user, entry)

        assert len(result['crisis_indicators']) >= 2
        assert result['urgency_score'] > 6  # Multiple keywords compound

    def test_crisis_keyword_case_insensitive(self, test_user):
        """Crisis keyword detection is case-insensitive"""
        crisis_system = CrisisPreventionSystem()

        entry = JournalEntry.objects.create(
            user=test_user,
            mood_rating=2,
            content="FEELING SUICIDAL",  # Uppercase
            timestamp=timezone.now()
        )

        result = crisis_system.assess_crisis_risk(test_user, entry)

        assert result['crisis_detected'] == True
        assert 'suicidal_ideation' in result['crisis_indicators']


@pytest.mark.django_db
class TestConsecutiveLowMoodPattern:
    """Test consecutive low mood day pattern detection"""

    def test_3_consecutive_low_mood_days_triggers_intervention(self, test_user):
        """3+ consecutive days of low mood (≤3) triggers intervention"""
        crisis_system = CrisisPreventionSystem()

        # Create 3 consecutive days of low mood
        for days_ago in range(3):
            create_journal_entry(test_user, mood=3, stress=3, days_ago=days_ago)

        result = crisis_system.check_mood_pattern(test_user)

        assert result['consecutive_low_days'] >= 3
        assert result['pattern_detected'] == True
        assert result['recommended_action'] == 'escalate'

    def test_2_consecutive_days_no_intervention_yet(self, test_user):
        """Only 2 consecutive days = monitoring, not intervention"""
        crisis_system = CrisisPreventionSystem()

        for days_ago in range(2):
            create_journal_entry(test_user, mood=3, stress=3, days_ago=days_ago)

        result = crisis_system.check_mood_pattern(test_user)

        assert result['consecutive_low_days'] == 2
        assert result['pattern_detected'] == False
        assert result['recommended_action'] == 'monitor'

    def test_5_consecutive_low_mood_days_increases_urgency(self, test_user, consecutive_low_mood_entries):
        """5+ consecutive days significantly increases urgency"""
        crisis_system = CrisisPreventionSystem()

        result = crisis_system.check_mood_pattern(test_user)

        assert result['consecutive_low_days'] >= 5
        assert result['urgency_modifier'] > 1.5  # Urgency multiplier
        assert result['intervention_type'] == 'professional_referral'


@pytest.mark.django_db
class TestRapidMoodDropDetection:
    """Test rapid mood drop detection (3+ points in 24 hours)"""

    def test_rapid_mood_drop_4_points_triggers_alert(self, test_user, rapid_mood_drop_entries):
        """Mood drop of 4+ points in 24h triggers crisis alert"""
        crisis_system = CrisisPreventionSystem()

        result = crisis_system.detect_rapid_mood_change(test_user)

        assert result['rapid_drop_detected'] == True
        assert result['mood_drop_magnitude'] == 4  # 5 → 1
        assert result['time_window_hours'] <= 24
        assert result['crisis_risk'] == 'high'

    def test_gradual_mood_decline_no_rapid_alert(self, test_user):
        """Gradual decline over 7 days doesn't trigger rapid drop alert"""
        crisis_system = CrisisPreventionSystem()

        # Gradual decline: 5 → 4 → 3 → 2 over 7 days
        moods = [5, 5, 4, 4, 3, 3, 2]
        for i, mood in enumerate(moods):
            create_journal_entry(test_user, mood=mood, days_ago=6-i)

        result = crisis_system.detect_rapid_mood_change(test_user)

        assert result['rapid_drop_detected'] == False
        assert result['pattern'] == 'gradual_decline'


@pytest.mark.django_db
class TestMissingDataHandling:
    """Test handling of missing or incomplete mood data"""

    def test_missing_mood_rating_uses_imputation(self, test_user):
        """Missing mood rating uses historical average (imputation)"""
        crisis_system = CrisisPreventionSystem()

        # Create historical data (average mood = 4)
        for i in range(7):
            create_journal_entry(test_user, mood=4, days_ago=i+1)

        # Create entry with missing mood
        entry = JournalEntry.objects.create(
            user=test_user,
            mood_rating=None,  # Missing
            stress_level=3,
            content="Forgot to rate mood",
            timestamp=timezone.now()
        )

        result = crisis_system.assess_crisis_risk(test_user, entry)

        assert result['mood_rating_imputed'] == True
        assert result['imputed_mood'] == 4  # Historical average
        assert result['data_quality'] == 'imputed'

    def test_no_historical_data_uses_neutral_default(self, test_user):
        """User with no historical data gets neutral default (mood=3)"""
        crisis_system = CrisisPreventionSystem()

        # No historical entries - first journal entry
        entry = JournalEntry.objects.create(
            user=test_user,
            mood_rating=None,  # Missing
            content="First entry",
            timestamp=timezone.now()
        )

        result = crisis_system.assess_crisis_risk(test_user, entry)

        assert result['mood_rating_imputed'] == True
        assert result['imputed_mood'] == 3  # Neutral default
        assert result['data_quality'] == 'default'

    def test_all_metrics_missing_skip_analysis(self, test_user):
        """Entry with all metrics missing skips crisis analysis"""
        crisis_system = CrisisPreventionSystem()

        entry = JournalEntry.objects.create(
            user=test_user,
            mood_rating=None,
            stress_level=None,
            energy_level=None,
            content="No ratings provided",
            timestamp=timezone.now()
        )

        result = crisis_system.assess_crisis_risk(test_user, entry)

        assert result['analysis_skipped'] == True
        assert result['skip_reason'] == 'insufficient_data'


@pytest.mark.django_db
class TestFalsePositiveNegativeRates:
    """Test false positive and false negative rates for crisis detection"""

    def test_false_positive_rate_below_5_percent(self):
        """
        CRITICAL: False positive rate MUST be <5%

        False positive = Flagging non-crisis as crisis
        Target: <5% (95%+ specificity)
        """
        crisis_system = CrisisPreventionSystem()

        # Create 100 test users with various non-crisis entries
        false_positives = 0
        total_non_crisis = 100

        for i in range(total_non_crisis):
            user = create_test_user_dynamic(f"user_{i}")

            # Non-crisis entry (mood=4, mild stress)
            entry = create_journal_entry(user, mood=4, stress=2, energy=4)

            result = crisis_system.assess_crisis_risk(user, entry)

            if result.get('crisis_detected'):
                false_positives += 1

        false_positive_rate = false_positives / total_non_crisis

        assert false_positive_rate < 0.05, f"False positive rate too high: {false_positive_rate:.2%} (target: <5%)"

    def test_false_negative_rate_below_1_percent(self):
        """
        CRITICAL: False negative rate MUST be <1%

        False negative = Missing actual crisis
        Target: <1% (99%+ sensitivity) - User safety critical
        """
        crisis_system = CrisisPreventionSystem()

        # Create 100 test users with actual crisis indicators
        false_negatives = 0
        total_crisis = 100

        for i in range(total_crisis):
            user = create_test_user_dynamic(f"crisis_user_{i}")

            # Actual crisis entry (mood=1, stress=5, crisis keyword)
            entry = JournalEntry.objects.create(
                user=user,
                mood_rating=1,
                stress_level=5,
                content="Feeling suicidal and hopeless",
                timestamp=timezone.now()
            )

            result = crisis_system.assess_crisis_risk(user, entry)

            if not result.get('crisis_detected'):
                false_negatives += 1

        false_negative_rate = false_negatives / total_crisis

        assert false_negative_rate < 0.01, f"False negative rate too high: {false_negative_rate:.2%} (target: <1%)"


@pytest.mark.django_db
class TestEdgeCases:
    """Test edge cases and boundary conditions"""

    def test_mood_exactly_at_threshold_3(self, test_user):
        """Mood = 3 (boundary) triggers low-risk intervention"""
        crisis_system = CrisisPreventionSystem()

        entry = create_journal_entry(test_user, mood=3, stress=2)

        result = crisis_system.assess_crisis_risk(test_user, entry)

        assert result['at_threshold'] == True
        assert result['urgency_level'] in ['low', 'medium']

    def test_user_with_no_consent_skips_analysis(self, test_user_no_consent):
        """User without crisis monitoring consent skips analysis"""
        crisis_system = CrisisPreventionSystem()

        entry = create_journal_entry(test_user_no_consent, mood=1, stress=5)

        result = crisis_system.assess_crisis_risk(test_user_no_consent, entry)

        assert result['analysis_skipped'] == True
        assert result['skip_reason'] == 'no_consent'

    def test_user_withdraws_consent_mid_monitoring(self, test_user):
        """User withdrawing consent stops crisis monitoring"""
        crisis_system = CrisisPreventionSystem()

        # User withdraws consent
        progress = test_user.wellnessuserprogress
        progress.crisis_monitoring_enabled = False
        progress.intervention_consent = False
        progress.save()

        entry = create_journal_entry(test_user, mood=1, stress=5)

        result = crisis_system.assess_crisis_risk(test_user, entry)

        assert result['analysis_skipped'] == True
        assert result['consent_withdrawn'] == True

    def test_multiple_entries_same_day_uses_worst_metrics(self, test_user):
        """Multiple entries on same day: Use worst mood/stress values"""
        crisis_system = CrisisPreventionSystem()

        # Morning: Good mood
        create_journal_entry(test_user, mood=5, stress=1, content="Morning: feeling great")

        # Evening: Crisis mood
        crisis_entry = create_journal_entry(test_user, mood=1, stress=5, content="Evening: everything collapsed")

        result = crisis_system.assess_daily_risk(test_user, timezone.now().date())

        assert result['mood_min'] == 1  # Worst mood of day
        assert result['stress_max'] == 5  # Worst stress of day
        assert result['crisis_detected'] == True

    def test_entry_with_only_text_no_ratings(self, test_user):
        """Entry with only text (no ratings) uses keyword analysis only"""
        crisis_system = CrisisPreventionSystem()

        entry = JournalEntry.objects.create(
            user=test_user,
            mood_rating=None,
            stress_level=None,
            content="Feeling hopeless and suicidal",  # Crisis keywords
            timestamp=timezone.now()
        )

        result = crisis_system.assess_crisis_risk(test_user, entry)

        assert result['analysis_method'] == 'keyword_only'
        assert result['crisis_detected'] == True
        assert len(result['crisis_indicators']) >= 2  # hopelessness + suicidal


@pytest.mark.django_db
class TestCrisisHistory:
    """Test crisis history tracking and pattern analysis"""

    def test_crisis_history_tracked(self, test_user):
        """Crisis events are tracked in history for pattern analysis"""
        crisis_system = CrisisPreventionSystem()

        # Trigger crisis
        entry = create_journal_entry(test_user, mood=1, stress=5)
        result = crisis_system.assess_crisis_risk(test_user, entry)

        # Check history was recorded
        history = crisis_system.get_crisis_history(test_user)

        assert len(history) >= 1
        assert history[0]['urgency_level'] == result['urgency_level']
        assert history[0]['timestamp'] is not None

    def test_recurring_crises_detected(self, test_user):
        """Recurring crises (2+ in 30 days) flag high-risk user"""
        crisis_system = CrisisPreventionSystem()

        # Crisis 1 (20 days ago)
        create_intervention_log(test_user, intervention_type='crisis', urgency='critical', days_ago=20)

        # Crisis 2 (10 days ago)
        create_intervention_log(test_user, intervention_type='crisis', urgency='critical', days_ago=10)

        # Check for pattern
        pattern = crisis_system.analyze_crisis_recurrence(test_user)

        assert pattern['recurring_crises'] == True
        assert pattern['crisis_count_30_days'] >= 2
        assert pattern['risk_classification'] == 'high_risk_user'


@pytest.mark.django_db
class TestPerformance:
    """Test crisis detection performance under load"""

    def test_crisis_detection_completes_within_5_seconds(self, test_user):
        """Crisis detection MUST complete within 5 seconds"""
        import time

        crisis_system = CrisisPreventionSystem()

        # Create entry with complex analysis required
        entry = create_journal_entry(test_user, mood=2, stress=4, content="Long text" * 100)

        start = time.time()
        result = crisis_system.assess_crisis_risk(test_user, entry)
        elapsed = time.time() - start

        assert elapsed < 5.0, f"Crisis detection too slow: {elapsed:.2f}s (target: <5s)"
        assert result is not None

    def test_daily_batch_handles_10000_users(self):
        """Daily batch processing handles 10,000+ users efficiently"""
        import time

        crisis_system = CrisisPreventionSystem()

        # Create 100 test users (representative sample)
        users = [create_test_user_dynamic(f"batch_user_{i}") for i in range(100)]

        start = time.time()

        for user in users:
            create_journal_entry(user, mood=3, stress=3)
            crisis_system.assess_crisis_risk(user, user.journalentry_set.latest('timestamp'))

        elapsed = time.time() - start

        # Should process 100 users in <10 seconds (scales to 10K in ~1000s = 16 min)
        assert elapsed < 10.0, f"Batch processing too slow: {elapsed:.2f}s for 100 users"


def create_test_user_dynamic(username):
    """Helper to create dynamic test users"""
    from apps.peoples.models import People
    from apps.wellness.models import WellnessUserProgress

    user = People.objects.create(
        username=username,
        email=f"{username}@example.com",
        peoplename=username.replace('_', ' ').title(),
        isverified=True
    )

    WellnessUserProgress.objects.create(
        user=user,
        crisis_monitoring_enabled=True,
        intervention_consent=True
    )

    return user


# Additional test classes to add:
# - TestIntegrationWithJournalAnalytics (10 tests)
# - TestConcurrentCrisisDetection (5 tests)
# - TestDatabaseFailureHandling (5 tests)
# - TestAuditTrailCompleteness (8 tests)

# Total: 50+ comprehensive tests for 100% coverage
