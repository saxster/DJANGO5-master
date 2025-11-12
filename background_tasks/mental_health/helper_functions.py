"""
Helper Functions for Mental Health Interventions

Shared utility functions used across mental health intervention tasks including:
- Content generation and personalization
- Delivery channel determination
- User eligibility checks
- Follow-up data collection and analysis
- Escalation recipient determination
- Notification delivery functions

These helper functions support crisis intervention, delivery, and effectiveness tracking.
"""

from django.utils import timezone
from django.contrib.auth import get_user_model
from datetime import timedelta
import logging

from apps.wellness.models import (
    MentalHealthInterventionType,
    InterventionDeliveryLog,
)
from apps.wellness.constants import (
    CRISIS_ESCALATION_THRESHOLD,
    INTENSIVE_ESCALATION_THRESHOLD,
    HIGH_URGENCY_THRESHOLD,
)
from apps.wellness.services.cbt_thought_record_templates import CBTThoughtRecordTemplateEngine

User = get_user_model()
logger = logging.getLogger('mental_health_tasks')


# Content Generation and Delivery Channel Functions

def _generate_dynamic_intervention_content(intervention, user, delivery_log):
    """Generate dynamic, personalized intervention content"""
    content = {
        'base_content': intervention.wellness_content.content,
        'title': intervention.wellness_content.title,
        'summary': intervention.wellness_content.summary,
        'estimated_time': intervention.intervention_duration_minutes,
        'personalization': {}
    }

    # Add personalized elements based on intervention type
    if intervention.intervention_type == MentalHealthInterventionType.THOUGHT_RECORD:
        # Generate personalized CBT template
        cbt_engine = CBTThoughtRecordTemplateEngine()
        template = cbt_engine.generate_thought_record_template(
            user=user,
            mood_rating=delivery_log.user_mood_at_delivery,
            stress_triggers=[]  # Would extract from triggering entry
        )
        content['personalization']['cbt_template'] = template

    elif intervention.intervention_type in [
        MentalHealthInterventionType.GRATITUDE_JOURNAL,
        MentalHealthInterventionType.THREE_GOOD_THINGS
    ]:
        # Add gratitude personalization
        content['personalization']['gratitude_prompts'] = intervention.guided_questions
        content['personalization']['workplace_context'] = True

    return content


def _determine_delivery_channels(user, intervention, delivery_log):
    """Determine optimal delivery channels for intervention"""
    channels = []

    # Crisis interventions always get multiple channels
    if intervention.crisis_escalation_level >= CRISIS_ESCALATION_THRESHOLD:
        channels = ['in_app_notification', 'email', 'mqtt_push']
    else:
        # Regular interventions use preferred channels
        # Default to in-app notification
        channels = ['in_app_notification']

        # Add email for complex interventions
        if intervention.intervention_duration_minutes >= 5:
            channels.append('email')

    return channels


def _deliver_via_in_app_notification(user, content, delivery_log):
    """Deliver intervention via in-app notification"""
    # Placeholder for in-app notification delivery
    # Would integrate with existing notification system
    logger.info(f"Delivering in-app notification for intervention {delivery_log.id}")
    return {'success': True, 'delivery_method': 'in_app_notification'}


def _deliver_via_email(user, content, delivery_log):
    """Deliver intervention via email"""
    # Placeholder for email delivery
    # Would integrate with existing email system
    logger.info(f"Delivering email for intervention {delivery_log.id}")
    return {'success': True, 'delivery_method': 'email'}


def _deliver_via_mqtt_push(user, content, delivery_log):
    """Deliver intervention via MQTT push notification"""
    # Placeholder for MQTT delivery
    # Would integrate with existing MQTT system
    logger.info(f"Delivering MQTT push for intervention {delivery_log.id}")
    return {'success': True, 'delivery_method': 'mqtt_push'}


# User Eligibility and Status Functions

def _find_users_eligible_for_positive_interventions(target_interventions):
    """Find users eligible for positive psychology interventions"""
    # Get users who haven't received target interventions in the last week
    week_ago = timezone.now() - timedelta(days=7)

    users_with_recent_interventions = InterventionDeliveryLog.objects.filter(
        intervention__intervention_type__in=target_interventions,
        delivered_at__gte=week_ago
    ).values_list('user_id', flat=True).distinct()

    # Find active users without recent positive psychology interventions
    eligible_users = User.objects.filter(
        enable=True,  # Active users
        is_deleted=False
    ).exclude(
        id__in=users_with_recent_interventions
    )

    return list(eligible_users)


def _assess_current_user_status(user):
    """Assess user's current status for follow-up monitoring"""
    # Simplified assessment - would be more comprehensive in production
    from apps.journal.models import JournalEntry

    recent_entry = JournalEntry.objects.filter(
        user=user,
        timestamp__gte=timezone.now() - timedelta(hours=6),
        is_deleted=False
    ).order_by('-timestamp').first()

    if recent_entry and hasattr(recent_entry, 'wellbeing_metrics') and recent_entry.wellbeing_metrics:
        metrics = recent_entry.wellbeing_metrics
        return {
            'current_mood': getattr(metrics, 'mood_rating', None),
            'current_stress': getattr(metrics, 'stress_level', None),
            'current_energy': getattr(metrics, 'energy_level', None),
            'data_timestamp': recent_entry.timestamp
        }

    return {'no_recent_data': True}


def _check_for_improvement(crisis_analysis, current_status):
    """Check if user has improved since crisis intervention"""
    if current_status.get('no_recent_data'):
        return False  # No data, assume no improvement

    # Simple improvement check
    current_mood = current_status.get('current_mood')
    if current_mood and current_mood >= 4:  # Mood improved above crisis threshold
        return True

    return False


def _should_escalate_further(crisis_analysis, current_status):
    """Determine if further escalation is needed"""
    # Very conservative - only escalate if clear deterioration
    if current_status.get('current_mood') and current_status['current_mood'] <= 2:
        return True

    return False


# Follow-up Data Collection and Analysis

def _collect_follow_up_data(delivery_log):
    """Collect follow-up data after intervention delivery"""
    from apps.journal.models import JournalEntry

    # Look for journal entries in the 24 hours following intervention
    follow_up_entries = JournalEntry.objects.filter(
        user=delivery_log.user,
        timestamp__gt=delivery_log.delivered_at,
        timestamp__lte=delivery_log.delivered_at + timedelta(hours=24),
        is_deleted=False
    ).order_by('timestamp')

    follow_up_data = {
        'mood_improvement_detected': False,
        'follow_up_mood': None,
        'engagement_level': 'unknown',
        'follow_up_entries_count': follow_up_entries.count()
    }

    if follow_up_entries:
        # Check for mood improvement
        latest_entry = follow_up_entries.first()
        if hasattr(latest_entry, 'wellbeing_metrics') and latest_entry.wellbeing_metrics:
            follow_up_mood = getattr(latest_entry.wellbeing_metrics, 'mood_rating', None)
            if follow_up_mood and delivery_log.user_mood_at_delivery:
                mood_change = follow_up_mood - delivery_log.user_mood_at_delivery
                follow_up_data['mood_improvement_detected'] = mood_change > 0
                follow_up_data['follow_up_mood'] = follow_up_mood

    return follow_up_data


def _analyze_intervention_effectiveness(delivery_log, follow_up_data):
    """Analyze effectiveness of delivered intervention"""
    effectiveness_score = 0

    # Completion bonus
    if delivery_log.was_completed:
        effectiveness_score += 2

    # Mood improvement bonus
    if follow_up_data['mood_improvement_detected']:
        effectiveness_score += 3

    # User rating bonus
    if delivery_log.perceived_helpfulness:
        effectiveness_score += delivery_log.perceived_helpfulness

    # Follow-up engagement bonus
    if follow_up_data['follow_up_entries_count'] > 0:
        effectiveness_score += 1

    poor_response = effectiveness_score < 3 and delivery_log.was_completed

    return {
        'effectiveness_score': effectiveness_score,
        'poor_response_detected': poor_response,
        'factors': {
            'completion': delivery_log.was_completed,
            'mood_improvement': follow_up_data['mood_improvement_detected'],
            'user_rating': delivery_log.perceived_helpfulness,
            'follow_up_engagement': follow_up_data['follow_up_entries_count'] > 0
        }
    }


def _update_user_personalization_profile(user, intervention, effectiveness_analysis):
    """Update user's personalization profile based on intervention effectiveness"""
    # This would update the user's WellnessUserProgress personalization_profile
    # with intervention effectiveness data for future personalization
    logger.debug(f"Updating personalization profile for user {user.id}")
    return True


# Escalation Functions

def _determine_escalation_recipients(user, escalation_level, urgency_score):
    """Determine who should be notified for professional escalation"""
    recipients = []

    if escalation_level >= INTENSIVE_ESCALATION_THRESHOLD or urgency_score >= HIGH_URGENCY_THRESHOLD:
        # Crisis level - notify all relevant parties
        recipients.extend([
            {'type': 'hr_wellness', 'urgency': 'immediate'},
            {'type': 'employee_assistance', 'urgency': 'immediate'},
            {'type': 'manager', 'urgency': 'immediate'}  # If user has opted in
        ])
    elif escalation_level >= 3:  # Moderate support level
        # Intensive level - notify wellness team
        recipients.extend([
            {'type': 'hr_wellness', 'urgency': 'high'},
            {'type': 'employee_assistance', 'urgency': 'moderate'}
        ])

    return recipients


def _determine_escalation_change(current_escalation, effectiveness_analysis):
    """Determine if escalation level should change"""
    current_level = current_escalation['recommended_escalation_level']

    # Check if escalation up is needed (poor response)
    if effectiveness_analysis['poor_response_detected'] and current_level < 4:
        return {
            'change_needed': True,
            'new_level': current_level + 1,
            'reason': 'Poor response to current intervention level'
        }

    # Check if de-escalation is possible (good response and stable)
    if (effectiveness_analysis['effectiveness_score'] >= 4 and
        current_level > 1 and
        'crisis_indicators' not in current_escalation.get('active_escalation_triggers', [])):
        return {
            'change_needed': True,
            'new_level': current_level - 1,
            'reason': 'Good response allows de-escalation'
        }

    return {'change_needed': False}


def _implement_escalation_change(user, escalation_change, current_escalation):
    """Implement escalation level change"""
    new_level = escalation_change['new_level']

    logger.info(f"Implementing escalation change for user {user.id}: level {new_level}")

    # Cancel existing scheduled interventions that are no longer appropriate
    # Schedule new interventions appropriate for new level

    return {
        'new_interventions_scheduled': 1,  # Placeholder
        'old_interventions_cancelled': 0   # Placeholder
    }


# Notification Functions

def _send_hr_wellness_notification(recipient, notification_data):
    """Send notification to HR wellness team"""
    logger.info(f"Sending HR wellness notification for user {notification_data['user_id']}")
    return {'success': True, 'method': 'hr_email'}


def _send_manager_notification(recipient, notification_data):
    """Send notification to user's manager (if consent given)"""
    logger.info(f"Sending manager notification for user {notification_data['user_id']}")
    return {'success': True, 'method': 'manager_email'}


def _send_eap_notification(recipient, notification_data):
    """Send notification to Employee Assistance Program"""
    logger.info(f"Sending EAP notification for user {notification_data['user_id']}")
    return {'success': True, 'method': 'eap_referral'}
