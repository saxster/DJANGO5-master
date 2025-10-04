"""
Work Order Search Adapter

Searches across work orders with site and asset relationships

Complies with Rule #7: < 150 lines
Complies with Rule #12: Query optimization
"""

from typing import Dict, List, Any
from django.db.models import QuerySet, Q
from django.utils import timezone
from apps.work_order_management.models import WOM
from .base_adapter import BaseSearchAdapter


class WorkOrderAdapter(BaseSearchAdapter):
    """Search adapter for Work Order entities"""

    entity_type = 'work_order'

    def get_queryset(self) -> QuerySet:
        """
        Return optimized WOM queryset with related data
        """
        return WOM.objects.select_related(
            'bt',
            'client',
            'location',
            'asset',
            'assigned_to',
            'vendor'
        ).prefetch_related(
            'womdetails_set',
            'approver_set'
        ).filter(
            tenant=self.tenant
        )

    def apply_filters(self, queryset: QuerySet, filters: Dict) -> QuerySet:
        """Apply Work Order-specific filters"""

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

        if 'location' in filters:
            queryset = queryset.filter(location_id=filters['location'])

        if 'asset' in filters:
            queryset = queryset.filter(asset_id=filters['asset'])

        if 'assigned_to' in filters:
            queryset = queryset.filter(assigned_to_id=filters['assigned_to'])

        if 'is_overdue' in filters and filters['is_overdue']:
            queryset = queryset.filter(
                due_date__lt=timezone.now(),
                status__in=['PENDING', 'IN_PROGRESS']
            )

        if 'wo_type' in filters:
            queryset = queryset.filter(wo_type=filters['wo_type'])

        return queryset

    def format_result(self, instance: WOM) -> Dict:
        """Format WOM instance to search result"""

        is_overdue = (
            instance.due_date and
            instance.due_date < timezone.now() and
            instance.status in ['PENDING', 'IN_PROGRESS']
        )

        subtitle_parts = []
        if instance.location:
            subtitle_parts.append(f"Site: {instance.location.sitename}")
        if instance.asset:
            subtitle_parts.append(f"Asset: {instance.asset.assetname}")

        snippet = instance.description[:200] if instance.description else ''

        return {
            'id': str(instance.id),
            'title': f"WO-{instance.wo_number} - {instance.title or 'Work Order'}",
            'subtitle': ' | '.join(subtitle_parts),
            'snippet': snippet,
            'metadata': {
                'wo_number': instance.wo_number,
                'status': instance.status,
                'priority': instance.priority,
                'is_overdue': is_overdue,
                'wo_type': instance.wo_type,
                'assigned_to': instance.assigned_to.peoplename if instance.assigned_to else None,
                'due_date': instance.due_date.isoformat() if instance.due_date else None,
            }
        }

    def get_actions(self, instance: WOM) -> List[Dict]:
        """Get available actions for Work Order"""

        actions = [
            {
                'label': 'Open',
                'href': f'/operations/work-orders/{instance.id}',
                'method': 'GET'
            }
        ]

        if self.user.has_perm('work_order_management.change_wom'):
            actions.extend([
                {
                    'label': 'Assign',
                    'href': f'/api/v1/work-orders/{instance.id}/assign',
                    'method': 'POST'
                },
                {
                    'label': 'Edit',
                    'href': f'/operations/work-orders/{instance.id}/edit',
                    'method': 'GET'
                }
            ])

        if instance.status not in ['COMPLETED', 'CANCELLED'] and self.user.has_perm('work_order_management.escalate_wom'):
            actions.append({
                'label': 'Escalate',
                'href': f'/api/v1/work-orders/{instance.id}/escalate',
                'method': 'POST'
            })

        if self.user.has_perm('work_order_management.export_wom'):
            actions.append({
                'label': 'Export PDF',
                'href': f'/api/v1/work-orders/{instance.id}/export',
                'method': 'GET'
            })

        return actions

    def get_search_fields(self) -> List[str]:
        """Return searchable fields for Work Order"""
        return [
            'wo_number',
            'title',
            'description',
            'location__sitename',
            'asset__assetname',
            'vendor__name'
        ]