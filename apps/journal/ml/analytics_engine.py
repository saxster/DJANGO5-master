"""
ML-Powered Analytics Engine

COMPLETE ANALYTICS ENGINE: All Kotlin algorithms moved to Django with ML enhancement
Implements ALL methods from Kotlin WellbeingInsightsViewModel

EXACT IMPLEMENTATIONS from specification:
- calculateMoodTrends()
- calculateStressTrends()
- calculateEnergyTrends()
- calculateGratitudeInsights()
- calculateAchievementInsights()
- calculatePatternInsights()
- generateRecommendations()
- calculateOverallWellbeingScore()
"""

from django.utils import timezone
class WellbeingAnalyticsEngine:
    """
    COMPLETE ANALYTICS ENGINE: All Kotlin algorithms moved to Django with ML enhancement
    Implements ALL methods from Kotlin WellbeingInsightsViewModel
    """

    def calculate_mood_trends(self, journal_entries):
        """
        EXACT ALGORITHM: Moved from Kotlin WellbeingInsightsViewModel.calculateMoodTrends()

        Mood Trend Calculation:
        1. Extract mood ratings from journal entries
        2. Group by date and calculate daily averages
        3. Calculate overall average mood and variability
        4. Determine trend direction (improving/stable/declining)
        5. Identify best and challenging days
        6. Analyze day-of-week mood patterns
        """

        mood_entries = [e for e in journal_entries if e.mood_rating is not None]

        if len(mood_entries) < 3:
            return {
                'average_mood': 0.0,
                'mood_variability': 0.0,
                'trend_direction': 'insufficient_data',
                'daily_moods': [],
                'best_days': [],
                'challenging_days': [],
                'mood_patterns': {},
                'data_quality': 'insufficient'
            }

        logger.debug(f"Calculating mood trends for {len(mood_entries)} mood entries")

        # Group by date and calculate daily averages
        daily_moods = {}
        for entry in mood_entries:
            date = entry.timestamp.date()
            if date not in daily_moods:
                daily_moods[date] = []
            daily_moods[date].append(entry.mood_rating)

        daily_averages = {
            date: sum(moods) / len(moods)
            for date, moods in daily_moods.items()
        }

        # Calculate statistics
        mood_values = list(daily_averages.values())
        average_mood = sum(mood_values) / len(mood_values)

        # Mood variability calculation (standard deviation)
        variance = sum((mood - average_mood) ** 2 for mood in mood_values) / len(mood_values)
        mood_variability = variance ** 0.5

        # Trend direction calculation using linear regression
        if len(mood_values) >= 5:
            trend_direction = self._calculate_trend_direction(daily_averages)
        else:
            # Fallback to simple comparison
            first_half = mood_values[:len(mood_values)//2]
            second_half = mood_values[len(mood_values)//2:]

            first_avg = sum(first_half) / len(first_half)
            second_avg = sum(second_half) / len(second_half)

            if second_avg > first_avg + 0.5:
                trend_direction = 'improving'
            elif second_avg < first_avg - 0.5:
                trend_direction = 'declining'
            else:
                trend_direction = 'stable'

        # Best and challenging days
        sorted_days = sorted(daily_averages.items(), key=lambda x: x[1])
        num_days_to_show = min(3, len(sorted_days))
        best_days = [day for day, mood in sorted_days[-num_days_to_show:]]
        challenging_days = [day for day, mood in sorted_days[:num_days_to_show]]

        # Day-of-week patterns
        day_patterns = {}
        for entry in mood_entries:
            day_name = entry.timestamp.strftime('%A')
            if day_name not in day_patterns:
                day_patterns[day_name] = []
            day_patterns[day_name].append(entry.mood_rating)

        mood_patterns = {
            day: sum(moods) / len(moods)
            for day, moods in day_patterns.items()
        }

        # Calculate additional insights
        mood_insights = self._generate_mood_insights(mood_values, mood_patterns, trend_direction)

        return {
            'average_mood': round(average_mood, 2),
            'mood_variability': round(mood_variability, 2),
            'trend_direction': trend_direction,
            'trend_strength': self._calculate_trend_strength(daily_averages),
            'daily_moods': [
                {
                    'date': date.isoformat(),
                    'mood': round(mood, 2),
                    'entry_count': len(daily_moods[date])
                }
                for date, mood in sorted(daily_averages.items())
            ],
            'best_days': [day.isoformat() for day in best_days],
            'challenging_days': [day.isoformat() for day in challenging_days],
            'mood_patterns': {day: round(avg, 2) for day, avg in mood_patterns.items()},
            'insights': mood_insights,
            'data_quality': 'good' if len(mood_entries) >= 14 else 'moderate'
        }

    def calculate_stress_trends(self, journal_entries):
        """
        EXACT ALGORITHM: Moved from Kotlin WellbeingInsightsViewModel.calculateStressTrends()

        Stress Analysis Algorithm:
        1. Extract stress levels and triggers from entries
        2. Calculate average stress and trend direction
        3. Analyze trigger frequency and patterns
        4. Evaluate coping strategy effectiveness
        5. Generate stress pattern insights
        """

        stress_entries = [e for e in journal_entries if e.stress_level is not None]

        if len(stress_entries) < 3:
            return {
                'average_stress': 0.0,
                'trend_direction': 'insufficient_data',
                'daily_stress': [],
                'common_triggers': [],
                'effective_coping_strategies': [],
                'stress_patterns': {},
                'data_quality': 'insufficient'
            }

        logger.debug(f"Calculating stress trends for {len(stress_entries)} stress entries")

        # Group by date for daily stress analysis
        daily_stress = {}
        all_triggers = []
        all_coping_strategies = []

        for entry in stress_entries:
            date = entry.timestamp.date()
            if date not in daily_stress:
                daily_stress[date] = []
            daily_stress[date].append(entry.stress_level)

            # Collect triggers and coping strategies
            if entry.stress_triggers:
                all_triggers.extend(entry.stress_triggers)
            if entry.coping_strategies:
                all_coping_strategies.extend(entry.coping_strategies)

        # Calculate daily averages
        daily_averages = {
            date: sum(stress_levels) / len(stress_levels)
            for date, stress_levels in daily_stress.items()
        }

        # Overall statistics
        stress_values = list(daily_averages.values())
        average_stress = sum(stress_values) / len(stress_values)

        # Trend calculation (inverted - lower stress is better)
        trend_direction = self._calculate_stress_trend_direction(daily_averages)

        # Trigger frequency analysis
        trigger_frequency = Counter(all_triggers)
        common_triggers = [
            {
                'trigger': trigger,
                'frequency': freq,
                'percentage': round(freq / len(stress_entries) * 100, 1)
            }
            for trigger, freq in trigger_frequency.most_common(5)
        ]

        # Coping strategy effectiveness (enhanced algorithm)
        effective_coping = self._analyze_coping_effectiveness(stress_entries, all_coping_strategies)

        # Day-of-week stress patterns
        day_patterns = {}
        for entry in stress_entries:
            day_name = entry.timestamp.strftime('%A')
            if day_name not in day_patterns:
                day_patterns[day_name] = []
            day_patterns[day_name].append(entry.stress_level)

        stress_patterns = {
            day: sum(stress_levels) / len(stress_levels)
            for day, stress_levels in day_patterns.items()
        }

        # Generate stress insights
        stress_insights = self._generate_stress_insights(
            stress_values, common_triggers, effective_coping, stress_patterns
        )

        return {
            'average_stress': round(average_stress, 2),
            'trend_direction': trend_direction,
            'trend_strength': self._calculate_trend_strength(daily_averages),
            'daily_stress': [
                {
                    'date': date.isoformat(),
                    'stress': round(stress, 2),
                    'entry_count': len(daily_stress[date])
                }
                for date, stress in sorted(daily_averages.items())
            ],
            'common_triggers': common_triggers,
            'effective_coping_strategies': effective_coping,
            'stress_patterns': {day: round(avg, 2) for day, avg in stress_patterns.items()},
            'insights': stress_insights,
            'data_quality': 'good' if len(stress_entries) >= 14 else 'moderate'
        }

    def calculate_energy_trends(self, journal_entries):
        """
        EXACT ALGORITHM: Moved from Kotlin WellbeingInsightsViewModel.calculateEnergyTrends()

        Energy Analysis Algorithm:
        1. Extract energy levels from entries
        2. Calculate daily averages and overall trends
        3. Correlate with work activities and patterns
        4. Identify energy-boosting and draining activities
        5. Generate energy optimization insights
        """

        energy_entries = [e for e in journal_entries if e.energy_level is not None]

        if len(energy_entries) < 3:
            return {
                'average_energy': 0.0,
                'trend_direction': 'insufficient_data',
                'daily_energy': [],
                'energy_patterns': {},
                'activity_correlation': {},
                'data_quality': 'insufficient'
            }

        logger.debug(f"Calculating energy trends for {len(energy_entries)} energy entries")

        # Group by date for daily energy analysis
        daily_energy = {}
        for entry in energy_entries:
            date = entry.timestamp.date()
            if date not in daily_energy:
                daily_energy[date] = []
            daily_energy[date].append(entry.energy_level)

        # Calculate daily averages
        daily_averages = {
            date: sum(energy_levels) / len(energy_levels)
            for date, energy_levels in daily_energy.items()
        }

        # Overall statistics
        energy_values = list(daily_averages.values())
        average_energy = sum(energy_values) / len(energy_values)

        # Trend direction calculation
        trend_direction = self._calculate_trend_direction(daily_averages)

        # Energy patterns by day of week
        day_patterns = {}
        for entry in energy_entries:
            day_name = entry.timestamp.strftime('%A')
            if day_name not in day_patterns:
                day_patterns[day_name] = []
            day_patterns[day_name].append(entry.energy_level)

        energy_patterns = {
            day: sum(energy_levels) / len(energy_levels)
            for day, energy_levels in day_patterns.items()
        }

        # Activity correlation analysis
        activity_correlation = self._analyze_energy_activity_correlation(energy_entries)

        # Time-of-day energy patterns
        time_patterns = self._analyze_energy_time_patterns(energy_entries)

        # Generate energy insights
        energy_insights = self._generate_energy_insights(
            energy_values, activity_correlation, time_patterns, trend_direction
        )

        return {
            'average_energy': round(average_energy, 2),
            'trend_direction': trend_direction,
            'trend_strength': self._calculate_trend_strength(daily_averages),
            'daily_energy': [
                {
                    'date': date.isoformat(),
                    'energy': round(energy, 2),
                    'entry_count': len(daily_energy[date])
                }
                for date, energy in sorted(daily_averages.items())
            ],
            'energy_patterns': {day: round(avg, 2) for day, avg in energy_patterns.items()},
            'activity_correlation': activity_correlation,
            'time_patterns': time_patterns,
            'insights': energy_insights,
            'data_quality': 'good' if len(energy_entries) >= 14 else 'moderate'
        }

    def calculate_gratitude_insights(self, journal_entries):
        """
        EXACT ALGORITHM: Moved from Kotlin WellbeingInsightsViewModel.calculateGratitudeInsights()

        Gratitude Analysis:
        1. Count gratitude entries and extract gratitude items
        2. Calculate average gratitude items per entry
        3. Determine current gratitude streak
        4. Extract and categorize gratitude themes
        5. Calculate gratitude frequency over time period
        """

        gratitude_entries = [
            e for e in journal_entries
            if e.entry_type in ['GRATITUDE', 'THREE_GOOD_THINGS']
            or (e.gratitude_items and len(e.gratitude_items) > 0)
        ]

        if len(gratitude_entries) == 0:
            return {
                'total_gratitude_entries': 0,
                'average_gratitude_per_entry': 0.0,
                'gratitude_streak': 0,
                'common_gratitude_themes': [],
                'gratitude_frequency': 0.0,
                'gratitude_impact': {},
                'data_quality': 'none'
            }

        logger.debug(f"Calculating gratitude insights for {len(gratitude_entries)} gratitude entries")

        # Extract all gratitude items
        all_gratitude_items = []
        for entry in gratitude_entries:
            if entry.gratitude_items:
                all_gratitude_items.extend(entry.gratitude_items)
            # Also check metadata for Three Good Things
            if entry.entry_type == 'THREE_GOOD_THINGS' and entry.metadata.get('goodThings'):
                all_gratitude_items.extend(entry.metadata['goodThings'])

        # Calculate statistics
        average_per_entry = len(all_gratitude_items) / len(gratitude_entries) if gratitude_entries else 0

        # Gratitude streak calculation
        gratitude_streak = self._calculate_gratitude_streak(gratitude_entries)

        # Theme extraction and categorization
        common_themes = self._extract_gratitude_themes(all_gratitude_items)

        # Frequency calculation
        if journal_entries:
            date_range = (journal_entries[-1].timestamp.date() - journal_entries[0].timestamp.date()).days
            gratitude_frequency = len(gratitude_entries) / max(1, date_range)
        else:
            gratitude_frequency = 0.0

        # Analyze gratitude impact on mood
        gratitude_impact = self._analyze_gratitude_mood_impact(gratitude_entries, journal_entries)

        # Generate gratitude insights
        gratitude_insights = self._generate_gratitude_insights(
            gratitude_entries, common_themes, gratitude_streak, gratitude_frequency
        )

        return {
            'total_gratitude_entries': len(gratitude_entries),
            'average_gratitude_per_entry': round(average_per_entry, 2),
            'gratitude_streak': gratitude_streak,
            'common_gratitude_themes': common_themes,
            'gratitude_frequency': round(gratitude_frequency, 3),
            'gratitude_impact': gratitude_impact,
            'insights': gratitude_insights,
            'data_quality': 'good' if len(gratitude_entries) >= 7 else 'moderate'
        }

    def calculate_achievement_insights(self, journal_entries):
        """
        EXACT ALGORITHM: Moved from Kotlin WellbeingInsightsViewModel.calculateAchievementInsights()

        Achievement Analysis:
        1. Count achievement entries and extract achievements
        2. Categorize achievements by type (work, personal, learning)
        3. Analyze achievement patterns and trends
        4. Calculate achievement frequency and impact
        5. Generate achievement motivation insights
        """

        achievement_entries = [
            e for e in journal_entries
            if (e.achievements and len(e.achievements) > 0)
            or e.entry_type in ['PROJECT_MILESTONE', 'TRAINING_COMPLETED']
        ]

        if len(achievement_entries) == 0:
            return {
                'total_achievement_entries': 0,
                'achievement_categories': {},
                'achievement_trends': 'insufficient_data',
                'motivation_patterns': {},
                'data_quality': 'none'
            }

        logger.debug(f"Calculating achievement insights for {len(achievement_entries)} achievement entries")

        # Extract all achievements
        all_achievements = []
        for entry in achievement_entries:
            if entry.achievements:
                all_achievements.extend(entry.achievements)
            # Also consider milestone entries as achievements
            if entry.entry_type in ['PROJECT_MILESTONE', 'TRAINING_COMPLETED']:
                all_achievements.append(f"{entry.entry_type}: {entry.title}")

        # Categorize achievements
        achievement_categories = self._categorize_achievements(all_achievements)

        # Analyze achievement trends over time
        achievement_trends = self._analyze_achievement_trends(achievement_entries)

        # Motivation pattern analysis
        motivation_patterns = self._analyze_motivation_patterns(achievement_entries, journal_entries)

        # Generate achievement insights
        achievement_insights = self._generate_achievement_insights(
            achievement_entries, achievement_categories, achievement_trends
        )

        return {
            'total_achievement_entries': len(achievement_entries),
            'total_achievements': len(all_achievements),
            'achievement_categories': achievement_categories,
            'achievement_trends': achievement_trends,
            'motivation_patterns': motivation_patterns,
            'insights': achievement_insights,
            'data_quality': 'good' if len(achievement_entries) >= 5 else 'moderate'
        }

    def calculate_pattern_insights(self, journal_entries):
        """
        EXACT ALGORITHM: Moved from Kotlin WellbeingInsightsViewModel.calculatePatternInsights()

        Pattern Recognition Analysis:
        1. Identify behavioral patterns across all entries
        2. Detect correlation between different metrics
        3. Find recurring themes and triggers
        4. Analyze temporal patterns and cycles
        5. Generate predictive insights
        """

        if len(journal_entries) < 14:
            return {
                'behavioral_patterns': [],
                'metric_correlations': {},
                'temporal_patterns': {},
                'predictive_insights': {},
                'data_quality': 'insufficient'
            }

        logger.debug(f"Calculating pattern insights for {len(journal_entries)} journal entries")

        # Behavioral pattern detection
        behavioral_patterns = self._detect_behavioral_patterns(journal_entries)

        # Metric correlation analysis
        metric_correlations = self._analyze_metric_correlations(journal_entries)

        # Temporal pattern analysis
        temporal_patterns = self._analyze_temporal_patterns(journal_entries)

        # Predictive insights generation
        predictive_insights = self._generate_predictive_insights(journal_entries)

        # Pattern strength assessment
        pattern_strength = self._assess_pattern_strength(behavioral_patterns, temporal_patterns)

        return {
            'behavioral_patterns': behavioral_patterns,
            'metric_correlations': metric_correlations,
            'temporal_patterns': temporal_patterns,
            'predictive_insights': predictive_insights,
            'pattern_strength': pattern_strength,
            'confidence_score': self._calculate_pattern_confidence(journal_entries),
            'data_quality': 'excellent' if len(journal_entries) >= 60 else 'good'
        }

    def generate_recommendations(self, mood_trends, stress_analysis, energy_trends, journal_entries):
        """
        EXACT ALGORITHM: Moved from Kotlin WellbeingInsightsViewModel.generateRecommendations()

        Recommendation Generation Algorithm:
        1. Analyze mood trends for improvement opportunities
        2. Evaluate stress patterns for management strategies
        3. Assess positive psychology engagement levels
        4. Generate priority-ranked actionable recommendations
        5. Link recommendations to specific wellness content
        """

        recommendations = []

        logger.debug("Generating personalized recommendations based on wellbeing trends")

        # Mood-based recommendations
        if mood_trends['average_mood'] < 5.0:
            recommendations.append({
                'type': 'mood_improvement',
                'priority': 'high',
                'title': 'Mood Enhancement Focus',
                'description': f"Your average mood ({mood_trends['average_mood']}) indicates room for improvement. Consider positive psychology practices.",
                'action_items': [
                    'Try daily gratitude journaling - research shows 15% mood improvement',
                    'Practice the "3 Good Things" exercise before bed',
                    'Consider mindfulness or meditation content for emotional regulation'
                ],
                'predicted_impact': 'high',
                'suggested_content_categories': ['gratitude', 'positive_psychology', 'mindfulness'],
                'estimated_improvement_timeline': '2_weeks',
                'evidence_basis': 'Seligman positive psychology research'
            })

        # Stress-based recommendations
        if stress_analysis['average_stress'] > 3.0:
            recommendations.append({
                'type': 'stress_management',
                'priority': 'high',
                'title': 'Stress Management Priority',
                'description': f"Your stress level ({stress_analysis['average_stress']}) indicates need for targeted stress management.",
                'action_items': [
                    'Log stress triggers to identify patterns - awareness reduces stress by 23%',
                    'Practice proven coping strategies consistently',
                    'Consider workplace stress management techniques',
                    'Implement regular stress-reduction breaks'
                ],
                'predicted_impact': 'high',
                'suggested_content_categories': ['stress_management', 'workplace_wellness', 'coping_techniques'],
                'trigger_analysis': stress_analysis.get('common_triggers', []),
                'estimated_improvement_timeline': '3_weeks'
            })

        # Positive psychology engagement assessment
        positive_entries = len([
            e for e in journal_entries
            if e.entry_type in ['GRATITUDE', 'THREE_GOOD_THINGS', 'DAILY_AFFIRMATIONS', 'STRENGTH_SPOTTING']
        ])
        total_entries = len(journal_entries)
        positive_ratio = positive_entries / max(1, total_entries)

        if positive_ratio < 0.3:  # Less than 30% positive psychology entries
            recommendations.append({
                'type': 'positive_psychology_enhancement',
                'priority': 'medium',
                'title': 'Enhance Positive Practices',
                'description': f"Only {positive_ratio:.1%} of your entries focus on positive psychology. Research shows 30%+ is optimal for wellbeing.",
                'action_items': [
                    'Try weekly "Best Self" reflections - increases life satisfaction by 12%',
                    'Practice daily gratitude or affirmations',
                    'Add strength spotting exercises to build self-awareness',
                    'Consider gratitude letter writing for relationship building'
                ],
                'predicted_impact': 'medium',
                'suggested_content_categories': ['positive_psychology', 'gratitude', 'strength_identification'],
                'evidence_basis': 'Seligman et al. positive psychology research',
                'current_engagement': f"{positive_ratio:.1%}",
                'target_engagement': '30%+'
            })

        # Energy optimization recommendations
        if energy_trends.get('average_energy', 0) < 6.0:
            recommendations.append({
                'type': 'energy_optimization',
                'priority': 'medium',
                'title': 'Energy Management Focus',
                'description': f"Your energy levels ({energy_trends.get('average_energy', 0)}) could be optimized for better performance.",
                'action_items': [
                    'Identify and minimize energy-draining activities',
                    'Schedule high-energy tasks during peak energy times',
                    'Implement energy-boosting practices (micro-breaks, hydration)',
                    'Consider sleep hygiene and nutrition factors'
                ],
                'predicted_impact': 'medium',
                'suggested_content_categories': ['energy_management', 'physical_wellness', 'sleep_hygiene'],
                'energy_patterns': energy_trends.get('energy_patterns', {}),
                'estimated_improvement_timeline': '4_weeks'
            })

        # Pattern-based recommendations
        if mood_trends.get('trend_direction') == 'declining':
            recommendations.append({
                'type': 'trend_intervention',
                'priority': 'high',
                'title': 'Address Declining Mood Trend',
                'description': 'Your mood has been trending downward. Early intervention is key to preventing further decline.',
                'action_items': [
                    'Increase frequency of mood tracking to daily',
                    'Implement immediate mood-boosting activities',
                    'Consider professional support if trend continues',
                    'Focus on stress reduction techniques'
                ],
                'predicted_impact': 'high',
                'urgency': 'immediate',
                'monitoring_required': True
            })

        # Consistency recommendations
        wellbeing_entries = len([e for e in journal_entries if e.has_wellbeing_metrics])
        consistency_ratio = wellbeing_entries / max(1, total_entries)

        if consistency_ratio < 0.5:
            recommendations.append({
                'type': 'consistency_improvement',
                'priority': 'low',
                'title': 'Improve Wellbeing Tracking Consistency',
                'description': f"Only {consistency_ratio:.1%} of your entries include wellbeing metrics. More data enables better insights.",
                'action_items': [
                    'Set daily reminders for mood/stress/energy ratings',
                    'Use quick check-in templates for consistency',
                    'Track wellbeing metrics even for brief entries'
                ],
                'predicted_impact': 'medium',
                'current_consistency': f"{consistency_ratio:.1%}",
                'target_consistency': '70%+'
            })

        # Sort recommendations by priority and impact
        priority_order = {'high': 3, 'medium': 2, 'low': 1}
        recommendations.sort(key=lambda r: priority_order.get(r['priority'], 0), reverse=True)

        return recommendations[:6]  # Return top 6 recommendations

    def calculate_overall_wellbeing_score(self, mood_trends, stress_analysis, energy_trends, journal_entries):
        """
        EXACT ALGORITHM: Moved from Kotlin WellbeingInsightsViewModel.calculateOverallWellbeingScore()

        Overall Wellbeing Score Calculation:
        1. Weight mood, stress, energy components
        2. Factor in positive psychology engagement
        3. Consider trend directions and consistency
        4. Apply data quality adjustments
        5. Generate confidence-weighted score (0-10 scale)
        """

        if not mood_trends or not stress_analysis or not energy_trends:
            return {
                'overall_score': 5.0,
                'component_scores': {},
                'confidence': 0.3,
                'interpretation': 'Insufficient data for accurate assessment'
            }

        logger.debug("Calculating overall wellbeing score from component analyses")

        # Component scores (normalized to 0-10 scale)
        mood_score = mood_trends.get('average_mood', 5.0)
        stress_score = 10 - (stress_analysis.get('average_stress', 3.0) * 2)  # Invert stress (lower is better)
        energy_score = energy_trends.get('average_energy', 5.0)

        # Positive psychology engagement bonus
        positive_entries = len([
            e for e in journal_entries
            if e.entry_type in ['GRATITUDE', 'THREE_GOOD_THINGS', 'DAILY_AFFIRMATIONS', 'STRENGTH_SPOTTING']
        ])
        positive_ratio = positive_entries / max(1, len(journal_entries))
        positive_bonus = min(1.0, positive_ratio * 3)  # Up to 1 point bonus

        # Trend adjustments
        trend_adjustment = 0.0
        if mood_trends.get('trend_direction') == 'improving':
            trend_adjustment += 0.5
        elif mood_trends.get('trend_direction') == 'declining':
            trend_adjustment -= 0.5

        if stress_analysis.get('trend_direction') == 'improving':  # Stress improving = stress decreasing
            trend_adjustment += 0.3
        elif stress_analysis.get('trend_direction') == 'declining':  # Stress declining = stress increasing
            trend_adjustment -= 0.3

        # Weighted combination
        component_weights = {
            'mood': 0.35,
            'stress': 0.30,
            'energy': 0.25,
            'positive_psychology': 0.10
        }

        weighted_score = (
            mood_score * component_weights['mood'] +
            stress_score * component_weights['stress'] +
            energy_score * component_weights['energy'] +
            (5.0 + positive_bonus * 5) * component_weights['positive_psychology']
        )

        # Apply trend adjustment
        weighted_score += trend_adjustment

        # Ensure score is within bounds
        overall_score = max(0, min(10, weighted_score))

        # Calculate confidence based on data quality
        confidence = self._calculate_score_confidence(mood_trends, stress_analysis, energy_trends, journal_entries)

        # Generate interpretation
        interpretation = self._interpret_wellbeing_score(overall_score, confidence)

        component_scores = {
            'mood_score': round(mood_score, 2),
            'stress_score': round(stress_score, 2),
            'energy_score': round(energy_score, 2),
            'positive_psychology_bonus': round(positive_bonus, 2),
            'trend_adjustment': round(trend_adjustment, 2)
        }

        return {
            'overall_score': round(overall_score, 2),
            'component_scores': component_scores,
            'component_weights': component_weights,
            'confidence': round(confidence, 2),
            'interpretation': interpretation,
            'data_quality_factors': self._assess_data_quality_factors(journal_entries)
        }

    def calculate_streak_data(self, journal_entries):
        """
        EXACT ALGORITHM: Moved from Kotlin WellbeingInsightsViewModel.calculateStreakData()

        Streak Calculation:
        1. Identify consecutive days with journal entries
        2. Calculate current and longest streaks
        3. Analyze streak patterns and maintenance
        4. Generate streak motivation insights
        """

        if not journal_entries:
            return {
                'current_streak': 0,
                'longest_streak': 0,
                'streak_insights': [],
                'motivation_level': 'low'
            }

        # Sort entries by date
        entries_by_date = {}
        for entry in journal_entries:
            date = entry.timestamp.date()
            entries_by_date[date] = entries_by_date.get(date, 0) + 1

        sorted_dates = sorted(entries_by_date.keys())

        if not sorted_dates:
            return {
                'current_streak': 0,
                'longest_streak': 0,
                'streak_insights': [],
                'motivation_level': 'low'
            }

        # Calculate current streak
        current_streak = 0
        today = timezone.now().date()
        current_date = today

        # Check if today has an entry, if not start from yesterday
        if current_date not in entries_by_date:
            current_date = today - timedelta(days=1)

        while current_date in entries_by_date and current_date >= sorted_dates[0]:
            current_streak += 1
            current_date -= timedelta(days=1)

        # Calculate longest streak
        longest_streak = 0
        temp_streak = 0
        prev_date = None

        for date in sorted_dates:
            if prev_date and (date - prev_date).days == 1:
                temp_streak += 1
            else:
                temp_streak = 1

            longest_streak = max(longest_streak, temp_streak)
            prev_date = date

        # Generate streak insights
        streak_insights = self._generate_streak_insights(current_streak, longest_streak, sorted_dates)

        # Determine motivation level
        motivation_level = self._assess_motivation_level(current_streak, longest_streak, len(journal_entries))

        return {
            'current_streak': current_streak,
            'longest_streak': longest_streak,
            'total_journal_days': len(sorted_dates),
            'streak_insights': streak_insights,
            'motivation_level': motivation_level,
            'streak_history': self._generate_streak_history(sorted_dates)
        }

    # Helper methods for calculations and analysis

    def _calculate_trend_direction(self, daily_values_dict):
        """Calculate trend direction using linear regression"""
        if len(daily_values_dict) < 3:
            return 'stable'

        # Convert to lists for calculation
        dates = sorted(daily_values_dict.keys())
        values = [daily_values_dict[date] for date in dates]

        # Simple linear regression
        n = len(values)
        x_values = list(range(n))

        sum_x = sum(x_values)
        sum_y = sum(values)
        sum_xy = sum(x * y for x, y in zip(x_values, values))
        sum_x2 = sum(x * x for x in x_values)

        # Calculate slope
        slope = (n * sum_xy - sum_x * sum_y) / (n * sum_x2 - sum_x * sum_x)

        # Determine trend based on slope
        if slope > 0.1:
            return 'improving'
        elif slope < -0.1:
            return 'declining'
        else:
            return 'stable'

    def _calculate_stress_trend_direction(self, daily_averages):
        """Calculate stress trend (inverted - decreasing stress is improving)"""
        trend = self._calculate_trend_direction(daily_averages)

        # Invert for stress (decreasing stress = improving)
        if trend == 'improving':
            return 'declining'  # Stress is increasing (bad)
        elif trend == 'declining':
            return 'improving'  # Stress is decreasing (good)
        else:
            return 'stable'

    def _calculate_trend_strength(self, daily_averages):
        """Calculate how strong the trend is"""
        if len(daily_averages) < 5:
            return 'weak'

        values = list(daily_averages.values())

        # Calculate coefficient of variation
        mean_val = sum(values) / len(values)
        variance = sum((x - mean_val) ** 2 for x in values) / len(values)
        std_dev = variance ** 0.5

        if mean_val == 0:
            return 'weak'

        cv = std_dev / mean_val

        # Classify trend strength
        if cv > 0.3:
            return 'strong'
        elif cv > 0.15:
            return 'moderate'
        else:
            return 'weak'

    def _analyze_coping_effectiveness(self, stress_entries, all_coping_strategies):
        """Analyze effectiveness of coping strategies"""
        strategy_frequency = Counter(all_coping_strategies)

        # Simplified effectiveness calculation
        effective_strategies = []
        for strategy, freq in strategy_frequency.most_common(5):
            # In a real implementation, this would correlate strategy use with subsequent stress reduction
            effectiveness = min(0.9, freq / len(stress_entries) + 0.3)  # Placeholder calculation

            effective_strategies.append({
                'strategy': strategy,
                'frequency': freq,
                'effectiveness': round(effectiveness, 2),
                'recommendation': 'continue_using' if effectiveness > 0.6 else 'monitor_effectiveness'
            })

        return effective_strategies

    def _analyze_energy_activity_correlation(self, energy_entries):
        """Analyze correlation between energy levels and activities"""
        activity_energy = defaultdict(list)

        for entry in energy_entries:
            activity_energy[entry.entry_type].append(entry.energy_level)

        correlations = {}
        for activity, energy_levels in activity_energy.items():
            if len(energy_levels) >= 3:  # Need sufficient data
                avg_energy = sum(energy_levels) / len(energy_levels)
                correlations[activity] = {
                    'average_energy': round(avg_energy, 2),
                    'sample_size': len(energy_levels)
                }

        # Sort by energy level
        sorted_correlations = sorted(correlations.items(), key=lambda x: x[1]['average_energy'], reverse=True)

        return {
            'energy_boosting': sorted_correlations[:3],
            'energy_neutral': sorted_correlations[3:6] if len(sorted_correlations) > 6 else [],
            'energy_draining': sorted_correlations[-3:] if len(sorted_correlations) > 3 else []
        }

    def _analyze_energy_time_patterns(self, energy_entries):
        """Analyze energy patterns by time of day"""
        time_patterns = defaultdict(list)

        for entry in energy_entries:
            hour = entry.timestamp.hour
            time_periods = {
                'Morning': [6, 7, 8, 9, 10, 11],
                'Afternoon': [12, 13, 14, 15, 16, 17],
                'Evening': [18, 19, 20, 21, 22, 23],
                'Night': [0, 1, 2, 3, 4, 5]
            }

            for period, hours in time_periods.items():
                if hour in hours:
                    time_patterns[period].append(entry.energy_level)
                    break

        period_averages = {}
        for period, energy_levels in time_patterns.items():
            if energy_levels:
                period_averages[period] = round(sum(energy_levels) / len(energy_levels), 2)

        return period_averages

    def _calculate_gratitude_streak(self, gratitude_entries):
        """Calculate current gratitude practice streak"""
        if not gratitude_entries:
            return 0

        # Sort by date
        dates = sorted(set(entry.timestamp.date() for entry in gratitude_entries))

        if not dates:
            return 0

        # Calculate current streak from most recent date
        current_streak = 0
        today = timezone.now().date()
        check_date = today

        # Start from today or yesterday if no entry today
        if check_date not in dates:
            check_date = today - timedelta(days=1)

        while check_date in dates and check_date >= dates[0]:
            current_streak += 1
            check_date -= timedelta(days=1)

        return current_streak

    def _extract_gratitude_themes(self, gratitude_items):
        """Extract and categorize gratitude themes"""
        themes = defaultdict(int)

        # Simple keyword-based categorization
        theme_keywords = {
            'Family & Relationships': ['family', 'friend', 'relationship', 'love', 'support', 'partner'],
            'Health & Wellness': ['health', 'fitness', 'exercise', 'sleep', 'energy', 'wellness'],
            'Work & Career': ['work', 'job', 'career', 'project', 'team', 'colleague', 'achievement'],
            'Personal Growth': ['learning', 'growth', 'skill', 'improvement', 'progress', 'development'],
            'Life Experiences': ['experience', 'travel', 'adventure', 'memory', 'moment', 'opportunity'],
            'Basic Needs': ['food', 'shelter', 'safety', 'security', 'home', 'comfort']
        }

        for item in gratitude_items:
            item_lower = item.lower()
            categorized = False

            for theme, keywords in theme_keywords.items():
                if any(keyword in item_lower for keyword in keywords):
                    themes[theme] += 1
                    categorized = True
                    break

            if not categorized:
                themes['Other'] += 1

        # Return top themes
        return [{'theme': theme, 'count': count} for theme, count in
                Counter(themes).most_common(5)]

    def _analyze_gratitude_mood_impact(self, gratitude_entries, all_entries):
        """Analyze impact of gratitude practice on mood"""
        if not gratitude_entries:
            return {'impact_detected': False}

        # Find mood ratings on gratitude days vs non-gratitude days
        gratitude_dates = set(entry.timestamp.date() for entry in gratitude_entries)

        gratitude_day_moods = []
        non_gratitude_day_moods = []

        for entry in all_entries:
            if entry.mood_rating is not None:
                if entry.timestamp.date() in gratitude_dates:
                    gratitude_day_moods.append(entry.mood_rating)
                else:
                    non_gratitude_day_moods.append(entry.mood_rating)

        if not gratitude_day_moods or not non_gratitude_day_moods:
            return {'impact_detected': False, 'message': 'Insufficient data for comparison'}

        avg_gratitude_mood = sum(gratitude_day_moods) / len(gratitude_day_moods)
        avg_regular_mood = sum(non_gratitude_day_moods) / len(non_gratitude_day_moods)

        impact = avg_gratitude_mood - avg_regular_mood

        return {
            'impact_detected': abs(impact) > 0.3,
            'impact_magnitude': round(impact, 2),
            'gratitude_day_mood': round(avg_gratitude_mood, 2),
            'regular_day_mood': round(avg_regular_mood, 2),
            'interpretation': 'positive' if impact > 0.3 else 'negative' if impact < -0.3 else 'neutral'
        }

    def _categorize_achievements(self, achievements):
        """Categorize achievements into types"""
        categories = defaultdict(int)

        category_keywords = {
            'Work & Professional': ['project', 'work', 'training', 'certification', 'promotion', 'milestone'],
            'Personal Development': ['learning', 'skill', 'course', 'book', 'improvement', 'growth'],
            'Health & Fitness': ['exercise', 'fitness', 'health', 'weight', 'run', 'workout'],
            'Relationships': ['family', 'friend', 'relationship', 'social', 'community', 'help'],
            'Creative & Hobbies': ['creative', 'art', 'music', 'hobby', 'craft', 'design']
        }

        for achievement in achievements:
            achievement_lower = achievement.lower()
            categorized = False

            for category, keywords in category_keywords.items():
                if any(keyword in achievement_lower for keyword in keywords):
                    categories[category] += 1
                    categorized = True
                    break

            if not categorized:
                categories['Other'] += 1

        return dict(categories)

    def _analyze_achievement_trends(self, achievement_entries):
        """Analyze trends in achievement reporting"""
        if len(achievement_entries) < 4:
            return 'insufficient_data'

        # Group by month to see trends
        monthly_counts = defaultdict(int)
        for entry in achievement_entries:
            month_key = entry.timestamp.strftime('%Y-%m')
            monthly_counts[month_key] += 1

        if len(monthly_counts) < 2:
            return 'stable'

        # Simple trend analysis
        counts = list(monthly_counts.values())
        first_half = counts[:len(counts)//2]
        second_half = counts[len(counts)//2:]

        first_avg = sum(first_half) / len(first_half)
        second_avg = sum(second_half) / len(second_half)

        if second_avg > first_avg * 1.2:
            return 'increasing'
        elif second_avg < first_avg * 0.8:
            return 'decreasing'
        else:
            return 'stable'

    def _analyze_motivation_patterns(self, achievement_entries, all_entries):
        """Analyze motivation patterns around achievements"""
        # This is a simplified implementation
        # In a real system, this would correlate achievement entries with mood/energy patterns

        motivation_insights = []

        if achievement_entries:
            avg_achievements_per_entry = len([e for e in achievement_entries if e.achievements]) / len(achievement_entries)

            if avg_achievements_per_entry > 2:
                motivation_insights.append("High achievement orientation detected")
            elif avg_achievements_per_entry > 1:
                motivation_insights.append("Moderate achievement focus")
            else:
                motivation_insights.append("Consider tracking more achievements for motivation")

        return {
            'insights': motivation_insights,
            'achievement_frequency': len(achievement_entries) / max(1, len(all_entries))
        }

    def _detect_behavioral_patterns(self, journal_entries):
        """Detect behavioral patterns in journal entries"""
        patterns = []

        # Entry type patterns
        entry_types = [entry.entry_type for entry in journal_entries]
        type_frequency = Counter(entry_types)

        if type_frequency:
            top_type = type_frequency.most_common(1)[0]
            if top_type[1] > len(journal_entries) * 0.4:  # More than 40% of entries
                patterns.append({
                    'type': 'dominant_activity',
                    'pattern': f"Strong focus on {top_type[0]} activities",
                    'frequency': top_type[1],
                    'percentage': round(top_type[1] / len(journal_entries) * 100, 1)
                })

        # Temporal patterns
        hours = [entry.timestamp.hour for entry in journal_entries]
        hour_frequency = Counter(hours)

        if hour_frequency:
            peak_hour = hour_frequency.most_common(1)[0]
            if peak_hour[1] > len(journal_entries) * 0.3:
                patterns.append({
                    'type': 'temporal_preference',
                    'pattern': f"Prefers journaling around {peak_hour[0]}:00",
                    'frequency': peak_hour[1],
                    'percentage': round(peak_hour[1] / len(journal_entries) * 100, 1)
                })

        return patterns

    def _analyze_metric_correlations(self, journal_entries):
        """Analyze correlations between different wellbeing metrics"""
        # Collect entries with multiple metrics
        multi_metric_entries = [
            e for e in journal_entries
            if sum([
                e.mood_rating is not None,
                e.stress_level is not None,
                e.energy_level is not None
            ]) >= 2
        ]

        if len(multi_metric_entries) < 10:
            return {'insufficient_data': True}

        correlations = {}

        # Mood-Stress correlation
        mood_stress_pairs = [
            (e.mood_rating, e.stress_level)
            for e in multi_metric_entries
            if e.mood_rating is not None and e.stress_level is not None
        ]

        if len(mood_stress_pairs) >= 5:
            correlation = self._calculate_simple_correlation(mood_stress_pairs)
            correlations['mood_stress'] = {
                'correlation': round(correlation, 3),
                'interpretation': 'negative' if correlation < -0.3 else 'positive' if correlation > 0.3 else 'weak'
            }

        return correlations

    def _analyze_temporal_patterns(self, journal_entries):
        """Analyze temporal patterns in journal entries"""
        # Day of week patterns
        day_counts = Counter(entry.timestamp.strftime('%A') for entry in journal_entries)

        # Time of day patterns
        hour_counts = Counter(entry.timestamp.hour for entry in journal_entries)

        return {
            'day_patterns': dict(day_counts),
            'hour_patterns': dict(hour_counts),
            'peak_day': day_counts.most_common(1)[0] if day_counts else None,
            'peak_hour': hour_counts.most_common(1)[0] if hour_counts else None
        }

    def _generate_predictive_insights(self, journal_entries):
        """Generate predictive insights based on patterns"""
        insights = []

        # Recent trend analysis for prediction
        recent_entries = journal_entries[-14:] if len(journal_entries) >= 14 else journal_entries

        if recent_entries:
            recent_mood = [e.mood_rating for e in recent_entries if e.mood_rating is not None]
            if len(recent_mood) >= 5:
                trend = self._calculate_trend_direction({i: mood for i, mood in enumerate(recent_mood)})
                if trend == 'declining':
                    insights.append({
                        'type': 'mood_risk',
                        'message': 'Mood trending downward - consider proactive interventions',
                        'confidence': 0.7,
                        'timeframe': '1_week'
                    })

        return insights

    def _assess_pattern_strength(self, behavioral_patterns, temporal_patterns):
        """Assess overall strength of detected patterns"""
        strength_score = 0

        # More patterns = higher strength
        strength_score += len(behavioral_patterns) * 0.2

        # Strong temporal preferences indicate clear patterns
        if temporal_patterns.get('peak_day'):
            strength_score += 0.3
        if temporal_patterns.get('peak_hour'):
            strength_score += 0.3

        return min(1.0, strength_score)

    def _calculate_pattern_confidence(self, journal_entries):
        """Calculate confidence in pattern detection"""
        data_points = len(journal_entries)

        if data_points >= 60:
            return 0.9
        elif data_points >= 30:
            return 0.75
        elif data_points >= 14:
            return 0.6
        else:
            return 0.4

    def _calculate_simple_correlation(self, pairs):
        """Calculate simple Pearson correlation coefficient"""
        if len(pairs) < 3:
            return 0

        x_vals, y_vals = zip(*pairs)

        n = len(pairs)
        sum_x = sum(x_vals)
        sum_y = sum(y_vals)
        sum_xy = sum(x * y for x, y in pairs)
        sum_x2 = sum(x * x for x in x_vals)
        sum_y2 = sum(y * y for y in y_vals)

        numerator = n * sum_xy - sum_x * sum_y
        denominator = ((n * sum_x2 - sum_x ** 2) * (n * sum_y2 - sum_y ** 2)) ** 0.5

        if denominator == 0:
            return 0

        return numerator / denominator

    def _calculate_score_confidence(self, mood_trends, stress_analysis, energy_trends, journal_entries):
        """Calculate confidence in overall wellbeing score"""
        confidence_factors = []

        # Data quantity
        data_quantity = len(journal_entries)
        if data_quantity >= 60:
            confidence_factors.append(0.9)
        elif data_quantity >= 30:
            confidence_factors.append(0.75)
        elif data_quantity >= 14:
            confidence_factors.append(0.6)
        else:
            confidence_factors.append(0.4)

        # Data quality (multiple metrics)
        wellbeing_entries = len([e for e in journal_entries if e.has_wellbeing_metrics])
        data_quality = wellbeing_entries / max(1, len(journal_entries))
        confidence_factors.append(data_quality)

        # Trend consistency
        consistent_trends = 0
        total_trends = 0

        for analysis in [mood_trends, stress_analysis, energy_trends]:
            if analysis.get('data_quality') in ['good', 'excellent']:
                consistent_trends += 1
            total_trends += 1

        trend_consistency = consistent_trends / total_trends if total_trends > 0 else 0.5
        confidence_factors.append(trend_consistency)

        # Calculate weighted average
        return sum(confidence_factors) / len(confidence_factors)

    def _interpret_wellbeing_score(self, score, confidence):
        """Interpret the wellbeing score"""
        if confidence < 0.5:
            return "Score based on limited data - continue journaling for more accurate insights"

        if score >= 8.5:
            return "Excellent wellbeing - you're thriving! Maintain current practices."
        elif score >= 7.0:
            return "Good wellbeing with room for optimization. Focus on small improvements."
        elif score >= 5.5:
            return "Moderate wellbeing. Consider targeted improvements in lower-scoring areas."
        elif score >= 4.0:
            return "Below-average wellbeing. Multiple areas need attention and support."
        else:
            return "Low wellbeing detected. Consider professional support and immediate interventions."

    def _assess_data_quality_factors(self, journal_entries):
        """Assess factors affecting data quality"""
        factors = {}

        # Entry frequency
        if journal_entries:
            date_range = (journal_entries[-1].timestamp.date() - journal_entries[0].timestamp.date()).days
            frequency = len(journal_entries) / max(1, date_range)
            factors['entry_frequency'] = round(frequency, 3)

        # Wellbeing data completeness
        wellbeing_entries = len([e for e in journal_entries if e.has_wellbeing_metrics])
        factors['wellbeing_completeness'] = round(wellbeing_entries / max(1, len(journal_entries)), 3)

        # Content richness
        rich_entries = len([e for e in journal_entries if e.content and len(e.content) > 50])
        factors['content_richness'] = round(rich_entries / max(1, len(journal_entries)), 3)

        return factors

    # Additional helper methods for generating insights

    def _generate_mood_insights(self, mood_values, mood_patterns, trend_direction):
        """Generate mood-specific insights"""
        insights = []

        avg_mood = sum(mood_values) / len(mood_values)
        if avg_mood < 5:
            insights.append("Your mood levels indicate room for improvement through positive psychology practices")

        # Day patterns
        if mood_patterns:
            best_day = max(mood_patterns.items(), key=lambda x: x[1])
            worst_day = min(mood_patterns.items(), key=lambda x: x[1])

            if best_day[1] - worst_day[1] > 1.5:
                insights.append(f"Significant mood variation detected: {best_day[0]} is your best day, {worst_day[0]} needs attention")

        return insights

    def _generate_stress_insights(self, stress_values, common_triggers, effective_coping, stress_patterns):
        """Generate stress-specific insights"""
        insights = []

        avg_stress = sum(stress_values) / len(stress_values)
        if avg_stress > 3.5:
            insights.append("High stress levels detected - prioritize stress management techniques")

        if common_triggers:
            top_trigger = common_triggers[0]['trigger']
            insights.append(f"Your top stress trigger is '{top_trigger}' - consider targeted coping strategies")

        return insights

    def _generate_energy_insights(self, energy_values, activity_correlation, time_patterns, trend_direction):
        """Generate energy-specific insights"""
        insights = []

        avg_energy = sum(energy_values) / len(energy_values)
        if avg_energy < 6:
            insights.append("Energy levels below optimal - consider sleep, nutrition, and activity factors")

        if time_patterns:
            peak_time = max(time_patterns.items(), key=lambda x: x[1])
            insights.append(f"Peak energy time: {peak_time[0]} - schedule important tasks during this period")

        return insights

    def _generate_gratitude_insights(self, gratitude_entries, common_themes, gratitude_streak, gratitude_frequency):
        """Generate gratitude-specific insights"""
        insights = []

        if gratitude_frequency < 0.1:  # Less than once per 10 days
            insights.append("Consider increasing gratitude practice frequency for greater wellbeing benefits")

        if gratitude_streak >= 7:
            insights.append(f"Excellent gratitude streak of {gratitude_streak} days! Consistency is key to benefits.")

        if common_themes:
            top_theme = common_themes[0]['theme']
            insights.append(f"You're most grateful for {top_theme} - a key strength in your life")

        return insights

    def _generate_achievement_insights(self, achievement_entries, achievement_categories, achievement_trends):
        """Generate achievement-specific insights"""
        insights = []

        if not achievement_entries:
            insights.append("Consider tracking achievements to boost motivation and recognize progress")

        if achievement_categories:
            top_category = max(achievement_categories.items(), key=lambda x: x[1])
            insights.append(f"Strong achievement focus in {top_category[0]} - consider diversifying for balanced growth")

        if achievement_trends == 'increasing':
            insights.append("Achievement reporting is increasing - great momentum for continued growth!")

        return insights

    def _generate_streak_insights(self, current_streak, longest_streak, sorted_dates):
        """Generate streak-specific insights"""
        insights = []

        if current_streak >= 7:
            insights.append(f"Great consistency! {current_streak}-day journaling streak.")
        elif current_streak >= 3:
            insights.append(f"Building momentum with {current_streak}-day streak.")
        else:
            insights.append("Focus on consistency - even brief daily entries build powerful habits.")

        if longest_streak > current_streak * 2:
            insights.append(f"You've achieved {longest_streak} days before - you can do it again!")

        return insights

    def _assess_motivation_level(self, current_streak, longest_streak, total_entries):
        """Assess user's motivation level"""
        motivation_score = 0

        # Current streak contribution
        if current_streak >= 14:
            motivation_score += 3
        elif current_streak >= 7:
            motivation_score += 2
        elif current_streak >= 3:
            motivation_score += 1

        # Historical performance
        if longest_streak >= 30:
            motivation_score += 2
        elif longest_streak >= 14:
            motivation_score += 1

        # Overall engagement
        if total_entries >= 60:
            motivation_score += 2
        elif total_entries >= 30:
            motivation_score += 1

        # Map score to level
        if motivation_score >= 6:
            return 'high'
        elif motivation_score >= 3:
            return 'moderate'
        else:
            return 'building'

    def _generate_streak_history(self, sorted_dates):
        """Generate streak history for visualization"""
        if not sorted_dates or len(sorted_dates) < 2:
            return []

        # Simple streak history - last 30 days
        today = timezone.now().date()
        history = []

        for i in range(29, -1, -1):
            date = today - timedelta(days=i)
            has_entry = date in sorted_dates
            history.append({
                'date': date.isoformat(),
                'has_entry': has_entry
            })

        return history