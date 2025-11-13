"""
Urgency Analyzer - Real-time urgency scoring and crisis detection

EXTRACTED FROM:
- apps/journal/services/analytics_service.py (analyze_entry_for_immediate_action, lines 268-355)
- apps/journal/services/analytics_service.py (helper methods, lines 728-846)

COMPLEXITY: Cyclomatic complexity >15 in original implementation
CONSOLIDATES: Crisis detection, stress triggers, performance indicators

PURPOSE:
- Real-time urgency scoring (0-10 scale)
- Crisis keyword detection
- Intervention category identification
- Delivery timing calculation

URGENCY ALGORITHM:
- stress_level >= 4: +3 points (high stress threshold)
- mood_rating <= 2: +4 points (crisis mood threshold)
- energy_level <= 3: +1 point (fatigue threshold)
- crisis_keywords: +2 points (content analysis)
- entry_type == 'SAFETY_CONCERN': +2 points

CLASSIFICATION:
- 7-10: CRITICAL → immediate wellness content delivery
- 5-6:  HIGH     → same hour delivery
- 3-4:  MEDIUM   → same day delivery
- 1-2:  LOW      → next session delivery
"""

from apps.journal.logging import get_journal_logger
from apps.wellness.constants import CRISIS_KEYWORDS, STRESS_TRIGGER_PATTERNS

logger = get_journal_logger(__name__)


class UrgencyAnalyzer:
    """
    Real-time urgency analysis for immediate wellness interventions

    This class consolidates urgency scoring logic previously duplicated
    across analytics_service.py and pattern_analyzer.py.
    """

    def __init__(self):
        self.crisis_keywords = CRISIS_KEYWORDS
        self.stress_trigger_patterns = STRESS_TRIGGER_PATTERNS

    def analyze_entry_for_immediate_action(self, journal_entry):
        """
        Analyze individual entry for immediate intervention needs

        Args:
            journal_entry: JournalEntry instance

        Returns:
            dict: Immediate action analysis results with urgency score,
                  categories, timing, crisis indicators
        """
        logger.debug(f"Analyzing entry {journal_entry.id} for immediate action")

        urgency_score = 0
        intervention_categories = []
        immediate_actions = []
        crisis_indicators = []

        # Stress urgency analysis
        if hasattr(journal_entry, 'stress_level') and journal_entry.stress_level and journal_entry.stress_level >= 4:
            urgency_score += 3
            intervention_categories.append('stress_management')
            immediate_actions.append('breathing_exercises')

            # Analyze stress triggers
            if hasattr(journal_entry, 'stress_triggers') and journal_entry.stress_triggers:
                trigger_analysis = self._analyze_stress_triggers(journal_entry.stress_triggers)
                urgency_score += trigger_analysis['additional_urgency']
                intervention_categories.extend(trigger_analysis['categories'])
                immediate_actions.extend(trigger_analysis['actions'])

        # Mood crisis detection
        if hasattr(journal_entry, 'mood_rating') and journal_entry.mood_rating and journal_entry.mood_rating <= 2:
            urgency_score += 4
            intervention_categories.append('mood_crisis_support')
            immediate_actions.append('immediate_mood_support')
            crisis_indicators.append(f'Very low mood rating: {journal_entry.mood_rating}/10')

            # Content analysis for crisis keywords
            if journal_entry.content:
                content_analysis = self._analyze_content_for_crisis(journal_entry.content)
                if content_analysis['crisis_detected']:
                    urgency_score += 2
                    intervention_categories.append('crisis_intervention')
                    crisis_indicators.extend(content_analysis['indicators'])

        # Energy depletion analysis
        if hasattr(journal_entry, 'energy_level') and journal_entry.energy_level and journal_entry.energy_level <= 3:
            urgency_score += 1
            intervention_categories.append('energy_management')
            immediate_actions.append('energy_boost_techniques')

        # Safety concern analysis
        if journal_entry.entry_type == 'SAFETY_CONCERN':
            urgency_score += 2
            intervention_categories.append('workplace_safety_education')
            immediate_actions.append('safety_protocols')

        # Performance indicators
        performance_analysis = self._analyze_performance_indicators(journal_entry)
        if performance_analysis['concerning_patterns']:
            urgency_score += performance_analysis['urgency_boost']
            intervention_categories.extend(performance_analysis['categories'])

        # Calculate intervention timing and priority
        urgency_level = self._categorize_urgency(urgency_score)
        delivery_timing = self._calculate_delivery_timing(urgency_score)

        result = {
            'urgency_score': urgency_score,
            'urgency_level': urgency_level,
            'intervention_categories': list(set(intervention_categories)),
            'immediate_actions': list(set(immediate_actions)),
            'delivery_timing': delivery_timing,
            'follow_up_required': urgency_score >= 7,
            'crisis_indicators': crisis_indicators,
            'crisis_detected': urgency_score >= 6,
            'recommended_content_count': min(5, max(1, urgency_score // 2)),
            'confidence_score': self._calculate_analysis_confidence(journal_entry, urgency_score)
        }

        # Log critical situations
        if result['crisis_detected']:
            logger.critical(
                f"CRISIS INDICATORS DETECTED: User {journal_entry.user.id}, "
                f"Entry {journal_entry.id}, Urgency: {urgency_score}"
            )

        return result

    def _analyze_stress_triggers(self, triggers):
        """Analyze stress triggers for urgency calculation"""
        additional_urgency = 0
        categories = []
        actions = []

        for trigger in triggers:
            trigger_lower = trigger.lower()

            # Check each trigger pattern category
            for pattern_name, pattern_data in self.stress_trigger_patterns.items():
                if any(kw in trigger_lower for kw in pattern_data['keywords']):
                    additional_urgency += pattern_data['urgency_boost']
                    categories.append(pattern_data['category'])
                    actions.append(pattern_data['action'])
                    break  # Only match first pattern

        return {
            'additional_urgency': min(3, additional_urgency),
            'categories': categories,
            'actions': actions
        }

    def _analyze_content_for_crisis(self, content):
        """Analyze content for crisis indicators"""
        if not content:
            return {'crisis_detected': False, 'indicators': []}

        content_lower = content.lower()
        found_keywords = [kw for kw in self.crisis_keywords if kw in content_lower]

        return {
            'crisis_detected': len(found_keywords) > 0,
            'indicators': [f"Crisis keywords: {', '.join(found_keywords)}"] if found_keywords else []
        }

    def _analyze_performance_indicators(self, entry):
        """Analyze performance indicators for urgency"""
        concerning_patterns = []
        urgency_boost = 0
        categories = []

        if hasattr(entry, 'completion_rate') and entry.completion_rate is not None and entry.completion_rate < 0.5:
            concerning_patterns.append('low_completion_rate')
            urgency_boost += 1
            categories.append('productivity_support')

        if hasattr(entry, 'efficiency_score') and entry.efficiency_score is not None and entry.efficiency_score < 5.0:
            concerning_patterns.append('low_efficiency')
            urgency_boost += 1
            categories.append('efficiency_optimization')

        return {
            'concerning_patterns': concerning_patterns,
            'urgency_boost': urgency_boost,
            'categories': categories
        }

    def _categorize_urgency(self, urgency_score):
        """Categorize urgency level"""
        if urgency_score >= 7:
            return 'critical'
        elif urgency_score >= 5:
            return 'high'
        elif urgency_score >= 3:
            return 'medium'
        elif urgency_score >= 1:
            return 'low'
        else:
            return 'none'

    def _calculate_delivery_timing(self, urgency_score):
        """Calculate optimal delivery timing"""
        if urgency_score >= 7:
            return 'immediate'
        elif urgency_score >= 5:
            return 'same_hour'
        elif urgency_score >= 3:
            return 'same_day'
        elif urgency_score >= 1:
            return 'next_session'
        else:
            return 'routine'

    def _calculate_analysis_confidence(self, entry, urgency_score):
        """Calculate confidence in analysis"""
        confidence = 0.5

        # More data points = higher confidence
        data_points = 0
        if hasattr(entry, 'mood_rating') and entry.mood_rating is not None:
            data_points += 1
        if hasattr(entry, 'stress_level') and entry.stress_level is not None:
            data_points += 1
        if hasattr(entry, 'energy_level') and entry.energy_level is not None:
            data_points += 1
        if entry.content and len(entry.content) > 50:
            data_points += 1

        confidence += (data_points / 4) * 0.3

        if urgency_score >= 5:
            confidence += 0.2

        return min(1.0, confidence)
