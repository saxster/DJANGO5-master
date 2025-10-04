"""
NOC RBAC Service.

Role-based access control for NOC dashboard and operations.
Follows .claude/rules.md Rule #7 (<150 lines), Rule #12 (query optimization).
"""

import logging
from typing import List
from django.db.models import QuerySet
from apps.peoples.services import UserCapabilityService
from ..constants import NOC_CAPABILITIES

__all__ = ['NOCRBACService']

logger = logging.getLogger('noc.rbac')


class NOCRBACService:
    """Service for NOC permission checking and filtering."""

    @staticmethod
    def get_visible_clients(user) -> QuerySet:
        """
        Get clients visible to user based on NOC capabilities.

        Permission hierarchy:
        - noc:view_all_clients: See all clients in tenant
        - noc:view_client: See assigned client
        - noc:view_assigned_sites: See only assigned sites' clients
        - Default: No access

        Args:
            user: People instance

        Returns:
            QuerySet of Bt instances (clients)
        """
        from apps.onboarding.models import Bt
        from apps.onboarding.managers import BtManager

        capabilities = UserCapabilityService.get_effective_permissions(user)

        if 'noc:view_all_clients' in capabilities or user.isadmin:
            return Bt.objects.filter(
                tenant=user.tenant,
                identifier__tacode='CLIENT'
            ).select_related('tenant', 'identifier')

        if 'noc:view_client' in capabilities:
            if hasattr(user, 'peopleorganizational') and user.peopleorganizational.client:
                client = user.peopleorganizational.client.get_client_parent()
                return Bt.objects.filter(id=client.id).select_related('tenant', 'identifier')

        if 'noc:view_assigned_sites' in capabilities:
            sites = BtManager().get_sitelist_web(user.peopleorganizational.client.id, user.id)
            client_ids = set(site.get_client_parent().id for site in sites if site.get_client_parent())
            return Bt.objects.filter(id__in=client_ids).select_related('tenant', 'identifier')

        return Bt.objects.none()

    @staticmethod
    def filter_sites_by_permission(user, sites: QuerySet) -> QuerySet:
        """
        Filter sites based on user permissions.

        Args:
            user: People instance
            sites: QuerySet of Bt instances (sites)

        Returns:
            Filtered QuerySet of sites user can access
        """
        from apps.onboarding.managers import BtManager

        capabilities = UserCapabilityService.get_effective_permissions(user)

        if 'noc:view_all_clients' in capabilities or user.isadmin:
            return sites

        if 'noc:view_assigned_sites' in capabilities:
            if hasattr(user, 'peopleorganizational') and user.peopleorganizational.client:
                accessible_sites = BtManager().get_sitelist_web(
                    user.peopleorganizational.client.id,
                    user.id
                )
                accessible_ids = [s.id for s in accessible_sites]
                return sites.filter(id__in=accessible_ids)

        return sites.none()

    @staticmethod
    def can_acknowledge_alerts(user) -> bool:
        """Check if user can acknowledge alerts."""
        capabilities = UserCapabilityService.get_effective_permissions(user)
        return 'noc:ack_alerts' in capabilities or user.isadmin

    @staticmethod
    def can_escalate_alerts(user) -> bool:
        """Check if user can escalate alerts."""
        capabilities = UserCapabilityService.get_effective_permissions(user)
        return 'noc:escalate' in capabilities or user.isadmin

    @staticmethod
    def can_manage_maintenance(user) -> bool:
        """Check if user can manage maintenance windows."""
        capabilities = UserCapabilityService.get_effective_permissions(user)
        return 'noc:manage_maintenance' in capabilities or user.isadmin

    @staticmethod
    def can_export_data(user) -> bool:
        """Check if user can export NOC data."""
        capabilities = UserCapabilityService.get_effective_permissions(user)
        return 'noc:export' in capabilities or user.isadmin

    @staticmethod
    def can_view_pii(user) -> bool:
        """Check if user can view PII data in alerts."""
        capabilities = UserCapabilityService.get_effective_permissions(user)
        return (
            'noc:view_pii' in capabilities or
            'noc:view_all_clients' in capabilities or
            user.isadmin
        )

    @staticmethod
    def can_configure_alerts(user) -> bool:
        """Check if user can configure alert rules and thresholds."""
        capabilities = UserCapabilityService.get_effective_permissions(user)
        return 'noc:configure' in capabilities or user.isadmin

    @staticmethod
    def can_assign_incidents(user) -> bool:
        """Check if user can assign incidents to others."""
        capabilities = UserCapabilityService.get_effective_permissions(user)
        return 'noc:assign_incidents' in capabilities or user.isadmin

    @staticmethod
    def can_view_audit_logs(user) -> bool:
        """Check if user can view NOC audit logs."""
        capabilities = UserCapabilityService.get_effective_permissions(user)
        return 'noc:audit_view' in capabilities or user.isadmin

    @staticmethod
    def get_accessible_alert_types(user) -> list:
        """
        Get list of alert types accessible to user.

        Args:
            user: People instance

        Returns:
            list: Alert type codes accessible to user
        """
        from ..constants import ALERT_TYPES

        if user.isadmin or user.has_capability('noc:view_all_clients'):
            return list(ALERT_TYPES.keys())

        allowed_types = [
            'SLA_BREACH',
            'TICKET_ESCALATED',
            'WORK_ORDER_OVERDUE',
        ]

        if user.has_capability('noc:view_client'):
            allowed_types.extend([
                'DEVICE_OFFLINE',
                'ATTENDANCE_MISSING',
                'SYNC_DEGRADED',
            ])

        return allowed_types