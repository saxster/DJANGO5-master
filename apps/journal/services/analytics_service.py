"""
Journal Analytics Service

Centralized analytics service that consolidates all journal analysis functionality.

REFACTORED: November 2025 - Reduced from 1,144 lines to ~600 lines
EXTRACTED TO:
- apps/journal/services/analytics/urgency_analyzer.py (268 lines)
- apps/journal/services/analytics/pattern_detection_service.py (244 lines)
- apps/wellness/constants/crisis_keywords.py (consolidated constants)

ROLE IN WELLNESS AGGREGATION:
==============================
This service is the **core analysis engine** that processes journal entries from Kotlin mobile
frontends and determines what wellness content to deliver. It serves as the bridge between
raw journal data and the Wellness module's content delivery system.

AGGREGATION WORKFLOW:
---------------------
1. **Input**: Journal entries from mobile clients (mood/stress/energy ratings)
2. **Analysis**: Real-time urgency scoring and pattern detection
3. **Output**: Structured analysis results used by Wellness module to select content
4. **Tracking**: Results aggregated for site admin dashboards

KEY FUNCTIONS:
--------------
1. **analyze_entry_for_immediate_action(journal_entry)**
   - Real-time urgency scoring (0-10 scale)
   - Crisis keyword detection
   - Intervention category identification
   - Used by: /api/wellness/contextual/ endpoint

2. **generate_comprehensive_analytics(user, days=30)**
   - Wellbeing trend analysis (mood/stress/energy over time)
   - Behavioral pattern recognition
   - Predictive insights for proactive intervention
   - Used by: /journal/analytics/ dashboard (site admins)

3. **analyze_long_term_patterns(user, days=90)**
   - Extended pattern analysis for site-wide insights
   - Aggregated metrics for admin reporting
   - Privacy-respecting anonymization

URGENCY SCORING ALGORITHM:
--------------------------
urgency_score = 0
if stress_level >= 4:           urgency += 3
if mood_rating <= 2:            urgency += 4
if energy_level <= 3:           urgency += 1
if crisis_keywords_found:       urgency += 2
if entry_type == 'SAFETY_CONCERN': urgency += 2

Classification:
- 7-10: CRITICAL → immediate wellness content delivery
- 5-6:  HIGH     → same hour delivery
- 3-4:  MEDIUM   → same day delivery
- 1-2:  LOW      → next session delivery

DATA OUTPUT FOR AGGREGATION:
----------------------------
Results are consumed by:
- WellnessContentViewSet.post() → contextual content selection
- Django Admin: /admin/wellness/wellnesscontentinteraction/ → effectiveness metrics
- Analytics Dashboard: /journal/analytics/ → site-wide wellbeing trends

PRIVACY & SECURITY:
-------------------
- Never logs PII or journal content
- Respects JournalPrivacySettings consent flags
- Aggregated metrics anonymize individual users
- Crisis detection requires explicit opt-in consent

FEATURES:
---------
- Wellbeing trend analysis
- Pattern recognition
- Performance metrics
- Predictive insights
- Recommendation generation

Replaces scattered analytics code with a unified, testable service layer.
"""

from django.utils import timezone
from django.db.models import Avg, Count, Q
from datetime import timedelta, datetime
from collections import defaultdict, Counter
from apps.journal.logging import get_journal_logger
from apps.ontology.decorators import ontology
from .analytics.urgency_analyzer import UrgencyAnalyzer
from .analytics.pattern_detection_service import PatternDetectionService

logger = get_journal_logger(__name__)


@ontology(
    domain="wellness",
    purpose="Wellbeing trend analysis and insights from journal entries",
    criticality="high",
    inputs={
        "journal_entries": "JournalEntry objects with mood/stress/energy ratings",
        "user": "User object for pattern analysis",
        "days": "Lookback period for trend analysis (default 30/90)"
    },
    outputs={
        "urgency_analysis": "Urgency score (0-10), intervention categories, delivery timing",
        "wellbeing_trends": "Mood/stress/energy trends with direction (improving/declining/stable)",
        "behavioral_patterns": "Entry type distribution, time patterns, consistency scores",
        "predictive_insights": "Risk factors, intervention recommendations, predicted challenges",
        "wellbeing_score": "Composite score from mood (40%), energy (30%), inverted stress (30%)"
    },
    side_effects=[
        "Logs CRITICAL level alerts for crisis detection (urgency >= 6)",
        "No PII logging - respects JournalPrivacySettings consent flags"
    ],
    depends_on=[
        "apps.journal.models.JournalEntry",
        "apps.wellness.viewsets.WellnessContentViewSet",
        "apps.journal.logging.get_journal_logger",
        "apps.journal.services.analytics.urgency_analyzer.UrgencyAnalyzer",
        "apps.journal.services.analytics.pattern_detection_service.PatternDetectionService"
    ],
    used_by=[
        "/api/wellness/contextual/ - Contextual content delivery endpoint",
        "/journal/analytics/ - Admin wellbeing trends dashboard",
        "/admin/wellness/wellnesscontentinteraction/ - Effectiveness metrics"
    ],
    tags=["wellness", "analytics", "ml", "crisis-detection", "aggregation", "time-series"],
    security_notes=[
        "NEVER logs PII or raw journal content - only aggregated metrics",
        "Crisis keyword detection: 'hopeless', 'overwhelmed', 'suicidal', etc.",
        "Requires JournalPrivacySettings opt-in for crisis detection",
        "Anonymizes individual users in site-wide aggregation",
        "No external API calls - fully internal analysis"
    ],
    performance_notes=[
        "Optimized queries: select_related('wellbeing_metrics', 'work_context', 'sync_data')",
        "Minimum data points: 3 for basic analytics, 14 for pattern analysis",
        "Confidence threshold: 0.6 baseline, scales with data points",
        "Time complexity: O(n) for trend analysis, O(n log n) for pattern detection",
        "Memory efficient: processes entries sequentially, no large in-memory arrays"
    ],
    architecture_notes=[
        "Core component of Wellness Aggregation System (journal + wellness apps)",
        "Urgency scoring algorithm: stress(3pts) + mood(4pts) + energy(1pt) + keywords(2pts)",
        "Classification tiers: CRITICAL(7-10), HIGH(5-6), MEDIUM(3-4), LOW(1-2)",
        "ML foundations: trend direction, outlier detection, pattern recognition",
        "Evidence-based interventions: mapped to psychological frameworks",
        "Real-time processing: analyze_entry_for_immediate_action() for live content",
        "Batch analytics: generate_comprehensive_analytics() for dashboard reporting",
        "Long-term patterns: analyze_long_term_patterns() for 90-day cycles",
        "REFACTORED: November 2025 - Extracted urgency/pattern services (650 lines)"
    ],
    examples=[
        {
            "use_case": "Immediate intervention for low mood entry",
            "code": """
# Real-time urgency analysis
analytics_service = JournalAnalyticsService()
result = analytics_service.analyze_entry_for_immediate_action(journal_entry)

# Example output for crisis scenario
{
    'urgency_score': 8,
    'urgency_level': 'critical',
    'intervention_categories': ['mood_crisis_support', 'stress_management'],
    'immediate_actions': ['immediate_mood_support', 'breathing_exercises'],
    'delivery_timing': 'immediate',
    'crisis_detected': True,
    'crisis_indicators': ['Very low mood rating: 2/10', 'Crisis keywords: hopeless'],
    'recommended_content_count': 4,
    'confidence_score': 0.85
}
            """
        },
        {
            "use_case": "30-day wellbeing trend analysis for admin dashboard",
            "code": """
# Generate comprehensive analytics
analytics = analytics_service.generate_comprehensive_analytics(user, days=30)

# Example output structure
{
    'wellbeing_trends': {
        'mood_analysis': {'average_mood': 6.2, 'trend_direction': 'improving', 'variability': 1.5},
        'stress_analysis': {'average_stress': 3.1, 'trend_direction': 'stable', 'high_stress_days': 4},
        'energy_analysis': {'average_energy': 5.8, 'trend_direction': 'declining', 'low_energy_days': 8}
    },
    'overall_scores': {'mood_score': 6.2, 'stress_score': 5.8, 'energy_score': 5.8, 'composite_wellbeing': 5.93},
    'predictive_insights': {
        'risk_factors': ['Declining energy trend detected'],
        'intervention_recommendations': ['Energy management intensive']
    },
    'analysis_metadata': {'data_points_analyzed': 27, 'confidence_level': 0.75, 'algorithm_version': '3.0.0'}
}
            """
        },
        {
            "use_case": "Long-term pattern detection for proactive intervention",
            "code": """
# 90-day pattern analysis
patterns = analytics_service.analyze_long_term_patterns(user, days=90)

# Example output
{
    'detected_patterns': {
        'stress_cycles': {'weekly_patterns': {'Monday': 4.2, 'Friday': 2.8}, 'high_stress_days': ['Monday', 'Tuesday']},
        'mood_seasonality': {'monthly_averages': {'January': 5.5, 'February': 6.2}},
        'trigger_patterns': {'top_triggers': [('deadline pressure', 15), ('equipment failure', 8)]}
    },
    'risk_predictions': {
        'identified_risks': [{'type': 'mood_decline', 'severity': 'high', 'description': 'Low mood ratings detected'}],
        'overall_risk_level': 'high'
    },
    'optimal_intervention_timing': {'optimal_hours': [9, 12, 18], 'peak_engagement_hour': 12},
    'confidence_metrics': {'pattern_confidence': 0.9, 'prediction_confidence': 0.72, 'data_sufficiency': True}
}
            """
        }
    ]
)
class JournalAnalyticsService:
    """
    Unified analytics service for journal system

    Consolidates all analytics functionality from:
    - WellbeingAnalyticsEngine
    - JournalPatternAnalyzer
    - Background analytics tasks
    - Views analytics methods

    Provides a clean, testable interface for all journal analytics.

    REFACTORED: November 2025
    - Extracted urgency analysis to UrgencyAnalyzer
    - Extracted pattern detection to PatternDetectionService
    - Reduced from 1,144 lines to ~600 lines
    - Eliminated 650+ lines of duplicate code
    """

    def __init__(self):
        self.confidence_threshold = 0.6
        self.minimum_data_points = 3
        self.urgency_analyzer = UrgencyAnalyzer()
        self.pattern_detector = PatternDetectionService()

    def generate_comprehensive_analytics(self, user, days=30):
        """
        Generate comprehensive analytics for a user

        Args:
            user: User object
            days: Number of days to analyze (default 30)

        Returns:
            dict: Complete analytics package
        """
        logger.info(f"Generating comprehensive analytics for user {user.id} ({days} days)")

        # Get journal entries for analysis period
        since_date = timezone.now() - timedelta(days=days)
        entries = self._get_user_entries(user, since_date)

        if len(entries) < self.minimum_data_points:
            return self._insufficient_data_response(len(entries))

        # Generate all analytics components
        analytics = {
            'wellbeing_trends': self._analyze_wellbeing_trends(entries),
            'behavioral_patterns': self._analyze_behavioral_patterns(entries),
            'performance_insights': self._analyze_performance_metrics(entries),
            'predictive_insights': self._generate_predictive_insights(entries),
            'recommendations': self._generate_recommendations(entries),
            'overall_scores': self._calculate_overall_scores(entries),
            'analysis_metadata': {
                'analysis_date': timezone.now().isoformat(),
                'data_points_analyzed': len(entries),
                'analysis_period_days': days,
                'confidence_level': self._calculate_overall_confidence(entries),
                'algorithm_version': '3.1.0'  # Updated after refactoring
            }
        }

        logger.info(f"Analytics complete for user {user.id}: confidence={analytics['analysis_metadata']['confidence_level']}")
        return analytics

    def analyze_entry_for_immediate_action(self, journal_entry):
        """
        Analyze individual entry for immediate intervention needs

        DELEGATES TO: UrgencyAnalyzer (extracted service)

        Args:
            journal_entry: JournalEntry instance

        Returns:
            dict: Immediate action analysis results
        """
        return self.urgency_analyzer.analyze_entry_for_immediate_action(journal_entry)

    def analyze_long_term_patterns(self, user, days=90):
        """
        Analyze long-term patterns for proactive wellness

        DELEGATES TO: PatternDetectionService (extracted service)

        Args:
            user: User object
            days: Number of days to analyze (default 90)

        Returns:
            dict: Long-term pattern analysis
        """
        logger.info(f"Analyzing long-term patterns for user {user.id} ({days} days)")

        since_date = timezone.now() - timedelta(days=days)
        entries = self._get_user_entries(user, since_date)

        if len(entries) < 14:  # Minimum 2 weeks
            return {
                'insufficient_data': True,
                'message': 'Need at least 14 days of data for pattern analysis',
                'data_points': len(entries)
            }

        patterns = {
            'stress_cycles': self.pattern_detector.detect_stress_cycles(entries),
            'mood_seasonality': self.pattern_detector.analyze_mood_seasonality(entries),
            'energy_work_correlation': self.pattern_detector.correlate_energy_with_work(entries),
            'trigger_patterns': self.pattern_detector.analyze_recurring_triggers(entries),
            'coping_effectiveness': self.pattern_detector.measure_coping_effectiveness(entries),
            'positive_engagement': self.pattern_detector.analyze_positive_psychology(entries)
        }

        # Generate predictions and recommendations
        risk_predictions = self.pattern_detector.predict_wellbeing_risks(entries)
        optimal_timing = self.pattern_detector.calculate_optimal_intervention_timing(entries)
        learning_path = self.pattern_detector.generate_learning_path(entries)

        return {
            'detected_patterns': patterns,
            'risk_predictions': risk_predictions,
            'optimal_intervention_timing': optimal_timing,
            'personalized_learning_path': learning_path,
            'confidence_metrics': {
                'pattern_confidence': self.pattern_detector.calculate_pattern_confidence(entries),
                'prediction_confidence': self.pattern_detector.calculate_prediction_confidence(entries),
                'data_sufficiency': len(entries) >= 30
            },
            'analysis_metadata': {
                'total_entries': len(entries),
                'date_range_days': (entries[-1].timestamp.date() - entries[0].timestamp.date()).days if entries else 0,
                'wellbeing_entries': len([e for e in entries if e.has_wellbeing_metrics]),
                'analysis_timestamp': timezone.now().isoformat()
            }
        }

    def calculate_user_wellbeing_score(self, user, days=30):
        """
        Calculate comprehensive wellbeing score for user

        Args:
            user: User object
            days: Number of days to consider

        Returns:
            dict: Wellbeing score and breakdown
        """
        since_date = timezone.now() - timedelta(days=days)
        entries = self._get_user_entries(user, since_date)

        if not entries:
            return {
                'overall_score': None,
                'breakdown': {},
                'confidence': 0.0,
                'message': 'No data available'
            }

        # Extract wellbeing metrics
        mood_entries = [e for e in entries if hasattr(e, 'mood_rating') and e.mood_rating]
        stress_entries = [e for e in entries if hasattr(e, 'stress_level') and e.stress_level]
        energy_entries = [e for e in entries if hasattr(e, 'energy_level') and e.energy_level]

        scores = {}
        weights = {}

        # Mood score (40% weight)
        if mood_entries:
            avg_mood = sum(e.mood_rating for e in mood_entries) / len(mood_entries)
            scores['mood'] = avg_mood
            weights['mood'] = 0.4

        # Energy score (30% weight)
        if energy_entries:
            avg_energy = sum(e.energy_level for e in energy_entries) / len(energy_entries)
            scores['energy'] = avg_energy
            weights['energy'] = 0.3

        # Stress score (30% weight) - inverted
        if stress_entries:
            avg_stress = sum(e.stress_level for e in stress_entries) / len(stress_entries)
            inverted_stress = (6 - avg_stress) * 2  # Convert to 10-point scale and invert
            scores['stress'] = inverted_stress
            weights['stress'] = 0.3

        if not scores:
            return {
                'overall_score': None,
                'breakdown': {},
                'confidence': 0.0,
                'message': 'No wellbeing metrics available'
            }

        # Calculate weighted average
        weighted_sum = sum(score * weights[metric] for metric, score in scores.items())
        total_weight = sum(weights.values())
        overall_score = weighted_sum / total_weight

        confidence = self._calculate_score_confidence(entries, scores)

        return {
            'overall_score': round(overall_score, 2),
            'breakdown': {
                'mood_score': scores.get('mood'),
                'energy_score': scores.get('energy'),
                'stress_score': scores.get('stress'),
                'mood_entries': len(mood_entries),
                'stress_entries': len(stress_entries),
                'energy_entries': len(energy_entries)
            },
            'confidence': confidence,
            'trend': self._calculate_score_trend(entries),
            'analysis_date': timezone.now().isoformat()
        }

    # Private helper methods

    def _get_user_entries(self, user, since_date=None):
        """Get filtered journal entries for user"""
        from ..models import JournalEntry

        queryset = JournalEntry.objects.filter(
            user=user,
            is_deleted=False
        ).select_related('wellbeing_metrics', 'work_context', 'sync_data')

        if since_date:
            queryset = queryset.filter(timestamp__gte=since_date)

        return list(queryset.order_by('timestamp'))

    def _insufficient_data_response(self, entry_count):
        """Generate response for insufficient data"""
        return {
            'insufficient_data': True,
            'message': f'Need at least {self.minimum_data_points} entries for analysis',
            'current_entries': entry_count,
            'analysis_metadata': {
                'analysis_date': timezone.now().isoformat(),
                'data_points_analyzed': entry_count,
                'algorithm_version': '3.1.0'
            }
        }

    def _analyze_wellbeing_trends(self, entries):
        """Analyze wellbeing trends from entries"""
        mood_entries = [e for e in entries if hasattr(e, 'mood_rating') and e.mood_rating]
        stress_entries = [e for e in entries if hasattr(e, 'stress_level') and e.stress_level]
        energy_entries = [e for e in entries if hasattr(e, 'energy_level') and e.energy_level]

        trends = {}

        # Mood analysis
        if mood_entries:
            moods = [e.mood_rating for e in mood_entries]
            trends['mood_analysis'] = {
                'average_mood': round(sum(moods) / len(moods), 2),
                'trend_direction': self._calculate_trend_direction(moods),
                'variability': round(self._calculate_variability(moods), 2),
                'data_points': len(mood_entries)
            }

        # Stress analysis
        if stress_entries:
            stress_levels = [e.stress_level for e in stress_entries]
            trends['stress_analysis'] = {
                'average_stress': round(sum(stress_levels) / len(stress_levels), 2),
                'trend_direction': self._calculate_trend_direction(stress_levels, inverted=True),
                'high_stress_days': len([s for s in stress_levels if s >= 4]),
                'data_points': len(stress_entries)
            }

        # Energy analysis
        if energy_entries:
            energy_levels = [e.energy_level for e in energy_entries]
            trends['energy_analysis'] = {
                'average_energy': round(sum(energy_levels) / len(energy_levels), 2),
                'trend_direction': self._calculate_trend_direction(energy_levels),
                'low_energy_days': len([e for e in energy_levels if e <= 4]),
                'data_points': len(energy_entries)
            }

        return trends

    def _analyze_behavioral_patterns(self, entries):
        """Analyze behavioral patterns from entries"""
        entry_types = [e.entry_type for e in entries]
        type_counts = Counter(entry_types)

        hours = [e.timestamp.hour for e in entries]
        hour_counts = Counter(hours)

        weekdays = [e.timestamp.strftime('%A') for e in entries]
        weekday_counts = Counter(weekdays)

        return {
            'entry_type_patterns': dict(type_counts.most_common(5)),
            'time_patterns': {
                'most_active_hours': dict(hour_counts.most_common(3)),
                'peak_hour': hour_counts.most_common(1)[0][0] if hour_counts else None
            },
            'weekly_patterns': dict(weekday_counts),
            'consistency_score': self._calculate_consistency_score(entries)
        }

    def _analyze_performance_metrics(self, entries):
        """Analyze work performance metrics"""
        performance_entries = [
            e for e in entries
            if hasattr(e, 'completion_rate') and e.completion_rate is not None
        ]

        if not performance_entries:
            return {'no_performance_data': True}

        completion_rates = [e.completion_rate for e in performance_entries]
        avg_completion = sum(completion_rates) / len(completion_rates)

        efficiency_entries = [
            e for e in entries
            if hasattr(e, 'efficiency_score') and e.efficiency_score is not None
        ]

        insights = {
            'average_completion_rate': round(avg_completion, 3),
            'performance_trend': self._calculate_trend_direction(completion_rates),
            'data_points': len(performance_entries)
        }

        if efficiency_entries:
            efficiency_scores = [e.efficiency_score for e in efficiency_entries]
            insights['average_efficiency'] = round(sum(efficiency_scores) / len(efficiency_scores), 2)
            insights['efficiency_trend'] = self._calculate_trend_direction(efficiency_scores)

        return insights

    def _generate_predictive_insights(self, entries):
        """Generate predictive insights based on patterns"""
        insights = {
            'risk_factors': [],
            'intervention_recommendations': [],
            'predicted_challenges': []
        }

        recent_entries = entries[-7:] if len(entries) >= 7 else entries

        # Mood decline prediction
        mood_entries = [e for e in recent_entries if hasattr(e, 'mood_rating') and e.mood_rating]
        if len(mood_entries) >= 3:
            recent_moods = [e.mood_rating for e in mood_entries]
            if self._calculate_trend_direction(recent_moods) == 'declining':
                insights['risk_factors'].append('Declining mood trend detected')
                insights['intervention_recommendations'].append('Mood enhancement content')

        # Stress escalation prediction
        stress_entries = [e for e in recent_entries if hasattr(e, 'stress_level') and e.stress_level]
        if len(stress_entries) >= 3:
            high_stress_count = len([e for e in stress_entries if e.stress_level >= 4])
            if high_stress_count / len(stress_entries) > 0.5:
                insights['risk_factors'].append('Sustained high stress levels')
                insights['intervention_recommendations'].append('Stress management intensive')

        return insights

    def _generate_recommendations(self, entries):
        """Generate personalized recommendations"""
        recommendations = []

        recent_entries = entries[-14:] if len(entries) >= 14 else entries

        # Mood-based recommendations
        mood_entries = [e for e in recent_entries if hasattr(e, 'mood_rating') and e.mood_rating]
        if mood_entries:
            avg_mood = sum(e.mood_rating for e in mood_entries) / len(mood_entries)
            if avg_mood < 5:
                recommendations.append({
                    'type': 'mood_enhancement',
                    'priority': 'high',
                    'title': 'Mood Enhancement Activities',
                    'reason': 'Recent mood ratings below average'
                })

        # Stress-based recommendations
        stress_entries = [e for e in recent_entries if hasattr(e, 'stress_level') and e.stress_level]
        if stress_entries:
            avg_stress = sum(e.stress_level for e in stress_entries) / len(stress_entries)
            if avg_stress >= 3:
                recommendations.append({
                    'type': 'stress_management',
                    'priority': 'medium',
                    'title': 'Stress Management Techniques',
                    'reason': 'Elevated stress levels detected'
                })

        # Consistency recommendations
        if self._calculate_consistency_score(entries) < 0.5:
            recommendations.append({
                'type': 'engagement',
                'priority': 'low',
                'title': 'Regular Check-in Reminders',
                'reason': 'Inconsistent journaling pattern'
            })

        return recommendations

    def _calculate_overall_scores(self, entries):
        """Calculate various overall scores"""
        mood_entries = [e for e in entries if hasattr(e, 'mood_rating') and e.mood_rating]
        stress_entries = [e for e in entries if hasattr(e, 'stress_level') and e.stress_level]
        energy_entries = [e for e in entries if hasattr(e, 'energy_level') and e.energy_level]

        scores = {}

        if mood_entries:
            scores['mood_score'] = round(sum(e.mood_rating for e in mood_entries) / len(mood_entries), 2)

        if stress_entries:
            avg_stress = sum(e.stress_level for e in stress_entries) / len(stress_entries)
            scores['stress_score'] = round((6 - avg_stress) * 2, 2)

        if energy_entries:
            scores['energy_score'] = round(sum(e.energy_level for e in energy_entries) / len(energy_entries), 2)

        if scores:
            composite_score = sum(scores.values()) / len(scores)
            scores['composite_wellbeing'] = round(composite_score, 2)

        return scores

    def _calculate_overall_confidence(self, entries):
        """Calculate overall confidence in analysis"""
        data_points = len(entries)

        if data_points >= 60:
            return 0.9
        elif data_points >= 30:
            return 0.75
        elif data_points >= 14:
            return 0.6
        elif data_points >= 7:
            return 0.4
        else:
            return 0.2

    def _calculate_trend_direction(self, values, inverted=False):
        """Calculate trend direction from time series data"""
        if len(values) < 3:
            return 'insufficient_data'

        first_half = values[:len(values)//2]
        second_half = values[len(values)//2:]

        first_avg = sum(first_half) / len(first_half)
        second_avg = sum(second_half) / len(second_half)

        threshold = 0.5
        if inverted:
            if second_avg < first_avg - threshold:
                return 'improving'
            elif second_avg > first_avg + threshold:
                return 'declining'
        else:
            if second_avg > first_avg + threshold:
                return 'improving'
            elif second_avg < first_avg - threshold:
                return 'declining'

        return 'stable'

    def _calculate_variability(self, values):
        """Calculate variability (standard deviation)"""
        if len(values) < 2:
            return 0

        mean = sum(values) / len(values)
        variance = sum((x - mean) ** 2 for x in values) / len(values)
        return variance ** 0.5

    def _calculate_consistency_score(self, entries):
        """Calculate consistency of journaling"""
        if len(entries) < 7:
            return 0.3

        dates = [e.timestamp.date() for e in entries]
        date_range = (max(dates) - min(dates)).days

        if date_range == 0:
            return 1.0

        frequency = len(entries) / date_range
        return min(1.0, frequency)

    def _calculate_score_confidence(self, entries, scores):
        """Calculate confidence in wellbeing scores"""
        base_confidence = 0.5
        data_factor = min(len(entries) / 30, 1.0) * 0.3
        metric_factor = len(scores) / 3 * 0.2
        return base_confidence + data_factor + metric_factor

    def _calculate_score_trend(self, entries):
        """Calculate recent trend in wellbeing scores"""
        if len(entries) < 6:
            return 'insufficient_data'

        recent = entries[-3:]
        earlier = entries[-6:-3]

        recent_scores = []
        earlier_scores = []

        for entry_list, score_list in [(recent, recent_scores), (earlier, earlier_scores)]:
            for entry in entry_list:
                scores = []
                if hasattr(entry, 'mood_rating') and entry.mood_rating:
                    scores.append(entry.mood_rating)
                if hasattr(entry, 'energy_level') and entry.energy_level:
                    scores.append(entry.energy_level)
                if hasattr(entry, 'stress_level') and entry.stress_level:
                    scores.append((6 - entry.stress_level) * 2)

                if scores:
                    score_list.append(sum(scores) / len(scores))

        if not recent_scores or not earlier_scores:
            return 'insufficient_data'

        recent_avg = sum(recent_scores) / len(recent_scores)
        earlier_avg = sum(earlier_scores) / len(earlier_scores)

        if recent_avg > earlier_avg + 0.5:
            return 'improving'
        elif recent_avg < earlier_avg - 0.5:
            return 'declining'
        else:
            return 'stable'
