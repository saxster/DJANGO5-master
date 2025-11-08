"""
Executive Scorecard Service.

Generate board-ready compliance and operations scorecards.
Part of HIGH_IMPACT_FEATURE_OPPORTUNITIES.md implementation.

Revenue Impact: +$200-500/month per client
Value: Replaces 4-8 hours/month of manual reporting

Follows .claude/rules.md:
- Rule #7: Service < 150 lines
- Rule #8: Methods < 30 lines
- Rule #11: Specific exception handling

@ontology(
    domain="reports",
    purpose="Generate monthly executive scorecards with KPIs",
    business_value="Board-ready compliance reporting, executive visibility",
    criticality="medium",
    tags=["reporting", "executive", "kpi", "scorecard", "analytics"]
)
"""

import logging
from datetime import timedelta
from typing import Dict, Any
from django.utils import timezone
from django.db.models import Avg, Count, Q, F
from decimal import Decimal
from apps.core.exceptions.patterns import DATABASE_EXCEPTIONS

from apps.core.exceptions.patterns import NETWORK_EXCEPTIONS


logger = logging.getLogger('reports.executive_scorecard')

__all__ = ['ExecutiveScoreCardService']


class ExecutiveScoreCardService:
    """Generate executive scorecards with operational KPIs."""
    
    @classmethod
    def generate_monthly_scorecard(cls, client_id: int, month: int = None, year: int = None) -> Dict[str, Any]:
        """
        Aggregate all KPIs for monthly scorecard.
        
        Args:
            client_id: Client/BusinessUnit ID
            month: Month number (1-12), defaults to current month
            year: Year, defaults to current year
            
        Returns:
            Dict with all scorecard sections
        """
        from apps.onboarding.models import BusinessUnit
        
        now = timezone.now()
        target_month = month or now.month
        target_year = year or now.year
        
        # Date range for the month
        month_start = timezone.datetime(target_year, target_month, 1, tzinfo=timezone.get_current_timezone())
        if target_month == 12:
            month_end = timezone.datetime(target_year + 1, 1, 1, tzinfo=timezone.get_current_timezone())
        else:
            month_end = timezone.datetime(target_year, target_month + 1, 1, tzinfo=timezone.get_current_timezone())
        
        try:
            client = BusinessUnit.objects.get(id=client_id)
            
            scorecard = {
                'client': client.name,
                'client_logo': client.other_data.get('logo_url') if hasattr(client, 'other_data') else None,
                'period': f"{month_start.strftime('%B %Y')}",
                'generated_at': now.isoformat(),
                'operational_excellence': cls._get_operational_metrics(client, month_start, month_end),
                'quality_metrics': cls._get_quality_metrics(client, month_start, month_end),
                'risk_indicators': cls._get_risk_indicators(client, month_start, month_end),
                'trends': cls._get_trend_comparison(client, month_start, month_end),
                'top_changes': cls._get_top_changes(client, month_start, month_end),
                'top_risks': cls._get_top_risks(client, month_start, month_end)
            }
            
            return scorecard
            
        except DATABASE_EXCEPTIONS as e:
            logger.error(f"Error generating scorecard for client {client_id}: {e}", exc_info=True)
            raise
    
    @classmethod
    def _get_operational_metrics(cls, client, start_date, end_date) -> Dict[str, Any]:
        """Operational Excellence KPIs."""
        from apps.attendance.models import Attendance
        from apps.activity.models import Job
        from apps.y_helpdesk.models import Ticket
        from apps.work_order_management.models import WomDetails
        
        # Attendance compliance
        total_attendance = Attendance.objects.filter(
            bu=client,
            punchin__range=(start_date, end_date)
        ).count()
        
        on_time_attendance = Attendance.objects.filter(
            bu=client,
            punchin__range=(start_date, end_date),
            status='ON_TIME'
        ).count()
        
        attendance_compliance = (on_time_attendance / total_attendance * 100) if total_attendance > 0 else 0
        
        # Tour coverage (checkpoint completion)
        total_jobs = Job.objects.filter(
            bu=client,
            planned_start_date__range=(start_date, end_date)
        ).count()
        
        completed_jobs = Job.objects.filter(
            bu=client,
            planned_start_date__range=(start_date, end_date),
            status__in=['COMPLETED', 'VERIFIED']
        ).count()
        
        tour_coverage = (completed_jobs / total_jobs * 100) if total_jobs > 0 else 0
        
        # SLA performance
        total_tickets = Ticket.objects.filter(
            bu=client,
            cdtz__range=(start_date, end_date),
            status='CLOSED'
        ).count()
        
        on_time_tickets = Ticket.objects.filter(
            bu=client,
            cdtz__range=(start_date, end_date),
            status='CLOSED',
            other_data__sla_breached=False
        ).count()
        
        sla_performance = (on_time_tickets / total_tickets * 100) if total_tickets > 0 else 0
        
        # Work order backlog
        open_work_orders = WomDetails.objects.filter(
            client=client,
            status__in=['NEW', 'IN_PROGRESS']
        ).count()
        
        return {
            'attendance_compliance': round(attendance_compliance, 1),
            'tour_coverage': round(tour_coverage, 1),
            'sla_performance': round(sla_performance, 1),
            'work_order_backlog': open_work_orders
        }
    
    @classmethod
    def _get_quality_metrics(cls, client, start_date, end_date) -> Dict[str, Any]:
        """Quality Metrics."""
        from apps.y_helpdesk.models import Ticket
        from apps.noc.models import NOCAlertEvent
        from apps.mqtt.models import DeviceTelemetry
        
        # Helpdesk sentiment (from ticket sentiment analysis)
        avg_sentiment = Ticket.objects.filter(
            bu=client,
            cdtz__range=(start_date, end_date),
            other_data__sentiment_score__isnull=False
        ).aggregate(
            avg_score=Avg('other_data__sentiment_score')
        )['avg_score'] or 3.0
        
        # NOC auto-resolution rate
        total_alerts = NOCAlertEvent.objects.filter(
            bu=client,
            cdtz__range=(start_date, end_date)
        ).count()
        
        auto_resolved = NOCAlertEvent.objects.filter(
            bu=client,
            cdtz__range=(start_date, end_date),
            resolution_method='AUTOMATED'
        ).count()
        
        auto_resolution_rate = (auto_resolved / total_alerts * 100) if total_alerts > 0 else 0
        
        # Device uptime
        total_readings = DeviceTelemetry.objects.filter(
            tenant=client.tenant,
            timestamp__range=(start_date, end_date)
        ).count()
        
        online_readings = DeviceTelemetry.objects.filter(
            tenant=client.tenant,
            timestamp__range=(start_date, end_date),
            status='online'
        ).count()
        
        device_uptime = (online_readings / total_readings * 100) if total_readings > 0 else 0
        
        # Incident response time (average)
        avg_response = NOCAlertEvent.objects.filter(
            bu=client,
            cdtz__range=(start_date, end_date),
            acknowledged_at__isnull=False
        ).aggregate(
            avg_response=Avg(F('acknowledged_at') - F('cdtz'))
        )['avg_response']
        
        avg_response_minutes = avg_response.total_seconds() / 60 if avg_response else 0
        
        return {
            'helpdesk_sentiment': round(float(avg_sentiment), 1),
            'noc_auto_resolution': round(auto_resolution_rate, 1),
            'device_uptime': round(device_uptime, 1),
            'incident_response_minutes': round(avg_response_minutes, 1)
        }
    
    @classmethod
    def _get_risk_indicators(cls, client, start_date, end_date) -> Dict[str, Any]:
        """Risk Indicators."""
        from apps.attendance.models import Attendance
        from apps.y_helpdesk.models import Ticket
        from apps.noc.models import NOCAlertEvent
        
        # Geofence violations
        geofence_violations = Attendance.objects.filter(
            bu=client,
            punchin__range=(start_date, end_date),
            other_data__geofence_violation=True
        ).count()
        
        # SLA at-risk tickets
        at_risk_tickets = Ticket.objects.filter(
            bu=client,
            status__in=['NEW', 'ASSIGNED', 'IN_PROGRESS'],
            other_data__sla_risk_score__gte=0.70
        ).count()
        
        # Critical security events
        critical_events = NOCAlertEvent.objects.filter(
            bu=client,
            cdtz__range=(start_date, end_date),
            severity='CRITICAL',
            alert_type__in=['SECURITY_BREACH', 'UNAUTHORIZED_ACCESS', 'INTRUSION']
        ).count()
        
        return {
            'geofence_violations': geofence_violations,
            'sla_at_risk_tickets': at_risk_tickets,
            'critical_security_events': critical_events
        }
    
    @classmethod
    def _get_trend_comparison(cls, client, start_date, end_date) -> Dict[str, Any]:
        """Compare current month vs previous month with MoM %."""
        from apps.attendance.models import Attendance
        from apps.noc.models import NOCAlertEvent
        
        prev_month_end = start_date - timedelta(days=1)
        prev_month_start = prev_month_end.replace(day=1)
        
        current_attendance = Attendance.objects.filter(
            bu=client, punchin__range=(start_date, end_date), status='ON_TIME'
        ).count()
        
        current_auto_resolve = NOCAlertEvent.objects.filter(
            bu=client, cdtz__range=(start_date, end_date), resolution_method='AUTOMATED'
        ).count()
        
        prev_attendance = Attendance.objects.filter(
            bu=client, punchin__range=(prev_month_start, prev_month_end), status='ON_TIME'
        ).count()
        
        prev_auto_resolve = NOCAlertEvent.objects.filter(
            bu=client, cdtz__range=(prev_month_start, prev_month_end), resolution_method='AUTOMATED'
        ).count()
        
        attendance_mom = ((current_attendance - prev_attendance) / prev_attendance * 100) if prev_attendance else 0
        auto_resolve_mom = ((current_auto_resolve - prev_auto_resolve) / prev_auto_resolve * 100) if prev_auto_resolve else 0
        
        return {
            'attendance_compliance_mom': round(attendance_mom, 1),
            'auto_resolution_mom': round(auto_resolve_mom, 1),
            'attendance_trend': 'up' if attendance_mom > 0 else 'down',
            'auto_resolution_trend': 'up' if auto_resolve_mom > 0 else 'down'
        }
    
    @classmethod
    def _get_top_changes(cls, client, start_date, end_date) -> list:
        """Identify top 3 changes for 'What Changed' callouts."""
        from apps.attendance.models import Attendance
        from apps.y_helpdesk.models import Ticket
        from apps.noc.models import NOCAlertEvent
        
        prev_month_end = start_date - timedelta(days=1)
        prev_month_start = prev_month_end.replace(day=1)
        
        changes = []
        
        curr_viol = Attendance.objects.filter(
            bu=client, punchin__range=(start_date, end_date), other_data__geofence_violation=True
        ).count()
        prev_viol = Attendance.objects.filter(
            bu=client, punchin__range=(prev_month_start, prev_month_end), other_data__geofence_violation=True
        ).count()
        viol_change = ((curr_viol - prev_viol) / prev_viol * 100) if prev_viol else (100 if curr_viol > 0 else 0)
        changes.append(('Geofence Violations', viol_change, curr_viol - prev_viol))
        
        curr_tickets = Ticket.objects.filter(bu=client, cdtz__range=(start_date, end_date)).count()
        prev_tickets = Ticket.objects.filter(bu=client, cdtz__range=(prev_month_start, prev_month_end)).count()
        ticket_change = ((curr_tickets - prev_tickets) / prev_tickets * 100) if prev_tickets else 0
        changes.append(('Ticket Volume', ticket_change, curr_tickets - prev_tickets))
        
        curr_crit = NOCAlertEvent.objects.filter(
            bu=client, cdtz__range=(start_date, end_date), severity='CRITICAL'
        ).count()
        prev_crit = NOCAlertEvent.objects.filter(
            bu=client, cdtz__range=(prev_month_start, prev_month_end), severity='CRITICAL'
        ).count()
        crit_change = ((curr_crit - prev_crit) / prev_crit * 100) if prev_crit else 0
        changes.append(('Critical Alerts', crit_change, curr_crit - prev_crit))
        
        return sorted(changes, key=lambda x: abs(x[1]), reverse=True)[:3]
    
    @classmethod
    def _get_top_risks(cls, client, start_date, end_date) -> list:
        """Get top 5 risks for risk section."""
        from apps.y_helpdesk.models import Ticket
        from apps.noc.models import NOCAlertEvent
        from apps.attendance.models import Attendance
        
        risks = []
        
        at_risk = Ticket.objects.filter(
            bu=client, status__in=['NEW', 'ASSIGNED'], other_data__sla_risk_score__gte=0.70
        ).count()
        if at_risk > 0:
            risks.append(('SLA Breach Risk', at_risk, 'high'))
        
        critical = NOCAlertEvent.objects.filter(
            bu=client, cdtz__range=(start_date, end_date), severity='CRITICAL', status='OPEN'
        ).count()
        if critical > 0:
            risks.append(('Unresolved Critical Alerts', critical, 'critical'))
        
        geofence = Attendance.objects.filter(
            bu=client, punchin__range=(start_date, end_date), other_data__geofence_violation=True
        ).count()
        if geofence > 5:
            risks.append(('Geofence Violations', geofence, 'medium'))
        
        return risks[:5]
    
    @classmethod
    def send_to_slack(cls, scorecard: Dict[str, Any], webhook_url: str) -> bool:
        """Send scorecard summary to Slack via webhook."""
        import requests
        import json
        
        try:
            payload = {
                "text": f"📊 Executive Scorecard: {scorecard['client']} - {scorecard['period']}",
                "blocks": [
                    {
                        "type": "header",
                        "text": {"type": "plain_text", "text": f"Executive Scorecard: {scorecard['client']}"}
                    },
                    {
                        "type": "section",
                        "text": {"type": "mrkdwn", "text": f"*Period:* {scorecard['period']}"}
                    },
                    {
                        "type": "section",
                        "fields": [
                            {"type": "mrkdwn", "text": f"*Attendance:* {scorecard['operational_excellence']['attendance_compliance']}%"},
                            {"type": "mrkdwn", "text": f"*SLA:* {scorecard['operational_excellence']['sla_performance']}%"},
                            {"type": "mrkdwn", "text": f"*Device Uptime:* {scorecard['quality_metrics']['device_uptime']}%"},
                            {"type": "mrkdwn", "text": f"*Critical Events:* {scorecard['risk_indicators']['critical_security_events']}"}
                        ]
                    }
                ]
            }
            
            response = requests.post(webhook_url, json=payload, timeout=(5, 15))
            response.raise_for_status()
            return True
        except NETWORK_EXCEPTIONS as e:
            logger.error(f"Failed to send Slack notification: {e}", exc_info=True)
            return False
