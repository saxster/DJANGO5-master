"""
Django Management Command: Batch Translation of Wisdom Conversations

Provides comprehensive batch translation capabilities for existing wisdom conversations
with progress tracking, error handling, and flexible filtering options.

Usage:
    python manage.py translate_conversations --language hi --max-translations 100
    python manage.py translate_conversations --all-languages --tenant-id 1
    python manage.py translate_conversations --conversation-ids 1,2,3 --language te
"""

import sys
from datetime import datetime, timedelta
from typing import List, Optional, Dict
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone
from django.conf import settings
from django.contrib.auth import get_user_model

from apps.wellness.models.wisdom_conversations import WisdomConversation
from apps.wellness.models.conversation_translation import WisdomConversationTranslation
from apps.wellness.services.conversation_translation_service import ConversationTranslationService
from apps.wellness.tasks import translate_conversation_async
from apps.tenants.models import Tenant
from apps.core.exceptions.patterns import DATABASE_EXCEPTIONS

User = get_user_model()


class Command(BaseCommand):
    help = '''
    Batch translate wisdom conversations to target languages.

    This command provides flexible options for translating existing conversations:
    - Translate to specific language(s)
    - Filter by tenant, date range, or specific conversations
    - Choose between immediate processing or background queue
    - Track progress and generate detailed reports
    '''

    def add_arguments(self, parser):
        """Add command line arguments"""

        # Language options
        parser.add_argument(
            '--language',
            type=str,
            help='Target language code (hi, te, es, fr, ar, zh)'
        )

        parser.add_argument(
            '--all-languages',
            action='store_true',
            help='Translate to all supported languages'
        )

        # Filtering options
        parser.add_argument(
            '--tenant-id',
            type=int,
            help='Translate conversations for specific tenant only'
        )

        parser.add_argument(
            '--conversation-ids',
            type=str,
            help='Comma-separated list of specific conversation IDs to translate'
        )

        parser.add_argument(
            '--date-from',
            type=str,
            help='Translate conversations from this date onwards (YYYY-MM-DD)'
        )

        parser.add_argument(
            '--date-to',
            type=str,
            help='Translate conversations up to this date (YYYY-MM-DD)'
        )

        # Processing options
        parser.add_argument(
            '--max-translations',
            type=int,
            default=50,
            help='Maximum number of translations to process (default: 50)'
        )

        parser.add_argument(
            '--background',
            action='store_true',
            help='Queue translations as background tasks instead of processing immediately'
        )

        parser.add_argument(
            '--force-refresh',
            action='store_true',
            help='Refresh existing translations (re-translate even if translation exists)'
        )

        # Output options
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be translated without actually doing it'
        )

        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Show detailed progress and translation information'
        )

    def handle(self, *args, **options):
        """Main command handler"""

        self.verbosity = options.get('verbosity', 1)
        self.verbose = options.get('verbose', False)
        self.dry_run = options.get('dry_run', False)

        # Validate arguments
        try:
            target_languages = self._validate_and_get_languages(options)
            conversations = self._get_conversations_to_translate(options)
        except CommandError as e:
            self.stdout.write(self.style.ERROR(str(e)))
            return

        if not conversations:
            self.stdout.write(self.style.WARNING('No conversations found matching the criteria.'))
            return

        # Display summary
        self._display_summary(conversations, target_languages, options)

        if self.dry_run:
            self.stdout.write(self.style.SUCCESS('\nDry run complete. No translations were processed.'))
            return

        # Process translations
        if options.get('background', False):
            self._queue_background_translations(conversations, target_languages, options)
        else:
            self._process_immediate_translations(conversations, target_languages, options)

    def _validate_and_get_languages(self, options) -> List[str]:
        """Validate and return target languages"""

        supported_languages = ['hi', 'te', 'es', 'fr', 'ar', 'zh']

        if options.get('all_languages'):
            return supported_languages

        language = options.get('language')
        if not language:
            raise CommandError('You must specify either --language or --all-languages')

        if language not in supported_languages:
            raise CommandError(
                f'Unsupported language: {language}. '
                f'Supported languages: {", ".join(supported_languages)}'
            )

        return [language]

    def _get_conversations_to_translate(self, options) -> List[WisdomConversation]:
        """Get conversations matching the filtering criteria"""

        queryset = WisdomConversation.objects.all()

        # Filter by tenant
        if options.get('tenant_id'):
            try:
                tenant = Tenant.objects.get(id=options['tenant_id'])
                queryset = queryset.filter(tenant=tenant)
            except Tenant.DoesNotExist:
                raise CommandError(f'Tenant with ID {options["tenant_id"]} not found')

        # Filter by specific conversation IDs
        if options.get('conversation_ids'):
            try:
                conversation_ids = [
                    int(id_str.strip())
                    for id_str in options['conversation_ids'].split(',')
                ]
                queryset = queryset.filter(id__in=conversation_ids)
            except ValueError:
                raise CommandError('Invalid conversation IDs format. Use comma-separated integers.')

        # Filter by date range
        if options.get('date_from'):
            try:
                date_from = datetime.strptime(options['date_from'], '%Y-%m-%d').date()
                queryset = queryset.filter(conversation_date__gte=date_from)
            except ValueError:
                raise CommandError('Invalid date format for --date-from. Use YYYY-MM-DD.')

        if options.get('date_to'):
            try:
                date_to = datetime.strptime(options['date_to'], '%Y-%m-%d').date()
                queryset = queryset.filter(conversation_date__lte=date_to)
            except ValueError:
                raise CommandError('Invalid date format for --date-to. Use YYYY-MM-DD.')

        # Limit results
        max_translations = options.get('max_translations', 50)
        queryset = queryset.order_by('-conversation_date')[:max_translations]

        return list(queryset)

    def _display_summary(self, conversations: List[WisdomConversation],
                        target_languages: List[str], options: Dict):
        """Display translation summary before processing"""

        self.stdout.write(self.style.SUCCESS('\n=== Translation Summary ==='))
        self.stdout.write(f'Conversations to process: {len(conversations)}')
        self.stdout.write(f'Target languages: {", ".join(target_languages)}')
        self.stdout.write(f'Total translations needed: {len(conversations) * len(target_languages)}')

        if options.get('background'):
            self.stdout.write(f'Processing mode: Background queue')
        else:
            self.stdout.write(f'Processing mode: Immediate')

        if options.get('force_refresh'):
            self.stdout.write(f'Force refresh: Enabled (will re-translate existing translations)')

        if self.dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN MODE - No actual translations will be performed'))

        # Show conversation details if verbose
        if self.verbose and len(conversations) <= 10:
            self.stdout.write('\nConversations to translate:')
            for conv in conversations:
                preview = conv.conversation_text[:100] + "..." if len(conv.conversation_text) > 100 else conv.conversation_text
                self.stdout.write(f'  - {conv.id}: {preview}')

    def _queue_background_translations(self, conversations: List[WisdomConversation],
                                     target_languages: List[str], options: Dict):
        """Queue translations as background Celery tasks"""

        queued_count = 0
        skipped_count = 0

        self.stdout.write('\nQueueing background translations...')

        for conversation in conversations:
            for language in target_languages:

                # Check if translation already exists (unless force refresh)
                if not options.get('force_refresh'):
                    existing = WisdomConversationTranslation.objects.filter(
                        original_conversation=conversation,
                        target_language=language,
                        status='completed'
                    ).first()

                    if existing and not existing.is_expired:
                        if self.verbose:
                            self.stdout.write(f'  Skipping {conversation.id} → {language} (already exists)')
                        skipped_count += 1
                        continue

                # Queue the translation
                translate_conversation_async.delay(
                    conversation_id=conversation.id,
                    target_language=language,
                    priority='manual'
                )

                queued_count += 1

                if self.verbose:
                    self.stdout.write(f'  Queued: {conversation.id} → {language}')

        self.stdout.write(self.style.SUCCESS(
            f'\nBackground translation summary:'
            f'\n  Queued: {queued_count} translations'
            f'\n  Skipped: {skipped_count} existing translations'
        ))

    def _process_immediate_translations(self, conversations: List[WisdomConversation],
                                      target_languages: List[str], options: Dict):
        """Process translations immediately with progress tracking"""

        translation_service = ConversationTranslationService()

        successful_count = 0
        failed_count = 0
        skipped_count = 0

        total_translations = len(conversations) * len(target_languages)
        current_translation = 0

        self.stdout.write('\nProcessing translations...')

        for conversation in conversations:
            for language in target_languages:
                current_translation += 1

                # Progress indicator
                if not self.verbose:
                    progress = (current_translation / total_translations) * 100
                    sys.stdout.write(f'\rProgress: {progress:.1f}% ({current_translation}/{total_translations})')
                    sys.stdout.flush()

                try:
                    # Check if translation already exists (unless force refresh)
                    if not options.get('force_refresh'):
                        existing = WisdomConversationTranslation.objects.filter(
                            original_conversation=conversation,
                            target_language=language,
                            status='completed'
                        ).first()

                        if existing and not existing.is_expired:
                            if self.verbose:
                                self.stdout.write(f'  Skipping {conversation.id} → {language} (already exists)')
                            skipped_count += 1
                            continue

                    # Perform translation
                    if self.verbose:
                        self.stdout.write(f'  Translating {conversation.id} → {language}...')

                    result = translation_service.translate_conversation(
                        conversation=conversation,
                        target_language=language,
                        user=None  # System translation
                    )

                    if result['success']:
                        successful_count += 1

                        if self.verbose:
                            backend = result.get('backend_used', 'unknown')
                            confidence = result.get('confidence', 0) * 100
                            self.stdout.write(
                                f'    ✓ Success using {backend} (confidence: {confidence:.1f}%)'
                            )
                    else:
                        failed_count += 1
                        error = result.get('error', 'Unknown error')

                        if self.verbose:
                            self.stdout.write(f'    ✗ Failed: {error}')
                        else:
                            self.stdout.write(f'\nTranslation failed: {conversation.id} → {language}: {error}')

                except DATABASE_EXCEPTIONS as e:
                    failed_count += 1

                    if self.verbose:
                        self.stdout.write(f'    ✗ Exception: {str(e)}')
                    else:
                        self.stdout.write(f'\nException during translation: {conversation.id} → {language}: {str(e)}')

        # Clear progress line if not verbose
        if not self.verbose:
            sys.stdout.write('\n')

        # Final summary
        self.stdout.write(self.style.SUCCESS(
            f'\nTranslation complete!'
            f'\n  Successful: {successful_count}'
            f'\n  Failed: {failed_count}'
            f'\n  Skipped: {skipped_count}'
            f'\n  Total processed: {successful_count + failed_count + skipped_count}'
        ))

        if failed_count > 0:
            self.stdout.write(self.style.WARNING(
                f'\nSome translations failed. Check logs for details or use --verbose for more information.'
            ))

    def _generate_report(self, results: Dict):
        """Generate detailed translation report"""

        report = f'''
=== Translation Report ===
Generated: {timezone.now().strftime('%Y-%m-%d %H:%M:%S')}

Summary:
  Total conversations: {results['total_conversations']}
  Target languages: {', '.join(results['target_languages'])}
  Successful translations: {results['successful']}
  Failed translations: {results['failed']}
  Skipped translations: {results['skipped']}

Performance:
  Average translation time: {results.get('avg_time', 'N/A')}
  Success rate: {results.get('success_rate', 'N/A')}%

Errors encountered:
'''

        for error in results.get('errors', []):
            report += f"  - {error}\n"

        return report