"""
REST API ViewSets with Tenant Isolation

Provides secure REST API endpoints with automatic tenant filtering and pagination.

Security Features:
- Tenant isolation enforced on all viewsets
- Pagination to prevent resource exhaustion
- Query optimization to prevent N+1 queries
- Permission-based access control

Refactored: 2025-10-01
Compliance: Addresses CRITICAL tenant isolation vulnerability
"""

from rest_framework import viewsets
from apps.service.rest_service import serializers as ytpl_serializers
from apps.service.rest_service.mixins import TenantFilteredViewSetMixin
from apps.peoples import models as people_models
from apps.onboarding import models as ob_models
from apps.activity import models as act_models
from apps.attendance.models import PeopleEventlog

# Add Job and Jobneed to act_models namespace (they're in job_model submodule)
from apps.activity.models.job_model import Job, Jobneed
act_models.Job = Job
act_models.Jobneed = Jobneed


class PeopleViewset(TenantFilteredViewSetMixin, viewsets.ReadOnlyModelViewSet):
    """
    API endpoint for People (users) data.

    Endpoint: /api/rest/people/
    Methods: GET (list), GET (detail)
    Security: Tenant-filtered, paginated
    """
    queryset = people_models.People.objects.all()
    serializer_class = ytpl_serializers.PeopleSerializer

    def _get_related_fields(self):
        """Optimize queries by pre-fetching related models."""
        return ['bu', 'client', 'department']


class PELViewset(TenantFilteredViewSetMixin, viewsets.ReadOnlyModelViewSet):
    """
    API endpoint for People Event Logs (attendance/location events).

    Endpoint: /api/rest/event-logs/
    Methods: GET (list), GET (detail)
    Security: Tenant-filtered, paginated
    """
    queryset = PeopleEventlog.objects.all()
    serializer_class = ytpl_serializers.PeopleEventLogSerializer

    def _get_related_fields(self):
        """Optimize queries by pre-fetching related models."""
        return ['peopleid', 'peopleid__client', 'peopleid__bu']


class PgroupViewset(TenantFilteredViewSetMixin, viewsets.ReadOnlyModelViewSet):
    """
    API endpoint for People Groups (organizational groups/teams).

    Endpoint: /api/rest/groups/
    Methods: GET (list), GET (detail)
    Security: Tenant-filtered, paginated
    """
    queryset = people_models.Pgroup.objects.all()
    serializer_class = ytpl_serializers.PgroupSerializer

    def _get_related_fields(self):
        """Optimize queries by pre-fetching related models."""
        return ['bu']


class BtViewset(TenantFilteredViewSetMixin, viewsets.ReadOnlyModelViewSet):
    """
    API endpoint for Business Units (sites/locations).

    Endpoint: /api/rest/business-units/
    Methods: GET (list), GET (detail)
    Security: Tenant-filtered, paginated
    """
    queryset = ob_models.Bt.objects.all()
    serializer_class = ytpl_serializers.BtSerializer

    def _get_related_fields(self):
        """Optimize queries by pre-fetching related models."""
        return ['clientid']


class ShiftViewset(TenantFilteredViewSetMixin, viewsets.ReadOnlyModelViewSet):
    """
    API endpoint for Shifts (work schedules).

    Endpoint: /api/rest/shifts/
    Methods: GET (list), GET (detail)
    Security: Tenant-filtered, paginated
    """
    queryset = ob_models.Shift.objects.all()
    serializer_class = ytpl_serializers.ShiftSerializer

    def _get_related_fields(self):
        """Optimize queries by pre-fetching related models."""
        return ['bu']


class TypeAssistViewset(TenantFilteredViewSetMixin, viewsets.ReadOnlyModelViewSet):
    """
    API endpoint for Type Assistance (lookup data, reference codes).

    Endpoint: /api/rest/type-assist/
    Methods: GET (list), GET (detail)
    Security: Tenant-filtered, paginated
    """
    queryset = ob_models.TypeAssist.objects.all()
    serializer_class = ytpl_serializers.TypeAssistSerializer

    def _get_related_fields(self):
        """Optimize queries by pre-fetching related models."""
        # TypeAssist is typically a lookup table without many relations
        return []


class PgbelongingViewset(TenantFilteredViewSetMixin, viewsets.ReadOnlyModelViewSet):
    """
    API endpoint for People Group Belongings (user-group associations).

    Endpoint: /api/rest/group-memberships/
    Methods: GET (list), GET (detail)
    Security: Tenant-filtered, paginated
    """
    queryset = people_models.Pgbelonging.objects.all()
    serializer_class = ytpl_serializers.PgbelongingSerializer

    def _get_related_fields(self):
        """Optimize queries by pre-fetching related models."""
        return ['peopleid', 'pgroupid', 'buid']


class JobViewset(TenantFilteredViewSetMixin, viewsets.ReadOnlyModelViewSet):
    """
    API endpoint for Jobs (tasks/work orders).

    Endpoint: /api/rest/jobs/
    Methods: GET (list), GET (detail)
    Security: Tenant-filtered, paginated
    """
    queryset = act_models.Job.objects.all()
    serializer_class = ytpl_serializers.JobSerializer

    def _get_related_fields(self):
        """Optimize queries by pre-fetching related models."""
        return [
            'locn',
            'clientid',
            'bu',
            'assetcode',
            'createdby',
            'assignedto'
        ]


class JobneedViewset(TenantFilteredViewSetMixin, viewsets.ReadOnlyModelViewSet):
    """
    API endpoint for Job Needs (task requirements/checklist items).

    Endpoint: /api/rest/job-needs/
    Methods: GET (list), GET (detail)
    Security: Tenant-filtered, paginated
    """
    queryset = act_models.Jobneed.objects.all()
    serializer_class = ytpl_serializers.JobneedSerializer

    def _get_related_fields(self):
        """Optimize queries by pre-fetching related models."""
        return ['jobcode', 'questioncode']


# Export all viewsets for URL registration
__all__ = [
    'PeopleViewset',
    'PELViewset',
    'PgroupViewset',
    'BtViewset',
    'ShiftViewset',
    'TypeAssistViewset',
    'PgbelongingViewset',
    'JobViewset',
    'JobneedViewset',
]
