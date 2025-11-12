"""
Work Order Sync Service for WOM Domain

Handles mobile sync operations for Work Orders (WOM model) with status
transition validation and conflict detection.

Following .claude/rules.md:
- Rule #7: Service <150 lines
- Rule #11: Specific exception handling
"""

import logging
from django.core.exceptions import ValidationError
from typing import Dict, Any, Optional

from apps.core.services.sync.base_sync_service import BaseSyncService
from apps.work_order_management.models import Wom

logger = logging.getLogger(__name__)


class WOMSyncService(BaseSyncService):
    """
    Service for syncing WOM (Work Order) records from mobile clients.

    Provides:
    - Bulk work order sync with conflict detection
    - Status transition validation
    - Multi-tenant isolation
    - Delta sync for pulling server changes
    """

    def sync_work_orders(
        self,
        user,
        sync_data: Dict[str, Any],
        serializer_class
    ) -> Dict[str, Any]:
        """
        Sync work orders from mobile client.

        Args:
            user: Authenticated user
            sync_data: {entries: [...], last_sync_timestamp: ..., client_id: ...}
            serializer_class: Serializer for validation

        Returns:
            {synced_items: [...], conflicts: [...], errors: [...]}
        """
        if not user or not user.is_authenticated:
            raise ValidationError("User must be authenticated")

        extra_filters = self._get_user_filters(user)

        return self.process_sync_batch(
            user=user,
            sync_data=sync_data,
            model_class=Wom,
            serializer_class=serializer_class,
            extra_filters=extra_filters
        )

    def get_work_order_changes(
        self,
        user,
        timestamp: Optional[str] = None,
        status_filter: Optional[str] = None,
        limit: int = 100
    ) -> Dict[str, Any]:
        """
        Get work order changes since timestamp for delta sync.

        Args:
            user: Authenticated user
            timestamp: ISO timestamp for delta query
            status_filter: Optional status filter (in_progress, completed, etc.)
            limit: Maximum records to return

        Returns:
            {items: [...], has_more: bool, next_timestamp: ...}
        """
        if not user or not user.is_authenticated:
            raise ValidationError("User must be authenticated")

        extra_filters = self._get_user_filters(user)

        if status_filter:
            extra_filters['status'] = status_filter

        return self.get_changes_since(
            user=user,
            timestamp=timestamp,
            model_class=Wom,
            extra_filters=extra_filters,
            limit=limit
        )

    def _get_user_filters(self, user) -> Dict[str, Any]:
        """Get multi-tenant filters based on user context."""
        filters = {}

        if hasattr(user, 'peopleorganizational'):
            org = user.peopleorganizational
            if org.bu:
                filters['bu'] = org.bu
            if org.client:
                filters['client'] = org.client

        return filters

    def validate_status_transition(
        self,
        current_status: str,
        new_status: str
    ) -> bool:
        """
        Validate work order status transitions.

        Allowed transitions:
        - draft → in_progress
        - in_progress → completed, paused
        - paused → in_progress, cancelled
        - completed → closed
        """
        if current_status == new_status:
            return True

        allowed_transitions = {
            'draft': ['in_progress', 'cancelled'],
            'in_progress': ['completed', 'paused', 'cancelled'],
            'paused': ['in_progress', 'cancelled'],
            'completed': ['closed'],
            'closed': [],
            'cancelled': []
        }

        current_lower = current_status.lower() if current_status else 'draft'
        new_lower = new_status.lower() if new_status else 'draft'

        if current_lower not in allowed_transitions:
            return True

        return new_lower in allowed_transitions[current_lower]