"""
People Search Adapter

Searches across People model with profile and organizational data
Uses optimized queries with with_profile() and with_organizational()

Complies with Rule #7: < 150 lines
Complies with Rule #12: Query optimization with select_related/prefetch_related
"""

from typing import Dict, List, Any
from django.db.models import QuerySet, Q
from apps.peoples.models import People
from .base_adapter import BaseSearchAdapter


class PeopleAdapter(BaseSearchAdapter):
    """Search adapter for People entities"""

    entity_type = 'people'

    def get_queryset(self) -> QuerySet:
        """
        Return optimized People queryset

        Uses existing optimization helpers from refactored People model
        """
        return People.objects.with_profile().with_organizational().filter(
            tenant=self.tenant,
            enable=True
        )

    def apply_filters(self, queryset: QuerySet, filters: Dict) -> QuerySet:
        """Apply People-specific filters"""

        if 'status' in filters:
            queryset = queryset.filter(enable=filters['status'] == 'active')

        if 'department' in filters:
            queryset = queryset.filter(
                organizational__department__icontains=filters['department']
            )

        if 'peopletype' in filters:
            queryset = queryset.filter(
                organizational__peopletype=filters['peopletype']
            )

        if 'is_verified' in filters:
            queryset = queryset.filter(isverified=filters['is_verified'])

        return queryset

    def format_result(self, instance: People) -> Dict:
        """Format People instance to search result"""

        subtitle_parts = []
        if hasattr(instance, 'organizational') and instance.organizational:
            if instance.organizational.designation:
                subtitle_parts.append(instance.organizational.designation)
            if instance.organizational.department:
                subtitle_parts.append(instance.organizational.department)

        return {
            'id': str(instance.uuid),
            'title': instance.peoplename,
            'subtitle': ' | '.join(subtitle_parts) if subtitle_parts else instance.loginid,
            'snippet': f"Email: {instance.email}" if instance.email else '',
            'metadata': {
                'peoplecode': instance.peoplecode,
                'loginid': instance.loginid,
                'is_verified': instance.isverified,
                'is_admin': instance.isadmin,
            }
        }

    def get_actions(self, instance: People) -> List[Dict]:
        """Get available actions for People"""

        actions = [
            {
                'label': 'Open Profile',
                'href': f'/people/{instance.uuid}',
                'method': 'GET'
            }
        ]

        if self.user.has_perm('activity.assign_task'):
            actions.append({
                'label': 'Assign to Task',
                'href': f'/api/v1/tasks/assign',
                'method': 'POST',
                'payload': {'person_id': str(instance.uuid)}
            })

        if self.user.has_perm('peoples.change_people'):
            actions.append({
                'label': 'Edit',
                'href': f'/people/{instance.uuid}/edit',
                'method': 'GET'
            })

        return actions

    def get_search_fields(self) -> List[str]:
        """Return searchable fields for People"""
        return [
            'peoplename',
            'loginid',
            'email',
            'peoplecode',
            'organizational__designation',
            'organizational__department'
        ]