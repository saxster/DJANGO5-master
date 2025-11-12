"""
Journal Workflow Orchestrator

Coordinates complex multi-step journal operations and integrates with various services.
Provides a centralized interface for handling journal workflows that involve multiple
components like analytics, pattern recognition, content delivery, and background tasks.
"""

from django.utils import timezone
from django.db import transaction
from django.core.exceptions import ValidationError
from apps.journal.logging import get_journal_logger
from apps.core.exceptions.patterns import DATABASE_EXCEPTIONS


logger = get_journal_logger(__name__)


class JournalWorkflowOrchestrator:
    """
    Orchestrates complex journal workflows

    Provides high-level coordination of journal operations that involve multiple
    services and components. Ensures proper error handling, transaction management,
    and service integration.
    """

    def __init__(self):
        self._analytics_service = None
        self._pattern_analyzer = None

    @property
    def analytics_service(self):
        """Lazy loading of analytics service"""
        if not self._analytics_service:
            from .analytics_service import JournalAnalyticsService
            self._analytics_service = JournalAnalyticsService()
        return self._analytics_service

    @property
    def pattern_analyzer(self):
        """Lazy loading of pattern analyzer"""
        if not self._pattern_analyzer:
            from .pattern_analyzer import JournalPatternAnalyzer
            self._pattern_analyzer = JournalPatternAnalyzer()
        return self._pattern_analyzer

    def create_journal_entry_with_analysis(self, user, entry_data):
        """
        Create journal entry and trigger comprehensive analysis

        Args:
            user: User creating the entry
            entry_data: Dict with entry data

        Returns:
            dict: Creation result with analysis
        """
        logger.info(f"Creating journal entry with analysis for user {user.id}")

        try:
            with transaction.atomic():
                # Create the journal entry
                journal_entry = self._create_journal_entry(user, entry_data)

                # Trigger immediate pattern analysis
                immediate_analysis = self.pattern_analyzer.analyze_entry_for_immediate_action(journal_entry)

                # Schedule background analytics update
                self._schedule_analytics_update(user.id, journal_entry.id)

                # Handle crisis intervention if needed
                if immediate_analysis.get('crisis_detected', False):
                    self._handle_crisis_intervention(user, journal_entry, immediate_analysis)

                # Schedule wellness content if needed
                if immediate_analysis.get('urgency_level') in ['high', 'critical']:
                    self._schedule_wellness_content(user.id, immediate_analysis)

                return {
                    'success': True,
                    'journal_entry': journal_entry,
                    'immediate_analysis': immediate_analysis,
                    'actions_taken': self._get_actions_taken(immediate_analysis)
                }

        except (ValidationError, ValueError) as e:
            logger.error(f"Journal entry creation failed for user {user.id}: {e}")
            return {
                'success': False,
                'error': str(e),
                'error_type': 'validation_error'
            }

        except DATABASE_EXCEPTIONS as e:
            logger.error(f"Unexpected error creating journal entry for user {user.id}: {e}")
            return {
                'success': False,
                'error': 'An unexpected error occurred',
                'error_type': 'system_error'
            }

    def update_journal_entry_with_reanalysis(self, journal_entry, update_data):
        """
        Update journal entry and re-trigger analysis if needed

        Args:
            journal_entry: Existing JournalEntry instance
            update_data: Dict with update data

        Returns:
            dict: Update result with analysis
        """
        logger.info(f"Updating journal entry {journal_entry.id} with reanalysis")

        try:
            with transaction.atomic():
                # Store original values for comparison
                original_mood = getattr(journal_entry, 'mood_rating', None)
                original_stress = getattr(journal_entry, 'stress_level', None)

                # Update the entry
                updated_entry = self._update_journal_entry(journal_entry, update_data)

                # Check if reanalysis is needed
                needs_reanalysis = self._needs_reanalysis(
                    original_mood, original_stress,
                    getattr(updated_entry, 'mood_rating', None),
                    getattr(updated_entry, 'stress_level', None)
                )

                result = {
                    'success': True,
                    'journal_entry': updated_entry,
                    'reanalysis_triggered': needs_reanalysis
                }

                if needs_reanalysis:
                    # Re-trigger analysis
                    analysis = self.pattern_analyzer.analyze_entry_for_immediate_action(updated_entry)
                    result['analysis'] = analysis

                    # Handle any new crisis situations
                    if analysis.get('crisis_detected', False):
                        self._handle_crisis_intervention(updated_entry.user, updated_entry, analysis)

                    # Schedule analytics update
                    self._schedule_analytics_update(updated_entry.user.id, updated_entry.id)

                return result

        except (ValidationError, ValueError) as e:
            logger.error(f"Journal entry update failed for entry {journal_entry.id}: {e}")
            return {
                'success': False,
                'error': str(e),
                'error_type': 'validation_error'
            }

        except DATABASE_EXCEPTIONS as e:
            logger.error(f"Unexpected error updating journal entry {journal_entry.id}: {e}")
            return {
                'success': False,
                'error': 'An unexpected error occurred',
                'error_type': 'system_error'
            }

    def generate_user_analytics_report(self, user, days=30, include_predictions=True):
        """
        Generate comprehensive analytics report for user

        Args:
            user: User object
            days: Number of days to analyze
            include_predictions: Whether to include predictive insights

        Returns:
            dict: Comprehensive analytics report
        """
        logger.info(f"Generating analytics report for user {user.id} ({days} days)")

        try:
            # Generate comprehensive analytics
            analytics = self.analytics_service.generate_comprehensive_analytics(user, days)

            # Add wellbeing score
            wellbeing_score = self.analytics_service.calculate_user_wellbeing_score(user, days)
            analytics['wellbeing_score_detail'] = wellbeing_score

            # Add long-term patterns if sufficient data
            if days >= 90 or include_predictions:
                long_term_patterns = self.analytics_service.analyze_long_term_patterns(user, days)
                analytics['long_term_patterns'] = long_term_patterns

            # Add report metadata
            analytics['report_metadata'] = {
                'generated_at': timezone.now().isoformat(),
                'user_id': str(user.id),
                'user_name': user.peoplename,
                'report_type': 'comprehensive',
                'includes_predictions': include_predictions
            }

            return {
                'success': True,
                'analytics': analytics
            }

        except (ValueError, TypeError, AttributeError) as e:
            logger.error(f"Analytics report generation failed for user {user.id}: {e}")
            return {
                'success': False,
                'error': str(e),
                'error_type': 'analytics_error'
            }

    def bulk_process_entries(self, entries_data, user):
        """
        Process multiple journal entries in bulk (e.g., from mobile sync)

        Args:
            entries_data: List of entry data dicts
            user: User object

        Returns:
            dict: Bulk processing results
        """
        logger.info(f"Bulk processing {len(entries_data)} entries for user {user.id}")

        results = {
            'success': True,
            'processed_count': 0,
            'created_entries': [],
            'updated_entries': [],
            'errors': [],
            'analytics_triggered': False,
            'crisis_interventions': 0
        }

        try:
            with transaction.atomic():
                for entry_data in entries_data:
                    try:
                        # Determine if this is create or update
                        mobile_id = entry_data.get('mobile_id')
                        existing_entry = None

                        if mobile_id:
                            from ..models import JournalEntry
                            existing_entry = JournalEntry.objects.filter(
                                mobile_id=mobile_id,
                                user=user
                            ).first()

                        if existing_entry:
                            # Update existing entry
                            updated_entry = self._update_journal_entry(existing_entry, entry_data)
                            results['updated_entries'].append(updated_entry.id)
                        else:
                            # Create new entry
                            new_entry = self._create_journal_entry(user, entry_data)
                            results['created_entries'].append(new_entry.id)

                            # Check for crisis situations in new entries
                            analysis = self.pattern_analyzer.analyze_entry_for_immediate_action(new_entry)
                            if analysis.get('crisis_detected', False):
                                self._handle_crisis_intervention(user, new_entry, analysis)
                                results['crisis_interventions'] += 1

                        results['processed_count'] += 1

                    except (ValidationError, ValueError) as e:
                        results['errors'].append({
                            'entry_data': entry_data,
                            'error': str(e)
                        })

                # Schedule analytics update for all processed entries
                if results['processed_count'] > 0:
                    self._schedule_analytics_update(user.id, trigger_reason='bulk_sync')
                    results['analytics_triggered'] = True

                return results

        except DATABASE_EXCEPTIONS as e:
            logger.error(f"Bulk processing failed for user {user.id}: {e}")
            results['success'] = False
            results['error'] = str(e)
            return results

    def handle_privacy_settings_change(self, user, old_settings, new_settings):
        """
        Handle changes to user privacy settings

        Args:
            user: User object
            old_settings: Previous privacy settings
            new_settings: New privacy settings

        Returns:
            dict: Privacy update results
        """
        logger.info(f"Handling privacy settings change for user {user.id}")

        try:
            actions_taken = []

            # Check if analytics consent was revoked
            if (old_settings.get('analytics_consent', False) and
                not new_settings.get('analytics_consent', False)):

                # Clear cached analytics data
                self._clear_user_analytics_cache(user.id)
                actions_taken.append('analytics_cache_cleared')

            # Check if data retention period changed
            old_retention = old_settings.get('data_retention_days', 365)
            new_retention = new_settings.get('data_retention_days', 365)

            if new_retention < old_retention:
                # Schedule data cleanup for shorter retention period
                self._schedule_data_cleanup(user.id, new_retention)
                actions_taken.append('data_cleanup_scheduled')

            # Check if crisis intervention consent changed
            if (not old_settings.get('crisis_intervention_consent', False) and
                new_settings.get('crisis_intervention_consent', False)):

                # Retroactively check recent entries for crisis indicators
                self._retroactive_crisis_check(user)
                actions_taken.append('retroactive_crisis_check')

            return {
                'success': True,
                'actions_taken': actions_taken,
                'privacy_impact_assessment': self._assess_privacy_impact(old_settings, new_settings)
            }

        except DATABASE_EXCEPTIONS as e:
            logger.error(f"Privacy settings update failed for user {user.id}: {e}")
            return {
                'success': False,
                'error': str(e)
            }

    def schedule_periodic_wellness_check(self, user):
        """
        Schedule periodic wellness check for user

        Args:
            user: User object

        Returns:
            dict: Scheduling result
        """
        logger.info(f"Scheduling periodic wellness check for user {user.id}")

        try:
            # Generate current wellness summary
            wellness_summary = self.analytics_service.calculate_user_wellbeing_score(user, days=7)

            # Determine check frequency based on current wellness
            if wellness_summary.get('overall_score', 10) < 5:
                check_frequency = 'daily'
            elif wellness_summary.get('overall_score', 10) < 7:
                check_frequency = 'weekly'
            else:
                check_frequency = 'bi_weekly'

            # Schedule the wellness check
            self._schedule_wellness_check(user.id, check_frequency)

            return {
                'success': True,
                'check_frequency': check_frequency,
                'current_wellness_score': wellness_summary.get('overall_score'),
                'next_check_scheduled': True
            }

        except DATABASE_EXCEPTIONS as e:
            logger.error(f"Wellness check scheduling failed for user {user.id}: {e}")
            return {
                'success': False,
                'error': str(e)
            }

    # Private helper methods

    def _create_journal_entry(self, user, entry_data):
        """Create journal entry from data"""
        from ..models import JournalEntry

        # Set defaults
        entry_data['user'] = user
        entry_data['tenant'] = getattr(user, 'tenant', None)

        if not entry_data.get('timestamp'):
            entry_data['timestamp'] = timezone.now()

        # Create the entry
        journal_entry = JournalEntry.objects.create(**entry_data)

        logger.debug(f"Created journal entry {journal_entry.id} for user {user.id}")
        return journal_entry

    def _update_journal_entry(self, journal_entry, update_data):
        """Update journal entry with new data"""
        # Update fields
        for field, value in update_data.items():
            if hasattr(journal_entry, field):
                setattr(journal_entry, field, value)

        # Save with version increment
        if hasattr(journal_entry, 'sync_data') and journal_entry.sync_data:
            journal_entry.sync_data.increment_version()

        journal_entry.save()

        logger.debug(f"Updated journal entry {journal_entry.id}")
        return journal_entry

    def _needs_reanalysis(self, old_mood, old_stress, new_mood, new_stress):
        """Check if entry changes warrant reanalysis"""
        # Reanalyze if mood changed significantly
        if old_mood and new_mood and abs(old_mood - new_mood) >= 2:
            return True

        # Reanalyze if stress changed significantly
        if old_stress and new_stress and abs(old_stress - new_stress) >= 1:
            return True

        # Reanalyze if either metric became concerning
        if (new_mood and new_mood <= 3) or (new_stress and new_stress >= 4):
            return True

        return False

    def _schedule_analytics_update(self, user_id, entry_id=None, trigger_reason='entry_change'):
        """Schedule background analytics update"""
        try:
            # Import here to avoid circular imports
            from ...background_tasks.journal_wellness_tasks import update_user_analytics
            update_user_analytics.delay(user_id, entry_id)
            logger.debug(f"Scheduled analytics update for user {user_id}")
        except ImportError:
            logger.warning("Background tasks not available for analytics update")

    def _handle_crisis_intervention(self, user, journal_entry, analysis):
        """Handle crisis intervention workflow"""
        try:
            # Import here to avoid circular imports
            from ...background_tasks.journal_wellness_tasks import process_crisis_intervention
            process_crisis_intervention.delay(
                user.id,
                journal_entry.id,
                analysis.get('crisis_indicators', [])
            )
            logger.critical(f"Crisis intervention triggered for user {user.id}, entry {journal_entry.id}")
        except ImportError:
            logger.error("Background tasks not available for crisis intervention")

    def _schedule_wellness_content(self, user_id, analysis):
        """Schedule wellness content delivery"""
        try:
            # Import here to avoid circular imports
            from ...background_tasks.journal_wellness_tasks import schedule_wellness_content_delivery
            schedule_wellness_content_delivery.delay(user_id, 'pattern_triggered')
            logger.debug(f"Scheduled wellness content for user {user_id}")
        except ImportError:
            logger.warning("Background tasks not available for wellness content scheduling")

    def _get_actions_taken(self, analysis):
        """Get list of actions taken based on analysis"""
        actions = []

        if analysis.get('crisis_detected', False):
            actions.append('crisis_intervention_triggered')

        if analysis.get('urgency_level') in ['high', 'critical']:
            actions.append('wellness_content_scheduled')

        if analysis.get('follow_up_required', False):
            actions.append('follow_up_scheduled')

        actions.append('analytics_update_scheduled')

        return actions

    def _clear_user_analytics_cache(self, user_id):
        """Clear cached analytics data for user"""
        # TODO: Implement cache clearing logic
        logger.debug(f"Cleared analytics cache for user {user_id}")

    def _schedule_data_cleanup(self, user_id, retention_days):
        """Schedule data cleanup based on retention policy"""
        try:
            # Import here to avoid circular imports
            from ...background_tasks.journal_wellness_tasks import enforce_data_retention_policies
            enforce_data_retention_policies.delay()
            logger.debug(f"Scheduled data cleanup for user {user_id}")
        except ImportError:
            logger.warning("Background tasks not available for data cleanup")

    def _retroactive_crisis_check(self, user):
        """Retroactively check recent entries for crisis indicators"""
        try:
            from ..models import JournalEntry
            recent_entries = JournalEntry.objects.filter(
                user=user,
                timestamp__gte=timezone.now() - timedelta(days=7),
                is_deleted=False
            )

            crisis_count = 0
            for entry in recent_entries:
                analysis = self.pattern_analyzer.analyze_entry_for_immediate_action(entry)
                if analysis.get('crisis_detected', False):
                    self._handle_crisis_intervention(user, entry, analysis)
                    crisis_count += 1

            logger.info(f"Retroactive crisis check for user {user.id}: {crisis_count} interventions triggered")

        except DATABASE_EXCEPTIONS as e:
            logger.error(f"Retroactive crisis check failed for user {user.id}: {e}")

    def _assess_privacy_impact(self, old_settings, new_settings):
        """Assess privacy impact of settings changes"""
        impact = {
            'data_access_changed': False,
            'retention_changed': False,
            'consent_changes': []
        }

        # Check for data access changes
        data_access_fields = ['wellbeing_sharing_consent', 'manager_access_consent', 'analytics_consent']
        for field in data_access_fields:
            if old_settings.get(field) != new_settings.get(field):
                impact['data_access_changed'] = True
                impact['consent_changes'].append(field)

        # Check for retention changes
        if old_settings.get('data_retention_days') != new_settings.get('data_retention_days'):
            impact['retention_changed'] = True

        return impact

    def _schedule_wellness_check(self, user_id, frequency):
        """Schedule periodic wellness check"""
        try:
            # Import here to avoid circular imports
            from ...background_tasks.journal_wellness_tasks import check_wellness_milestones
            check_wellness_milestones.delay(user_id)
            logger.debug(f"Scheduled {frequency} wellness check for user {user_id}")
        except ImportError:
            logger.warning("Background tasks not available for wellness check scheduling")