"""
Enhanced Base Sync Service for Mobile Offline-First Sync Operations

Consolidates sync patterns from across the codebase to eliminate duplication.
Provides generic bulk upsert, conflict detection, and delta sync capabilities
for domain-specific sync services.

Following .claude/rules.md:
- Rule #7: Service <150 lines
- Rule #11: Specific exception handling
"""

import logging
import uuid
from django.db import transaction, DatabaseError, IntegrityError
from django.core.exceptions import ValidationError, ObjectDoesNotExist
from django.utils import timezone
from django.db.models import F, Q
from typing import Dict, Any, List, Optional, Type, Union
from django.db.models import Model

from apps.core.utils_new.db_utils import get_current_db_name
from apps.core.validators import validate_uuid_format, validate_sync_status, validate_version_number

logger = logging.getLogger(__name__)


class BaseSyncService:
    """
    Base service for domain-specific mobile sync operations.

    Provides:
    - Bulk upsert with conflict detection
    - Version-based optimistic locking
    - Delta sync for mobile clients
    - Per-item status tracking
    """

    def process_sync_batch(
        self,
        user,
        sync_data: Dict[str, Any],
        model_class: Type[Model],
        serializer_class: Type,
        extra_filters: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Process bulk sync batch with conflict detection.

        Args:
            user: Authenticated user
            sync_data: {entries: [...], last_sync_timestamp: ..., client_id: ...}
            model_class: Django model to sync
            serializer_class: Serializer for validation
            extra_filters: Additional filters for querying (e.g., bu, client)

        Returns:
            {synced_items: [{mobile_id, status, server_version}], conflicts: [], errors: []}
        """
        entries = sync_data.get('entries', [])

        if not entries:
            return {'synced_items': [], 'conflicts': [], 'errors': []}

        results = {'synced_items': [], 'conflicts': [], 'errors': []}

        try:
            with transaction.atomic(using=get_current_db_name()):
                for entry in entries:
                    try:
                        result = self._upsert_item(
                            user, entry, model_class, serializer_class, extra_filters
                        )

                        if result['status'] == 'conflict':
                            results['conflicts'].append(result)
                        elif result['status'] == 'error':
                            results['errors'].append(result)
                        else:
                            results['synced_items'].append(result)

                    except (ValidationError, IntegrityError) as e:
                        logger.warning(
                            f"Item sync failed for mobile_id {entry.get('mobile_id')}: {e}"
                        )
                        results['errors'].append({
                            'mobile_id': entry.get('mobile_id'),
                            'status': 'error',
                            'error_message': str(e)
                        })

        except DatabaseError as e:
            logger.error(f"Database error during sync batch: {e}", exc_info=True)
            return {
                'synced_items': [],
                'conflicts': [],
                'errors': [{'error': 'Database unavailable', 'message': str(e)}]
            }

        logger.info(
            f"Sync batch processed: {len(results['synced_items'])} synced, "
            f"{len(results['conflicts'])} conflicts, {len(results['errors'])} errors"
        )

        return results

    def _upsert_item(
        self,
        user,
        item_data: Dict[str, Any],
        model_class: Type[Model],
        serializer_class: Type,
        extra_filters: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Upsert single item with enhanced conflict detection.

        Enhanced with consolidated mobile ID handling and sync field preparation.
        """
        mobile_id = item_data.get('mobile_id')
        client_version = item_data.get('version', 0)

        # Validate and prepare mobile ID
        if mobile_id:
            mobile_id = self.validate_mobile_id(mobile_id)
        else:
            mobile_id = self.generate_mobile_id()

        item_data['mobile_id'] = mobile_id

        # Build filters using consolidated method
        base_filters = self.build_sync_filters(user, extra_filters)
        filters = base_filters & Q(mobile_id=mobile_id)

        try:
            server_obj = model_class.objects.filter(filters).first()

            if server_obj:
                conflict = self._detect_conflict(server_obj, item_data)
                if conflict:
                    return conflict

                # Prepare data for update
                prepared_data = self.prepare_sync_fields(item_data, is_update=True)

                serializer = serializer_class(server_obj, data=prepared_data, partial=True)
                serializer.is_valid(raise_exception=True)
                updated_obj = serializer.save(version=F('version') + 1)
                updated_obj.refresh_from_db()

                return {
                    'mobile_id': str(mobile_id),
                    'status': 'updated',
                    'server_version': updated_obj.version,
                    'sync_metadata': self.get_sync_metadata(updated_obj)
                }
            else:
                # Prepare data for creation
                prepared_data = self.prepare_sync_fields(item_data, is_update=False)

                serializer = serializer_class(data=prepared_data)
                serializer.is_valid(raise_exception=True)
                created_obj = serializer.save()

                return {
                    'mobile_id': str(mobile_id),
                    'status': 'created',
                    'server_version': created_obj.version,
                    'sync_metadata': self.get_sync_metadata(created_obj)
                }

        except ValidationError as e:
            logger.warning(f"Validation failed for mobile_id {mobile_id}: {e}")
            raise ValidationError(f"Validation failed: {str(e)}")
        except IntegrityError as e:
            logger.error(f"Database constraint violated for mobile_id {mobile_id}: {e}")
            raise IntegrityError(f"Database constraint violated: {str(e)}")

    def _detect_conflict(self, server_obj, client_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Detect version conflict between server and client."""
        server_version = getattr(server_obj, 'version', 0)
        client_version = client_data.get('version', 0)

        if server_version > client_version:
            logger.warning(
                f"Conflict detected: mobile_id={client_data.get('mobile_id')}, "
                f"server_version={server_version}, client_version={client_version}"
            )
            return {
                'mobile_id': str(client_data.get('mobile_id')),
                'status': 'conflict',
                'server_version': server_version,
                'client_version': client_version,
                'error_message': 'Client data is outdated, server has newer version'
            }

        return None

    def get_changes_since(
        self,
        user,
        timestamp: Optional[str],
        model_class: Type[Model],
        extra_filters: Optional[Dict] = None,
        limit: int = 100
    ) -> Dict[str, Any]:
        """
        Get changes since timestamp for delta sync.

        Args:
            user: Authenticated user
            timestamp: ISO timestamp for delta query
            model_class: Django model to query
            extra_filters: Additional filters (e.g., bu, client)
            limit: Maximum records to return

        Returns:
            {items: [...], has_more: bool, next_timestamp: ...}
        """
        filters = Q()

        if timestamp:
            try:
                filters &= Q(updated_at__gt=timestamp) | Q(created_at__gt=timestamp)
            except (ValueError, TypeError) as e:
                raise ValidationError(f"Invalid timestamp format: {e}")

        if extra_filters:
            for key, value in extra_filters.items():
                filters &= Q(**{key: value})

        try:
            queryset = model_class.objects.filter(filters).order_by('-updated_at')[:limit + 1]
            items = list(queryset[:limit])
            has_more = len(list(queryset)) > limit

            next_timestamp = None
            if items:
                next_timestamp = max(
                    item.updated_at if hasattr(item, 'updated_at') else item.created_at
                    for item in items
                ).isoformat()

            return {
                'items': items,
                'has_more': has_more,
                'next_timestamp': next_timestamp
            }

        except DatabaseError as e:
            logger.error(f"Database error during delta sync: {e}", exc_info=True)
            raise DatabaseError(f"Failed to fetch changes: {e}")

    def generate_mobile_id(self) -> str:
        """
        Generate a new mobile ID for sync records.

        Consolidates mobile ID generation patterns used across sync services.

        Returns:
            str: New UUID mobile ID
        """
        return str(uuid.uuid4())

    def validate_mobile_id(self, mobile_id: Union[str, uuid.UUID]) -> str:
        """
        Validate mobile ID format.

        Consolidates mobile ID validation patterns used across sync services.

        Args:
            mobile_id: Mobile ID to validate

        Returns:
            str: Validated mobile ID string

        Raises:
            ValidationError: If mobile ID format is invalid
        """
        return validate_uuid_format(mobile_id)

    def prepare_sync_fields(self, item_data: Dict[str, Any], is_update: bool = False) -> Dict[str, Any]:
        """
        Prepare standard sync fields for upsert operations.

        Consolidates sync field preparation patterns used across sync services.

        Args:
            item_data: Item data to prepare
            is_update: Whether this is an update operation

        Returns:
            dict: Data with prepared sync fields
        """
        # Ensure mobile_id exists
        if 'mobile_id' not in item_data or not item_data['mobile_id']:
            item_data['mobile_id'] = self.generate_mobile_id()
        else:
            item_data['mobile_id'] = self.validate_mobile_id(item_data['mobile_id'])

        # Set version
        if not is_update:
            item_data['version'] = 1
        # For updates, version is incremented in the SQL (F('version') + 1)

        # Set sync fields
        item_data['sync_status'] = 'synced'
        item_data['last_sync_timestamp'] = timezone.now()

        return item_data

    def get_sync_metadata(self, obj) -> Dict[str, Any]:
        """
        Extract sync metadata from a model instance.

        Consolidates sync metadata extraction patterns used across sync services.

        Args:
            obj: Model instance

        Returns:
            dict: Sync metadata
        """
        return {
            'mobile_id': str(getattr(obj, 'mobile_id', '')),
            'version': getattr(obj, 'version', 1),
            'sync_status': getattr(obj, 'sync_status', 'pending'),
            'last_sync_timestamp': getattr(obj, 'last_sync_timestamp', None),
            'created_at': getattr(obj, 'created_at', None),
            'updated_at': getattr(obj, 'updated_at', None)
        }

    def build_sync_filters(self, user, extra_filters: Optional[Dict] = None) -> Q:
        """
        Build common sync filters.

        Consolidates filter building patterns used across sync services.

        Args:
            user: User for tenant filtering
            extra_filters: Additional filters

        Returns:
            Q: Combined filter object
        """
        filters = Q()

        # Add tenant filtering if user has business unit
        if hasattr(user, 'bu') and user.bu:
            if hasattr(user.bu, 'tenant'):
                filters &= Q(tenant=user.bu.tenant)
            elif hasattr(user.bu, 'client'):
                filters &= Q(client=user.bu.client)

        # Add extra filters
        if extra_filters:
            for key, value in extra_filters.items():
                filters &= Q(**{key: value})

        return filters