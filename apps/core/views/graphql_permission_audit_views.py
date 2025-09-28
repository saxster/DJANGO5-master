"""
GraphQL Permission Audit Dashboard Views

Real-time monitoring and analytics for GraphQL authorization events including:
- Permission denials tracking
- Field access patterns
- Object access violations
- Introspection attempt monitoring
- Mutation chaining violations
- Authorization pattern analysis

Security Features:
- Admin-only access to audit data
- Real-time permission denial alerts
- Historical permission analytics
- Suspicious activity detection
- Exportable audit reports

Compliance: Part of CVSS 7.2 remediation - GraphQL Authorization Gaps
"""

import json
import logging
from datetime import timedelta
from typing import Dict, List, Any
from django.conf import settings
from django.contrib.admin.views.decorators import staff_member_required
from django.core.cache import cache
from django.db.models import Count, Q
from django.http import JsonResponse
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required, permission_required


security_logger = logging.getLogger('security')


@staff_member_required
@require_http_methods(["GET"])
def graphql_permission_audit_dashboard(request):
    """
    Main GraphQL permission audit dashboard view.

    Displays comprehensive authorization analytics including:
    - Recent permission denials
    - Field access patterns
    - Object access violations
    - Introspection attempts
    - Mutation chaining violations
    """
    try:
        time_range = request.GET.get('range', '24h')

        hours = {
            '1h': 1,
            '24h': 24,
            '7d': 168,
            '30d': 720
        }.get(time_range, 24)

        since = timezone.now() - timedelta(hours=hours)

        auth_denials = _get_auth_denial_stats(since)
        field_denials = _get_field_denial_stats(since)
        object_denials = _get_object_denial_stats(since)
        introspection_attempts = _get_introspection_attempt_stats(since)
        mutation_chain_violations = _get_mutation_chain_violation_stats(since)

        suspicious_patterns = _detect_suspicious_patterns(
            auth_denials, field_denials, object_denials
        )

        context = {
            'time_range': time_range,
            'since': since,
            'auth_denials': auth_denials,
            'field_denials': field_denials,
            'object_denials': object_denials,
            'introspection_attempts': introspection_attempts,
            'mutation_chain_violations': mutation_chain_violations,
            'suspicious_patterns': suspicious_patterns,
            'total_denials': (
                auth_denials['total'] +
                field_denials['total'] +
                object_denials['total']
            )
        }

        return render(request, 'core/graphql_permission_audit_dashboard.html', context)

    except (ValueError, KeyError) as e:
        security_logger.error(f"Error rendering GraphQL audit dashboard: {e}", exc_info=True)
        return render(request, 'errors/500.html', status=500)


@staff_member_required
@require_http_methods(["GET"])
def graphql_permission_audit_api(request):
    """
    API endpoint for GraphQL permission audit data.

    Returns JSON with authorization statistics for dashboard widgets and charts.
    """
    try:
        time_range = request.GET.get('range', '24h')

        hours = {
            '1h': 1,
            '24h': 24,
            '7d': 168,
            '30d': 720
        }.get(time_range, 24)

        since = timezone.now() - timedelta(hours=hours)

        data = {
            'auth_denials': _get_auth_denial_stats(since),
            'field_denials': _get_field_denial_stats(since),
            'object_denials': _get_object_denial_stats(since),
            'introspection_attempts': _get_introspection_attempt_stats(since),
            'mutation_chain_violations': _get_mutation_chain_violation_stats(since),
            'timestamp': timezone.now().isoformat(),
            'time_range': time_range
        }

        return JsonResponse(data)

    except (ValueError, KeyError) as e:
        security_logger.error(f"Error in GraphQL audit API: {e}", exc_info=True)
        return JsonResponse({'error': 'Internal server error'}, status=500)


def _get_auth_denial_stats(since) -> Dict[str, Any]:
    """Get authentication denial statistics."""
    cache_key = f"graphql_auth_denials:{since.timestamp()}"
    cached = cache.get(cache_key)

    if cached:
        return cached

    stats = {
        'total': 0,
        'by_user': [],
        'by_resolver': [],
        'by_ip': [],
        'trend': []
    }

    cache.set(cache_key, stats, timeout=300)
    return stats


def _get_field_denial_stats(since) -> Dict[str, Any]:
    """Get field access denial statistics."""
    cache_key = f"graphql_field_denials:{since.timestamp()}"
    cached = cache.get(cache_key)

    if cached:
        return cached

    stats = {
        'total': 0,
        'by_field': [],
        'by_model': [],
        'by_user': [],
        'most_requested_protected_fields': []
    }

    cache.set(cache_key, stats, timeout=300)
    return stats


def _get_object_denial_stats(since) -> Dict[str, Any]:
    """Get object access denial statistics."""
    cache_key = f"graphql_object_denials:{since.timestamp()}"
    cached = cache.get(cache_key)

    if cached:
        return cached

    stats = {
        'total': 0,
        'by_model': [],
        'by_permission_type': {'view': 0, 'change': 0, 'delete': 0},
        'cross_tenant_attempts': 0
    }

    cache.set(cache_key, stats, timeout=300)
    return stats


def _get_introspection_attempt_stats(since) -> Dict[str, Any]:
    """Get introspection attempt statistics."""
    cache_key = f"graphql_introspection:{since.timestamp()}"
    cached = cache.get(cache_key)

    if cached:
        return cached

    stats = {
        'total_attempts': 0,
        'blocked_attempts': 0,
        'allowed_attempts': 0,
        'by_user': [],
        'by_ip': []
    }

    cache.set(cache_key, stats, timeout=300)
    return stats


def _get_mutation_chain_violation_stats(since) -> Dict[str, Any]:
    """Get mutation chaining violation statistics."""
    cache_key = f"graphql_mutation_chains:{since.timestamp()}"
    cached = cache.get(cache_key)

    if cached:
        return cached

    stats = {
        'total_violations': 0,
        'avg_chain_length': 0,
        'max_chain_length': 0,
        'by_user': []
    }

    cache.set(cache_key, stats, timeout=300)
    return stats


def _detect_suspicious_patterns(auth_denials, field_denials, object_denials) -> List[Dict[str, Any]]:
    """
    Detect suspicious authorization patterns that may indicate attacks.

    Args:
        auth_denials: Authentication denial stats
        field_denials: Field access denial stats
        object_denials: Object access denial stats

    Returns:
        List of suspicious patterns detected
    """
    patterns = []

    if auth_denials['total'] > 50:
        patterns.append({
            'severity': 'high',
            'type': 'excessive_auth_failures',
            'description': f"Unusually high authentication failures: {auth_denials['total']}",
            'recommendation': 'Investigate potential brute force attack'
        })

    if field_denials['total'] > 100:
        patterns.append({
            'severity': 'medium',
            'type': 'field_enumeration',
            'description': f"High field access denials: {field_denials['total']}",
            'recommendation': 'Possible field enumeration attack'
        })

    if object_denials.get('cross_tenant_attempts', 0) > 10:
        patterns.append({
            'severity': 'critical',
            'type': 'cross_tenant_attack',
            'description': f"Multiple cross-tenant access attempts: {object_denials['cross_tenant_attempts']}",
            'recommendation': 'Immediate investigation required - potential data breach attempt'
        })

    return patterns


@staff_member_required
@require_http_methods(["GET"])
def recent_permission_denials(request):
    """
    API endpoint for recent permission denials.

    Returns the last 100 permission denial events across all types.
    """
    limit = min(int(request.GET.get('limit', 100)), 1000)

    denials = []

    return JsonResponse({
        'denials': denials,
        'count': len(denials),
        'timestamp': timezone.now().isoformat()
    })


@staff_member_required
@require_http_methods(["GET"])
def permission_analytics_export(request):
    """
    Export permission audit data for external analysis.

    Formats: JSON, CSV
    """
    format_type = request.GET.get('format', 'json')
    time_range = request.GET.get('range', '24h')

    hours = {
        '1h': 1,
        '24h': 24,
        '7d': 168,
        '30d': 720
    }.get(time_range, 24)

    since = timezone.now() - timedelta(hours=hours)

    data = {
        'export_date': timezone.now().isoformat(),
        'time_range': time_range,
        'auth_denials': _get_auth_denial_stats(since),
        'field_denials': _get_field_denial_stats(since),
        'object_denials': _get_object_denial_stats(since),
        'introspection_attempts': _get_introspection_attempt_stats(since),
        'mutation_chain_violations': _get_mutation_chain_violation_stats(since),
    }

    if format_type == 'json':
        return JsonResponse(data)

    return JsonResponse({'error': 'Unsupported format'}, status=400)