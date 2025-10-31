"""
Site Group Management Service

Handles all business logic for Site Group operations including:
- CRUD operations for site groups
- Site assignment management
- JSON parsing and validation
- Complex bulk operations
"""

from __future__ import annotations

import logging
from typing import Dict, Any, Optional, List
from dataclasses import dataclass

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models import QuerySet

from apps.core.services.base_service import BaseService
from apps.core.services import with_transaction, monitor_service_performance
from apps.core.error_handling import ErrorHandler
from apps.core.exceptions import UserManagementException, DatabaseException
from apps.core.utils_new.db_utils import get_current_db_name
import apps.peoples.utils as putils

logger = logging.getLogger(__name__)


@dataclass
class SiteGroupOperationResult:
    """Result structure for site group operations."""
    success: bool
    group: Optional[Pgroup] = None
    error_message: Optional[str] = None
    correlation_id: Optional[str] = None
    data: Optional[Dict[str, Any]] = None


class SiteGroupManagementService(BaseService):
    """
    Service for managing Site Group operations.

    Extracted from peoples/views.py SiteGroup view class.
    """

    def __init__(self):
        super().__init__()
        self.related_fields = ["identifier"]
        self.list_fields = ["groupname", "enable", "id"]

    @monitor_service_performance("get_site_group_list")
    def get_site_group_list(
        self,
        request_params: Dict[str, Any],
        session: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Get paginated list of site groups.

        Args:
            request_params: Request parameters
            session: User session data

        Returns:
            Dictionary with pagination data
        """
        from apps.peoples.models import Pgroup  # Late import to prevent circular dependency

        try:
            total, filtered, objs = Pgroup.objects.list_view_sitegrp(
                request_params, {'session': session}
            )

            return {
                "draw": request_params.get("draw"),
                "data": list(objs),
                "recordsFiltered": filtered,
                "recordsTotal": total
            }

        except DatabaseException as e:
            self.logger.error(f"Database error retrieving site groups: {str(e)}")
            raise

    @monitor_service_performance("create_site_group")
    @with_transaction()
    def create_site_group(
        self,
        form_data: Dict[str, Any],
        assigned_sites: List[Dict[str, Any]],
        user: Any,
        session: Dict[str, Any]
    ) -> SiteGroupOperationResult:
        """
        Create new site group with site assignments.

        Args:
            form_data: Form cleaned data
            assigned_sites: List of site dictionaries with buid
            user: Current user performing operation
            session: User session data

        Returns:
            SiteGroupOperationResult with created group
        """
        from apps.peoples.models import Pgroup  # Late import to prevent circular dependency

        try:
            with transaction.atomic(using=get_current_db_name()):
                group = Pgroup(**form_data)
                putils.save_userinfo(group, user, session)

                self._save_assigned_sites(group, assigned_sites, user, session)

                self.logger.info(f"Created site group: {group.groupname}")

                return SiteGroupOperationResult(
                    success=True,
                    group=group,
                    data={
                        "success": "Record has been saved successfully",
                        "pk": group.pk,
                        "row": {"id": group.id, "groupname": group.groupname, "enable": group.enable}
                    }
                )

        except IntegrityError as e:
            correlation_id = ErrorHandler.handle_exception(
                e,
                context={'operation': 'create_site_group'},
                level='error'
            )
            return SiteGroupOperationResult(
                success=False,
                error_message="Site group already exists or violates constraints",
                correlation_id=correlation_id
            )
        except ValidationError as e:
            correlation_id = ErrorHandler.handle_exception(
                e,
                context={'operation': 'create_site_group_validation'},
                level='warning'
            )
            return SiteGroupOperationResult(
                success=False,
                error_message="Invalid site group data provided",
                correlation_id=correlation_id
            )

    @monitor_service_performance("update_site_group")
    @with_transaction()
    def update_site_group(
        self,
        group_id: int,
        form_data: Dict[str, Any],
        assigned_sites: List[Dict[str, Any]],
        user: Any,
        session: Dict[str, Any]
    ) -> SiteGroupOperationResult:
        """
        Update existing site group and assignments.

        Args:
            group_id: ID of group to update
            form_data: Form cleaned data
            assigned_sites: List of site dictionaries
            user: Current user performing operation
            session: User session data

        Returns:
            SiteGroupOperationResult with updated group
        """
        from apps.peoples.models import Pgroup  # Late import to prevent circular dependency

        try:
            with transaction.atomic(using=get_current_db_name()):
                group = Pgroup.objects.get(id=group_id)

                for field, value in form_data.items():
                    setattr(group, field, value)

                putils.save_userinfo(group, user, session)

                self._reset_assigned_sites(group)
                self._save_assigned_sites(group, assigned_sites, user, session)

                self.logger.info(f"Updated site group: {group.groupname}")

                return SiteGroupOperationResult(
                    success=True,
                    group=group,
                    data={
                        "success": "Record has been updated successfully",
                        "pk": group.pk,
                        "row": {"id": group.id, "groupname": group.groupname, "enable": group.enable}
                    }
                )

        except Pgroup.DoesNotExist as e:
            correlation_id = ErrorHandler.handle_exception(
                e,
                context={'operation': 'update_site_group', 'group_id': group_id},
                level='warning'
            )
            return SiteGroupOperationResult(
                success=False,
                error_message="Site group not found",
                correlation_id=correlation_id
            )
        except IntegrityError as e:
            correlation_id = ErrorHandler.handle_exception(
                e,
                context={'operation': 'update_site_group'},
                level='error'
            )
            return SiteGroupOperationResult(
                success=False,
                error_message="Update violates data constraints",
                correlation_id=correlation_id
            )

    def _reset_assigned_sites(self, group: Pgroup) -> None:
        """Remove all existing site assignments for group."""
        from apps.peoples.models import Pgbelonging  # Late import to prevent circular dependency
        Pgbelonging.objects.filter(pgroup_id=group.id).delete()

    def _save_assigned_sites(
        self,
        group: Pgroup,
        sites_array: List[Dict[str, Any]],
        user: Any,
        session: Dict[str, Any]
    ) -> None:
        """
        Save site assignments atomically.

        Args:
            group: Group instance
            sites_array: List of site dictionaries
            user: Current user
            session: User session data
        """
        from apps.peoples.models import Pgbelonging  # Late import to prevent circular dependency

        for site in sites_array:
            belonging = Pgbelonging(
                pgroup=group,
                people_id=1,
                assignsites_id=site.get("buid"),
                client_id=session.get("client_id"),
                bu_id=session.get("bu_id"),
                tenant_id=session.get("tenantid", 1)
            )
            putils.save_userinfo(belonging, user, session)

    @monitor_service_performance("get_assigned_sites")
    def get_assigned_sites(
        self,
        group_id: int
    ) -> List[Dict[str, Any]]:
        """
        Get list of sites assigned to a site group.

        Args:
            group_id: ID of site group

        Returns:
            List of assigned site data
        """
        from apps.peoples.models import Pgbelonging  # Late import to prevent circular dependency

        return list(
            Pgbelonging.objects.get_assigned_sitesto_sitegrp(group_id)
        )

    @monitor_service_performance("get_site_group")
    def get_site_group(
        self,
        group_id: int
    ) -> Optional[Pgroup]:
        """
        Retrieve site group by ID.

        Args:
            group_id: ID of site group to retrieve

        Returns:
            Pgroup instance or None
        """
        from apps.peoples.models import Pgroup  # Late import to prevent circular dependency

        try:
            return Pgroup.objects.select_related(
                *self.related_fields
            ).get(id=group_id)
        except Pgroup.DoesNotExist:
            self.logger.warning(f"Site group not found: {group_id}")
            return None

    @monitor_service_performance("delete_site_group")
    @with_transaction()
    def delete_site_group(
        self,
        group_id: int,
        user: Any,
        session: Dict[str, Any]
    ) -> SiteGroupOperationResult:
        """
        Delete site group and all assignments.

        Args:
            group_id: ID of group to delete
            user: Current user performing operation
            session: User session data

        Returns:
            SiteGroupOperationResult with deletion status
        """
        from apps.peoples.models import Pgroup, Pgbelonging  # Late import to prevent circular dependency

        try:
            group = Pgroup.objects.get(id=group_id)
            groupname = group.groupname

            Pgbelonging.objects.filter(pgroup_id=group_id).delete()
            group.delete()

            self.logger.info(
                f"Deleted site group: {groupname}",
                extra={'user': user.id if user else None}
            )

            return SiteGroupOperationResult(
                success=True,
                data={"id": group_id}
            )

        except Pgroup.DoesNotExist as e:
            correlation_id = ErrorHandler.handle_exception(
                e,
                context={'operation': 'delete_site_group', 'group_id': group_id},
                level='warning'
            )
            return SiteGroupOperationResult(
                success=False,
                error_message="Site group not found",
                correlation_id=correlation_id
            )

    def get_service_name(self) -> str:
        """Return service name for monitoring."""
        return "SiteGroupManagementService"