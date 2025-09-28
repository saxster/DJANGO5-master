"""
Journal Data Migration Management Command

Comprehensive data migration tools for journal and wellness system:
- Migrate existing data from other systems
- Bulk import journal entries with validation
- Export user data for compliance (GDPR)
- Data cleanup and maintenance operations
- Privacy compliance verification
"""

from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta
import json
import csv
import logging

from apps.journal.models import JournalEntry, JournalPrivacySettings
from apps.tenants.models import Tenant
from apps.journal.privacy import JournalPrivacyManager

User = get_user_model()
logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Migrate and manage journal data with privacy compliance'

    def add_arguments(self, parser):
        parser.add_argument(
            '--operation',
            type=str,
            choices=['import', 'export', 'cleanup', 'validate', 'anonymize'],
            required=True,
            help='Migration operation to perform',
        )
        parser.add_argument(
            '--tenant',
            type=str,
            help='Tenant subdomain to process (default: all tenants)',
        )
        parser.add_argument(
            '--user-id',
            type=str,
            help='Specific user ID to process',
        )
        parser.add_argument(
            '--input-file',
            type=str,
            help='Input file for import operations',
        )
        parser.add_argument(
            '--output-file',
            type=str,
            help='Output file for export operations',
        )
        parser.add_argument(
            '--format',
            type=str,
            choices=['json', 'csv'],
            default='json',
            help='Data format for import/export',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Perform dry run without making changes',
        )
        parser.add_argument(
            '--preserve-analytics',
            action='store_true',
            help='Preserve analytics data during anonymization',
        )

    def handle(self, *args, **options):
        """Main command handler"""
        operation = options['operation']

        self.stdout.write(
            self.style.SUCCESS(f'🔄 Starting journal data {operation} operation...')
        )

        try:
            if operation == 'import':
                result = self._handle_import(options)
            elif operation == 'export':
                result = self._handle_export(options)
            elif operation == 'cleanup':
                result = self._handle_cleanup(options)
            elif operation == 'validate':
                result = self._handle_validate(options)
            elif operation == 'anonymize':
                result = self._handle_anonymize(options)

            self._display_results(operation, result)

        except (FileNotFoundError, IOError, OSError, PermissionError, TypeError, ValidationError, ValueError) as e:
            self.stdout.write(self.style.ERROR(f'Operation failed: {e}'))
            raise

    def _handle_import(self, options):
        """Handle data import operations"""
        input_file = options.get('input_file')
        if not input_file:
            raise CommandError('--input-file required for import operation')

        tenant = self._get_tenant(options.get('tenant'))
        format_type = options.get('format', 'json')
        dry_run = options.get('dry_run', False)

        self.stdout.write(f'📥 Importing journal data from {input_file} ({format_type} format)')

        try:
            if format_type == 'json':
                result = self._import_json_data(input_file, tenant, dry_run)
            elif format_type == 'csv':
                result = self._import_csv_data(input_file, tenant, dry_run)

            return result

        except (FileNotFoundError, IOError, OSError, PermissionError, TypeError, ValidationError, ValueError) as e:
            logger.error(f"Data import failed: {e}")
            raise

    def _handle_export(self, options):
        """Handle data export operations"""
        output_file = options.get('output_file')
        if not output_file:
            raise CommandError('--output-file required for export operation')

        user_id = options.get('user_id')
        tenant = self._get_tenant(options.get('tenant'))
        format_type = options.get('format', 'json')

        self.stdout.write(f'📤 Exporting journal data to {output_file} ({format_type} format)')

        try:
            if user_id:
                # Export specific user's data
                user = User.objects.get(id=user_id)
                result = self._export_user_data(user, output_file, format_type)
            elif tenant:
                # Export tenant data
                result = self._export_tenant_data(tenant, output_file, format_type)
            else:
                # Export all data
                result = self._export_all_data(output_file, format_type)

            return result

        except (DatabaseError, FileNotFoundError, IOError, IntegrityError, OSError, ObjectDoesNotExist, PermissionError, TypeError, ValidationError, ValueError) as e:
            logger.error(f"Data export failed: {e}")
            raise

    def _handle_cleanup(self, options):
        """Handle data cleanup operations"""
        tenant = self._get_tenant(options.get('tenant'))
        dry_run = options.get('dry_run', False)

        self.stdout.write('🧹 Performing data cleanup operations...')

        try:
            privacy_manager = JournalPrivacyManager()

            if tenant:
                # Cleanup for specific tenant
                result = self._cleanup_tenant_data(tenant, dry_run, privacy_manager)
            else:
                # Cleanup for all tenants
                result = self._cleanup_all_data(dry_run, privacy_manager)

            return result

        except (DatabaseError, FileNotFoundError, IOError, IntegrityError, OSError, ObjectDoesNotExist, PermissionError, TypeError, ValidationError, ValueError) as e:
            logger.error(f"Data cleanup failed: {e}")
            raise

    def _handle_validate(self, options):
        """Handle data validation operations"""
        tenant = self._get_tenant(options.get('tenant'))

        self.stdout.write('🔍 Validating journal data integrity...')

        try:
            validation_result = self._validate_data_integrity(tenant)
            return validation_result

        except (DatabaseError, FileNotFoundError, IOError, IntegrityError, OSError, ObjectDoesNotExist, PermissionError, TypeError, ValidationError, ValueError) as e:
            logger.error(f"Data validation failed: {e}")
            raise

    def _handle_anonymize(self, options):
        """Handle data anonymization operations"""
        user_id = options.get('user_id')
        if not user_id:
            raise CommandError('--user-id required for anonymize operation')

        preserve_analytics = options.get('preserve_analytics', False)
        dry_run = options.get('dry_run', False)

        self.stdout.write(f'🔒 Anonymizing data for user {user_id}...')

        try:
            user = User.objects.get(id=user_id)
            privacy_manager = JournalPrivacyManager()

            if dry_run:
                # Simulate anonymization
                result = self._simulate_anonymization(user, preserve_analytics)
            else:
                # Perform actual anonymization
                result = privacy_manager.anonymize_user_data(user, preserve_analytics)

            return result

        except User.DoesNotExist:
            raise CommandError(f'User {user_id} not found')
        except (DatabaseError, FileNotFoundError, IOError, IntegrityError, OSError, ObjectDoesNotExist, PermissionError, TypeError, ValidationError, ValueError) as e:
            logger.error(f"Data anonymization failed: {e}")
            raise

    def _import_json_data(self, input_file, tenant, dry_run):
        """Import journal data from JSON file"""
        imported_count = 0
        error_count = 0
        errors = []

        try:
            with open(input_file, 'r') as f:
                data = json.load(f)

            journal_entries = data.get('journal_entries', [])

            for entry_data in journal_entries:
                try:
                    if dry_run:
                        # Validate without creating
                        self._validate_entry_data(entry_data, tenant)
                        imported_count += 1
                    else:
                        # Create entry
                        self._create_entry_from_import(entry_data, tenant)
                        imported_count += 1

                except (FileNotFoundError, IOError, OSError, PermissionError, TypeError, ValidationError, ValueError) as e:
                    error_count += 1
                    errors.append({
                        'entry_title': entry_data.get('title', 'Unknown'),
                        'error': str(e)
                    })

            return {
                'success': error_count == 0,
                'imported_count': imported_count,
                'error_count': error_count,
                'errors': errors[:10],  # First 10 errors
                'dry_run': dry_run
            }

        except FileNotFoundError:
            raise CommandError(f'Input file {input_file} not found')

    def _export_user_data(self, user, output_file, format_type):
        """Export specific user's data"""
        try:
            privacy_manager = JournalPrivacyManager()
            user_data = privacy_manager.export_user_data(user, format_type)

            if format_type == 'json':
                with open(output_file, 'w') as f:
                    json.dump(user_data, f, indent=2, default=str)
            elif format_type == 'csv':
                self._export_user_data_csv(user_data, output_file)

            return {
                'success': True,
                'user_id': str(user.id),
                'user_name': user.peoplename,
                'journal_entries': len(user_data.get('journal_entries', [])),
                'wellness_interactions': len(user_data.get('wellness_data', {}).get('interactions', [])),
                'output_file': output_file
            }

        except (DatabaseError, FileNotFoundError, IOError, IntegrityError, OSError, ObjectDoesNotExist, PermissionError, TypeError, ValidationError, ValueError) as e:
            logger.error(f"User data export failed: {e}")
            raise

    def _cleanup_tenant_data(self, tenant, dry_run, privacy_manager):
        """Cleanup data for specific tenant"""
        cleanup_results = {
            'tenant_name': tenant.tenantname,
            'operations': []
        }

        # Cleanup old journal entries based on retention policies
        old_entries = JournalEntry.objects.filter(
            user__tenant=tenant,
            created_at__lt=timezone.now() - timedelta(days=365)
        )

        if dry_run:
            cleanup_results['operations'].append({
                'type': 'old_entries_cleanup',
                'count_to_process': old_entries.count(),
                'dry_run': True
            })
        else:
            deleted_count = old_entries.count()
            old_entries.delete()
            cleanup_results['operations'].append({
                'type': 'old_entries_cleanup',
                'deleted_count': deleted_count
            })

        # Cleanup old wellness interactions
        old_interactions = WellnessContentInteraction.objects.filter(
            user__tenant=tenant,
            interaction_date__lt=timezone.now() - timedelta(days=365)
        )

        if dry_run:
            cleanup_results['operations'].append({
                'type': 'old_interactions_cleanup',
                'count_to_process': old_interactions.count(),
                'dry_run': True
            })
        else:
            deleted_count = old_interactions.count()
            old_interactions.delete()
            cleanup_results['operations'].append({
                'type': 'old_interactions_cleanup',
                'deleted_count': deleted_count
            })

        return cleanup_results

    def _validate_data_integrity(self, tenant):
        """Validate data integrity for tenant"""
        validation_results = {
            'validation_timestamp': timezone.now().isoformat(),
            'checks': []
        }

        # Check for orphaned records
        orphaned_media = self._check_orphaned_media(tenant)
        validation_results['checks'].append(orphaned_media)

        # Check privacy settings consistency
        privacy_consistency = self._check_privacy_consistency(tenant)
        validation_results['checks'].append(privacy_consistency)

        # Check data retention compliance
        retention_compliance = self._check_retention_compliance(tenant)
        validation_results['checks'].append(retention_compliance)

        # Check foreign key integrity
        fk_integrity = self._check_foreign_key_integrity(tenant)
        validation_results['checks'].append(fk_integrity)

        # Overall validation status
        all_passed = all(check.get('passed', False) for check in validation_results['checks'])
        validation_results['overall_status'] = 'passed' if all_passed else 'issues_found'

        return validation_results

    def _check_orphaned_media(self, tenant):
        """Check for orphaned media attachments"""
        from apps.journal.models import JournalMediaAttachment

        orphaned_media = JournalMediaAttachment.objects.filter(
            journal_entry__user__tenant=tenant,
            journal_entry__is_deleted=True
        )

        return {
            'check_name': 'orphaned_media_attachments',
            'passed': orphaned_media.count() == 0,
            'orphaned_count': orphaned_media.count(),
            'description': 'Check for media attachments linked to deleted journal entries'
        }

    def _check_privacy_consistency(self, tenant):
        """Check privacy settings consistency"""
        tenant_users = User.objects.filter(tenant=tenant)
        users_without_privacy = tenant_users.exclude(
            id__in=JournalPrivacySettings.objects.values_list('user_id', flat=True)
        )

        # Check for wellbeing entries with non-private scope
        problematic_entries = JournalEntry.objects.filter(
            user__tenant=tenant,
            entry_type__in=['MOOD_CHECK_IN', 'STRESS_LOG', 'PERSONAL_REFLECTION'],
            privacy_scope__in=['shared', 'team', 'manager']
        )

        return {
            'check_name': 'privacy_consistency',
            'passed': users_without_privacy.count() == 0 and problematic_entries.count() == 0,
            'users_without_privacy': users_without_privacy.count(),
            'problematic_wellbeing_entries': problematic_entries.count(),
            'description': 'Check privacy settings consistency and wellbeing data protection'
        }

    def _check_retention_compliance(self, tenant):
        """Check data retention compliance"""
        users_with_auto_delete = User.objects.filter(
            tenant=tenant,
            journal_privacy_settings__auto_delete_enabled=True
        )

        overdue_entries = 0
        for user in users_with_auto_delete:
            privacy_settings = user.journal_privacy_settings
            cutoff_date = timezone.now() - timedelta(days=privacy_settings.data_retention_days)

            user_overdue = JournalEntry.objects.filter(
                user=user,
                created_at__lt=cutoff_date,
                is_deleted=False
            ).count()

            overdue_entries += user_overdue

        return {
            'check_name': 'data_retention_compliance',
            'passed': overdue_entries == 0,
            'users_with_auto_delete': users_with_auto_delete.count(),
            'overdue_entries': overdue_entries,
            'description': 'Check compliance with user data retention preferences'
        }

    def _check_foreign_key_integrity(self, tenant):
        """Check foreign key integrity"""
        # Check for journal entries with invalid user references
        invalid_user_refs = JournalEntry.objects.filter(
            user__tenant=tenant,
            user__isnull=True
        )

        # Check for wellness interactions with invalid content references
        invalid_content_refs = WellnessContentInteraction.objects.filter(
            user__tenant=tenant,
            content__isnull=True
        )

        return {
            'check_name': 'foreign_key_integrity',
            'passed': invalid_user_refs.count() == 0 and invalid_content_refs.count() == 0,
            'invalid_user_references': invalid_user_refs.count(),
            'invalid_content_references': invalid_content_refs.count(),
            'description': 'Check foreign key relationships are valid'
        }

    def _create_entry_from_import(self, entry_data, tenant):
        """Create journal entry from import data"""
        # Get user
        user_id = entry_data.get('user_id')
        if not user_id:
            raise ValueError('user_id required in entry data')

        try:
            user = User.objects.get(id=user_id, tenant=tenant)
        except User.DoesNotExist:
            raise ValueError(f'User {user_id} not found in tenant {tenant.tenantname}')

        # Validate required fields
        required_fields = ['title', 'entry_type', 'timestamp']
        for field in required_fields:
            if field not in entry_data:
                raise ValueError(f'Required field {field} missing')

        # Parse timestamp
        timestamp_str = entry_data['timestamp']
        if isinstance(timestamp_str, str):
            timestamp = timezone.datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
        else:
            timestamp = timestamp_str

        # Create entry
        entry = JournalEntry.objects.create(
            user=user,
            tenant=tenant,
            title=entry_data['title'],
            subtitle=entry_data.get('subtitle', ''),
            content=entry_data.get('content', ''),
            entry_type=entry_data['entry_type'],
            timestamp=timestamp,
            mood_rating=entry_data.get('mood_rating'),
            stress_level=entry_data.get('stress_level'),
            energy_level=entry_data.get('energy_level'),
            privacy_scope=entry_data.get('privacy_scope', 'private'),
            tags=entry_data.get('tags', []),
            metadata=entry_data.get('metadata', {})
        )

        return entry

    def _validate_entry_data(self, entry_data, tenant):
        """Validate entry data without creating"""
        # Validate user exists
        user_id = entry_data.get('user_id')
        if not User.objects.filter(id=user_id, tenant=tenant).exists():
            raise ValueError(f'User {user_id} not found')

        # Validate entry type
        valid_types = [choice[0] for choice in JournalEntry.JournalEntryType.choices]
        if entry_data.get('entry_type') not in valid_types:
            raise ValueError(f'Invalid entry_type: {entry_data.get("entry_type")}')

        # Validate wellbeing metrics
        mood_rating = entry_data.get('mood_rating')
        if mood_rating is not None and (mood_rating < 1 or mood_rating > 10):
            raise ValueError('mood_rating must be between 1 and 10')

        stress_level = entry_data.get('stress_level')
        if stress_level is not None and (stress_level < 1 or stress_level > 5):
            raise ValueError('stress_level must be between 1 and 5')

        return True

    def _export_user_data_csv(self, user_data, output_file):
        """Export user data in CSV format"""
        with open(output_file, 'w', newline='') as csvfile:
            # Write journal entries
            if user_data.get('journal_entries'):
                writer = csv.DictWriter(csvfile, fieldnames=[
                    'id', 'title', 'entry_type', 'timestamp', 'mood_rating',
                    'stress_level', 'energy_level', 'privacy_scope'
                ])
                writer.writeheader()

                for entry in user_data['journal_entries']:
                    writer.writerow({
                        'id': entry['id'],
                        'title': entry['title'],
                        'entry_type': entry['entry_type'],
                        'timestamp': entry['timestamp'],
                        'mood_rating': entry.get('mood_rating', ''),
                        'stress_level': entry.get('stress_level', ''),
                        'energy_level': entry.get('energy_level', ''),
                        'privacy_scope': entry['privacy_scope']
                    })

    def _get_tenant(self, tenant_subdomain):
        """Get tenant object from subdomain"""
        if tenant_subdomain:
            try:
                return Tenant.objects.get(subdomain_prefix=tenant_subdomain)
            except Tenant.DoesNotExist:
                raise CommandError(f'Tenant "{tenant_subdomain}" not found')
        return None

    def _simulate_anonymization(self, user, preserve_analytics):
        """Simulate anonymization process"""
        # Count what would be affected
        journal_entries = JournalEntry.objects.filter(user=user)
        wellness_interactions = WellnessContentInteraction.objects.filter(user=user)

        from apps.journal.models import JournalMediaAttachment
        media_attachments = JournalMediaAttachment.objects.filter(
            journal_entry__user=user
        )

        return {
            'success': True,
            'simulation': True,
            'user_id': str(user.id),
            'preserve_analytics': preserve_analytics,
            'would_affect': {
                'journal_entries': journal_entries.count(),
                'wellness_interactions': wellness_interactions.count(),
                'media_attachments': media_attachments.count()
            },
            'actions_that_would_be_taken': [
                'Remove personally identifiable information from journal entries',
                'Delete all media attachments',
                'Anonymize wellness interaction feedback',
                'Preserve mood/stress/energy metrics for analytics' if preserve_analytics else 'Delete all personal data'
            ]
        }

    def _display_results(self, operation, result):
        """Display operation results"""
        if result.get('success'):
            self.stdout.write(self.style.SUCCESS(f'✅ {operation.title()} completed successfully!'))

            if operation == 'import':
                self.stdout.write(f'  📊 Imported: {result.get("imported_count", 0)} entries')
                if result.get('error_count', 0) > 0:
                    self.stdout.write(f'  ⚠️ Errors: {result["error_count"]}')

            elif operation == 'export':
                self.stdout.write(f'  📊 Exported to: {result.get("output_file", "file")}')
                if 'journal_entries' in result:
                    self.stdout.write(f'  📝 Journal entries: {result["journal_entries"]}')

            elif operation == 'cleanup':
                operations = result.get('operations', [])
                for op in operations:
                    if op.get('deleted_count'):
                        self.stdout.write(f'  🗑️ {op["type"]}: {op["deleted_count"]} deleted')

            elif operation == 'validate':
                checks = result.get('checks', [])
                passed_checks = [c for c in checks if c.get('passed')]
                self.stdout.write(f'  ✅ Passed: {len(passed_checks)}/{len(checks)} validation checks')

            elif operation == 'anonymize':
                if result.get('simulation'):
                    self.stdout.write('  🔍 Simulation completed - no data modified')
                else:
                    anonymized = result.get('anonymized_data', {})
                    self.stdout.write(f'  🔒 Anonymized: {sum(anonymized.values())} records')

        else:
            self.stdout.write(self.style.ERROR(f'❌ {operation.title()} failed'))
            if result.get('error'):
                self.stdout.write(f'  Error: {result["error"]}')

        # Show additional details
        if result.get('dry_run'):
            self.stdout.write(self.style.WARNING('  ⚠️ DRY RUN - No actual changes made'))

        if result.get('errors'):
            self.stdout.write(f'  📋 First few errors:')
            for error in result['errors'][:3]:
                self.stdout.write(f'    • {error}')

        self.stdout.write(f'\n📅 Operation completed at: {timezone.now()}')


# Additional utility command for system maintenance
class DataMaintenanceCommand(BaseCommand):
    """Additional data maintenance operations"""

    def add_arguments(self, parser):
        parser.add_argument(
            '--operation',
            type=str,
            choices=['reindex_search', 'update_analytics', 'check_health'],
            required=True,
            help='Maintenance operation to perform',
        )

    def handle(self, *args, **options):
        operation = options['operation']

        if operation == 'reindex_search':
            self._reindex_elasticsearch()
        elif operation == 'update_analytics':
            self._update_all_analytics()
        elif operation == 'check_health':
            self._check_system_health()

    def _reindex_elasticsearch(self):
        """Reindex all Elasticsearch data"""
        self.stdout.write('🔍 Reindexing Elasticsearch...')

        from apps.journal.search import reindex_all_tenants
        results = reindex_all_tenants()

        for tenant_name, result in results.items():
            if result.get('index_created'):
                self.stdout.write(f'  ✅ {tenant_name}: Index updated')
            else:
                self.stdout.write(f'  ❌ {tenant_name}: Index failed')

    def _update_all_analytics(self):
        """Update analytics for all users"""
        self.stdout.write('📊 Updating analytics for all users...')

        from background_tasks.journal_wellness_tasks import update_user_analytics

        users_with_data = User.objects.filter(
            journal_entries__isnull=False
        ).distinct()

        for user in users_with_data:
            update_user_analytics.delay(str(user.id))

        self.stdout.write(f'  📈 Queued analytics updates for {users_with_data.count()} users')

    def _check_system_health(self):
        """Check overall system health"""
        self.stdout.write('🏥 Checking system health...')

        # Check database connections
        from django.db import connection
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
            self.stdout.write('  ✅ Database: Connected')
        except (DatabaseError, FileNotFoundError, IOError, IntegrityError, OSError, ObjectDoesNotExist, PermissionError, TypeError, ValidationError, ValueError) as e:
            self.stdout.write(f'  ❌ Database: {e}')

        # Check Elasticsearch
        from apps.journal.search import JournalElasticsearchService
        es_service = JournalElasticsearchService()
        if es_service.es_client:
            self.stdout.write('  ✅ Elasticsearch: Available')
        else:
            self.stdout.write('  ⚠️ Elasticsearch: Not available (fallback to database search)')

        # Check MQTT
        mqtt_config = getattr(settings, 'MQTT_CONFIG', {})
        if mqtt_config.get('BROKER_ADDRESS'):
            self.stdout.write('  ✅ MQTT: Configured')
        else:
            self.stdout.write('  ⚠️ MQTT: Not configured')

        self.stdout.write('🎯 System health check completed')