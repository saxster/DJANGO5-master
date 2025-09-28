"""
Capability Management Service

Handles all business logic for Capability model operations including:
- CRUD operations for capabilities
- Parent-child relationship management
- Capability validation
- Search and filtering
"""

import logging
from typing import Dict, Any, Optional, List
from dataclasses import dataclass

from django.core.exceptions import ValidationError, PermissionDenied
from django.db import IntegrityError
from django.db.models import Q, QuerySet

from apps.core.services.base_service import BaseService
from apps.core.services import with_transaction
from apps.core.error_handling import ErrorHandler
from apps.core.exceptions import UserManagementException, DatabaseException
from apps.peoples.models import Capability
import apps.peoples.utils as putils

logger = logging.getLogger(__name__)


@dataclass
class CapabilityOperationResult:
    """Result structure for capability operations."""
    success: bool
    capability: Optional[Capability] = None
    error_message: Optional[str] = None
    correlation_id: Optional[str] = None
    data: Optional[Dict[str, Any]] = None


class CapabilityManagementService(BaseService):
    """
    Service for managing Capability model operations.

    Extracted from peoples/views.py Capability view class.
    """

    def __init__(self):
        super().__init__()
        self.related_fields = ["parent"]
        self.list_fields = ["id", "capscode", "capsname", "cfor", "parent__capscode"]

    @BaseService.monitor_performance("get_capability_list")
    def get_capability_list(
        self,
        session: Dict[str, Any],
        exclude_none: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Get list of all capabilities with proper relationships.

        Args:
            session: User session data
            exclude_none: Whether to exclude NONE capability

        Returns:
            List of capability dictionaries
        """
        try:
            queryset = Capability.objects.select_related(
                *self.related_fields
            )

            if exclude_none:
                queryset = queryset.filter(~Q(capscode="NONE"))

            return list(queryset.values(*self.list_fields))

        except DatabaseException as e:
            self.logger.error(f"Database error retrieving capabilities: {str(e)}")
            raise

    @BaseService.monitor_performance("create_capability")
    @with_transaction()
    def create_capability(
        self,
        form_data: Dict[str, Any],
        user: Any,
        session: Dict[str, Any]
    ) -> CapabilityOperationResult:
        """
        Create new capability with validation.

        Args:
            form_data: Form cleaned data
            user: Current user performing operation
            session: User session data

        Returns:
            CapabilityOperationResult with created capability
        """
        try:
            capability = Capability(**form_data)
            capability.save()

            putils.save_userinfo(
                capability, user, session, create=True
            )

            self.logger.info(f"Created capability: {capability.capscode}")

            return CapabilityOperationResult(
                success=True,
                capability=capability,
                data={
                    "success": "Record has been saved successfully",
                    "row": Capability.objects.values(
                        *self.list_fields
                    ).get(id=capability.id)
                }
            )

        except IntegrityError as e:
            correlation_id = ErrorHandler.handle_exception(
                e,
                context={'operation': 'create_capability'},
                level='error'
            )
            return CapabilityOperationResult(
                success=False,
                error_message="Capability already exists or violates constraints",
                correlation_id=correlation_id
            )
        except ValidationError as e:
            correlation_id = ErrorHandler.handle_exception(
                e,
                context={'operation': 'create_capability_validation'},
                level='warning'
            )
            return CapabilityOperationResult(
                success=False,
                error_message="Invalid capability data provided",
                correlation_id=correlation_id
            )

    @BaseService.monitor_performance("update_capability")
    @with_transaction()
    def update_capability(
        self,
        capability_id: int,
        form_data: Dict[str, Any],
        user: Any,
        session: Dict[str, Any]
    ) -> CapabilityOperationResult:
        """
        Update existing capability.

        Args:
            capability_id: ID of capability to update
            form_data: Form cleaned data
            user: Current user performing operation
            session: User session data

        Returns:
            CapabilityOperationResult with updated capability
        """
        try:
            capability = Capability.objects.get(id=capability_id)

            for field, value in form_data.items():
                setattr(capability, field, value)

            capability.save()

            putils.save_userinfo(
                capability, user, session, create=False
            )

            self.logger.info(f"Updated capability: {capability.capscode}")

            return CapabilityOperationResult(
                success=True,
                capability=capability,
                data={
                    "success": "Record has been updated successfully",
                    "row": Capability.objects.values(
                        *self.list_fields
                    ).get(id=capability.id)
                }
            )

        except Capability.DoesNotExist as e:
            correlation_id = ErrorHandler.handle_exception(
                e,
                context={'operation': 'update_capability', 'capability_id': capability_id},
                level='warning'
            )
            return CapabilityOperationResult(
                success=False,
                error_message="Capability not found",
                correlation_id=correlation_id
            )
        except IntegrityError as e:
            correlation_id = ErrorHandler.handle_exception(
                e,
                context={'operation': 'update_capability'},
                level='error'
            )
            return CapabilityOperationResult(
                success=False,
                error_message="Update violates data constraints",
                correlation_id=correlation_id
            )

    @BaseService.monitor_performance("get_capability")
    def get_capability(
        self,
        capability_id: int
    ) -> Optional[Capability]:
        """
        Retrieve capability by ID with relationships.

        Args:
            capability_id: ID of capability to retrieve

        Returns:
            Capability instance or None
        """
        try:
            return Capability.objects.select_related(
                *self.related_fields
            ).get(id=capability_id)
        except Capability.DoesNotExist:
            self.logger.warning(f"Capability not found: {capability_id}")
            return None

    @BaseService.monitor_performance("delete_capability")
    @with_transaction()
    def delete_capability(
        self,
        capability_id: int,
        user: Any,
        session: Dict[str, Any]
    ) -> CapabilityOperationResult:
        """
        Delete capability record.

        Args:
            capability_id: ID of capability to delete
            user: Current user performing operation
            session: User session data

        Returns:
            CapabilityOperationResult with deletion status
        """
        try:
            capability = Capability.objects.get(id=capability_id)
            capscode = capability.capscode

            capability.delete()

            self.logger.info(
                f"Deleted capability: {capscode}",
                extra={'user': user.id if user else None}
            )

            return CapabilityOperationResult(
                success=True,
                data={"id": capability_id}
            )

        except Capability.DoesNotExist as e:
            correlation_id = ErrorHandler.handle_exception(
                e,
                context={'operation': 'delete_capability', 'capability_id': capability_id},
                level='warning'
            )
            return CapabilityOperationResult(
                success=False,
                error_message="Capability not found",
                correlation_id=correlation_id
            )
        except IntegrityError as e:
            correlation_id = ErrorHandler.handle_exception(
                e,
                context={'operation': 'delete_capability'},
                level='error'
            )
            return CapabilityOperationResult(
                success=False,
                error_message="Cannot delete capability with dependencies",
                correlation_id=correlation_id
            )

    def get_service_name(self) -> str:
        """Return service name for monitoring."""
        return "CapabilityManagementService"