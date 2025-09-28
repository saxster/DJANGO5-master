"""
Mass Assignment Protection Utility

Prevents mass assignment vulnerabilities by enforcing whitelist-based
field access control for all API endpoints.

Compliance:
- Rule #13: Prevents unauthorized field modifications
- Rule #5: No debug information exposure
- Defends against privilege escalation via mass assignment

HIGH-IMPACT SECURITY FEATURE - Mass Assignment Defense
"""

import logging
from typing import List, Dict, Any, Set
from django.core.exceptions import FieldDoesNotExist
from rest_framework import serializers

logger = logging.getLogger('security')


class MassAssignmentProtector:
    """
    Utility class to protect against mass assignment vulnerabilities.

    Validates that only explicitly allowed fields are being modified.
    """

    PROTECTED_FIELDS = {
        'is_staff',
        'is_superuser',
        'is_active',
        'groups',
        'user_permissions',
        'password',
        'last_login',
        'date_joined',
    }

    SENSITIVE_FIELDS = {
        'created_at',
        'updated_at',
        'uuid',
        'tenant_id',
        'client_id',
    }

    @classmethod
    def validate_fields(
        cls,
        model_class,
        input_data: Dict[str, Any],
        allowed_fields: List[str],
        context: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        Validate that only allowed fields are being modified.

        Args:
            model_class: Django model class
            input_data: Input data dictionary
            allowed_fields: List of explicitly allowed field names
            context: Optional context (request, user, etc.)

        Returns:
            Validated and filtered input data

        Raises:
            serializers.ValidationError: If protected fields are in input
        """
        context = context or {}

        submitted_fields = set(input_data.keys())
        allowed_set = set(allowed_fields)

        protected_submitted = submitted_fields & cls.PROTECTED_FIELDS
        if protected_submitted:
            logger.warning(
                "Mass assignment attempt on protected fields",
                extra={
                    'model': model_class.__name__,
                    'protected_fields': list(protected_submitted),
                    'user': context.get('user'),
                }
            )
            raise serializers.ValidationError(
                f"Cannot modify protected fields: {', '.join(protected_submitted)}"
            )

        unauthorized_fields = submitted_fields - allowed_set - cls.SENSITIVE_FIELDS
        if unauthorized_fields:
            logger.warning(
                "Mass assignment attempt on unauthorized fields",
                extra={
                    'model': model_class.__name__,
                    'unauthorized_fields': list(unauthorized_fields),
                    'user': context.get('user'),
                }
            )

            filtered_data = {k: v for k, v in input_data.items() if k in allowed_set}
            return filtered_data

        return input_data

    @classmethod
    def get_model_writable_fields(cls, model_class, exclude_auto: bool = True) -> Set[str]:
        """
        Get list of writable fields for a model.

        Args:
            model_class: Django model class
            exclude_auto: Exclude auto-generated fields

        Returns:
            Set of writable field names
        """
        writable_fields = set()

        for field in model_class._meta.get_fields():
            if field.many_to_many or field.one_to_many:
                continue

            if exclude_auto and field.name in cls.SENSITIVE_FIELDS:
                continue

            if field.name in cls.PROTECTED_FIELDS:
                continue

            if not getattr(field, 'editable', True):
                continue

            writable_fields.add(field.name)

        return writable_fields

    @classmethod
    def check_privilege_escalation(
        cls,
        model_class,
        input_data: Dict[str, Any],
        user,
        instance = None
    ) -> None:
        """
        Check for privilege escalation attempts.

        Args:
            model_class: Django model class
            input_data: Input data dictionary
            user: Current user making the request
            instance: Existing instance being updated (None for create)

        Raises:
            serializers.ValidationError: If privilege escalation detected
        """
        escalation_fields = {
            'isadmin',
            'is_staff',
            'is_superuser',
            'enable',
            'isverified',
            'permissions',
        }

        submitted_escalation = set(input_data.keys()) & escalation_fields

        if submitted_escalation:
            if not user.is_staff and not user.is_superuser:
                logger.critical(
                    "Privilege escalation attempt by non-staff user",
                    extra={
                        'user': user.id,
                        'username': user.loginid if hasattr(user, 'loginid') else user.username,
                        'attempted_fields': list(submitted_escalation),
                        'model': model_class.__name__,
                    }
                )
                raise serializers.ValidationError(
                    "Insufficient permissions to modify these fields"
                )

            if instance:
                for field in submitted_escalation:
                    current_value = getattr(instance, field, None)
                    new_value = input_data[field]

                    if current_value != new_value:
                        logger.warning(
                            "Privilege modification by staff user",
                            extra={
                                'user': user.id,
                                'field': field,
                                'old_value': current_value,
                                'new_value': new_value,
                                'instance': instance.id if hasattr(instance, 'id') else None,
                            }
                        )

    @classmethod
    def create_field_whitelist(
        cls,
        model_class,
        base_fields: List[str],
        admin_only_fields: List[str] = None,
        user = None
    ) -> List[str]:
        """
        Create field whitelist based on user permissions.

        Args:
            model_class: Django model class
            base_fields: Base fields available to all users
            admin_only_fields: Fields only available to admins
            user: Current user (to check permissions)

        Returns:
            List of allowed fields for this user
        """
        admin_only_fields = admin_only_fields or []

        allowed = set(base_fields)

        if user and (user.is_staff or user.is_superuser or getattr(user, 'isadmin', False)):
            allowed.update(admin_only_fields)

        model_fields = cls.get_model_writable_fields(model_class)
        allowed = allowed & model_fields

        return list(allowed)