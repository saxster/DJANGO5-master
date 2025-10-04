"""
Sync Analytics Dashboard Views

Provides API endpoints and UI views for sync monitoring.

Following .claude/rules.md:
- Rule #8: View methods <30 lines
- Rule #11: Specific exception handling
"""

import logging
from django.http import JsonResponse
from django.views import View
from django.core.exceptions import ValidationError, PermissionDenied
from django.db import DatabaseError
from django.contrib.auth.mixins import LoginRequiredMixin

from apps.core.services.sync_analytics_service import SyncAnalyticsService

logger = logging.getLogger(__name__)


class SyncDashboardAPIView(LoginRequiredMixin, View):
    """
    API endpoint for sync analytics dashboard data.

    GET /api/sync/dashboard/
    Returns:
        {
            latest_snapshot: {...},
            trend_7days: [...],
            unhealthy_devices: [...],
            conflict_hotspots: [...]
        }
    """

    def get(self, request):
        try:
            tenant_id = self._get_tenant_id(request.user)
            service = SyncAnalyticsService()
            metrics = service.get_dashboard_metrics(tenant_id=tenant_id)

            return JsonResponse(metrics, status=200)

        except PermissionDenied as e:
            logger.warning(f"Permission denied: {e}")
            return JsonResponse({'error': 'Permission denied'}, status=403)
        except DatabaseError as e:
            logger.error(f"Database error in dashboard view: {e}")
            return JsonResponse({'error': 'Service unavailable'}, status=503)
        except ValidationError as e:
            logger.warning(f"Validation error: {e}")
            return JsonResponse({'error': str(e)}, status=400)

    def _get_tenant_id(self, user):
        """Extract tenant ID from user context."""
        if hasattr(user, 'peopleorganizational'):
            org = user.peopleorganizational
            if hasattr(org, 'client') and org.client:
                return getattr(org.client, 'id', None)
        return None


class CreateSnapshotAPIView(LoginRequiredMixin, View):
    """
    API endpoint to manually trigger snapshot creation.

    POST /api/sync/snapshot/create/
    Body: {time_window_hours: 1}
    Returns: {snapshot_id: ..., status: "created"}
    """

    def post(self, request):
        try:
            if not request.user.is_staff:
                raise PermissionDenied("Admin access required")

            import json
            body = json.loads(request.body)
            time_window = body.get('time_window_hours', 1)

            tenant_id = self._get_tenant_id(request.user)
            service = SyncAnalyticsService()
            snapshot = service.create_snapshot(
                tenant_id=tenant_id,
                time_window_hours=time_window
            )

            return JsonResponse({
                'snapshot_id': snapshot.id,
                'status': 'created',
                'timestamp': snapshot.timestamp.isoformat()
            }, status=201)

        except PermissionDenied as e:
            logger.warning(f"Permission denied: {e}")
            return JsonResponse({'error': str(e)}, status=403)
        except (ValidationError, ValueError, json.JSONDecodeError) as e:
            logger.warning(f"Invalid request: {e}")
            return JsonResponse({'error': str(e)}, status=400)
        except DatabaseError as e:
            logger.error(f"Database error creating snapshot: {e}")
            return JsonResponse({'error': 'Service unavailable'}, status=503)

    def _get_tenant_id(self, user):
        """Extract tenant ID from user context."""
        if hasattr(user, 'peopleorganizational'):
            org = user.peopleorganizational
            if hasattr(org, 'client') and org.client:
                return getattr(org.client, 'id', None)
        return None


class DeviceHealthAPIView(LoginRequiredMixin, View):
    """
    API endpoint for device health metrics.

    GET /api/sync/device-health/?device_id=...
    Returns: {device_id, health_score, last_sync_at, ...}
    """

    def get(self, request):
        try:
            device_id = request.GET.get('device_id')

            if not device_id:
                raise ValidationError("device_id parameter required")

            from apps.core.models.sync_analytics import SyncDeviceHealth
            device_health = SyncDeviceHealth.objects.filter(
                device_id=device_id,
                user=request.user
            ).first()

            if not device_health:
                return JsonResponse({
                    'error': 'Device not found'
                }, status=404)

            return JsonResponse({
                'device_id': device_health.device_id,
                'health_score': device_health.health_score,
                'last_sync_at': device_health.last_sync_at.isoformat(),
                'total_syncs': device_health.total_syncs,
                'failed_syncs': device_health.failed_syncs_count,
                'avg_sync_duration_ms': device_health.avg_sync_duration_ms,
                'conflicts_encountered': device_health.conflicts_encountered,
                'network_type': device_health.network_type,
            }, status=200)

        except ValidationError as e:
            logger.warning(f"Validation error: {e}")
            return JsonResponse({'error': str(e)}, status=400)
        except DatabaseError as e:
            logger.error(f"Database error fetching device health: {e}")
            return JsonResponse({'error': 'Service unavailable'}, status=503)