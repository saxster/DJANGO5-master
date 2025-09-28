"""
People Management Service

Handles all business logic for People model operations including:
- CRUD operations
- Field encryption/decryption
- QR code generation
- Search and pagination
- Image upload handling
"""

import logging
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass

from django.core.exceptions import ValidationError, PermissionDenied
from django.db import IntegrityError, transaction
from django.db.models import Q, QuerySet

from apps.core.services.base_service import BaseService
from apps.core.services import with_transaction
from apps.core.error_handling import ErrorHandler
from apps.core.exceptions import (
    UserManagementException,
    SecurityException,
    DatabaseException
)
from apps.core.services.secure_encryption_service import SecureEncryptionService
from apps.peoples.models import People
import apps.peoples.utils as putils

logger = logging.getLogger(__name__)


@dataclass
class PeopleListResult:
    """Result structure for people list queries."""
    data: List[Dict[str, Any]]
    total: int
    filtered: int
    draw: int


@dataclass
class PeopleOperationResult:
    """Result structure for people operations."""
    success: bool
    people: Optional[People] = None
    error_message: Optional[str] = None
    correlation_id: Optional[str] = None
    data: Optional[Dict[str, Any]] = None


class PeopleManagementService(BaseService):
    """
    Service for managing People model operations.

    Extracted from peoples/views.py to separate business logic from HTTP handling.
    """

    def __init__(self):
        super().__init__()
        self.related_fields = ["peopletype", "bu", "department", "designation"]
        self.list_fields = [
            "id", "peoplecode", "peoplename", "peopletype__taname",
            "bu__buname", "isadmin", "enable", "email", "mobno",
            "department__taname", "designation__taname"
        ]

    @BaseService.monitor_performance("get_people_list")
    def get_people_list(
        self,
        request_params: Dict[str, Any],
        session: Dict[str, Any]
    ) -> PeopleListResult:
        """
        Get paginated and filtered list of people.

        Args:
            request_params: Request parameters (search, pagination, ordering)
            session: User session data

        Returns:
            PeopleListResult with paginated data
        """
        try:
            draw = int(request_params.get("draw", 1))
            start = int(request_params.get("start", 0))
            length = int(request_params.get("length", 10))
            search_value = request_params.get("search[value]", "").strip()

            queryset = self._build_people_queryset(session)

            if search_value:
                queryset = self._apply_search_filter(queryset, search_value)

            queryset = self._apply_ordering(queryset, request_params)

            total = queryset.count()
            paginated = queryset[start:start + length]
            data = self._serialize_people_list(list(paginated))

            return PeopleListResult(
                data=data,
                total=total,
                filtered=total,
                draw=draw
            )

        except (ValueError, TypeError) as e:
            correlation_id = ErrorHandler.handle_exception(
                e,
                context={'operation': 'get_people_list'},
                level='warning'
            )
            raise UserManagementException(
                "Invalid pagination parameters",
                original_exception=e
            ) from e
        except DatabaseException as e:
            self.logger.error(f"Database error retrieving people list: {str(e)}")
            raise

    def _build_people_queryset(self, session: Dict[str, Any]) -> QuerySet:
        """Build base queryset with proper select_related."""
        return People.objects.people_list_view(
            {'session': session},
            self.list_fields,
            self.related_fields
        )

    def _apply_search_filter(
        self,
        queryset: QuerySet,
        search_value: str
    ) -> QuerySet:
        """Apply search filter across multiple fields."""
        return queryset.filter(
            Q(peoplename__icontains=search_value)
            | Q(peoplecode__icontains=search_value)
            | Q(department__taname__icontains=search_value)
            | Q(bu__buname__icontains=search_value)
        )

    def _apply_ordering(
        self,
        queryset: QuerySet,
        request_params: Dict[str, Any]
    ) -> QuerySet:
        """Apply ordering to queryset based on request parameters."""
        order_col = request_params.get("order[0][column]")
        order_dir = request_params.get("order[0][dir]")
        column_name = request_params.get(f"columns[{order_col}][data]")

        if column_name:
            order_prefix = "" if order_dir == "asc" else "-"
            return queryset.order_by(f"{order_prefix}{column_name}")

        return queryset

    def _serialize_people_list(
        self,
        data: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Serialize people list with field decryption.

        Args:
            data: Raw queryset data

        Returns:
            List of serialized people records
        """
        encrypted_fields = ['email', 'mobno']

        for row in data:
            for field in encrypted_fields:
                if field in row and row[field]:
                    row[field] = self._decrypt_field_value(row[field], field)

        return data

    def _decrypt_field_value(self, value: str, field_name: str) -> str:
        """
        Safely decrypt a field value using SecureEncryptionService.

        Args:
            value: Encrypted value from database
            field_name: Name of field being decrypted

        Returns:
            Decrypted value or placeholder
        """
        if not value:
            return value

        try:
            if SecureEncryptionService.is_securely_encrypted(value):
                return SecureEncryptionService.decrypt(value)
            elif value.startswith('ENC_V1:'):
                legacy_payload = value[len('ENC_V1:'):]
                migration_successful, result = SecureEncryptionService.migrate_legacy_data(legacy_payload)
                if migration_successful:
                    return SecureEncryptionService.decrypt(result)
                return legacy_payload
            else:
                return value
        except (ValueError, TypeError) as e:
            correlation_id = ErrorHandler.handle_exception(
                e,
                context={'operation': 'field_decryption', 'field': field_name},
                level='warning'
            )
            self.logger.warning(
                f"Field decryption failed for {field_name}, treating as plain text",
                extra={'correlation_id': correlation_id}
            )
            return value
        except SecurityException as e:
            correlation_id = ErrorHandler.handle_exception(
                e,
                context={'operation': 'field_decryption_security', 'field': field_name},
                level='critical'
            )
            self.logger.critical(
                f"Security issue during field decryption for {field_name}",
                extra={'correlation_id': correlation_id}
            )
            return "[ENCRYPTED]"

    @BaseService.monitor_performance("create_people")
    @with_transaction()
    def create_people(
        self,
        form_data: Dict[str, Any],
        json_form_data: Dict[str, Any],
        user: Any,
        session: Dict[str, Any],
        files: Optional[Dict[str, Any]] = None
    ) -> PeopleOperationResult:
        """
        Create new people record with validation.

        Args:
            form_data: Main form cleaned data
            json_form_data: JSON form (extras) cleaned data
            user: Current user performing operation
            session: User session data
            files: Uploaded files dictionary

        Returns:
            PeopleOperationResult with created person
        """
        try:
            people = People(**form_data)

            if files and files.get("peopleimg"):
                people.peopleimg = files["peopleimg"]

            if not people.password:
                people.set_password(form_data.get("peoplecode", "default"))

            people.save()

            self._save_people_extras(people, json_form_data)

            bu_id = people.bu.id if people.bu else None
            putils.save_userinfo(
                people, user, session, create=True, bu=bu_id
            )

            self.logger.info(f"Created people record: {people.peoplecode}")

            return PeopleOperationResult(
                success=True,
                people=people,
                data={"pk": people.id}
            )

        except IntegrityError as e:
            correlation_id = ErrorHandler.handle_exception(
                e,
                context={'operation': 'create_people'},
                level='error'
            )
            return PeopleOperationResult(
                success=False,
                error_message="People record already exists or violates constraints",
                correlation_id=correlation_id
            )
        except ValidationError as e:
            correlation_id = ErrorHandler.handle_exception(
                e,
                context={'operation': 'create_people_validation'},
                level='warning'
            )
            return PeopleOperationResult(
                success=False,
                error_message="Invalid data provided",
                correlation_id=correlation_id
            )

    @BaseService.monitor_performance("update_people")
    @with_transaction()
    def update_people(
        self,
        people_id: int,
        form_data: Dict[str, Any],
        json_form_data: Dict[str, Any],
        user: Any,
        session: Dict[str, Any],
        files: Optional[Dict[str, Any]] = None
    ) -> PeopleOperationResult:
        """
        Update existing people record.

        Args:
            people_id: ID of people to update
            form_data: Main form cleaned data
            json_form_data: JSON form (extras) cleaned data
            user: Current user performing operation
            session: User session data
            files: Uploaded files dictionary

        Returns:
            PeopleOperationResult with updated person
        """
        try:
            people = People.objects.get(id=people_id)

            for field, value in form_data.items():
                setattr(people, field, value)

            if files and files.get("peopleimg"):
                people.peopleimg = files["peopleimg"]

            people.save()

            self._save_people_extras(people, json_form_data)

            bu_id = people.bu.id if people.bu else None
            putils.save_userinfo(
                people, user, session, create=False, bu=bu_id
            )

            self.logger.info(f"Updated people record: {people.peoplecode}")

            return PeopleOperationResult(
                success=True,
                people=people,
                data={"pk": people.id}
            )

        except People.DoesNotExist as e:
            correlation_id = ErrorHandler.handle_exception(
                e,
                context={'operation': 'update_people', 'people_id': people_id},
                level='warning'
            )
            return PeopleOperationResult(
                success=False,
                error_message="People record not found",
                correlation_id=correlation_id
            )
        except IntegrityError as e:
            correlation_id = ErrorHandler.handle_exception(
                e,
                context={'operation': 'update_people'},
                level='error'
            )
            return PeopleOperationResult(
                success=False,
                error_message="Update violates data constraints",
                correlation_id=correlation_id
            )

    def _save_people_extras(
        self,
        people: People,
        json_form_data: Dict[str, Any]
    ) -> None:
        """
        Save people extras (JSON form data).

        Args:
            people: People instance
            json_form_data: Extras form data
        """
        if not putils.save_jsonform({'cleaned_data': json_form_data}, people):
            self.logger.warning(
                f"Failed to save people extras for {people.peoplecode}"
            )

    @BaseService.monitor_performance("get_people")
    def get_people(
        self,
        people_id: int,
        session: Dict[str, Any]
    ) -> Optional[People]:
        """
        Retrieve people record by ID with security checks.

        Args:
            people_id: ID of people to retrieve
            session: User session for authorization

        Returns:
            People instance or None
        """
        try:
            return People.objects.select_related(
                *self.related_fields
            ).get(id=people_id)
        except People.DoesNotExist:
            self.logger.warning(f"People not found: {people_id}")
            return None

    @BaseService.monitor_performance("delete_people")
    @with_transaction()
    def delete_people(
        self,
        people_id: int,
        user: Any,
        session: Dict[str, Any]
    ) -> PeopleOperationResult:
        """
        Delete people record (soft delete preferred).

        Args:
            people_id: ID of people to delete
            user: Current user performing operation
            session: User session data

        Returns:
            PeopleOperationResult with deletion status
        """
        try:
            people = People.objects.get(id=people_id)

            people.enable = False
            people.save()

            self.logger.info(
                f"Soft deleted people record: {people.peoplecode}",
                extra={'user': user.id if user else None}
            )

            return PeopleOperationResult(
                success=True,
                data={"id": people_id}
            )

        except People.DoesNotExist as e:
            correlation_id = ErrorHandler.handle_exception(
                e,
                context={'operation': 'delete_people', 'people_id': people_id},
                level='warning'
            )
            return PeopleOperationResult(
                success=False,
                error_message="People record not found",
                correlation_id=correlation_id
            )

    def get_service_name(self) -> str:
        """Return service name for monitoring."""
        return "PeopleManagementService"