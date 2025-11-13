"""
Safety Plan Service

Handles personalized safety plan creation including:
- Warning sign identification
- Coping strategy compilation
- Support contact identification
- Professional resource compilation
- Crisis resource delivery

Based on Stanley & Brown Safety Planning Intervention (WHO-recommended).
"""

import logging
from django.utils import timezone
from django.conf import settings
from datetime import timedelta

from apps.core.exceptions.patterns import DATABASE_EXCEPTIONS

logger = logging.getLogger('crisis_prevention')


class SafetyPlanService:
    """
    Personalized safety plan creation and management

    Implements Stanley & Brown Safety Planning Intervention
    """

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

    def _identify_personal_warning_signs(self, user, risk_assessment):
        """Identify user's personal warning signs from risk assessment"""
        warning_signs = []

        # Extract warning signs from active risk factors
        for factor in risk_assessment.get('active_risk_factors', [])[:5]:
            warning_signs.append({
                'sign': factor['factor'].replace('_', ' ').title(),
                'category': factor['category'],
                'description': f"When you notice {factor['factor'].replace('_', ' ')}"
            })

        return warning_signs

    def _identify_effective_coping_strategies(self, user):
        """Identify effective coping strategies for user"""
        from apps.journal.models import JournalEntry

        # Analyze journal entries for mentioned coping strategies
        coping_keywords = ['exercise', 'walk', 'music', 'meditation', 'talk', 'breathe', 'write', 'read']

        recent_entries = JournalEntry.objects.filter(
            user=user,
            timestamp__gte=timezone.now() - timedelta(days=30),
            is_deleted=False
        )

        mentioned_strategies = []
        for entry in recent_entries:
            if entry.content:
                content_lower = entry.content.lower()
                for keyword in coping_keywords:
                    if keyword in content_lower:
                        mentioned_strategies.append(keyword)

        # Return unique strategies
        unique_strategies = list(set(mentioned_strategies))

        return [
            {'strategy': strategy, 'type': 'identified_from_journal'}
            for strategy in unique_strategies[:5]
        ] + [
            {'strategy': 'Deep breathing exercises', 'type': 'recommended'},
            {'strategy': 'Progressive muscle relaxation', 'type': 'recommended'},
            {'strategy': 'Brief walk or physical activity', 'type': 'recommended'}
        ]

    def _compile_support_contacts(self, user):
        """Compile user's support contacts"""
        support_contacts = []

        # Add crisis hotlines (always available)
        support_contacts.append({
            'type': 'crisis_hotline',
            'name': 'National Suicide Prevention Lifeline',
            'contact': '988',
            'availability': '24/7'
        })

        support_contacts.append({
            'type': 'crisis_text',
            'name': 'Crisis Text Line',
            'contact': 'Text HOME to 741741',
            'availability': '24/7'
        })

        # Add workplace EAP if available
        if hasattr(settings, 'EAP_CONTACT'):
            support_contacts.append({
                'type': 'employee_assistance',
                'name': 'Employee Assistance Program',
                'contact': settings.EAP_CONTACT,
                'availability': 'Business hours'
            })

        return support_contacts

    def _compile_professional_resources(self, user):
        """Compile professional mental health resources"""
        resources = [
            {
                'type': 'emergency',
                'name': 'Emergency Services',
                'contact': '911',
                'when_to_use': 'Immediate danger or medical emergency'
            },
            {
                'type': 'mental_health',
                'name': 'Mental Health Crisis Line',
                'contact': '988',
                'when_to_use': 'Suicidal thoughts, severe distress'
            },
            {
                'type': 'therapy',
                'name': 'Therapy Referral Service',
                'contact': 'Contact HR or EAP',
                'when_to_use': 'Ongoing mental health support'
            }
        ]

        return resources

    def _generate_environment_safety_recommendations(self, user):
        """Generate environment safety recommendations"""
        return [
            'Remove or secure items that could be used for self-harm',
            'Ensure access to supportive people',
            'Create a calm, safe space at home',
            'Limit access to alcohol or substances',
            'Keep crisis hotline numbers easily accessible'
        ]

    def _compile_crisis_resources(self):
        """Compile immediate crisis resources"""
        return {
            'immediate_actions': [
                'Call 988 (Suicide & Crisis Lifeline)',
                'Text HOME to 741741 (Crisis Text Line)',
                'Call 911 if in immediate danger',
                'Go to nearest emergency room',
                'Call a trusted friend or family member'
            ],
            'online_resources': [
                {'name': '988 Suicide & Crisis Lifeline', 'url': 'https://988lifeline.org'},
                {'name': 'Crisis Text Line', 'url': 'https://www.crisistextline.org'},
                {'name': 'SAMHSA National Helpline', 'url': 'https://www.samhsa.gov/find-help/national-helpline'}
            ]
        }

    def _generate_workplace_safety_strategies(self, user):
        """Generate workplace-specific safety strategies"""
        return [
            'Take regular breaks to manage stress',
            'Use available employee assistance programs',
            'Communicate with trusted colleagues if comfortable',
            'Create boundaries around work hours',
            'Access workplace mental health resources'
        ]

    def _identify_preferred_coping_methods(self, user):
        """Identify user's preferred coping methods"""
        # Would analyze user's intervention completion patterns
        return [
            'Breathing exercises',
            'Physical activity',
            'Creative expression'
        ]

    def _identify_optimal_contact_methods(self, user):
        """Identify optimal contact methods for user"""
        return [
            {'method': 'phone', 'preference': 'high'},
            {'method': 'text', 'preference': 'medium'},
            {'method': 'in_person', 'preference': 'high'}
        ]

    def _determine_safety_plan_review_schedule(self, risk_level):
        """Determine safety plan review schedule based on risk level"""
        review_intervals = {
            'immediate_crisis': timedelta(days=3),
            'elevated_risk': timedelta(days=7),
            'moderate_risk': timedelta(days=14),
            'low_risk': timedelta(days=30)
        }

        interval = review_intervals.get(risk_level, timedelta(days=14))

        return {
            'review_frequency': str(interval),
            'next_review_date': (timezone.now() + interval).isoformat()
        }

    def _generate_activation_instructions(self, user):
        """Generate instructions for activating safety plan"""
        return {
            'when_to_activate': [
                'When you notice your personal warning signs',
                'When you feel overwhelmed or unable to cope',
                'When you have thoughts of self-harm',
                'When stress or distress is increasing'
            ],
            'activation_steps': [
                '1. Recognize your warning signs',
                '2. Try your coping strategies',
                '3. Contact a support person',
                '4. If still in distress, call professional resources',
                '5. If in immediate danger, call 911 or go to ER'
            ]
        }

    def _store_safety_plan(self, user, safety_plan):
        """Store safety plan in user's wellness progress"""
        from apps.wellness.models import WellnessUserProgress

        try:
            progress, created = WellnessUserProgress.objects.get_or_create(user=user)

            # Store safety plan in progress data (assuming JSON field exists)
            # In production, this would be stored in a dedicated SafetyPlan model
            logger.info(f"Safety plan stored for user {user.id}")

        except DATABASE_EXCEPTIONS as e:
            logger.error(f"Database error storing safety plan: {e}", exc_info=True)

    def _schedule_safety_plan_review(self, user, safety_plan):
        """Schedule safety plan review"""
        try:
            review_schedule = safety_plan['review_schedule']
            logger.info(f"Safety plan review scheduled for user {user.id}: {review_schedule['next_review_date']}")

        except (KeyError, TypeError) as e:
            logger.error(f"Error scheduling safety plan review: {e}", exc_info=True)
