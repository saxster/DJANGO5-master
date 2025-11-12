"""
Conflict Detector Service for ML Conflict Prediction

Detects conflicts arising from concurrent edits by analyzing SyncLog entries.

Detection Patterns:
- Concurrent Edit: Multiple users editing same entity within time window
- Field Collision: Multiple users changing same fields
- Stale Update: User updating with outdated data

Created: November 2025 (Ultrathink Phase 4 - ML Conflict Prediction)
"""

import logging
from typing import Optional, List, Set
from datetime import timedelta
from django.utils import timezone
from django.db import DatabaseError, transaction

from apps.core.models.sync_tracking import SyncLog, ConflictResolution

logger = logging.getLogger(__name__)


class ConflictDetector:
    """
    Service for detecting sync conflicts in real-time.

    Purpose:
    - Real-time conflict detection
    - ML training data generation
    - User notification triggers
    """

    # Time window for detecting concurrent edits (5 minutes)
    CONFLICT_WINDOW_SECONDS = 300

    # Minimum field overlap to trigger conflict
    MIN_FIELD_OVERLAP = 1

    @classmethod
    def detect_concurrent_edits(cls, sync_log: SyncLog) -> Optional[ConflictResolution]:
        """
        Detect if this sync operation conflicts with recent edits.

        Args:
            sync_log: SyncLog entry to check for conflicts

        Returns:
            ConflictResolution if conflict detected, None otherwise
        """
        try:
            # Find concurrent edits within time window
            concurrent_edits = cls._find_concurrent_edits(sync_log)

            if not concurrent_edits:
                return None

            # Check for field collisions
            conflicting_edits = cls._filter_field_collisions(sync_log, concurrent_edits)

            if not conflicting_edits:
                return None

            # Create conflict resolution record
            conflict = cls._create_conflict_record(
                sync_log,
                conflicting_edits,
                conflict_type='concurrent_edit'
            )

            logger.warning(
                f"Conflict detected: {conflict.conflict_type} for {sync_log.entity_type}:{sync_log.entity_id}",
                extra={
                    'conflict_id': conflict.id,
                    'sync_log_id': sync_log.id,
                    'user_count': len(set(log.user_id for log in conflicting_edits + [sync_log])),
                    'field_overlap': len(cls._get_overlapping_fields(sync_log, conflicting_edits))
                }
            )

            return conflict

        except (DatabaseError, Exception) as e:
            logger.error(
                f"Conflict detection failed for sync_log {sync_log.id}: {e}",
                exc_info=True
            )
            return None

    @classmethod
    def _find_concurrent_edits(cls, sync_log: SyncLog) -> List[SyncLog]:
        """
        Find other edits to same entity within time window.

        Args:
            sync_log: SyncLog to check

        Returns:
            List of concurrent SyncLog entries
        """
        window_start = sync_log.timestamp - timedelta(seconds=cls.CONFLICT_WINDOW_SECONDS)
        window_end = sync_log.timestamp + timedelta(seconds=cls.CONFLICT_WINDOW_SECONDS)

        concurrent_edits = SyncLog.objects.filter(
            entity_type=sync_log.entity_type,
            entity_id=sync_log.entity_id,
            timestamp__gte=window_start,
            timestamp__lte=window_end
        ).exclude(
            pk=sync_log.pk
        ).exclude(
            user=sync_log.user  # Exclude same user
        )

        return list(concurrent_edits)

    @classmethod
    def _filter_field_collisions(cls, sync_log: SyncLog, concurrent_edits: List[SyncLog]) -> List[SyncLog]:
        """
        Filter concurrent edits to only those with field collisions.

        Args:
            sync_log: SyncLog to check
            concurrent_edits: List of concurrent edits

        Returns:
            List of SyncLog entries with field collisions
        """
        sync_fields = set(sync_log.field_changes.keys())
        conflicting_edits = []

        for edit in concurrent_edits:
            edit_fields = set(edit.field_changes.keys())
            overlap = sync_fields & edit_fields

            if len(overlap) >= cls.MIN_FIELD_OVERLAP:
                conflicting_edits.append(edit)

        return conflicting_edits

    @classmethod
    def _get_overlapping_fields(cls, sync_log: SyncLog, concurrent_edits: List[SyncLog]) -> Set[str]:
        """
        Get set of fields that have conflicts.

        Args:
            sync_log: SyncLog to check
            concurrent_edits: List of concurrent edits

        Returns:
            Set of overlapping field names
        """
        sync_fields = set(sync_log.field_changes.keys())
        all_overlaps = set()

        for edit in concurrent_edits:
            edit_fields = set(edit.field_changes.keys())
            all_overlaps |= (sync_fields & edit_fields)

        return all_overlaps

    @classmethod
    @transaction.atomic
    def _create_conflict_record(
        cls,
        sync_log: SyncLog,
        conflicting_edits: List[SyncLog],
        conflict_type: str = 'concurrent_edit'
    ) -> ConflictResolution:
        """
        Create ConflictResolution record.

        Args:
            sync_log: Primary SyncLog entry
            conflicting_edits: List of conflicting SyncLog entries
            conflict_type: Type of conflict detected

        Returns:
            ConflictResolution instance
        """
        # Calculate severity based on field overlap
        overlapping_fields = cls._get_overlapping_fields(sync_log, conflicting_edits)
        severity = cls._calculate_severity(len(overlapping_fields), len(conflicting_edits))

        # Create conflict record
        conflict = ConflictResolution.objects.create(
            tenant=sync_log.tenant,
            conflict_type=conflict_type,
            detected_at=timezone.now(),
            resolution_strategy='unresolved',
            severity=severity,
            resolution_data={
                'conflicting_fields': list(overlapping_fields),
                'user_count': len(set(log.user_id for log in conflicting_edits + [sync_log])),
                'time_window_seconds': cls.CONFLICT_WINDOW_SECONDS
            }
        )

        # Associate all involved sync logs
        conflict.sync_logs.add(sync_log)
        conflict.sync_logs.add(*conflicting_edits)

        return conflict

    @classmethod
    def _calculate_severity(cls, field_overlap_count: int, edit_count: int) -> str:
        """
        Calculate conflict severity.

        Args:
            field_overlap_count: Number of overlapping fields
            edit_count: Number of conflicting edits

        Returns:
            Severity level (low/medium/high/critical)
        """
        # Critical: Many fields, many users
        if field_overlap_count >= 5 or edit_count >= 4:
            return 'critical'

        # High: Multiple fields or users
        if field_overlap_count >= 3 or edit_count >= 2:
            return 'high'

        # Medium: Some overlap
        if field_overlap_count >= 2:
            return 'medium'

        # Low: Minimal overlap
        return 'low'

    @classmethod
    def resolve_conflict(
        cls,
        conflict_id: int,
        strategy: str = 'last_write_wins',
        resolution_data: dict = None
    ) -> bool:
        """
        Mark conflict as resolved.

        Args:
            conflict_id: ConflictResolution ID
            strategy: Resolution strategy used
            resolution_data: Additional resolution details

        Returns:
            True if successful
        """
        try:
            conflict = ConflictResolution.objects.get(pk=conflict_id)
            conflict.mark_resolved(strategy, resolution_data or {})

            logger.info(
                f"Conflict {conflict_id} resolved using {strategy}",
                extra={'conflict_id': conflict_id, 'strategy': strategy}
            )

            return True

        except ConflictResolution.DoesNotExist:
            logger.error(f"Conflict {conflict_id} not found")
            return False
        except Exception as e:
            logger.error(f"Failed to resolve conflict {conflict_id}: {e}", exc_info=True)
            return False

    @classmethod
    def get_unresolved_conflicts(cls, entity_type: str = None, severity: str = None) -> List[ConflictResolution]:
        """
        Get unresolved conflicts, optionally filtered.

        Args:
            entity_type: Filter by entity type
            severity: Filter by severity

        Returns:
            List of unresolved ConflictResolution entries
        """
        queryset = ConflictResolution.objects.filter(resolved_at__isnull=True)

        if entity_type:
            queryset = queryset.filter(sync_logs__entity_type=entity_type).distinct()

        if severity:
            queryset = queryset.filter(severity=severity)

        return list(queryset.order_by('-detected_at'))

    @classmethod
    def get_conflict_statistics(cls, days: int = 7) -> dict:
        """
        Get conflict statistics for the past N days.

        Args:
            days: Number of days to analyze

        Returns:
            Dict with conflict statistics
        """
        cutoff_date = timezone.now() - timedelta(days=days)

        conflicts = ConflictResolution.objects.filter(detected_at__gte=cutoff_date)

        stats = {
            'total_conflicts': conflicts.count(),
            'unresolved_conflicts': conflicts.filter(resolved_at__isnull=True).count(),
            'by_type': {},
            'by_severity': {},
            'average_resolution_time_seconds': None
        }

        # Count by type
        for conflict_type, _ in ConflictResolution._meta.get_field('conflict_type').choices:
            count = conflicts.filter(conflict_type=conflict_type).count()
            if count > 0:
                stats['by_type'][conflict_type] = count

        # Count by severity
        for severity, _ in ConflictResolution._meta.get_field('severity').choices:
            count = conflicts.filter(severity=severity).count()
            if count > 0:
                stats['by_severity'][severity] = count

        # Calculate average resolution time
        resolved_conflicts = conflicts.filter(resolved_at__isnull=False)
        if resolved_conflicts.exists():
            resolution_times = [
                (c.resolved_at - c.detected_at).total_seconds()
                for c in resolved_conflicts
                if c.resolved_at
            ]
            if resolution_times:
                stats['average_resolution_time_seconds'] = sum(resolution_times) / len(resolution_times)

        return stats
