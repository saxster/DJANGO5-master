"""
Performance Analytics Custom DRF Permissions.

Custom permission classes for performance analytics API endpoints.
"""

import logging
from rest_framework import permissions

__all__ = ['IsSupervisorOrAdmin']

logger = logging.getLogger('performance_analytics.permissions')


class IsSupervisorOrAdmin(permissions.BasePermission):
    """Permission for supervisors and admins to view team performance."""

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False

        return (
            request.user.is_superuser or
            request.user.is_staff or
            hasattr(request.user, 'peopleorganizational') and
            request.user.peopleorganizational.designation in ['Supervisor', 'Manager', 'Admin']
        )
