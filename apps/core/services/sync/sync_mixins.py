"""
Sync Service Mixins - Shared functionality for mobile sync operations

Consolidates duplicate code patterns across domain-specific sync services.
Implements tenant filtering, status validation, and query optimization.

Following .claude/rules.md:
- Rule #7: Mixin classes <150 lines
- Rule #11: Specific exception handling
- Rule #12: Database query optimization with select_related()
"""

import logging
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, Set, List, Tuple
from django.db.models import Q
from django.core.exceptions import ValidationError
from django.core.cache import cache

logger = logging.getLogger(__name__)


class UserFilterMixin:
    """
    Mixin for consistent tenant filtering across sync services.

    Eliminates duplicate _get_user_filters() implementations found in:
    - TaskSyncService (apps/activity:96-110)
    - TicketSyncService (apps/y_helpdesk:98-108)
    - AttendanceSyncService (apps/attendance:83-95)
    """

    def get_user_filters(self, user, include_permissions: bool = True) -> Dict[str, Any]:
        """
        Get standardized multi-tenant filters based on user context.

        Args:
            user: Authenticated user with organizational data
            include_permissions: Whether to include permission-based filters

        Returns:
            Dict of filters for Django ORM queries

        Raises:
            ValidationError: If user lacks required organizational data
        """
        if not user or not user.is_authenticated:
            raise ValidationError("User must be authenticated for sync operations")

        filters = {}

        # Primary tenant filtering
        if hasattr(user, 'peopleorganizational'):
            org = user.peopleorganizational

            # Business unit filtering (highest priority)
            if hasattr(org, 'bu') and org.bu:
                filters['bu'] = org.bu

                # Include tenant if business unit has one
                if hasattr(org.bu, 'tenant') and org.bu.tenant:
                    filters['tenant'] = org.bu.tenant

            # Client filtering (fallback)
            elif hasattr(org, 'client') and org.client:
                filters['client'] = org.client

                # Include tenant if client has one
                if hasattr(org.client, 'tenant') and org.client.tenant:
                    filters['tenant'] = org.client.tenant

        # Permission-based filtering
        if include_permissions:
            permission_filters = self._get_permission_filters(user)
            filters.update(permission_filters)

        # Cache the filters for this user (5 minute TTL)
        cache_key = f"sync_user_filters:{user.id}"
        cache.set(cache_key, filters, 300)

        logger.debug(f"Generated filters for user {user.id}: {list(filters.keys())}")

        return filters

    def _get_permission_filters(self, user) -> Dict[str, Any]:
        """
        Get permission-based filters for data access control.

        Can be overridden by domain-specific services for custom logic.
        """
        filters = {}

        # Only show user's own data unless they have admin permissions
        if not getattr(user, 'isadmin', False):
            if hasattr(user, 'people'):
                filters['people'] = user.people
            else:
                filters['people'] = user

        return filters

    def build_sync_query_filters(self, user, extra_filters: Optional[Dict] = None) -> Q:
        """
        Build optimized Q object for sync queries with tenant isolation.

        Args:
            user: Authenticated user
            extra_filters: Additional domain-specific filters

        Returns:
            Q object for filtering queries
        """
        base_filters = self.get_user_filters(user)

        # Convert dict filters to Q object
        query_filters = Q()
        for key, value in base_filters.items():
            query_filters &= Q(**{key: value})

        # Add extra filters
        if extra_filters:
            for key, value in extra_filters.items():
                query_filters &= Q(**{key: value})

        return query_filters


class StatusTransitionMixin:
    """
    Mixin for standardized status transition validation.

    Consolidates different status validation implementations into
    configurable state machine pattern.
    """

    # Override in subclasses to define allowed transitions
    STATUS_TRANSITIONS: Dict[str, List[str]] = {}

    def validate_status_transition(self, current_status: str, new_status: str) -> bool:
        """
        Validate status transition using configured state machine.

        Args:
            current_status: Current object status
            new_status: Proposed new status

        Returns:
            True if transition is allowed
        """
        if not self.STATUS_TRANSITIONS:
            logger.warning(f"No status transitions defined for {self.__class__.__name__}")
            return True

        if current_status == new_status:
            return True

        current_upper = current_status.upper() if current_status else ''
        new_upper = new_status.upper() if new_status else ''

        allowed_transitions = self.STATUS_TRANSITIONS.get(current_upper, [])

        is_valid = new_upper in allowed_transitions

        if not is_valid:
            logger.warning(
                f"Invalid status transition: {current_status} → {new_status} "
                f"(allowed: {allowed_transitions})"
            )

        return is_valid

    def get_allowed_transitions(self, current_status: str) -> List[str]:
        """
        Get list of allowed status transitions from current state.

        Args:
            current_status: Current object status

        Returns:
            List of allowed next statuses
        """
        current_upper = current_status.upper() if current_status else ''
        return self.STATUS_TRANSITIONS.get(current_upper, [])


class SyncQueryOptimizationMixin:
    """
    Mixin for optimizing sync-related database queries.

    Implements consistent select_related() and prefetch_related() patterns
    to reduce database round trips.
    """

    # Override in subclasses to define optimization patterns
    SYNC_SELECT_RELATED: List[str] = []
    SYNC_PREFETCH_RELATED: List[str] = []

    def optimize_sync_queryset(self, queryset):
        """
        Apply query optimizations for sync operations.

        Args:
            queryset: Base queryset to optimize

        Returns:
            Optimized queryset with select_related/prefetch_related
        """
        if self.SYNC_SELECT_RELATED:
            queryset = queryset.select_related(*self.SYNC_SELECT_RELATED)

        if self.SYNC_PREFETCH_RELATED:
            queryset = queryset.prefetch_related(*self.SYNC_PREFETCH_RELATED)

        return queryset

    def get_optimized_object(self, model_class, filters: Q):
        """
        Get single object with sync optimizations applied.

        Args:
            model_class: Django model class
            filters: Q object for filtering

        Returns:
            Optimized model instance or None
        """
        queryset = model_class.objects.filter(filters)
        queryset = self.optimize_sync_queryset(queryset)

        return queryset.first()


class SyncMetadataMixin:
    """
    Mixin for consistent sync metadata handling.

    Standardizes mobile_id validation, version tracking, and
    sync field management across all sync services.
    """

    def extract_sync_metadata(self, obj) -> Dict[str, Any]:
        """
        Extract standardized sync metadata from model instance.

        Args:
            obj: Model instance with sync fields

        Returns:
            Dict of sync metadata
        """
        return {
            'mobile_id': str(getattr(obj, 'mobile_id', '')),
            'version': getattr(obj, 'version', 1),
            'sync_status': getattr(obj, 'sync_status', 'pending'),
            'last_sync_timestamp': getattr(obj, 'last_sync_timestamp', None),
            'created_at': getattr(obj, 'created_at', None),
            'updated_at': getattr(obj, 'updated_at', None),
        }

    def validate_sync_metadata(self, metadata: Dict[str, Any]) -> bool:
        """
        Validate sync metadata structure and values.

        Args:
            metadata: Sync metadata dict

        Returns:
            True if valid

        Raises:
            ValidationError: If metadata is invalid
        """
        required_fields = ['mobile_id', 'version']

        for field in required_fields:
            if field not in metadata or metadata[field] is None:
                raise ValidationError(f"Missing required sync field: {field}")

        # Validate mobile_id format (UUID)
        mobile_id = metadata['mobile_id']
        if not isinstance(mobile_id, str) or len(mobile_id) != 36:
            raise ValidationError(f"Invalid mobile_id format: {mobile_id}")

        # Validate version is positive integer
        version = metadata['version']
        if not isinstance(version, int) or version < 1:
            raise ValidationError(f"Invalid version number: {version}")

        return True