"""
Domain Sync Service - Abstract base for domain-specific sync operations

Provides template method pattern and standardized functionality for
task, ticket, attendance, and other domain sync services.

Following .claude/rules.md:
- Rule #7: Service <150 lines (using composition over inheritance)
- Rule #11: Specific exception handling
- Rule #12: Database query optimization
"""

import logging
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional, Type
from django.db.models import Model
from django.core.exceptions import ValidationError
from django.db import DatabaseError

from .base_sync_service import BaseSyncService
from .sync_mixins import (
    UserFilterMixin,
    StatusTransitionMixin,
    SyncQueryOptimizationMixin,
    SyncMetadataMixin
)

logger = logging.getLogger(__name__)


class DomainSyncService(
    BaseSyncService,
    UserFilterMixin,
    StatusTransitionMixin,
    SyncQueryOptimizationMixin,
    SyncMetadataMixin,
    ABC
):
    """
    Abstract base class for domain-specific sync services.

    Provides:
    - Template method pattern for sync operations
    - Standardized tenant filtering
    - Status transition validation
    - Query optimization
    - Conflict resolution hooks

    Subclasses must implement:
    - get_model_class()
    - get_serializer_class()
    - validate_domain_specific_data()
    """

    # Subclasses should override these
    DOMAIN_NAME: str = ""
    STATUS_TRANSITIONS: Dict[str, List[str]] = {}
    SYNC_SELECT_RELATED: List[str] = []
    SYNC_PREFETCH_RELATED: List[str] = []

    def __init__(self):
        """Initialize domain sync service with validation."""
        if not self.DOMAIN_NAME:
            raise ValidationError(f"{self.__class__.__name__} must define DOMAIN_NAME")
        super().__init__()

    @abstractmethod
    def get_model_class(self) -> Type[Model]:
        """Return the Django model class for this domain."""
        pass

    @abstractmethod
    def get_serializer_class(self) -> Type:
        """Return the serializer class for this domain."""
        pass

    def sync_domain_data(
        self,
        user,
        sync_data: Dict[str, Any],
        additional_filters: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Main entry point for domain sync operations.

        Template method that orchestrates the sync process:
        1. Validate user and permissions
        2. Prepare domain-specific filters
        3. Execute batch sync with domain validation
        4. Post-process results

        Args:
            user: Authenticated user
            sync_data: Sync payload from mobile client
            additional_filters: Extra domain-specific filters

        Returns:
            Sync result with items, conflicts, and errors
        """
        try:
            # Step 1: Validate user and permissions
            self._validate_sync_user(user)

            # Step 2: Prepare filters
            base_filters = self.get_user_filters(user)
            domain_filters = self._prepare_domain_filters(user, additional_filters)
            combined_filters = {**base_filters, **domain_filters}

            # Step 3: Execute sync with domain-specific validation
            results = self.process_sync_batch(
                user=user,
                sync_data=sync_data,
                model_class=self.get_model_class(),
                serializer_class=self.get_serializer_class(),
                extra_filters=combined_filters
            )

            # Step 4: Post-process results
            processed_results = self._post_process_sync_results(results, user)

            logger.info(
                f"{self.DOMAIN_NAME} sync completed: "
                f"{len(processed_results['synced_items'])} synced, "
                f"{len(processed_results['conflicts'])} conflicts"
            )

            return processed_results

        except ValidationError as e:
            logger.warning(f"{self.DOMAIN_NAME} sync validation error: {e}")
            return self._create_error_response(str(e), sync_data)
        except DatabaseError as e:
            logger.error(f"{self.DOMAIN_NAME} sync database error: {e}", exc_info=True)
            return self._create_error_response("Database temporarily unavailable", sync_data)

    def get_domain_changes(
        self,
        user,
        timestamp: Optional[str] = None,
        additional_filters: Optional[Dict] = None,
        limit: int = 100
    ) -> Dict[str, Any]:
        """
        Get domain-specific changes for delta sync.

        Args:
            user: Authenticated user
            timestamp: ISO timestamp for delta query
            additional_filters: Extra domain-specific filters
            limit: Maximum records to return

        Returns:
            Changes since timestamp with domain metadata
        """
        try:
            self._validate_sync_user(user)

            base_filters = self.get_user_filters(user)
            domain_filters = self._prepare_domain_filters(user, additional_filters)
            combined_filters = {**base_filters, **domain_filters}

            changes = self.get_changes_since(
                user=user,
                timestamp=timestamp,
                model_class=self.get_model_class(),
                extra_filters=combined_filters,
                limit=limit
            )

            # Enrich with domain-specific metadata
            enriched_changes = self._enrich_changes_with_metadata(changes)

            return enriched_changes

        except (ValidationError, DatabaseError) as e:
            logger.error(f"{self.DOMAIN_NAME} changes query error: {e}", exc_info=True)
            return {'items': [], 'has_more': False, 'next_timestamp': None, 'error': str(e)}

    def _validate_sync_user(self, user) -> None:
        """Validate user can perform sync operations for this domain."""
        if not user or not user.is_authenticated:
            raise ValidationError("User must be authenticated")

        # Domain-specific permission validation
        domain_permissions = self._get_domain_permissions(user)
        if not domain_permissions.get('can_sync', True):
            raise ValidationError(f"User lacks {self.DOMAIN_NAME} sync permissions")

    def _prepare_domain_filters(
        self,
        user,
        additional_filters: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Prepare domain-specific filters.

        Can be overridden by subclasses for custom filtering logic.
        """
        filters = additional_filters or {}

        # Add any domain-specific logic here
        domain_specific = self._get_domain_specific_filters(user)
        filters.update(domain_specific)

        return filters

    def _get_domain_specific_filters(self, user) -> Dict[str, Any]:
        """
        Get domain-specific filters.

        Override in subclasses for domain-specific logic.
        """
        return {}

    def _get_domain_permissions(self, user) -> Dict[str, Any]:
        """
        Get domain-specific permissions for user.

        Override in subclasses for domain-specific permission logic.
        """
        return {'can_sync': True, 'can_read': True, 'can_write': True}

    def _post_process_sync_results(self, results: Dict[str, Any], user) -> Dict[str, Any]:
        """
        Post-process sync results with domain-specific logic.

        Can be overridden by subclasses to add domain-specific metadata
        or perform additional validation.
        """
        # Add domain metadata
        results['domain'] = self.DOMAIN_NAME
        results['sync_timestamp'] = self._get_current_timestamp()

        # Enrich synced items with domain metadata
        for item in results.get('synced_items', []):
            item['domain'] = self.DOMAIN_NAME

        return results

    def _enrich_changes_with_metadata(self, changes: Dict[str, Any]) -> Dict[str, Any]:
        """
        Enrich change data with domain-specific metadata.

        Override in subclasses for domain-specific enrichment.
        """
        changes['domain'] = self.DOMAIN_NAME
        return changes

    def _create_error_response(self, error_message: str, sync_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create standardized error response."""
        return {
            'synced_items': [],
            'conflicts': [],
            'errors': [{
                'domain': self.DOMAIN_NAME,
                'error': error_message,
                'timestamp': self._get_current_timestamp()
            }],
            'domain': self.DOMAIN_NAME
        }

    def _get_current_timestamp(self) -> str:
        """Get current timestamp in ISO format."""
        from django.utils import timezone
        return timezone.now().isoformat()

    def validate_domain_specific_data(self, item_data: Dict[str, Any]) -> bool:
        """
        Validate domain-specific data before sync.

        Override in subclasses for domain-specific validation.

        Args:
            item_data: Item data to validate

        Returns:
            True if valid

        Raises:
            ValidationError: If data is invalid
        """
        return True

    def _upsert_item(
        self,
        user,
        item_data: Dict[str, Any],
        model_class: Type[Model],
        serializer_class: Type,
        extra_filters: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Override to add domain-specific validation and query optimization.
        """
        # Add domain-specific validation
        self.validate_domain_specific_data(item_data)

        # Add status transition validation if applicable
        if 'status' in item_data:
            mobile_id = item_data.get('mobile_id')
            if mobile_id:
                # Get current object to check status transition
                query_filters = self.build_sync_query_filters(user, extra_filters)
                query_filters &= self.Q(mobile_id=mobile_id)

                current_obj = self.get_optimized_object(model_class, query_filters)
                if current_obj:
                    current_status = getattr(current_obj, 'status', None)
                    new_status = item_data['status']

                    if not self.validate_status_transition(current_status, new_status):
                        return {
                            'mobile_id': str(mobile_id),
                            'status': 'error',
                            'error_message': f'Invalid status transition: {current_status} → {new_status}'
                        }

        # Call parent implementation with optimization
        return super()._upsert_item(user, item_data, model_class, serializer_class, extra_filters)

    def get_optimized_object(self, model_class, filters):
        """Get object with domain-specific query optimizations."""
        queryset = model_class.objects.filter(filters)
        return self.optimize_sync_queryset(queryset).first()

    # Import Q here to avoid circular imports
    from django.db.models import Q