"""
Sync Analytics Service for Mobile Offline Sync

Aggregates and analyzes sync metrics for monitoring and optimization.

Following .claude/rules.md:
- Rule #7: Service <150 lines
- Rule #11: Specific exception handling
"""

import logging
from django.db import DatabaseError
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.db.models import Count, Avg, Sum, Max, F
from datetime import timedelta
from typing import Dict, Any, Optional

from apps.core.models.sync_analytics import SyncAnalyticsSnapshot, SyncDeviceHealth
from apps.core.models.sync_conflict_policy import ConflictResolutionLog

logger = logging.getLogger(__name__)


class SyncAnalyticsService:
    """
    Service for collecting and analyzing sync metrics.

    Provides:
    - Periodic snapshot creation from sync logs
    - Device health score calculation
    - Conflict rate analysis
    - Bandwidth efficiency tracking
    """

    def create_snapshot(
        self,
        tenant_id: Optional[int] = None,
        time_window_hours: int = 1
    ) -> SyncAnalyticsSnapshot:
        """
        Create analytics snapshot for specified time window.

        Args:
            tenant_id: Filter for specific tenant
            time_window_hours: Hours to look back for metrics

        Returns:
            Created SyncAnalyticsSnapshot instance
        """
        try:
            since = timezone.now() - timedelta(hours=time_window_hours)

            conflict_logs = ConflictResolutionLog.objects.filter(created_at__gte=since)

            if tenant_id:
                conflict_logs = conflict_logs.filter(tenant_id=tenant_id)

            total_conflicts = conflict_logs.count()
            auto_resolved = conflict_logs.filter(resolution_result='resolved').count()
            manual_required = conflict_logs.filter(resolution_result='manual_required').count()

            conflict_rate = (total_conflicts / max(1, total_conflicts)) * 100 if total_conflicts > 0 else 0.0

            domain_stats = conflict_logs.values('domain').annotate(
                count=Count('id'),
                avg_server_version=Avg('server_version')
            )

            domain_breakdown = {
                stat['domain']: {
                    'conflicts': stat['count'],
                    'avg_server_version': stat['avg_server_version']
                }
                for stat in domain_stats
            }

            snapshot = SyncAnalyticsSnapshot.objects.create(
                tenant_id=tenant_id,
                total_sync_requests=conflict_logs.count(),
                successful_syncs=auto_resolved,
                failed_syncs=conflict_logs.filter(resolution_result='failed').count(),
                total_conflicts=total_conflicts,
                auto_resolved_conflicts=auto_resolved,
                manual_conflicts=manual_required,
                conflict_rate_pct=conflict_rate,
                domain_breakdown=domain_breakdown,
            )

            logger.info(
                f"Created sync snapshot for tenant {tenant_id}: "
                f"{total_conflicts} conflicts, {conflict_rate:.2f}% rate"
            )

            return snapshot

        except DatabaseError as e:
            logger.error(f"Database error creating sync snapshot: {e}", exc_info=True)
            raise DatabaseError(f"Failed to create snapshot: {e}")
        except (ValueError, TypeError) as e:
            logger.error(f"Data validation error: {e}")
            raise ValidationError(f"Invalid data for snapshot: {e}")

    def update_device_health(
        self,
        device_id: str,
        user,
        sync_success: bool,
        sync_duration_ms: float,
        conflict_occurred: bool = False
    ) -> SyncDeviceHealth:
        """
        Update device health metrics after sync operation.

        Args:
            device_id: Unique device identifier
            user: User associated with device
            sync_success: Whether sync was successful
            sync_duration_ms: Sync duration in milliseconds
            conflict_occurred: Whether conflict was encountered

        Returns:
            Updated SyncDeviceHealth instance
        """
        try:
            tenant_id = getattr(user, 'tenant_id', None)

            device_health, created = SyncDeviceHealth.objects.get_or_create(
                device_id=device_id,
                user=user,
                defaults={
                    'tenant_id': tenant_id,
                    'last_sync_at': timezone.now(),
                    'total_syncs': 0,
                    'failed_syncs_count': 0,
                    'avg_sync_duration_ms': 0.0,
                    'conflicts_encountered': 0,
                }
            )

            device_health.last_sync_at = timezone.now()
            device_health.total_syncs = F('total_syncs') + 1

            if not sync_success:
                device_health.failed_syncs_count = F('failed_syncs_count') + 1

            if conflict_occurred:
                device_health.conflicts_encountered = F('conflicts_encountered') + 1

            current_avg = device_health.avg_sync_duration_ms
            new_avg = (
                (current_avg * (device_health.total_syncs - 1) + sync_duration_ms)
                / device_health.total_syncs
            )
            device_health.avg_sync_duration_ms = new_avg

            device_health.save()
            device_health.refresh_from_db()

            device_health.update_health_score()

            return device_health

        except DatabaseError as e:
            logger.error(f"Database error updating device health: {e}", exc_info=True)
            raise DatabaseError(f"Failed to update device health: {e}")
        except (ValueError, TypeError) as e:
            logger.error(f"Invalid device health data: {e}")
            raise ValidationError(f"Invalid device data: {e}")

    def get_dashboard_metrics(self, tenant_id: Optional[int] = None) -> Dict[str, Any]:
        """
        Get comprehensive dashboard metrics.

        Returns:
            {
                latest_snapshot: {...},
                trend_7days: [...],
                unhealthy_devices: [...],
                conflict_hotspots: [...]
            }
        """
        try:
            latest = SyncAnalyticsSnapshot.get_latest_for_tenant(tenant_id) if tenant_id else None

            seven_days_ago = timezone.now() - timedelta(days=7)
            trend_data = SyncAnalyticsSnapshot.objects.filter(
                created_at__gte=seven_days_ago
            )

            if tenant_id:
                trend_data = trend_data.filter(tenant_id=tenant_id)

            trend_data = trend_data.order_by('timestamp')[:168]

            unhealthy_devices = SyncDeviceHealth.objects.filter(
                health_score__lt=70.0
            ).order_by('health_score')[:10]

            if tenant_id:
                unhealthy_devices = unhealthy_devices.filter(tenant_id=tenant_id)

            conflict_hotspots = ConflictResolutionLog.objects.filter(
                created_at__gte=seven_days_ago
            ).values('domain').annotate(
                conflict_count=Count('id')
            ).order_by('-conflict_count')[:5]

            return {
                'latest_snapshot': latest,
                'trend_7days': list(trend_data.values('timestamp', 'conflict_rate_pct', 'success_rate_pct')),
                'unhealthy_devices': list(unhealthy_devices.values(
                    'device_id', 'health_score', 'last_sync_at', 'user__peoplename'
                )),
                'conflict_hotspots': list(conflict_hotspots)
            }

        except DatabaseError as e:
            logger.error(f"Database error fetching dashboard metrics: {e}", exc_info=True)
            return {
                'latest_snapshot': None,
                'trend_7days': [],
                'unhealthy_devices': [],
                'conflict_hotspots': [],
                'error': str(e)
            }