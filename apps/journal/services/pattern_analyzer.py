"""
Journal Pattern Recognition Service

EXACT ALGORITHMS: All pattern recognition moved from Kotlin to Django
Real-time analysis of journal entries for immediate wellness interventions

Implements the complete algorithm from DJANGO_BACKEND_COMPLETE_JOURNAL_SPECIFICATION.md:
- Immediate intervention detection with urgency scoring
- Long-term pattern analysis for proactive wellness
- Crisis indicator detection and response triggering
- Stress cycle analysis and mood seasonality detection
- Coping strategy effectiveness measurement
- Positive psychology engagement analysis
"""

from django.utils import timezone
import re
import numpy as np

logger = logging.getLogger(__name__)


class JournalPatternAnalyzer:
    """
    EXACT ALGORITHMS: All pattern recognition moved from Kotlin to Django
    Real-time analysis of journal entries for immediate wellness interventions
    """

    # Crisis keywords for content analysis
    CRISIS_KEYWORDS = [
        'hopeless', 'overwhelmed', "can't cope", 'breaking point',
        'giving up', 'no point', 'worthless', 'suicidal', 'end it all',
        'nobody cares', 'failure', 'disaster', 'catastrophe', 'ruined'
    ]

    # Stress trigger patterns
    STRESS_TRIGGER_PATTERNS = {
        'equipment': ['equipment', 'machine', 'tool', 'device', 'system', 'malfunction'],
        'deadline': ['deadline', 'due', 'urgent', 'rush', 'time pressure', 'behind schedule'],
        'workload': ['overloaded', 'too much', 'exhausted', 'burnout', 'overwhelmed'],
        'interpersonal': ['conflict', 'argument', 'tension', 'difficult', 'colleague'],
        'safety': ['unsafe', 'dangerous', 'risk', 'hazard', 'accident', 'injury']
    }

    def analyze_entry_for_immediate_action(self, journal_entry):
        """
        CRITICAL ALGORITHM: Immediate intervention detection
        MOVED FROM: Kotlin WellbeingInsightsViewModel.calculateOverallWellbeingScore()

        Urgency Scoring Algorithm:
        - Stress level ≥ 4: +3 points (high stress threshold)
        - Mood ≤ 2: +4 points (crisis mood threshold)
        - Energy ≤ 3: +1 point (fatigue threshold)
        - Equipment/safety triggers: +2 points (workplace safety)
        - Deadline/pressure triggers: +1 point (time management)

        Total Score ≥ 5: Immediate intervention required
        Total Score 3-4: Same-day intervention recommended
        Total Score 1-2: Next-session intervention
        """

        urgency_score = 0
        intervention_categories = []
        immediate_actions = []
        crisis_indicators = []

        logger.debug(f"Analyzing entry {journal_entry.id} for immediate action needs")

        # Stress urgency analysis
        if journal_entry.stress_level and journal_entry.stress_level >= 4:
            urgency_score += 3
            intervention_categories.append('stress_management')
            immediate_actions.append('breathing_exercises')

            # Analyze stress triggers for targeted content
            triggers = journal_entry.stress_triggers or []
            stress_trigger_analysis = self._analyze_stress_triggers(triggers)
            urgency_score += stress_trigger_analysis['additional_urgency']
            intervention_categories.extend(stress_trigger_analysis['categories'])
            immediate_actions.extend(stress_trigger_analysis['actions'])

        # Mood crisis detection
        if journal_entry.mood_rating and journal_entry.mood_rating <= 2:
            urgency_score += 4
            intervention_categories.append('mood_crisis_support')
            immediate_actions.append('immediate_mood_support')
            crisis_indicators.append(f'Very low mood rating: {journal_entry.mood_rating}/10')

            # Check for crisis indicators in content
            content_analysis = self._analyze_content_for_crisis(journal_entry.content or '')
            if content_analysis['crisis_detected']:
                urgency_score += 2
                intervention_categories.append('crisis_intervention')
                crisis_indicators.extend(content_analysis['indicators'])
                immediate_actions.append('crisis_support_protocol')

        # Energy depletion analysis
        if journal_entry.energy_level and journal_entry.energy_level <= 3:
            urgency_score += 1
            intervention_categories.append('energy_management')
            immediate_actions.append('energy_boost_techniques')

        # Safety concern analysis
        if journal_entry.entry_type == 'SAFETY_CONCERN':
            urgency_score += 2
            intervention_categories.append('workplace_safety_education')
            immediate_actions.append('safety_protocols')

        # Work performance correlation
        performance_indicators = self._analyze_performance_indicators(journal_entry)
        if performance_indicators['concerning_patterns']:
            urgency_score += performance_indicators['urgency_boost']
            intervention_categories.extend(performance_indicators['categories'])

        # Calculate intervention timing
        urgency_level = self._categorize_urgency(urgency_score)
        delivery_timing = self._calculate_delivery_timing(urgency_score)

        result = {
            'urgency_score': urgency_score,  # 0-10+ scale
            'urgency_level': urgency_level,
            'intervention_categories': list(set(intervention_categories)),
            'immediate_actions': list(set(immediate_actions)),
            'delivery_timing': delivery_timing,
            'follow_up_required': urgency_score >= 7,
            'crisis_indicators': crisis_indicators,
            'crisis_detected': urgency_score >= 6,
            'recommended_content_count': min(5, max(1, urgency_score // 2)),
            'confidence_score': self._calculate_confidence(journal_entry, urgency_score)
        }

        logger.info(f"Pattern analysis complete for entry {journal_entry.id}: urgency={urgency_score}, level={urgency_level}")

        # Log crisis situations for monitoring
        if result['crisis_detected']:
            logger.critical(
                f"CRISIS INDICATORS DETECTED: User {journal_entry.user.id} "
                f"({journal_entry.user.peoplename}), Entry {journal_entry.id}, "
                f"Urgency: {urgency_score}, Indicators: {'; '.join(crisis_indicators)}"
            )

        return result

    def _analyze_stress_triggers(self, stress_triggers):
        """Analyze stress triggers for targeted interventions"""
        additional_urgency = 0
        categories = []
        actions = []

        for trigger in stress_triggers:
            trigger_lower = trigger.lower()

            # Equipment/technical stress
            if any(keyword in trigger_lower for keyword in self.STRESS_TRIGGER_PATTERNS['equipment']):
                additional_urgency += 2
                categories.append('equipment_stress_management')
                actions.append('equipment_failure_protocol')

            # Deadline pressure
            elif any(keyword in trigger_lower for keyword in self.STRESS_TRIGGER_PATTERNS['deadline']):
                additional_urgency += 1
                categories.append('time_management')
                actions.append('priority_setting_technique')

            # Workload stress
            elif any(keyword in trigger_lower for keyword in self.STRESS_TRIGGER_PATTERNS['workload']):
                additional_urgency += 1
                categories.append('workload_management')
                actions.append('workload_balancing')

            # Interpersonal stress
            elif any(keyword in trigger_lower for keyword in self.STRESS_TRIGGER_PATTERNS['interpersonal']):
                additional_urgency += 1
                categories.append('interpersonal_skills')
                actions.append('conflict_resolution')

            # Safety-related stress
            elif any(keyword in trigger_lower for keyword in self.STRESS_TRIGGER_PATTERNS['safety']):
                additional_urgency += 2
                categories.append('workplace_safety')
                actions.append('safety_protocols')

        return {
            'additional_urgency': min(3, additional_urgency),  # Cap additional urgency
            'categories': categories,
            'actions': actions
        }

    def _analyze_content_for_crisis(self, content):
        """Analyze journal content for crisis indicators"""
        if not content:
            return {'crisis_detected': False, 'indicators': []}

        content_lower = content.lower()
        found_keywords = []

        for keyword in self.CRISIS_KEYWORDS:
            if keyword in content_lower:
                found_keywords.append(keyword)

        # Advanced pattern matching for crisis indicators
        crisis_patterns = [
            r"can'?t\s+take\s+it",
            r"want\s+to\s+die",
            r"end\s+it\s+all",
            r"nobody\s+cares",
            r"complete\s+failure",
            r"everything\s+is\s+ruined"
        ]

        for pattern in crisis_patterns:
            if re.search(pattern, content_lower):
                found_keywords.append(f"pattern: {pattern}")

        crisis_detected = len(found_keywords) > 0

        return {
            'crisis_detected': crisis_detected,
            'indicators': [f"Crisis keywords detected: {', '.join(found_keywords)}"] if crisis_detected else []
        }

    def _analyze_performance_indicators(self, journal_entry):
        """Analyze work performance indicators for wellness correlation"""
        concerning_patterns = []
        urgency_boost = 0
        categories = []

        # Low completion rate
        if journal_entry.completion_rate is not None and journal_entry.completion_rate < 0.5:
            concerning_patterns.append('low_completion_rate')
            urgency_boost += 1
            categories.append('productivity_support')

        # Low efficiency score
        if journal_entry.efficiency_score is not None and journal_entry.efficiency_score < 5.0:
            concerning_patterns.append('low_efficiency')
            urgency_boost += 1
            categories.append('efficiency_optimization')

        # Low quality score
        if journal_entry.quality_score is not None and journal_entry.quality_score < 5.0:
            concerning_patterns.append('quality_concerns')
            urgency_boost += 1
            categories.append('quality_improvement')

        # Multiple performance issues
        if len(concerning_patterns) >= 2:
            urgency_boost += 1
            categories.append('comprehensive_performance_support')

        return {
            'concerning_patterns': concerning_patterns,
            'urgency_boost': urgency_boost,
            'categories': categories
        }

    def _categorize_urgency(self, urgency_score):
        """Categorize urgency level based on score"""
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
        """Calculate when wellness content should be delivered"""
        if urgency_score >= 7:
            return 'immediate'  # Within minutes
        elif urgency_score >= 5:
            return 'same_hour'  # Within 1 hour
        elif urgency_score >= 3:
            return 'same_day'   # Within 8 hours
        elif urgency_score >= 1:
            return 'next_session'  # Next day/session
        else:
            return 'routine'    # Regular scheduling

    def _calculate_confidence(self, journal_entry, urgency_score):
        """Calculate confidence level of the analysis"""
        confidence = 0.5  # Base confidence

        # More data = higher confidence
        data_points = 0
        if journal_entry.mood_rating is not None:
            data_points += 1
        if journal_entry.stress_level is not None:
            data_points += 1
        if journal_entry.energy_level is not None:
            data_points += 1
        if journal_entry.content and len(journal_entry.content) > 50:
            data_points += 1

        confidence += (data_points / 4) * 0.3

        # Higher urgency with multiple indicators = higher confidence
        if urgency_score >= 5:
            confidence += 0.2

        return min(1.0, confidence)

    def detect_long_term_patterns(self, user_journal_history):
        """
        COMPLEX PATTERN DETECTION: Long-term trend analysis for proactive wellness
        MOVED FROM: Multiple Kotlin analytics methods

        Pattern Detection Algorithms:
        1. Stress Cycle Analysis - Weekly/monthly stress patterns
        2. Mood Seasonality - Seasonal affective patterns
        3. Energy-Work Correlation - Energy levels vs work type
        4. Trigger Pattern Recognition - Recurring stress triggers
        5. Coping Effectiveness - Which strategies work best for user
        6. Positive Psychology Engagement - Gratitude/affirmation patterns
        """

        if len(user_journal_history) < 14:
            return {
                'insufficient_data': True,
                'message': 'Need at least 14 days of journal data for pattern analysis',
                'data_points': len(user_journal_history)
            }

        logger.info(f"Analyzing long-term patterns for {len(user_journal_history)} journal entries")

        # 1. Stress Cycle Analysis
        stress_entries = [e for e in user_journal_history if e.stress_level is not None]
        stress_cycles = self._detect_stress_cycles(stress_entries)

        # 2. Mood Seasonality Detection
        mood_entries = [e for e in user_journal_history if e.mood_rating is not None]
        mood_seasonality = self._analyze_mood_seasonality(mood_entries)

        # 3. Energy-Work Correlation
        energy_work_correlation = self._correlate_energy_with_work_context(user_journal_history)

        # 4. Trigger Pattern Recognition
        trigger_patterns = self._analyze_recurring_triggers(stress_entries)

        # 5. Coping Strategy Effectiveness
        coping_effectiveness = self._measure_coping_strategy_effectiveness(stress_entries)

        # 6. Positive Psychology Engagement Analysis
        positive_entries = [e for e in user_journal_history if e.entry_type in [
            'GRATITUDE', 'THREE_GOOD_THINGS', 'DAILY_AFFIRMATIONS', 'STRENGTH_SPOTTING'
        ]]
        positive_engagement = self._analyze_positive_psychology_patterns(positive_entries)

        # Generate risk predictions and recommendations
        risk_predictions = self._predict_wellbeing_risks(user_journal_history)
        optimal_timing = self._calculate_optimal_intervention_timing(user_journal_history)
        learning_path = self._generate_learning_path(user_journal_history)

        return {
            'detected_patterns': {
                'stress_cycles': stress_cycles,
                'mood_seasonality': mood_seasonality,
                'energy_work_correlation': energy_work_correlation,
                'trigger_patterns': trigger_patterns,
                'coping_effectiveness': coping_effectiveness,
                'positive_engagement': positive_engagement
            },
            'risk_predictions': risk_predictions,
            'optimal_intervention_timing': optimal_timing,
            'personalized_learning_path': learning_path,
            'confidence_metrics': {
                'pattern_confidence': self._calculate_pattern_confidence(user_journal_history),
                'prediction_confidence': self._calculate_prediction_confidence(user_journal_history),
                'data_sufficiency': len(user_journal_history) >= 30  # Minimum for reliable patterns
            },
            'analysis_metadata': {
                'total_entries': len(user_journal_history),
                'date_range_days': (user_journal_history[-1].timestamp.date() -
                                  user_journal_history[0].timestamp.date()).days,
                'wellbeing_entries': len([e for e in user_journal_history if e.has_wellbeing_metrics]),
                'analysis_timestamp': timezone.now().isoformat()
            }
        }

    def _detect_stress_cycles(self, stress_entries):
        """
        EXACT ALGORITHM: Weekly and monthly stress pattern detection
        MOVED FROM: Kotlin WellbeingInsightsViewModel.calculateStressTrends()
        """

        if len(stress_entries) < 14:  # Need minimum 2 weeks of data
            return {'insufficient_data': True, 'required_days': 14}

        # Group by day of week
        day_patterns = defaultdict(list)
        for entry in stress_entries:
            day_name = entry.timestamp.strftime('%A')
            day_patterns[day_name].append(entry.stress_level)

        # Calculate average stress by day of week
        day_averages = {
            day: sum(stress_levels) / len(stress_levels)
            for day, stress_levels in day_patterns.items()
        }

        # Identify high-stress days
        overall_avg = sum(day_averages.values()) / len(day_averages)
        high_stress_days = [
            day for day, avg in day_averages.items()
            if avg > overall_avg + 0.5
        ]

        # Monthly pattern analysis
        monthly_patterns = self._analyze_monthly_stress_patterns(stress_entries)

        # Detect weekly cycles
        weekly_variance = np.var(list(day_averages.values())) if len(day_averages) > 1 else 0

        return {
            'weekly_patterns': day_averages,
            'high_stress_days': high_stress_days,
            'monthly_patterns': monthly_patterns,
            'cycle_strength': 'strong' if weekly_variance > 0.5 else 'weak',
            'cycle_confidence': self._calculate_cycle_confidence(day_patterns),
            'predicted_next_high_stress': self._predict_next_stress_spike(day_averages, high_stress_days)
        }

    def _analyze_monthly_stress_patterns(self, stress_entries):
        """Analyze stress patterns by month"""
        monthly_data = defaultdict(list)

        for entry in stress_entries:
            month_key = entry.timestamp.strftime('%B')
            monthly_data[month_key].append(entry.stress_level)

        monthly_averages = {
            month: sum(levels) / len(levels)
            for month, levels in monthly_data.items()
        }

        return {
            'monthly_averages': monthly_averages,
            'highest_stress_month': max(monthly_averages.items(), key=lambda x: x[1]) if monthly_averages else None,
            'lowest_stress_month': min(monthly_averages.items(), key=lambda x: x[1]) if monthly_averages else None
        }

    def _analyze_mood_seasonality(self, mood_entries):
        """Analyze mood patterns for seasonal affective tendencies"""
        if len(mood_entries) < 30:
            return {'insufficient_data': True, 'required_days': 30}

        seasonal_data = defaultdict(list)

        for entry in mood_entries:
            # Group by season
            month = entry.timestamp.month
            if month in [12, 1, 2]:
                season = 'Winter'
            elif month in [3, 4, 5]:
                season = 'Spring'
            elif month in [6, 7, 8]:
                season = 'Summer'
            else:
                season = 'Fall'

            seasonal_data[season].append(entry.mood_rating)

        seasonal_averages = {
            season: sum(moods) / len(moods)
            for season, moods in seasonal_data.items() if moods
        }

        # Detect seasonal pattern strength
        if len(seasonal_averages) >= 2:
            mood_variance = np.var(list(seasonal_averages.values()))
            pattern_strength = 'strong' if mood_variance > 2.0 else 'moderate' if mood_variance > 1.0 else 'weak'
        else:
            pattern_strength = 'insufficient_data'

        return {
            'seasonal_averages': seasonal_averages,
            'pattern_strength': pattern_strength,
            'potential_sad': seasonal_averages.get('Winter', 10) < seasonal_averages.get('Summer', 0) - 1.5,
            'best_season': max(seasonal_averages.items(), key=lambda x: x[1]) if seasonal_averages else None,
            'challenging_season': min(seasonal_averages.items(), key=lambda x: x[1]) if seasonal_averages else None
        }

    def _correlate_energy_with_work_context(self, journal_entries):
        """Analyze correlation between energy levels and work context"""
        energy_by_context = defaultdict(list)

        for entry in journal_entries:
            if entry.energy_level is not None:
                # Use entry type as work context
                context = entry.entry_type
                energy_by_context[context].append(entry.energy_level)

        context_averages = {
            context: sum(energy_levels) / len(energy_levels)
            for context, energy_levels in energy_by_context.items()
            if len(energy_levels) >= 3  # Need at least 3 data points
        }

        # Identify energy-draining and energy-boosting activities
        if context_averages:
            overall_avg = sum(context_averages.values()) / len(context_averages)
            energy_draining = [ctx for ctx, avg in context_averages.items() if avg < overall_avg - 1.0]
            energy_boosting = [ctx for ctx, avg in context_averages.items() if avg > overall_avg + 1.0]
        else:
            energy_draining = []
            energy_boosting = []

        return {
            'context_averages': context_averages,
            'energy_draining_activities': energy_draining,
            'energy_boosting_activities': energy_boosting,
            'correlation_strength': 'moderate',  # Simplified calculation
            'recommendations': self._generate_energy_recommendations(energy_draining, energy_boosting)
        }

    def _analyze_recurring_triggers(self, stress_entries):
        """Analyze recurring stress triggers and their patterns"""
        all_triggers = []
        trigger_contexts = defaultdict(list)

        for entry in stress_entries:
            if entry.stress_triggers:
                for trigger in entry.stress_triggers:
                    all_triggers.append(trigger.lower())
                    trigger_contexts[trigger.lower()].append({
                        'date': entry.timestamp.date(),
                        'stress_level': entry.stress_level,
                        'entry_type': entry.entry_type
                    })

        # Count trigger frequency
        trigger_frequency = Counter(all_triggers)

        # Analyze trigger patterns
        recurring_triggers = {}
        for trigger, contexts in trigger_contexts.items():
            if len(contexts) >= 3:  # At least 3 occurrences
                avg_stress = sum(ctx['stress_level'] for ctx in contexts) / len(contexts)
                recurring_triggers[trigger] = {
                    'frequency': len(contexts),
                    'avg_stress_impact': avg_stress,
                    'contexts': [ctx['entry_type'] for ctx in contexts],
                    'severity': 'high' if avg_stress >= 4 else 'medium' if avg_stress >= 3 else 'low'
                }

        return {
            'top_triggers': trigger_frequency.most_common(5),
            'recurring_patterns': recurring_triggers,
            'trigger_categories': self._categorize_triggers(trigger_frequency),
            'intervention_priorities': self._prioritize_trigger_interventions(recurring_triggers)
        }

    def _measure_coping_strategy_effectiveness(self, stress_entries):
        """Measure effectiveness of different coping strategies"""
        strategy_outcomes = defaultdict(list)

        # Track coping strategies and subsequent stress levels
        sorted_entries = sorted(stress_entries, key=lambda x: x.timestamp)

        for i, entry in enumerate(sorted_entries):
            if entry.coping_strategies:
                # Look for stress reduction in subsequent entries
                for j in range(i + 1, min(i + 4, len(sorted_entries))):  # Check next 3 entries
                    next_entry = sorted_entries[j]
                    time_diff = (next_entry.timestamp - entry.timestamp).days

                    if time_diff <= 7 and next_entry.stress_level is not None:  # Within a week
                        stress_reduction = entry.stress_level - next_entry.stress_level

                        for strategy in entry.coping_strategies:
                            strategy_outcomes[strategy.lower()].append({
                                'stress_reduction': stress_reduction,
                                'time_to_effect': time_diff,
                                'initial_stress': entry.stress_level
                            })
                        break

        # Calculate effectiveness scores
        strategy_effectiveness = {}
        for strategy, outcomes in strategy_outcomes.items():
            if len(outcomes) >= 2:  # Need at least 2 data points
                avg_reduction = sum(o['stress_reduction'] for o in outcomes) / len(outcomes)
                success_rate = len([o for o in outcomes if o['stress_reduction'] > 0]) / len(outcomes)

                strategy_effectiveness[strategy] = {
                    'avg_stress_reduction': avg_reduction,
                    'success_rate': success_rate,
                    'usage_count': len(outcomes),
                    'effectiveness_score': (avg_reduction + success_rate) / 2,
                    'recommendation': self._get_strategy_recommendation(avg_reduction, success_rate)
                }

        # Rank strategies by effectiveness
        ranked_strategies = sorted(
            strategy_effectiveness.items(),
            key=lambda x: x[1]['effectiveness_score'],
            reverse=True
        )

        return {
            'strategy_effectiveness': strategy_effectiveness,
            'top_strategies': ranked_strategies[:3],
            'ineffective_strategies': [s for s, data in ranked_strategies if data['effectiveness_score'] < 0],
            'recommendations': self._generate_coping_recommendations(ranked_strategies)
        }

    def _analyze_positive_psychology_patterns(self, positive_entries):
        """Analyze positive psychology engagement patterns"""
        if not positive_entries:
            return {
                'engagement_level': 'none',
                'recommendations': ['Start with daily gratitude practice', 'Try the "3 Good Things" exercise']
            }

        # Analyze gratitude patterns
        gratitude_entries = [e for e in positive_entries if e.entry_type == 'GRATITUDE']
        gratitude_frequency = len(gratitude_entries) / len(positive_entries) if positive_entries else 0

        # Analyze affirmation patterns
        affirmation_entries = [e for e in positive_entries if e.entry_type == 'DAILY_AFFIRMATIONS']

        # Calculate engagement metrics
        total_positive_items = 0
        for entry in positive_entries:
            if entry.gratitude_items:
                total_positive_items += len(entry.gratitude_items)
            if entry.affirmations:
                total_positive_items += len(entry.affirmations)
            if entry.achievements:
                total_positive_items += len(entry.achievements)

        avg_positive_items = total_positive_items / len(positive_entries) if positive_entries else 0

        # Determine engagement level
        if avg_positive_items >= 3 and gratitude_frequency >= 0.5:
            engagement_level = 'high'
        elif avg_positive_items >= 1.5 and gratitude_frequency >= 0.3:
            engagement_level = 'moderate'
        else:
            engagement_level = 'low'

        return {
            'engagement_level': engagement_level,
            'gratitude_frequency': gratitude_frequency,
            'avg_positive_items_per_entry': avg_positive_items,
            'most_common_practices': self._identify_common_positive_practices(positive_entries),
            'consistency_score': self._calculate_positive_consistency(positive_entries),
            'recommendations': self._generate_positive_psychology_recommendations(engagement_level, positive_entries)
        }

    def _predict_wellbeing_risks(self, journal_history):
        """Predict potential wellbeing risks based on patterns"""
        risks = []

        # Recent trend analysis
        recent_entries = [e for e in journal_history if
                         e.timestamp >= timezone.now() - timedelta(days=14)]

        if recent_entries:
            # Mood decline risk
            mood_entries = [e for e in recent_entries if e.mood_rating is not None]
            if len(mood_entries) >= 3:
                recent_avg = sum(e.mood_rating for e in mood_entries[-3:]) / 3
                earlier_avg = sum(e.mood_rating for e in mood_entries[:-3]) / max(1, len(mood_entries[:-3]))

                if recent_avg < earlier_avg - 1.0:
                    risks.append({
                        'type': 'mood_decline',
                        'severity': 'medium' if recent_avg >= 5 else 'high',
                        'description': 'Mood trending downward over past 2 weeks',
                        'intervention': 'mood_support_content'
                    })

            # Stress escalation risk
            stress_entries = [e for e in recent_entries if e.stress_level is not None]
            if len(stress_entries) >= 3:
                high_stress_count = len([e for e in stress_entries if e.stress_level >= 4])
                if high_stress_count / len(stress_entries) > 0.5:
                    risks.append({
                        'type': 'chronic_stress',
                        'severity': 'high',
                        'description': 'Sustained high stress levels detected',
                        'intervention': 'stress_management_intensive'
                    })

        return {
            'identified_risks': risks,
            'overall_risk_level': 'high' if any(r['severity'] == 'high' for r in risks) else
                                 'medium' if risks else 'low',
            'monitoring_recommendations': self._generate_monitoring_recommendations(risks)
        }

    def _calculate_optimal_intervention_timing(self, journal_history):
        """Calculate optimal timing for wellness interventions"""
        # Analyze when user is most receptive to wellness content
        # This is a simplified version - real implementation would be more sophisticated

        hour_patterns = defaultdict(list)
        for entry in journal_history:
            hour = entry.timestamp.hour
            engagement_score = 1  # Base score

            # Higher score for positive entries
            if entry.entry_type in ['GRATITUDE', 'THREE_GOOD_THINGS', 'DAILY_AFFIRMATIONS']:
                engagement_score += 2

            hour_patterns[hour].append(engagement_score)

        # Calculate average engagement by hour
        optimal_hours = {}
        for hour, scores in hour_patterns.items():
            if len(scores) >= 3:  # Need sufficient data
                avg_score = sum(scores) / len(scores)
                optimal_hours[hour] = avg_score

        # Find best times
        if optimal_hours:
            best_hours = sorted(optimal_hours.items(), key=lambda x: x[1], reverse=True)[:3]
            return {
                'optimal_hours': [hour for hour, score in best_hours],
                'peak_engagement_hour': best_hours[0][0],
                'engagement_pattern': optimal_hours
            }

        return {
            'optimal_hours': [9, 12, 18],  # Default times
            'peak_engagement_hour': 12,
            'engagement_pattern': {}
        }

    def _generate_learning_path(self, journal_history):
        """Generate personalized learning path based on patterns"""
        path_recommendations = []

        # Analyze user's primary challenges
        stress_entries = [e for e in journal_history if e.stress_level and e.stress_level >= 4]
        mood_entries = [e for e in journal_history if e.mood_rating and e.mood_rating <= 4]

        # Prioritize based on frequency and severity
        if len(stress_entries) > len(journal_history) * 0.3:
            path_recommendations.append({
                'priority': 1,
                'category': 'stress_management',
                'modules': ['breathing_techniques', 'stress_identification', 'coping_strategies'],
                'estimated_duration': '2-3 weeks'
            })

        if len(mood_entries) > len(journal_history) * 0.3:
            path_recommendations.append({
                'priority': 2,
                'category': 'mood_enhancement',
                'modules': ['gratitude_practice', 'cognitive_reframing', 'positive_psychology'],
                'estimated_duration': '3-4 weeks'
            })

        # Add foundational content
        path_recommendations.append({
            'priority': 3,
            'category': 'workplace_wellness',
            'modules': ['mindful_breaks', 'work_life_balance', 'communication_skills'],
            'estimated_duration': '2-3 weeks'
        })

        return {
            'recommended_path': path_recommendations,
            'total_estimated_duration': '6-8 weeks',
            'personalization_factors': self._identify_personalization_factors(journal_history)
        }

    # Helper methods for various calculations
    def _calculate_cycle_confidence(self, day_patterns):
        """Calculate confidence in detected cycles"""
        if len(day_patterns) < 5:  # Need most days of week
            return 0.3

        # Check for consistent patterns
        consistency_scores = []
        for day_data in day_patterns.values():
            if len(day_data) > 1:
                variance = np.var(day_data)
                consistency_scores.append(1 / (1 + variance))  # Lower variance = higher consistency

        return sum(consistency_scores) / len(consistency_scores) if consistency_scores else 0.5

    def _predict_next_stress_spike(self, day_averages, high_stress_days):
        """Predict when next stress spike might occur"""
        if not high_stress_days:
            return None

        # Simple prediction based on historical patterns
        today = timezone.now().strftime('%A')
        days_of_week = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']

        try:
            today_index = days_of_week.index(today)
        except ValueError:
            return None

        # Find next high stress day
        for i in range(1, 8):
            next_day_index = (today_index + i) % 7
            next_day = days_of_week[next_day_index]
            if next_day in high_stress_days:
                return {
                    'day': next_day,
                    'days_ahead': i,
                    'predicted_stress_level': day_averages.get(next_day, 3.0),
                    'confidence': 0.7
                }

        return None

    def _categorize_triggers(self, trigger_frequency):
        """Categorize triggers into types"""
        categories = defaultdict(list)

        for trigger, count in trigger_frequency.items():
            trigger_lower = trigger.lower()

            # Categorize based on keywords
            if any(kw in trigger_lower for kw in self.STRESS_TRIGGER_PATTERNS['equipment']):
                categories['technical'].append((trigger, count))
            elif any(kw in trigger_lower for kw in self.STRESS_TRIGGER_PATTERNS['deadline']):
                categories['time_pressure'].append((trigger, count))
            elif any(kw in trigger_lower for kw in self.STRESS_TRIGGER_PATTERNS['workload']):
                categories['workload'].append((trigger, count))
            elif any(kw in trigger_lower for kw in self.STRESS_TRIGGER_PATTERNS['interpersonal']):
                categories['interpersonal'].append((trigger, count))
            else:
                categories['other'].append((trigger, count))

        return dict(categories)

    def _prioritize_trigger_interventions(self, recurring_triggers):
        """Prioritize interventions based on trigger analysis"""
        priorities = []

        for trigger, data in recurring_triggers.items():
            priority_score = data['frequency'] * data['avg_stress_impact']
            priorities.append({
                'trigger': trigger,
                'priority_score': priority_score,
                'severity': data['severity'],
                'recommended_action': self._get_trigger_intervention(trigger, data)
            })

        return sorted(priorities, key=lambda x: x['priority_score'], reverse=True)

    def _get_strategy_recommendation(self, avg_reduction, success_rate):
        """Get recommendation for coping strategy"""
        if avg_reduction > 1.0 and success_rate > 0.7:
            return 'highly_effective'
        elif avg_reduction > 0.5 and success_rate > 0.5:
            return 'moderately_effective'
        elif avg_reduction > 0 and success_rate > 0.3:
            return 'somewhat_effective'
        else:
            return 'ineffective'

    def _generate_coping_recommendations(self, ranked_strategies):
        """Generate recommendations for coping strategies"""
        recommendations = []

        if ranked_strategies:
            top_strategy = ranked_strategies[0]
            recommendations.append(f"Continue using '{top_strategy[0]}' - it's working well for you")

            # Find strategies to improve or replace
            ineffective = [s for s, data in ranked_strategies if data[1]['effectiveness_score'] < 0.2]
            if ineffective:
                recommendations.append(f"Consider alternatives to '{ineffective[0][0]}' - it may not be helping")

        return recommendations

    def _identify_common_positive_practices(self, positive_entries):
        """Identify most common positive psychology practices"""
        practice_counts = Counter()

        for entry in positive_entries:
            practice_counts[entry.entry_type] += 1

        return practice_counts.most_common(3)

    def _calculate_positive_consistency(self, positive_entries):
        """Calculate consistency of positive psychology practice"""
        if len(positive_entries) < 7:
            return 0.3

        # Check for regular practice over time
        dates = [e.timestamp.date() for e in positive_entries]
        date_range = (max(dates) - min(dates)).days

        if date_range == 0:
            return 1.0

        # Calculate frequency
        frequency = len(positive_entries) / date_range
        return min(1.0, frequency)

    def _generate_positive_psychology_recommendations(self, engagement_level, positive_entries):
        """Generate recommendations for positive psychology practices"""
        recommendations = []

        if engagement_level == 'low':
            recommendations.extend([
                'Start with daily gratitude - write down 3 things you\'re grateful for',
                'Try the "3 Good Things" exercise before bed',
                'Set a daily reminder for positive reflection'
            ])
        elif engagement_level == 'moderate':
            recommendations.extend([
                'Consider adding strength-spotting exercises',
                'Try weekly "Best Self" reflections',
                'Explore daily affirmations practice'
            ])
        else:  # high
            recommendations.extend([
                'You\'re doing great with positive practices!',
                'Consider mentoring others in positive psychology',
                'Explore advanced techniques like gratitude letters'
            ])

        return recommendations

    def _generate_monitoring_recommendations(self, risks):
        """Generate recommendations for monitoring identified risks"""
        recommendations = []

        for risk in risks:
            if risk['type'] == 'mood_decline':
                recommendations.append('Monitor mood ratings daily for early intervention')
            elif risk['type'] == 'chronic_stress':
                recommendations.append('Track stress triggers and coping strategy effectiveness')

        if not recommendations:
            recommendations.append('Continue regular wellness check-ins')

        return recommendations

    def _identify_personalization_factors(self, journal_history):
        """Identify factors for personalizing the learning path"""
        factors = []

        # Identify preferred entry types
        entry_types = [e.entry_type for e in journal_history]
        common_types = Counter(entry_types).most_common(3)
        factors.append(f"Prefers {common_types[0][0]} entries")

        # Identify time patterns
        hours = [e.timestamp.hour for e in journal_history]
        common_hours = Counter(hours).most_common(2)
        if common_hours:
            factors.append(f"Most active at {common_hours[0][0]}:00")

        return factors

    def _generate_energy_recommendations(self, draining_activities, boosting_activities):
        """Generate recommendations for energy management"""
        recommendations = []

        if draining_activities:
            recommendations.append(f"Consider strategies to manage energy during {draining_activities[0]} activities")

        if boosting_activities:
            recommendations.append(f"Try to incorporate more {boosting_activities[0]} activities")

        return recommendations

    def _get_trigger_intervention(self, trigger, data):
        """Get specific intervention for a trigger"""
        trigger_lower = trigger.lower()

        if any(kw in trigger_lower for kw in self.STRESS_TRIGGER_PATTERNS['equipment']):
            return 'technical_problem_solving_skills'
        elif any(kw in trigger_lower for kw in self.STRESS_TRIGGER_PATTERNS['deadline']):
            return 'time_management_techniques'
        elif any(kw in trigger_lower for kw in self.STRESS_TRIGGER_PATTERNS['workload']):
            return 'workload_balancing_strategies'
        else:
            return 'general_stress_management'

    def _calculate_pattern_confidence(self, journal_history):
        """Calculate overall confidence in pattern detection"""
        data_points = len(journal_history)

        if data_points >= 60:
            return 0.9
        elif data_points >= 30:
            return 0.75
        elif data_points >= 14:
            return 0.6
        else:
            return 0.4

    def _calculate_prediction_confidence(self, journal_history):
        """Calculate confidence in predictions"""
        # More data and consistent patterns = higher confidence
        return min(0.8, len(journal_history) / 100)


# Convenience function for triggering pattern analysis
def trigger_pattern_analysis(journal_entry):
    """Convenience function to trigger pattern analysis from signals"""
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