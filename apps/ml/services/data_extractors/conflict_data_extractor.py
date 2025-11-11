"""
Conflict Data Extractor for ML Conflict Prediction

Extracts training data from SyncLog and ConflictResolution models for ML-based
conflict prediction.

Features Extracted:
- Concurrent editors count
- Hours since last sync
- User historical conflict rate
- Entity edit frequency
- Field overlap score

Created: November 2025 (Ultrathink Phase 4 - ML Conflict Prediction)

Following .claude/rules.md:
- Rule #7: Service < 150 lines
- Rule #11: Specific exception handling
- Rule #13: DateTime standards
"""

import logging
import pandas as pd
from datetime import timedelta
from typing import Dict, Any
from django.utils import timezone
from django.db.models import Count
from apps.core.exceptions.patterns import DATABASE_EXCEPTIONS

logger = logging.getLogger('ml.data_extraction')


class ConflictDataExtractor:
    """Extract training data for conflict prediction from sync logs."""

    def extract_training_data(self, days_back: int = 90) -> pd.DataFrame:
        """
        Extract sync events and conflict outcomes from past N days.

        Args:
            days_back: Number of days to look back (default: 90)

        Returns:
            DataFrame with features and target variable

        Raises:
            DATABASE_EXCEPTIONS: If database query fails
        """
        try:
            from apps.core.models.sync_tracking import SyncLog, ConflictResolution

            cutoff_date = timezone.now() - timedelta(days=days_back)

            # Get all sync logs in time window
            sync_logs = SyncLog.objects.filter(
                timestamp__gte=cutoff_date
            ).select_related('user').order_by('timestamp')

            if not sync_logs.exists():
                logger.warning(f"No sync logs found in past {days_back} days")
                return pd.DataFrame(columns=self._get_feature_columns())

            # Get all conflicts in time window
            conflicts = ConflictResolution.objects.filter(
                detected_at__gte=cutoff_date
            ).prefetch_related('sync_logs')

            # Build conflict lookup (sync_log_id -> conflict)
            conflict_lookup = {}
            for conflict in conflicts:
                for sync_log in conflict.sync_logs.all():
                    conflict_lookup[sync_log.id] = conflict

            # Extract features for each sync log
            data = []
            for sync_log in sync_logs:
                features = {
                    'id': sync_log.id,
                    'user_id': sync_log.user_id,
                    'entity_type': sync_log.entity_type,
                    'entity_id': sync_log.entity_id,
                    'timestamp': sync_log.timestamp,
                    'concurrent_editors': self._count_concurrent_editors(sync_log),
                    'hours_since_last_sync': self._hours_since_last_sync(sync_log),
                    'user_conflict_rate': self._user_conflict_rate(sync_log),
                    'entity_edit_frequency': self._entity_edit_frequency(sync_log),
                    'field_overlap_score': self._field_overlap_score(sync_log),
                    'conflict_occurred': 1 if sync_log.id in conflict_lookup else 0
                }
                data.append(features)

            df = pd.DataFrame(data)

            logger.info(
                f"Extracted {len(df)} sync events from past {days_back} days "
                f"({df['conflict_occurred'].sum()} conflicts)"
            )

            return df

        except DATABASE_EXCEPTIONS as e:
            logger.error(
                f"Failed to extract training data: {e}",
                exc_info=True
            )
            raise

    def _get_feature_columns(self) -> list:
        """Get list of feature column names."""
        return [
            'id', 'user_id', 'entity_type', 'entity_id', 'timestamp',
            'concurrent_editors', 'hours_since_last_sync', 'user_conflict_rate',
            'entity_edit_frequency', 'field_overlap_score', 'conflict_occurred'
        ]

    def _count_concurrent_editors(self, sync_log) -> int:
        """
        Count users editing same entity in ±5 minute window.

        Args:
            sync_log: SyncLog instance

        Returns:
            Count of concurrent editors (excluding self)
        """
        from apps.core.models.sync_tracking import SyncLog

        concurrent_logs = sync_log.get_concurrent_edits(time_window_seconds=300)
        unique_users = set(log.user_id for log in concurrent_logs)
        return len(unique_users)

    def _hours_since_last_sync(self, sync_log) -> float:
        """
        Calculate hours since user's previous sync.

        Args:
            sync_log: SyncLog instance

        Returns:
            Hours since last sync (default: 168 hours = 1 week)
        """
        from apps.core.models.sync_tracking import SyncLog

        previous_sync = SyncLog.objects.filter(
            user=sync_log.user,
            timestamp__lt=sync_log.timestamp
        ).order_by('-timestamp').first()

        if previous_sync:
            delta = sync_log.timestamp - previous_sync.timestamp
            return delta.total_seconds() / 3600
        return 168.0  # Default to 1 week

    def _user_conflict_rate(self, sync_log) -> float:
        """
        Calculate user's historical conflict rate (past 30 days).

        Args:
            sync_log: SyncLog instance

        Returns:
            Conflict rate (0.0-1.0)
        """
        from apps.core.models.sync_tracking import SyncLog, ConflictResolution

        cutoff = sync_log.timestamp - timedelta(days=30)

        # Get user's sync logs in past 30 days
        user_syncs = SyncLog.objects.filter(
            user=sync_log.user,
            timestamp__gte=cutoff,
            timestamp__lte=sync_log.timestamp
        ).count()

        if user_syncs == 0:
            return 0.0

        # Count conflicts involving this user
        user_conflicts = ConflictResolution.objects.filter(
            sync_logs__user=sync_log.user,
            detected_at__gte=cutoff,
            detected_at__lte=sync_log.timestamp
        ).distinct().count()

        return user_conflicts / user_syncs

    def _entity_edit_frequency(self, sync_log) -> float:
        """
        Calculate edit frequency for entity (edits per day, past 30 days).

        Args:
            sync_log: SyncLog instance

        Returns:
            Edits per day
        """
        from apps.core.models.sync_tracking import SyncLog

        cutoff = sync_log.timestamp - timedelta(days=30)

        edit_count = SyncLog.objects.filter(
            entity_type=sync_log.entity_type,
            entity_id=sync_log.entity_id,
            timestamp__gte=cutoff,
            timestamp__lte=sync_log.timestamp
        ).count()

        return edit_count / 30.0

    def _field_overlap_score(self, sync_log) -> float:
        """
        Calculate percentage of fields edited by multiple users.

        Args:
            sync_log: SyncLog instance

        Returns:
            Field overlap score (0.0-1.0)
        """
        if not sync_log.field_changes:
            return 0.0

        # Get concurrent edits
        concurrent_logs = sync_log.get_concurrent_edits(time_window_seconds=300)

        if not concurrent_logs:
            return 0.0

        # Calculate field overlap
        sync_fields = set(sync_log.field_changes.keys())
        overlapping_fields = set()

        for log in concurrent_logs:
            log_fields = set(log.field_changes.keys())
            overlapping_fields |= (sync_fields & log_fields)

        if not sync_fields:
            return 0.0

        return len(overlapping_fields) / len(sync_fields)

    def save_training_data(self, df: pd.DataFrame, output_path: str) -> None:
        """
        Save training data to CSV.

        Args:
            df: Training DataFrame
            output_path: CSV file path

        Raises:
            OSError: If file write fails
        """
        try:
            df.to_csv(output_path, index=False)
            logger.info(f"Training data saved to {output_path}")
        except OSError as e:
            logger.error(
                f"Failed to save training data to {output_path}: {e}",
                exc_info=True
            )
            raise
