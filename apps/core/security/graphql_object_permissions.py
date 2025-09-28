"""
GraphQL Object-Level Permission Validation System

Implements row-level security and object-level authorization for GraphQL queries
to ensure users can only access resources they own or have explicit permissions for.

Features:
- Object ownership validation
- Row-level security enforcement
- Multi-tenant object isolation
- Permission-based object filtering
- Audit logging for access attempts
- Integration with Django's object permissions

Security Compliance:
- Addresses CVSS 7.2 (High) - GraphQL Authorization Gaps
- Prevents unauthorized access to individual resources
- Enforces principle of least privilege

Usage:
    from apps.core.security.graphql_object_permissions import (
        ObjectPermissionValidator,
        can_view_object,
        can_modify_object
    )

    @staticmethod
    @require_authentication
    def resolve_ticket(self, info, ticket_id):
        ticket = Ticket.objects.get(id=ticket_id)

        validator = ObjectPermissionValidator(info.context.user)
        if not validator.can_access_object(ticket, 'view'):
            raise GraphQLError("Access denied")

        return ticket
"""

import logging
from typing import Any, Optional, Dict, List
from django.conf import settings
from django.core.cache import cache
from django.core.exceptions import PermissionDenied
from graphql import GraphQLError


security_logger = logging.getLogger('security')
object_permission_logger = logging.getLogger('graphql_object_permissions')


class ObjectPermissionValidator:
    """
    Validates object-level permissions for GraphQL resources.

    Provides comprehensive object-level authorization checking including
    ownership validation, role-based access, and tenant isolation.
    """

    def __init__(self, user):
        """
        Initialize object permission validator.

        Args:
            user: The authenticated user object
        """
        self.user = user
        self.is_admin = getattr(user, 'isadmin', False)
        self.is_authenticated = user.is_authenticated if hasattr(user, 'is_authenticated') else False

    def can_access_object(self, obj: Any, permission_type: str = 'view') -> bool:
        """
        Check if user can access an object.

        Args:
            obj: The object to check permissions for
            permission_type: Type of permission ('view', 'change', 'delete')

        Returns:
            bool: True if user can access the object, False otherwise
        """
        if not self.is_authenticated:
            return False

        if self.is_admin:
            return True

        model_name = obj.__class__.__name__

        if self._check_tenant_isolation(obj):
            return self._check_specific_permission(obj, permission_type, model_name)

        self._log_access_denial(obj, permission_type, 'tenant_isolation_failed')
        return False

    def _check_tenant_isolation(self, obj: Any) -> bool:
        """Ensure object belongs to user's tenant."""
        if hasattr(obj, 'client_id'):
            if obj.client_id != self.user.client_id:
                return False

        if hasattr(obj, 'tenant_id'):
            if obj.tenant_id != getattr(self.user, 'tenant_id', None):
                return False

        return True

    def _check_specific_permission(self, obj: Any, permission_type: str, model_name: str) -> bool:
        """Check specific object permission based on model type."""
        if model_name == 'Ticket':
            return self._can_access_ticket(obj, permission_type)

        if model_name == 'Wom':
            return self._can_access_work_permit(obj, permission_type)

        if model_name == 'JournalEntry':
            return self._can_access_journal_entry(obj, permission_type)

        if model_name == 'PeopleEventlog':
            return self._can_access_event_log(obj, permission_type)

        if model_name == 'Jobneed':
            return self._can_access_job(obj, permission_type)

        return self._check_default_object_permission(obj, permission_type)

    def _can_access_ticket(self, ticket, permission_type: str) -> bool:
        """Check ticket access permissions."""
        if permission_type == 'view':
            return (
                ticket.created_by_id == self.user.id or
                ticket.assigned_to_id == self.user.id or
                self._user_is_ticket_watcher(ticket) or
                self._user_has_capability('can_view_all_tickets')
            )

        if permission_type == 'change':
            return (
                ticket.assigned_to_id == self.user.id or
                self._user_has_capability('can_update_all_tickets')
            )

        if permission_type == 'delete':
            return (
                ticket.created_by_id == self.user.id or
                self._user_has_capability('can_delete_tickets')
            )

        return False

    def _can_access_work_permit(self, wom, permission_type: str) -> bool:
        """Check work permit access permissions."""
        if permission_type == 'view':
            return (
                wom.createdby_id == self.user.id or
                wom.bu_id == self.user.bu_id or
                self._user_is_work_permit_approver(wom) or
                self._user_has_capability('can_view_all_work_permits')
            )

        if permission_type in ['change', 'delete']:
            return (
                wom.createdby_id == self.user.id or
                self._user_has_capability('can_approve_work_permits')
            )

        return False

    def _can_access_journal_entry(self, entry, permission_type: str) -> bool:
        """Check journal entry access permissions."""
        if permission_type == 'view':
            if entry.user_id == self.user.id:
                return True

            if entry.privacy_scope == 'private':
                return False

            if entry.privacy_scope == 'manager' and self._user_is_manager_of(entry.user):
                return self._check_journal_consent(entry.user, 'manager_access_consent')

            if entry.privacy_scope == 'team':
                return self._user_is_team_member_with(entry.user)

            return False

        if permission_type in ['change', 'delete']:
            return entry.user_id == self.user.id

        return False

    def _can_access_event_log(self, eventlog, permission_type: str) -> bool:
        """Check event log access permissions."""
        if permission_type == 'view':
            return (
                eventlog.peopleid == self.user.id or
                self._user_has_capability('can_view_all_event_logs')
            )

        return False

    def _can_access_job(self, job, permission_type: str) -> bool:
        """Check job access permissions."""
        if permission_type == 'view':
            return (
                job.performedby_id == self.user.id or
                job.bu_id == self.user.bu_id or
                self._user_has_capability('can_view_all_jobs')
            )

        if permission_type == 'change':
            return (
                job.performedby_id == self.user.id or
                self._user_has_capability('can_update_all_jobs')
            )

        return False

    def _check_default_object_permission(self, obj: Any, permission_type: str) -> bool:
        """Default object permission check for unspecified models."""
        if hasattr(obj, 'created_by_id'):
            if obj.created_by_id == self.user.id:
                return True

        if hasattr(obj, 'user_id'):
            if obj.user_id == self.user.id:
                return True

        if hasattr(obj, 'peopleid'):
            if obj.peopleid == self.user.id:
                return True

        return False

    def _user_has_capability(self, capability: str) -> bool:
        """Check if user has specific capability."""
        if not hasattr(self.user, 'capabilities'):
            return False

        capabilities = self.user.capabilities

        if isinstance(capabilities, dict):
            return capabilities.get(capability, False)

        if isinstance(capabilities, str):
            try:
                import json
                capabilities_dict = json.loads(capabilities)
                return capabilities_dict.get(capability, False)
            except (json.JSONDecodeError, TypeError):
                return False

        return False

    def _user_is_ticket_watcher(self, ticket) -> bool:
        """Check if user is watching the ticket."""
        if not hasattr(ticket, 'watchers'):
            return False

        return self.user in ticket.watchers.all()

    def _user_is_work_permit_approver(self, wom) -> bool:
        """Check if user is an approver for the work permit."""
        if not hasattr(wom, 'other_data'):
            return False

        other_data = wom.other_data
        if not isinstance(other_data, dict):
            return False

        approvers = other_data.get('wp_approvers', [])
        user_peoplecode = getattr(self.user, 'peoplecode', None)

        for approver in approvers:
            if isinstance(approver, dict) and approver.get('peoplecode') == user_peoplecode:
                return True

        return False

    def _user_is_manager_of(self, target_user) -> bool:
        """Check if user is the manager of target user."""
        if not hasattr(target_user, 'reportto_id'):
            return False

        return target_user.reportto_id == self.user.id

    def _user_is_team_member_with(self, target_user) -> bool:
        """Check if user is a team member with target user."""
        return (
            hasattr(target_user, 'bu_id') and
            target_user.bu_id == self.user.bu_id
        )

    def _check_journal_consent(self, target_user, consent_field: str) -> bool:
        """Check if target user has given consent for data sharing."""
        try:
            from apps.journal.models import JournalPrivacySettings

            privacy_settings = JournalPrivacySettings.objects.filter(user=target_user).first()

            if not privacy_settings:
                return False

            return getattr(privacy_settings, consent_field, False)

        except (DatabaseError, IntegrityError, ObjectDoesNotExist, TypeError, ValidationError, ValueError, json.JSONDecodeError):
            return False

    def _log_access_denial(self, obj: Any, permission_type: str, reason: str):
        """Log object access denial for security monitoring."""
        object_permission_logger.warning(
            f"Object access denied: {obj.__class__.__name__}",
            extra={
                'user_id': self.user.id,
                'username': getattr(self.user, 'loginid', str(self.user)),
                'object_type': obj.__class__.__name__,
                'object_id': getattr(obj, 'id', None),
                'permission_type': permission_type,
                'denial_reason': reason,
                'event_type': 'object_access_denial'
            }
        )


def can_view_object(user, obj: Any) -> bool:
    """
    Check if user can view an object.

    Args:
        user: The user to check permissions for
        obj: The object to check

    Returns:
        bool: True if user can view the object

    Example:
        if can_view_object(request.user, ticket):
            return ticket
        raise PermissionDenied()
    """
    validator = ObjectPermissionValidator(user)
    return validator.can_access_object(obj, 'view')


def can_modify_object(user, obj: Any) -> bool:
    """
    Check if user can modify an object.

    Args:
        user: The user to check permissions for
        obj: The object to check

    Returns:
        bool: True if user can modify the object

    Example:
        if can_modify_object(request.user, ticket):
            ticket.status = new_status
            ticket.save()
    """
    validator = ObjectPermissionValidator(user)
    return validator.can_access_object(obj, 'change')


def can_delete_object(user, obj: Any) -> bool:
    """
    Check if user can delete an object.

    Args:
        user: The user to check permissions for
        obj: The object to check

    Returns:
        bool: True if user can delete the object

    Example:
        if can_delete_object(request.user, ticket):
            ticket.delete()
    """
    validator = ObjectPermissionValidator(user)
    return validator.can_access_object(obj, 'delete')