"""
Journal Pattern Recognition Service

REFACTORED: November 2025 - Reduced from 1,058 lines to ~300 lines

CHANGES:
- Deleted 650+ lines of duplicate fallback code (_detect_long_term_patterns_fallback)
- Delegates to JournalAnalyticsService for most functionality
- Uses centralized crisis keywords from apps/wellness/constants
- Maintains backward compatibility with existing callers

PREVIOUS STATE:
- 70% duplicate logic with analytics_service.py
- Fallback methods never used (delegation always worked)
- Crisis keywords duplicated across 3 files

NEW ARCHITECTURE:
- Thin wrapper around JournalAnalyticsService
- Real-time pattern detection only
- No duplicate code

Real-time analysis of journal entries for immediate wellness interventions

Implements the complete algorithm from DJANGO_BACKEND_COMPLETE_JOURNAL_SPECIFICATION.md:
- Immediate intervention detection with urgency scoring
- Long-term pattern analysis for proactive wellness (delegated)
- Crisis indicator detection and response triggering
- Stress cycle analysis and mood seasonality detection (delegated)
- Coping strategy effectiveness measurement (delegated)
- Positive psychology engagement analysis (delegated)
"""

from django.utils import timezone
from collections import defaultdict, Counter
from datetime import timedelta
import re
from apps.journal.logging import get_journal_logger
from apps.wellness.constants import CRISIS_KEYWORDS, STRESS_TRIGGER_PATTERNS

logger = get_journal_logger(__name__)


class JournalPatternAnalyzer:
    """
    REFACTORED: Thin wrapper around JournalAnalyticsService

    DELEGATES TO:
    - apps/journal/services/analytics_service.JournalAnalyticsService (main analytics)
    - apps/journal/services/analytics/urgency_analyzer.UrgencyAnalyzer (urgency scoring)
    - apps/journal/services/analytics/pattern_detection_service.PatternDetectionService (patterns)

    MAINTAINS:
    - Backward compatibility with existing code
    - analyze_entry_for_immediate_action() interface
    - detect_long_term_patterns() interface
    """

    def __init__(self):
        """Initialize with consolidated crisis keywords"""
        self.CRISIS_KEYWORDS = CRISIS_KEYWORDS
        self.STRESS_TRIGGER_PATTERNS = STRESS_TRIGGER_PATTERNS

    def analyze_entry_for_immediate_action(self, journal_entry):
        """
        CRITICAL ALGORITHM: Immediate intervention detection
        MOVED FROM: Kotlin WellbeingInsightsViewModel.calculateOverallWellbeingScore()

        DELEGATES TO: JournalAnalyticsService.analyze_entry_for_immediate_action()

        Urgency Scoring Algorithm:
        - Stress level ≥ 4: +3 points (high stress threshold)
        - Mood ≤ 2: +4 points (crisis mood threshold)
        - Energy ≤ 3: +1 point (fatigue threshold)
        - Equipment/safety triggers: +2 points (workplace safety)
        - Deadline/pressure triggers: +1 point (time management)

        Total Score ≥ 5: Immediate intervention required
        Total Score 3-4: Same-day intervention recommended
        Total Score 1-2: Next-session intervention

        Args:
            journal_entry: JournalEntry instance

        Returns:
            dict: Urgency analysis with score, level, categories, timing, confidence
        """
        from .analytics_service import JournalAnalyticsService

        analytics_service = JournalAnalyticsService()
        result = analytics_service.analyze_entry_for_immediate_action(journal_entry)

        logger.info(
            f"Pattern analysis complete for entry {journal_entry.id}: "
            f"urgency={result['urgency_score']}, level={result['urgency_level']}"
        )

        # Log crisis situations for monitoring (backward compatibility)
        if result.get('crisis_detected'):
            logger.critical(
                f"CRISIS INDICATORS DETECTED: User {journal_entry.user.id} "
                f"({journal_entry.user.peoplename}), Entry {journal_entry.id}, "
                f"Urgency: {result['urgency_score']}, "
                f"Indicators: {'; '.join(result.get('crisis_indicators', []))}"
            )

        return result

    def detect_long_term_patterns(self, user_journal_history):
        """
        DELEGATES TO: JournalAnalyticsService.analyze_long_term_patterns()

        REMOVED: _detect_long_term_patterns_fallback() (650 lines) - NEVER CALLED

        Pattern Detection Algorithms:
        1. Stress Cycle Analysis - Weekly/monthly stress patterns
        2. Mood Seasonality - Seasonal affective patterns
        3. Energy-Work Correlation - Energy levels vs work type
        4. Trigger Pattern Recognition - Recurring stress triggers
        5. Coping Effectiveness - Which strategies work best for user
        6. Positive Psychology Engagement - Gratitude/affirmation patterns

        Args:
            user_journal_history: List of JournalEntry objects or User object

        Returns:
            dict: Long-term pattern analysis from analytics service
        """
        from .analytics_service import JournalAnalyticsService

        analytics_service = JournalAnalyticsService()

        # Handle both list of entries and User object
        if user_journal_history and hasattr(user_journal_history[0], 'user'):
            # List of entries - extract user
            user = user_journal_history[0].user
            return analytics_service.analyze_long_term_patterns(user, days=90)
        elif hasattr(user_journal_history, 'id'):
            # User object passed directly
            return analytics_service.analyze_long_term_patterns(user_journal_history, days=90)
        else:
            # Fallback for edge cases
            logger.warning("detect_long_term_patterns called with unexpected argument type")
            return {
                'insufficient_data': True,
                'message': 'Invalid input: expected User object or list of JournalEntry objects'
            }

    # Legacy methods for backward compatibility (delegated)
    def _analyze_stress_triggers(self, stress_triggers):
        """DEPRECATED: Use UrgencyAnalyzer._analyze_stress_triggers() directly"""
        from .analytics.urgency_analyzer import UrgencyAnalyzer
        analyzer = UrgencyAnalyzer()
        return analyzer._analyze_stress_triggers(stress_triggers)

    def _analyze_content_for_crisis(self, content):
        """DEPRECATED: Use UrgencyAnalyzer._analyze_content_for_crisis() directly"""
        from .analytics.urgency_analyzer import UrgencyAnalyzer
        analyzer = UrgencyAnalyzer()
        return analyzer._analyze_content_for_crisis(content)

    def _analyze_performance_indicators(self, journal_entry):
        """DEPRECATED: Use UrgencyAnalyzer._analyze_performance_indicators() directly"""
        from .analytics.urgency_analyzer import UrgencyAnalyzer
        analyzer = UrgencyAnalyzer()
        return analyzer._analyze_performance_indicators(journal_entry)

    def _categorize_urgency(self, urgency_score):
        """DEPRECATED: Use UrgencyAnalyzer._categorize_urgency() directly"""
        from .analytics.urgency_analyzer import UrgencyAnalyzer
        analyzer = UrgencyAnalyzer()
        return analyzer._categorize_urgency(urgency_score)

    def _calculate_delivery_timing(self, urgency_score):
        """DEPRECATED: Use UrgencyAnalyzer._calculate_delivery_timing() directly"""
        from .analytics.urgency_analyzer import UrgencyAnalyzer
        analyzer = UrgencyAnalyzer()
        return analyzer._calculate_delivery_timing(urgency_score)

    def _calculate_confidence(self, journal_entry, urgency_score):
        """DEPRECATED: Use UrgencyAnalyzer._calculate_analysis_confidence() directly"""
        from .analytics.urgency_analyzer import UrgencyAnalyzer
        analyzer = UrgencyAnalyzer()
        return analyzer._calculate_analysis_confidence(journal_entry, urgency_score)

    # Pattern detection methods (delegated)
    def _detect_stress_cycles(self, stress_entries):
        """DEPRECATED: Use PatternDetectionService.detect_stress_cycles() directly"""
        from .analytics.pattern_detection_service import PatternDetectionService
        detector = PatternDetectionService()
        return detector.detect_stress_cycles(stress_entries)

    def _analyze_mood_seasonality(self, mood_entries):
        """DEPRECATED: Use PatternDetectionService.analyze_mood_seasonality() directly"""
        from .analytics.pattern_detection_service import PatternDetectionService
        detector = PatternDetectionService()
        return detector.analyze_mood_seasonality(mood_entries)

    def _correlate_energy_with_work_context(self, journal_entries):
        """DEPRECATED: Use PatternDetectionService.correlate_energy_with_work() directly"""
        from .analytics.pattern_detection_service import PatternDetectionService
        detector = PatternDetectionService()
        return detector.correlate_energy_with_work(journal_entries)

    def _analyze_recurring_triggers(self, stress_entries):
        """DEPRECATED: Use PatternDetectionService.analyze_recurring_triggers() directly"""
        from .analytics.pattern_detection_service import PatternDetectionService
        detector = PatternDetectionService()
        return detector.analyze_recurring_triggers(stress_entries)

    def _measure_coping_strategy_effectiveness(self, stress_entries):
        """DEPRECATED: Use PatternDetectionService.measure_coping_effectiveness() directly"""
        from .analytics.pattern_detection_service import PatternDetectionService
        detector = PatternDetectionService()
        return detector.measure_coping_effectiveness(stress_entries)

    def _analyze_positive_psychology_patterns(self, positive_entries):
        """DEPRECATED: Use PatternDetectionService.analyze_positive_psychology() directly"""
        from .analytics.pattern_detection_service import PatternDetectionService
        detector = PatternDetectionService()
        return detector.analyze_positive_psychology(positive_entries)

    def _predict_wellbeing_risks(self, journal_history):
        """DEPRECATED: Use PatternDetectionService.predict_wellbeing_risks() directly"""
        from .analytics.pattern_detection_service import PatternDetectionService
        detector = PatternDetectionService()
        return detector.predict_wellbeing_risks(journal_history)

    def _calculate_optimal_intervention_timing(self, journal_history):
        """DEPRECATED: Use PatternDetectionService.calculate_optimal_intervention_timing() directly"""
        from .analytics.pattern_detection_service import PatternDetectionService
        detector = PatternDetectionService()
        return detector.calculate_optimal_intervention_timing(journal_history)

    def _generate_learning_path(self, journal_history):
        """DEPRECATED: Use PatternDetectionService.generate_learning_path() directly"""
        from .analytics.pattern_detection_service import PatternDetectionService
        detector = PatternDetectionService()
        return detector.generate_learning_path(journal_history)

    def _calculate_pattern_confidence(self, journal_history):
        """DEPRECATED: Use PatternDetectionService.calculate_pattern_confidence() directly"""
        from .analytics.pattern_detection_service import PatternDetectionService
        detector = PatternDetectionService()
        return detector.calculate_pattern_confidence(journal_history)

    def _calculate_prediction_confidence(self, journal_history):
        """DEPRECATED: Use PatternDetectionService.calculate_prediction_confidence() directly"""
        from .analytics.pattern_detection_service import PatternDetectionService
        detector = PatternDetectionService()
        return detector.calculate_prediction_confidence(journal_history)


# Convenience function for triggering pattern analysis
def trigger_pattern_analysis(journal_entry):
    """
    Convenience function to trigger pattern analysis from signals

    DELEGATES TO: JournalPatternAnalyzer.analyze_entry_for_immediate_action()

    Args:
        journal_entry: JournalEntry instance

    Returns:
        dict: Analysis results or None on error
    """
    try:
        analyzer = JournalPatternAnalyzer()
        analysis = analyzer.analyze_entry_for_immediate_action(journal_entry)

        logger.info(f"Pattern analysis triggered for entry {journal_entry.id}: urgency={analysis['urgency_score']}")

        # TODO: Integrate with wellness content delivery system
        # if analysis['urgency_score'] >= 3:
        #     from apps.wellness.services.content_delivery import deliver_urgent_content
        #     deliver_urgent_content(journal_entry.user, analysis)

        return analysis

    except (AttributeError, TypeError, ValueError) as e:
        logger.error(f"Pattern analysis failed for entry {journal_entry.id}: {e}")
        return None
