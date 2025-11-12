"""
Dashboard views.

Provides:
- Command Center dashboard view
- REST API endpoints for command center data
"""

import logging
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from apps.dashboard.services.command_center_service import CommandCenterService
from apps.core.exceptions.patterns import DATABASE_EXCEPTIONS
from apps.core.exceptions.patterns import NETWORK_EXCEPTIONS


logger = logging.getLogger(__name__)


@login_required
def command_center_view(request):
    """
    Render command center dashboard.

    Template: dashboard/command_center.html
    WebSocket: ws://host/ws/command-center/
    """
    context = {
        'page_title': 'Command Center',
        'websocket_url': '/ws/command-center/',
    }
    
    return render(request, 'dashboard/command_center.html', context)


@login_required
@require_http_methods(["GET"])
def command_center_api(request):
    """
    REST API endpoint for command center data.

    Fallback for environments without WebSocket support.

    GET /api/dashboard/command-center/

    Returns:
        JSON with command center summary
    """
    try:
        # Get tenant ID from user
        tenant_id = get_user_tenant_id(request.user)
        
        if not tenant_id:
            return JsonResponse({
                'error': 'User not associated with tenant'
            }, status=400)

        summary = CommandCenterService.get_live_summary(tenant_id)

        logger.info(
            "command_center_api_request",
            extra={
                'user': request.user.username,
                'tenant_id': tenant_id
            }
        )

        return JsonResponse({
            'success': True,
            'data': summary
        })

    except DATABASE_EXCEPTIONS as e:
        logger.error(
            "command_center_api_error",
            extra={
                'user': request.user.username,
                'error': str(e)
            },
            exc_info=True
        )
        return JsonResponse({
            'success': False,
            'error': 'Database error occurred'
        }, status=500)

    except NETWORK_EXCEPTIONS as e:
        logger.error(
            "command_center_api_unexpected_error",
            extra={
                'user': request.user.username,
                'error': str(e)
            },
            exc_info=True
        )
        return JsonResponse({
            'success': False,
            'error': 'Unexpected error occurred'
        }, status=500)


@login_required
@require_http_methods(["POST"])
def invalidate_cache_api(request):
    """
    Invalidate command center cache.

    POST /api/dashboard/invalidate-cache/

    Returns:
        JSON with success status
    """
    try:
        tenant_id = get_user_tenant_id(request.user)
        
        if not tenant_id:
            return JsonResponse({
                'error': 'User not associated with tenant'
            }, status=400)

        CommandCenterService.invalidate_cache(tenant_id)

        return JsonResponse({
            'success': True,
            'message': 'Cache invalidated successfully'
        })

    except (ValueError, TypeError, AttributeError) as e:
        logger.error(
            "cache_invalidation_error",
            extra={
                'user': request.user.username,
                'error': str(e)
            },
            exc_info=True
        )
        return JsonResponse({
            'success': False,
            'error': 'Failed to invalidate cache'
        }, status=500)


def get_user_tenant_id(user):
    """
    Get user's tenant ID - NEVER falls back to BU ID.

    BU IDs are organizational units that can be shared across tenants,
    making them unsuitable for cache keys or tenant isolation.

    Returns:
        int or None: User's tenant_id if available, None otherwise

    Security:
        - NEVER returns bu_id (business unit ID) as it's shared across tenants
        - Failing with None is safer than poisoning cache with wrong tenant data
        - Callers should handle None appropriately (error or skip caching)
    """
    return getattr(user, 'tenant_id', None)
