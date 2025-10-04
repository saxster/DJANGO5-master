"""
Tenant Management Views

Provides diagnostic and health check endpoints for multi-tenant routing.
"""

import logging
from django.http import JsonResponse
from django.views import View
from django.contrib.admin.views.decorators import staff_member_required
from django.utils.decorators import method_decorator

from intelliwiz_config.settings.tenants import TENANT_MAPPINGS, get_tenant_for_host
from apps.core.utils_new.db_utils import (
    hostname_from_request,
    tenant_db_from_request,
    get_current_db_name,
    THREAD_LOCAL
)

logger = logging.getLogger(__name__)


@method_decorator(staff_member_required, name='dispatch')
class TenantDiagnosticsView(View):
    """
    Diagnostic endpoint for tenant routing.

    Security:
        - Requires staff authentication
        - Exposes current tenant context for debugging
        - Logs access for audit

    Endpoints:
        GET /admin/tenants/diagnostics/
    """

    def get(self, request):
        """
        Return current tenant context and routing information.

        Response includes:
            - Request hostname
            - Matched tenant database
            - Thread-local database context
            - All configured tenant mappings (for staff)
            - Health check status
        """
        hostname = hostname_from_request(request)
        tenant_db = tenant_db_from_request(request)
        thread_local_db = get_current_db_name()

        # Check if THREAD_LOCAL.DB is set
        has_thread_local_db = hasattr(THREAD_LOCAL, 'DB')

        # Health check: verify middleware is working
        middleware_working = has_thread_local_db and thread_local_db == tenant_db

        diagnostics = {
            'hostname': hostname,
            'tenant_database': tenant_db,
            'thread_local_database': thread_local_db,
            'thread_local_db_set': has_thread_local_db,
            'middleware_working': middleware_working,
            'tenant_count': len(TENANT_MAPPINGS),
            'health_status': 'healthy' if middleware_working else 'degraded',
        }

        # Include full tenant mapping for superusers
        if request.user.is_superuser:
            diagnostics['tenant_mappings'] = TENANT_MAPPINGS

        # Log diagnostic access
        logger.info(
            f"Tenant diagnostics accessed by {request.user.loginid}",
            extra={
                'user_id': request.user.id,
                'hostname': hostname,
                'health_status': diagnostics['health_status']
            }
        )

        # Warning if middleware not working
        if not middleware_working:
            logger.warning(
                "Tenant middleware not functioning correctly",
                extra={
                    'hostname': hostname,
                    'expected_db': tenant_db,
                    'actual_db': thread_local_db,
                    'has_thread_local': has_thread_local_db
                }
            )

        return JsonResponse(diagnostics)


@method_decorator(staff_member_required, name='dispatch')
class TenantHealthCheckView(View):
    """
    Simple health check for tenant routing.

    Returns:
        200: Tenant routing is working correctly
        503: Tenant routing is degraded
    """

    def get(self, request):
        """Quick health check for monitoring systems."""
        hostname = hostname_from_request(request)
        tenant_db = tenant_db_from_request(request)
        thread_local_db = get_current_db_name()

        is_healthy = (
            hasattr(THREAD_LOCAL, 'DB') and
            thread_local_db == tenant_db
        )

        status_code = 200 if is_healthy else 503

        return JsonResponse(
            {
                'status': 'healthy' if is_healthy else 'degraded',
                'hostname': hostname,
                'database': tenant_db
            },
            status=status_code
        )


class TenantInfoView(View):
    """
    Public endpoint showing current tenant context.

    Security:
        - No authentication required
        - Limited information exposure
        - Useful for debugging frontend issues
    """

    def get(self, request):
        """Return basic tenant information."""
        hostname = hostname_from_request(request)
        tenant_db = tenant_db_from_request(request)

        # Only expose non-sensitive information
        return JsonResponse({
            'hostname': hostname,
            'tenant_configured': tenant_db != 'default' or hostname in TENANT_MAPPINGS,
            'authenticated': request.user.is_authenticated,
        })
