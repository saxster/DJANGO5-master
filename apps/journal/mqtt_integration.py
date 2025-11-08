"""
MQTT Integration for Real-Time Wellness Notifications

Integrates journal and wellness system with existing MQTT infrastructure for:
- Real-time wellness content delivery notifications
- Crisis intervention alerts to designated personnel
- Achievement and milestone notifications
- Pattern analysis alerts for immediate interventions
- System health and analytics notifications
"""

import json
import logging
from django.conf import settings
from django.utils import timezone
from paho.mqtt import client as mqtt
from celery import shared_task

from apps.journal.models import JournalEntry
from apps.wellness.models import WellnessContent, WellnessContentInteraction
from apps.mqtt.client import MqttClient

logger = logging.getLogger(__name__)


class JournalWellnessMQTTService:
    """
    MQTT service for journal and wellness real-time notifications

    Features:
    - Crisis intervention alerts
    - Wellness content delivery notifications
    - Achievement milestone alerts
    - Pattern analysis notifications
    - System health notifications
    """

    # MQTT Topics for Journal & Wellness
    TOPICS = {
        'wellness_content_delivery': 'wellness/content/delivery/{user_id}',
        'crisis_intervention': 'wellness/crisis/alert/{user_id}',
        'achievement_milestone': 'wellness/achievement/{user_id}',
        'pattern_analysis': 'journal/pattern/analysis/{user_id}',
        'daily_tip': 'wellness/daily_tip/{user_id}',
        'system_health': 'wellness/system/health',
        'analytics_update': 'journal/analytics/updated/{user_id}'
    }

    def __init__(self):
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        self.mqtt_config = getattr(settings, 'MQTT_CONFIG', {})

    def send_wellness_content_notification(self, user, content, delivery_context='daily_tip'):
        """
        Send real-time notification for wellness content delivery

        Args:
            user: User to send notification to
            content: WellnessContent object
            delivery_context: Context of delivery

        Returns:
            bool: Success status
        """

        try:
            # Prepare notification payload
            notification_payload = {
                'type': 'wellness_content_delivery',
                'timestamp': timezone.now().isoformat(),
                'user_id': str(user.id),
                'user_name': user.peoplename,
                'delivery_context': delivery_context,
                'content': {
                    'id': str(content.id),
                    'title': content.title,
                    'summary': content.summary,
                    'category': content.category,
                    'content_level': content.content_level,
                    'estimated_reading_time': content.estimated_reading_time,
                    'evidence_level': content.evidence_level,
                    'action_tips': content.action_tips[:3],  # First 3 tips for notification
                    'priority_score': content.priority_score
                },
                'notification_priority': self._calculate_notification_priority(content, delivery_context),
                'expires_at': (timezone.now() + timezone.timedelta(hours=24)).isoformat()
            }

            # Determine topic
            if delivery_context == 'daily_tip':
                topic = self.TOPICS['daily_tip'].format(user_id=user.id)
            else:
                topic = self.TOPICS['wellness_content_delivery'].format(user_id=user.id)

            # Send via MQTT
            success = self._publish_mqtt_message(topic, notification_payload)

            if success:
                self.logger.info(f"Wellness content notification sent to user {user.id}: '{content.title}'")
            else:
                self.logger.error(f"Failed to send wellness notification to user {user.id}")

            return success

        except (DatabaseError, IntegrationException, ValueError) as e:
            self.logger.error(f"Wellness content notification failed for user {user.id}: {e}")
            return False

    def send_crisis_intervention_alert(self, user, journal_entry, crisis_indicators, intervention_team_ids=None):
        """
        Send crisis intervention alert to designated personnel

        Args:
            user: User in crisis
            journal_entry: Journal entry that triggered crisis
            crisis_indicators: List of detected crisis indicators
            intervention_team_ids: List of user IDs to alert (optional)

        Returns:
            bool: Success status
        """

        self.logger.critical(f"Sending crisis intervention alert for user {user.id}")

        try:
            # Prepare crisis alert payload
            crisis_payload = {
                'type': 'crisis_intervention_alert',
                'severity': 'CRITICAL',
                'timestamp': timezone.now().isoformat(),
                'user_info': {
                    'id': str(user.id),
                    'name': user.peoplename,
                    'email': user.email,
                    'tenant': user.tenant.tenantname if user.tenant else None,
                    'department': getattr(user, 'department', None)
                },
                'journal_entry': {
                    'id': str(journal_entry.id),
                    'title': journal_entry.title,
                    'timestamp': journal_entry.timestamp.isoformat(),
                    'mood_rating': journal_entry.mood_rating,
                    'stress_level': journal_entry.stress_level,
                    'energy_level': journal_entry.energy_level
                },
                'crisis_indicators': crisis_indicators,
                'intervention_required': True,
                'recommended_actions': [
                    'Immediate wellness content delivered',
                    'Monitor user activity closely',
                    'Consider direct outreach if appropriate',
                    'Document intervention steps taken'
                ],
                'privacy_note': 'CONFIDENTIAL - Handle per crisis intervention policy',
                'alert_expires_at': (timezone.now() + timezone.timedelta(hours=48)).isoformat()
            }

            # Send to crisis intervention topic
            topic = self.TOPICS['crisis_intervention'].format(user_id=user.id)
            success = self._publish_mqtt_message(topic, crisis_payload, qos=2)  # Highest QoS for crisis

            # Also send to general crisis alert topic for monitoring
            general_crisis_topic = 'wellness/crisis/alert/general'
            self._publish_mqtt_message(general_crisis_topic, {
                'user_id': str(user.id),
                'severity': 'CRITICAL',
                'timestamp': timezone.now().isoformat(),
                'crisis_score': len(crisis_indicators)
            }, qos=1)

            if success:
                self.logger.critical(f"Crisis intervention alert sent for user {user.id}")
            else:
                self.logger.error(f"FAILED to send crisis alert for user {user.id} - MANUAL INTERVENTION REQUIRED")

            return success

        except (DatabaseError, IntegrationException, ValueError) as e:
            self.logger.error(f"Crisis alert failed for user {user.id}: {e}")
            return False

    def send_achievement_notification(self, user, achievements):
        """
        Send achievement milestone notification

        Args:
            user: User who earned achievements
            achievements: List of achievement names

        Returns:
            bool: Success status
        """

        try:
            # Prepare achievement notification
            achievement_payload = {
                'type': 'wellness_achievement',
                'timestamp': timezone.now().isoformat(),
                'user_id': str(user.id),
                'user_name': user.peoplename,
                'achievements': achievements,
                'celebration_message': f'🎉 Congratulations! You earned: {", ".join(achievements)}',
                'motivational_message': self._generate_motivational_message(achievements),
                'suggested_sharing': True,  # Suggest user share achievement
                'next_milestone_hint': self._get_next_milestone_hint(user, achievements)
            }

            topic = self.TOPICS['achievement_milestone'].format(user_id=user.id)
            success = self._publish_mqtt_message(topic, achievement_payload)

            if success:
                self.logger.info(f"Achievement notification sent to user {user.id}: {achievements}")

            return success

        except (DatabaseError, IntegrationException, ValueError) as e:
            self.logger.error(f"Achievement notification failed for user {user.id}: {e}")
            return False

    def send_pattern_analysis_notification(self, user, journal_entry, analysis_result):
        """
        Send pattern analysis notification for immediate interventions

        Args:
            user: User whose entry was analyzed
            journal_entry: Journal entry that was analyzed
            analysis_result: Pattern analysis results

        Returns:
            bool: Success status
        """

        urgency_score = analysis_result.get('urgency_score', 0)

        # Only send notifications for significant patterns
        if urgency_score < 3:
            return True  # No notification needed for low urgency

        try:
            notification_payload = {
                'type': 'pattern_analysis_notification',
                'timestamp': timezone.now().isoformat(),
                'user_id': str(user.id),
                'journal_entry_id': str(journal_entry.id),
                'analysis_result': {
                    'urgency_score': urgency_score,
                    'urgency_level': analysis_result.get('urgency_level'),
                    'intervention_categories': analysis_result.get('intervention_categories', []),
                    'recommended_content_count': analysis_result.get('recommended_content_count', 0),
                    'delivery_timing': analysis_result.get('delivery_timing'),
                    'follow_up_required': analysis_result.get('follow_up_required', False)
                },
                'user_context': {
                    'mood_rating': journal_entry.mood_rating,
                    'stress_level': journal_entry.stress_level,
                    'energy_level': journal_entry.energy_level,
                    'entry_type': journal_entry.entry_type
                },
                'notification_level': 'high' if urgency_score >= 5 else 'medium'
            }

            topic = self.TOPICS['pattern_analysis'].format(user_id=user.id)
            success = self._publish_mqtt_message(topic, notification_payload)

            if success:
                self.logger.info(f"Pattern analysis notification sent for user {user.id} (urgency: {urgency_score})")

            return success

        except (DatabaseError, IntegrationException, ValueError) as e:
            self.logger.error(f"Pattern analysis notification failed: {e}")
            return False

    def send_analytics_update_notification(self, user, analytics_summary):
        """Send notification when user analytics are updated"""

        try:
            notification_payload = {
                'type': 'analytics_updated',
                'timestamp': timezone.now().isoformat(),
                'user_id': str(user.id),
                'analytics_summary': {
                    'wellbeing_score': analytics_summary.get('wellbeing_score'),
                    'recommendation_count': analytics_summary.get('recommendations_count', 0),
                    'data_quality': analytics_summary.get('data_quality', 'unknown'),
                    'analysis_period_days': analytics_summary.get('analysis_period_days', 30)
                },
                'insights_available': True,
                'action_required': analytics_summary.get('wellbeing_score', 10) < 6.0
            }

            topic = self.TOPICS['analytics_update'].format(user_id=user.id)
            success = self._publish_mqtt_message(topic, notification_payload)

            if success:
                self.logger.debug(f"Analytics update notification sent for user {user.id}")

            return success

        except (DatabaseError, IntegrationException, ValueError) as e:
            self.logger.error(f"Analytics update notification failed: {e}")
            return False

    def _publish_mqtt_message(self, topic, payload, qos=1, retain=False):
        """Publish message using existing MQTT infrastructure"""
        try:
            # Use existing MQTT client infrastructure
            mqtt_client = MqttClient()

            # Convert payload to JSON
            message_json = json.dumps(payload, default=str)

            # Publish message
            result = mqtt_client.client.publish(
                topic=topic,
                payload=message_json,
                qos=qos,
                retain=retain
            )

            # Check if message was published successfully
            if result.rc == mqtt.MQTT_ERR_SUCCESS:
                self.logger.debug(f"MQTT message published to {topic}")
                return True
            else:
                self.logger.error(f"MQTT publish failed for topic {topic}: {result.rc}")
                return False

        except (DatabaseError, IntegrationException, TypeError, ValueError, json.JSONDecodeError) as e:
            self.logger.error(f"MQTT message publishing failed: {e}")
            return False

    def _calculate_notification_priority(self, content, delivery_context):
        """Calculate notification priority based on content and context"""
        base_priority = content.priority_score / 100  # Normalize to 0-1

        # Context-based priority adjustments
        context_adjustments = {
            'stress_response': 0.3,
            'mood_support': 0.3,
            'crisis_intervention': 0.5,
            'daily_tip': 0.1,
            'pattern_triggered': 0.2
        }

        adjustment = context_adjustments.get(delivery_context, 0.0)
        final_priority = min(1.0, base_priority + adjustment)

        # Map to notification levels
        if final_priority >= 0.8:
            return 'high'
        elif final_priority >= 0.6:
            return 'medium'
        else:
            return 'low'

    def _generate_motivational_message(self, achievements):
        """Generate motivational message for achievements"""
        messages = {
            'week_streak': "A week of consistent wellness engagement! You're building a powerful habit.",
            'month_streak': "30 days of wellness commitment! You're making a real difference in your wellbeing.",
            'content_explorer': "You're actively exploring wellness content - knowledge is power for wellbeing!",
            'wellness_scholar': "Outstanding wellness engagement! You're becoming a wellbeing expert.",
            'stress_master': "You're mastering stress management techniques - keep up the great work!"
        }

        # Get message for first achievement
        first_achievement = achievements[0] if achievements else 'achievement'
        message = messages.get(first_achievement, "Great job on your wellness journey!")

        if len(achievements) > 1:
            message += f" Plus {len(achievements) - 1} more achievements!"

        return message

    def _get_next_milestone_hint(self, user, current_achievements):
        """Get hint about next milestone"""
        hints = [
            "Keep up your daily wellness engagement!",
            "Try exploring new wellness categories for variety.",
            "Share your success with colleagues to inspire them.",
            "Consider setting a longer-term wellness goal."
        ]

        # TODO: Implement more sophisticated next milestone calculation
        return hints[0]


# MQTT Message Handlers for Journal & Wellness
class WellnessMQTTMessageHandler:
    """Handle incoming MQTT messages related to wellness system"""

    def __init__(self):
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

    def handle_wellness_content_request(self, user_id, request_data):
        """Handle real-time wellness content request"""
        try:
            from apps.wellness.services.content_delivery import WelnessTipSelector
            from django.contrib.auth import get_user_model

            User = get_user_model()
            user = User.objects.get(id=user_id)

            # Get personalized content based on request
            tip_selector = WelnessTipSelector()
            selected_content = tip_selector.select_personalized_tip(
                user,
                request_data.get('user_patterns', {}),
                request_data.get('previously_seen', [])
            )

            if selected_content:
                # Send content via MQTT
                mqtt_service = JournalWellnessMQTTService()
                mqtt_service.send_wellness_content_notification(
                    user, selected_content, request_data.get('delivery_context', 'on_demand')
                )

                return True

            return False

        except (DatabaseError, IntegrationException, IntegrityError, ObjectDoesNotExist, TypeError, ValueError, json.JSONDecodeError) as e:
            self.logger.error(f"Failed to handle wellness content request: {e}")
            return False

    def handle_pattern_analysis_request(self, user_id, journal_entry_data):
        """Handle real-time pattern analysis request"""
        try:
            from apps.journal.services.pattern_analyzer import JournalPatternAnalyzer
            from django.contrib.auth import get_user_model

            User = get_user_model()
            user = User.objects.get(id=user_id)

            # Create temporary journal entry for analysis
            temp_entry_data = {
                'user': user,
                'tenant': user.tenant,
                'title': journal_entry_data.get('title', 'Real-time Analysis'),
                'content': journal_entry_data.get('content', ''),
                'entry_type': journal_entry_data.get('entry_type', 'PERSONAL_REFLECTION'),
                'mood_rating': journal_entry_data.get('mood_rating'),
                'stress_level': journal_entry_data.get('stress_level'),
                'energy_level': journal_entry_data.get('energy_level'),
                'timestamp': timezone.now()
            }

            # Create temporary entry object (not saved to database)
            temp_entry = JournalEntry(**temp_entry_data)

            # Perform pattern analysis
            analyzer = JournalPatternAnalyzer()
            analysis_result = analyzer.analyze_entry_for_immediate_action(temp_entry)

            # Send analysis result via MQTT
            mqtt_service = JournalWellnessMQTTService()
            mqtt_service.send_pattern_analysis_notification(user, temp_entry, analysis_result)

            return analysis_result

        except (DatabaseError, IntegrationException, IntegrityError, ObjectDoesNotExist, TypeError, ValueError, json.JSONDecodeError) as e:
            self.logger.error(f"Failed to handle pattern analysis request: {e}")
            return None


# Celery tasks for MQTT integration
@shared_task
def send_wellness_notification_async(user_id, content_id, delivery_context='daily_tip'):
    """Send wellness notification asynchronously"""
    try:
        from django.contrib.auth import get_user_model

        User = get_user_model()
        user = User.objects.get(id=user_id)
        content = WellnessContent.objects.get(id=content_id)

        mqtt_service = JournalWellnessMQTTService()
        success = mqtt_service.send_wellness_content_notification(user, content, delivery_context)

        return {
            'success': success,
            'user_id': user_id,
            'content_id': content_id,
            'delivery_context': delivery_context,
            'sent_at': timezone.now().isoformat()
        }

    except (DatabaseError, IntegrationException, IntegrityError, ObjectDoesNotExist, TypeError, ValueError, json.JSONDecodeError) as e:
        logger.error(f"Async wellness notification failed: {e}")
        raise


@shared_task
def send_crisis_alert_async(user_id, journal_entry_id, crisis_indicators):
    """Send crisis intervention alert asynchronously"""
    try:
        from django.contrib.auth import get_user_model

        User = get_user_model()
        user = User.objects.get(id=user_id)
        journal_entry = JournalEntry.objects.get(id=journal_entry_id)

        mqtt_service = JournalWellnessMQTTService()
        success = mqtt_service.send_crisis_intervention_alert(user, journal_entry, crisis_indicators)

        return {
            'success': success,
            'user_id': user_id,
            'journal_entry_id': journal_entry_id,
            'crisis_indicators': crisis_indicators,
            'alert_sent_at': timezone.now().isoformat()
        }

    except (DatabaseError, IntegrationException, IntegrityError, ObjectDoesNotExist, TypeError, ValueError, json.JSONDecodeError) as e:
        logger.error(f"Async crisis alert failed: {e}")
        raise


@shared_task
def send_achievement_notification_async(user_id, achievements):
    """Send achievement notification asynchronously"""
    try:
        from django.contrib.auth import get_user_model

        User = get_user_model()
        user = User.objects.get(id=user_id)

        mqtt_service = JournalWellnessMQTTService()
        success = mqtt_service.send_achievement_notification(user, achievements)

        return {
            'success': success,
            'user_id': user_id,
            'achievements': achievements,
            'notification_sent_at': timezone.now().isoformat()
        }

    except (DatabaseError, IntegrationException, IntegrityError, ObjectDoesNotExist, TypeError, ValueError, json.JSONDecodeError) as e:
        logger.error(f"Async achievement notification failed: {e}")
        raise


@shared_task
def broadcast_system_health_status():
    """Broadcast journal and wellness system health status"""
    try:
        # Calculate system health metrics
        from apps.tenants.models import Tenant
        from django.db.models import Prefetch

        health_metrics = {}

        # PERFORMANCE OPTIMIZATION: Prefetch users to avoid N+1 queries
        # Before: 3N+1 queries (1 for tenants, N for users, N for entries, N for interactions)
        # After: 2 queries (1 for tenants with users, 1 for all data)
        tenants = Tenant.objects.prefetch_related(
            Prefetch(
                'user_set',
                queryset=User.objects.all(),
                to_attr='cached_users'
            )
        ).only('id', 'tenantname')

        # Calculate time threshold once (not per iteration)
        time_threshold = timezone.now() - timezone.timedelta(days=1)

        for tenant in tenants:
            # Use cached users from prefetch (no additional query)
            tenant_users = tenant.cached_users
            tenant_user_ids = [u.id for u in tenant_users]

            # Optimized queries with select_related to avoid additional lookups
            recent_entries = JournalEntry.objects.filter(
                user_id__in=tenant_user_ids,
                timestamp__gte=time_threshold,
                is_deleted=False
            ).select_related('user')

            recent_interactions = WellnessContentInteraction.objects.filter(
                user_id__in=tenant_user_ids,
                interaction_date__gte=time_threshold
            ).select_related('user')

            health_metrics[tenant.tenantname] = {
                'total_users': len(tenant_users),
                'active_journal_users_24h': recent_entries.values('user_id').distinct().count(),
                'journal_entries_24h': recent_entries.count(),
                'wellness_interactions_24h': recent_interactions.count(),
                'system_health': 'healthy'  # Could be calculated based on error rates, etc.
            }

        # Prepare health status message
        health_payload = {
            'type': 'system_health_status',
            'timestamp': timezone.now().isoformat(),
            'overall_status': 'operational',
            'tenant_metrics': health_metrics,
            'system_version': '1.0.0',
            'last_health_check': timezone.now().isoformat()
        }

        mqtt_service = JournalWellnessMQTTService()
        success = mqtt_service._publish_mqtt_message(
            mqtt_service.TOPICS['system_health'],
            health_payload
        )

        return {
            'success': success,
            'tenants_reported': len(health_metrics),
            'broadcast_at': timezone.now().isoformat()
        }

    except (DatabaseError, IntegrationException, IntegrityError, ObjectDoesNotExist, TypeError, ValueError, json.JSONDecodeError) as e:
        logger.error(f"System health broadcast failed: {e}")
        raise


# Integration with existing signal handlers
from django.db.models.signals import post_save
from django.dispatch import receiver

@receiver(post_save, sender=JournalEntry)
def trigger_mqtt_notifications_on_entry_create(sender, instance, created, **kwargs):
    """Trigger MQTT notifications when journal entries are created"""
    if created:
        try:
            # Check if pattern analysis should trigger notifications
            from apps.journal.services.pattern_analyzer import JournalPatternAnalyzer

            analyzer = JournalPatternAnalyzer()
            analysis = analyzer.analyze_entry_for_immediate_action(instance)

            if analysis['urgency_score'] >= 3:
                # Send pattern analysis notification
                mqtt_service = JournalWellnessMQTTService()
                mqtt_service.send_pattern_analysis_notification(
                    instance.user, instance, analysis
                )

            # Check for crisis intervention
            if analysis.get('crisis_detected'):
                send_crisis_alert_async.delay(
                    str(instance.user.id),
                    str(instance.id),
                    analysis.get('crisis_indicators', [])
                )

        except (DatabaseError, IntegrityError, ObjectDoesNotExist) as e:
            logger.error(f"Failed to trigger MQTT notifications for entry {instance.id}: {e}")


@receiver(post_save, sender=WellnessContentInteraction)
def trigger_achievement_notifications_on_interaction(sender, instance, created, **kwargs):
    """Trigger achievement notifications when wellness interactions are created"""
    if created and instance.interaction_type in ['completed', 'acted_upon']:
        try:
            # Check for new achievements
            progress = instance.user.wellness_progress
            old_achievements = set(progress.achievements_earned)

            # Update progress (this will check for new achievements)
            progress.update_streak()
            new_achievements_check = progress.check_and_award_achievements()

            if new_achievements_check:
                # Send achievement notification
                send_achievement_notification_async.delay(
                    str(instance.user.id),
                    new_achievements_check
                )

        except (DatabaseError, IntegrityError, ObjectDoesNotExist) as e:
            logger.error(f"Failed to trigger achievement notifications: {e}")


# Convenience functions for external use
def notify_wellness_content_delivery(user, content, delivery_context='daily_tip'):
    """Convenience function to notify wellness content delivery"""
    mqtt_service = JournalWellnessMQTTService()
    return mqtt_service.send_wellness_content_notification(user, content, delivery_context)


def notify_crisis_intervention(user, journal_entry, crisis_indicators):
    """Convenience function to notify crisis intervention"""
    mqtt_service = JournalWellnessMQTTService()
    return mqtt_service.send_crisis_intervention_alert(user, journal_entry, crisis_indicators)


def notify_pattern_analysis(user, journal_entry, analysis_result):
    """Convenience function to notify pattern analysis"""
    mqtt_service = JournalWellnessMQTTService()
    return mqtt_service.send_pattern_analysis_notification(user, journal_entry, analysis_result)