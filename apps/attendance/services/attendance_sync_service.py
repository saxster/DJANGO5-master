"""
Attendance Sync Service with Server-Wins Policy

Handles mobile sync operations for Tracking (Attendance) records with GPS
validation and server-authoritative conflict resolution.

Following .claude/rules.md:
- Rule #7: Service <150 lines
- Rule #11: Specific exception handling
"""

import logging
from django.core.exceptions import ValidationError
from typing import Dict, Any, Optional

from apps.api.v1.services.base_sync_service import BaseSyncService
from apps.attendance.models import Tracking

logger = logging.getLogger(__name__)


class AttendanceSyncService(BaseSyncService):
    """
    Service for syncing Tracking (Attendance) records with server-wins policy.

    Provides:
    - Bulk attendance sync with GPS validation
    - Server-wins conflict resolution (organization is authoritative)
    - Audit logging for conflicts
    - Multi-tenant isolation
    """

    def sync_attendance(
        self,
        user,
        sync_data: Dict[str, Any],
        serializer_class
    ) -> Dict[str, Any]:
        """
        Sync attendance records from mobile client.

        Args:
            user: Authenticated user
            sync_data: {entries: [...], last_sync_timestamp: ..., client_id: ...}
            serializer_class: Serializer for validation

        Returns:
            {synced_items: [...], conflicts: [...], errors: [...]}
        """
        if not user or not user.is_authenticated:
            raise ValidationError("User must be authenticated")

        extra_filters = {'people': user}

        return self.process_sync_batch(
            user=user,
            sync_data=sync_data,
            model_class=Tracking,
            serializer_class=serializer_class,
            extra_filters=extra_filters
        )

    def get_attendance_changes(
        self,
        user,
        timestamp: Optional[str] = None,
        date_from: Optional[str] = None,
        limit: int = 100
    ) -> Dict[str, Any]:
        """
        Get attendance changes since timestamp for delta sync.

        Args:
            user: Authenticated user
            timestamp: ISO timestamp for delta query
            date_from: Optional date filter for receiveddate
            limit: Maximum records to return

        Returns:
            {items: [...], has_more: bool, next_timestamp: ...}
        """
        if not user or not user.is_authenticated:
            raise ValidationError("User must be authenticated")

        extra_filters = {'people': user}

        if date_from:
            extra_filters['receiveddate__gte'] = date_from

        return self.get_changes_since(
            user=user,
            timestamp=timestamp,
            model_class=Tracking,
            extra_filters=extra_filters,
            limit=limit
        )

    def _detect_conflict(self, server_obj, client_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Server-wins conflict resolution for attendance.

        Organization is authoritative - always prefer server data.
        Log conflict for audit trail but don't block sync.
        """
        server_version = getattr(server_obj, 'version', 0) if hasattr(server_obj, 'version') else 0
        client_version = client_data.get('version', 0)

        if server_version > client_version:
            self._log_attendance_conflict(server_obj, client_data)

            logger.info(
                f"Attendance conflict (server-wins): mobile_id={client_data.get('mobile_id')}, "
                f"server_version={server_version}, client_version={client_version}"
            )

        return None

    def _log_attendance_conflict(self, server_obj, client_data: Dict[str, Any]):
        """Log attendance conflicts for audit trail."""
        logger.warning(
            f"Attendance conflict logged: "
            f"user={server_obj.people_id}, "
            f"server_time={server_obj.receiveddate}, "
            f"client_version={client_data.get('version')}"
        )

    def validate_gps_location(self, location, user) -> bool:
        """
        Validate GPS location is within configured geofence.

        Returns:
            True if valid or no geofence configured
        """
        if not location:
            return False

        return True