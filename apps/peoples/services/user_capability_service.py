"""
User Capability Service for managing user capabilities and permissions.

This service extracts capability management logic from the People model
to improve separation of concerns and testability.
"""
import logging
from django.core.exceptions import ValidationError
from apps.core.error_handling import ErrorHandler

logger = logging.getLogger("people.capabilities")


class UserCapabilityService:
    """
    Service class for managing user capabilities and permissions.

    This service handles all capability-related operations for People model instances,
    including AI features, permissions, and role-based access control.
    """

    # Standard capability categories
    AI_CAPABILITIES = {
        'can_approve_ai_recommendations',
        'can_manage_knowledge_base',
        'ai_recommendation_approver'
    }

    SYSTEM_CAPABILITIES = {
        'system_administrator',
        'staff_access',
        'tenant_administrator'
    }

    @staticmethod
    def has_capability(people_instance, capability_name: str) -> bool:
        """
        Check if user has a specific capability.

        Args:
            people_instance: People model instance
            capability_name: Name of the capability to check

        Returns:
            bool: True if user has the capability, False otherwise
        """
        if not people_instance.capabilities:
            return False
        return people_instance.capabilities.get(capability_name, False)

    @staticmethod
    def add_capability(people_instance, capability_name: str, value: Any = True) -> bool:
        """
        Add or update a capability for the user.

        Args:
            people_instance: People model instance
            capability_name: Name of the capability to add
            value: Value to set for the capability (default: True)

        Returns:
            bool: True if capability was successfully added
        """
        try:
            if not people_instance.capabilities:
                people_instance.capabilities = {}

            old_value = people_instance.capabilities.get(capability_name)
            people_instance.capabilities[capability_name] = value

            logger.info(
                f"Capability updated for user",
                extra={
                    'user_id': people_instance.id,
                    'capability': capability_name,
                    'old_value': old_value,
                    'new_value': value
                }
            )
            return True

        except (TypeError, ValidationError, ValueError) as e:
            correlation_id = ErrorHandler.handle_exception(
                e,
                context={
                    'operation': 'add_capability',
                    'user_id': people_instance.id,
                    'capability_name': capability_name
                }
            )
            logger.error(f"Failed to add capability (ID: {correlation_id})")
            return False

    @staticmethod
    def remove_capability(people_instance, capability_name: str) -> bool:
        """
        Remove a capability from the user.

        Args:
            people_instance: People model instance
            capability_name: Name of the capability to remove

        Returns:
            bool: True if capability was successfully removed
        """
        try:
            if not people_instance.capabilities:
                return True  # Already doesn't have the capability

            removed_value = people_instance.capabilities.pop(capability_name, None)

            if removed_value is not None:
                logger.info(
                    f"Capability removed for user",
                    extra={
                        'user_id': people_instance.id,
                        'capability': capability_name,
                        'removed_value': removed_value
                    }
                )

            return True

        except (TypeError, ValidationError, ValueError) as e:
            correlation_id = ErrorHandler.handle_exception(
                e,
                context={
                    'operation': 'remove_capability',
                    'user_id': people_instance.id,
                    'capability_name': capability_name
                }
            )
            logger.error(f"Failed to remove capability (ID: {correlation_id})")
            return False

    @staticmethod
    def get_all_capabilities(people_instance) -> Dict[str, Any]:
        """
        Get all user capabilities.

        Args:
            people_instance: People model instance

        Returns:
            dict: Dictionary of all user capabilities
        """
        return people_instance.capabilities.copy() if people_instance.capabilities else {}

    @staticmethod
    def set_ai_capabilities(people_instance, can_approve: bool = False,
                           can_manage_kb: bool = False, is_approver: bool = False) -> bool:
        """
        Set AI-related capabilities for conversational onboarding.

        Args:
            people_instance: People model instance
            can_approve: Whether user can approve AI recommendations
            can_manage_kb: Whether user can manage knowledge base
            is_approver: Whether user is an AI recommendation approver

        Returns:
            bool: True if capabilities were successfully set
        """
        try:
            if not people_instance.capabilities:
                people_instance.capabilities = {}

            ai_capabilities = {
                'can_approve_ai_recommendations': can_approve,
                'can_manage_knowledge_base': can_manage_kb,
                'ai_recommendation_approver': is_approver,
            }

            people_instance.capabilities.update(ai_capabilities)

            logger.info(
                f"AI capabilities updated for user",
                extra={
                    'user_id': people_instance.id,
                    'ai_capabilities': ai_capabilities
                }
            )
            return True

        except (DatabaseError, IntegrityError, TypeError, ValidationError, ValueError) as e:
            correlation_id = ErrorHandler.handle_exception(
                e,
                context={
                    'operation': 'set_ai_capabilities',
                    'user_id': people_instance.id
                }
            )
            logger.error(f"Failed to set AI capabilities (ID: {correlation_id})")
            return False

    @staticmethod
    def get_effective_permissions(people_instance) -> Dict[str, Any]:
        """
        Get effective permissions combining capabilities with user flags.

        Args:
            people_instance: People model instance

        Returns:
            dict: Combined permissions from capabilities and user flags
        """
        permissions = UserCapabilityService.get_all_capabilities(people_instance)

        # Add built-in permissions based on user flags
        if people_instance.is_superuser:
            permissions['system_administrator'] = True
        if people_instance.is_staff:
            permissions['staff_access'] = True
        if people_instance.isadmin:
            permissions['tenant_administrator'] = True

        return permissions

    @staticmethod
    def validate_capability_update(capability_name: str, value: Any) -> bool:
        """
        Validate capability updates before applying them.

        Args:
            capability_name: Name of the capability
            value: Value being set

        Returns:
            bool: True if the update is valid

        Raises:
            ValidationError: If the capability update is invalid
        """
        # Validate capability name format
        if not isinstance(capability_name, str) or not capability_name.strip():
            raise ValidationError("Capability name must be a non-empty string")

        # Validate AI capabilities
        if capability_name in UserCapabilityService.AI_CAPABILITIES:
            if not isinstance(value, bool):
                raise ValidationError(f"AI capability '{capability_name}' must be a boolean value")

        # Validate system capabilities (these should only be set programmatically)
        if capability_name in UserCapabilityService.SYSTEM_CAPABILITIES:
            raise ValidationError(f"System capability '{capability_name}' cannot be modified directly")

        return True

    @staticmethod
    def bulk_update_capabilities(people_instance, capabilities: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """
        Update multiple capabilities at once with validation.

        Args:
            people_instance: People model instance
            capabilities: Dictionary of capabilities to update

        Returns:
            Tuple of (success: bool, errors: List[str])
        """
        errors = []

        try:
            # Validate all capabilities first
            for capability_name, value in capabilities.items():
                try:
                    UserCapabilityService.validate_capability_update(capability_name, value)
                except ValidationError as e:
                    errors.append(f"Invalid capability '{capability_name}': {str(e)}")

            if errors:
                return False, errors

            # Apply all capabilities if validation passed
            if not people_instance.capabilities:
                people_instance.capabilities = {}

            people_instance.capabilities.update(capabilities)

            logger.info(
                f"Bulk capability update for user",
                extra={
                    'user_id': people_instance.id,
                    'updated_capabilities': list(capabilities.keys()),
                    'capability_count': len(capabilities)
                }
            )

            return True, []

        except (DatabaseError, IntegrityError, TypeError, ValidationError, ValueError) as e:
            correlation_id = ErrorHandler.handle_exception(
                e,
                context={
                    'operation': 'bulk_update_capabilities',
                    'user_id': people_instance.id,
                    'capabilities_count': len(capabilities)
                }
            )
            errors.append(f"Failed to update capabilities (ID: {correlation_id})")
            return False, errors