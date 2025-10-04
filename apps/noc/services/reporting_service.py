"""
NOC Reporting Service.

Generates NOC analytics, MTTR calculations, and operational reports.
Follows .claude/rules.md Rule #7 (<150 lines), Rule #12 (query optimization).
"""

import logging
from datetime import timedelta
from typing import Dict, Any, List
from django.db.models import Avg, Count, Q, F, DurationField
from django.db.models.functions import TruncDate
from django.utils import timezone
from ..models import NOCAlertEvent, NOCIncident, NOCMetricSnapshot

__all__ = ['NOCReportingService']

logger = logging.getLogger('noc.reporting')


class NOCReportingService:
    """Service for NOC analytics and reporting."""

    @staticmethod
    def calculate_mttr(client, days=30) -> Dict[str, Any]:
        """
        Calculate Mean Time To Resolution for alerts.

        Args:
            client: Client Bt instance
            days: Number of days to analyze (default: 30)

        Returns:
            Dict with MTTR metrics by severity
        """
        start_date = timezone.now() - timedelta(days=days)

        resolved_alerts = NOCAlertEvent.objects.filter(
            client=client,
            status='RESOLVED',
            resolved_at__gte=start_date,
            time_to_resolve__isnull=False
        )

        overall_mttr = resolved_alerts.aggregate(
            avg_resolution_time=Avg('time_to_resolve')
        )['avg_resolution_time']

        mttr_by_severity = {}
        for severity in ['CRITICAL', 'HIGH', 'MEDIUM', 'LOW', 'INFO']:
            severity_mttr = resolved_alerts.filter(severity=severity).aggregate(
                avg=Avg('time_to_resolve'),
                count=Count('id')
            )
            mttr_by_severity[severity] = {
                'average': severity_mttr['avg'],
                'count': severity_mttr['count']
            }

        return {
            'overall_mttr': overall_mttr,
            'by_severity': mttr_by_severity,
            'period_days': days,
            'total_resolved': resolved_alerts.count()
        }

    @staticmethod
    def get_alert_frequency_analysis(client, days=30) -> Dict[str, Any]:
        """
        Analyze alert frequency and trending.

        Args:
            client: Client Bt instance
            days: Number of days to analyze

        Returns:
            Dict with frequency analysis by type and trend
        """
        start_date = timezone.now() - timedelta(days=days)

        alerts = NOCAlertEvent.objects.filter(
            client=client,
            cdtz__gte=start_date
        )

        by_type = dict(alerts.values('alert_type').annotate(
            count=Count('id')
        ).values_list('alert_type', 'count'))

        by_day = alerts.annotate(
            date=TruncDate('cdtz')
        ).values('date').annotate(count=Count('id')).order_by('date')

        trend = [{'date': item['date'], 'count': item['count']} for item in by_day]

        return {
            'by_type': by_type,
            'daily_trend': trend,
            'total_alerts': alerts.count(),
            'period_days': days
        }

    @staticmethod
    def get_sla_compliance_report(client, days=30) -> Dict[str, Any]:
        """
        Calculate SLA compliance metrics.

        Args:
            client: Client Bt instance
            days: Number of days to analyze

        Returns:
            Dict with SLA compliance percentages
        """
        start_date = timezone.now() - timedelta(days=days)

        incidents = NOCIncident.objects.filter(
            client=client,
            cdtz__gte=start_date,
            sla_target__isnull=False
        )

        total = incidents.count()
        if total == 0:
            return {'compliance_rate': 100.0, 'total_incidents': 0}

        met = incidents.filter(resolved_at__lte=F('sla_target')).count()
        missed = total - met

        return {
            'compliance_rate': (met / total * 100) if total > 0 else 100.0,
            'met_sla': met,
            'missed_sla': missed,
            'total_incidents': total,
            'period_days': days
        }

    @staticmethod
    def get_top_noisy_sites(client, days=7, limit=10) -> List[Dict[str, Any]]:
        """
        Identify sites generating most alerts (noise reduction target).

        Args:
            client: Client Bt instance
            days: Number of days to analyze
            limit: Number of top sites to return

        Returns:
            List of dicts with site info and alert counts
        """
        start_date = timezone.now() - timedelta(days=days)

        noisy_sites = NOCAlertEvent.objects.filter(
            client=client,
            cdtz__gte=start_date,
            bu__isnull=False
        ).values('bu', 'bu__buname').annotate(
            alert_count=Count('id'),
            suppressed_total=models.Sum('suppressed_count')
        ).order_by('-alert_count')[:limit]

        return list(noisy_sites)


from django.db import models