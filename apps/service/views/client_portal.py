"""
Client Portal Views - Read-Only Access.

Provides time-bound, read-only access to KPI dashboards and reports
for external clients without full system credentials.

Follows .claude/rules.md:
- Rule #7: File < 200 lines
- Rule #11: Specific exception handling
- Rule #12: Security first - token validation

@ontology(
    domain="service",
    purpose="Client-facing read-only portal for KPIs and reports",
    business_value="Client transparency, reduced support burden",
    criticality="medium",
    tags=["portal", "client", "dashboard", "reports"]
)
"""

import logging
from django.shortcuts import render
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_http_methods
from django.core.exceptions import ValidationError, PermissionDenied
from django.db.models import Avg, Count, Q
from django.utils import timezone
from datetime import timedelta

from apps.core.utils_new.link_signer import LinkSigner
from apps.client_onboarding.models import BusinessUnit
from apps.reports.services.executive_scorecard_service import ExecutiveScoreCardService

logger = logging.getLogger('service.client_portal')

__all__ = ['portal_dashboard', 'portal_reports', 'portal_kpi_data']


def _validate_token(request):
    """Extract and validate access token from request."""
    token = request.GET.get('token')
    if not token:
        raise PermissionDenied("Access token required")
    
    try:
        client_id, scope = LinkSigner.verify_token(token)
        return client_id, scope
    except ValidationError as e:
        logger.warning(f"Token validation failed: {e}")
        raise PermissionDenied("Invalid or expired access token")


@require_http_methods(["GET"])
def portal_dashboard(request):
    """Main client portal dashboard."""
    client_id, scope = _validate_token(request)
    
    try:
        client = BusinessUnit.objects.get(id=client_id)
        
        context = {
            'client': client,
            'scope': scope,
            'access_token': request.GET.get('token')
        }
        
        return render(request, 'portal/dashboard.html', context)
        
    except BusinessUnit.DoesNotExist:
        raise PermissionDenied("Invalid client access")


@require_http_methods(["GET"])
def portal_reports(request):
    """Scheduled reports view."""
    client_id, scope = _validate_token(request)
    
    try:
        client = BusinessUnit.objects.get(id=client_id)
        
        context = {
            'client': client,
            'scope': scope,
            'access_token': request.GET.get('token')
        }
        
        return render(request, 'portal/reports.html', context)
        
    except BusinessUnit.DoesNotExist:
        raise PermissionDenied("Invalid client access")


@require_http_methods(["GET"])
def portal_kpi_data(request):
    """API endpoint for KPI data (JSON)."""
    client_id, scope = _validate_token(request)
    
    try:
        client = BusinessUnit.objects.get(id=client_id)
        now = timezone.now()
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        
        from apps.attendance.models import Attendance
        from apps.y_helpdesk.models import Ticket
        from apps.activity.models import Job
        from apps.mqtt.models import DeviceTelemetry
        
        total_attendance = Attendance.objects.filter(
            bu=client,
            punchin__gte=month_start
        ).count()
        
        on_time_attendance = Attendance.objects.filter(
            bu=client,
            punchin__gte=month_start,
            status='ON_TIME'
        ).count()
        
        attendance_rate = (on_time_attendance / total_attendance * 100) if total_attendance > 0 else 0
        
        total_tickets = Ticket.objects.filter(bu=client, cdtz__gte=month_start).count()
        closed_tickets = Ticket.objects.filter(
            bu=client, cdtz__gte=month_start, status='CLOSED'
        ).count()
        
        total_tours = Job.objects.filter(
            bu=client,
            planned_start_date__gte=month_start
        ).count()
        
        completed_tours = Job.objects.filter(
            bu=client,
            planned_start_date__gte=month_start,
            status__in=['COMPLETED', 'VERIFIED']
        ).count()
        
        tour_completion = (completed_tours / total_tours * 100) if total_tours > 0 else 0
        
        total_devices = DeviceTelemetry.objects.filter(
            tenant=client.tenant,
            timestamp__gte=month_start
        ).values('device_id').distinct().count()
        
        online_devices = DeviceTelemetry.objects.filter(
            tenant=client.tenant,
            timestamp__gte=month_start,
            status='online'
        ).values('device_id').distinct().count()
        
        device_uptime = (online_devices / total_devices * 100) if total_devices > 0 else 0
        
        data = {
            'period': month_start.strftime('%B %Y'),
            'kpis': {
                'attendance_compliance': round(attendance_rate, 1),
                'tour_completion': round(tour_completion, 1),
                'ticket_stats': {
                    'total': total_tickets,
                    'closed': closed_tickets,
                    'open': total_tickets - closed_tickets
                },
                'device_uptime': round(device_uptime, 1),
                'device_count': total_devices
            },
            'last_updated': timezone.now().isoformat()
        }
        
        return JsonResponse(data)
        
    except BusinessUnit.DoesNotExist:
        return JsonResponse({'error': 'Invalid client access'}, status=403)
    except (ValueError, TypeError, AttributeError) as e:
        logger.error(f"KPI data fetch failed: {e}", exc_info=True)
        return JsonResponse({'error': 'Data retrieval failed'}, status=500)
