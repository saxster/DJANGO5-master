"""
Automatic Conversation Generator

Service that automatically generates wisdom conversations from intervention deliveries
in real-time, ensuring the user's "conversation book" is continuously updated with
new chapters as their mental health journey progresses.

Chain of Thought Reasoning:
1. Monitor intervention delivery events
2. Automatically transform deliveries into conversations
3. Manage generation queue and priorities
4. Handle batch processing for efficiency
5. Ensure conversation quality and flow
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.db.models import Q, F
from django.db import transaction

from ..models.wisdom_conversations import (
    ConversationThread, WisdomConversation, ConversationEngagement
)
from ..models.mental_health_interventions import InterventionDeliveryLog
from .wisdom_conversation_generator import WisdomConversationGenerator
from .conversation_flow_manager import ConversationFlowManager
from .conversation_personalization_system import ConversationPersonalizationSystem

User = get_user_model()
logger = logging.getLogger(__name__)


class AutomaticConversationGenerator:
    """
    Automatically generates wisdom conversations from intervention deliveries
    to maintain continuous narrative flow in the user's mental health journey.

    Ultra-think approach: Create seamless automation that feels like a caring
    AI companion is always there, thoughtfully creating conversation entries
    as the user progresses through their mental health journey.
    """

    def __init__(self):
        self.conversation_generator = WisdomConversationGenerator()
        self.flow_manager = ConversationFlowManager()
        self.personalization_system = ConversationPersonalizationSystem()

        # Generation settings
        self.max_daily_conversations = 5  # Prevent overwhelming users
        self.min_time_between_conversations = 2  # Hours
        self.batch_processing_size = 50  # Process deliveries in batches
        self.quality_threshold = 0.6  # Minimum quality score for auto-generation

        # Priority levels for different intervention types
        self.generation_priorities = {
            'CRISIS_SUPPORT': 10,  # Immediate
            'CBT_THOUGHT_RECORD': 8,  # High
            'MOTIVATIONAL_INTERVIEWING': 6,  # Medium-high
            'STRESS_MANAGEMENT': 5,  # Medium
            'THREE_GOOD_THINGS': 4,  # Medium-low
            'GRATITUDE_JOURNAL': 3,  # Low
            'WORKPLACE_WELLNESS': 3,  # Low
            'PREVENTIVE_CARE': 2,  # Very low
        }

    def process_intervention_delivery(self, delivery_log: InterventionDeliveryLog) -> Optional[WisdomConversation]:
        """
        Process a single intervention delivery and generate conversation if appropriate.

        Main entry point for automatic conversation generation from intervention deliveries.
        """

        logger.info(f"Processing intervention delivery {delivery_log.id} for automatic conversation generation")

        try:
            # Check if conversation generation is appropriate
            if not self._should_generate_conversation(delivery_log):
                logger.debug(f"Skipping conversation generation for delivery {delivery_log.id}")
                return None

            # Check daily conversation limits
            if not self._check_daily_limits(delivery_log.user):
                logger.info(f"Daily conversation limit reached for user {delivery_log.user.peoplename}")
                return None

            # Check time spacing between conversations
            if not self._check_conversation_spacing(delivery_log):
                logger.info(f"Conversation spacing requirements not met for delivery {delivery_log.id}")
                return None

            # Generate the conversation
            conversation = self._generate_conversation_from_delivery(delivery_log)

            if conversation:
                # Post-generation quality checks and optimizations
                self._post_generation_processing(conversation)

                logger.info(f"Successfully generated conversation {conversation.id} from delivery {delivery_log.id}")
                return conversation

        except Exception as e:
            logger.error(f"Error processing intervention delivery {delivery_log.id}: {e}")
            return None

    def process_batch_deliveries(self, deliveries: List[InterventionDeliveryLog]) -> Dict:
        """
        Process multiple intervention deliveries in batch for efficiency.

        Used for bulk processing of existing deliveries or periodic cleanup.
        """

        logger.info(f"Processing batch of {len(deliveries)} intervention deliveries")

        results = {
            'total_processed': 0,
            'conversations_generated': 0,
            'skipped': 0,
            'errors': 0,
            'generated_conversations': []
        }

        # Sort deliveries by priority
        sorted_deliveries = sorted(
            deliveries,
            key=lambda d: self.generation_priorities.get(d.intervention.intervention_type, 1),
            reverse=True
        )

        # Group by user to manage per-user limits
        user_deliveries = {}
        for delivery in sorted_deliveries:
            user_id = delivery.user.id
            if user_id not in user_deliveries:
                user_deliveries[user_id] = []
            user_deliveries[user_id].append(delivery)

        # Process each user's deliveries
        for user_id, user_delivery_list in user_deliveries.items():
            user_results = self._process_user_deliveries(user_delivery_list)

            results['total_processed'] += user_results['processed']
            results['conversations_generated'] += user_results['generated']
            results['skipped'] += user_results['skipped']
            results['errors'] += user_results['errors']
            results['generated_conversations'].extend(user_results['conversations'])

        logger.info(f"Batch processing complete: {results}")
        return results

    def generate_conversations_for_user(self, user: User, days_back: int = 30) -> Dict:
        """
        Generate conversations for all eligible intervention deliveries for a specific user.

        Useful for onboarding existing users to the wisdom conversations feature.
        """

        logger.info(f"Generating conversations for user {user.peoplename} over last {days_back} days")

        start_date = timezone.now() - timedelta(days=days_back)

        # Get all eligible deliveries for the user
        deliveries = InterventionDeliveryLog.objects.filter(
            user=user,
            delivered_at__gte=start_date,
            effectiveness_score__gte=2.0  # Only process moderately effective interventions
        ).select_related('intervention').order_by('delivered_at')

        # Check for existing conversations to avoid duplicates
        existing_conversations = set(
            WisdomConversation.objects.filter(
                user=user,
                source_intervention_delivery__in=deliveries
            ).values_list('source_intervention_delivery_id', flat=True)
        )

        # Filter out deliveries that already have conversations
        new_deliveries = [d for d in deliveries if d.id not in existing_conversations]

        if not new_deliveries:
            logger.info(f"No new deliveries to process for user {user.peoplename}")
            return {
                'total_deliveries': deliveries.count(),
                'new_deliveries': 0,
                'conversations_generated': 0,
                'message': 'All eligible deliveries already have conversations'
            }

        # Process deliveries in chronological order for better narrative flow
        results = self.process_batch_deliveries(new_deliveries)

        # Optimize conversation flow after generation
        if results['conversations_generated'] > 0:
            self._optimize_user_conversation_flow(user)

        return {
            'total_deliveries': deliveries.count(),
            'new_deliveries': len(new_deliveries),
            'conversations_generated': results['conversations_generated'],
            'skipped': results['skipped'],
            'errors': results['errors'],
            'generated_conversations': results['generated_conversations']
        }

    def _should_generate_conversation(self, delivery_log: InterventionDeliveryLog) -> bool:
        """Determine if a conversation should be generated for this delivery"""

        # Check if conversation already exists
        if WisdomConversation.objects.filter(source_intervention_delivery=delivery_log).exists():
            return False

        # Check effectiveness threshold
        if delivery_log.effectiveness_score < 2.0:
            logger.debug(f"Delivery {delivery_log.id} effectiveness too low: {delivery_log.effectiveness_score}")
            return False

        # Check intervention type eligibility
        intervention_type = delivery_log.intervention.intervention_type
        if intervention_type not in self.generation_priorities:
            logger.debug(f"Intervention type {intervention_type} not eligible for automatic generation")
            return False

        # Check user preferences
        if not self._check_user_preferences(delivery_log.user):
            return False

        # Check for crisis situations (always generate)
        if intervention_type == 'CRISIS_SUPPORT':
            return True

        # Check delivery quality
        if delivery_log.personalization_score < self.quality_threshold:
            logger.debug(f"Delivery {delivery_log.id} quality too low: {delivery_log.personalization_score}")
            return False

        return True

    def _check_daily_limits(self, user: User) -> bool:
        """Check if user has reached daily conversation generation limit"""

        today = timezone.now().date()
        today_conversations = WisdomConversation.objects.filter(
            user=user,
            conversation_date__date=today,
            source_type='intervention_delivery'
        ).count()

        return today_conversations < self.max_daily_conversations

    def _check_conversation_spacing(self, delivery_log: InterventionDeliveryLog) -> bool:
        """Check if enough time has passed since last generated conversation"""

        user = delivery_log.user
        min_time_ago = timezone.now() - timedelta(hours=self.min_time_between_conversations)

        recent_conversation = WisdomConversation.objects.filter(
            user=user,
            conversation_date__gte=min_time_ago,
            source_type='intervention_delivery'
        ).exists()

        return not recent_conversation

    def _check_user_preferences(self, user: User) -> bool:
        """Check if user has enabled automatic conversation generation"""

        try:
            from ..models.user_progress import WellnessUserProgress
            wellness_progress = WellnessUserProgress.objects.get(user=user)

            # Check if user has enabled contextual delivery (proxy for conversation generation)
            return getattr(wellness_progress, 'contextual_delivery_enabled', True)

        except WellnessUserProgress.DoesNotExist:
            # Default to enabled for users without wellness progress
            return True

    def _generate_conversation_from_delivery(self, delivery_log: InterventionDeliveryLog) -> Optional[WisdomConversation]:
        """Generate a conversation from an intervention delivery"""

        try:
            with transaction.atomic():
                # Generate the conversation
                conversation = self.conversation_generator.generate_conversation_from_delivery(delivery_log)

                # Apply additional quality enhancements
                self._enhance_conversation_quality(conversation)

                # Track automatic generation event
                self._track_automatic_generation(conversation, delivery_log)

                return conversation

        except Exception as e:
            logger.error(f"Error generating conversation from delivery {delivery_log.id}: {e}")
            return None

    def _enhance_conversation_quality(self, conversation: WisdomConversation):
        """Apply additional quality enhancements to generated conversation"""

        # Check for and improve contextual bridging
        if not conversation.contextual_bridge_text:
            bridge_text = self._generate_missing_bridge(conversation)
            if bridge_text:
                conversation.contextual_bridge_text = bridge_text
                conversation.save(update_fields=['contextual_bridge_text'])

        # Apply personalization improvements
        personalized_text = self.personalization_system.personalize_conversation_content(
            conversation.conversation_text,
            conversation.user,
            {
                'tone': conversation.conversation_tone,
                'intervention_type': conversation.conversation_metadata.get('intervention_type'),
                'thread_type': conversation.thread.thread_type
            },
            conversation.thread
        )

        if personalized_text != conversation.conversation_text:
            conversation.conversation_text = personalized_text
            conversation.personalization_score = min(1.0, conversation.personalization_score + 0.1)
            conversation.save(update_fields=['conversation_text', 'personalization_score'])

    def _generate_missing_bridge(self, conversation: WisdomConversation) -> Optional[str]:
        """Generate a contextual bridge if missing"""

        previous_conversation = conversation.get_previous_conversation()
        if not previous_conversation:
            return None

        # Use flow manager to generate bridge
        time_gap = conversation.conversation_date - previous_conversation.conversation_date

        if time_gap.days > 1:
            return "As I reflect on our recent conversations, something important comes to mind..."
        else:
            return "Building on what we discussed earlier..."

    def _track_automatic_generation(self, conversation: WisdomConversation, delivery_log: InterventionDeliveryLog):
        """Track the automatic generation event for analytics"""

        ConversationEngagement.objects.create(
            user=conversation.user,
            conversation=conversation,
            engagement_type='view',  # Initial system view
            access_context='automated_generation',
            engagement_metadata={
                'generation_type': 'automatic',
                'source_delivery_id': str(delivery_log.id),
                'intervention_type': delivery_log.intervention.intervention_type,
                'generation_time': timezone.now().isoformat(),
                'quality_score': conversation.personalization_score,
            }
        )

    def _process_user_deliveries(self, deliveries: List[InterventionDeliveryLog]) -> Dict:
        """Process all deliveries for a specific user"""

        user = deliveries[0].user if deliveries else None
        if not user:
            return {'processed': 0, 'generated': 0, 'skipped': 0, 'errors': 0, 'conversations': []}

        results = {'processed': 0, 'generated': 0, 'skipped': 0, 'errors': 0, 'conversations': []}

        daily_count = 0
        last_conversation_time = None

        for delivery in deliveries:
            results['processed'] += 1

            try:
                # Check daily limits
                if daily_count >= self.max_daily_conversations:
                    results['skipped'] += 1
                    continue

                # Check time spacing
                if (last_conversation_time and
                    delivery.delivered_at - last_conversation_time < timedelta(hours=self.min_time_between_conversations)):
                    results['skipped'] += 1
                    continue

                # Generate conversation
                conversation = self._generate_conversation_from_delivery(delivery)

                if conversation:
                    results['generated'] += 1
                    results['conversations'].append(conversation)
                    daily_count += 1
                    last_conversation_time = delivery.delivered_at
                else:
                    results['skipped'] += 1

            except Exception as e:
                logger.error(f"Error processing delivery {delivery.id}: {e}")
                results['errors'] += 1

        return results

    def _optimize_user_conversation_flow(self, user: User):
        """Optimize conversation flow after batch generation"""

        try:
            # Analyze and optimize flow
            flow_organization = self.flow_manager.organize_user_conversations(user)

            # Apply any recommended improvements
            recommendations = flow_organization.get('flow_recommendations', [])

            for recommendation in recommendations:
                if recommendation['type'] == 'add_narrative_bridges':
                    self._add_missing_bridges(user, recommendation)
                elif recommendation['type'] == 'improve_thread_flow':
                    self._improve_thread_flow(user, recommendation)

        except Exception as e:
            logger.error(f"Error optimizing conversation flow for user {user.id}: {e}")

    def _add_missing_bridges(self, user: User, recommendation: Dict):
        """Add missing narrative bridges to conversations"""

        conversations_needing_bridges = WisdomConversation.objects.filter(
            user=user,
            contextual_bridge_text__exact='',
            sequence_number__gt=1
        )

        for conversation in conversations_needing_bridges[:5]:  # Limit to 5 to avoid overwhelming
            bridge_text = self._generate_missing_bridge(conversation)
            if bridge_text:
                conversation.contextual_bridge_text = bridge_text
                conversation.save(update_fields=['contextual_bridge_text'])

    def _improve_thread_flow(self, user: User, recommendation: Dict):
        """Improve flow within specific threads"""

        # This could involve reordering conversations, improving transitions, etc.
        # For now, just log the recommendation
        logger.info(f"Thread flow improvement needed for user {user.id}: {recommendation}")

    def get_generation_statistics(self, user: Optional[User] = None, days: int = 30) -> Dict:
        """Get statistics about automatic conversation generation"""

        start_date = timezone.now() - timedelta(days=days)

        base_query = WisdomConversation.objects.filter(
            conversation_date__gte=start_date,
            source_type='intervention_delivery'
        )

        if user:
            base_query = base_query.filter(user=user)

        total_generated = base_query.count()
        by_intervention_type = {}

        conversations = base_query.select_related('source_intervention_delivery__intervention')
        for conversation in conversations:
            intervention_type = conversation.source_intervention_delivery.intervention.intervention_type
            by_intervention_type[intervention_type] = by_intervention_type.get(intervention_type, 0) + 1

        # Calculate average quality
        quality_scores = list(base_query.values_list('personalization_score', flat=True))
        avg_quality = sum(quality_scores) / len(quality_scores) if quality_scores else 0

        return {
            'total_generated': total_generated,
            'by_intervention_type': by_intervention_type,
            'average_quality_score': avg_quality,
            'generation_rate': total_generated / days,
            'period_days': days,
        }

    def cleanup_old_generation_data(self, days_to_keep: int = 365):
        """Clean up old generation tracking data"""

        cutoff_date = timezone.now() - timedelta(days=days_to_keep)

        # Clean up old engagement records for automatic generation
        deleted_count = ConversationEngagement.objects.filter(
            access_context='automated_generation',
            engagement_date__lt=cutoff_date
        ).delete()[0]

        logger.info(f"Cleaned up {deleted_count} old automatic generation tracking records")