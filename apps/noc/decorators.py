"""
NOC RBAC Decorators for Access Control and Audit Logging.

Provides decorators for enforcing capabilities and auditing access to NOC resources.
Follows .claude/rules.md Rule #7 (<150 lines), Rule #11 (specific exceptions).
"""

import logging
from functools import wraps
from django.http import JsonResponse
from rest_framework.response import Response

logger = logging.getLogger('noc.decorators')

__all__ = [
    'require_noc_capability',
    'audit_noc_access',
    'inject_noc_scope',
]


def require_noc_capability(capability):
    """
    Enforce capability and inject organizational scope.

    Args:
        capability: NOC capability name (e.g., 'noc:view_all_clients')

    Returns:
        Decorated function with capability check
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if not hasattr(request, 'user') or not request.user.is_authenticated:
                return _unauthorized_response('Authentication required')

            if not request.user.has_capability(capability):
                _log_unauthorized_attempt(
                    request.user,
                    capability,
                    request.path
                )
                return _unauthorized_response('Insufficient permissions')

            _inject_scope_to_request(request)

            return view_func(request, *args, **kwargs)

        return wrapper
    return decorator


def audit_noc_access(entity_type):
    """
    Log access to sensitive NOC data.

    Args:
        entity_type: Type of entity being accessed

    Returns:
        Decorated function with audit logging
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            response = view_func(request, *args, **kwargs)

            if _is_success_response(response):
                _create_audit_log(
                    request.user,
                    'VIEW_SENSITIVE',
                    entity_type,
                    kwargs.get('id', kwargs.get('pk', 0)),
                    request.path,
                    request.META.get('REMOTE_ADDR')
                )

            return response

        return wrapper
    return decorator


def inject_noc_scope(view_func):
    """
    Inject NOC scope into request for data filtering.

    Returns:
        Decorated function with scope injection
    """
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        _inject_scope_to_request(request)
        return view_func(request, *args, **kwargs)

    return wrapper


def _inject_scope_to_request(request):
    """
    Inject scope attributes to request.

    Args:
        request: Django request object
    """
    from apps.noc.services import NOCRBACService

    request.noc_clients = NOCRBACService.get_visible_clients(request.user)
    request.noc_can_ack = NOCRBACService.can_acknowledge_alerts(request.user)
    request.noc_can_escalate = NOCRBACService.can_escalate_alerts(request.user)
    request.noc_can_export = NOCRBACService.can_export_data(request.user)


def _unauthorized_response(message):
    """
    Build unauthorized response.

    Args:
        message: Error message

    Returns:
        JsonResponse or DRF Response
    """
    error_data = {'error': message, 'status': 'unauthorized'}
    return JsonResponse(error_data, status=403)


def _is_success_response(response):
    """
    Check if response is successful.

    Args:
        response: HTTP response

    Returns:
        bool: True if success status code
    """
    if isinstance(response, Response):
        return 200 <= response.status_code < 300

    if hasattr(response, 'status_code'):
        return 200 <= response.status_code < 300

    return False


def _log_unauthorized_attempt(user, capability, endpoint):
    """
    Log unauthorized access attempt.

    Args:
        user: People instance
        capability: Required capability
        endpoint: Endpoint path
    """
    from apps.noc.models import NOCAuditLog

    try:
        NOCAuditLog.objects.create(
            tenant=user.tenant,
            action='UNAUTHORIZED_ACCESS',
            actor=user,
            entity_type='endpoint',
            entity_id=0,
            metadata={
                'capability': capability,
                'endpoint': endpoint,
            },
            ip_address=None
        )
    except (ValueError, AttributeError) as e:
        logger.error(
            f"Failed to log unauthorized attempt",
            extra={'user_id': user.id, 'error': str(e)}
        )


def _create_audit_log(user, action, entity_type, entity_id, endpoint, ip_address):
    """
    Create audit log entry.

    Args:
        user: People instance
        action: Action performed
        entity_type: Type of entity
        entity_id: Entity ID
        endpoint: Endpoint path
        ip_address: Client IP address
    """
    from apps.noc.models import NOCAuditLog

    try:
        NOCAuditLog.objects.create(
            tenant=user.tenant,
            action=action,
            actor=user,
            entity_type=entity_type,
            entity_id=entity_id,
            metadata={'endpoint': endpoint},
            ip_address=ip_address
        )
    except (ValueError, AttributeError) as e:
        logger.error(
            f"Failed to create audit log",
            extra={'user_id': user.id, 'action': action, 'error': str(e)}
        )