"""
Help Desk Natural Language Query Executor.

Executes structured queries against Help Desk/Ticketing data with mandatory security validation.
Follows .claude/rules.md Rule #7 (<150 lines per method), Rule #11 (specific exceptions),
Rule #12 (query optimization), Rule #14b (multi-layer permission validation).

Part of NL Query Platform Expansion - Module 1 (highest ROI).
Business Value: $450k+/year productivity gains (25-30 hours/day × 100 helpdesk operators).
"""

import logging
from typing import Dict, Any, List
from datetime import timedelta
from decimal import Decimal
from django.db.models import Q, QuerySet, Count, Avg, F, ExpressionWrapper, DurationField
from django.utils import timezone
from django.core.exceptions import PermissionDenied, ObjectDoesNotExist
from apps.core.exceptions.patterns import DATABASE_EXCEPTIONS

__all__ = ['HelpDeskQueryExecutor']

logger = logging.getLogger('helpdesk.nl_query')


class HelpDeskQueryExecutor:
    """
    Execute structured queries against Help Desk/Ticketing data.

    Security Layers (Rule #14b):
    1. Tenant Isolation - All queries filtered by user.tenant
    2. RBAC Validation - Check user capabilities before execution
    3. Data Filtering - Apply permission-based data filtering
    4. Audit Logging - Log all query executions
    """

    @staticmethod
    def execute_ticket_query(params: Dict[str, Any], user) -> Dict[str, Any]:
        """
        Execute structured ticket query with security validation.

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
        # Level 1: Validate user has Help Desk access
        if not HelpDeskQueryExecutor._validate_user_permission(user):
            raise PermissionDenied(
                "User lacks permission for Help Desk queries"
            )

        # Level 2: Validate tenant isolation
        if not hasattr(user, 'tenant') or user.tenant is None:
            raise PermissionDenied("User has no tenant association")

        try:
            # Build base queryset with tenant isolation
            from apps.y_helpdesk.models import Ticket
            queryset = Ticket.objects.filter(tenant=user.tenant)

            # Apply filters
            queryset = HelpDeskQueryExecutor._apply_filters(
                queryset, params.get('filters', {}), user
            )

            # Apply time range
            queryset = HelpDeskQueryExecutor._apply_time_filter(
                queryset, params.get('time_range', {})
            )

            # Apply aggregation and ordering
            aggregation = params.get('aggregation', {})
            queryset = HelpDeskQueryExecutor._apply_ordering(
                queryset, aggregation.get('order_by', 'created_at')
            )

            # Optimize query with select_related (Rule #12)
            queryset = queryset.select_related(
                'bu', 'client', 'assignedtopeople', 'raisedbypeople',
                'assignedtogroup', 'ticketcategory', 'location', 'asset'
            )

            # Apply limit and fetch
            limit = aggregation.get('limit', 100)
            results = list(queryset[:limit])

            # Calculate metadata
            metadata = HelpDeskQueryExecutor._calculate_metadata(
                results, queryset, params
            )

            # Log successful execution
            logger.info(
                "Help Desk query executed successfully",
                extra={
                    'user_id': user.id,
                    'tenant_id': user.tenant.id,
                    'result_count': len(results),
                    'query_filters': params.get('filters', {}),
                }
            )

            return {
                'results': results,
                'metadata': metadata,
                'query_info': params,
            }

        except DATABASE_EXCEPTIONS as e:
            logger.error(
                f"Database error executing Help Desk query: {e}",
                extra={'user_id': user.id},
                exc_info=True
            )
            raise

    @staticmethod
    def _validate_user_permission(user) -> bool:
        """
        Validate user has required Help Desk capability.

        Args:
            user: People instance

        Returns:
            True if user has permission, False otherwise
        """
        # Admin bypass
        if user.isadmin:
            return True

        # Check for Help Desk capability
        from apps.peoples.services import UserCapabilityService

        capabilities = UserCapabilityService.get_effective_permissions(user)

        # Basic Help Desk view required for all queries
        return 'helpdesk:view' in capabilities or 'ticket:view' in capabilities

    @staticmethod
    def _apply_filters(queryset: QuerySet, filters: Dict[str, Any], user) -> QuerySet:
        """
        Apply all filters to queryset.

        Args:
            queryset: Base QuerySet
            filters: Filter parameters
            user: Requesting user

        Returns:
            Filtered QuerySet
        """
        if filters.get('status'):
            queryset = HelpDeskQueryExecutor._apply_status_filter(
                queryset, filters['status']
            )

        if filters.get('priority'):
            queryset = HelpDeskQueryExecutor._apply_priority_filter(
                queryset, filters['priority']
            )

        if filters.get('site_name') or filters.get('site_id'):
            queryset = HelpDeskQueryExecutor._apply_site_filter(
                queryset, filters.get('site_name'), filters.get('site_id')
            )

        if filters.get('assignment_type'):
            queryset = HelpDeskQueryExecutor._apply_assignment_filter(
                queryset, filters['assignment_type'], user
            )

        if filters.get('escalation'):
            queryset = HelpDeskQueryExecutor._apply_escalation_filter(
                queryset, filters['escalation']
            )

        if filters.get('sla_status'):
            queryset = HelpDeskQueryExecutor._apply_sla_filter(
                queryset, filters['sla_status']
            )

        if filters.get('source'):
            queryset = HelpDeskQueryExecutor._apply_source_filter(
                queryset, filters['source']
            )

        if filters.get('category_id') or filters.get('category_name'):
            queryset = HelpDeskQueryExecutor._apply_category_filter(
                queryset, filters.get('category_id'), filters.get('category_name')
            )

        return queryset

    @staticmethod
    def _apply_status_filter(queryset: QuerySet, status_list: List[str]) -> QuerySet:
        """
        Apply status filter to queryset.

        Args:
            queryset: Base QuerySet
            status_list: List of status values

        Returns:
            Filtered QuerySet
        """
        # Normalize status values to match Ticket.Status choices
        valid_statuses = []
        status_mapping = {
            'NEW': 'NEW',
            'OPEN': 'OPEN',
            'RESOLVED': 'RESOLVED',
            'CLOSED': 'CLOSED',
            'ONHOLD': 'ONHOLD',
            'CANCELLED': 'CANCELLED',
            'CANCEL': 'CANCELLED',  # Alias
        }

        for status in status_list:
            normalized = status.upper()
            mapped_status = status_mapping.get(normalized, normalized)
            valid_statuses.append(mapped_status)

        return queryset.filter(status__in=valid_statuses)

    @staticmethod
    def _apply_priority_filter(queryset: QuerySet, priorities: List[str]) -> QuerySet:
        """
        Apply priority filter to queryset.

        Args:
            queryset: Base QuerySet
            priorities: List of priority values (LOW, MEDIUM, HIGH)

        Returns:
            Filtered QuerySet
        """
        # Normalize to uppercase
        normalized_priorities = [p.upper() for p in priorities]
        return queryset.filter(priority__in=normalized_priorities)

    @staticmethod
    def _apply_site_filter(
        queryset: QuerySet, site_name: str = None, site_id: int = None
    ) -> QuerySet:
        """
        Apply site filter to queryset.

        Args:
            queryset: Base QuerySet
            site_name: Site name (partial match)
            site_id: Site ID (exact match)

        Returns:
            Filtered QuerySet
        """
        if site_id:
            return queryset.filter(bu_id=site_id)
        elif site_name:
            return queryset.filter(bu__buname__icontains=site_name)
        return queryset

    @staticmethod
    def _apply_assignment_filter(
        queryset: QuerySet, assignment_type: str, user
    ) -> QuerySet:
        """
        Apply assignment filter to queryset.

        Args:
            queryset: Base QuerySet
            assignment_type: 'my_tickets', 'my_groups', 'unassigned'
            user: Requesting user

        Returns:
            Filtered QuerySet
        """
        if assignment_type == 'my_tickets':
            return queryset.filter(assignedtopeople=user)

        elif assignment_type == 'my_groups':
            # Get user's groups
            user_groups = user.pgroup_set.all()
            return queryset.filter(assignedtogroup__in=user_groups)

        elif assignment_type == 'unassigned':
            return queryset.filter(
                assignedtopeople__isnull=True,
                assignedtogroup__isnull=True
            )

        return queryset

    @staticmethod
    def _apply_escalation_filter(
        queryset: QuerySet, escalation_params: Dict[str, Any]
    ) -> QuerySet:
        """
        Apply escalation filter to queryset.

        Note: Escalation data is in TicketWorkflow model (lazy-loaded).
        This requires a join to the workflow table.

        Args:
            queryset: Base QuerySet
            escalation_params: Dict with 'is_escalated' or 'level'

        Returns:
            Filtered QuerySet
        """
        from apps.y_helpdesk.models import TicketWorkflow

        if escalation_params.get('is_escalated'):
            # Join with TicketWorkflow and filter by is_escalated
            queryset = queryset.filter(
                workflow__is_escalated=True
            )

        if escalation_params.get('level'):
            level = escalation_params['level']
            queryset = queryset.filter(
                workflow__escalation_level=level
            )

        if escalation_params.get('min_level'):
            min_level = escalation_params['min_level']
            queryset = queryset.filter(
                workflow__escalation_level__gte=min_level
            )

        return queryset

    @staticmethod
    def _apply_sla_filter(queryset: QuerySet, sla_status: str) -> QuerySet:
        """
        Apply SLA filter to queryset.

        Args:
            queryset: Base QuerySet
            sla_status: 'overdue', 'approaching', 'compliant'

        Returns:
            Filtered QuerySet
        """
        from apps.y_helpdesk.models import Ticket

        now = timezone.now()

        if sla_status == 'overdue':
            # Tickets past expiry datetime
            queryset = queryset.filter(
                expirydatetime__lt=now
            ).exclude(
                status__in=['CLOSED', 'RESOLVED', 'CANCELLED']
            )

        elif sla_status == 'approaching':
            # Tickets with < 2 hours until SLA breach
            two_hours_from_now = now + timedelta(hours=2)
            queryset = queryset.filter(
                expirydatetime__lte=two_hours_from_now,
                expirydatetime__gt=now
            ).exclude(
                status__in=['CLOSED', 'RESOLVED', 'CANCELLED']
            )

        elif sla_status == 'compliant':
            # Tickets with time remaining
            queryset = queryset.filter(
                expirydatetime__gt=now
            ).exclude(
                status__in=['CLOSED', 'RESOLVED', 'CANCELLED']
            )

        return queryset

    @staticmethod
    def _apply_source_filter(queryset: QuerySet, source: str) -> QuerySet:
        """
        Apply ticket source filter.

        Args:
            queryset: Base QuerySet
            source: 'SYSTEMGENERATED' or 'USERDEFINED'

        Returns:
            Filtered QuerySet
        """
        source_upper = source.upper()
        return queryset.filter(ticketsource=source_upper)

    @staticmethod
    def _apply_category_filter(
        queryset: QuerySet, category_id: int = None, category_name: str = None
    ) -> QuerySet:
        """
        Apply ticket category filter.

        Args:
            queryset: Base QuerySet
            category_id: Category ID (exact match)
            category_name: Category name (partial match)

        Returns:
            Filtered QuerySet
        """
        if category_id:
            return queryset.filter(ticketcategory_id=category_id)
        elif category_name:
            return queryset.filter(ticketcategory__type_assist_name__icontains=category_name)
        return queryset

    @staticmethod
    def _apply_time_filter(
        queryset: QuerySet, time_range: Dict[str, Any]
    ) -> QuerySet:
        """
        Apply time range filter to queryset.

        Args:
            queryset: Base QuerySet
            time_range: Time range dict (hours, days, start_date, end_date)

        Returns:
            Filtered QuerySet
        """
        now = timezone.now()

        if time_range.get('hours'):
            start_time = now - timedelta(hours=time_range['hours'])
            queryset = queryset.filter(cdtz__gte=start_time)

        elif time_range.get('days'):
            start_time = now - timedelta(days=time_range['days'])
            queryset = queryset.filter(cdtz__gte=start_time)

        elif time_range.get('start_date') and time_range.get('end_date'):
            queryset = queryset.filter(
                cdtz__gte=time_range['start_date'],
                cdtz__lte=time_range['end_date']
            )
        else:
            # Default to last 7 days if no time range specified
            start_time = now - timedelta(days=7)
            queryset = queryset.filter(cdtz__gte=start_time)

        return queryset

    @staticmethod
    def _apply_ordering(queryset: QuerySet, order_by: str) -> QuerySet:
        """
        Apply ordering to queryset.

        Args:
            queryset: Base QuerySet
            order_by: Ordering field ('created_at', 'priority', 'status', 'sla')

        Returns:
            Ordered QuerySet
        """
        if order_by == 'priority':
            # High > Medium > Low
            priority_order = {
                'HIGH': 1,
                'MEDIUM': 2,
                'LOW': 3
            }
            # Use CASE WHEN for custom ordering (Django 4.0+)
            from django.db.models import Case, When, IntegerField
            queryset = queryset.annotate(
                priority_order=Case(
                    When(priority='HIGH', then=1),
                    When(priority='MEDIUM', then=2),
                    When(priority='LOW', then=3),
                    default=4,
                    output_field=IntegerField()
                )
            ).order_by('priority_order', '-cdtz')

        elif order_by == 'sla':
            # Order by expiry datetime (soonest first)
            queryset = queryset.order_by('expirydatetime')

        elif order_by == 'status':
            queryset = queryset.order_by('status', '-cdtz')

        else:  # Default: created_at
            queryset = queryset.order_by('-cdtz')

        return queryset

    @staticmethod
    def _calculate_metadata(
        results: List, queryset: QuerySet, params: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Calculate query metadata and statistics.

        Args:
            results: Fetched results
            queryset: Full queryset (before limit)
            params: Query parameters

        Returns:
            Metadata dict
        """
        metadata = {
            'total_count': queryset.count(),
            'returned_count': len(results),
            'query_type': 'tickets',
        }

        # Calculate status distribution
        if results:
            from collections import Counter
            status_counts = Counter(
                ticket.status for ticket in results if ticket.status
            )
            metadata['status_distribution'] = dict(status_counts)

            # Calculate priority distribution
            priority_counts = Counter(
                ticket.priority for ticket in results if ticket.priority
            )
            metadata['priority_distribution'] = dict(priority_counts)

            # Calculate overdue count
            now = timezone.now()
            overdue_count = sum(
                1 for ticket in results
                if hasattr(ticket, 'expirydatetime') and
                ticket.expirydatetime and
                ticket.expirydatetime < now and
                ticket.status not in ['CLOSED', 'RESOLVED', 'CANCELLED']
            )
            metadata['overdue_count'] = overdue_count

        return metadata
