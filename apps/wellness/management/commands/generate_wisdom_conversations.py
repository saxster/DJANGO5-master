"""
Generate Wisdom Conversations Management Command

Django management command to process existing intervention delivery data and
generate wisdom conversations for users who want to backfill their conversation
history or for initial setup of the "Conversations with Wisdom" feature.

Usage:
  python manage.py generate_wisdom_conversations --user USER_ID
  python manage.py generate_wisdom_conversations --all-users
  python manage.py generate_wisdom_conversations --days 90
  python manage.py generate_wisdom_conversations --intervention-type GRATITUDE_JOURNAL
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.db.models import Q, Count
from django.db import transaction

from ...models.wisdom_conversations import (
    ConversationThread, WisdomConversation, ConversationEngagement
)
from ...models.mental_health_interventions import InterventionDeliveryLog
from ...services.automatic_conversation_generator import AutomaticConversationGenerator
from ...services.conversation_flow_manager import ConversationFlowManager
from apps.core.exceptions.patterns import DATABASE_EXCEPTIONS

User = get_user_model()
logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Generate wisdom conversations from existing intervention delivery data'

    def add_arguments(self, parser):
        parser.add_argument(
            '--user',
            type=str,
            help='Generate conversations for specific user ID',
        )

        parser.add_argument(
            '--all-users',
            action='store_true',
            help='Generate conversations for all users with intervention data',
        )

        parser.add_argument(
            '--days',
            type=int,
            default=30,
            help='Number of days back to process (default: 30)',
        )

        parser.add_argument(
            '--intervention-type',
            type=str,
            help='Process only specific intervention type (e.g., GRATITUDE_JOURNAL)',
        )

        parser.add_argument(
            '--min-effectiveness',
            type=float,
            default=2.0,
            help='Minimum effectiveness score to process (default: 2.0)',
        )

        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be generated without actually creating conversations',
        )

        parser.add_argument(
            '--batch-size',
            type=int,
            default=50,
            help='Process deliveries in batches of this size (default: 50)',
        )

        parser.add_argument(
            '--force',
            action='store_true',
            help='Force regeneration even if conversations already exist',
        )

        parser.add_argument(
            '--optimize-flow',
            action='store_true',
            help='Optimize conversation flow after generation',
        )

        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Show detailed progress information',
        )

    def handle(self, *args, **options):
        """Main command handler"""

        self.verbosity = int(options['verbosity'])
        self.verbose = options['verbose']
        self.dry_run = options['dry_run']

        # Setup logging level
        if self.verbose:
            logger.setLevel(logging.DEBUG)

        self.stdout.write(
            self.style.SUCCESS('Starting wisdom conversation generation...')
        )

        # Validate arguments
        if not options['user'] and not options['all_users']:
            raise CommandError('Must specify either --user or --all-users')

        if options['user'] and options['all_users']:
            raise CommandError('Cannot specify both --user and --all-users')

        # Initialize services
        self.generator = AutomaticConversationGenerator()
        self.flow_manager = ConversationFlowManager()

        try:
            if options['user']:
                results = self._process_single_user(
                    options['user'],
                    options
                )
            else:
                results = self._process_all_users(options)

            self._display_results(results)

            # Optimize flow if requested
            if options['optimize_flow'] and not self.dry_run:
                self._optimize_conversation_flow(results)

        except DATABASE_EXCEPTIONS as e:
            logger.error(f"Command failed: {e}", exc_info=True)
            raise CommandError(f"Failed to generate conversations: {e}")

    def _process_single_user(self, user_identifier: str, options: Dict) -> Dict:
        """Process conversations for a single user"""

        try:
            # Try to get user by ID first, then by username
            try:
                user = User.objects.get(id=user_identifier)
            except (User.DoesNotExist, ValueError):
                user = User.objects.get(peoplename=user_identifier)

        except User.DoesNotExist:
            raise CommandError(f"User not found: {user_identifier}")

        self.stdout.write(f"Processing user: {user.peoplename} (ID: {user.id})")

        # Get eligible deliveries
        deliveries = self._get_eligible_deliveries(user, options)

        if not deliveries:
            self.stdout.write(
                self.style.WARNING(f"No eligible deliveries found for user {user.peoplename}")
            )
            return {
                'users_processed': 1,
                'total_deliveries': 0,
                'conversations_generated': 0,
                'skipped': 0,
                'errors': 0
            }

        # Process deliveries
        user_results = self._process_user_deliveries(user, deliveries, options)

        return {
            'users_processed': 1,
            'total_deliveries': len(deliveries),
            'conversations_generated': user_results['conversations_generated'],
            'skipped': user_results['skipped'],
            'errors': user_results['errors'],
            'processed_users': [user.peoplename]
        }

    def _process_all_users(self, options: Dict) -> Dict:
        """Process conversations for all users with intervention data"""

        # Get users with intervention deliveries
        start_date = timezone.now() - timedelta(days=options['days'])

        users_with_deliveries = User.objects.filter(
            intervention_deliveries__delivered_at__gte=start_date,
            intervention_deliveries__effectiveness_score__gte=options['min_effectiveness']
        ).distinct()

        if options['intervention_type']:
            users_with_deliveries = users_with_deliveries.filter(
                intervention_deliveries__intervention__intervention_type=options['intervention_type']
            )

        total_users = users_with_deliveries.count()

        if total_users == 0:
            self.stdout.write(
                self.style.WARNING("No users found with eligible intervention deliveries")
            )
            return {
                'users_processed': 0,
                'total_deliveries': 0,
                'conversations_generated': 0,
                'skipped': 0,
                'errors': 0
            }

        self.stdout.write(f"Found {total_users} users with eligible deliveries")

        # Process each user
        total_results = {
            'users_processed': 0,
            'total_deliveries': 0,
            'conversations_generated': 0,
            'skipped': 0,
            'errors': 0,
            'processed_users': []
        }

        for i, user in enumerate(users_with_deliveries, 1):
            self.stdout.write(f"Processing user {i}/{total_users}: {user.peoplename}")

            try:
                deliveries = self._get_eligible_deliveries(user, options)
                if deliveries:
                    user_results = self._process_user_deliveries(user, deliveries, options)

                    total_results['users_processed'] += 1
                    total_results['total_deliveries'] += len(deliveries)
                    total_results['conversations_generated'] += user_results['conversations_generated']
                    total_results['skipped'] += user_results['skipped']
                    total_results['errors'] += user_results['errors']
                    total_results['processed_users'].append(user.peoplename)

            except DATABASE_EXCEPTIONS as e:
                logger.error(f"Error processing user {user.peoplename}: {e}", exc_info=True)
                total_results['errors'] += 1

        return total_results

    def _get_eligible_deliveries(self, user: User, options: Dict) -> List[InterventionDeliveryLog]:
        """Get eligible intervention deliveries for a user"""

        start_date = timezone.now() - timedelta(days=options['days'])

        # Build query
        deliveries_query = InterventionDeliveryLog.objects.filter(
            user=user,
            delivered_at__gte=start_date,
            effectiveness_score__gte=options['min_effectiveness']
        ).select_related('intervention')

        # Filter by intervention type if specified
        if options['intervention_type']:
            deliveries_query = deliveries_query.filter(
                intervention__intervention_type=options['intervention_type']
            )

        # Exclude deliveries that already have conversations unless force is specified
        if not options['force']:
            existing_conversation_delivery_ids = WisdomConversation.objects.filter(
                user=user,
                source_intervention_delivery__isnull=False
            ).values_list('source_intervention_delivery_id', flat=True)

            deliveries_query = deliveries_query.exclude(
                id__in=existing_conversation_delivery_ids
            )

        return list(deliveries_query.order_by('delivered_at'))

    def _process_user_deliveries(
        self,
        user: User,
        deliveries: List[InterventionDeliveryLog],
        options: Dict
    ) -> Dict:
        """Process deliveries for a single user"""

        if self.verbose:
            self.stdout.write(f"  Found {len(deliveries)} eligible deliveries")

        results = {
            'conversations_generated': 0,
            'skipped': 0,
            'errors': 0,
            'conversations': []
        }

        batch_size = options['batch_size']

        # Process in batches
        for i in range(0, len(deliveries), batch_size):
            batch = deliveries[i:i+batch_size]
            batch_num = (i // batch_size) + 1
            total_batches = (len(deliveries) + batch_size - 1) // batch_size

            if self.verbose:
                self.stdout.write(f"  Processing batch {batch_num}/{total_batches} ({len(batch)} deliveries)")

            batch_results = self._process_delivery_batch(user, batch, options)

            results['conversations_generated'] += batch_results['conversations_generated']
            results['skipped'] += batch_results['skipped']
            results['errors'] += batch_results['errors']
            results['conversations'].extend(batch_results['conversations'])

        if self.verbose:
            self.stdout.write(
                f"  User {user.peoplename}: {results['conversations_generated']} generated, "
                f"{results['skipped']} skipped, {results['errors']} errors"
            )

        return results

    def _process_delivery_batch(
        self,
        user: User,
        deliveries: List[InterventionDeliveryLog],
        options: Dict
    ) -> Dict:
        """Process a batch of deliveries"""

        results = {
            'conversations_generated': 0,
            'skipped': 0,
            'errors': 0,
            'conversations': []
        }

        for delivery in deliveries:
            try:
                if self.dry_run:
                    # In dry run mode, just count what would be processed
                    if self._should_process_delivery(delivery, options):
                        results['conversations_generated'] += 1
                        if self.verbose:
                            self.stdout.write(
                                f"    [DRY RUN] Would generate conversation for "
                                f"{delivery.intervention.intervention_type} delivery {delivery.id}"
                            )
                    else:
                        results['skipped'] += 1
                else:
                    # Actually process the delivery
                    conversation = self._generate_conversation_for_delivery(delivery, options)

                    if conversation:
                        results['conversations_generated'] += 1
                        results['conversations'].append(conversation)

                        if self.verbose:
                            self.stdout.write(
                                f"    Generated conversation {conversation.id} for "
                                f"{delivery.intervention.intervention_type} delivery"
                            )
                    else:
                        results['skipped'] += 1

            except DATABASE_EXCEPTIONS as e:
                logger.error(f"Error processing delivery {delivery.id}: {e}", exc_info=True)
                results['errors'] += 1

        return results

    def _should_process_delivery(self, delivery: InterventionDeliveryLog, options: Dict) -> bool:
        """Check if a delivery should be processed"""

        # Check effectiveness threshold
        if delivery.effectiveness_score < options['min_effectiveness']:
            return False

        # Check if conversation already exists (unless force is specified)
        if not options['force']:
            if WisdomConversation.objects.filter(source_intervention_delivery=delivery).exists():
                return False

        return True

    def _generate_conversation_for_delivery(
        self,
        delivery: InterventionDeliveryLog,
        options: Dict
    ) -> Optional[WisdomConversation]:
        """Generate a conversation for a specific delivery"""

        try:
            with transaction.atomic():
                conversation = self.generator.process_intervention_delivery(delivery)

                if conversation:
                    # Mark the conversation as generated by management command
                    conversation.conversation_metadata = conversation.conversation_metadata.copy()
                    conversation.conversation_metadata['generation_source'] = 'management_command'
                    conversation.conversation_metadata['command_timestamp'] = timezone.now().isoformat()
                    conversation.save(update_fields=['conversation_metadata'])

                return conversation

        except DATABASE_EXCEPTIONS as e:
            logger.error(f"Failed to generate conversation for delivery {delivery.id}: {e}", exc_info=True)
            return None

    def _optimize_conversation_flow(self, results: Dict):
        """Optimize conversation flow for processed users"""

        if not results.get('processed_users'):
            return

        self.stdout.write("Optimizing conversation flow...")

        for username in results['processed_users']:
            try:
                user = User.objects.get(peoplename=username)
                flow_organization = self.flow_manager.organize_user_conversations(user)

                recommendations = flow_organization.get('flow_recommendations', [])
                if recommendations:
                    self.stdout.write(f"  Applying {len(recommendations)} flow improvements for {username}")

                    # Apply basic flow improvements
                    self._apply_flow_recommendations(user, recommendations)

            except DATABASE_EXCEPTIONS as e:
                logger.error(f"Error optimizing flow for user {username}: {e}", exc_info=True)

    def _apply_flow_recommendations(self, user: User, recommendations: List[Dict]):
        """Apply flow recommendations for a user"""

        for recommendation in recommendations[:3]:  # Limit to top 3 recommendations
            if recommendation['type'] == 'add_narrative_bridges':
                self._add_missing_bridges(user)
            elif recommendation['type'] == 'improve_thread_flow':
                self._improve_thread_sequencing(user)

    def _add_missing_bridges(self, user: User):
        """Add missing narrative bridges to conversations"""

        conversations_needing_bridges = WisdomConversation.objects.filter(
            user=user,
            contextual_bridge_text__exact='',
            sequence_number__gt=1
        )[:10]  # Limit to 10 to avoid overwhelming

        for conversation in conversations_needing_bridges:
            previous_conversation = conversation.get_previous_conversation()
            if previous_conversation:
                time_gap = conversation.conversation_date - previous_conversation.conversation_date

                if time_gap.days > 7:
                    bridge_text = "After some time to reflect, I wanted to share something important with you..."
                elif time_gap.days > 1:
                    bridge_text = "Continuing our conversation from a few days ago..."
                else:
                    bridge_text = "Building on what we discussed earlier..."

                conversation.contextual_bridge_text = bridge_text
                conversation.save(update_fields=['contextual_bridge_text'])

    def _improve_thread_sequencing(self, user: User):
        """Improve sequencing within conversation threads"""

        # For now, just ensure proper sequence numbering
        threads = ConversationThread.objects.filter(user=user)

        for thread in threads:
            conversations = list(thread.wisdom_conversations.order_by('conversation_date'))

            for i, conversation in enumerate(conversations, 1):
                if conversation.sequence_number != i:
                    conversation.sequence_number = i
                    conversation.save(update_fields=['sequence_number'])

    def _display_results(self, results: Dict):
        """Display command execution results"""

        self.stdout.write(
            self.style.SUCCESS('\n=== Wisdom Conversation Generation Results ===')
        )

        self.stdout.write(f"Users processed: {results['users_processed']}")
        self.stdout.write(f"Total deliveries analyzed: {results['total_deliveries']}")
        self.stdout.write(f"Conversations generated: {results['conversations_generated']}")
        self.stdout.write(f"Deliveries skipped: {results['skipped']}")

        if results['errors'] > 0:
            self.stdout.write(
                self.style.WARNING(f"Errors encountered: {results['errors']}")
            )

        if self.dry_run:
            self.stdout.write(
                self.style.WARNING("\nDRY RUN MODE - No conversations were actually created")
            )

        # Show success rate
        if results['total_deliveries'] > 0:
            success_rate = (results['conversations_generated'] / results['total_deliveries']) * 100
            self.stdout.write(f"Success rate: {success_rate:.1f}%")

        # Show processing rate
        if results['conversations_generated'] > 0:
            self.stdout.write(
                self.style.SUCCESS(
                    f"\nSuccessfully generated {results['conversations_generated']} wisdom conversations!"
                )
            )

        self.stdout.write("\nConversations can be viewed at: /wellness/conversations/")

    def _get_delivery_stats(self, deliveries: List[InterventionDeliveryLog]) -> Dict:
        """Get statistics about deliveries to be processed"""

        stats = {
            'by_type': {},
            'by_effectiveness': {},
            'date_range': None
        }

        if not deliveries:
            return stats

        # Count by intervention type
        for delivery in deliveries:
            intervention_type = delivery.intervention.intervention_type
            stats['by_type'][intervention_type] = stats['by_type'].get(intervention_type, 0) + 1

        # Count by effectiveness score ranges
        for delivery in deliveries:
            score = delivery.effectiveness_score
            if score >= 4.0:
                range_key = '4.0-5.0 (Excellent)'
            elif score >= 3.0:
                range_key = '3.0-3.9 (Good)'
            elif score >= 2.0:
                range_key = '2.0-2.9 (Fair)'
            else:
                range_key = '1.0-1.9 (Poor)'

            stats['by_effectiveness'][range_key] = stats['by_effectiveness'].get(range_key, 0) + 1

        # Date range
        dates = [d.delivered_at for d in deliveries]
        stats['date_range'] = {
            'start': min(dates).strftime('%Y-%m-%d'),
            'end': max(dates).strftime('%Y-%m-%d')
        }

        return stats