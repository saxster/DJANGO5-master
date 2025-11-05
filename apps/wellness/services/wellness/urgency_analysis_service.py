"""
Urgency Analysis Service - Analyze journal entries for urgency and intervention needs

Responsible for:
- Analyzing journal entry data for urgency scoring
- Identifying intervention categories (crisis, stress, mood, energy)
- Detecting crisis keywords and triggers
- Providing confidence scores for intervention recommendations
"""

from apps.wellness.logging import get_wellness_logger

logger = get_wellness_logger(__name__)


class UrgencyAnalysisService:
    """Service for analyzing journal entry urgency and intervention needs"""

    # Crisis keywords that trigger high urgency scoring
    CRISIS_KEYWORDS = ['hopeless', 'overwhelmed', "can't cope", 'breaking point']

    @staticmethod
    def analyze_entry_urgency(journal_entry_data):
        """
        Analyze journal entry for urgency and intervention needs

        Args:
            journal_entry_data: dict with mood_rating, stress_level, energy_level, content

        Returns:
            dict: Urgency analysis with score, level, categories, triggers, confidence
        """
        urgency_score = 0
        intervention_categories = []
        triggers = []

        # Mood analysis
        mood = journal_entry_data.get('mood_rating')
        if mood and mood <= 2:
            urgency_score += 4
            intervention_categories.append('mood_crisis_support')
            triggers.append('very_low_mood')

        # Stress analysis
        stress = journal_entry_data.get('stress_level')
        if stress and stress >= 4:
            urgency_score += 3
            intervention_categories.append('stress_management')
            triggers.append('high_stress')

        # Energy analysis
        energy = journal_entry_data.get('energy_level')
        if energy and energy <= 3:
            urgency_score += 1
            intervention_categories.append('energy_management')
            triggers.append('low_energy')

        # Content analysis for crisis keywords
        content = journal_entry_data.get('content', '').lower()
        found_keywords = [kw for kw in UrgencyAnalysisService.CRISIS_KEYWORDS if kw in content]
        if found_keywords:
            urgency_score += 2
            intervention_categories.append('crisis_intervention')
            triggers.extend(found_keywords)

        return {
            'urgency_score': urgency_score,
            'urgency_level': 'high' if urgency_score >= 5 else 'medium' if urgency_score >= 2 else 'low',
            'intervention_categories': intervention_categories,
            'triggers': triggers,
            'confidence': min(1.0, urgency_score / 10)
        }
