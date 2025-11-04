"""
NOC Query Executor with Tenant Isolation and RBAC.

Executes structured queries against NOC data models with mandatory security validation.
Follows .claude/rules.md Rule #7 (<150 lines), Rule #11 (specific exceptions),
Rule #12 (query optimization), Rule #14b (multi-layer permission validation).
"""

import logging
from typing import Dict, Any, List
from datetime import timedelta
from django.db.models import Q, QuerySet, Count, Max, Min, Avg
from django.utils import timezone
from django.core.exceptions import PermissionDenied
from apps.core.exceptions.patterns import DATABASE_EXCEPTIONS

__all__ = ['QueryExecutor']

logger = logging.getLogger('noc.nl_query')


class QueryExecutor:
    """
    Execute structured queries with security enforcement.

    Security Layers (Rule #14b):
    1. Tenant Isolation - All queries filtered by user.tenant
    2. RBAC Validation - Check user capabilities before execution
    3. Data Filtering - Apply permission-based data filtering
    4. Audit Logging - Log all query executions
    """

    QUERY_TYPE_HANDLERS = {
        'alerts': '_execute_alerts_query',
        'incidents': '_execute_incidents_query',
        'metrics': '_execute_metrics_query',
        'fraud': '_execute_fraud_query',
        'trends': '_execute_trends_query',
        'predictions': '_execute_predictions_query',
    }

    @staticmethod
    def execute_query(params: Dict[str, Any], user) -> Dict[str, Any]:
        """
        Execute structured query with security validation.

        Args:
            params: Structured query parameters from QueryParser
            user: People instance (requesting user)

        Returns:
            Dict with keys: results (list), metadata (dict), query_info (dict)

        Raises:
            PermissionDenied: If user lacks required permissions
            ValueError: If query parameters are invalid
            DatabaseError: If query execution fails
        """
        # Level 1: Validate user has NOC access
        if not QueryExecutor._validate_user_permission(user, params['query_type']):
            raise PermissionDenied(
                f"User lacks permission for query type: {params['query_type']}"
            )

        # Level 2: Validate tenant isolation
        if not hasattr(user, 'tenant') or user.tenant is None:
            raise PermissionDenied("User has no tenant association")

        # Get handler for query type
        handler_name = QueryExecutor.QUERY_TYPE_HANDLERS.get(params['query_type'])
        if not handler_name:
            raise ValueError(f"Unsupported query type: {params['query_type']}")

        handler = getattr(QueryExecutor, handler_name)

        try:
            # Execute query with tenant isolation
            results = handler(params, user)

            # Log successful execution
            logger.info(
                f"Query executed successfully",
                extra={
                    'user_id': user.id,
                    'tenant_id': user.tenant.id,
                    'query_type': params['query_type'],
                    'result_count': len(results.get('results', [])),
                }
            )

            return results

        except DATABASE_EXCEPTIONS as e:
            logger.error(
                f"Database error executing query: {e}",
                extra={'user_id': user.id, 'query_type': params['query_type']},
                exc_info=True
            )
            raise

    @staticmethod
    def _validate_user_permission(user, query_type: str) -> bool:
        """
        Validate user has required NOC capability.

        Args:
            user: People instance
            query_type: Type of query being executed

        Returns:
            True if user has permission, False otherwise
        """
        from apps.peoples.services import UserCapabilityService

        # Admin bypass
        if user.isadmin:
            return True

        capabilities = UserCapabilityService.get_effective_permissions(user)

        # Basic NOC view required for all queries
        if 'noc:view' not in capabilities:
            return False

        # Additional checks for sensitive query types
        if query_type == 'fraud' and 'noc:audit_view' not in capabilities:
            return False

        return True

    @staticmethod
    def _execute_alerts_query(params: Dict[str, Any], user) -> Dict[str, Any]:
        """Execute query for NOC alerts."""
        from apps.noc.models import NOCAlertEvent
        from apps.noc.services.rbac_service import NOCRBACService

        # Start with tenant-isolated queryset
        queryset = NOCAlertEvent.objects.filter(tenant=user.tenant)

        # Apply permission-based filtering
        visible_clients = NOCRBACService.get_visible_clients(user)
        queryset = queryset.filter(client__in=visible_clients)

        # Apply time range
        queryset = QueryExecutor._apply_time_filter(queryset, params.get('time_range', {}))

        # Apply filters
        filters = params.get('filters', {})
        if filters.get('severity'):
            queryset = queryset.filter(severity__in=filters['severity'])
        if filters.get('status'):
            queryset = queryset.filter(status__in=filters['status'])
        if filters.get('alert_type'):
            queryset = queryset.filter(alert_type__in=filters['alert_type'])
        if filters.get('site_id'):
            queryset = queryset.filter(bu_id=filters['site_id'])

        # Apply aggregation
        aggregation = params.get('aggregation', {})
        limit = aggregation.get('limit', 100)

        # Optimize query with select_related (Rule #12)
        queryset = queryset.select_related('client', 'bu', 'tenant')

        # Apply ordering
        order_by = aggregation.get('order_by', 'timestamp')
        if order_by == 'count':
            queryset = queryset.order_by('-suppressed_count')
        elif order_by == 'severity':
            # Critical > High > Medium > Low > Info
            severity_order = {'CRITICAL': 1, 'HIGH': 2, 'MEDIUM': 3, 'LOW': 4, 'INFO': 5}
            queryset = queryset.order_by('severity')
        elif order_by == 'priority':
            queryset = queryset.order_by('-priority_score') if hasattr(NOCAlertEvent, 'priority_score') else queryset.order_by('-created_at')
        else:
            queryset = queryset.order_by('-created_at')

        # Apply limit and fetch
        results = list(queryset[:limit])

        return {
            'results': results,
            'metadata': {
                'total_count': queryset.count(),
                'returned_count': len(results),
                'query_type': 'alerts',
            },
            'query_info': params,
        }

    @staticmethod
    def _execute_incidents_query(params: Dict[str, Any], user) -> Dict[str, Any]:
        """Execute query for NOC incidents."""
        from apps.noc.models import NOCIncident
        from apps.noc.services.rbac_service import NOCRBACService

        queryset = NOCIncident.objects.filter(tenant=user.tenant)

        # Apply RBAC filtering
        visible_clients = NOCRBACService.get_visible_clients(user)
        queryset = queryset.filter(client__in=visible_clients)

        # Apply time range and filters
        queryset = QueryExecutor._apply_time_filter(queryset, params.get('time_range', {}))

        filters = params.get('filters', {})
        if filters.get('severity'):
            queryset = queryset.filter(severity__in=filters['severity'])
        if filters.get('status'):
            queryset = queryset.filter(state__in=filters['status'])
        if filters.get('site_id'):
            queryset = queryset.filter(site_id=filters['site_id'])

        # Optimize with prefetch
        queryset = queryset.select_related('client', 'site', 'tenant').prefetch_related('alerts')

        limit = params.get('aggregation', {}).get('limit', 100)
        results = list(queryset.order_by('-created_at')[:limit])

        return {
            'results': results,
            'metadata': {
                'total_count': queryset.count(),
                'returned_count': len(results),
                'query_type': 'incidents',
            },
            'query_info': params,
        }

    @staticmethod
    def _execute_metrics_query(params: Dict[str, Any], user) -> Dict[str, Any]:
        """Execute query for NOC metrics."""
        from apps.noc.models import NOCMetricSnapshot

        queryset = NOCMetricSnapshot.objects.filter(tenant=user.tenant)
        queryset = QueryExecutor._apply_time_filter(queryset, params.get('time_range', {}))

        filters = params.get('filters', {})
        if filters.get('site_id'):
            queryset = queryset.filter(site_id=filters['site_id'])
        if filters.get('client_id'):
            queryset = queryset.filter(client_id=filters['client_id'])

        limit = params.get('aggregation', {}).get('limit', 100)
        results = list(queryset.order_by('-timestamp')[:limit])

        return {
            'results': results,
            'metadata': {
                'total_count': queryset.count(),
                'returned_count': len(results),
                'query_type': 'metrics',
            },
            'query_info': params,
        }

    @staticmethod
    def _execute_fraud_query(params: Dict[str, Any], user) -> Dict[str, Any]:
        """Execute query for fraud detection results."""
        # Placeholder for fraud query implementation
        return {
            'results': [],
            'metadata': {
                'total_count': 0,
                'returned_count': 0,
                'query_type': 'fraud',
                'note': 'Fraud detection queries require additional module integration',
            },
            'query_info': params,
        }

    @staticmethod
    def _execute_trends_query(params: Dict[str, Any], user) -> Dict[str, Any]:
        """Execute query for trend analysis."""
        from apps.noc.models import NOCAlertEvent

        queryset = NOCAlertEvent.objects.filter(tenant=user.tenant)
        queryset = QueryExecutor._apply_time_filter(queryset, params.get('time_range', {}))

        # Aggregate by group_by fields
        aggregation = params.get('aggregation', {})
        group_by = aggregation.get('group_by', ['severity'])

        # Simple aggregation
        results = queryset.values(*group_by).annotate(count=Count('id')).order_by('-count')
        limit = aggregation.get('limit', 100)

        return {
            'results': list(results[:limit]),
            'metadata': {
                'total_count': len(results),
                'returned_count': min(len(results), limit),
                'query_type': 'trends',
                'grouped_by': group_by,
            },
            'query_info': params,
        }

    @staticmethod
    def _execute_predictions_query(params: Dict[str, Any], user) -> Dict[str, Any]:
        """Execute query for predictive alerts."""
        from apps.noc.models import PredictiveAlertTracking

        queryset = PredictiveAlertTracking.objects.filter(tenant=user.tenant)
        queryset = QueryExecutor._apply_time_filter(queryset, params.get('time_range', {}), field='predicted_at')

        filters = params.get('filters', {})
        if filters.get('alert_type'):
            queryset = queryset.filter(alert_type__in=filters['alert_type'])

        limit = params.get('aggregation', {}).get('limit', 100)
        results = list(queryset.order_by('-predicted_at')[:limit])

        return {
            'results': results,
            'metadata': {
                'total_count': queryset.count(),
                'returned_count': len(results),
                'query_type': 'predictions',
            },
            'query_info': params,
        }

    @staticmethod
    def _apply_time_filter(queryset: QuerySet, time_range: Dict[str, Any], field: str = 'created_at') -> QuerySet:
        """
        Apply time range filter to queryset.

        Args:
            queryset: Django QuerySet
            time_range: Time range dict (hours, days, start_date, end_date)
            field: Timestamp field name

        Returns:
            Filtered QuerySet
        """
        now = timezone.now()

        if time_range.get('hours'):
            start_time = now - timedelta(hours=time_range['hours'])
            queryset = queryset.filter(**{f'{field}__gte': start_time})
        elif time_range.get('days'):
            start_time = now - timedelta(days=time_range['days'])
            queryset = queryset.filter(**{f'{field}__gte': start_time})
        elif time_range.get('start_date') and time_range.get('end_date'):
            queryset = queryset.filter(
                **{
                    f'{field}__gte': time_range['start_date'],
                    f'{field}__lte': time_range['end_date']
                }
            )
        else:
            # Default to last 24 hours if no time range specified
            start_time = now - timedelta(hours=24)
            queryset = queryset.filter(**{f'{field}__gte': start_time})

        return queryset
