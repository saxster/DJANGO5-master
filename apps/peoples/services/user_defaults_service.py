"""
User Defaults Service for managing default field values in People model.

This service handles the complex logic of setting default values for foreign key fields
in a secure, maintainable way while preventing recursive operations.

Updated to support new model split architecture:
- People: Core authentication fields
- PeopleProfile: Personal information
- PeopleOrganizational: Organizational relationships
"""
import logging
from typing import Tuple, Dict, Any
from django.db import DatabaseError
from apps.core import utils
from apps.core.error_handling import ErrorHandler

logger = logging.getLogger("people.defaults")


class UserDefaultsService:
    """
    Service class for managing default values in People model instances.

    This service extracts complex default-setting logic from the model's save method
    to improve maintainability and testability.

    Updated for new architecture:
    - Organizational defaults now handled in PeopleOrganizational model
    - This service focuses on People model defaults only
    """

    @staticmethod
    def set_default_fields(people_instance) -> Tuple[bool, Dict[str, Any]]:
        """
        Set default values for People model fields if they are None.

        Note: Organizational field defaults are now handled by
        PeopleOrganizational.save() method.

        Args:
            people_instance: People model instance to set defaults for

        Returns:
            Tuple of (defaults_were_set: bool, context: dict)
        """
        defaults_set = False
        context = {
            'user_id': people_instance.id,
            'peoplename': people_instance.peoplename,
            'errors': []
        }

        logger.info(
            f"Setting defaults for People model (organizational defaults handled separately)",
            extra={'user_id': people_instance.id}
        )

        return defaults_set, context

    @staticmethod
    def initialize_capabilities(people_instance) -> bool:
        """
        Initialize capabilities field if empty.

        Args:
            people_instance: People model instance

        Returns:
            bool: True if capabilities were initialized
        """
        if not people_instance.capabilities:
            people_instance.capabilities = {}
            return True
        return False

    @staticmethod
    def set_profile_defaults(profile_instance) -> Tuple[bool, Dict[str, Any]]:
        """
        Set default values for PeopleProfile instance.

        Args:
            profile_instance: PeopleProfile model instance

        Returns:
            Tuple of (defaults_were_set: bool, context: dict)
        """
        defaults_set = False
        context = {
            'profile_id': profile_instance.people_id,
            'errors': []
        }

        from ..constants import peoplejson

        if not profile_instance.people_extras:
            profile_instance.people_extras = peoplejson()
            defaults_set = True

        return defaults_set, context

    @staticmethod
    def set_organizational_defaults(org_instance) -> Tuple[bool, Dict[str, Any]]:
        """
        Set default values for PeopleOrganizational instance.

        Note: This method is kept for service layer consistency, but the actual
        default setting is handled in PeopleOrganizational.save() method.

        Args:
            org_instance: PeopleOrganizational model instance

        Returns:
            Tuple of (defaults_were_set: bool, context: dict)
        """
        defaults_set = False
        context = {
            'organizational_id': org_instance.people_id,
            'errors': []
        }

        logger.info(
            f"Organizational defaults handled by model save method",
            extra={'people_id': org_instance.people_id}
        )

        return defaults_set, context