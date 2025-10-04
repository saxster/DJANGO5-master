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
    allowed_clients = NOCRBACService.get_visible_clients(request.user)
    oics = People.objects.filter(
        is_active=True,
        peopleorganizational__isnull=False
    ).distinct()

    context = {
        'allowed_clients': allowed_clients,
        'oics': oics,
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