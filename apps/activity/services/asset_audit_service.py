"""
Asset Audit Service for Comprehensive Change Tracking (Sprint 4.4)

Provides field-level change tracking and lifecycle management for assets:
- Track all field changes with before/after values
- User attribution for all changes
- Change reason documentation
- Lifecycle stage transitions
- Audit trail queries

Author: Development Team
Date: October 2025
"""

import logging
import json
from typing import Dict, Any, List, Optional
from django.db import transaction, DatabaseError, IntegrityError
from django.utils import timezone

from apps.activity.models import Asset, AssetFieldHistory, AssetLifecycleStage

logger = logging.getLogger(__name__)


class AssetAuditService:
    """
    Service for comprehensive asset audit trail management.

    Tracks all field-level changes and lifecycle transitions with
    full user attribution and change documentation.
    """

    # Fields to exclude from change tracking (auto-managed)
    EXCLUDED_FIELDS = {'id', 'mdtz', 'tenant', 'enable'}

    def track_asset_changes(
        self,
        asset: Asset,
        old_values: Dict[str, Any],
        new_values: Dict[str, Any],
        changed_by_id: int,
        change_reason: str = "",
        change_source: str = "WEB_UI",
        metadata: Dict[str, Any] = None
    ) -> List[AssetFieldHistory]:
        """
        Track field-level changes for an asset.

        Args:
            asset: Asset instance
            old_values: Dictionary of old field values
            new_values: Dictionary of new field values
            changed_by_id: User ID who made the change
            change_reason: Reason for the change
            change_source: Source of change (WEB_UI, API, etc.)
            metadata: Additional metadata (IP, user agent, etc.)

        Returns:
            List of created AssetFieldHistory records
        """
        try:
            history_records = []

            with transaction.atomic():
                # Compare fields and create history records
                for field_name, new_value in new_values.items():
                    # Skip excluded fields
                    if field_name in self.EXCLUDED_FIELDS:
                        continue

                    old_value = old_values.get(field_name)

                    # Only track if value actually changed
                    if old_value != new_value:
                        # Serialize complex values
                        old_value_str = self._serialize_value(old_value)
                        new_value_str = self._serialize_value(new_value)

                        history_record = AssetFieldHistory.objects.create(
                            asset=asset,
                            field_name=field_name,
                            old_value=old_value_str,
                            new_value=new_value_str,
                            changed_by_id=changed_by_id,
                            change_reason=change_reason,
                            change_source=change_source,
                            tenant_id=asset.tenant_id,
                            metadata=metadata or {}
                        )

                        history_records.append(history_record)

                        logger.info(
                            f"Asset {asset.assetcode} field changed: "
                            f"{field_name} = {old_value_str} → {new_value_str}"
                        )

            return history_records

        except (DatabaseError, IntegrityError) as e:
            logger.error(f"Error tracking asset changes: {e}")
            return []

    def _serialize_value(self, value: Any) -> str:
        """
        Serialize field value to string for storage.

        Args:
            value: Field value (any type)

        Returns:
            String representation
        """
        if value is None:
            return ""
        elif isinstance(value, (dict, list)):
            return json.dumps(value)
        else:
            return str(value)

    def get_field_history(
        self,
        asset_id: int,
        field_name: Optional[str] = None,
        tenant_id: int = None,
        days: int = 90
    ) -> List[Dict[str, Any]]:
        """
        Get field change history for an asset.

        Args:
            asset_id: Asset ID
            field_name: Specific field name (optional, returns all if not specified)
            tenant_id: Tenant ID for multi-tenancy
            days: Number of days to look back

        Returns:
            List of change history records
        """
        try:
            from datetime import timedelta

            since_date = timezone.now() - timedelta(days=days)

            query = AssetFieldHistory.objects.filter(
                asset_id=asset_id,
                tenant_id=tenant_id,
                cdtz__gte=since_date
            ).select_related('changed_by', 'asset')

            if field_name:
                query = query.filter(field_name=field_name)

            history = query.order_by('-cdtz')[:100]  # Limit to 100 most recent

            return [
                {
                    'id': str(record.id),
                    'field_name': record.field_name,
                    'old_value': record.old_value,
                    'new_value': record.new_value,
                    'changed_by': record.changed_by.username if record.changed_by else 'System',
                    'changed_at': record.cdtz.isoformat(),
                    'change_reason': record.change_reason,
                    'change_source': record.change_source
                }
                for record in history
            ]

        except Exception as e:
            logger.error(f"Error retrieving field history: {e}")
            return []

    def transition_lifecycle_stage(
        self,
        asset: Asset,
        new_stage: str,
        transitioned_by_id: int,
        notes: str = "",
        stage_metadata: Dict[str, Any] = None
    ) -> Optional[AssetLifecycleStage]:
        """
        Transition asset to a new lifecycle stage.

        Args:
            asset: Asset instance
            new_stage: New lifecycle stage
            transitioned_by_id: User ID performing transition
            notes: Optional notes about the transition
            stage_metadata: Stage-specific metadata

        Returns:
            Created AssetLifecycleStage instance or None on error
        """
        try:
            with transaction.atomic():
                # End current stage
                current_stages = AssetLifecycleStage.objects.filter(
                    asset=asset,
                    is_current=True
                )

                for current_stage in current_stages:
                    current_stage.is_current = False
                    current_stage.stage_ended = timezone.now()
                    current_stage.save(update_fields=['is_current', 'stage_ended'])

                # Create new stage
                new_stage_record = AssetLifecycleStage.objects.create(
                    asset=asset,
                    stage=new_stage,
                    stage_started=timezone.now(),
                    is_current=True,
                    stage_metadata=stage_metadata or {},
                    transitioned_by_id=transitioned_by_id,
                    notes=notes,
                    tenant_id=asset.tenant_id
                )

                logger.info(
                    f"Asset {asset.assetcode} lifecycle stage transitioned to {new_stage}"
                )

                return new_stage_record

        except (DatabaseError, IntegrityError) as e:
            logger.error(f"Error transitioning lifecycle stage: {e}")
            return None

    def get_lifecycle_history(
        self,
        asset_id: int,
        tenant_id: int
    ) -> List[Dict[str, Any]]:
        """
        Get complete lifecycle history for an asset.

        Args:
            asset_id: Asset ID
            tenant_id: Tenant ID

        Returns:
            List of lifecycle stage records
        """
        try:
            stages = AssetLifecycleStage.objects.filter(
                asset_id=asset_id,
                tenant_id=tenant_id
            ).select_related('transitioned_by').order_by('-stage_started')

            return [
                {
                    'stage': stage.stage,
                    'stage_started': stage.stage_started.isoformat(),
                    'stage_ended': stage.stage_ended.isoformat() if stage.stage_ended else None,
                    'is_current': stage.is_current,
                    'duration_days': (
                        (stage.stage_ended or timezone.now()) - stage.stage_started
                    ).days,
                    'transitioned_by': stage.transitioned_by.username if stage.transitioned_by else 'System',
                    'notes': stage.notes,
                    'metadata': stage.stage_metadata
                }
                for stage in stages
            ]

        except Exception as e:
            logger.error(f"Error retrieving lifecycle history: {e}")
            return []
