"""
NOC UI View Controllers.

Template rendering views for NOC dashboard pages.
Follows .claude/rules.md Rule #8 (view methods <30 lines).
"""

from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from apps.noc.decorators import require_noc_capability
from apps.noc.services import NOCRBACService
from apps.peoples.models import People

__all__ = ['noc_dashboard_view', 'noc_incidents_view', 'noc_maintenance_view']


@login_required
@require_noc_capability('noc:view')
def noc_dashboard_view(request):
    """Render main NOC dashboard page."""
    from apps.threat_intelligence.models import IntelligenceAlert
    from django.utils import timezone
    from datetime import timedelta
    
    allowed_clients = NOCRBACService.get_visible_clients(request.user)
    oics = (
        People.objects.filter(
            tenant=request.user.tenant,
            is_active=True,
            peopleorganizational__isnull=False
        )
        .select_related(
            'peopleorganizational',
            'peopleorganizational__client',
            'peopleorganizational__bu'
        )
        .distinct()
    )

    recent_threat_alerts = IntelligenceAlert.objects.filter(
        tenant=request.user.tenant,
        created_at__gte=timezone.now() - timedelta(hours=24),
        acknowledged_at__isnull=True
    ).select_related('threat_event').order_by('-severity', '-created_at')[:5]

    critical_threat_count = IntelligenceAlert.objects.filter(
        tenant=request.user.tenant,
        severity='CRITICAL',
        acknowledged_at__isnull=True
    ).count()

    context = {
        'allowed_clients': allowed_clients,
        'oics': oics,
        'recent_threat_alerts': recent_threat_alerts,
        'critical_threat_count': critical_threat_count,
        'page_title': 'NOC Dashboard'
    }
    return render(request, 'noc/overview.html', context)


@login_required
@require_noc_capability('noc:view')
def noc_incidents_view(request):
    """Render incidents management page."""
    allowed_clients = NOCRBACService.get_visible_clients(request.user)

    context = {
        'allowed_clients': allowed_clients,
        'page_title': 'Incident Management'
    }
    return render(request, 'noc/incidents.html', context)


@login_required
@require_noc_capability('noc:view')
def noc_maintenance_view(request):
    """Render maintenance windows page."""
    allowed_clients = NOCRBACService.get_visible_clients(request.user)

    context = {
        'allowed_clients': allowed_clients,
        'page_title': 'Maintenance Windows'
    }
    return render(request, 'noc/maintenance.html', context)
