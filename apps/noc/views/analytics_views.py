"""
NOC Analytics Views.

REST API endpoints for trend analytics and metrics over time.
Follows .claude/rules.md Rule #8 (view methods <30 lines), Rule #12 (query optimization).
"""

import logging
from datetime import timedelta
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from django.utils import timezone
from django.db.models import Count, Avg, Q
from apps.noc.decorators import require_noc_capability
from apps.noc.models import NOCAlertEvent, NOCIncident, NOCMetricSnapshot
from apps.noc.services import NOCRBACService
from .utils import success_response, error_response, parse_filter_params

__all__ = ['NOCAnalyticsTrendsView', 'NOCMTTRAnalyticsView']

logger = logging.getLogger('noc.views.analytics')


class NOCAnalyticsTrendsView(APIView):
    """Trend analytics for alerts, incidents, and SLA compliance."""

    permission_classes = [IsAuthenticated]

    @require_noc_capability('noc:view')
    def get(self, request):
        """Get trend analytics data."""
        try:
            filters = parse_filter_params(request)
            days = int(request.GET.get('days', 7))
            window_start = timezone.now() - timedelta(days=days)

            allowed_clients = NOCRBACService.get_visible_clients(request.user)

            if client_ids := filters.get('client_ids'):
                allowed_clients = allowed_clients.filter(id__in=client_ids)

            alert_trends = self._get_alert_trends(allowed_clients, window_start, days)
            incident_trends = self._get_incident_trends(allowed_clients, window_start, days)
            sla_metrics = self._get_sla_metrics(allowed_clients, window_start)

            return success_response({
                'alert_trends': alert_trends,
                'incident_trends': incident_trends,
                'sla_metrics': sla_metrics,
                'period_days': days
            })

        except (ValueError, TypeError) as e:
            logger.error(f"Error generating analytics", extra={'error': str(e), 'user_id': request.user.id})
            return error_response("Failed to generate analytics", {'detail': str(e)})

    def _get_alert_trends(self, clients, window_start, days):
        """Calculate alert frequency trends."""
        alerts = NOCAlertEvent.objects.filter(
            client__in=clients,
            cdtz__gte=window_start
        )

        daily_counts = {}
        for day in range(days):
            day_start = window_start + timedelta(days=day)
            day_end = day_start + timedelta(days=1)

            daily_counts[day_start.date().isoformat()] = {
                'total': alerts.filter(cdtz__gte=day_start, cdtz__lt=day_end).count(),
                'critical': alerts.filter(cdtz__gte=day_start, cdtz__lt=day_end, severity='CRITICAL').count(),
                'high': alerts.filter(cdtz__gte=day_start, cdtz__lt=day_end, severity='HIGH').count(),
            }

        return daily_counts

    def _get_incident_trends(self, clients, window_start, days):
        """Calculate incident trends."""
        incidents = NOCIncident.objects.filter(
            alerts__client__in=clients,
            created_at__gte=window_start
        ).distinct()

        daily_counts = {}
        for day in range(days):
            day_start = window_start + timedelta(days=day)
            day_end = day_start + timedelta(days=1)

            daily_counts[day_start.date().isoformat()] = {
                'created': incidents.filter(created_at__gte=day_start, created_at__lt=day_end).count(),
                'resolved': incidents.filter(resolved_at__gte=day_start, resolved_at__lt=day_end).count(),
            }

        return daily_counts

    def _get_sla_metrics(self, clients, window_start):
        """Calculate SLA compliance metrics."""
        resolved_alerts = NOCAlertEvent.objects.filter(
            client__in=clients,
            resolved_at__gte=window_start,
            status='RESOLVED',
            time_to_resolve__isnull=False
        )

        avg_time_to_resolve = resolved_alerts.aggregate(
            avg_seconds=Avg('time_to_resolve')
        )['avg_seconds']

        sla_target_hours = 4
        sla_breaches = resolved_alerts.filter(
            time_to_resolve__gt=timedelta(hours=sla_target_hours)
        ).count()

        return {
            'avg_time_to_resolve_minutes': (avg_time_to_resolve.total_seconds() / 60) if avg_time_to_resolve else 0,
            'sla_breaches': sla_breaches,
            'total_resolved': resolved_alerts.count(),
            'sla_compliance_percent': ((resolved_alerts.count() - sla_breaches) / resolved_alerts.count() * 100) if resolved_alerts.count() > 0 else 100
        }


class NOCMTTRAnalyticsView(APIView):
    """Mean Time To Resolve (MTTR) analytics."""

    permission_classes = [IsAuthenticated]

    @require_noc_capability('noc:view')
    def get(self, request):
        """Get MTTR analytics by severity and client."""
        try:
            filters = parse_filter_params(request)
            days = int(request.GET.get('days', 30))
            window_start = timezone.now() - timedelta(days=days)

            allowed_clients = NOCRBACService.get_visible_clients(request.user)

            if client_ids := filters.get('client_ids'):
                allowed_clients = allowed_clients.filter(id__in=client_ids)

            mttr_by_severity = self._calculate_mttr_by_severity(allowed_clients, window_start)
            mttr_by_client = self._calculate_mttr_by_client(allowed_clients, window_start)

            return success_response({
                'mttr_by_severity': mttr_by_severity,
                'mttr_by_client': mttr_by_client,
                'period_days': days
            })

        except (ValueError, TypeError) as e:
            logger.error(f"Error calculating MTTR", extra={'error': str(e), 'user_id': request.user.id})
            return error_response("Failed to calculate MTTR", {'detail': str(e)})

    def _calculate_mttr_by_severity(self, clients, window_start):
        """Calculate MTTR grouped by severity."""
        results = {}

        for severity_code, severity_name in [('CRITICAL', 'Critical'), ('HIGH', 'High'), ('MEDIUM', 'Medium'), ('LOW', 'Low')]:
            alerts = NOCAlertEvent.objects.filter(
                client__in=clients,
                resolved_at__gte=window_start,
                severity=severity_code,
                time_to_resolve__isnull=False
            )

            avg_time = alerts.aggregate(avg=Avg('time_to_resolve'))['avg']

            results[severity_code] = {
                'count': alerts.count(),
                'avg_minutes': (avg_time.total_seconds() / 60) if avg_time else 0
            }

        return results

    def _calculate_mttr_by_client(self, clients, window_start):
        """Calculate MTTR per client - optimized with single aggregated query."""
        from django.db.models import Avg, Count, F
        from django.db.models.functions import Extract
        
        # Single query with aggregation per client
        results = NOCAlertEvent.objects.filter(
            client__in=clients[:10],
            resolved_at__gte=window_start,
            time_to_resolve__isnull=False
        ).values(
            'client', 'client__buname'
        ).annotate(
            count=Count('id'),
            avg_time=Avg('time_to_resolve')
        ).order_by('-count')[:10]
        
        # Convert to expected format
        return [
            {
                'client_id': r['client'],
                'client_name': r['client__buname'],
                'count': r['count'],
                'avg_minutes': (r['avg_time'].total_seconds() / 60) if r['avg_time'] else 0
            }
            for r in results
        ]