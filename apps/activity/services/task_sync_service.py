"""
Task Sync Service for Activity/JobNeed Domain

Handles mobile sync operations for tasks (JobNeed model) with conflict detection
and multi-tenant isolation.

Following .claude/rules.md:
- Rule #7: Service <150 lines
- Rule #11: Specific exception handling
"""

import logging
from django.core.exceptions import ValidationError, ObjectDoesNotExist
from django.db import IntegrityError
from typing import Dict, Any, Optional

from apps.api.v1.services.base_sync_service import BaseSyncService
from apps.activity.models.job_model import Jobneed


logger = logging.getLogger(__name__)


class TaskSyncService(BaseSyncService):
    """
    Service for syncing JobNeed (Task) records from mobile clients.

    Provides:
    - Bulk task sync with conflict detection
    - Multi-tenant isolation (bu/client filtering)
    - Permission validation
    - Delta sync for pulling server changes
    """

    def sync_tasks(
        self,
        user,
        sync_data: Dict[str, Any],
        serializer_class
    ) -> Dict[str, Any]:
        """
        Sync tasks from mobile client.

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
            model_class=Jobneed,
            serializer_class=serializer_class,
            extra_filters=extra_filters
        )

    def get_task_changes(
        self,
        user,
        timestamp: Optional[str] = None,
        limit: int = 100
    ) -> Dict[str, Any]:
        """
        Get task changes since timestamp for delta sync.

        Args:
            user: Authenticated user
            timestamp: ISO timestamp for delta query
            limit: Maximum records to return

        Returns:
            {items: [...], has_more: bool, next_timestamp: ...}
        """
        if not user or not user.is_authenticated:
            raise ValidationError("User must be authenticated")

        extra_filters = self._get_user_filters(user)

        return self.get_changes_since(
            user=user,
            timestamp=timestamp,
            model_class=Jobneed,
            extra_filters=extra_filters,
            limit=limit
        )

    def _get_user_filters(self, user) -> Dict[str, Any]:
        """
        Get multi-tenant filters based on user context.

        Ensures users only see tasks for their business unit/client.
        """
        filters = {}

        if hasattr(user, 'peopleorganizational'):
            org = user.peopleorganizational
            if org.bu:
                filters['bu'] = org.bu
            if org.client:
                filters['client'] = org.client

        return filters

    def validate_task_status_transition(
        self,
        current_status: str,
        new_status: str
    ) -> bool:
        """
        Validate task status transitions.

        Allowed transitions:
        - ASSIGNED → INPROGRESS
        - INPROGRESS → COMPLETED, PARTIALLYCOMPLETED
        - PARTIALLYCOMPLETED → COMPLETED
        - Any → STANDBY (for maintenance)
        """
        if current_status == new_status:
            return True

        allowed_transitions = {
            'ASSIGNED': ['INPROGRESS', 'STANDBY'],
            'INPROGRESS': ['COMPLETED', 'PARTIALLYCOMPLETED', 'STANDBY'],
            'PARTIALLYCOMPLETED': ['COMPLETED', 'INPROGRESS', 'STANDBY'],
            'STANDBY': ['ASSIGNED', 'INPROGRESS'],
            'COMPLETED': ['STANDBY'],
        }

        if current_status not in allowed_transitions:
            return True

        return new_status in allowed_transitions[current_status]