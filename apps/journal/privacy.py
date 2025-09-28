"""
Privacy Controls and Consent Management System

Enterprise-grade privacy controls for journal data including:
- Granular consent management with audit trails
- Privacy scope enforcement across all operations
- GDPR/HIPAA compliance features
- Data retention and auto-deletion policies
- Privacy violation detection and logging
- Consent withdrawal handling
"""

from django.utils import timezone
from django.core.exceptions import PermissionDenied
from datetime import timedelta
import logging

from apps.journal.models import JournalEntry, JournalPrivacySettings

logger = logging.getLogger(__name__)


class JournalPrivacyManager:
    """
    Comprehensive privacy management for journal data

    Features:
    - Consent validation for all data operations
    - Privacy scope enforcement with tenant awareness
    - Audit logging for privacy-sensitive operations
    - Data retention policy enforcement
    - GDPR right-to-be-forgotten compliance
    """

    def __init__(self):
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

    def check_data_access_permission(self, user, journal_entry, operation='read'):
        """
        Check if user has permission to access journal entry data

        Args:
            user: User requesting access
            journal_entry: JournalEntry object
            operation: Type of operation ('read', 'write', 'delete', 'share')

        Returns:
            dict: Permission result with details

        Raises:
            PermissionDenied: If access is not allowed
        """

        self.logger.debug(f"Checking {operation} permission for user {user.id} on entry {journal_entry.id}")

        # Owner always has full access
        if journal_entry.user == user:
            return {
                'allowed': True,
                'reason': 'owner_access',
                'privacy_scope': journal_entry.privacy_scope
            }

        # Admin users have limited access based on privacy scope
        if user.is_superuser:
            # Even admins cannot access private wellbeing data without explicit consent
            if journal_entry.is_wellbeing_entry and journal_entry.privacy_scope == 'private':
                privacy_settings = self._get_privacy_settings(journal_entry.user)
                if not privacy_settings.analytics_consent:
                    self.logger.warning(f"Admin {user.id} denied access to private wellbeing data for user {journal_entry.user.id}")
                    raise PermissionDenied("Access denied to private wellbeing data without user consent")

            return {
                'allowed': True,
                'reason': 'admin_access',
                'privacy_scope': journal_entry.privacy_scope,
                'audit_required': True
            }

        # Check privacy scope for non-owners
        effective_scope = journal_entry.get_effective_privacy_scope(user)

        if effective_scope == 'private':
            self.logger.info(f"Access denied to private entry {journal_entry.id} for user {user.id}")
            raise PermissionDenied("This journal entry is private")

        elif effective_scope == 'shared':
            if user.id not in journal_entry.sharing_permissions:
                raise PermissionDenied("You are not in the sharing permissions for this entry")

        elif effective_scope == 'manager':
            # TODO: Implement manager relationship checking
            if not self._check_manager_relationship(user, journal_entry.user):
                raise PermissionDenied("You are not the manager of this user")

        elif effective_scope == 'team':
            # TODO: Implement team membership checking
            if not self._check_team_membership(user, journal_entry.user):
                raise PermissionDenied("You are not a team member of this user")

        elif effective_scope == 'aggregate_only':
            if operation != 'aggregate':
                raise PermissionDenied("This entry is only available for aggregated analytics")

        # Log access for audit trail
        self._log_privacy_access(user, journal_entry, operation, 'granted')

        return {
            'allowed': True,
            'reason': f'{effective_scope}_access',
            'privacy_scope': effective_scope,
            'audit_logged': True
        }

    def validate_consent_for_operation(self, user, operation_type, data_types=None):
        """
        Validate user consent for specific data operations

        Args:
            user: User whose data is being processed
            operation_type: Type of operation ('analytics', 'sharing', 'crisis_intervention')
            data_types: List of data types being processed

        Returns:
            dict: Consent validation result
        """

        try:
            privacy_settings = user.journal_privacy_settings
        except JournalPrivacySettings.DoesNotExist:
            self.logger.error(f"No privacy settings found for user {user.id}")
            return {
                'valid': False,
                'reason': 'no_privacy_settings',
                'required_action': 'create_privacy_settings'
            }

        consent_checks = {
            'analytics': privacy_settings.analytics_consent,
            'wellbeing_sharing': privacy_settings.wellbeing_sharing_consent,
            'manager_access': privacy_settings.manager_access_consent,
            'crisis_intervention': privacy_settings.crisis_intervention_consent
        }

        # Check specific operation consent
        if operation_type in consent_checks:
            consent_given = consent_checks[operation_type]

            if not consent_given:
                self.logger.info(f"Consent not given for {operation_type} by user {user.id}")
                return {
                    'valid': False,
                    'reason': f'no_consent_for_{operation_type}',
                    'required_action': 'obtain_consent'
                }

        # Additional checks for wellbeing data
        if data_types and 'wellbeing' in data_types:
            if not privacy_settings.wellbeing_sharing_consent:
                return {
                    'valid': False,
                    'reason': 'no_wellbeing_sharing_consent',
                    'required_action': 'obtain_wellbeing_consent'
                }

        # Log consent usage
        self._log_consent_usage(user, operation_type, data_types)

        return {
            'valid': True,
            'consent_timestamp': privacy_settings.consent_timestamp,
            'last_updated': privacy_settings.updated_at
        }

    def enforce_data_retention_policy(self, user=None):
        """
        Enforce data retention policies and auto-deletion

        Args:
            user: Specific user (if None, applies to all users)

        Returns:
            dict: Retention enforcement results
        """

        self.logger.info(f"Enforcing data retention policies for user {user.id if user else 'all users'}")

        if user:
            users_to_process = [user]
        else:
            # Get all users with auto-delete enabled
            users_to_process = User.objects.filter(
                journal_privacy_settings__auto_delete_enabled=True
            )

        total_deleted = 0
        total_anonymized = 0

        for user_obj in users_to_process:
            try:
                privacy_settings = user_obj.journal_privacy_settings
                retention_days = privacy_settings.data_retention_days

                if privacy_settings.auto_delete_enabled:
                    deleted, anonymized = self._apply_retention_policy(user_obj, retention_days)
                    total_deleted += deleted
                    total_anonymized += anonymized

            except JournalPrivacySettings.DoesNotExist:
                self.logger.warning(f"No privacy settings for user {user_obj.id}")
                continue

        self.logger.info(f"Retention policy enforcement complete: {total_deleted} deleted, {total_anonymized} anonymized")

        return {
            'users_processed': len(users_to_process),
            'entries_deleted': total_deleted,
            'entries_anonymized': total_anonymized,
            'processed_at': timezone.now()
        }

    def handle_consent_withdrawal(self, user, consent_types):
        """
        Handle user withdrawal of consent for data processing

        Args:
            user: User withdrawing consent
            consent_types: List of consent types being withdrawn

        Returns:
            dict: Consent withdrawal processing results
        """

        self.logger.warning(f"Processing consent withdrawal for user {user.id}: {consent_types}")

        try:
            privacy_settings = user.journal_privacy_settings

            actions_taken = []

            # Update consent flags
            for consent_type in consent_types:
                if consent_type == 'analytics':
                    privacy_settings.analytics_consent = False
                    actions_taken.append('disabled_analytics_processing')

                elif consent_type == 'wellbeing_sharing':
                    privacy_settings.wellbeing_sharing_consent = False
                    # Anonymize or delete shared wellbeing data
                    self._anonymize_shared_wellbeing_data(user)
                    actions_taken.append('anonymized_shared_wellbeing_data')

                elif consent_type == 'manager_access':
                    privacy_settings.manager_access_consent = False
                    # Remove manager access permissions
                    self._revoke_manager_access(user)
                    actions_taken.append('revoked_manager_access')

                elif consent_type == 'crisis_intervention':
                    privacy_settings.crisis_intervention_consent = False
                    actions_taken.append('disabled_crisis_intervention')

            privacy_settings.save()

            # Log consent withdrawal for audit trail
            self._log_consent_withdrawal(user, consent_types, actions_taken)

            return {
                'success': True,
                'consent_types_withdrawn': consent_types,
                'actions_taken': actions_taken,
                'withdrawal_timestamp': timezone.now()
            }

        except (DatabaseError, IntegrityError, ObjectDoesNotExist, TypeError, ValidationError, ValueError) as e:
            self.logger.error(f"Failed to process consent withdrawal for user {user.id}: {e}")
            return {
                'success': False,
                'error': str(e),
                'partial_actions': []
            }

    def generate_privacy_report(self, user):
        """
        Generate comprehensive privacy report for user (GDPR compliance)

        Args:
            user: User to generate report for

        Returns:
            dict: Complete privacy and data usage report
        """

        self.logger.info(f"Generating privacy report for user {user.id}")

        try:
            privacy_settings = user.journal_privacy_settings

            # Get all user's journal data
            journal_entries = JournalEntry.objects.filter(user=user, is_deleted=False)

            # Get wellness interactions
            from apps.wellness.models import WellnessContentInteraction
            wellness_interactions = WellnessContentInteraction.objects.filter(user=user)

            report = {
                'user_information': {
                    'user_id': str(user.id),
                    'user_name': user.peoplename,
                    'tenant': user.tenant.tenantname if user.tenant else None,
                    'report_generated': timezone.now().isoformat()
                },
                'privacy_settings': {
                    'default_privacy_scope': privacy_settings.default_privacy_scope,
                    'consents': {
                        'wellbeing_sharing': privacy_settings.wellbeing_sharing_consent,
                        'manager_access': privacy_settings.manager_access_consent,
                        'analytics': privacy_settings.analytics_consent,
                        'crisis_intervention': privacy_settings.crisis_intervention_consent
                    },
                    'data_retention_days': privacy_settings.data_retention_days,
                    'auto_delete_enabled': privacy_settings.auto_delete_enabled,
                    'consent_given': privacy_settings.consent_timestamp.isoformat()
                },
                'data_summary': {
                    'total_journal_entries': journal_entries.count(),
                    'wellbeing_entries': journal_entries.filter(
                        entry_type__in=['MOOD_CHECK_IN', 'STRESS_LOG', 'PERSONAL_REFLECTION']
                    ).count(),
                    'private_entries': journal_entries.filter(privacy_scope='private').count(),
                    'shared_entries': journal_entries.filter(privacy_scope='shared').count(),
                    'wellness_interactions': wellness_interactions.count(),
                    'date_range': {
                        'first_entry': journal_entries.first().created_at.isoformat() if journal_entries.exists() else None,
                        'last_entry': journal_entries.last().created_at.isoformat() if journal_entries.exists() else None
                    }
                },
                'data_usage': {
                    'analytics_processing': privacy_settings.analytics_consent,
                    'pattern_recognition': privacy_settings.crisis_intervention_consent,
                    'wellness_personalization': privacy_settings.analytics_consent,
                    'crisis_monitoring': privacy_settings.crisis_intervention_consent
                },
                'third_party_sharing': {
                    'manager_access': privacy_settings.manager_access_consent,
                    'team_sharing': journal_entries.filter(privacy_scope='team').exists(),
                    'aggregated_analytics': privacy_settings.analytics_consent
                },
                'rights_and_controls': {
                    'right_to_access': 'Available via API endpoints',
                    'right_to_rectification': 'Available via update endpoints',
                    'right_to_erasure': 'Available via delete endpoints and auto-deletion',
                    'right_to_portability': 'Available via export endpoints',
                    'right_to_withdraw_consent': 'Available via privacy settings updates'
                }
            }

            return report

        except (DatabaseError, IntegrityError, ObjectDoesNotExist, TypeError, ValidationError, ValueError) as e:
            self.logger.error(f"Failed to generate privacy report for user {user.id}: {e}")
            return {
                'error': 'Failed to generate privacy report',
                'user_id': str(user.id),
                'generated_at': timezone.now().isoformat()
            }

    def export_user_data(self, user, format='json'):
        """
        Export all user data for portability (GDPR Article 20)

        Args:
            user: User requesting data export
            format: Export format ('json', 'csv')

        Returns:
            dict: Complete user data export
        """

        self.logger.info(f"Exporting user data for {user.id} in {format} format")

        try:
            # Get all user's data
            journal_entries = JournalEntry.objects.filter(user=user).order_by('timestamp')
            privacy_settings = user.journal_privacy_settings

            from apps.wellness.models import WellnessContentInteraction, WellnessUserProgress
            wellness_interactions = WellnessContentInteraction.objects.filter(user=user).order_by('interaction_date')

            try:
                wellness_progress = user.wellness_progress
            except WellnessUserProgress.DoesNotExist:
                wellness_progress = None

            export_data = {
                'export_metadata': {
                    'user_id': str(user.id),
                    'export_timestamp': timezone.now().isoformat(),
                    'export_format': format,
                    'data_version': '1.0'
                },
                'user_profile': {
                    'name': user.peoplename,
                    'email': user.email,
                    'login_id': user.loginid,
                    'tenant': user.tenant.tenantname if user.tenant else None
                },
                'privacy_settings': {
                    'default_privacy_scope': privacy_settings.default_privacy_scope,
                    'wellbeing_sharing_consent': privacy_settings.wellbeing_sharing_consent,
                    'manager_access_consent': privacy_settings.manager_access_consent,
                    'analytics_consent': privacy_settings.analytics_consent,
                    'crisis_intervention_consent': privacy_settings.crisis_intervention_consent,
                    'data_retention_days': privacy_settings.data_retention_days,
                    'consent_timestamp': privacy_settings.consent_timestamp.isoformat()
                },
                'journal_entries': [
                    {
                        'id': str(entry.id),
                        'title': entry.title,
                        'content': entry.content,
                        'entry_type': entry.entry_type,
                        'timestamp': entry.timestamp.isoformat(),
                        'mood_rating': entry.mood_rating,
                        'stress_level': entry.stress_level,
                        'energy_level': entry.energy_level,
                        'gratitude_items': entry.gratitude_items,
                        'achievements': entry.achievements,
                        'location_site_name': entry.location_site_name,
                        'tags': entry.tags,
                        'privacy_scope': entry.privacy_scope,
                        'created_at': entry.created_at.isoformat()
                    }
                    for entry in journal_entries
                ],
                'wellness_data': {
                    'progress': {
                        'current_streak': wellness_progress.current_streak if wellness_progress else 0,
                        'total_content_viewed': wellness_progress.total_content_viewed if wellness_progress else 0,
                        'achievements_earned': wellness_progress.achievements_earned if wellness_progress else [],
                        'preferred_content_level': wellness_progress.preferred_content_level if wellness_progress else None
                    } if wellness_progress else None,
                    'interactions': [
                        {
                            'content_title': interaction.content.title,
                            'interaction_type': interaction.interaction_type,
                            'user_rating': interaction.user_rating,
                            'action_taken': interaction.action_taken,
                            'interaction_date': interaction.interaction_date.isoformat()
                        }
                        for interaction in wellness_interactions
                    ]
                }
            }

            # Log data export for audit
            self._log_data_export(user, format, len(journal_entries), len(wellness_interactions))

            return export_data

        except (DatabaseError, IntegrityError, ObjectDoesNotExist, TypeError, ValidationError, ValueError) as e:
            self.logger.error(f"Failed to export data for user {user.id}: {e}")
            raise

    def anonymize_user_data(self, user, preserve_analytics=False):
        """
        Anonymize user data while preserving analytics value

        Args:
            user: User whose data should be anonymized
            preserve_analytics: Whether to preserve data for analytics in anonymized form

        Returns:
            dict: Anonymization results
        """

        self.logger.warning(f"Anonymizing data for user {user.id} (preserve_analytics={preserve_analytics})")

        try:
            anonymized_data = {
                'journal_entries': 0,
                'wellness_interactions': 0,
                'media_attachments': 0
            }

            # Anonymize journal entries
            journal_entries = JournalEntry.objects.filter(user=user)

            for entry in journal_entries:
                if preserve_analytics:
                    # Remove personally identifiable information but keep metrics
                    entry.title = f"[Anonymized Entry {entry.id}]"
                    entry.content = "[Content removed for privacy]"
                    entry.location_site_name = "[Location anonymized]"
                    entry.location_address = ""
                    entry.team_members = []
                    entry.gratitude_items = []
                    entry.affirmations = []
                    entry.achievements = []
                    entry.learnings = []
                    # Keep mood, stress, energy for analytics
                    entry.save()
                else:
                    # Complete deletion
                    entry.delete()

                anonymized_data['journal_entries'] += 1

            # Anonymize wellness interactions
            from apps.wellness.models import WellnessContentInteraction
            wellness_interactions = WellnessContentInteraction.objects.filter(user=user)

            for interaction in wellness_interactions:
                if preserve_analytics:
                    # Keep engagement metrics but remove personal data
                    interaction.user_feedback = "[Feedback removed for privacy]"
                    interaction.save()
                else:
                    interaction.delete()

                anonymized_data['wellness_interactions'] += 1

            # Handle media attachments
            from apps.journal.models import JournalMediaAttachment
            media_attachments = JournalMediaAttachment.objects.filter(
                journal_entry__user=user
            )

            for attachment in media_attachments:
                # Always delete media files for privacy
                if attachment.file:
                    attachment.file.delete()
                attachment.delete()
                anonymized_data['media_attachments'] += 1

            # Log anonymization
            self._log_data_anonymization(user, anonymized_data, preserve_analytics)

            return {
                'success': True,
                'anonymized_data': anonymized_data,
                'preserve_analytics': preserve_analytics,
                'anonymized_at': timezone.now()
            }

        except (DatabaseError, IntegrityError, ObjectDoesNotExist, TypeError, ValidationError, ValueError) as e:
            self.logger.error(f"Failed to anonymize data for user {user.id}: {e}")
            raise

    def check_privacy_compliance(self, tenant=None):
        """
        Check privacy compliance across the system

        Args:
            tenant: Specific tenant to check (if None, checks all)

        Returns:
            dict: Compliance report
        """

        self.logger.info(f"Running privacy compliance check for tenant {tenant.id if tenant else 'all'}")

        compliance_issues = []
        recommendations = []

        # Check for users without privacy settings
        users_without_settings = User.objects.exclude(
            id__in=JournalPrivacySettings.objects.values_list('user_id', flat=True)
        )

        if tenant:
            users_without_settings = users_without_settings.filter(tenant=tenant)

        if users_without_settings.exists():
            compliance_issues.append({
                'type': 'missing_privacy_settings',
                'count': users_without_settings.count(),
                'severity': 'high',
                'description': 'Users without privacy settings found'
            })
            recommendations.append('Create privacy settings for all users via management command')

        # Check for overdue data retention
        overdue_data = self._check_overdue_data_retention(tenant)
        if overdue_data['overdue_count'] > 0:
            compliance_issues.append({
                'type': 'overdue_data_retention',
                'count': overdue_data['overdue_count'],
                'severity': 'medium',
                'description': 'Data past retention period found'
            })
            recommendations.append('Run data retention cleanup command')

        # Check for privacy scope violations
        privacy_violations = self._check_privacy_scope_violations(tenant)
        if privacy_violations:
            compliance_issues.append({
                'type': 'privacy_scope_violations',
                'violations': privacy_violations,
                'severity': 'high',
                'description': 'Privacy scope violations detected'
            })

        return {
            'compliance_status': 'compliant' if not compliance_issues else 'issues_found',
            'issues': compliance_issues,
            'recommendations': recommendations,
            'checked_at': timezone.now(),
            'tenant': tenant.tenantname if tenant else 'all_tenants'
        }

    # Helper methods

    def _get_privacy_settings(self, user):
        """Get user's privacy settings, creating if necessary"""
        try:
            return user.journal_privacy_settings
        except JournalPrivacySettings.DoesNotExist:
            return JournalPrivacySettings.objects.create(
                user=user,
                consent_timestamp=timezone.now()
            )

    def _check_manager_relationship(self, manager, employee):
        """Check if user is manager of another user"""
        # TODO: Implement based on your org structure
        # This would check against your existing People/Department relationships
        return False  # Placeholder

    def _check_team_membership(self, user1, user2):
        """Check if users are on the same team"""
        # TODO: Implement based on your team structure
        # This would check against your existing team/department relationships
        return False  # Placeholder

    def _apply_retention_policy(self, user, retention_days):
        """Apply data retention policy for specific user"""
        cutoff_date = timezone.now() - timedelta(days=retention_days)

        # Get entries past retention period
        old_entries = JournalEntry.objects.filter(
            user=user,
            created_at__lt=cutoff_date
        )

        deleted_count = 0
        anonymized_count = 0

        for entry in old_entries:
            if entry.is_wellbeing_entry:
                # Delete wellbeing entries completely for privacy
                entry.delete()
                deleted_count += 1
            else:
                # Anonymize work entries to preserve business insights
                entry.content = "[Content removed per retention policy]"
                entry.title = f"[Anonymized Entry - {entry.entry_type}]"
                entry.save()
                anonymized_count += 1

        return deleted_count, anonymized_count

    def _anonymize_shared_wellbeing_data(self, user):
        """Anonymize shared wellbeing data when consent is withdrawn"""
        shared_wellbeing_entries = JournalEntry.objects.filter(
            user=user,
            privacy_scope__in=['shared', 'team', 'manager'],
            entry_type__in=['MOOD_CHECK_IN', 'STRESS_LOG', 'PERSONAL_REFLECTION']
        )

        for entry in shared_wellbeing_entries:
            entry.privacy_scope = 'private'
            entry.sharing_permissions = []
            entry.save()

    def _revoke_manager_access(self, user):
        """Revoke manager access to user's entries"""
        manager_accessible_entries = JournalEntry.objects.filter(
            user=user,
            privacy_scope='manager'
        )

        manager_accessible_entries.update(privacy_scope='private')

    def _check_overdue_data_retention(self, tenant):
        """Check for data past retention period"""
        # Get users with auto-delete enabled
        users_with_retention = User.objects.filter(
            journal_privacy_settings__auto_delete_enabled=True
        )

        if tenant:
            users_with_retention = users_with_retention.filter(tenant=tenant)

        overdue_count = 0

        for user in users_with_retention:
            privacy_settings = user.journal_privacy_settings
            cutoff_date = timezone.now() - timedelta(days=privacy_settings.data_retention_days)

            overdue_entries = JournalEntry.objects.filter(
                user=user,
                created_at__lt=cutoff_date
            ).count()

            overdue_count += overdue_entries

        return {
            'overdue_count': overdue_count,
            'users_checked': users_with_retention.count()
        }

    def _check_privacy_scope_violations(self, tenant):
        """Check for privacy scope violations"""
        violations = []

        # Check for wellbeing entries with non-private scope
        problematic_entries = JournalEntry.objects.filter(
            entry_type__in=['MOOD_CHECK_IN', 'STRESS_LOG', 'PERSONAL_REFLECTION'],
            privacy_scope__in=['shared', 'team', 'manager']
        )

        if tenant:
            problematic_entries = problematic_entries.filter(tenant=tenant)

        if problematic_entries.exists():
            violations.append({
                'type': 'wellbeing_data_not_private',
                'count': problematic_entries.count(),
                'description': 'Wellbeing entries with non-private scope found'
            })

        return violations

    def _log_privacy_access(self, user, journal_entry, operation, result):
        """Log privacy-sensitive access for audit trail"""
        # TODO: Implement comprehensive audit logging
        self.logger.info(
            f"PRIVACY ACCESS: User {user.id} {operation} entry {journal_entry.id} - {result}"
        )

    def _log_consent_usage(self, user, operation_type, data_types):
        """Log consent usage for audit trail"""
        self.logger.info(
            f"CONSENT USAGE: User {user.id} consent used for {operation_type} on {data_types}"
        )

    def _log_consent_withdrawal(self, user, consent_types, actions_taken):
        """Log consent withdrawal for audit trail"""
        self.logger.warning(
            f"CONSENT WITHDRAWAL: User {user.id} withdrew {consent_types}, actions: {actions_taken}"
        )

    def _log_data_export(self, user, format, journal_count, wellness_count):
        """Log data export for audit trail"""
        self.logger.info(
            f"DATA EXPORT: User {user.id} exported {journal_count} journal entries "
            f"and {wellness_count} wellness interactions in {format} format"
        )

    def _log_data_anonymization(self, user, anonymized_data, preserve_analytics):
        """Log data anonymization for audit trail"""
        self.logger.warning(
            f"DATA ANONYMIZATION: User {user.id} data anonymized "
            f"(preserve_analytics={preserve_analytics}): {anonymized_data}"
        )


class ConsentManager:
    """
    Specialized consent management for complex consent scenarios

    Features:
    - Granular consent tracking
    - Consent versioning and updates
    - Automatic consent validation
    - Consent withdrawal processing
    - Compliance reporting
    """

    def __init__(self):
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

    def request_consent(self, user, consent_types, purpose_description):
        """
        Request specific consent from user

        Args:
            user: User to request consent from
            consent_types: List of consent types needed
            purpose_description: Clear description of how data will be used

        Returns:
            dict: Consent request details
        """

        self.logger.info(f"Requesting consent from user {user.id} for {consent_types}")

        try:
            privacy_settings = user.journal_privacy_settings
        except JournalPrivacySettings.DoesNotExist:
            privacy_settings = JournalPrivacySettings.objects.create(
                user=user,
                consent_timestamp=timezone.now()
            )

        # Generate consent request
        consent_request = {
            'user_id': str(user.id),
            'consent_types': consent_types,
            'purpose_description': purpose_description,
            'current_consents': {
                'wellbeing_sharing': privacy_settings.wellbeing_sharing_consent,
                'manager_access': privacy_settings.manager_access_consent,
                'analytics': privacy_settings.analytics_consent,
                'crisis_intervention': privacy_settings.crisis_intervention_consent
            },
            'consent_implications': self._generate_consent_implications(consent_types),
            'withdrawal_process': 'Consent can be withdrawn at any time via privacy settings',
            'request_timestamp': timezone.now().isoformat()
        }

        return consent_request

    def process_consent_response(self, user, consent_responses):
        """
        Process user's consent responses

        Args:
            user: User giving consent
            consent_responses: Dict of consent type -> boolean responses

        Returns:
            dict: Processing results
        """

        self.logger.info(f"Processing consent responses from user {user.id}: {consent_responses}")

        try:
            privacy_settings = user.journal_privacy_settings

            for consent_type, granted in consent_responses.items():
                if consent_type == 'wellbeing_sharing':
                    privacy_settings.wellbeing_sharing_consent = granted
                elif consent_type == 'manager_access':
                    privacy_settings.manager_access_consent = granted
                elif consent_type == 'analytics':
                    privacy_settings.analytics_consent = granted
                elif consent_type == 'crisis_intervention':
                    privacy_settings.crisis_intervention_consent = granted

            privacy_settings.save()

            # Log consent changes
            self._log_consent_changes(user, consent_responses)

            return {
                'success': True,
                'updated_consents': consent_responses,
                'updated_at': timezone.now()
            }

        except (DatabaseError, IntegrityError, ObjectDoesNotExist, TypeError, ValidationError, ValueError) as e:
            self.logger.error(f"Failed to process consent for user {user.id}: {e}")
            return {
                'success': False,
                'error': str(e)
            }

    def _generate_consent_implications(self, consent_types):
        """Generate clear explanations of what each consent allows"""
        implications = {}

        consent_descriptions = {
            'wellbeing_sharing': 'Allows sharing anonymized wellbeing metrics for workplace wellness programs',
            'manager_access': 'Allows your direct manager to see work-related journal entries (not personal wellbeing data)',
            'analytics': 'Allows anonymous analysis of your data to improve wellness recommendations',
            'crisis_intervention': 'Allows the system to alert appropriate personnel if crisis indicators are detected'
        }

        for consent_type in consent_types:
            if consent_type in consent_descriptions:
                implications[consent_type] = consent_descriptions[consent_type]

        return implications

    def _log_consent_changes(self, user, consent_responses):
        """Log consent changes for audit trail"""
        for consent_type, granted in consent_responses.items():
            action = 'granted' if granted else 'withdrawn'
            self.logger.info(f"CONSENT CHANGE: User {user.id} {action} {consent_type} consent")


# Convenience functions for use throughout the application

def check_journal_access(user, journal_entry, operation='read'):
    """Convenience function to check journal access permissions"""
    privacy_manager = JournalPrivacyManager()
    return privacy_manager.check_data_access_permission(user, journal_entry, operation)


def validate_user_consent(user, operation_type, data_types=None):
    """Convenience function to validate user consent"""
    privacy_manager = JournalPrivacyManager()
    return privacy_manager.validate_consent_for_operation(user, operation_type, data_types)


def process_consent_withdrawal(user, consent_types):
    """Convenience function to process consent withdrawal"""
    privacy_manager = JournalPrivacyManager()
    return privacy_manager.handle_consent_withdrawal(user, consent_types)


def generate_user_privacy_report(user):
    """Convenience function to generate privacy report"""
    privacy_manager = JournalPrivacyManager()
    return privacy_manager.generate_privacy_report(user)


def export_user_data_for_portability(user, format='json'):
    """Convenience function for data portability"""
    privacy_manager = JournalPrivacyManager()
    return privacy_manager.export_user_data(user, format)