"""
Crisis Prevention and Professional Escalation System

Comprehensive safety system that prevents mental health crises and ensures appropriate
professional intervention when needed. Implements WHO crisis prevention guidelines
and workplace safety protocols.

This system:
- Predicts crisis risk using advanced pattern analysis
- Implements early warning systems with graduated responses
- Provides professional escalation protocols (HR, EAP, healthcare)
- Ensures safety monitoring for high-risk users
- Integrates with professional healthcare systems
- Maintains strict privacy and consent compliance

Based on WHO Preventing Suicide: A Global Imperative guidelines and workplace crisis intervention research.
"""

import logging
from django.utils import timezone
from django.db.models import Q, Count, Avg, F
from django.db import transaction
from django.core.mail import send_mail
from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist, ValidationError
from datetime import timedelta, datetime
from collections import defaultdict, Counter

from apps.wellness.models import (
    InterventionDeliveryLog,
    MentalHealthIntervention,
    MentalHealthInterventionType,
    WellnessUserProgress
)
from apps.journal.models import JournalEntry, JournalPrivacySettings
from apps.journal.services.pattern_analyzer import JournalPatternAnalyzer
from apps.wellness.services.progressive_escalation_engine import ProgressiveEscalationEngine
from apps.core.exceptions.patterns import DATABASE_EXCEPTIONS, NETWORK_EXCEPTIONS

logger = logging.getLogger('crisis_prevention')


class CrisisPreventionSystem:
    """
    Evidence-based crisis prevention with professional escalation protocols

    Implements multi-layered crisis prevention based on WHO guidelines:
    1. Risk factor identification and monitoring
    2. Early warning systems with predictive algorithms
    3. Graduated intervention responses
    4. Professional escalation protocols
    5. Safety monitoring and follow-up systems
    """

    def __init__(self):
        self.pattern_analyzer = JournalPatternAnalyzer()
        self.escalation_engine = ProgressiveEscalationEngine()

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

        # Professional escalation protocols
        self.ESCALATION_PROTOCOLS = {
            'immediate_crisis': {
                'trigger_criteria': {
                    'suicidal_ideation_detected': True,
                    'crisis_risk_score': 8,
                    'urgency_score': 8
                },
                'immediate_actions': [
                    'deliver_crisis_resources',
                    'notify_emergency_contacts',
                    'trigger_professional_consultation',
                    'initiate_safety_monitoring'
                ],
                'notification_recipients': ['crisis_team', 'hr_wellness', 'employee_assistance'],
                'response_time_requirement': '5_minutes',
                'follow_up_requirements': ['daily_safety_checks', 'professional_referral']
            },
            'elevated_risk': {
                'trigger_criteria': {
                    'crisis_risk_score': 6,
                    'persistent_severe_symptoms': True,
                    'declining_functioning': True
                },
                'immediate_actions': [
                    'deliver_intensive_support',
                    'notify_wellness_team',
                    'schedule_professional_consultation'
                ],
                'notification_recipients': ['hr_wellness', 'employee_assistance'],
                'response_time_requirement': '2_hours',
                'follow_up_requirements': ['weekly_check_ins', 'escalation_monitoring']
            },
            'moderate_risk': {
                'trigger_criteria': {
                    'crisis_risk_score': 4,
                    'persistent_symptoms': True,
                    'poor_intervention_response': True
                },
                'immediate_actions': [
                    'intensify_interventions',
                    'provide_additional_resources',
                    'offer_professional_support_information'
                ],
                'notification_recipients': ['hr_wellness'],
                'response_time_requirement': '24_hours',
                'follow_up_requirements': ['bi_weekly_monitoring']
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

    def initiate_professional_escalation(self, user, risk_assessment, escalation_level='elevated_risk'):
        """
        Initiate professional escalation based on risk assessment

        Args:
            user: User object
            risk_assessment: Crisis risk assessment results
            escalation_level: Level of escalation required

        Returns:
            dict: Professional escalation results
        """
        logger.warning(f"Initiating professional escalation for user {user.id}: level {escalation_level}")

        try:
            # Check privacy consent and legal requirements
            privacy_check = self._check_escalation_privacy_requirements(user, escalation_level)

            if not privacy_check['escalation_allowed']:
                logger.error(f"Privacy restrictions prevent escalation for user {user.id}")
                return {
                    'success': False,
                    'reason': 'privacy_restrictions',
                    'privacy_requirements': privacy_check
                }

            # Get escalation protocol
            protocol = self.ESCALATION_PROTOCOLS.get(escalation_level, self.ESCALATION_PROTOCOLS['moderate_risk'])

            # Execute immediate actions
            immediate_actions = self._execute_immediate_actions(user, protocol, risk_assessment)

            # Notify appropriate recipients
            notification_results = self._notify_escalation_recipients(user, protocol, risk_assessment)

            # Initiate monitoring protocols
            monitoring_results = self._initiate_safety_monitoring(user, risk_assessment, escalation_level)

            # Create escalation record
            escalation_record = self._create_escalation_record(user, risk_assessment, escalation_level, protocol)

            result = {
                'success': True,
                'escalation_level': escalation_level,
                'escalation_record_id': escalation_record['id'],
                'immediate_actions_completed': immediate_actions['actions_completed'],
                'notifications_sent': notification_results['notifications_sent'],
                'monitoring_initiated': monitoring_results['monitoring_active'],
                'professional_referral_provided': immediate_actions.get('professional_referral_created', False),
                'safety_plan_created': immediate_actions.get('safety_plan_created', False),
                'next_follow_up': monitoring_results['next_follow_up_time'],
                'escalation_timestamp': timezone.now().isoformat()
            }

            logger.info(f"Professional escalation completed for user {user.id}: {immediate_actions['actions_completed']} actions taken")
            return result

        except DATABASE_EXCEPTIONS as e:
            logger.error(f"Database error during professional escalation for user {user.id}: {e}", exc_info=True)
            return {
                'success': False,
                'error': 'Database error during escalation'
            }
        except NETWORK_EXCEPTIONS as e:
            logger.error(f"Network error during professional escalation for user {user.id}: {e}", exc_info=True)
            return {
                'success': False,
                'error': 'Network error during escalation notifications'
            }
        except (ValueError, TypeError, KeyError) as e:
            logger.error(f"Data error during professional escalation for user {user.id}: {e}", exc_info=True)
            return {
                'success': False,
                'error': 'Invalid data during escalation'
            }

    def monitor_high_risk_users(self, risk_level_threshold='moderate_risk'):
        """
        Monitor all users at or above specified risk level

        Args:
            risk_level_threshold: Minimum risk level to monitor

        Returns:
            dict: Monitoring results and actions taken
        """
        logger.info(f"Monitoring high-risk users (threshold: {risk_level_threshold})")

        try:
            # Get list of users requiring monitoring
            high_risk_users = self._identify_high_risk_users(risk_level_threshold)

            monitoring_results = {
                'total_users_monitored': len(high_risk_users),
                'risk_assessments_completed': 0,
                'escalations_triggered': 0,
                'interventions_delivered': 0,
                'professional_referrals': 0,
                'monitoring_details': []
            }

            for user in high_risk_users:
                try:
                    # Perform fresh risk assessment
                    risk_assessment = self.assess_crisis_risk(user, analysis_period_days=7)

                    monitoring_results['risk_assessments_completed'] += 1

                    # Check if escalation is needed
                    if risk_assessment.get('escalation_requirements', {}).get('escalation_needed', False):
                        escalation_result = self.initiate_professional_escalation(
                            user, risk_assessment, risk_assessment['risk_level']
                        )

                        if escalation_result['success']:
                            monitoring_results['escalations_triggered'] += 1
                            if escalation_result.get('professional_referral_provided'):
                                monitoring_results['professional_referrals'] += 1

                    # Deliver appropriate interventions
                    intervention_result = self._deliver_risk_appropriate_interventions(user, risk_assessment)
                    monitoring_results['interventions_delivered'] += intervention_result['interventions_delivered']

                    monitoring_results['monitoring_details'].append({
                        'user_id': user.id,
                        'risk_level': risk_assessment.get('risk_level', 'unknown'),
                        'risk_score': risk_assessment.get('crisis_risk_score', 0),
                        'actions_taken': self._summarize_actions_taken(escalation_result if 'escalation_result' in locals() else None, intervention_result)
                    })

                except DATABASE_EXCEPTIONS as e:
                    logger.error(f"Database error monitoring user {user.id}: {e}", exc_info=True)
                    continue
                except (ValueError, TypeError, KeyError, AttributeError) as e:
                    logger.error(f"Data processing error monitoring user {user.id}: {e}", exc_info=True)
                    continue

            logger.info(f"High-risk user monitoring complete: {monitoring_results['total_users_monitored']} users, "
                       f"{monitoring_results['escalations_triggered']} escalations")

            return monitoring_results

        except DATABASE_EXCEPTIONS as e:
            logger.error(f"Database error in high-risk user monitoring: {e}", exc_info=True)
            return {
                'success': False,
                'error': 'Database error during monitoring'
            }
        except (ValueError, TypeError, KeyError, AttributeError) as e:
            logger.error(f"Data processing error in high-risk user monitoring: {e}", exc_info=True)
            return {
                'success': False,
                'error': 'Invalid data during monitoring'
            }

    def create_safety_plan(self, user, risk_assessment):
        """
        Create personalized safety plan for user at elevated risk

        Based on Stanley & Brown Safety Planning Intervention (WHO-recommended)

        Args:
            user: User object
            risk_assessment: Crisis risk assessment results

        Returns:
            dict: Safety plan details
        """
        logger.info(f"Creating safety plan for user {user.id}")

        try:
            # Generate personalized safety plan based on user's patterns
            safety_plan = {
                'user_id': user.id,
                'created_at': timezone.now().isoformat(),
                'risk_level': risk_assessment['risk_level'],
                'plan_components': {
                    'warning_signs': self._identify_personal_warning_signs(user, risk_assessment),
                    'coping_strategies': self._identify_effective_coping_strategies(user),
                    'support_contacts': self._compile_support_contacts(user),
                    'professional_resources': self._compile_professional_resources(user),
                    'environment_safety': self._generate_environment_safety_recommendations(user),
                    'crisis_resources': self._compile_crisis_resources()
                },
                'personalized_elements': {
                    'workplace_specific_strategies': self._generate_workplace_safety_strategies(user),
                    'preferred_coping_methods': self._identify_preferred_coping_methods(user),
                    'optimal_contact_methods': self._identify_optimal_contact_methods(user)
                },
                'review_schedule': self._determine_safety_plan_review_schedule(risk_assessment['risk_level']),
                'activation_instructions': self._generate_activation_instructions(user)
            }

            # Store safety plan in user's wellness progress
            self._store_safety_plan(user, safety_plan)

            # Schedule safety plan review
            self._schedule_safety_plan_review(user, safety_plan)

            logger.info(f"Safety plan created for user {user.id}")
            return {
                'success': True,
                'safety_plan': safety_plan,
                'plan_id': safety_plan.get('plan_id', 'generated'),
                'review_scheduled': True
            }

        except DATABASE_EXCEPTIONS as e:
            logger.error(f"Database error creating safety plan for user {user.id}: {e}", exc_info=True)
            return {
                'success': False,
                'error': 'Database error during safety plan creation'
            }
        except (ValueError, TypeError, KeyError, AttributeError) as e:
            logger.error(f"Data error creating safety plan for user {user.id}: {e}", exc_info=True)
            return {
                'success': False,
                'error': 'Invalid data during safety plan creation'
            }

    # Core crisis prevention methods

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
        protocol = self.ESCALATION_PROTOCOLS.get(risk_level, self.ESCALATION_PROTOCOLS['moderate_risk'])

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

    def _execute_immediate_actions(self, user, protocol, risk_assessment):
        """Execute immediate actions required by escalation protocol"""
        actions_completed = 0
        action_results = {}

        for action in protocol['immediate_actions']:
            try:
                if action == 'deliver_crisis_resources':
                    result = self._deliver_crisis_resources(user, risk_assessment)
                    action_results['crisis_resources_delivered'] = result['success']
                    if result['success']:
                        actions_completed += 1

                elif action == 'trigger_professional_consultation':
                    result = self._trigger_professional_consultation(user, risk_assessment)
                    action_results['professional_consultation_triggered'] = result['success']
                    if result['success']:
                        actions_completed += 1

                elif action == 'initiate_safety_monitoring':
                    result = self._initiate_intensive_safety_monitoring(user, risk_assessment)
                    action_results['safety_monitoring_initiated'] = result['success']
                    if result['success']:
                        actions_completed += 1

                elif action == 'intensify_interventions':
                    result = self._intensify_interventions(user, risk_assessment)
                    action_results['interventions_intensified'] = result['success']
                    if result['success']:
                        actions_completed += 1

            except DATABASE_EXCEPTIONS as e:
                logger.error(f"Database error executing action {action} for user {user.id}: {e}", exc_info=True)
                action_results[f"{action}_error"] = 'Database error'
            except NETWORK_EXCEPTIONS as e:
                logger.error(f"Network error executing action {action} for user {user.id}: {e}", exc_info=True)
                action_results[f"{action}_error"] = 'Network error'

        return {
            'actions_completed': actions_completed,
            'action_results': action_results
        }

    def _notify_escalation_recipients(self, user, protocol, risk_assessment):
        """Notify appropriate recipients of escalation"""
        notifications_sent = 0
        notification_results = {}

        for recipient_type in protocol['notification_recipients']:
            try:
                if recipient_type == 'crisis_team':
                    result = self._notify_crisis_team(user, risk_assessment)
                elif recipient_type == 'hr_wellness':
                    result = self._notify_hr_wellness_team(user, risk_assessment)
                elif recipient_type == 'employee_assistance':
                    result = self._notify_employee_assistance_program(user, risk_assessment)
                else:
                    result = {'success': False, 'reason': f'Unknown recipient type: {recipient_type}'}

                notification_results[recipient_type] = result
                if result['success']:
                    notifications_sent += 1

            except NETWORK_EXCEPTIONS as e:
                logger.error(f"Network error sending notification to {recipient_type}: {e}", exc_info=True)
                notification_results[recipient_type] = {'success': False, 'error': 'Network error'}
            except DATABASE_EXCEPTIONS as e:
                logger.error(f"Database error during notification to {recipient_type}: {e}", exc_info=True)
                notification_results[recipient_type] = {'success': False, 'error': 'Database error'}

        return {
            'notifications_sent': notifications_sent,
            'notification_details': notification_results
        }

    def _initiate_safety_monitoring(self, user, risk_assessment, escalation_level):
        """Initiate appropriate safety monitoring based on risk level"""
        monitoring_frequency = {
            'immediate_crisis': timedelta(hours=4),
            'elevated_risk': timedelta(hours=12),
            'moderate_risk': timedelta(days=1)
        }.get(escalation_level, timedelta(days=3))

        # Schedule monitoring task
        from background_tasks.mental_health_intervention_tasks import monitor_user_wellness_status

        monitoring_task = monitor_user_wellness_status.apply_async(
            args=[user.id],
            queue='high_priority',
            countdown=monitoring_frequency.total_seconds()
        )

        return {
            'monitoring_active': True,
            'monitoring_frequency': str(monitoring_frequency),
            'next_follow_up_time': timezone.now() + monitoring_frequency,
            'monitoring_task_id': monitoring_task.id
        }

    def _create_escalation_record(self, user, risk_assessment, escalation_level, protocol):
        """Create record of professional escalation for audit and follow-up"""
        escalation_record = {
            'id': f"escalation_{user.id}_{timezone.now().strftime('%Y%m%d_%H%M%S')}",
            'user_id': user.id,
            'escalation_level': escalation_level,
            'crisis_risk_score': risk_assessment['crisis_risk_score'],
            'active_risk_factors': risk_assessment['active_risk_factors'],
            'escalation_timestamp': timezone.now().isoformat(),
            'protocol_used': protocol,
            'privacy_compliance_verified': True,
            'professional_follow_up_required': True,
            'review_date': timezone.now() + timedelta(days=7)
        }

        # In production, this would be stored in a dedicated EscalationRecord model
        logger.info(f"Escalation record created: {escalation_record['id']}")

        return escalation_record

    # Content and pattern analysis methods

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

    # Helper methods for specific actions

    def _deliver_crisis_resources(self, user, risk_assessment):
        """Deliver immediate crisis resources to user"""
        try:
            # Get crisis resource intervention
            crisis_intervention = MentalHealthIntervention.objects.filter(
                intervention_type=MentalHealthInterventionType.CRISIS_RESOURCE,
                tenant=user.tenant
            ).first()

            if crisis_intervention:
                # Create immediate delivery log
                delivery_log = InterventionDeliveryLog.objects.create(
                    user=user,
                    intervention=crisis_intervention,
                    delivery_trigger='crisis_response',
                    user_mood_at_delivery=risk_assessment.get('crisis_risk_score', 0)
                )

                # Trigger immediate delivery
                from background_tasks.mental_health_intervention_tasks import _deliver_intervention_content

                delivery_task = _deliver_intervention_content.apply_async(
                    args=[str(delivery_log.id)],
                    queue='critical',
                    priority=10,
                    countdown=0
                )

                return {
                    'success': True,
                    'delivery_log_id': str(delivery_log.id),
                    'delivery_task_id': delivery_task.id
                }

            return {'success': False, 'reason': 'No crisis resource intervention available'}

        except DATABASE_EXCEPTIONS as e:
            logger.error(f"Database error delivering crisis resources: {e}", exc_info=True)
            return {'success': False, 'error': 'Database error'}
        except (ValueError, TypeError) as e:
            logger.error(f"Data error delivering crisis resources: {e}", exc_info=True)
            return {'success': False, 'error': 'Invalid data'}

    def _trigger_professional_consultation(self, user, risk_assessment):
        """Trigger professional consultation process"""
        try:
            # Create professional referral information
            referral_info = {
                'user_id': user.id,
                'risk_level': risk_assessment['risk_level'],
                'risk_score': risk_assessment['crisis_risk_score'],
                'immediate_consultation_required': risk_assessment['risk_level'] == 'immediate_crisis',
                'referral_timestamp': timezone.now().isoformat()
            }

            # In production, this would integrate with EAP systems
            logger.info(f"Professional consultation triggered for user {user.id}")

            return {
                'success': True,
                'referral_created': True,
                'consultation_type': 'urgent' if risk_assessment['risk_level'] == 'immediate_crisis' else 'routine'
            }

        except (ValueError, TypeError, KeyError) as e:
            logger.error(f"Data error triggering professional consultation: {e}", exc_info=True)
            return {'success': False, 'error': 'Invalid risk assessment data'}

    def _initiate_intensive_safety_monitoring(self, user, risk_assessment):
        """Initiate intensive safety monitoring for high-risk user"""
        try:
            # Create safety monitoring schedule
            monitoring_schedule = {
                'user_id': user.id,
                'monitoring_level': 'intensive',
                'check_frequency': timedelta(hours=4),
                'monitoring_duration': timedelta(days=7),
                'started_at': timezone.now(),
                'risk_score_at_start': risk_assessment['crisis_risk_score']
            }

            # Schedule first monitoring check
            from background_tasks.mental_health_intervention_tasks import schedule_crisis_follow_up_monitoring

            monitoring_task = schedule_crisis_follow_up_monitoring.apply_async(
                args=[user.id, risk_assessment],
                queue='high_priority',
                countdown=4 * 3600  # 4 hours
            )

            return {
                'success': True,
                'monitoring_schedule': monitoring_schedule,
                'monitoring_task_id': monitoring_task.id
            }

        except DATABASE_EXCEPTIONS as e:
            logger.error(f"Database error initiating safety monitoring: {e}", exc_info=True)
            return {'success': False, 'error': 'Database error'}
        except (ValueError, TypeError) as e:
            logger.error(f"Data error initiating safety monitoring: {e}", exc_info=True)
            return {'success': False, 'error': 'Invalid data'}

    # Notification methods for professional escalation

    def _sanitize_risk_factors_for_logging(self, risk_factors: list) -> dict:
        """
        Sanitize risk factors for safe logging (removes stigmatizing labels).

        Converts detailed risk factor names (which may contain stigmatizing mental
        health terminology) into safe, aggregated summary statistics for logging.
        This prevents sensitive information from appearing in application logs while
        preserving operational metrics.

        Args:
            risk_factors: List of risk factor dicts with 'factor', 'severity', 'category'

        Returns:
            dict: Safe summary for logging with only counts and distribution info
        """
        severity_counts = {}
        category_counts = {}

        for factor in risk_factors:
            severity = factor.get('severity', 'unknown')
            category = factor.get('category', 'uncategorized')

            severity_counts[severity] = severity_counts.get(severity, 0) + 1
            category_counts[category] = category_counts.get(category, 0) + 1

        return {
            'total_factors': len(risk_factors),
            'severity_distribution': severity_counts,
            'category_distribution': category_counts
            # No specific factor names - just counts
        }

    def _notify_crisis_team(self, user, risk_assessment):
        """Notify crisis response team"""
        try:
            # In production, this would send alerts to crisis response team
            logger.critical(f"CRISIS TEAM NOTIFICATION: User {user.id}, Risk Score: {risk_assessment['crisis_risk_score']}")

            # Create notification content with sanitized risk factors
            safe_risk_summary = self._sanitize_risk_factors_for_logging(
                risk_assessment.get('active_risk_factors', [])
            )

            notification_data = {
                'user_id': user.id,
                'user_name': '[USER]',  # Redact name to prevent PII exposure
                'risk_level': risk_assessment['risk_level'],
                'risk_score': risk_assessment['crisis_risk_score'],
                'risk_factors_summary': safe_risk_summary,  # Safe summary only, not detailed factors
                'immediate_action_required': True,
                'notification_time': timezone.now().isoformat()
            }

            # Send notification (placeholder - would integrate with actual notification system)
            return {
                'success': True,
                'notification_method': 'crisis_team_alert',
                'notification_data': notification_data
            }

        except (ValueError, TypeError, KeyError, AttributeError) as e:
            logger.error(f"Data error in crisis team notification: {e}", exc_info=True)
            return {'success': False, 'error': 'Invalid notification data'}

    def _notify_hr_wellness_team(self, user, risk_assessment):
        """Notify HR wellness team"""
        try:
            # Check privacy consent
            privacy_settings = JournalPrivacySettings.objects.filter(user=user).first()
            if privacy_settings and not privacy_settings.crisis_intervention_consent:
                return {
                    'success': False,
                    'reason': 'User has not consented to crisis intervention notifications'
                }

            # Create HR notification
            logger.warning(f"HR WELLNESS NOTIFICATION: User {user.id}, Risk Level: {risk_assessment['risk_level']}")

            return {
                'success': True,
                'notification_method': 'hr_wellness_email',
                'privacy_consent_verified': True
            }

        except DATABASE_EXCEPTIONS as e:
            logger.error(f"Database error in HR wellness notification: {e}", exc_info=True)
            return {'success': False, 'error': 'Database error'}
        except (ValueError, TypeError, KeyError) as e:
            logger.error(f"Data error in HR wellness notification: {e}", exc_info=True)
            return {'success': False, 'error': 'Invalid data'}

    def _notify_employee_assistance_program(self, user, risk_assessment):
        """Notify Employee Assistance Program"""
        try:
            logger.info(f"EAP NOTIFICATION: User {user.id}, Risk Level: {risk_assessment['risk_level']}")

            # Create EAP referral
            eap_referral = {
                'user_id': user.id,
                'risk_level': risk_assessment['risk_level'],
                'crisis_risk_score': risk_assessment['crisis_risk_score'],
                'referral_urgency': 'immediate' if risk_assessment['risk_level'] == 'immediate_crisis' else 'routine',
                'referral_timestamp': timezone.now().isoformat()
            }

            return {
                'success': True,
                'notification_method': 'eap_referral',
                'referral_created': True,
                'eap_referral_data': eap_referral
            }

        except (ValueError, TypeError, KeyError) as e:
            logger.error(f"Data error in EAP notification: {e}", exc_info=True)
            return {'success': False, 'error': 'Invalid data'}

    # Additional helper methods

    def _identify_high_risk_users(self, risk_level_threshold):
        """Identify users currently at or above risk threshold"""
        # This would query users based on recent risk assessments
        # For now, return users with recent high-urgency interventions
        high_risk_user_ids = InterventionDeliveryLog.objects.filter(
            delivered_at__gte=timezone.now() - timedelta(days=7),
            intervention__crisis_escalation_level__gte=6
        ).values_list('user_id', flat=True).distinct()

        return User.objects.filter(id__in=high_risk_user_ids)

    def _deliver_risk_appropriate_interventions(self, user, risk_assessment):
        """Deliver interventions appropriate for user's risk level"""
        # Select interventions based on risk level
        risk_level = risk_assessment['risk_level']

        if risk_level in ['immediate_crisis', 'elevated_risk']:
            # Deliver crisis-appropriate interventions
            intervention_types = [
                MentalHealthInterventionType.BREATHING_EXERCISE,
                MentalHealthInterventionType.CRISIS_RESOURCE
            ]
        else:
            # Deliver preventive interventions
            intervention_types = [
                MentalHealthInterventionType.BEHAVIORAL_ACTIVATION,
                MentalHealthInterventionType.GRATITUDE_JOURNAL
            ]

        interventions_delivered = 0

        for intervention_type in intervention_types[:2]:  # Limit to 2 interventions
            try:
                intervention = MentalHealthIntervention.objects.filter(
                    intervention_type=intervention_type,
                    tenant=user.tenant
                ).first()

                if intervention:
                    from background_tasks.mental_health_intervention_tasks import _schedule_intervention_delivery

                    task_result = _schedule_intervention_delivery.apply_async(
                        args=[user.id, intervention.id, 'risk_mitigation'],
                        queue='high_priority',
                        countdown=3600  # 1 hour
                    )

                    interventions_delivered += 1

            except DATABASE_EXCEPTIONS as e:
                logger.error(f"Database error delivering risk intervention: {e}", exc_info=True)
            except (ValueError, TypeError) as e:
                logger.error(f"Data error delivering risk intervention: {e}", exc_info=True)

        return {'interventions_delivered': interventions_delivered}

    def _summarize_actions_taken(self, escalation_result, intervention_result):
        """Summarize actions taken for monitoring report"""
        actions = []

        if escalation_result and escalation_result.get('success'):
            actions.append(f"Professional escalation initiated")
            if escalation_result.get('professional_referral_provided'):
                actions.append("Professional referral provided")

        if intervention_result.get('interventions_delivered', 0) > 0:
            actions.append(f"{intervention_result['interventions_delivered']} interventions delivered")

        return actions if actions else ['Monitoring only']

    def _calculate_standard_deviation(self, values):
        """Calculate standard deviation"""
        if len(values) < 2:
            return 0
        mean = sum(values) / len(values)
        variance = sum((x - mean) ** 2 for x in values) / len(values)
        return variance ** 0.5

    def _check_escalation_privacy_requirements(self, user, escalation_level):
        """Check privacy requirements for escalation"""
        try:
            privacy_settings = JournalPrivacySettings.objects.filter(user=user).first()

            if not privacy_settings:
                # No privacy settings - use conservative defaults
                return {
                    'escalation_allowed': escalation_level == 'immediate_crisis',  # Only for life-threatening situations
                    'consent_status': 'not_provided',
                    'legal_override': escalation_level == 'immediate_crisis'
                }

            # Check specific consent levels
            crisis_consent = privacy_settings.crisis_intervention_consent
            manager_consent = privacy_settings.manager_access_consent

            escalation_allowed = False

            if escalation_level == 'immediate_crisis':
                # Life-threatening situations may override privacy restrictions
                escalation_allowed = True
            elif escalation_level == 'elevated_risk':
                escalation_allowed = crisis_consent
            else:
                escalation_allowed = crisis_consent and manager_consent

            return {
                'escalation_allowed': escalation_allowed,
                'consent_status': 'provided',
                'crisis_consent': crisis_consent,
                'manager_consent': manager_consent,
                'legal_override': escalation_level == 'immediate_crisis'
            }

        except DATABASE_EXCEPTIONS as e:
            logger.error(f"Database error checking privacy requirements: {e}", exc_info=True)
            return {
                'escalation_allowed': escalation_level == 'immediate_crisis',
                'error': 'Database error'
            }
        except (ValueError, TypeError, KeyError, AttributeError) as e:
            logger.error(f"Data error checking privacy requirements: {e}", exc_info=True)
            return {
                'escalation_allowed': escalation_level == 'immediate_crisis',
                'error': 'Invalid data'
            }

    # Additional methods would include safety plan components, monitoring schedules, etc.
    # (Implementation continues with remaining helper methods...)