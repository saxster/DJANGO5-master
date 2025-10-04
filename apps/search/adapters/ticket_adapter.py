"""
Ticket Search Adapter

Searches across help desk tickets with permission enforcement

Complies with Rule #7: < 150 lines
Complies with Rule #12: Query optimization
"""

from typing import Dict, List, Any
from django.db.models import QuerySet, Q
from django.utils import timezone
from apps.y_helpdesk.models import Ticket
from .base_adapter import BaseSearchAdapter


class TicketAdapter(BaseSearchAdapter):
    """Search adapter for Ticket entities"""

    entity_type = 'ticket'

    def get_queryset(self) -> QuerySet:
        """
        Return optimized Ticket queryset with related data
        """
        return Ticket.objects.select_related(
            'bt',
            'client',
            'assigned_to',
            'created_by',
            'category'
        ).prefetch_related(
            'ticketesc_set'
        ).filter(
            tenant=self.tenant
        )

    def apply_filters(self, queryset: QuerySet, filters: Dict) -> QuerySet:
        """Apply Ticket-specific filters"""

        if 'status' in filters:
            statuses = filters['status']
            if not isinstance(statuses, list):
                statuses = [statuses]
            queryset = queryset.filter(status__in=statuses)

        if 'priority' in filters:
            priorities = filters['priority']
            if not isinstance(priorities, list):
                priorities = [priorities]
            queryset = queryset.filter(priority__in=priorities)

        if 'assigned_to' in filters:
            queryset = queryset.filter(assigned_to_id=filters['assigned_to'])

        if 'is_overdue' in filters and filters['is_overdue']:
            queryset = queryset.filter(
                ticket_end_date__lt=timezone.now(),
                status__in=['NEW', 'OPEN', 'ONHOLD']
            )

        if 'created_after' in filters:
            queryset = queryset.filter(created_on__gte=filters['created_after'])

        return queryset

    def format_result(self, instance: Ticket) -> Dict:
        """Format Ticket instance to search result"""

        is_overdue = (
            instance.ticket_end_date and
            instance.ticket_end_date < timezone.now() and
            instance.status in ['NEW', 'OPEN', 'ONHOLD']
        )

        snippet = instance.summary[:200] if instance.summary else ''

        return {
            'id': str(instance.id),
            'title': f"#{instance.ticketnumber} - {instance.subject}",
            'subtitle': f"Priority: {instance.get_priority_display()} | Status: {instance.get_status_display()}",
            'snippet': snippet,
            'metadata': {
                'ticketnumber': instance.ticketnumber,
                'priority': instance.priority,
                'status': instance.status,
                'is_overdue': is_overdue,
                'assigned_to': instance.assigned_to.peoplename if instance.assigned_to else None,
                'created_by': instance.created_by.peoplename if instance.created_by else None,
            }
        }

    def get_actions(self, instance: Ticket) -> List[Dict]:
        """Get available actions for Ticket"""

        actions = [
            {
                'label': 'Open',
                'href': f'/help-desk/tickets/{instance.id}',
                'method': 'GET'
            }
        ]

        if self.user.has_perm('y_helpdesk.change_ticket'):
            actions.extend([
                {
                    'label': 'Add Comment',
                    'href': f'/api/v1/tickets/{instance.id}/comments',
                    'method': 'POST'
                },
                {
                    'label': 'Assign',
                    'href': f'/api/v1/tickets/{instance.id}/assign',
                    'method': 'POST'
                }
            ])

        if instance.status not in ['RESOLVED', 'CLOSED'] and self.user.has_perm('y_helpdesk.escalate_ticket'):
            actions.append({
                'label': 'Escalate',
                'href': f'/api/v1/tickets/{instance.id}/escalate',
                'method': 'POST'
            })

        if instance.status in ['NEW', 'OPEN'] and self.user.has_perm('y_helpdesk.resolve_ticket'):
            actions.append({
                'label': 'Resolve',
                'href': f'/api/v1/tickets/{instance.id}/resolve',
                'method': 'POST'
            })

        return actions

    def get_search_fields(self) -> List[str]:
        """Return searchable fields for Ticket"""
        return [
            'ticketnumber',
            'subject',
            'summary',
            'bt__buname',
            'category__name'
        ]