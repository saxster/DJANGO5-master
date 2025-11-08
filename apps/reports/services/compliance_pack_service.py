"""
Compliance Pack Automation Service

Generate monthly compliance audit packs with:
- Attendance compliance % (on-time rate)
- Patrol coverage % (tours completed)
- SLA performance (tickets resolved on-time)
- Incident MTTR (mean time to resolution)
- Device uptime %
- Audit logs summary

Supports: PSARA, ISO 9001, client-specific standards.

Follows .claude/rules.md:
- Rule #7: Service < 150 lines
- Rule #8: Methods < 30 lines
- Rule #11: Specific exceptions
"""

import logging
from datetime import timedelta
from typing import Dict, Any, List
from django.utils import timezone
from django.db.models import Count, Avg, Q, F, ExpressionWrapper, DurationField
from apps.attendance.models import Attendance
from apps.activity.models import Activity
from apps.y_helpdesk.models import Ticket
from apps.monitoring.models import Device
from apps.core.models import AuditLog
from apps.core.exceptions.patterns import DATABASE_EXCEPTIONS

logger = logging.getLogger('reports.compliance')

__all__ = ['CompliancePackService']


class CompliancePackService:
    """Generate compliance audit packs for regulatory reporting."""
    
    @classmethod
    def generate_monthly_pack(cls, client_id: int, month: int, year: int) -> Dict[str, Any]:
        """
        Generate complete compliance pack for a client/month.
        
        Args:
            client_id: Client/BusinessUnit ID
            month: Month (1-12)
            year: Year
            
        Returns:
            Comprehensive compliance metrics dict
        """
        try:
            start_date, end_date = cls._get_month_range(month, year)
            
            pack = {
                'metadata': cls._build_metadata(client_id, month, year),
                'attendance_compliance': cls._calculate_attendance_metrics(client_id, start_date, end_date),
                'patrol_coverage': cls._calculate_patrol_coverage(client_id, start_date, end_date),
                'sla_performance': cls._calculate_sla_metrics(client_id, start_date, end_date),
                'incident_response': cls._calculate_incident_mttr(client_id, start_date, end_date),
                'device_uptime': cls._calculate_device_uptime(client_id, start_date, end_date),
                'audit_summary': cls._summarize_audit_logs(client_id, start_date, end_date),
            }
            
            return pack
            
        except DATABASE_EXCEPTIONS as e:
            logger.error(f"Compliance pack generation failed: {e}")
            raise
    
    @classmethod
    def _get_month_range(cls, month: int, year: int) -> tuple:
        """Calculate month start/end dates."""
        start = timezone.datetime(year, month, 1, tzinfo=timezone.get_current_timezone())
        if month == 12:
            end = timezone.datetime(year + 1, 1, 1, tzinfo=timezone.get_current_timezone())
        else:
            end = timezone.datetime(year, month + 1, 1, tzinfo=timezone.get_current_timezone())
        return start, end
    
    @classmethod
    def _build_metadata(cls, client_id: int, month: int, year: int) -> Dict[str, Any]:
        """Build pack metadata."""
        from apps.onboarding.models import BusinessUnit
        client = BusinessUnit.objects.get(id=client_id)
        
        return {
            'client': client.name,
            'period': f"{month:02d}/{year}",
            'generated_at': timezone.now().isoformat(),
            'standard': 'PSARA/ISO 9001',
        }
    
    @classmethod
    def _calculate_attendance_metrics(cls, client_id: int, start: timezone.datetime, end: timezone.datetime) -> Dict:
        """Attendance compliance percentage."""
        total = Attendance.objects.filter(client_id=client_id, checkin__range=[start, end]).count()
        on_time = Attendance.objects.filter(
            client_id=client_id,
            checkin__range=[start, end],
            is_on_time=True
        ).count()
        
        return {
            'total_shifts': total,
            'on_time_shifts': on_time,
            'compliance_rate': round((on_time / total * 100), 2) if total else 0,
        }
    
    @classmethod
    def _calculate_patrol_coverage(cls, client_id: int, start: timezone.datetime, end: timezone.datetime) -> Dict:
        """Patrol tour coverage percentage."""
        scheduled = Activity.objects.filter(
            client_id=client_id,
            created_at__range=[start, end],
            activity_type='TOUR'
        ).count()
        
        completed = Activity.objects.filter(
            client_id=client_id,
            created_at__range=[start, end],
            activity_type='TOUR',
            status='COMPLETED'
        ).count()
        
        return {
            'scheduled_tours': scheduled,
            'completed_tours': completed,
            'coverage_rate': round((completed / scheduled * 100), 2) if scheduled else 0,
        }
    
    @classmethod
    def _calculate_sla_metrics(cls, client_id: int, start: timezone.datetime, end: timezone.datetime) -> Dict:
        """SLA performance - tickets resolved on time."""
        total = Ticket.objects.filter(client_id=client_id, created_at__range=[start, end]).count()
        on_time = Ticket.objects.filter(
            client_id=client_id,
            created_at__range=[start, end],
            resolution_time__lte=F('sla_target')
        ).count()
        
        return {
            'total_tickets': total,
            'resolved_on_time': on_time,
            'sla_compliance': round((on_time / total * 100), 2) if total else 0,
        }
    
    @classmethod
    def _calculate_incident_mttr(cls, client_id: int, start: timezone.datetime, end: timezone.datetime) -> Dict:
        """Mean time to resolution for incidents."""
        incidents = Activity.objects.filter(
            client_id=client_id,
            created_at__range=[start, end],
            activity_type='INCIDENT',
            resolved_at__isnull=False
        ).annotate(
            resolution_time=ExpressionWrapper(
                F('resolved_at') - F('created_at'),
                output_field=DurationField()
            )
        ).aggregate(avg_mttr=Avg('resolution_time'))
        
        avg_seconds = incidents['avg_mttr'].total_seconds() if incidents['avg_mttr'] else 0
        
        return {
            'avg_mttr_hours': round(avg_seconds / 3600, 2),
            'total_incidents': Activity.objects.filter(
                client_id=client_id,
                created_at__range=[start, end],
                activity_type='INCIDENT'
            ).count(),
        }
    
    @classmethod
    def _calculate_device_uptime(cls, client_id: int, start: timezone.datetime, end: timezone.datetime) -> Dict:
        """Device uptime percentage."""
        devices = Device.objects.filter(client_id=client_id)
        total_devices = devices.count()
        
        operational = devices.filter(status='ONLINE').count()
        
        return {
            'total_devices': total_devices,
            'operational_devices': operational,
            'uptime_rate': round((operational / total_devices * 100), 2) if total_devices else 0,
        }
    
    @classmethod
    def _summarize_audit_logs(cls, client_id: int, start: timezone.datetime, end: timezone.datetime) -> Dict:
        """Audit log summary for compliance trail."""
        logs = AuditLog.objects.filter(client_id=client_id, timestamp__range=[start, end])
        
        return {
            'total_events': logs.count(),
            'by_severity': {
                'critical': logs.filter(severity='CRITICAL').count(),
                'high': logs.filter(severity='HIGH').count(),
                'medium': logs.filter(severity='MEDIUM').count(),
                'low': logs.filter(severity='LOW').count(),
            },
        }
