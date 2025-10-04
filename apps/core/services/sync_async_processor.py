"""
Sync Async Processor - Non-blocking operations for sync system

Handles non-critical sync operations asynchronously to improve response times:
- Analytics aggregation
- Health score calculations
- Cache warming
- Cleanup tasks

Follows .claude/rules.md:
- Rule #7: Service methods < 50 lines
- Rule #11: Specific exception handling
- Rule #17: Transaction management
"""

import logging
import asyncio
from typing import Dict, Any, Optional
from django.db import DatabaseError, transaction
from django.core.exceptions import ObjectDoesNotExist
from django.utils import timezone
from asgiref.sync import sync_to_async

from apps.core.models.sync_analytics import SyncAnalyticsSnapshot, SyncDeviceHealth
from apps.core.models.sync_conflict_policy import ConflictResolutionLog
from apps.core.services.sync_cache_service import sync_cache_service
from apps.core.utils_new.db_utils import get_current_db_name

logger = logging.getLogger(__name__)


class SyncAsyncProcessor:
    """
    Handles non-critical sync operations asynchronously.

    Use this for operations that don't need to block the sync response:
    - Device health score updates
    - Analytics aggregation
    - Cache warming
    - Historical data cleanup
    """

    @classmethod
    async def update_device_health_async(cls, device_id: str, user_id: int,
                                        tenant_id: Optional[int] = None) -> bool:
        """
        Update device health score asynchronously.

        Args:
            device_id: Device identifier
            user_id: User ID
            tenant_id: Optional tenant ID

        Returns:
            True if successful
        """
        try:
            device_health = await sync_to_async(
                SyncDeviceHealth.objects.select_for_update().get
            )(device_id=device_id, user_id=user_id)

            device_health.last_sync_at = timezone.now()
            device_health.total_syncs += 1

            device_health.update_health_score()

            health_data = {
                'health_score': device_health.health_score,
                'total_syncs': device_health.total_syncs,
                'last_sync_at': device_health.last_sync_at.isoformat(),
            }

            await sync_to_async(sync_cache_service.cache_device_health)(
                device_id, health_data
            )

            logger.debug(f"Updated device health for {device_id}: {device_health.health_score}")
            return True

        except ObjectDoesNotExist:
            await cls._create_device_health_record(device_id, user_id, tenant_id)
            return True
        except DatabaseError as e:
            logger.error(f"Failed to update device health: {e}", exc_info=True)
            return False

    @classmethod
    async def _create_device_health_record(cls, device_id: str, user_id: int,
                                          tenant_id: Optional[int]) -> None:
        """Create initial device health record."""
        try:
            await sync_to_async(SyncDeviceHealth.objects.create)(
                device_id=device_id,
                user_id=user_id,
                tenant_id=tenant_id,
                last_sync_at=timezone.now(),
                total_syncs=1,
                health_score=100.0
            )
            logger.info(f"Created device health record for {device_id}")
        except (DatabaseError, ValueError) as e:
            logger.error(f"Failed to create device health record: {e}", exc_info=True)

    @classmethod
    async def aggregate_analytics_async(cls, tenant_id: Optional[int] = None,
                                       hours: int = 1) -> bool:
        """
        Aggregate sync analytics for the past N hours.

        Args:
            tenant_id: Optional tenant filter
            hours: Hours to aggregate (default 1)

        Returns:
            True if successful
        """
        try:
            from django.db.models import Count, Avg, Sum
            from datetime import timedelta

            since = timezone.now() - timedelta(hours=hours)

            conflict_logs = ConflictResolutionLog.objects.filter(
                created_at__gte=since
            )

            if tenant_id:
                conflict_logs = conflict_logs.filter(tenant_id=tenant_id)

            stats = await sync_to_async(lambda: conflict_logs.aggregate(
                total_conflicts=Count('id'),
                auto_resolved=Count('id', filter=lambda q: q.filter(resolution_result='resolved')),
                manual_required=Count('id', filter=lambda q: q.filter(resolution_result='manual_required')),
            ))()

            device_stats = await sync_to_async(lambda: SyncDeviceHealth.objects.filter(
                last_sync_at__gte=since
            ).aggregate(
                unique_devices=Count('device_id', distinct=True),
                unique_users=Count('user_id', distinct=True),
                avg_sync_duration=Avg('avg_sync_duration_ms'),
            ))()

            snapshot_data = {
                'tenant_id': tenant_id,
                'total_conflicts': stats.get('total_conflicts', 0),
                'auto_resolved_conflicts': stats.get('auto_resolved', 0),
                'manual_conflicts': stats.get('manual_required', 0),
                'unique_devices': device_stats.get('unique_devices', 0),
                'unique_users': device_stats.get('unique_users', 0),
                'avg_sync_duration_ms': device_stats.get('avg_sync_duration', 0.0) or 0.0,
            }

            await sync_to_async(SyncAnalyticsSnapshot.objects.create)(**snapshot_data)

            logger.info(f"Aggregated analytics: {snapshot_data}")
            return True

        except (DatabaseError, ValueError, TypeError) as e:
            logger.error(f"Failed to aggregate analytics: {e}", exc_info=True)
            return False

    @classmethod
    async def warm_cache_for_tenant_async(cls, tenant_id: int) -> int:
        """
        Pre-warm cache with tenant policies asynchronously.

        Args:
            tenant_id: Tenant ID

        Returns:
            Number of policies cached
        """
        try:
            cached_count = await sync_to_async(
                sync_cache_service.warm_cache_for_tenant
            )(tenant_id)

            logger.info(f"Warmed cache for tenant {tenant_id}: {cached_count} policies")
            return cached_count

        except (DatabaseError, IOError, ValueError) as e:
            logger.error(f"Failed to warm cache: {e}", exc_info=True)
            return 0

    @classmethod
    async def cleanup_expired_records_async(cls, batch_size: int = 1000) -> Dict[str, int]:
        """
        Clean up expired records asynchronously.

        Args:
            batch_size: Records to delete per batch

        Returns:
            Dict with cleanup counts
        """
        try:
            from apps.core.models.sync_idempotency import SyncIdempotencyRecord
            from apps.core.models.upload_session import UploadSession

            idempotency_deleted = await sync_to_async(
                SyncIdempotencyRecord.cleanup_expired
            )()

            upload_deleted = await sync_to_async(
                UploadSession.cleanup_expired
            )()

            old_conflicts_deleted = await sync_to_async(
                cls._cleanup_old_conflict_logs
            )(days=90)

            cleanup_summary = {
                'idempotency_records': idempotency_deleted,
                'upload_sessions': upload_deleted,
                'old_conflicts': old_conflicts_deleted,
            }

            logger.info(f"Cleanup completed: {cleanup_summary}")
            return cleanup_summary

        except (DatabaseError, ValueError) as e:
            logger.error(f"Cleanup failed: {e}", exc_info=True)
            return {}

    @staticmethod
    def _cleanup_old_conflict_logs(days: int = 90) -> int:
        """Delete conflict logs older than N days."""
        from datetime import timedelta

        cutoff = timezone.now() - timedelta(days=days)
        deleted_count, _ = ConflictResolutionLog.objects.filter(
            created_at__lt=cutoff
        ).delete()

        return deleted_count

    @classmethod
    async def process_batch_async(cls, tasks: list) -> Dict[str, Any]:
        """
        Process multiple async tasks concurrently.

        Args:
            tasks: List of coroutines to execute

        Returns:
            Dict with results and errors
        """
        try:
            results = await asyncio.gather(*tasks, return_exceptions=True)

            successes = sum(1 for r in results if not isinstance(r, Exception))
            failures = sum(1 for r in results if isinstance(r, Exception))

            errors = [
                str(r) for r in results if isinstance(r, Exception)
            ]

            return {
                'total': len(tasks),
                'successes': successes,
                'failures': failures,
                'errors': errors[:5],
            }

        except (asyncio.CancelledError, ValueError) as e:
            logger.error(f"Batch processing failed: {e}", exc_info=True)
            return {'total': len(tasks), 'successes': 0, 'failures': len(tasks), 'errors': [str(e)]}


sync_async_processor = SyncAsyncProcessor()