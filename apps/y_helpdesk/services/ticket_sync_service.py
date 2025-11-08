"""
Ticket Sync Service with Escalation Preservation

Handles mobile sync operations for Ticket records with status transition
validation and escalation workflow preservation.

Following .claude/rules.md:
- Rule #7: Service <150 lines
- Rule #11: Specific exception handling
"""

import logging
from django.core.exceptions import ValidationError
from typing import Dict, Any, Optional

from apps.core.services.sync.base_sync_service import BaseSyncService
from apps.y_helpdesk.models import Ticket
from .ticket_state_machine import TicketStateMachine

logger = logging.getLogger(__name__)


class TicketSyncService(BaseSyncService):
    """
    Service for syncing Ticket records with escalation preservation.

    Provides:
    - Bulk ticket sync with conflict detection
    - Status transition validation
    - Escalation workflow preservation (server-side takes precedence)
    - Ticket history logging
    """

    def sync_tickets(
        self,
        user,
        sync_data: Dict[str, Any],
        serializer_class
    ) -> Dict[str, Any]:
        """
        Sync tickets from mobile client.

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
            model_class=Ticket,
            serializer_class=serializer_class,
            extra_filters=extra_filters
        )

    def get_ticket_changes(
        self,
        user,
        timestamp: Optional[str] = None,
        priority_filter: Optional[str] = None,
        limit: int = 100
    ) -> Dict[str, Any]:
        """
        Get ticket changes since timestamp for delta sync.

        Args:
            user: Authenticated user
            timestamp: ISO timestamp for delta query
            priority_filter: Optional priority filter (HIGH, MEDIUM, LOW)
            limit: Maximum records to return

        Returns:
            {items: [...], has_more: bool, next_timestamp: ...}
        """
        if not user or not user.is_authenticated:
            raise ValidationError("User must be authenticated")

        extra_filters = self._get_user_filters(user)

        if priority_filter:
            extra_filters['priority'] = priority_filter.upper()

        return self.get_changes_since(
            user=user,
            timestamp=timestamp,
            model_class=Ticket,
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
        Validate ticket status transitions using centralized TicketStateMachine.

        Args:
            current_status: Current ticket status
            new_status: Target status

        Returns:
            True if transition is valid
        """
        # Delegate to centralized TicketStateMachine
        return TicketStateMachine.is_valid_transition(current_status, new_status)