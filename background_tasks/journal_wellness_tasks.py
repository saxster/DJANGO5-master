"""
Background Tasks for Journal & Wellness System

Comprehensive background task system using existing PostgreSQL Task Queue infrastructure.
Provides automated analytics updates, wellness content scheduling, and maintenance operations.

Integration with existing Celery/PostgreSQL task queue system for:
- Real-time analytics computation and caching
- Daily wellness content scheduling and delivery
- Crisis intervention alert processing
- Data retention and cleanup operations
- Performance optimization and maintenance
"""

from celery import shared_task
from django.utils import timezone
from django.db import transaction
from django.contrib.auth import get_user_model
from django.db.models import Count, Avg, Q
from datetime import timedelta, datetime
import logging
import json

from apps.journal.models import JournalEntry, JournalPrivacySettings
from apps.wellness.models import WellnessContent, WellnessUserProgress, WellnessContentInteraction
from apps.journal.ml.analytics_engine import WellbeingAnalyticsEngine
from apps.journal.services.pattern_analyzer import JournalPatternAnalyzer
from apps.wellness.services.content_delivery import WellnessTipSelector, UserProfileBuilder
from apps.journal.privacy import JournalPrivacyManager

User = get_user_model()
logger = logging.getLogger('background_tasks')


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def update_user_analytics(self, user_id, trigger_entry_id=None):
    """
    Update user's wellbeing analytics in background

    Args:
        user_id: User to update analytics for
        trigger_entry_id: Journal entry that triggered the update (optional)

    Returns:
        dict: Analytics update results
    """

    logger.info(f"Updating analytics for user {user_id} (triggered by entry {trigger_entry_id})")

    try:
        user = User.objects.get(id=user_id)

        # Check user consent for analytics processing
        try:
            privacy_settings = user.journal_privacy_settings
            if not privacy_settings.analytics_consent:
                logger.info(f"Skipping analytics update - user {user_id} has not consented")
                return {
                    'success': True,
                    'skipped': True,
                    'reason': 'no_analytics_consent'
                }
        except JournalPrivacySettings.DoesNotExist:
            logger.warning(f"No privacy settings for user {user_id} - skipping analytics")
            return {
                'success': True,
                'skipped': True,
                'reason': 'no_privacy_settings'
            }

        # Get user's journal entries for analysis (last 90 days)
        journal_entries = list(JournalEntry.objects.filter(
            user=user,
            timestamp__gte=timezone.now() - timedelta(days=90),
            is_deleted=False
        ).order_by('timestamp'))

        if len(journal_entries) < 3:
            logger.debug(f"Insufficient data for analytics - user {user_id} has {len(journal_entries)} entries")
            return {
                'success': True,
                'skipped': True,
                'reason': 'insufficient_data',
                'entry_count': len(journal_entries)
            }

        # Generate comprehensive analytics
        analytics_engine = WellbeingAnalyticsEngine()

        # Calculate all analytics components
        mood_trends = analytics_engine.calculate_mood_trends(journal_entries)
        stress_analysis = analytics_engine.calculate_stress_trends(journal_entries)
        energy_trends = analytics_engine.calculate_energy_trends(journal_entries)
        gratitude_insights = analytics_engine.calculate_gratitude_insights(journal_entries)
        achievement_insights = analytics_engine.calculate_achievement_insights(journal_entries)
        pattern_insights = analytics_engine.calculate_pattern_insights(journal_entries)

        # Generate recommendations
        recommendations = analytics_engine.generate_recommendations(
            mood_trends, stress_analysis, energy_trends, journal_entries
        )

        # Calculate overall wellbeing score
        wellbeing_score = analytics_engine.calculate_overall_wellbeing_score(
            mood_trends, stress_analysis, energy_trends, journal_entries
        )

        # Cache analytics results for quick API access
        analytics_cache_key = f"user_analytics_{user_id}"
        analytics_data = {
            'wellbeing_trends': {
                'mood_analysis': mood_trends,
                'stress_analysis': stress_analysis,
                'energy_analysis': energy_trends,
                'gratitude_insights': gratitude_insights,
                'achievement_insights': achievement_insights
            },
            'behavioral_patterns': pattern_insights,
            'recommendations': recommendations,
            'overall_wellbeing_score': wellbeing_score,
            'analysis_metadata': {
                'analysis_date': timezone.now().isoformat(),
                'data_points_analyzed': len(journal_entries),
                'algorithm_version': '2.1.0',
                'trigger_entry_id': trigger_entry_id
            }
        }

        # TODO: Cache analytics data using Django cache framework
        # cache.set(analytics_cache_key, analytics_data, timeout=3600)  # 1 hour cache

        logger.info(f"Analytics updated for user {user_id}: wellbeing_score={wellbeing_score['overall_score']}")

        # Schedule wellness content delivery if patterns indicate need
        if wellbeing_score['overall_score'] < 6.0:
            schedule_wellness_content_delivery.delay(user_id, 'low_wellbeing_score')

        return {
            'success': True,
            'user_id': user_id,
            'wellbeing_score': wellbeing_score['overall_score'],
            'entry_count': len(journal_entries),
            'recommendations_count': len(recommendations),
            'updated_at': timezone.now().isoformat()
        }

    except User.DoesNotExist:
        logger.error(f"User {user_id} not found for analytics update")
        return {
            'success': False,
            'error': 'user_not_found',
            'user_id': user_id
        }

    except (ConnectionError, DatabaseError, IntegrationException, IntegrityError, ObjectDoesNotExist, ValueError) as e:
        logger.error(f"Analytics update failed for user {user_id}: {e}")
        # Retry with exponential backoff
        raise self.retry(exc=e, countdown=60 * (2 ** self.request.retries))


@shared_task(bind=True, max_retries=2)
def schedule_wellness_content_delivery(self, user_id, trigger_reason='daily_schedule'):
    """
    Schedule personalized wellness content delivery

    Args:
        user_id: User to schedule content for
        trigger_reason: Reason for scheduling ('daily_schedule', 'low_wellbeing_score', 'crisis_detected')

    Returns:
        dict: Scheduling results
    """

    logger.info(f"Scheduling wellness content for user {user_id} (reason: {trigger_reason})")

    try:
        user = User.objects.get(id=user_id)

        # Get or create user progress
        progress, created = WellnessUserProgress.objects.get_or_create(
            user=user,
            defaults={'tenant': user.tenant}
        )

        # Check if user has enabled contextual delivery
        if not progress.contextual_delivery_enabled and trigger_reason != 'crisis_detected':
            logger.debug(f"Contextual delivery disabled for user {user_id}")
            return {
                'success': True,
                'skipped': True,
                'reason': 'contextual_delivery_disabled'
            }

        # Check daily tip delivery timing
        if trigger_reason == 'daily_schedule':
            # Check if user already received daily tip today
            today_interactions = WellnessContentInteraction.objects.filter(
                user=user,
                delivery_context='daily_tip',
                interaction_date__date=timezone.now().date()
            )

            if today_interactions.exists():
                logger.debug(f"Daily tip already delivered to user {user_id} today")
                return {
                    'success': True,
                    'skipped': True,
                    'reason': 'daily_tip_already_delivered'
                }

        # Analyze user patterns for personalization
        recent_entries = JournalEntry.objects.filter(
            user=user,
            timestamp__gte=timezone.now() - timedelta(days=7),
            is_deleted=False
        ).order_by('-timestamp')

        user_patterns = {}
        if recent_entries.exists():
            # Calculate recent patterns
            mood_entries = recent_entries.exclude(mood_rating__isnull=True)
            stress_entries = recent_entries.exclude(stress_level__isnull=True)
            energy_entries = recent_entries.exclude(energy_level__isnull=True)

            if mood_entries.exists():
                user_patterns['current_mood'] = mood_entries.first().mood_rating
                user_patterns['avg_mood'] = mood_entries.aggregate(avg=Avg('mood_rating'))['avg']

            if stress_entries.exists():
                user_patterns['current_stress'] = stress_entries.first().stress_level
                user_patterns['avg_stress'] = stress_entries.aggregate(avg=Avg('stress_level'))['avg']

            if energy_entries.exists():
                user_patterns['current_energy'] = energy_entries.first().energy_level

        # Select appropriate content
        tip_selector = WelnessTipSelector()
        selected_content = tip_selector.select_personalized_tip(
            user, user_patterns, []  # No previously seen content for scheduled delivery
        )

        if selected_content:
            # Create interaction record for scheduled delivery
            interaction = WellnessContentInteraction.objects.create(
                user=user,
                content=selected_content,
                interaction_type='viewed',
                delivery_context='daily_tip' if trigger_reason == 'daily_schedule' else 'pattern_triggered',
                user_mood_at_delivery=user_patterns.get('current_mood'),
                user_stress_at_delivery=user_patterns.get('current_stress'),
                metadata={
                    'scheduled_delivery': True,
                    'trigger_reason': trigger_reason,
                    'selection_reason': tip_selector.last_selection_reason,
                    'predicted_effectiveness': tip_selector.predicted_effectiveness
                }
            )

            logger.info(f"Scheduled wellness content '{selected_content.title}' for user {user_id}")

            # TODO: Send push notification or MQTT message for content delivery
            # notify_user_wellness_content.delay(user_id, selected_content.id, interaction.id)

            return {
                'success': True,
                'user_id': user_id,
                'content_scheduled': {
                    'content_id': str(selected_content.id),
                    'content_title': selected_content.title,
                    'delivery_context': interaction.delivery_context,
                    'predicted_effectiveness': tip_selector.predicted_effectiveness
                },
                'interaction_id': str(interaction.id),
                'scheduled_at': timezone.now().isoformat()
            }

        else:
            logger.warning(f"No suitable wellness content found for user {user_id}")
            return {
                'success': True,
                'skipped': True,
                'reason': 'no_suitable_content',
                'user_patterns': user_patterns
            }

    except User.DoesNotExist:
        logger.error(f"User {user_id} not found for wellness content scheduling")
        return {
            'success': False,
            'error': 'user_not_found',
            'user_id': user_id
        }

    except (ConnectionError, DatabaseError, IntegrationException, IntegrityError, ObjectDoesNotExist, ValueError) as e:
        logger.error(f"Wellness content scheduling failed for user {user_id}: {e}")
        # Retry once with delay
        raise self.retry(exc=e, countdown=300, max_retries=2)


@shared_task(bind=True)
def check_wellness_milestones(self, user_id):
    """
    Check and award wellness milestones and achievements

    Args:
        user_id: User to check milestones for

    Returns:
        dict: Milestone check results
    """

    logger.debug(f"Checking wellness milestones for user {user_id}")

    try:
        user = User.objects.get(id=user_id)

        # Get user's wellness progress
        try:
            progress = user.wellness_progress
        except WellnessUserProgress.DoesNotExist:
            logger.info(f"No wellness progress found for user {user_id}")
            return {
                'success': True,
                'skipped': True,
                'reason': 'no_wellness_progress'
            }

        # Check for new achievements
        old_achievements = set(progress.achievements_earned)
        new_achievements = progress.check_and_award_achievements()

        if new_achievements:
            # Update progress with new achievements
            progress.save()

            logger.info(f"New achievements for user {user_id}: {new_achievements}")

            # Send achievement notifications if enabled
            if progress.milestone_alerts_enabled:
                send_milestone_notification.delay(user_id, new_achievements)

            # Schedule celebratory wellness content
            schedule_wellness_content_delivery.delay(user_id, 'milestone_achievement')

            return {
                'success': True,
                'user_id': user_id,
                'new_achievements': new_achievements,
                'total_achievements': len(progress.achievements_earned),
                'notification_sent': progress.milestone_alerts_enabled
            }

        else:
            return {
                'success': True,
                'user_id': user_id,
                'new_achievements': [],
                'message': 'No new achievements'
            }

    except User.DoesNotExist:
        logger.error(f"User {user_id} not found for milestone check")
        return {
            'success': False,
            'error': 'user_not_found'
        }

    except (ConnectionError, DatabaseError, IntegrationException, IntegrityError, ObjectDoesNotExist, ValueError) as e:
        logger.error(f"Milestone check failed for user {user_id}: {e}")
        raise


@shared_task(bind=True)
def process_crisis_intervention(self, user_id, journal_entry_id, crisis_indicators):
    """
    Process crisis intervention workflow

    Args:
        user_id: User in crisis
        journal_entry_id: Journal entry that triggered crisis detection
        crisis_indicators: List of detected crisis indicators

    Returns:
        dict: Crisis intervention results
    """

    logger.critical(f"PROCESSING CRISIS INTERVENTION: User {user_id}, Entry {journal_entry_id}")

    try:
        user = User.objects.get(id=user_id)
        journal_entry = JournalEntry.objects.get(id=journal_entry_id)

        # Verify user has consented to crisis intervention
        try:
            privacy_settings = user.journal_privacy_settings
            if not privacy_settings.crisis_intervention_consent:
                logger.warning(f"Crisis detected but user {user_id} has not consented to intervention")
                return {
                    'success': True,
                    'skipped': True,
                    'reason': 'no_crisis_intervention_consent'
                }
        except JournalPrivacySettings.DoesNotExist:
            logger.error(f"No privacy settings for user {user_id} in crisis")
            return {
                'success': False,
                'error': 'no_privacy_settings'
            }

        # Get immediate crisis support content
        crisis_content = WellnessContent.objects.filter(
            tenant=user.tenant,
            is_active=True,
            delivery_context__in=['mood_support', 'stress_response'],
            evidence_level__in=['who_cdc', 'peer_reviewed']  # Only high-evidence for crisis
        ).order_by('-priority_score')[:3]

        # Deliver crisis content immediately
        crisis_interactions = []
        for content in crisis_content:
            interaction = WellnessContentInteraction.objects.create(
                user=user,
                content=content,
                interaction_type='viewed',
                delivery_context='mood_support',
                trigger_journal_entry=journal_entry,
                user_mood_at_delivery=journal_entry.mood_rating,
                user_stress_at_delivery=journal_entry.stress_level,
                metadata={
                    'crisis_intervention': True,
                    'crisis_indicators': crisis_indicators,
                    'intervention_timestamp': timezone.now().isoformat()
                }
            )
            crisis_interactions.append(interaction)

        # TODO: Alert crisis response team if configured
        # alert_crisis_response_team.delay(user_id, journal_entry_id, crisis_indicators)

        # Schedule follow-up content for next 24-48 hours
        schedule_crisis_followup_content.delay(user_id, journal_entry_id)

        logger.critical(f"Crisis intervention completed for user {user_id}: {len(crisis_content)} content items delivered")

        return {
            'success': True,
            'user_id': user_id,
            'journal_entry_id': journal_entry_id,
            'crisis_indicators': crisis_indicators,
            'content_delivered': len(crisis_content),
            'interactions_created': len(crisis_interactions),
            'intervention_timestamp': timezone.now().isoformat()
        }

    except (User.DoesNotExist, JournalEntry.DoesNotExist) as e:
        logger.error(f"Crisis intervention failed - object not found: {e}")
        return {
            'success': False,
            'error': 'object_not_found',
            'details': str(e)
        }

    except (ConnectionError, DatabaseError, IntegrationException, IntegrityError, ObjectDoesNotExist, ValueError) as e:
        logger.error(f"Crisis intervention processing failed: {e}")
        raise


@shared_task(bind=True)
def schedule_crisis_followup_content(self, user_id, journal_entry_id):
    """Schedule follow-up wellness content for crisis situations"""

    logger.info(f"Scheduling crisis follow-up content for user {user_id}")

    try:
        user = User.objects.get(id=user_id)

        # Get mental health and stress management content for follow-up
        followup_content = WellnessContent.objects.filter(
            tenant=user.tenant,
            is_active=True,
            category__in=['mental_health', 'stress_management'],
            content_level__in=['short_read', 'deep_dive'],
            evidence_level__in=['who_cdc', 'peer_reviewed', 'professional']
        ).order_by('-priority_score')[:5]

        # Schedule content delivery over next 48 hours
        scheduled_count = 0
        for i, content in enumerate(followup_content):
            # Schedule at intervals: 2 hours, 8 hours, 24 hours, 48 hours
            delivery_delays = [2, 8, 24, 48]
            if i < len(delivery_delays):
                schedule_specific_content_delivery.apply_async(
                    args=[user_id, str(content.id), 'crisis_followup'],
                    countdown=delivery_delays[i] * 3600  # Convert hours to seconds
                )
                scheduled_count += 1

        logger.info(f"Scheduled {scheduled_count} follow-up content items for user {user_id}")

        return {
            'success': True,
            'user_id': user_id,
            'followup_content_scheduled': scheduled_count
        }

    except (ConnectionError, DatabaseError, IntegrationException, IntegrityError, ObjectDoesNotExist, ValueError) as e:
        logger.error(f"Crisis follow-up scheduling failed: {e}")
        raise


@shared_task(bind=True)
def schedule_specific_content_delivery(self, user_id, content_id, delivery_context):
    """Deliver specific wellness content to user"""

    try:
        user = User.objects.get(id=user_id)
        content = WellnessContent.objects.get(id=content_id)

        # Create interaction for scheduled delivery
        interaction = WellnessContentInteraction.objects.create(
            user=user,
            content=content,
            interaction_type='viewed',
            delivery_context=delivery_context,
            metadata={
                'scheduled_delivery': True,
                'delivery_timestamp': timezone.now().isoformat()
            }
        )

        logger.info(f"Delivered scheduled content '{content.title}' to user {user_id}")

        return {
            'success': True,
            'content_delivered': content.title,
            'interaction_id': str(interaction.id)
        }

    except (ConnectionError, DatabaseError, IntegrationException, IntegrityError, ObjectDoesNotExist, ValueError) as e:
        logger.error(f"Scheduled content delivery failed: {e}")
        raise


@shared_task(bind=True)
def send_milestone_notification(self, user_id, achievements):
    """Send notification for wellness milestones"""

    logger.info(f"Sending milestone notification to user {user_id}: {achievements}")

    try:
        user = User.objects.get(id=user_id)

        # TODO: Integrate with MQTT notification system
        # notification_data = {
        #     'type': 'wellness_milestone',
        #     'user_id': user_id,
        #     'achievements': achievements,
        #     'message': f'Congratulations! You earned: {", ".join(achievements)}'
        # }
        # send_mqtt_notification.delay(user_id, notification_data)

        # For now, log the notification
        logger.info(f"MILESTONE NOTIFICATION: User {user.peoplename} earned {achievements}")

        return {
            'success': True,
            'user_id': user_id,
            'achievements': achievements,
            'notification_sent': True
        }

    except (ConnectionError, DatabaseError, IntegrationException, IntegrityError, ObjectDoesNotExist, ValueError) as e:
        logger.error(f"Milestone notification failed: {e}")
        raise


@shared_task
def daily_wellness_content_scheduling():
    """
    Daily task to schedule wellness content for all active users

    Runs daily to:
    - Send daily wellness tips to users who have them enabled
    - Check for users who need wellness interventions
    - Update user engagement streaks
    - Clean up expired content interactions
    """

    logger.info("Running daily wellness content scheduling")

    try:
        # Get all users with daily tips enabled
        users_with_daily_tips = WellnessUserProgress.objects.filter(
            daily_tip_enabled=True,
            user__isverified=True  # Only verified/active users
        ).select_related('user')

        scheduled_count = 0
        skipped_count = 0

        for progress in users_with_daily_tips:
            try:
                # Check if user already received content today
                today_tips = WellnessContentInteraction.objects.filter(
                    user=progress.user,
                    delivery_context='daily_tip',
                    interaction_date__date=timezone.now().date()
                )

                if not today_tips.exists():
                    # Schedule daily tip
                    schedule_wellness_content_delivery.delay(
                        progress.user.id, 'daily_schedule'
                    )
                    scheduled_count += 1
                else:
                    skipped_count += 1

            except (DatabaseError, IntegrityError, ObjectDoesNotExist) as e:
                logger.error(f"Failed to schedule daily tip for user {progress.user.id}: {e}")

        # Update user streaks
        update_result = update_all_user_streaks.delay()

        # Clean up old interactions
        cleanup_result = cleanup_old_wellness_interactions.delay()

        logger.info(f"Daily scheduling complete: {scheduled_count} scheduled, {skipped_count} skipped")

        return {
            'success': True,
            'users_scheduled': scheduled_count,
            'users_skipped': skipped_count,
            'total_users_checked': users_with_daily_tips.count(),
            'streak_update_task': update_result.id,
            'cleanup_task': cleanup_result.id,
            'scheduled_at': timezone.now().isoformat()
        }

    except (ConnectionError, DatabaseError, IntegrationException, IntegrityError, ObjectDoesNotExist, ValueError) as e:
        logger.error(f"Daily wellness scheduling failed: {e}")
        raise


@shared_task
def update_all_user_streaks():
    """Update wellness engagement streaks for all users"""

    logger.info("Updating wellness engagement streaks for all users")

    try:
        # Get all users with wellness progress
        all_progress = WellnessUserProgress.objects.select_related('user')

        updated_count = 0
        broken_streaks = 0

        for progress in all_progress:
            try:
                old_streak = progress.current_streak

                # Update streak based on recent activity
                progress.update_streak()

                if progress.current_streak != old_streak:
                    progress.save()
                    updated_count += 1

                    if progress.current_streak == 0 and old_streak > 0:
                        broken_streaks += 1
                        logger.debug(f"Streak broken for user {progress.user.id} (was {old_streak} days)")

            except (DatabaseError, IntegrityError) as e:
                logger.error(f"Failed to update streak for user {progress.user.id}: {e}")

        logger.info(f"Streak update complete: {updated_count} updated, {broken_streaks} broken")

        return {
            'success': True,
            'users_updated': updated_count,
            'streaks_broken': broken_streaks,
            'total_users': all_progress.count(),
            'updated_at': timezone.now().isoformat()
        }

    except (ConnectionError, DatabaseError, IntegrationException, IntegrityError, ObjectDoesNotExist, ValueError) as e:
        logger.error(f"Streak update failed: {e}")
        raise


@shared_task
def cleanup_old_wellness_interactions():
    """Clean up old wellness interaction records for performance"""

    logger.info("Cleaning up old wellness interactions")

    try:
        # Keep interactions for 1 year, delete older ones
        cutoff_date = timezone.now() - timedelta(days=365)

        old_interactions = WellnessContentInteraction.objects.filter(
            interaction_date__lt=cutoff_date
        )

        deleted_count = old_interactions.count()
        old_interactions.delete()

        logger.info(f"Cleaned up {deleted_count} old wellness interactions")

        return {
            'success': True,
            'deleted_count': deleted_count,
            'cutoff_date': cutoff_date.isoformat()
        }

    except (ConnectionError, DatabaseError, IntegrationException, IntegrityError, ObjectDoesNotExist, ValueError) as e:
        logger.error(f"Wellness interaction cleanup failed: {e}")
        raise


@shared_task
def enforce_data_retention_policies():
    """
    Enforce data retention policies for all users

    Runs daily to:
    - Apply user-specific retention policies
    - Auto-delete expired entries
    - Anonymize data per retention settings
    - Generate retention compliance reports
    """

    logger.info("Enforcing data retention policies")

    try:
        privacy_manager = JournalPrivacyManager()

        # Get users with auto-delete enabled
        users_with_retention = User.objects.filter(
            journal_privacy_settings__auto_delete_enabled=True
        )

        total_deleted = 0
        total_anonymized = 0

        for user in users_with_retention:
            try:
                retention_result = privacy_manager.enforce_data_retention_policy(user)
                total_deleted += retention_result['entries_deleted']
                total_anonymized += retention_result['entries_anonymized']

            except (DatabaseError, IntegrityError, ObjectDoesNotExist) as e:
                logger.error(f"Retention enforcement failed for user {user.id}: {e}")

        logger.info(f"Data retention enforcement complete: {total_deleted} deleted, {total_anonymized} anonymized")

        return {
            'success': True,
            'users_processed': users_with_retention.count(),
            'entries_deleted': total_deleted,
            'entries_anonymized': total_anonymized,
            'processed_at': timezone.now().isoformat()
        }

    except (ConnectionError, DatabaseError, IntegrationException, IntegrityError, ObjectDoesNotExist, ValueError) as e:
        logger.error(f"Data retention enforcement failed: {e}")
        raise


@shared_task(bind=True, max_retries=3)
def update_content_effectiveness_metrics(self, content_id):
    """
    Update effectiveness metrics for wellness content

    Args:
        content_id: Wellness content to update metrics for

    Returns:
        dict: Effectiveness update results
    """

    logger.debug(f"Updating effectiveness metrics for content {content_id}")

    try:
        content = WellnessContent.objects.get(id=content_id)

        # Get all interactions for this content
        interactions = WellnessContentInteraction.objects.filter(content=content)

        if not interactions.exists():
            return {
                'success': True,
                'skipped': True,
                'reason': 'no_interactions'
            }

        # Calculate effectiveness metrics
        total_interactions = interactions.count()
        completed_interactions = interactions.filter(interaction_type='completed').count()
        positive_interactions = interactions.filter(
            interaction_type__in=['completed', 'bookmarked', 'acted_upon', 'requested_more']
        ).count()
        dismissed_interactions = interactions.filter(interaction_type='dismissed').count()

        # Calculate rates
        completion_rate = completed_interactions / total_interactions if total_interactions > 0 else 0
        effectiveness_rate = positive_interactions / total_interactions if total_interactions > 0 else 0
        dismissal_rate = dismissed_interactions / total_interactions if total_interactions > 0 else 0

        # Calculate average engagement score
        avg_engagement = interactions.aggregate(avg=Avg('engagement_score'))['avg'] or 0

        # Calculate average rating
        rated_interactions = interactions.exclude(user_rating__isnull=True)
        avg_rating = rated_interactions.aggregate(avg=Avg('user_rating'))['avg'] if rated_interactions.exists() else None

        # Update content priority based on effectiveness
        effectiveness_score = (effectiveness_rate + completion_rate) / 2

        # Adjust priority score based on effectiveness
        if effectiveness_score > 0.8:
            # High effectiveness - boost priority
            new_priority = min(100, content.priority_score + 5)
        elif effectiveness_score < 0.4:
            # Low effectiveness - reduce priority
            new_priority = max(1, content.priority_score - 5)
        else:
            new_priority = content.priority_score

        content.priority_score = new_priority
        content.save()

        logger.debug(f"Updated content {content_id} effectiveness: {effectiveness_score:.2f}, priority: {new_priority}")

        return {
            'success': True,
            'content_id': content_id,
            'content_title': content.title,
            'metrics': {
                'total_interactions': total_interactions,
                'completion_rate': round(completion_rate, 3),
                'effectiveness_rate': round(effectiveness_rate, 3),
                'dismissal_rate': round(dismissal_rate, 3),
                'avg_engagement_score': round(avg_engagement, 2),
                'avg_rating': round(avg_rating, 2) if avg_rating else None
            },
            'priority_updated': {
                'old_priority': content.priority_score,
                'new_priority': new_priority
            },
            'updated_at': timezone.now().isoformat()
        }

    except WellnessContent.DoesNotExist:
        logger.error(f"Wellness content {content_id} not found")
        return {
            'success': False,
            'error': 'content_not_found'
        }

    except (ConnectionError, DatabaseError, IntegrationException, IntegrityError, ObjectDoesNotExist, ValueError) as e:
        logger.error(f"Content effectiveness update failed for {content_id}: {e}")
        raise self.retry(exc=e, countdown=300)


@shared_task
def generate_wellness_analytics_reports():
    """
    Generate comprehensive wellness analytics reports

    Runs weekly to:
    - Generate tenant-wide wellness reports
    - Calculate content effectiveness trends
    - Identify wellness program ROI metrics
    - Generate compliance and usage reports
    """

    logger.info("Generating wellness analytics reports")

    try:
        reports_generated = []

        # Generate reports for each tenant
        from apps.tenants.models import Tenant
        for tenant in Tenant.objects.all():
            try:
                report = generate_tenant_wellness_report(tenant)
                reports_generated.append(report)

            except (ValueError, TypeError) as e:
                logger.error(f"Failed to generate report for tenant {tenant.id}: {e}")

        # Generate system-wide effectiveness report
        effectiveness_report = generate_content_effectiveness_report()
        reports_generated.append(effectiveness_report)

        logger.info(f"Generated {len(reports_generated)} wellness analytics reports")

        return {
            'success': True,
            'reports_generated': len(reports_generated),
            'report_details': reports_generated,
            'generated_at': timezone.now().isoformat()
        }

    except (ConnectionError, DatabaseError, IntegrationException, IntegrityError, ObjectDoesNotExist, ValueError) as e:
        logger.error(f"Wellness analytics report generation failed: {e}")
        raise


def generate_tenant_wellness_report(tenant):
    """Generate wellness report for specific tenant"""
    logger.info(f"Generating wellness report for tenant {tenant.tenantname}")

    # Get tenant users
    tenant_users = User.objects.filter(tenant=tenant)

    # Get wellness metrics
    total_users = tenant_users.count()
    users_with_progress = WellnessUserProgress.objects.filter(user__in=tenant_users).count()

    # Get recent wellness interactions
    recent_interactions = WellnessContentInteraction.objects.filter(
        user__in=tenant_users,
        interaction_date__gte=timezone.now() - timedelta(days=30)
    )

    # Calculate engagement metrics
    active_users = recent_interactions.values('user').distinct().count()
    total_interactions = recent_interactions.count()
    avg_engagement = recent_interactions.aggregate(avg=Avg('engagement_score'))['avg'] or 0

    # Content category analysis
    category_stats = recent_interactions.values('content__category').annotate(
        count=Count('id'),
        avg_rating=Avg('user_rating')
    )

    report = {
        'tenant_name': tenant.tenantname,
        'reporting_period': '30_days',
        'user_metrics': {
            'total_users': total_users,
            'users_with_wellness_progress': users_with_progress,
            'active_users_last_30_days': active_users,
            'engagement_rate': round(active_users / total_users, 3) if total_users > 0 else 0
        },
        'interaction_metrics': {
            'total_interactions': total_interactions,
            'avg_engagement_score': round(avg_engagement, 2),
            'interactions_per_active_user': round(total_interactions / active_users, 1) if active_users > 0 else 0
        },
        'category_performance': list(category_stats),
        'generated_at': timezone.now().isoformat()
    }

    return report


def generate_content_effectiveness_report():
    """Generate system-wide content effectiveness report"""
    logger.info("Generating content effectiveness report")

    # Get all active content with interactions
    content_with_interactions = WellnessContent.objects.filter(
        is_active=True,
        interactions__isnull=False
    ).distinct()

    effectiveness_data = []

    for content in content_with_interactions:
        interactions = content.interactions.all()
        total = interactions.count()

        if total > 0:
            completed = interactions.filter(interaction_type='completed').count()
            positive = interactions.filter(
                interaction_type__in=['completed', 'bookmarked', 'acted_upon']
            ).count()

            effectiveness_data.append({
                'content_id': str(content.id),
                'title': content.title,
                'category': content.category,
                'evidence_level': content.evidence_level,
                'total_interactions': total,
                'completion_rate': round(completed / total, 3),
                'effectiveness_rate': round(positive / total, 3),
                'priority_score': content.priority_score
            })

    # Sort by effectiveness
    effectiveness_data.sort(key=lambda x: x['effectiveness_rate'], reverse=True)

    return {
        'report_type': 'content_effectiveness',
        'top_performing_content': effectiveness_data[:10],
        'underperforming_content': [c for c in effectiveness_data if c['effectiveness_rate'] < 0.3],
        'total_content_analyzed': len(effectiveness_data),
        'generated_at': timezone.now().isoformat()
    }


# Periodic maintenance tasks

@shared_task
def maintain_journal_search_index():
    """Maintain Elasticsearch search indexes"""
    logger.info("Maintaining journal search indexes")

    try:
        from .search import JournalElasticsearchService
        es_service = JournalElasticsearchService()

        # Reindex entries with outdated search data
        outdated_entries = JournalEntry.objects.filter(
            updated_at__gte=timezone.now() - timedelta(hours=24),
            is_deleted=False
        )

        reindexed_count = 0
        for entry in outdated_entries:
            if es_service.index_journal_entry(entry):
                reindexed_count += 1

        return {
            'success': True,
            'reindexed_count': reindexed_count,
            'maintained_at': timezone.now().isoformat()
        }

    except (ConnectionError, DatabaseError, IntegrationException, IntegrityError, ObjectDoesNotExist, ValueError) as e:
        logger.error(f"Search index maintenance failed: {e}")
        raise


@shared_task
def weekly_wellness_summary():
    """Generate weekly wellness summary for all users"""
    logger.info("Generating weekly wellness summaries")

    try:
        # This would generate personalized weekly summaries for users
        # showing their wellness trends, achievements, and recommendations

        users_with_progress = WellnessUserProgress.objects.filter(
            total_content_viewed__gt=0
        ).select_related('user')

        summaries_generated = 0

        for progress in users_with_progress:
            try:
                # Generate weekly summary
                summary = generate_user_weekly_summary(progress.user)

                # TODO: Send summary via email or notification
                # send_weekly_summary_notification.delay(progress.user.id, summary)

                summaries_generated += 1

            except (DatabaseError, IntegrityError, ObjectDoesNotExist) as e:
                logger.error(f"Failed to generate weekly summary for user {progress.user.id}: {e}")

        return {
            'success': True,
            'summaries_generated': summaries_generated,
            'users_processed': users_with_progress.count()
        }

    except (ConnectionError, DatabaseError, IntegrationException, IntegrityError, ObjectDoesNotExist, ValueError) as e:
        logger.error(f"Weekly summary generation failed: {e}")
        raise


def generate_user_weekly_summary(user):
    """Generate weekly wellness summary for individual user"""
    # Get user's entries from past week
    week_entries = JournalEntry.objects.filter(
        user=user,
        timestamp__gte=timezone.now() - timedelta(days=7),
        is_deleted=False
    )

    # Get wellness interactions from past week
    week_interactions = WellnessContentInteraction.objects.filter(
        user=user,
        interaction_date__gte=timezone.now() - timedelta(days=7)
    )

    summary = {
        'user_name': user.peoplename,
        'week_ending': timezone.now().date().isoformat(),
        'journal_activity': {
            'entries_created': week_entries.count(),
            'wellbeing_entries': week_entries.filter(
                entry_type__in=['MOOD_CHECK_IN', 'STRESS_LOG', 'GRATITUDE']
            ).count()
        },
        'wellness_engagement': {
            'content_viewed': week_interactions.count(),
            'content_completed': week_interactions.filter(interaction_type='completed').count()
        },
        'key_insights': [],  # Would be populated with actual insights
        'recommendations': []  # Would be populated with weekly recommendations
    }

    return summary


# Task scheduling configuration for Django admin
JOURNAL_WELLNESS_PERIODIC_TASKS = {
    'daily_wellness_content_scheduling': {
        'task': 'background_tasks.journal_wellness_tasks.daily_wellness_content_scheduling',
        'schedule': 'cron(hour=8, minute=0)',  # 8 AM daily
        'description': 'Schedule daily wellness content for all users'
    },
    'update_all_user_streaks': {
        'task': 'background_tasks.journal_wellness_tasks.update_all_user_streaks',
        'schedule': 'cron(hour=23, minute=30)',  # 11:30 PM daily
        'description': 'Update wellness engagement streaks'
    },
    'enforce_data_retention_policies': {
        'task': 'background_tasks.journal_wellness_tasks.enforce_data_retention_policies',
        'schedule': 'cron(hour=2, minute=0)',  # 2 AM daily
        'description': 'Enforce data retention and auto-deletion policies'
    },
    'cleanup_old_wellness_interactions': {
        'task': 'background_tasks.journal_wellness_tasks.cleanup_old_wellness_interactions',
        'schedule': 'cron(hour=3, minute=0, day_of_week=0)',  # Sunday 3 AM weekly
        'description': 'Clean up old wellness interaction records'
    },
    'generate_wellness_analytics_reports': {
        'task': 'background_tasks.journal_wellness_tasks.generate_wellness_analytics_reports',
        'schedule': 'cron(hour=6, minute=0, day_of_week=1)',  # Monday 6 AM weekly
        'description': 'Generate comprehensive wellness analytics reports'
    },
    'maintain_journal_search_index': {
        'task': 'background_tasks.journal_wellness_tasks.maintain_journal_search_index',
        'schedule': 'cron(hour=4, minute=0)',  # 4 AM daily
        'description': 'Maintain Elasticsearch search indexes'
    },
    'weekly_wellness_summary': {
        'task': 'background_tasks.journal_wellness_tasks.weekly_wellness_summary',
        'schedule': 'cron(hour=7, minute=0, day_of_week=0)',  # Sunday 7 AM weekly
        'description': 'Generate weekly wellness summaries for users'
    }
}