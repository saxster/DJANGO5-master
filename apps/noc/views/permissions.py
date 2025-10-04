"""
NOC Custom DRF Permissions.

Custom permission classes for NOC API endpoints.
Follows .claude/rules.md Rule #7 (<150 lines).
"""

import logging
from rest_framework import permissions
from apps.noc.services import NOCRBACService

__all__ = [
    'HasNOCViewPermission',
    'CanAcknowledgeAlerts',
    'CanEscalateAlerts',
    'CanManageMaintenance',
    'CanExportData',
    'CanViewAuditLogs',
]

logger = logging.getLogger('noc.permissions')


class HasNOCViewPermission(permissions.BasePermission):
    """Permission to view NOC dashboard and data."""

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False

        return request.user.has_capability('noc:view')


class CanAcknowledgeAlerts(permissions.BasePermission):
    """Permission to acknowledge alerts."""

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False

        return NOCRBACService.can_acknowledge_alerts(request.user)


class CanEscalateAlerts(permissions.BasePermission):
    """Permission to escalate alerts."""

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False

        return NOCRBACService.can_escalate_alerts(request.user)


class CanManageMaintenance(permissions.BasePermission):
    """Permission to manage maintenance windows."""

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False

        return NOCRBACService.can_manage_maintenance(request.user)


class CanExportData(permissions.BasePermission):
    """Permission to export NOC data."""

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False

        return NOCRBACService.can_export_data(request.user)


class CanViewAuditLogs(permissions.BasePermission):
    """Permission to view audit logs."""

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False

        return NOCRBACService.can_view_audit_logs(request.user)