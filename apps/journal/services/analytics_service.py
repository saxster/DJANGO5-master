"""
Journal Analytics Service

Centralized analytics service that consolidates all journal analysis functionality:
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

logger = get_journal_logger(__name__)


class JournalAnalyticsService:
    """
    Unified analytics service for journal system

    Consolidates all analytics functionality from:
    - WellbeingAnalyticsEngine
    - JournalPatternAnalyzer
    - Background analytics tasks
    - Views analytics methods

    Provides a clean, testable interface for all journal analytics.
    """

    def __init__(self):
        self.confidence_threshold = 0.6
        self.minimum_data_points = 3

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
                'algorithm_version': '3.0.0'
            }
        }

        logger.info(f"Analytics complete for user {user.id}: confidence={analytics['analysis_metadata']['confidence_level']}")
        return analytics

    def analyze_entry_for_immediate_action(self, journal_entry):
        """
        Analyze individual entry for immediate intervention needs

        Args:
            journal_entry: JournalEntry instance

        Returns:
            dict: Immediate action analysis results
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

    def analyze_long_term_patterns(self, user, days=90):
        """
        Analyze long-term patterns for proactive wellness

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
            'stress_cycles': self._detect_stress_cycles(entries),
            'mood_seasonality': self._analyze_mood_seasonality(entries),
            'energy_work_correlation': self._correlate_energy_with_work(entries),
            'trigger_patterns': self._analyze_recurring_triggers(entries),
            'coping_effectiveness': self._measure_coping_effectiveness(entries),
            'positive_engagement': self._analyze_positive_psychology(entries)
        }

        # Generate predictions and recommendations
        risk_predictions = self._predict_wellbeing_risks(entries)
        optimal_timing = self._calculate_optimal_intervention_timing(entries)
        learning_path = self._generate_learning_path(entries)

        return {
            'detected_patterns': patterns,
            'risk_predictions': risk_predictions,
            'optimal_intervention_timing': optimal_timing,
            'personalized_learning_path': learning_path,
            'confidence_metrics': {
                'pattern_confidence': self._calculate_pattern_confidence(entries),
                'prediction_confidence': self._calculate_prediction_confidence(entries),
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
                'algorithm_version': '3.0.0'
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
        # Entry type patterns
        entry_types = [e.entry_type for e in entries]
        type_counts = Counter(entry_types)

        # Time patterns
        hours = [e.timestamp.hour for e in entries]
        hour_counts = Counter(hours)

        # Weekly patterns
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

        # Recent trend analysis for predictions
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

        # Analyze recent patterns
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
            # Invert stress score (lower stress = higher score)
            avg_stress = sum(e.stress_level for e in stress_entries) / len(stress_entries)
            scores['stress_score'] = round((6 - avg_stress) * 2, 2)  # Convert to 10-point scale

        if energy_entries:
            scores['energy_score'] = round(sum(e.energy_level for e in energy_entries) / len(energy_entries), 2)

        # Calculate composite wellbeing score
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

    # Additional helper methods for specific analyses
    def _analyze_stress_triggers(self, triggers):
        """Analyze stress triggers for urgency calculation"""
        additional_urgency = 0
        categories = []
        actions = []

        STRESS_TRIGGER_PATTERNS = {
            'equipment': ['equipment', 'machine', 'tool', 'device', 'system'],
            'deadline': ['deadline', 'due', 'urgent', 'rush', 'time pressure'],
            'workload': ['overloaded', 'too much', 'exhausted', 'burnout'],
            'interpersonal': ['conflict', 'argument', 'tension', 'difficult'],
            'safety': ['unsafe', 'dangerous', 'risk', 'hazard', 'accident']
        }

        for trigger in triggers:
            trigger_lower = trigger.lower()

            if any(kw in trigger_lower for kw in STRESS_TRIGGER_PATTERNS['equipment']):
                additional_urgency += 2
                categories.append('equipment_stress_management')
                actions.append('equipment_failure_protocol')
            elif any(kw in trigger_lower for kw in STRESS_TRIGGER_PATTERNS['deadline']):
                additional_urgency += 1
                categories.append('time_management')
                actions.append('priority_setting_technique')

        return {
            'additional_urgency': min(3, additional_urgency),
            'categories': categories,
            'actions': actions
        }

    def _analyze_content_for_crisis(self, content):
        """Analyze content for crisis indicators"""
        if not content:
            return {'crisis_detected': False, 'indicators': []}

        CRISIS_KEYWORDS = [
            'hopeless', 'overwhelmed', "can't cope", 'breaking point',
            'giving up', 'no point', 'worthless', 'suicidal'
        ]

        content_lower = content.lower()
        found_keywords = [kw for kw in CRISIS_KEYWORDS if kw in content_lower]

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

    def _calculate_trend_direction(self, values, inverted=False):
        """Calculate trend direction from time series data"""
        if len(values) < 3:
            return 'insufficient_data'

        # Simple linear trend calculation
        first_half = values[:len(values)//2]
        second_half = values[len(values)//2:]

        first_avg = sum(first_half) / len(first_half)
        second_avg = sum(second_half) / len(second_half)

        threshold = 0.5
        if inverted:
            # For stress (lower is better)
            if second_avg < first_avg - threshold:
                return 'improving'
            elif second_avg > first_avg + threshold:
                return 'declining'
        else:
            # For mood/energy (higher is better)
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

        # Check regularity of entries
        dates = [e.timestamp.date() for e in entries]
        date_range = (max(dates) - min(dates)).days

        if date_range == 0:
            return 1.0

        frequency = len(entries) / date_range
        return min(1.0, frequency)

    def _detect_stress_cycles(self, entries):
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

    def _analyze_mood_seasonality(self, entries):
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
            'pattern_strength': 'moderate'  # Simplified for now
        }

    def _correlate_energy_with_work(self, entries):
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
            'energy_draining_activities': [],  # Would implement based on averages
            'energy_boosting_activities': []
        }

    def _analyze_recurring_triggers(self, entries):
        """Analyze recurring stress triggers"""
        all_triggers = []
        for entry in entries:
            if hasattr(entry, 'stress_triggers') and entry.stress_triggers:
                all_triggers.extend(entry.stress_triggers)

        trigger_frequency = Counter(all_triggers)

        return {
            'top_triggers': trigger_frequency.most_common(5),
            'trigger_categories': {}  # Would categorize by type
        }

    def _measure_coping_effectiveness(self, entries):
        """Measure effectiveness of coping strategies"""
        # Simplified implementation
        return {
            'strategy_effectiveness': {},
            'top_strategies': [],
            'recommendations': []
        }

    def _analyze_positive_psychology(self, entries):
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

    def _predict_wellbeing_risks(self, entries):
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

    def _calculate_optimal_intervention_timing(self, entries):
        """Calculate optimal timing for interventions"""
        hour_patterns = defaultdict(list)
        for entry in entries:
            hour_patterns[entry.timestamp.hour].append(1)  # Simple engagement score

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
            'optimal_hours': [9, 12, 18],  # Default
            'peak_engagement_hour': 12
        }

    def _generate_learning_path(self, entries):
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

    def _calculate_pattern_confidence(self, entries):
        """Calculate confidence in pattern detection"""
        data_points = len(entries)
        if data_points >= 60:
            return 0.9
        elif data_points >= 30:
            return 0.75
        else:
            return 0.6

    def _calculate_prediction_confidence(self, entries):
        """Calculate confidence in predictions"""
        return min(0.8, len(entries) / 100)

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
                    scores.append((6 - entry.stress_level) * 2)  # Invert stress

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