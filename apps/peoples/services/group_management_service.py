"""
Group Management Service

Handles all business logic for People Group (Pgroup) operations including:
- CRUD operations for people groups
- Group membership management (Pgbelonging)
- Atomic transaction handling
"""

import logging
from typing import Dict, Any, Optional, List
from dataclasses import dataclass

from django.core.exceptions import ValidationError, PermissionDenied
from django.db import IntegrityError, transaction
from django.db.models import Q, QuerySet

from apps.core.services.base_service import BaseService
from apps.core.services import with_transaction
from apps.core.error_handling import ErrorHandler
from apps.core.exceptions import UserManagementException, DatabaseException
from apps.peoples.models import Pgroup, Pgbelonging
import apps.peoples.utils as putils

logger = logging.getLogger(__name__)


@dataclass
class GroupOperationResult:
    """Result structure for group operations."""
    success: bool
    group: Optional[Pgroup] = None
    error_message: Optional[str] = None
    correlation_id: Optional[str] = None
    data: Optional[Dict[str, Any]] = None


class GroupManagementService(BaseService):
    """
    Service for managing Pgroup and Pgbelonging operations.

    Extracted from peoples/views.py PeopleGroup view class.
    """

    def __init__(self):
        super().__init__()
        self.related_fields = ["identifier", "bu"]
        self.list_fields = ["groupname", "enable", "id", "bu__buname", "bu__bucode"]

    @BaseService.monitor_performance("get_group_list")
    def get_group_list(
        self,
        session: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Get list of people groups for user's bu/client.

        Args:
            session: User session data

        Returns:
            List of group dictionaries
        """
        try:
            queryset = Pgroup.objects.select_related(
                *self.related_fields
            ).filter(
                ~Q(id=-1),
                bu_id=session.get("bu_id"),
                identifier__tacode="PEOPLEGROUP",
                client_id=session.get("client_id")
            ).values(*self.list_fields).order_by("-mdtz")

            return list(queryset)

        except DatabaseException as e:
            self.logger.error(f"Database error retrieving groups: {str(e)}")
            raise

    @BaseService.monitor_performance("create_group")
    @with_transaction()
    def create_group(
        self,
        form_data: Dict[str, Any],
        people_ids: List[int],
        user: Any,
        session: Dict[str, Any]
    ) -> GroupOperationResult:
        """
        Create new people group with members.

        Args:
            form_data: Form cleaned data
            people_ids: List of people IDs to add to group
            user: Current user performing operation
            session: User session data

        Returns:
            GroupOperationResult with created group
        """
        try:
            group = Pgroup(**form_data)
            putils.save_userinfo(group, user, session, create=True)

            self._save_group_memberships(group, people_ids, user, session)

            self.logger.info(f"Created people group: {group.groupname}")

            return GroupOperationResult(
                success=True,
                group=group,
                data={
                    "row": Pgroup.objects.values(
                        *self.list_fields
                    ).get(id=group.id)
                }
            )

        except IntegrityError as e:
            correlation_id = ErrorHandler.handle_exception(
                e,
                context={'operation': 'create_group'},
                level='error'
            )
            return GroupOperationResult(
                success=False,
                error_message="Group already exists or violates constraints",
                correlation_id=correlation_id
            )
        except ValidationError as e:
            correlation_id = ErrorHandler.handle_exception(
                e,
                context={'operation': 'create_group_validation'},
                level='warning'
            )
            return GroupOperationResult(
                success=False,
                error_message="Invalid group data provided",
                correlation_id=correlation_id
            )

    @BaseService.monitor_performance("update_group")
    @with_transaction()
    def update_group(
        self,
        group_id: int,
        form_data: Dict[str, Any],
        people_ids: List[int],
        user: Any,
        session: Dict[str, Any]
    ) -> GroupOperationResult:
        """
        Update existing people group and memberships.

        Args:
            group_id: ID of group to update
            form_data: Form cleaned data
            people_ids: List of people IDs for group
            user: Current user performing operation
            session: User session data

        Returns:
            GroupOperationResult with updated group
        """
        try:
            group = Pgroup.objects.get(id=group_id)

            Pgbelonging.objects.filter(pgroup_id=group_id).delete()

            for field, value in form_data.items():
                setattr(group, field, value)

            putils.save_userinfo(group, user, session, create=False)

            self._save_group_memberships(group, people_ids, user, session)

            self.logger.info(f"Updated people group: {group.groupname}")

            return GroupOperationResult(
                success=True,
                group=group,
                data={
                    "row": Pgroup.objects.values(
                        *self.list_fields
                    ).get(id=group.id)
                }
            )

        except Pgroup.DoesNotExist as e:
            correlation_id = ErrorHandler.handle_exception(
                e,
                context={'operation': 'update_group', 'group_id': group_id},
                level='warning'
            )
            return GroupOperationResult(
                success=False,
                error_message="Group not found",
                correlation_id=correlation_id
            )
        except IntegrityError as e:
            correlation_id = ErrorHandler.handle_exception(
                e,
                context={'operation': 'update_group'},
                level='error'
            )
            return GroupOperationResult(
                success=False,
                error_message="Update violates data constraints",
                correlation_id=correlation_id
            )

    def _save_group_memberships(
        self,
        group: Pgroup,
        people_ids: List[int],
        user: Any,
        session: Dict[str, Any]
    ) -> None:
        """
        Save group memberships atomically.

        Args:
            group: Group instance
            people_ids: List of people IDs
            user: Current user
            session: User session data
        """
        for people_id in people_ids:
            belonging = Pgbelonging(
                pgroup=group,
                people_id=people_id,
                client_id=session.get("client_id"),
                bu_id=session.get("bu_id"),
                tenant_id=session.get("tenantid", 1)
            )
            putils.save_userinfo(belonging, user, session)

    @BaseService.monitor_performance("get_group")
    def get_group(
        self,
        group_id: int
    ) -> Optional[Pgroup]:
        """
        Retrieve group by ID with relationships.

        Args:
            group_id: ID of group to retrieve

        Returns:
            Pgroup instance or None
        """
        try:
            return Pgroup.objects.select_related(
                *self.related_fields
            ).get(id=group_id)
        except Pgroup.DoesNotExist:
            self.logger.warning(f"Group not found: {group_id}")
            return None

    @BaseService.monitor_performance("get_group_members")
    def get_group_members(
        self,
        group_id: int
    ) -> List[int]:
        """
        Get list of people IDs belonging to a group.

        Args:
            group_id: ID of group

        Returns:
            List of people IDs
        """
        return list(
            Pgbelonging.objects.filter(
                pgroup_id=group_id
            ).values_list("people_id", flat=True)
        )

    @BaseService.monitor_performance("delete_group")
    @with_transaction()
    def delete_group(
        self,
        group_id: int,
        user: Any,
        session: Dict[str, Any]
    ) -> GroupOperationResult:
        """
        Delete group and all memberships.

        Args:
            group_id: ID of group to delete
            user: Current user performing operation
            session: User session data

        Returns:
            GroupOperationResult with deletion status
        """
        try:
            group = Pgroup.objects.get(id=group_id)
            groupname = group.groupname

            Pgbelonging.objects.filter(pgroup_id=group_id).delete()
            group.delete()

            self.logger.info(
                f"Deleted group: {groupname}",
                extra={'user': user.id if user else None}
            )

            return GroupOperationResult(
                success=True,
                data={"id": group_id}
            )

        except Pgroup.DoesNotExist as e:
            correlation_id = ErrorHandler.handle_exception(
                e,
                context={'operation': 'delete_group', 'group_id': group_id},
                level='warning'
            )
            return GroupOperationResult(
                success=False,
                error_message="Group not found",
                correlation_id=correlation_id
            )

    def get_service_name(self) -> str:
        """Return service name for monitoring."""
        return "GroupManagementService"