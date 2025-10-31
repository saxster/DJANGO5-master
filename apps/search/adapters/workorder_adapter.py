"""
Work Order Search Adapter

Searches across work orders with site and asset relationships

Complies with Rule #7: < 150 lines
Complies with Rule #12: Query optimization
"""

from typing import Dict, List, Any
from django.db.models import QuerySet, Q
from django.utils import timezone
from apps.work_order_management.models import Wom  # Correct model name (capital W, lowercase om)
from .base_adapter import BaseSearchAdapter


class WorkOrderAdapter(BaseSearchAdapter):
    """Search adapter for Work Order entities"""

    entity_type = 'work_order'

    def get_queryset(self) -> QuerySet:
        """
        Return optimized Wom queryset with related data.

        Optimizations (Sprint 5):
        - select_related: 6 foreign keys (eager loading)
        - prefetch_related: 2 reverse relations (N+1 prevention)
        - filter: Work orders only (excludes WP/SLA)
        """
        return Wom.objects.select_related(
            'bu',        # Business unit (site)
            'client',    # Client organization
            'location',  # Location
            'asset',     # Asset
            'vendor',    # Vendor
            'qset'       # QuestionSet
        ).prefetch_related(
            'womdetails_set',            # Work order details (Q&A)
            'womdetails_set__question'   # Question details
        ).filter(
            tenant=self.tenant,
            identifier='WO'  # Work orders only (NOT work permits 'WP' or SLAs)
        )

    def apply_filters(self, queryset: QuerySet, filters: Dict) -> QuerySet:
        """Apply Work Order-specific filters"""

        if 'status' in filters:
            statuses = filters['status']
            if not isinstance(statuses, list):
                statuses = [statuses]
            queryset = queryset.filter(workstatus__in=statuses)  # Correct field name: workstatus

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
                expirydatetime__lt=timezone.now(),  # Correct field name
                workstatus__in=['ASSIGNED', 'INPROGRESS']  # Correct status values
            )

        # Removed wo_type filter - use 'identifier' instead ('WO', 'WP', 'SLA')

        return queryset

    def format_result(self, instance: Wom) -> Dict:
        """Format Wom instance to search result"""

        is_overdue = (
            instance.expirydatetime and
            instance.expirydatetime < timezone.now() and
            instance.workstatus in ['ASSIGNED', 'INPROGRESS']
        )

        subtitle_parts = []
        if instance.location:
            subtitle_parts.append(f"Site: {instance.location.sitename}")
        if instance.asset:
            subtitle_parts.append(f"Asset: {instance.asset.assetname}")

        snippet = instance.description[:200] if instance.description else ''

        return {
            'id': str(instance.id),
            'title': f"WO-{instance.id} - {instance.description or 'Work Order'}",
            'subtitle': ' | '.join(subtitle_parts),
            'snippet': snippet,
            'metadata': {
                'work_order_id': instance.id,
                'status': instance.workstatus,
                'priority': instance.priority,
                'is_overdue': is_overdue,
                'identifier': instance.identifier,  # 'WO', 'WP', or 'SLA'
                'performed_by': instance.performedby,
                'planned_datetime': instance.plandatetime.isoformat() if instance.plandatetime else None,
                'expiry_datetime': instance.expirydatetime.isoformat() if instance.expirydatetime else None,
                'vendor': instance.vendor.name if instance.vendor else None,
            }
        }

    def get_actions(self, instance: Wom) -> List[Dict]:
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

        if instance.workstatus not in ['COMPLETED', 'CANCELLED', 'CLOSED'] and self.user.has_perm('work_order_management.escalate_wom'):
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
            'description',           # Main description field
            'performedby',          # Who is performing the work
            'location__sitename',   # Site name
            'location__sitecode',   # Site code
            'asset__assetname',     # Asset name
            'asset__assetcode',     # Asset code
            'vendor__name',         # Vendor name
            'vendor__code'          # Vendor code
        ]