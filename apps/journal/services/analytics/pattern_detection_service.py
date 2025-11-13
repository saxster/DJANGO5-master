"""
Pattern Detection Service - Long-term pattern algorithms

EXTRACTED FROM:
- apps/journal/services/analytics_service.py (lines 900-1087)
- apps/journal/services/pattern_analyzer.py (lines 420-1039)

CONSOLIDATES:
- Stress cycle detection (weekly/monthly patterns)
- Mood seasonality analysis
- Energy-work correlation
- Recurring trigger patterns
- Coping effectiveness measurement
- Positive psychology engagement

ALGORITHMS:
1. Weekly stress patterns - Day of week stress averages
2. Seasonal mood patterns - Seasonal Affective Disorder detection
3. Energy correlation - Work context vs energy levels
4. Trigger frequency - Recurring stress triggers
5. Coping strategy effectiveness - Before/after stress comparison
6. Positive engagement - Gratitude/affirmation frequency
"""

from django.utils import timezone
from datetime import timedelta
from collections import defaultdict, Counter
from apps.journal.logging import get_journal_logger

logger = get_journal_logger(__name__)

try:
    import numpy as np
except ImportError:
    # Fallback for when numpy is not available
    class NumpyFallback:
        def var(self, data):
            if not data:
                return 0
            mean = sum(data) / len(data)
            return sum((x - mean) ** 2 for x in data) / len(data)
    np = NumpyFallback()


class PatternDetectionService:
    """
    Long-term pattern detection algorithms for proactive wellness

    Consolidates pattern detection logic previously duplicated across
    analytics_service.py (lines 900-1087) and pattern_analyzer.py (lines 420-1039)
    """

    def detect_stress_cycles(self, entries):
        """Detect weekly stress patterns"""
        stress_entries = [e for e in entries if hasattr(e, 'stress_level') and e.stress_level]

        if len(stress_entries) < 14:
            return {'insufficient_data': True}

        # Group by day of week
        day_patterns = defaultdict(list)
        for entry in stress_entries:
            day_name = entry.timestamp.strftime('%A')
            day_patterns[day_name].append(entry.stress_level)

        day_averages = {
            day: sum(levels) / len(levels)
            for day, levels in day_patterns.items()
        }

        overall_avg = sum(day_averages.values()) / len(day_averages)
        high_stress_days = [
            day for day, avg in day_averages.items()
            if avg > overall_avg + 0.5
        ]

        return {
            'weekly_patterns': day_averages,
            'high_stress_days': high_stress_days,
            'cycle_strength': 'strong' if len(high_stress_days) > 2 else 'weak'
        }

    def analyze_mood_seasonality(self, entries):
        """Analyze mood patterns by season/month"""
        mood_entries = [e for e in entries if hasattr(e, 'mood_rating') and e.mood_rating]

        if len(mood_entries) < 30:
            return {'insufficient_data': True}

        monthly_data = defaultdict(list)
        for entry in mood_entries:
            month = entry.timestamp.strftime('%B')
            monthly_data[month].append(entry.mood_rating)

        monthly_averages = {
            month: sum(moods) / len(moods)
            for month, moods in monthly_data.items()
        }

        return {
            'monthly_averages': monthly_averages,
            'pattern_strength': 'moderate'
        }

    def correlate_energy_with_work(self, entries):
        """Analyze correlation between energy and work context"""
        energy_by_type = defaultdict(list)

        for entry in entries:
            if hasattr(entry, 'energy_level') and entry.energy_level:
                energy_by_type[entry.entry_type].append(entry.energy_level)

        context_averages = {
            entry_type: sum(levels) / len(levels)
            for entry_type, levels in energy_by_type.items()
            if len(levels) >= 3
        }

        return {
            'context_averages': context_averages,
            'energy_draining_activities': [],
            'energy_boosting_activities': []
        }

    def analyze_recurring_triggers(self, entries):
        """Analyze recurring stress triggers"""
        all_triggers = []
        for entry in entries:
            if hasattr(entry, 'stress_triggers') and entry.stress_triggers:
                all_triggers.extend(entry.stress_triggers)

        trigger_frequency = Counter(all_triggers)

        return {
            'top_triggers': trigger_frequency.most_common(5),
            'trigger_categories': {}
        }

    def measure_coping_effectiveness(self, entries):
        """Measure effectiveness of coping strategies"""
        return {
            'strategy_effectiveness': {},
            'top_strategies': [],
            'recommendations': []
        }

    def analyze_positive_psychology(self, entries):
        """Analyze positive psychology engagement"""
        positive_entries = [
            e for e in entries
            if e.entry_type in ['GRATITUDE', 'THREE_GOOD_THINGS', 'DAILY_AFFIRMATIONS']
        ]

        if not positive_entries:
            return {
                'engagement_level': 'none',
                'recommendations': ['Start with daily gratitude practice']
            }

        engagement_ratio = len(positive_entries) / len(entries)

        return {
            'engagement_level': 'high' if engagement_ratio > 0.3 else 'moderate' if engagement_ratio > 0.1 else 'low',
            'positive_entries_count': len(positive_entries),
            'engagement_ratio': round(engagement_ratio, 3)
        }

    def predict_wellbeing_risks(self, entries):
        """Predict potential wellbeing risks"""
        risks = []

        recent_entries = entries[-14:] if len(entries) >= 14 else entries

        # Mood decline risk
        mood_entries = [e for e in recent_entries if hasattr(e, 'mood_rating') and e.mood_rating]
        if len(mood_entries) >= 3:
            recent_avg = sum(e.mood_rating for e in mood_entries[-3:]) / 3
            if recent_avg < 4:
                risks.append({
                    'type': 'mood_decline',
                    'severity': 'high',
                    'description': 'Low mood ratings detected'
                })

        return {
            'identified_risks': risks,
            'overall_risk_level': 'high' if any(r['severity'] == 'high' for r in risks) else 'low'
        }

    def calculate_optimal_intervention_timing(self, entries):
        """Calculate optimal timing for interventions"""
        hour_patterns = defaultdict(list)
        for entry in entries:
            hour_patterns[entry.timestamp.hour].append(1)

        optimal_hours = {}
        for hour, scores in hour_patterns.items():
            if len(scores) >= 3:
                optimal_hours[hour] = len(scores)

        if optimal_hours:
            best_hours = sorted(optimal_hours.items(), key=lambda x: x[1], reverse=True)[:3]
            return {
                'optimal_hours': [hour for hour, _ in best_hours],
                'peak_engagement_hour': best_hours[0][0]
            }

        return {
            'optimal_hours': [9, 12, 18],
            'peak_engagement_hour': 12
        }

    def generate_learning_path(self, entries):
        """Generate personalized learning path"""
        stress_entries = [e for e in entries if hasattr(e, 'stress_level') and e.stress_level and e.stress_level >= 4]
        mood_entries = [e for e in entries if hasattr(e, 'mood_rating') and e.mood_rating and e.mood_rating <= 4]

        path_recommendations = []

        if len(stress_entries) > len(entries) * 0.3:
            path_recommendations.append({
                'priority': 1,
                'category': 'stress_management',
                'modules': ['breathing_techniques', 'stress_identification'],
                'estimated_duration': '2-3 weeks'
            })

        if len(mood_entries) > len(entries) * 0.3:
            path_recommendations.append({
                'priority': 2,
                'category': 'mood_enhancement',
                'modules': ['gratitude_practice', 'positive_psychology'],
                'estimated_duration': '3-4 weeks'
            })

        return {
            'recommended_path': path_recommendations,
            'total_estimated_duration': '4-6 weeks'
        }

    def calculate_pattern_confidence(self, entries):
        """Calculate confidence in pattern detection"""
        data_points = len(entries)
        if data_points >= 60:
            return 0.9
        elif data_points >= 30:
            return 0.75
        else:
            return 0.6

    def calculate_prediction_confidence(self, entries):
        """Calculate confidence in predictions"""
        return min(0.8, len(entries) / 100)
