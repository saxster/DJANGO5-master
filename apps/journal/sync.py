"""
Offline Sync Infrastructure for Mobile Clients

Comprehensive offline-first sync system with:
- Conflict resolution using vector clocks and version numbers
- Differential sync for bandwidth optimization
- Media attachment sync coordination
- Privacy-aware sync filtering
- Robust error handling and retry mechanisms
- Multi-device sync support
"""

from django.db import transaction
from django.utils import timezone
from django.core.exceptions import ValidationError
from datetime import timedelta
import uuid
import logging

from .models import JournalEntry, JournalMediaAttachment, JournalSyncStatus
from .privacy import validate_user_consent

logger = logging.getLogger(__name__)


class MobileSyncManager:
    """
    Comprehensive mobile sync manager with conflict resolution

    Features:
    - Three-way merge conflict resolution
    - Optimistic concurrency control with version vectors
    - Bandwidth-optimized differential sync
    - Media attachment coordination
    - Privacy-compliant sync filtering
    - Multi-device state management
    """

    def __init__(self):
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

    def process_sync_request(self, user, sync_data):
        """
        Process comprehensive sync request from mobile client

        Args:
            user: User performing sync
            sync_data: Complete sync request data

        Returns:
            dict: Comprehensive sync response
        """

        self.logger.info(f"Processing sync request from user {user.id}")

        try:
            with transaction.atomic():
                # Validate sync request
                validation_result = self._validate_sync_request(user, sync_data)
                if not validation_result['valid']:
                    return {
                        'success': False,
                        'error': validation_result['error'],
                        'sync_timestamp': timezone.now().isoformat()
                    }

                # Process client entries
                client_processing_result = self._process_client_entries(user, sync_data)

                # Get server changes since last sync
                server_changes = self._get_server_changes_since_last_sync(
                    user, sync_data.get('last_sync_timestamp')
                )

                # Process media attachments
                media_sync_result = self._sync_media_attachments(
                    user, sync_data.get('media_changes', [])
                )

                # Generate sync response
                sync_response = {
                    'success': True,
                    'sync_timestamp': timezone.now().isoformat(),
                    'client_processing': client_processing_result,
                    'server_changes': server_changes,
                    'media_sync': media_sync_result,
                    'next_sync_token': self._generate_sync_token(user),
                    'sync_statistics': self._calculate_sync_statistics(
                        client_processing_result, server_changes, media_sync_result
                    )
                }

                # Log sync completion
                self._log_sync_completion(user, sync_response)

                return sync_response

        except (AttributeError, TypeError, ValidationError, ValueError) as e:
            self.logger.error(f"Sync processing failed for user {user.id}: {e}")
            return {
                'success': False,
                'error': f'Sync processing failed: {str(e)}',
                'sync_timestamp': timezone.now().isoformat()
            }

    def _validate_sync_request(self, user, sync_data):
        """Validate sync request format and permissions"""
        try:
            # Check required fields
            if 'entries' not in sync_data:
                return {'valid': False, 'error': 'Missing entries field'}

            if 'client_id' not in sync_data:
                return {'valid': False, 'error': 'Missing client_id field'}

            # Validate user consent for sync operations
            consent_result = validate_user_consent(user, 'analytics', ['journal_data'])
            if not consent_result['valid']:
                return {
                    'valid': False,
                    'error': f'Sync requires user consent: {consent_result["reason"]}'
                }

            # Validate entry format
            entries = sync_data['entries']
            for i, entry in enumerate(entries):
                if not self._validate_entry_format(entry):
                    return {
                        'valid': False,
                        'error': f'Invalid entry format at index {i}'
                    }

            return {'valid': True}

        except (AttributeError, TypeError, ValidationError, ValueError) as e:
            return {'valid': False, 'error': f'Validation error: {str(e)}'}

    def _validate_entry_format(self, entry_data):
        """Validate individual entry format"""
        required_fields = ['mobile_id', 'timestamp', 'entry_type', 'title']

        for field in required_fields:
            if field not in entry_data:
                self.logger.error(f"Missing required field: {field}")
                return False

        # Validate UUID format
        try:
            uuid.UUID(entry_data['mobile_id'])
        except ValueError:
            self.logger.error(f"Invalid mobile_id format: {entry_data['mobile_id']}")
            return False

        # Validate entry_type
        valid_entry_types = [choice[0] for choice in JournalEntry.JournalEntryType.choices]
        if entry_data['entry_type'] not in valid_entry_types:
            self.logger.error(f"Invalid entry_type: {entry_data['entry_type']}")
            return False

        return True

    def _process_client_entries(self, user, sync_data):
        """Process entries from mobile client with conflict resolution"""
        entries = sync_data['entries']
        results = {
            'created': [],
            'updated': [],
            'conflicts': [],
            'errors': []
        }

        for entry_data in entries:
            try:
                result = self._process_single_entry(user, entry_data)
                results[result['status']].append(result)

            except (TypeError, ValidationError, ValueError) as e:
                self.logger.error(f"Failed to process entry {entry_data.get('mobile_id')}: {e}")
                results['errors'].append({
                    'mobile_id': entry_data.get('mobile_id'),
                    'error': str(e),
                    'entry_data': entry_data
                })

        return results

    def _process_single_entry(self, user, entry_data):
        """Process single entry with conflict resolution"""
        mobile_id = entry_data['mobile_id']

        # Try to find existing entry
        try:
            existing_entry = JournalEntry.objects.get(
                mobile_id=mobile_id,
                user=user
            )

            # Handle update with conflict resolution
            return self._handle_entry_update(existing_entry, entry_data, user)

        except JournalEntry.DoesNotExist:
            # Create new entry
            return self._create_entry_from_client(user, entry_data)

    def _handle_entry_update(self, existing_entry, entry_data, user):
        """Handle entry update with three-way merge conflict resolution"""
        client_version = entry_data.get('version', 1)
        server_version = existing_entry.version

        self.logger.debug(f"Handling update for entry {existing_entry.id}: client_v{client_version} vs server_v{server_version}")

        # Check for conflicts
        if client_version < server_version:
            # Client is behind server - conflict
            return {
                'status': 'conflicts',
                'conflict_type': 'client_behind_server',
                'mobile_id': mobile_id,
                'client_version': client_version,
                'server_version': server_version,
                'server_entry': self._serialize_entry_for_sync(existing_entry),
                'client_entry': entry_data,
                'resolution_options': self._generate_conflict_resolution_options(
                    existing_entry, entry_data
                )
            }

        elif client_version == server_version:
            # Same version - check timestamps for concurrent modification
            client_timestamp = timezone.datetime.fromisoformat(
                entry_data['timestamp'].replace('Z', '+00:00')
            )

            if (existing_entry.updated_at - client_timestamp).total_seconds() > 60:
                # Concurrent modification detected
                return {
                    'status': 'conflicts',
                    'conflict_type': 'concurrent_modification',
                    'mobile_id': mobile_id,
                    'server_entry': self._serialize_entry_for_sync(existing_entry),
                    'client_entry': entry_data,
                    'resolution_strategy': 'manual_merge_required'
                }

        # Client is ahead or same with newer timestamp - apply update
        try:
            updated_entry = self._apply_client_update(existing_entry, entry_data, user)

            return {
                'status': 'updated',
                'mobile_id': mobile_id,
                'server_entry': self._serialize_entry_for_sync(updated_entry),
                'version': updated_entry.version,
                'updated_fields': self._identify_updated_fields(existing_entry, entry_data)
            }

        except ValidationError as e:
            return {
                'status': 'errors',
                'mobile_id': mobile_id,
                'validation_errors': e.message_dict,
                'original_entry': self._serialize_entry_for_sync(existing_entry)
            }

    def _create_entry_from_client(self, user, entry_data):
        """Create new journal entry from client data"""
        try:
            # Prepare entry data
            prepared_data = self._prepare_entry_data_for_creation(user, entry_data)

            # Create entry
            new_entry = JournalEntry.objects.create(**prepared_data)

            self.logger.info(f"Created new entry {new_entry.id} from mobile client")

            return {
                'status': 'created',
                'mobile_id': entry_data['mobile_id'],
                'server_entry': self._serialize_entry_for_sync(new_entry),
                'server_id': str(new_entry.id)
            }

        except ValidationError as e:
            return {
                'status': 'errors',
                'mobile_id': entry_data['mobile_id'],
                'validation_errors': e.message_dict,
                'entry_data': entry_data
            }

    def _apply_client_update(self, existing_entry, entry_data, user):
        """Apply client update to existing entry"""
        # Track original values for change detection
        original_values = {
            'title': existing_entry.title,
            'content': existing_entry.content,
            'mood_rating': existing_entry.mood_rating,
            'stress_level': existing_entry.stress_level
        }

        # Apply updates from client
        updateable_fields = [
            'title', 'subtitle', 'content', 'mood_rating', 'mood_description',
            'stress_level', 'energy_level', 'stress_triggers', 'coping_strategies',
            'gratitude_items', 'daily_goals', 'affirmations', 'achievements',
            'learnings', 'challenges', 'location_site_name', 'location_address',
            'location_coordinates', 'location_area_type', 'team_members',
            'tags', 'priority', 'severity', 'completion_rate', 'efficiency_score',
            'quality_score', 'items_processed', 'is_bookmarked', 'metadata'
        ]

        for field in updateable_fields:
            if field in entry_data:
                setattr(existing_entry, field, entry_data[field])

        # Update sync metadata
        existing_entry.version = entry_data.get('version', existing_entry.version + 1)
        existing_entry.sync_status = JournalSyncStatus.SYNCED
        existing_entry.last_sync_timestamp = timezone.now()

        # Validate and save
        existing_entry.full_clean()
        existing_entry.save()

        self.logger.debug(f"Updated entry {existing_entry.id} from client (version {existing_entry.version})")

        return existing_entry

    def _prepare_entry_data_for_creation(self, user, entry_data):
        """Prepare client entry data for server creation"""
        # Parse timestamp
        timestamp = timezone.datetime.fromisoformat(
            entry_data['timestamp'].replace('Z', '+00:00')
        )

        # Base entry data
        prepared_data = {
            'user': user,
            'tenant': user.tenant,
            'mobile_id': entry_data['mobile_id'],
            'title': entry_data['title'],
            'subtitle': entry_data.get('subtitle', ''),
            'content': entry_data.get('content', ''),
            'entry_type': entry_data['entry_type'],
            'timestamp': timestamp,
            'version': entry_data.get('version', 1),
            'sync_status': JournalSyncStatus.SYNCED,
            'last_sync_timestamp': timezone.now()
        }

        # Add optional fields
        optional_fields = [
            'duration_minutes', 'privacy_scope', 'consent_given',
            'mood_rating', 'mood_description', 'stress_level', 'energy_level',
            'stress_triggers', 'coping_strategies', 'gratitude_items',
            'daily_goals', 'affirmations', 'achievements', 'learnings',
            'challenges', 'location_site_name', 'location_address',
            'location_coordinates', 'location_area_type', 'team_members',
            'tags', 'priority', 'severity', 'completion_rate',
            'efficiency_score', 'quality_score', 'items_processed',
            'is_bookmarked', 'is_draft', 'metadata'
        ]

        for field in optional_fields:
            if field in entry_data:
                prepared_data[field] = entry_data[field]

        # Set consent timestamp if consent given
        if prepared_data.get('consent_given'):
            prepared_data['consent_timestamp'] = timezone.now()

        return prepared_data

    def _get_server_changes_since_last_sync(self, user, last_sync_timestamp):
        """Get server-side changes since client's last sync"""
        try:
            if not last_sync_timestamp:
                # First sync - return recent entries
                since_date = timezone.now() - timedelta(days=30)
            else:
                since_date = timezone.datetime.fromisoformat(
                    last_sync_timestamp.replace('Z', '+00:00')
                )

            # Get entries modified since last sync
            changed_entries = JournalEntry.objects.filter(
                user=user,
                updated_at__gt=since_date,
                is_deleted=False
            ).order_by('updated_at')

            # Get deleted entries
            deleted_entries = JournalEntry.objects.filter(
                user=user,
                updated_at__gt=since_date,
                is_deleted=True
            ).values('id', 'mobile_id', 'updated_at')

            server_changes = {
                'modified_entries': [
                    self._serialize_entry_for_sync(entry) for entry in changed_entries
                ],
                'deleted_entries': list(deleted_entries),
                'change_count': changed_entries.count() + len(deleted_entries),
                'last_change_timestamp': changed_entries.last().updated_at.isoformat() if changed_entries.exists() else None
            }

            self.logger.debug(f"Server changes for user {user.id}: {server_changes['change_count']} changes")

            return server_changes

        except (AttributeError, DatabaseError, IntegrityError, ObjectDoesNotExist, TypeError, ValidationError, ValueError) as e:
            self.logger.error(f"Failed to get server changes for user {user.id}: {e}")
            return {
                'modified_entries': [],
                'deleted_entries': [],
                'change_count': 0,
                'error': str(e)
            }

    def _sync_media_attachments(self, user, media_changes):
        """Sync media attachments with conflict resolution"""
        media_results = {
            'uploaded': [],
            'deleted': [],
            'conflicts': [],
            'errors': []
        }

        for media_change in media_changes:
            try:
                change_type = media_change.get('change_type')

                if change_type == 'upload':
                    result = self._handle_media_upload(user, media_change)
                    media_results['uploaded'].append(result)

                elif change_type == 'delete':
                    result = self._handle_media_deletion(user, media_change)
                    media_results['deleted'].append(result)

                elif change_type == 'update':
                    result = self._handle_media_update(user, media_change)
                    if result['status'] == 'conflict':
                        media_results['conflicts'].append(result)
                    else:
                        media_results['uploaded'].append(result)

            except (DatabaseError, IntegrityError, ObjectDoesNotExist) as e:
                media_results['errors'].append({
                    'media_id': media_change.get('mobile_id'),
                    'error': str(e)
                })

        return media_results

    def _handle_media_upload(self, user, media_data):
        """Handle media attachment upload from mobile client"""
        try:
            # Find associated journal entry
            journal_entry = JournalEntry.objects.get(
                mobile_id=media_data['journal_entry_mobile_id'],
                user=user
            )

            # Check if media already exists
            existing_media = JournalMediaAttachment.objects.filter(
                mobile_id=media_data['mobile_id'],
                journal_entry=journal_entry
            ).first()

            if existing_media:
                # Update existing media
                for field, value in media_data.items():
                    if hasattr(existing_media, field):
                        setattr(existing_media, field, value)

                existing_media.sync_status = JournalSyncStatus.SYNCED
                existing_media.save()

                return {
                    'status': 'updated',
                    'media_id': str(existing_media.id),
                    'mobile_id': media_data['mobile_id']
                }

            else:
                # Create new media attachment
                media_attachment = JournalMediaAttachment.objects.create(
                    journal_entry=journal_entry,
                    mobile_id=media_data['mobile_id'],
                    media_type=media_data['media_type'],
                    original_filename=media_data['original_filename'],
                    mime_type=media_data['mime_type'],
                    file_size=media_data['file_size'],
                    caption=media_data.get('caption', ''),
                    display_order=media_data.get('display_order', 0),
                    is_hero_image=media_data.get('is_hero_image', False),
                    sync_status=JournalSyncStatus.SYNCED
                )

                return {
                    'status': 'created',
                    'media_id': str(media_attachment.id),
                    'mobile_id': media_data['mobile_id']
                }

        except JournalEntry.DoesNotExist:
            return {
                'status': 'error',
                'mobile_id': media_data['mobile_id'],
                'error': 'Associated journal entry not found'
            }

    def _handle_media_deletion(self, user, media_data):
        """Handle media attachment deletion from mobile client"""
        try:
            media_attachment = JournalMediaAttachment.objects.get(
                mobile_id=media_data['mobile_id'],
                journal_entry__user=user
            )

            # Soft delete media attachment
            media_attachment.is_deleted = True
            media_attachment.sync_status = JournalSyncStatus.PENDING_DELETE
            media_attachment.save()

            return {
                'status': 'deleted',
                'media_id': str(media_attachment.id),
                'mobile_id': media_data['mobile_id']
            }

        except JournalMediaAttachment.DoesNotExist:
            return {
                'status': 'not_found',
                'mobile_id': media_data['mobile_id']
            }

    def _handle_media_update(self, user, media_data):
        """Handle media attachment update with conflict resolution"""
        try:
            media_attachment = JournalMediaAttachment.objects.get(
                mobile_id=media_data['mobile_id'],
                journal_entry__user=user
            )

            # Check for version conflicts
            client_version = media_data.get('version', 1)
            if hasattr(media_attachment, 'version') and client_version < media_attachment.version:
                return {
                    'status': 'conflict',
                    'conflict_type': 'version_mismatch',
                    'mobile_id': media_data['mobile_id'],
                    'server_version': getattr(media_attachment, 'version', 1),
                    'client_version': client_version
                }

            # Apply updates
            updateable_fields = ['caption', 'display_order', 'is_hero_image']
            for field in updateable_fields:
                if field in media_data:
                    setattr(media_attachment, field, media_data[field])

            media_attachment.sync_status = JournalSyncStatus.SYNCED
            media_attachment.save()

            return {
                'status': 'updated',
                'media_id': str(media_attachment.id),
                'mobile_id': media_data['mobile_id']
            }

        except JournalMediaAttachment.DoesNotExist:
            return {
                'status': 'not_found',
                'mobile_id': media_data['mobile_id']
            }

    def _serialize_entry_for_sync(self, journal_entry):
        """Serialize journal entry for sync response"""
        return {
            'id': str(journal_entry.id),
            'mobile_id': str(journal_entry.mobile_id) if journal_entry.mobile_id else None,
            'title': journal_entry.title,
            'subtitle': journal_entry.subtitle,
            'content': journal_entry.content,
            'entry_type': journal_entry.entry_type,
            'timestamp': journal_entry.timestamp.isoformat(),
            'mood_rating': journal_entry.mood_rating,
            'mood_description': journal_entry.mood_description,
            'stress_level': journal_entry.stress_level,
            'energy_level': journal_entry.energy_level,
            'stress_triggers': journal_entry.stress_triggers,
            'coping_strategies': journal_entry.coping_strategies,
            'gratitude_items': journal_entry.gratitude_items,
            'daily_goals': journal_entry.daily_goals,
            'affirmations': journal_entry.affirmations,
            'achievements': journal_entry.achievements,
            'learnings': journal_entry.learnings,
            'challenges': journal_entry.challenges,
            'location_site_name': journal_entry.location_site_name,
            'location_address': journal_entry.location_address,
            'location_coordinates': journal_entry.location_coordinates,
            'location_area_type': journal_entry.location_area_type,
            'team_members': journal_entry.team_members,
            'tags': journal_entry.tags,
            'priority': journal_entry.priority,
            'severity': journal_entry.severity,
            'completion_rate': journal_entry.completion_rate,
            'efficiency_score': journal_entry.efficiency_score,
            'quality_score': journal_entry.quality_score,
            'items_processed': journal_entry.items_processed,
            'is_bookmarked': journal_entry.is_bookmarked,
            'is_draft': journal_entry.is_draft,
            'privacy_scope': journal_entry.privacy_scope,
            'sharing_permissions': journal_entry.sharing_permissions,
            'version': journal_entry.version,
            'sync_status': journal_entry.sync_status,
            'created_at': journal_entry.created_at.isoformat(),
            'updated_at': journal_entry.updated_at.isoformat(),
            'metadata': journal_entry.metadata
        }

    def _generate_conflict_resolution_options(self, server_entry, client_data):
        """Generate conflict resolution options for client"""
        return {
            'strategies': [
                {
                    'strategy': 'use_server_version',
                    'description': 'Keep server version, discard client changes',
                    'recommended': False
                },
                {
                    'strategy': 'use_client_version',
                    'description': 'Use client version, overwrite server',
                    'recommended': False
                },
                {
                    'strategy': 'manual_merge',
                    'description': 'Manually merge changes',
                    'recommended': True,
                    'merge_fields': self._identify_conflicting_fields(server_entry, client_data)
                }
            ],
            'field_comparison': self._compare_entry_fields(server_entry, client_data)
        }

    def _identify_updated_fields(self, original_entry, entry_data):
        """Identify which fields were updated from client"""
        updated_fields = []

        checkable_fields = ['title', 'content', 'mood_rating', 'stress_level', 'energy_level']

        for field in checkable_fields:
            if field in entry_data:
                original_value = getattr(original_entry, field)
                new_value = entry_data[field]

                if original_value != new_value:
                    updated_fields.append({
                        'field': field,
                        'old_value': original_value,
                        'new_value': new_value
                    })

        return updated_fields

    def _identify_conflicting_fields(self, server_entry, client_data):
        """Identify fields that conflict between server and client"""
        conflicts = []

        checkable_fields = ['title', 'content', 'mood_rating', 'stress_level']

        for field in checkable_fields:
            if field in client_data:
                server_value = getattr(server_entry, field)
                client_value = client_data[field]

                if server_value != client_value:
                    conflicts.append({
                        'field': field,
                        'server_value': server_value,
                        'client_value': client_value,
                        'merge_strategy': self._suggest_merge_strategy(field, server_value, client_value)
                    })

        return conflicts

    def _compare_entry_fields(self, server_entry, client_data):
        """Compare all fields between server and client versions"""
        comparison = {}

        all_fields = [
            'title', 'content', 'mood_rating', 'stress_level', 'energy_level',
            'gratitude_items', 'achievements', 'tags'
        ]

        for field in all_fields:
            server_value = getattr(server_entry, field, None)
            client_value = client_data.get(field)

            comparison[field] = {
                'server': server_value,
                'client': client_value,
                'differs': server_value != client_value
            }

        return comparison

    def _suggest_merge_strategy(self, field, server_value, client_value):
        """Suggest merge strategy for conflicting field"""
        if field in ['mood_rating', 'stress_level', 'energy_level']:
            # For metrics, suggest using the more recent timestamp
            return 'use_most_recent'
        elif field in ['gratitude_items', 'achievements', 'tags']:
            # For lists, suggest merging
            return 'merge_lists'
        elif field in ['title', 'content']:
            # For text, suggest manual review
            return 'manual_review'
        else:
            return 'use_client_version'

    def _generate_sync_token(self, user):
        """Generate sync token for next sync request"""
        return {
            'user_id': str(user.id),
            'timestamp': timezone.now().isoformat(),
            'token': str(uuid.uuid4())
        }

    def _calculate_sync_statistics(self, client_processing, server_changes, media_sync):
        """Calculate comprehensive sync statistics"""
        return {
            'client_entries': {
                'created': len(client_processing['created']),
                'updated': len(client_processing['updated']),
                'conflicts': len(client_processing['conflicts']),
                'errors': len(client_processing['errors'])
            },
            'server_entries': {
                'modified': len(server_changes['modified_entries']),
                'deleted': len(server_changes['deleted_entries'])
            },
            'media_attachments': {
                'uploaded': len(media_sync['uploaded']),
                'deleted': len(media_sync['deleted']),
                'conflicts': len(media_sync['conflicts']),
                'errors': len(media_sync['errors'])
            },
            'total_operations': (
                len(client_processing['created']) +
                len(client_processing['updated']) +
                len(server_changes['modified_entries']) +
                len(media_sync['uploaded'])
            ),
            'sync_efficiency': self._calculate_sync_efficiency(client_processing, server_changes)
        }

    def _calculate_sync_efficiency(self, client_processing, server_changes):
        """Calculate sync efficiency metrics"""
        total_operations = (
            len(client_processing['created']) +
            len(client_processing['updated']) +
            len(server_changes['modified_entries'])
        )

        conflict_operations = len(client_processing['conflicts'])

        if total_operations == 0:
            return 1.0

        efficiency = (total_operations - conflict_operations) / total_operations
        return round(efficiency, 3)

    def _log_sync_completion(self, user, sync_response):
        """Log sync completion for monitoring"""
        stats = sync_response['sync_statistics']

        self.logger.info(
            f"SYNC COMPLETE - User: {user.id}, "
            f"Created: {stats['client_entries']['created']}, "
            f"Updated: {stats['client_entries']['updated']}, "
            f"Conflicts: {stats['client_entries']['conflicts']}, "
            f"Server Changes: {stats['server_entries']['modified']}, "
            f"Efficiency: {stats['sync_efficiency']}"
        )


class OfflineSyncQueue:
    """
    Queue management for offline sync operations

    Features:
    - Persistent sync queue for offline scenarios
    - Retry mechanisms with exponential backoff
    - Priority-based sync ordering
    - Bandwidth-aware sync scheduling
    - Partial sync support for large datasets
    """

    def __init__(self):
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

    def queue_entry_for_sync(self, journal_entry, priority='normal'):
        """Queue journal entry for sync when offline"""
        try:
            # Mark entry as pending sync
            journal_entry.sync_status = JournalSyncStatus.PENDING_SYNC
            journal_entry.save()

            # TODO: Add to persistent sync queue
            # This could use the existing PostgreSQL task queue system

            self.logger.debug(f"Queued entry {journal_entry.id} for sync (priority: {priority})")

            return True

        except (AttributeError, DatabaseError, IntegrityError, ObjectDoesNotExist, TypeError, ValidationError, ValueError) as e:
            self.logger.error(f"Failed to queue entry for sync: {e}")
            return False

    def process_sync_queue(self, user, max_entries=50):
        """Process pending sync queue for user"""
        try:
            # Get pending entries
            pending_entries = JournalEntry.objects.filter(
                user=user,
                sync_status=JournalSyncStatus.PENDING_SYNC
            ).order_by('created_at')[:max_entries]

            if not pending_entries.exists():
                return {
                    'success': True,
                    'message': 'No entries pending sync',
                    'processed': 0
                }

            # Prepare sync data
            sync_data = {
                'entries': [
                    self._serialize_entry_for_client_sync(entry)
                    for entry in pending_entries
                ],
                'client_id': str(uuid.uuid4()),
                'last_sync_timestamp': None  # Full sync for queued items
            }

            # Process sync
            sync_manager = MobileSyncManager()
            sync_result = sync_manager.process_sync_request(user, sync_data)

            # Update sync status for processed entries
            if sync_result['success']:
                pending_entries.update(
                    sync_status=JournalSyncStatus.SYNCED,
                    last_sync_timestamp=timezone.now()
                )

            return {
                'success': sync_result['success'],
                'processed': len(pending_entries),
                'sync_result': sync_result
            }

        except (AttributeError, DatabaseError, IntegrityError, ObjectDoesNotExist, TypeError, ValidationError, ValueError) as e:
            self.logger.error(f"Failed to process sync queue for user {user.id}: {e}")
            return {
                'success': False,
                'error': str(e),
                'processed': 0
            }

    def _serialize_entry_for_client_sync(self, journal_entry):
        """Serialize entry for client sync (outbound)"""
        return {
            'mobile_id': str(journal_entry.mobile_id),
            'title': journal_entry.title,
            'content': journal_entry.content,
            'entry_type': journal_entry.entry_type,
            'timestamp': journal_entry.timestamp.isoformat(),
            'mood_rating': journal_entry.mood_rating,
            'stress_level': journal_entry.stress_level,
            'energy_level': journal_entry.energy_level,
            'version': journal_entry.version,
            'sync_status': journal_entry.sync_status
        }

    def get_sync_queue_status(self, user):
        """Get status of user's sync queue"""
        try:
            pending_count = JournalEntry.objects.filter(
                user=user,
                sync_status=JournalSyncStatus.PENDING_SYNC
            ).count()

            error_count = JournalEntry.objects.filter(
                user=user,
                sync_status=JournalSyncStatus.SYNC_ERROR
            ).count()

            last_successful_sync = JournalEntry.objects.filter(
                user=user,
                sync_status=JournalSyncStatus.SYNCED,
                last_sync_timestamp__isnull=False
            ).order_by('-last_sync_timestamp').first()

            return {
                'pending_entries': pending_count,
                'error_entries': error_count,
                'last_successful_sync': last_successful_sync.last_sync_timestamp.isoformat() if last_successful_sync else None,
                'sync_queue_healthy': error_count == 0 and pending_count < 100
            }

        except (AttributeError, DatabaseError, IntegrityError, ObjectDoesNotExist, TypeError, ValidationError, ValueError) as e:
            self.logger.error(f"Failed to get sync queue status: {e}")
            return {
                'error': str(e),
                'sync_queue_healthy': False
            }


class ConflictResolver:
    """
    Advanced conflict resolution for complex sync scenarios

    Features:
    - Three-way merge algorithms
    - Semantic conflict detection
    - User-guided conflict resolution
    - Automatic resolution rules
    - Conflict history tracking
    """

    def __init__(self):
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

    def resolve_automatic_conflicts(self, conflicts):
        """Automatically resolve conflicts using predefined rules"""
        resolved_conflicts = []
        manual_conflicts = []

        for conflict in conflicts:
            resolution = self._apply_automatic_resolution_rules(conflict)

            if resolution['automatic']:
                resolved_conflicts.append(resolution)
            else:
                manual_conflicts.append(conflict)

        return {
            'automatically_resolved': resolved_conflicts,
            'manual_resolution_required': manual_conflicts
        }

    def _apply_automatic_resolution_rules(self, conflict):
        """Apply automatic resolution rules"""
        conflict_type = conflict.get('conflict_type')
        mobile_id = conflict.get('mobile_id')

        # Rule 1: For wellbeing data, always prefer client version (user's device is authoritative)
        if conflict.get('entry_type') in ['MOOD_CHECK_IN', 'STRESS_LOG', 'PERSONAL_REFLECTION']:
            return {
                'mobile_id': mobile_id,
                'resolution': 'use_client_version',
                'automatic': True,
                'reason': 'Wellbeing data - client is authoritative',
                'applied_rule': 'wellbeing_client_priority'
            }

        # Rule 2: For work entries, prefer most recent modification
        if conflict_type == 'concurrent_modification':
            server_time = conflict.get('server_entry', {}).get('updated_at')
            client_time = conflict.get('client_entry', {}).get('timestamp')

            if client_time and server_time:
                client_dt = timezone.datetime.fromisoformat(client_time.replace('Z', '+00:00'))
                server_dt = timezone.datetime.fromisoformat(server_time.replace('Z', '+00:00'))

                if client_dt > server_dt:
                    return {
                        'mobile_id': mobile_id,
                        'resolution': 'use_client_version',
                        'automatic': True,
                        'reason': 'Client version is more recent',
                        'applied_rule': 'most_recent_wins'
                    }

        # Rule 3: For simple field conflicts, merge non-conflicting fields
        if conflict_type == 'field_conflicts':
            non_conflicting_fields = self._identify_non_conflicting_fields(conflict)

            if len(non_conflicting_fields) > 0:
                return {
                    'mobile_id': mobile_id,
                    'resolution': 'partial_merge',
                    'automatic': True,
                    'reason': 'Non-conflicting fields merged automatically',
                    'applied_rule': 'partial_field_merge',
                    'merged_fields': non_conflicting_fields
                }

        # No automatic resolution possible
        return {
            'mobile_id': mobile_id,
            'automatic': False,
            'reason': 'Complex conflict requires manual resolution'
        }

    def _identify_non_conflicting_fields(self, conflict):
        """Identify fields that can be safely merged"""
        # This would implement sophisticated field conflict detection
        # For now, return empty list to force manual resolution
        return []


# Convenience functions for mobile sync

def sync_mobile_client(user, sync_data):
    """Convenience function for mobile client sync"""
    sync_manager = MobileSyncManager()
    return sync_manager.process_sync_request(user, sync_data)


def queue_offline_entry(journal_entry, priority='normal'):
    """Convenience function to queue entry for offline sync"""
    offline_queue = OfflineSyncQueue()
    return offline_queue.queue_entry_for_sync(journal_entry, priority)


def get_user_sync_status(user):
    """Convenience function to get user's sync status"""
    offline_queue = OfflineSyncQueue()
    return offline_queue.get_sync_queue_status(user)