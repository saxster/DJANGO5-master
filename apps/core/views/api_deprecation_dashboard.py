"""
API Deprecation Analytics Dashboard
Provides visibility into deprecated API usage and migration progress.

Compliance with .claude/rules.md:
- Rule #8: View methods < 30 lines
- Rule #11: Specific exception handling
- Rule #15: No sensitive data logging
"""

import logging
from django.contrib.admin.views.decorators import staff_member_required
from django.utils.decorators import method_decorator
from django.views.generic import TemplateView
from django.http import JsonResponse
from django.core.exceptions import PermissionDenied
from apps.core.services.api_deprecation_service import APIDeprecationService

logger = logging.getLogger('api.deprecation.dashboard')


@method_decorator(staff_member_required, name='dispatch')
class APIDeprecationDashboard(TemplateView):
    """
    Dashboard showing deprecated API endpoints and migration progress.
    """
    template_name = 'core/api_deprecation_dashboard.html'

    def get_context_data(self, **kwargs):
        """Get dashboard data."""
        context = super().get_context_data(**kwargs)
        context['dashboard_data'] = APIDeprecationService.get_deprecation_dashboard_data()
        context['sunset_warnings'] = APIDeprecationService.get_sunset_warnings()
        return context


@staff_member_required
def api_deprecation_stats(request):
    """
    JSON endpoint for deprecation statistics.
    """
    endpoint = request.GET.get('endpoint')
    days = int(request.GET.get('days', 7))

    if not endpoint:
        return JsonResponse({'error': 'endpoint parameter required'}, status=400)

    try:
        stats = APIDeprecationService.get_usage_stats(endpoint, days)
        return JsonResponse(stats)

    except (ValueError, TypeError) as e:
        logger.warning(f"Invalid parameters for deprecation stats: {e}")
        return JsonResponse({'error': 'Invalid parameters'}, status=400)


@staff_member_required
def api_sunset_alerts(request):
    """
    JSON endpoint for sunset warnings.
    """
    try:
        warnings = APIDeprecationService.get_sunset_warnings()
        data = [
            {
                'endpoint': w.endpoint_pattern,
                'sunset_date': w.sunset_date.isoformat(),
                'days_remaining': (w.sunset_date - timezone.now()).days,
                'replacement': w.replacement_endpoint,
            }
            for w in warnings
        ]
        return JsonResponse({'warnings': data})

    except (ValueError, DatabaseError) as e:
        logger.error(f"Error fetching sunset alerts: {e}")
        return JsonResponse({'error': 'Server error'}, status=500)


@staff_member_required
def api_client_migration_status(request):
    """
    Show which clients are still on deprecated APIs.
    """
    try:
        clients = APIDeprecationService.get_clients_on_deprecated_api()
        return JsonResponse({'clients': clients})

    except (ValueError, DatabaseError) as e:
        logger.error(f"Error fetching client migration status: {e}")
        return JsonResponse({'error': 'Server error'}, status=500)


from django.utils import timezone
from django.db import DatabaseError

__all__ = [
    'APIDeprecationDashboard',
    'api_deprecation_stats',
    'api_sunset_alerts',
    'api_client_migration_status',
]