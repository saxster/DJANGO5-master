"""
Capability management mixin for People model.

This mixin provides capability-related methods to keep the core
People model under the 150-line limit (Rule #7).

All capability business logic is delegated to UserCapabilityService
for better separation of concerns and testability.
"""


class PeopleCapabilityMixin:
    """
    Mixin providing capability management methods for People model.

    This mixin delegates all capability operations to UserCapabilityService,
    following the service layer pattern for better maintainability.

    Methods:
        has_capability: Check if user has a specific capability
        add_capability: Add or update a capability
        remove_capability: Remove a capability
        get_all_capabilities: Get all user capabilities
        set_ai_capabilities: Set AI-related capabilities
        get_effective_permissions: Get combined capabilities and permissions
    """

    def has_capability(self, capability_name):
        """
        Check if user has a specific capability.

        Args:
            capability_name (str): Name of the capability to check

        Returns:
            bool: True if user has the capability, False otherwise

        Example:
            if user.has_capability('can_approve_workorders'):
                # Allow work order approval
        """
        from ..services import UserCapabilityService
        return UserCapabilityService.has_capability(self, capability_name)

    def add_capability(self, capability_name, value=True):
        """
        Add or update a capability for the user.

        Args:
            capability_name (str): Name of the capability
            value: Value to set for the capability (default: True)

        Returns:
            bool: True if capability was added/updated successfully

        Example:
            user.add_capability('can_manage_knowledge_base', True)
        """
        from ..services import UserCapabilityService
        return UserCapabilityService.add_capability(self, capability_name, value)

    def remove_capability(self, capability_name):
        """
        Remove a capability from the user.

        Args:
            capability_name (str): Name of the capability to remove

        Returns:
            bool: True if capability was removed successfully

        Example:
            user.remove_capability('can_approve_workorders')
        """
        from ..services import UserCapabilityService
        return UserCapabilityService.remove_capability(self, capability_name)

    def get_all_capabilities(self):
        """
        Get all capabilities for the user.

        Returns:
            dict: Dictionary of all user capabilities

        Example:
            capabilities = user.get_all_capabilities()
            # {'can_approve': True, 'can_manage_kb': False, ...}
        """
        from ..services import UserCapabilityService
        return UserCapabilityService.get_all_capabilities(self)

    def set_ai_capabilities(self, can_approve=False, can_manage_kb=False, is_approver=False):
        """
        Set AI-related capabilities for conversational onboarding.

        This is a convenience method for setting multiple AI-related
        capabilities at once.

        Args:
            can_approve (bool): Can approve AI-generated content
            can_manage_kb (bool): Can manage knowledge base
            is_approver (bool): Is designated as an approver

        Returns:
            bool: True if capabilities were set successfully

        Example:
            user.set_ai_capabilities(
                can_approve=True,
                can_manage_kb=True,
                is_approver=True
            )
        """
        from ..services import UserCapabilityService
        return UserCapabilityService.set_ai_capabilities(
            self,
            can_approve=can_approve,
            can_manage_kb=can_manage_kb,
            is_approver=is_approver
        )

    def get_effective_permissions(self):
        """
        Get effective permissions combining capabilities with user flags.

        This method combines:
        - Capabilities from the capabilities JSON field
        - Django permissions from groups and user permissions
        - User-level flags (is_staff, isadmin, etc.)

        Returns:
            dict: Combined permissions dictionary

        Example:
            permissions = user.get_effective_permissions()
            # {
            #     'is_staff': True,
            #     'is_admin': True,
            #     'capabilities': {...},
            #     'django_permissions': [...]
            # }
        """
        from ..services import UserCapabilityService
        return UserCapabilityService.get_effective_permissions(self)