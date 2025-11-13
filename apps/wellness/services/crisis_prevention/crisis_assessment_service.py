"""
Crisis Risk Assessment Service

Handles comprehensive crisis risk assessment including:
- Risk factor identification and scoring
- Mood and stress pattern analysis
- Content analysis for crisis keywords
- Protective factor assessment
- Risk level determination

Based on WHO Preventing Suicide: A Global Imperative guidelines.
"""

import logging
from django.utils import timezone
from django.db.models import Q, Count, Avg, F
from datetime import timedelta
from collections import defaultdict

from apps.journal.models import JournalEntry
from apps.wellness.models import InterventionDeliveryLog
from apps.core.exceptions.patterns import DATABASE_EXCEPTIONS

logger = logging.getLogger('crisis_prevention')


class CrisisAssessmentService:
    """
    Evidence-based crisis risk assessment service

    Implements WHO-based risk assessment:
    1. Risk factor identification and monitoring
    2. Early warning systems with predictive algorithms
    3. Graduated intervention responses
    """

    def __init__(self):
        # WHO-based crisis risk factors
        self.CRISIS_RISK_FACTORS = {
            'primary_risk_factors': {
                'suicidal_ideation': {
                    'keywords': ['suicidal', 'end it all', 'kill myself', 'want to die', 'better off dead'],
                    'weight': 10,
                    'immediate_action': True
                },
                'hopelessness': {
                    'keywords': ['hopeless', 'no point', 'nothing matters', 'no future', 'trapped'],
                    'weight': 8,
                    'immediate_action': True
                },
                'severe_depression_indicators': {
                    'keywords': ['worthless', 'burden', 'failure', 'useless', 'hate myself'],
                    'weight': 7,
                    'immediate_action': False
                }
            },
            'warning_signs': {
                'social_withdrawal': {
                    'keywords': ['alone', 'nobody cares', 'isolated', 'avoiding everyone'],
                    'weight': 5,
                    'immediate_action': False
                },
                'extreme_mood_changes': {
                    'behavioral_indicators': ['extreme_mood_swings', 'sudden_mood_drops'],
                    'weight': 6,
                    'immediate_action': False
                },
                'substance_concerns': {
                    'keywords': ['drinking', 'drugs', 'to cope', 'numb the pain'],
                    'weight': 6,
                    'immediate_action': False
                },
                'work_performance_collapse': {
                    'behavioral_indicators': ['multiple_absences', 'quality_decline', 'safety_concerns'],
                    'weight': 4,
                    'immediate_action': False
                }
            },
            'protective_factors': {
                'social_support': {
                    'keywords': ['family', 'friends', 'support', 'help', 'talk to'],
                    'weight': -3,  # Negative weight (protective)
                    'strengthening_target': True
                },
                'coping_skills': {
                    'keywords': ['cope', 'strategy', 'manage', 'deal with', 'handle'],
                    'weight': -2,
                    'strengthening_target': True
                },
                'future_orientation': {
                    'keywords': ['plans', 'goals', 'future', 'looking forward', 'hope'],
                    'weight': -2,
                    'strengthening_target': True
                }
            }
        }

    def assess_crisis_risk(self, user, journal_entry=None, analysis_period_days=14):
        """
        Comprehensive crisis risk assessment for user

        Args:
            user: User object
            journal_entry: Current journal entry (optional)
            analysis_period_days: Period to analyze for risk assessment

        Returns:
            dict: Complete crisis risk assessment with action recommendations
        """
        logger.info(f"Assessing crisis risk for user {user.id}")

        try:
            # Collect risk assessment data
            risk_data = self._collect_crisis_risk_data(user, journal_entry, analysis_period_days)

            # Calculate crisis risk score
            crisis_risk_score = self._calculate_crisis_risk_score(risk_data)

            # Identify active risk factors
            active_risk_factors = self._identify_active_risk_factors(risk_data)

            # Assess protective factors
            protective_factors = self._assess_protective_factors(risk_data)

            # Determine risk level and required actions
            risk_level = self._determine_risk_level(crisis_risk_score, active_risk_factors)

            # Generate action plan
            action_plan = self._generate_crisis_action_plan(risk_level, active_risk_factors, protective_factors)

            # Check escalation requirements
            escalation_requirements = self._check_escalation_requirements(risk_level, crisis_risk_score)

            assessment = {
                'user_id': user.id,
                'assessment_timestamp': timezone.now().isoformat(),
                'crisis_risk_score': crisis_risk_score,
                'risk_level': risk_level,
                'active_risk_factors': active_risk_factors,
                'protective_factors': protective_factors,
                'action_plan': action_plan,
                'escalation_requirements': escalation_requirements,
                'immediate_safety_concerns': risk_level in ['immediate_crisis', 'elevated_risk'],
                'professional_consultation_recommended': crisis_risk_score >= 6,
                'monitoring_requirements': self._determine_monitoring_requirements(risk_level),
                'next_assessment_date': self._calculate_next_assessment_date(risk_level),
                'privacy_compliance': self._check_privacy_compliance(user, risk_level)
            }

            # Log risk assessment
            if risk_level == 'immediate_crisis':
                logger.critical(f"IMMEDIATE CRISIS RISK: User {user.id}, Score: {crisis_risk_score}")
            elif risk_level == 'elevated_risk':
                logger.warning(f"ELEVATED CRISIS RISK: User {user.id}, Score: {crisis_risk_score}")
            else:
                logger.info(f"Crisis risk assessment complete: User {user.id}, Level: {risk_level}")

            return assessment

        except DATABASE_EXCEPTIONS as e:
            logger.error(f"Database error during crisis risk assessment for user {user.id}: {e}", exc_info=True)
            return {
                'success': False,
                'error': 'Database error during risk assessment',
                'user_id': user.id
            }
        except (ValueError, TypeError, KeyError, AttributeError) as e:
            logger.error(f"Data processing error during crisis risk assessment for user {user.id}: {e}", exc_info=True)
            return {
                'success': False,
                'error': 'Invalid data during risk assessment',
                'user_id': user.id
            }

    def _collect_crisis_risk_data(self, user, journal_entry, analysis_period_days):
        """Collect comprehensive data for crisis risk assessment"""
        since_date = timezone.now() - timedelta(days=analysis_period_days)

        # Get recent journal entries
        recent_entries = JournalEntry.objects.filter(
            user=user,
            timestamp__gte=since_date,
            is_deleted=False
        ).order_by('-timestamp')

        # Get intervention history
        intervention_history = InterventionDeliveryLog.objects.filter(
            user=user,
            delivered_at__gte=since_date
        ).select_related('intervention')

        # Collect risk data
        risk_data = {
            'recent_entries': list(recent_entries),
            'current_entry': journal_entry,
            'intervention_history': list(intervention_history),
            'mood_trends': self._extract_mood_trends(recent_entries),
            'stress_patterns': self._extract_stress_patterns(recent_entries),
            'content_analysis': self._analyze_content_for_risk_factors(recent_entries, journal_entry),
            'behavioral_changes': self._analyze_behavioral_risk_changes(user, since_date),
            'intervention_response_patterns': self._analyze_intervention_response_for_risk(intervention_history)
        }

        return risk_data

    def _calculate_crisis_risk_score(self, risk_data):
        """Calculate quantitative crisis risk score"""
        risk_score = 0

        # Content analysis risk factors
        content_risk = risk_data['content_analysis']
        for factor_category, factors in content_risk.items():
            for factor, details in factors.items():
                weight = details.get('weight', 0)
                frequency = details.get('frequency', 0)
                risk_score += weight * frequency

        # Mood trend risk factors
        mood_trends = risk_data['mood_trends']
        if mood_trends['average_mood'] < 3:
            risk_score += 5
        elif mood_trends['average_mood'] < 4:
            risk_score += 3

        if mood_trends['trend_direction'] == 'severely_declining':
            risk_score += 4
        elif mood_trends['trend_direction'] == 'declining':
            risk_score += 2

        # Stress pattern risk factors
        stress_patterns = risk_data['stress_patterns']
        if stress_patterns['average_stress'] >= 4.5:
            risk_score += 3
        elif stress_patterns['average_stress'] >= 4:
            risk_score += 2

        # Behavioral change risk factors
        behavioral_changes = risk_data['behavioral_changes']
        if behavioral_changes['social_withdrawal_detected']:
            risk_score += 3
        if behavioral_changes['work_performance_decline']:
            risk_score += 2

        # Intervention response risk factors
        intervention_response = risk_data['intervention_response_patterns']
        if intervention_response['poor_response_pattern']:
            risk_score += 2
        if intervention_response['intervention_avoidance']:
            risk_score += 1

        # Apply protective factor reductions
        protective_score = 0
        for factor_category, factors in content_risk.items():
            if factor_category == 'protective_factors':
                for factor, details in factors.items():
                    weight = abs(details.get('weight', 0))  # Protective factors have negative weights
                    frequency = details.get('frequency', 0)
                    protective_score += weight * frequency

        # Reduce risk score by protective factors (but don't go below 0)
        final_risk_score = max(0, risk_score - protective_score)

        return round(final_risk_score, 1)

    def _identify_active_risk_factors(self, risk_data):
        """Identify currently active risk factors"""
        active_factors = []

        # Content-based risk factors
        content_analysis = risk_data['content_analysis']
        for category, factors in content_analysis.items():
            if category != 'protective_factors':
                for factor, details in factors.items():
                    if details.get('frequency', 0) > 0:
                        active_factors.append({
                            'factor': factor,
                            'category': category,
                            'severity': details.get('weight', 0),
                            'frequency': details.get('frequency', 0),
                            'immediate_action_required': details.get('immediate_action', False)
                        })

        # Behavioral risk factors
        behavioral_changes = risk_data['behavioral_changes']
        for behavior, detected in behavioral_changes.items():
            if detected:
                active_factors.append({
                    'factor': behavior,
                    'category': 'behavioral_changes',
                    'severity': 3,  # Moderate severity for behavioral factors
                    'immediate_action_required': behavior in ['severe_isolation', 'safety_concerns']
                })

        # Sort by severity
        active_factors.sort(key=lambda x: x['severity'], reverse=True)

        return active_factors

    def _assess_protective_factors(self, risk_data):
        """Assess user's protective factors"""
        protective_factors = []

        # Content-based protective factors
        content_analysis = risk_data['content_analysis']
        protective_content = content_analysis.get('protective_factors', {})

        for factor, details in protective_content.items():
            if details.get('frequency', 0) > 0:
                protective_factors.append({
                    'factor': factor,
                    'strength': details.get('frequency', 0),
                    'strengthening_target': details.get('strengthening_target', False)
                })

        # Behavioral protective factors
        behavioral_changes = risk_data['behavioral_changes']
        if behavioral_changes.get('help_seeking_behavior'):
            protective_factors.append({
                'factor': 'help_seeking_behavior',
                'strength': 3,
                'strengthening_target': True
            })

        if behavioral_changes.get('social_connection_maintained'):
            protective_factors.append({
                'factor': 'social_connection',
                'strength': 2,
                'strengthening_target': True
            })

        return protective_factors

    def _determine_risk_level(self, crisis_risk_score, active_risk_factors):
        """Determine overall risk level based on score and factors"""
        # Check for immediate crisis indicators
        immediate_factors = [f for f in active_risk_factors if f.get('immediate_action_required', False)]

        if immediate_factors or crisis_risk_score >= 8:
            return 'immediate_crisis'
        elif crisis_risk_score >= 6:
            return 'elevated_risk'
        elif crisis_risk_score >= 4:
            return 'moderate_risk'
        elif crisis_risk_score >= 2:
            return 'low_risk'
        else:
            return 'minimal_risk'

    def _generate_crisis_action_plan(self, risk_level, active_risk_factors, protective_factors):
        """Generate comprehensive action plan based on risk assessment"""
        # Import escalation protocols from professional escalation service
        from apps.wellness.services.crisis_prevention.professional_escalation_service import ProfessionalEscalationService

        # Get escalation protocols
        escalation_service = ProfessionalEscalationService()
        protocol = escalation_service.ESCALATION_PROTOCOLS.get(risk_level, escalation_service.ESCALATION_PROTOCOLS['moderate_risk'])

        action_plan = {
            'immediate_actions': protocol['immediate_actions'],
            'response_time_requirement': protocol['response_time_requirement'],
            'follow_up_requirements': protocol['follow_up_requirements'],
            'risk_mitigation_strategies': self._generate_risk_mitigation_strategies(active_risk_factors),
            'protective_factor_strengthening': self._generate_protective_factor_strategies(protective_factors),
            'professional_resources': self._compile_appropriate_professional_resources(risk_level),
            'monitoring_plan': self._create_monitoring_plan(risk_level, active_risk_factors)
        }

        return action_plan

    def _check_escalation_requirements(self, risk_level, crisis_risk_score):
        """Check if professional escalation is required"""
        escalation_needed = risk_level in ['immediate_crisis', 'elevated_risk']

        return {
            'escalation_needed': escalation_needed,
            'escalation_urgency': 'immediate' if risk_level == 'immediate_crisis' else 'within_24_hours',
            'professional_consultation_required': crisis_risk_score >= 6,
            'emergency_services_consideration': crisis_risk_score >= 9,
            'manager_notification_required': risk_level == 'immediate_crisis',  # With consent
            'hr_notification_required': escalation_needed,
            'eap_referral_required': escalation_needed
        }

    def _analyze_content_for_risk_factors(self, recent_entries, current_entry):
        """Analyze journal content for crisis risk factors"""
        all_entries = list(recent_entries)
        if current_entry:
            all_entries.append(current_entry)

        content_analysis = {
            'primary_risk_factors': {},
            'warning_signs': {},
            'protective_factors': {}
        }

        all_content = ' '.join([entry.content for entry in all_entries if entry.content])
        content_lower = all_content.lower()

        # Analyze each risk factor category
        for category, factors in self.CRISIS_RISK_FACTORS.items():
            content_analysis[category] = {}

            for factor_name, factor_data in factors.items():
                keywords = factor_data.get('keywords', [])
                frequency = sum(1 for keyword in keywords if keyword in content_lower)

                if frequency > 0:
                    content_analysis[category][factor_name] = {
                        'frequency': frequency,
                        'weight': factor_data.get('weight', 0),
                        'immediate_action': factor_data.get('immediate_action', False)
                    }

        return content_analysis

    def _extract_mood_trends(self, recent_entries):
        """Extract mood trends from recent entries"""
        mood_ratings = []
        for entry in recent_entries:
            if hasattr(entry, 'wellbeing_metrics') and entry.wellbeing_metrics:
                mood = getattr(entry.wellbeing_metrics, 'mood_rating', None)
                if mood:
                    mood_ratings.append(mood)

        if not mood_ratings:
            return {'insufficient_data': True}

        average_mood = sum(mood_ratings) / len(mood_ratings)

        # Determine trend direction
        if len(mood_ratings) >= 3:
            first_half = mood_ratings[:len(mood_ratings)//2]
            second_half = mood_ratings[len(mood_ratings)//2:]

            first_avg = sum(first_half) / len(first_half)
            second_avg = sum(second_half) / len(second_half)

            if second_avg < first_avg - 2:
                trend_direction = 'severely_declining'
            elif second_avg < first_avg - 1:
                trend_direction = 'declining'
            elif second_avg > first_avg + 1:
                trend_direction = 'improving'
            else:
                trend_direction = 'stable'
        else:
            trend_direction = 'insufficient_data'

        return {
            'average_mood': round(average_mood, 2),
            'trend_direction': trend_direction,
            'lowest_mood': min(mood_ratings),
            'mood_variability': round(self._calculate_standard_deviation(mood_ratings), 2),
            'concerning_pattern': average_mood < 4 and trend_direction in ['declining', 'severely_declining']
        }

    def _extract_stress_patterns(self, recent_entries):
        """Extract stress patterns from recent entries"""
        stress_levels = []
        for entry in recent_entries:
            if hasattr(entry, 'wellbeing_metrics') and entry.wellbeing_metrics:
                stress = getattr(entry.wellbeing_metrics, 'stress_level', None)
                if stress:
                    stress_levels.append(stress)

        if not stress_levels:
            return {'insufficient_data': True}

        average_stress = sum(stress_levels) / len(stress_levels)
        high_stress_count = len([s for s in stress_levels if s >= 4])

        return {
            'average_stress': round(average_stress, 2),
            'high_stress_frequency': high_stress_count / len(stress_levels),
            'maximum_stress': max(stress_levels),
            'persistent_high_stress': high_stress_count >= len(stress_levels) * 0.6,
            'concerning_pattern': average_stress >= 4 and high_stress_count >= 3
        }

    def _analyze_behavioral_risk_changes(self, user, since_date):
        """Analyze behavioral changes that indicate risk"""
        # Get baseline data from earlier period
        baseline_start = since_date - timedelta(days=14)
        baseline_entries = JournalEntry.objects.filter(
            user=user,
            timestamp__gte=baseline_start,
            timestamp__lt=since_date,
            is_deleted=False
        ).count()

        recent_entries = JournalEntry.objects.filter(
            user=user,
            timestamp__gte=since_date,
            is_deleted=False
        ).count()

        # Calculate changes
        journaling_frequency_change = recent_entries - baseline_entries

        behavioral_changes = {
            'social_withdrawal_detected': journaling_frequency_change < -3,  # Significant decrease in journaling
            'work_performance_decline': False,  # Would analyze from work context entries
            'help_seeking_behavior': recent_entries > 0,  # Continuing to journal is help-seeking
            'social_connection_maintained': False,  # Would analyze from relationship mentions
            'routine_disruption': abs(journaling_frequency_change) > 5
        }

        return behavioral_changes

    def _analyze_intervention_response_for_risk(self, intervention_history):
        """Analyze intervention response patterns for risk indicators"""
        if not intervention_history:
            return {'insufficient_data': True}

        completion_rate = len([i for i in intervention_history if i.was_completed]) / len(intervention_history)

        avg_helpfulness = 0
        helpfulness_ratings = [i.perceived_helpfulness for i in intervention_history if i.perceived_helpfulness]
        if helpfulness_ratings:
            avg_helpfulness = sum(helpfulness_ratings) / len(helpfulness_ratings)

        return {
            'poor_response_pattern': completion_rate < 0.3 and avg_helpfulness < 2.0,
            'intervention_avoidance': completion_rate < 0.2,
            'declining_engagement': False,  # Would calculate trend
            'crisis_intervention_usage': len([i for i in intervention_history if i.intervention.crisis_escalation_level >= 6]),
            'recent_completion_rate': completion_rate
        }

    def _calculate_standard_deviation(self, values):
        """Calculate standard deviation"""
        if len(values) < 2:
            return 0
        mean = sum(values) / len(values)
        variance = sum((x - mean) ** 2 for x in values) / len(values)
        return variance ** 0.5

    def _determine_monitoring_requirements(self, risk_level):
        """Determine monitoring requirements based on risk level"""
        monitoring_map = {
            'immediate_crisis': {'frequency': 'every_4_hours', 'duration': '7_days'},
            'elevated_risk': {'frequency': 'every_12_hours', 'duration': '14_days'},
            'moderate_risk': {'frequency': 'daily', 'duration': '30_days'},
            'low_risk': {'frequency': 'weekly', 'duration': '30_days'},
            'minimal_risk': {'frequency': 'bi_weekly', 'duration': '30_days'}
        }
        return monitoring_map.get(risk_level, monitoring_map['moderate_risk'])

    def _calculate_next_assessment_date(self, risk_level):
        """Calculate next assessment date based on risk level"""
        assessment_intervals = {
            'immediate_crisis': timedelta(hours=4),
            'elevated_risk': timedelta(hours=12),
            'moderate_risk': timedelta(days=1),
            'low_risk': timedelta(days=3),
            'minimal_risk': timedelta(days=7)
        }
        interval = assessment_intervals.get(risk_level, timedelta(days=1))
        return (timezone.now() + interval).isoformat()

    def _check_privacy_compliance(self, user, risk_level):
        """Check privacy compliance requirements"""
        from apps.journal.models import JournalPrivacySettings

        try:
            privacy_settings = JournalPrivacySettings.objects.filter(user=user).first()

            if not privacy_settings:
                return {
                    'consent_provided': False,
                    'analysis_allowed': risk_level == 'immediate_crisis'
                }

            return {
                'consent_provided': privacy_settings.crisis_intervention_consent,
                'analysis_allowed': True,
                'manager_notification_allowed': privacy_settings.manager_access_consent
            }
        except DATABASE_EXCEPTIONS:
            return {'consent_provided': False, 'analysis_allowed': risk_level == 'immediate_crisis'}

    # Placeholder methods for action plan generation
    def _generate_risk_mitigation_strategies(self, active_risk_factors):
        """Generate risk mitigation strategies"""
        return [f"Address {factor['factor']}" for factor in active_risk_factors[:3]]

    def _generate_protective_factor_strategies(self, protective_factors):
        """Generate protective factor strengthening strategies"""
        return [f"Strengthen {factor['factor']}" for factor in protective_factors if factor.get('strengthening_target')]

    def _compile_appropriate_professional_resources(self, risk_level):
        """Compile professional resources appropriate for risk level"""
        if risk_level in ['immediate_crisis', 'elevated_risk']:
            return ['crisis_hotline', 'eap_services', 'mental_health_professional']
        return ['counseling_services', 'self_help_resources']

    def _create_monitoring_plan(self, risk_level, active_risk_factors):
        """Create monitoring plan"""
        return {
            'monitoring_frequency': self._determine_monitoring_requirements(risk_level)['frequency'],
            'focus_areas': [f['factor'] for f in active_risk_factors[:3]]
        }
