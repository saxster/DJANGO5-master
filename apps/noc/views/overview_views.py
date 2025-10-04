"""
NOC Overview Views.

REST API endpoint for dashboard overview metrics with aggregation.
Follows .claude/rules.md Rule #8 (view methods <30 lines), Rule #12 (query optimization).
"""

import logging
from datetime import timedelta
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from django.utils import timezone
from apps.noc.decorators import require_noc_capability
from apps.noc.models import NOCMetricSnapshot, NOCAlertEvent, NOCIncident
from apps.noc.serializers import MetricOverviewSerializer
from apps.noc.services import NOCRBACService, NOCPrivacyService
from .utils import success_response, error_response, parse_filter_params

__all__ = ['NOCOverviewView']

logger = logging.getLogger('noc.views.overview')


class NOCOverviewView(APIView):
    """Dashboard overview with aggregated metrics across clients and sites."""

    permission_classes = [IsAuthenticated]

    @require_noc_capability('noc:view')
    def get(self, request):
        """Get aggregated dashboard overview metrics."""
        try:
            filters = parse_filter_params(request)
            time_range_hours = filters.get('time_range_hours', 24)
            window_start = timezone.now() - timedelta(hours=time_range_hours)

            allowed_clients = NOCRBACService.get_visible_clients(request.user)

            if client_ids := filters.get('client_ids'):
                allowed_clients = allowed_clients.filter(id__in=client_ids)

            snapshots = self._get_filtered_snapshots(allowed_clients, filters, window_start)

            metrics = self._aggregate_metrics(snapshots, allowed_clients, request.user)
            metrics['time_range_hours'] = time_range_hours
            metrics['last_updated'] = timezone.now()

            serializer = MetricOverviewSerializer(metrics)
            return success_response(serializer.data)

        except (ValueError, KeyError) as e:
            logger.error(f"Error fetching overview", extra={'error': str(e), 'user_id': request.user.id})
            return error_response("Failed to fetch overview metrics", {'detail': str(e)})

    def _get_filtered_snapshots(self, clients, filters, window_start):
        """Get filtered snapshots with query optimization."""
        snapshots = NOCMetricSnapshot.objects.filter(
            client__in=clients,
            window_end__gte=window_start
        ).select_related('client', 'bu', 'oic')

        if city := filters.get('city'):
            snapshots = snapshots.filter(city=city)

        if state := filters.get('state'):
            snapshots = snapshots.filter(state=state)

        if oic_id := filters.get('oic_id'):
            snapshots = snapshots.filter(oic_id=oic_id)

        return snapshots

    def _aggregate_metrics(self, snapshots, clients, user):
        """Aggregate metrics from snapshots and calculate derived values."""
        tickets_open = sum(s.tickets_open for s in snapshots)
        tickets_overdue = sum(s.tickets_overdue for s in snapshots)
        attendance_present = sum(s.attendance_present for s in snapshots)
        attendance_expected = sum(s.attendance_expected for s in snapshots)

        active_alerts = NOCAlertEvent.objects.filter(
            client__in=clients,
            status__in=['NEW', 'ACKNOWLEDGED', 'ASSIGNED']
        ).count()

        critical_alerts = NOCAlertEvent.objects.filter(
            client__in=clients,
            severity='CRITICAL',
            status__in=['NEW', 'ACKNOWLEDGED']
        ).count()

        active_incidents = NOCIncident.objects.filter(
            alerts__client__in=clients,
            state__in=['NEW', 'ACKNOWLEDGED', 'ASSIGNED', 'IN_PROGRESS']
        ).distinct().count()

        attendance_ratio = (attendance_present / attendance_expected * 100) if attendance_expected > 0 else 0.0

        return NOCPrivacyService.mask_pii({
            'tickets_open': tickets_open,
            'tickets_overdue': tickets_overdue,
            'work_orders_pending': sum(s.work_orders_pending for s in snapshots),
            'attendance_present': attendance_present,
            'attendance_expected': attendance_expected,
            'attendance_ratio': round(attendance_ratio, 2),
            'device_offline': sum(s.device_health_offline for s in snapshots),
            'active_alerts': active_alerts,
            'active_incidents': active_incidents,
            'critical_alerts': critical_alerts,
            'clients_count': clients.count(),
            'sites_count': sum(1 for s in snapshots if s.bu_id)
        }, user)