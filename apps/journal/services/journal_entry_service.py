"""
Journal Entry Service

Handles business logic for journal entry CRUD operations.
Extracted from views.py to separate concerns and improve testability.
"""

from django.utils import timezone
from django.db.models import Avg
from apps.journal.logging import get_journal_logger
from apps.journal.logging.sanitizers import sanitize_title_for_logging

logger = get_journal_logger(__name__)


class JournalEntryService:
    """Service for journal entry CRUD operations and business logic"""

    def create_entry_with_analysis(self, user, validated_data):
        """
        Create journal entry with automated analysis

        Args:
            user: User object
            validated_data: Validated serializer data

        Returns:
            dict: {
                'success': bool,
                'journal_entry': JournalEntry or None,
                'error': str or None
            }
        """
        try:
            from apps.journal.services.workflow_orchestrator import JournalWorkflowOrchestrator
            orchestrator = JournalWorkflowOrchestrator()

            result = orchestrator.create_journal_entry_with_analysis(user, validated_data)

            if result['success']:
                sanitized_title = sanitize_title_for_logging(result['journal_entry'].title)
                logger.info(
                    f"Journal entry created: {sanitized_title}",
                    extra={'entry_id': str(result['journal_entry'].id)}
                )
            else:
                logger.error(f"Journal entry creation failed: {result.get('error')}")

            return result

        except ImportError:
            # Fallback to basic creation
            from apps.journal.models import JournalEntry
            journal_entry = JournalEntry.objects.create(
                user=user,
                tenant=getattr(user, 'tenant', None),
                **validated_data
            )
            sanitized_title = sanitize_title_for_logging(journal_entry.title)
            logger.info(
                f"Journal entry created (basic): {sanitized_title}",
                extra={'entry_id': str(journal_entry.id)}
            )

            # Trigger basic pattern analysis
            try:
                self._trigger_pattern_analysis(journal_entry)
            except (ImportError, AttributeError, TypeError) as e:
                logger.error(f"Pattern analysis failed: {e}", exc_info=True)

            return {
                'success': True,
                'journal_entry': journal_entry,
                'error': None
            }

    def update_entry_with_reanalysis(self, entry, validated_data):
        """
        Update journal entry with optional reanalysis

        Args:
            entry: Existing JournalEntry object
            validated_data: Validated serializer data

        Returns:
            dict: {
                'success': bool,
                'journal_entry': JournalEntry or None,
                'reanalysis_triggered': bool,
                'error': str or None
            }
        """
        try:
            from apps.journal.services.workflow_orchestrator import JournalWorkflowOrchestrator
            orchestrator = JournalWorkflowOrchestrator()

            result = orchestrator.update_journal_entry_with_reanalysis(entry, validated_data)

            if result['success']:
                sanitized_title = sanitize_title_for_logging(result['journal_entry'].title)
                logger.debug(
                    f"Journal entry updated: {sanitized_title}",
                    extra={'entry_id': str(result['journal_entry'].id)}
                )
            else:
                logger.error(f"Journal entry update failed: {result.get('error')}")

            return result

        except ImportError:
            # Fallback to basic update
            for key, value in validated_data.items():
                setattr(entry, key, value)
            entry.save()

            sanitized_title = sanitize_title_for_logging(entry.title)
            logger.debug(
                f"Journal entry updated (basic): {sanitized_title}",
                extra={'entry_id': str(entry.id)}
            )

            return {
                'success': True,
                'journal_entry': entry,
                'reanalysis_triggered': False,
                'error': None
            }

    def soft_delete_entry(self, entry):
        """
        Soft delete journal entry

        Args:
            entry: JournalEntry object

        Returns:
            bool: True if successful
        """
        if hasattr(entry, 'sync_data') and entry.sync_data:
            entry.sync_data.mark_for_deletion()
        else:
            entry.is_deleted = True
            if hasattr(entry, 'sync_status'):
                entry.sync_status = 'pending_delete'
            entry.save()

        sanitized_title = sanitize_title_for_logging(entry.title)
        logger.info(
            f"Journal entry soft deleted: {sanitized_title}",
            extra={'entry_id': str(entry.id)}
        )
        return True

    def toggle_bookmark(self, entry):
        """
        Toggle bookmark status

        Args:
            entry: JournalEntry object

        Returns:
            dict: {'id': int, 'is_bookmarked': bool}
        """
        entry.is_bookmarked = not entry.is_bookmarked
        entry.save()

        return {
            'id': entry.id,
            'is_bookmarked': entry.is_bookmarked
        }

    def calculate_basic_analytics(self, entries):
        """
        Calculate basic analytics for journal entries

        Args:
            entries: QuerySet of JournalEntry objects

        Returns:
            dict: Analytics summary
        """
        total_entries = entries.count()
        wellbeing_entries = entries.filter(
            entry_type__in=[
                'MOOD_CHECK_IN', 'GRATITUDE', 'STRESS_LOG',
                'THREE_GOOD_THINGS', 'PERSONAL_REFLECTION'
            ]
        )

        # Mood analytics
        mood_entries = entries.exclude(mood_rating__isnull=True)
        avg_mood = mood_entries.aggregate(avg=Avg('mood_rating'))['avg']

        # Stress analytics
        stress_entries = entries.exclude(stress_level__isnull=True)
        avg_stress = stress_entries.aggregate(avg=Avg('stress_level'))['avg']

        # Energy analytics
        energy_entries = entries.exclude(energy_level__isnull=True)
        avg_energy = energy_entries.aggregate(avg=Avg('energy_level'))['avg']

        return {
            'summary': {
                'total_entries': total_entries,
                'wellbeing_entries': wellbeing_entries.count(),
                'wellbeing_ratio': wellbeing_entries.count() / total_entries if total_entries > 0 else 0
            },
            'wellbeing_metrics': {
                'average_mood': round(avg_mood, 2) if avg_mood else None,
                'average_stress': round(avg_stress, 2) if avg_stress else None,
                'average_energy': round(avg_energy, 2) if avg_energy else None,
                'mood_entries_count': mood_entries.count(),
                'stress_entries_count': stress_entries.count(),
                'energy_entries_count': energy_entries.count()
            },
            'analysis_period': {
                'days': (entries.last().timestamp.date() - entries.first().timestamp.date()).days if entries.first() and entries.last() else 0,
                'start_date': entries.first().timestamp.isoformat() if entries.first() else None,
                'end_date': entries.last().timestamp.isoformat() if entries.last() else None
            }
        }

    def _trigger_pattern_analysis(self, journal_entry):
        """Trigger pattern analysis for wellness interventions"""
        try:
            from apps.journal.services.pattern_analyzer import JournalPatternAnalyzer

            analyzer = JournalPatternAnalyzer()
            analysis_result = analyzer.analyze_entry_for_immediate_action(journal_entry)

            logger.debug(f"Pattern analysis result for entry {journal_entry.id}: {analysis_result}")
            return analysis_result

        except ImportError:
            logger.debug("Pattern analyzer service not yet implemented")
            return None
