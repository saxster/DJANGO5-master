"""
GraphQL Field-Level Permissions Framework

Implements fine-grained field-level authorization for GraphQL types to control
access to sensitive fields based on user roles, permissions, and capabilities.

Features:
- Field visibility control based on user roles
- Dynamic field filtering at resolution time
- Permission caching for performance
- Integration with Django's permission system
- Capability-based field access control
- Audit logging for field access denials

Security Compliance:
- Addresses CVSS 7.2 (High) - GraphQL Authorization Gaps
- Implements defense-in-depth for field-level access
- Prevents unauthorized data exposure through nested queries

Usage:
    from apps.core.security.graphql_field_permissions import (
        FieldPermissionChecker,
        require_field_permission,
        filter_fields_by_permission
    )

    class SensitiveDataType(DjangoObjectType):
        @staticmethod
        def resolve_sensitive_field(parent, info):
            checker = FieldPermissionChecker(info.context.user)
            if not checker.can_access_field('model_name', 'sensitive_field'):
                return None
            return parent.sensitive_field
"""

import logging
from typing import Dict, Any, List, Optional, Set, Callable
from functools import wraps
from django.conf import settings
from django.core.cache import cache
from django.core.exceptions import PermissionDenied
from graphql import GraphQLError
import json


security_logger = logging.getLogger('security')
graphql_field_logger = logging.getLogger('graphql_field_permissions')


class FieldPermissionChecker:
    """
    Checks field-level permissions for GraphQL types based on user roles and capabilities.

    This class provides granular field-level access control to prevent unauthorized
    access to sensitive data through GraphQL queries.
    """

    SENSITIVE_FIELDS = {
        'People': {
            'mobno', 'email', 'password', 'peopleimg', 'deviceid',
            'emergencycontacts', 'emergencyemails', 'capabilities'
        },
        'PeopleEventlog': {
            'gpsdata', 'videolog', 'imagelog', 'deviceinfo'
        },
        'Ticket': {
            'internal_notes', 'escalation_details'
        },
        'Wom': {
            'approver_comments', 'internal_assessment'
        },
        'JournalEntry': {
            'mood_rating', 'stress_level', 'energy_level', 'stress_triggers',
            'coping_strategies', 'gratitude_items', 'daily_goals'
        }
    }

    ADMIN_ONLY_FIELDS = {
        'People': {'isadmin', 'is_staff', 'is_superuser', 'user_permissions'},
        'Ticket': {'internal_notes', 'sla_violations'},
        'Wom': {'approval_chain', 'internal_assessment'}
    }

    ROLE_BASED_FIELDS = {
        'manager': {
            'People': {'performance_metrics', 'attendance_summary'},
            'PeopleEventlog': {'location_history', 'activity_patterns'}
        },
        'hr': {
            'People': {'salary_grade', 'employment_details', 'disciplinary_records'}
        },
        'security': {
            'PeopleEventlog': {'gpsdata', 'videolog', 'imagelog'},
            'Ticket': {'security_assessment'}
        }
    }

    def __init__(self, user):
        """
        Initialize field permission checker for a user.

        Args:
            user: The authenticated user object
        """
        self.user = user
        self.is_admin = getattr(user, 'isadmin', False)
        self.is_authenticated = user.is_authenticated if hasattr(user, 'is_authenticated') else False
        self._permission_cache = {}

    def can_access_field(self, model_name: str, field_name: str) -> bool:
        """
        Check if user can access a specific field on a model.

        Args:
            model_name: Name of the model (e.g., 'People', 'Ticket')
            field_name: Name of the field to check

        Returns:
            bool: True if user can access the field, False otherwise
        """
        if not self.is_authenticated:
            return False

        cache_key = f"field_perm:{self.user.id}:{model_name}:{field_name}"

        if cache_key in self._permission_cache:
            return self._permission_cache[cache_key]

        cached_result = cache.get(cache_key)
        if cached_result is not None:
            self._permission_cache[cache_key] = cached_result
            return cached_result

        result = self._check_field_permission(model_name, field_name)

        self._permission_cache[cache_key] = result
        cache.set(cache_key, result, timeout=300)

        if not result:
            self._log_field_access_denial(model_name, field_name)

        return result

    def _check_field_permission(self, model_name: str, field_name: str) -> bool:
        """Internal method to check field permission."""
        if self.is_admin:
            return True

        if field_name in self.ADMIN_ONLY_FIELDS.get(model_name, set()):
            return False

        if field_name in self.SENSITIVE_FIELDS.get(model_name, set()):
            return self._check_sensitive_field_permission(model_name, field_name)

        if self._is_role_based_field(model_name, field_name):
            return self._check_role_based_permission(model_name, field_name)

        return True

    def _check_sensitive_field_permission(self, model_name: str, field_name: str) -> bool:
        """Check permission for sensitive fields."""
        user_capabilities = self._get_user_capabilities()

        capability_key = f"can_view_{model_name.lower()}_{field_name}"

        if user_capabilities.get(capability_key, False):
            return True

        if model_name == 'People' and field_name in {'mobno', 'email', 'peopleimg'}:
            return user_capabilities.get('can_view_people_details', False)

        if model_name == 'JournalEntry':
            return user_capabilities.get('can_view_wellbeing_data', False)

        return False

    def _check_role_based_permission(self, model_name: str, field_name: str) -> bool:
        """Check permission for role-based fields."""
        user_capabilities = self._get_user_capabilities()

        for role, role_fields in self.ROLE_BASED_FIELDS.items():
            if field_name in role_fields.get(model_name, set()):
                role_permission = user_capabilities.get(f'is_{role}', False)
                if role_permission:
                    return True

        return False

    def _is_role_based_field(self, model_name: str, field_name: str) -> bool:
        """Check if field is role-based."""
        for role_fields in self.ROLE_BASED_FIELDS.values():
            if field_name in role_fields.get(model_name, set()):
                return True
        return False

    def _get_user_capabilities(self) -> Dict[str, Any]:
        """Get user capabilities from JSON field."""
        if not hasattr(self.user, 'capabilities'):
            return {}

        capabilities = self.user.capabilities

        if isinstance(capabilities, dict):
            return capabilities

        if isinstance(capabilities, str):
            try:
                return json.loads(capabilities)
            except (json.JSONDecodeError, TypeError):
                return {}

        return {}

    def _log_field_access_denial(self, model_name: str, field_name: str):
        """Log field access denial for security monitoring."""
        security_logger.warning(
            f"Field access denied: {model_name}.{field_name}",
            extra={
                'user_id': self.user.id,
                'username': getattr(self.user, 'loginid', str(self.user)),
                'model': model_name,
                'field': field_name,
                'is_admin': self.is_admin,
                'event_type': 'field_access_denial'
            }
        )

    def filter_dict_by_permissions(self, model_name: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Filter a dictionary to only include fields the user can access.

        Args:
            model_name: Name of the model
            data: Dictionary of field values

        Returns:
            Filtered dictionary with only accessible fields
        """
        filtered_data = {}

        for field_name, value in data.items():
            if self.can_access_field(model_name, field_name):
                filtered_data[field_name] = value
            else:
                filtered_data[field_name] = None

        return filtered_data


def require_field_permission(model_name: str, field_name: str) -> Callable:
    """
    Decorator to require permission for accessing a specific field.

    Args:
        model_name: Name of the model containing the field
        field_name: Name of the field to protect

    Returns:
        Decorator function

    Raises:
        GraphQLError: If user doesn't have permission to access the field

    Example:
        @require_field_permission('People', 'mobno')
        def resolve_mobno(parent, info):
            return parent.mobno
    """
    def decorator(resolver: Callable) -> Callable:
        @wraps(resolver)
        def wrapper(*args, **kwargs):
            info = args[1] if len(args) > 1 else kwargs.get('info')

            if not info or not hasattr(info, 'context'):
                raise GraphQLError("Invalid request context")

            user = info.context.user

            if not user.is_authenticated:
                raise GraphQLError("Authentication required")

            checker = FieldPermissionChecker(user)

            if not checker.can_access_field(model_name, field_name):
                graphql_field_logger.warning(
                    f"Field access denied via decorator: {model_name}.{field_name}",
                    extra={
                        'user_id': user.id,
                        'model': model_name,
                        'field': field_name,
                        'resolver': resolver.__name__
                    }
                )
                return None

            return resolver(*args, **kwargs)

        return wrapper

    return decorator


def filter_fields_by_permission(model_name: str) -> Callable:
    """
    Decorator to automatically filter all fields in a resolver response based on permissions.

    Args:
        model_name: Name of the model

    Returns:
        Decorator function

    Example:
        @filter_fields_by_permission('People')
        def resolve_people(parent, info):
            return People.objects.all()
    """
    def decorator(resolver: Callable) -> Callable:
        @wraps(resolver)
        def wrapper(*args, **kwargs):
            info = args[1] if len(args) > 1 else kwargs.get('info')

            if not info or not hasattr(info, 'context'):
                return resolver(*args, **kwargs)

            user = info.context.user

            if not user.is_authenticated:
                return resolver(*args, **kwargs)

            result = resolver(*args, **kwargs)

            if result is None:
                return None

            checker = FieldPermissionChecker(user)

            if isinstance(result, dict):
                return checker.filter_dict_by_permissions(model_name, result)

            if isinstance(result, list):
                return [
                    checker.filter_dict_by_permissions(model_name, item)
                    if isinstance(item, dict) else item
                    for item in result
                ]

            return result

        return wrapper

    return decorator


class FieldPermissionMixin:
    """
    Mixin class for GraphQL types to provide automatic field-level permission checks.

    Usage:
        class PeopleType(FieldPermissionMixin, DjangoObjectType):
            model_name = 'People'

            class Meta:
                model = People
                fields = '__all__'
    """

    model_name: str = None

    @classmethod
    def get_node(cls, info, id):
        """Override get_node to apply field permissions."""
        node = super().get_node(info, id)

        if node and info.context.user.is_authenticated:
            cls._apply_field_permissions(node, info.context.user)

        return node

    @classmethod
    def _apply_field_permissions(cls, instance, user):
        """Apply field-level permissions to an object instance."""
        if not cls.model_name:
            return instance

        checker = FieldPermissionChecker(user)

        for field_name in dir(instance):
            if field_name.startswith('_'):
                continue

            if not checker.can_access_field(cls.model_name, field_name):
                try:
                    setattr(instance, field_name, None)
                except (AttributeError, TypeError):
                    pass

        return instance


def create_permission_aware_type(django_object_type_class, model_name: str, protected_fields: Set[str]):
    """
    Factory function to create a permission-aware GraphQL type.

    Args:
        django_object_type_class: The DjangoObjectType class
        model_name: Name of the model
        protected_fields: Set of field names that require permission checks

    Returns:
        Modified class with permission checking

    Example:
        PeopleType = create_permission_aware_type(
            PeopleType,
            'People',
            {'mobno', 'email', 'capabilities'}
        )
    """
    original_resolvers = {}

    for field_name in protected_fields:
        resolver_name = f'resolve_{field_name}'

        if hasattr(django_object_type_class, resolver_name):
            original_resolvers[field_name] = getattr(django_object_type_class, resolver_name)
        else:
            def create_default_resolver(fname):
                def default_resolver(parent, info):
                    return getattr(parent, fname, None)
                return default_resolver

            original_resolvers[field_name] = create_default_resolver(field_name)

    for field_name, original_resolver in original_resolvers.items():
        protected_resolver = require_field_permission(model_name, field_name)(original_resolver)
        setattr(django_object_type_class, f'resolve_{field_name}', staticmethod(protected_resolver))

    return django_object_type_class


class GraphQLFieldAccessLog:
    """
    Logging utility for tracking field access patterns and denials.
    """

    @staticmethod
    def log_field_access(user, model_name: str, field_name: str, granted: bool, correlation_id: str = None):
        """Log field access attempt."""
        log_level = logging.DEBUG if granted else logging.WARNING

        graphql_field_logger.log(
            log_level,
            f"Field access {'granted' if granted else 'denied'}: {model_name}.{field_name}",
            extra={
                'user_id': user.id if hasattr(user, 'id') else None,
                'username': getattr(user, 'loginid', str(user)),
                'model': model_name,
                'field': field_name,
                'granted': granted,
                'correlation_id': correlation_id,
                'event_type': 'field_access'
            }
        )

    @staticmethod
    def log_bulk_field_access(user, model_name: str, accessible_fields: List[str],
                              denied_fields: List[str], correlation_id: str = None):
        """Log bulk field access for query optimization."""
        graphql_field_logger.info(
            f"Bulk field access check for {model_name}",
            extra={
                'user_id': user.id if hasattr(user, 'id') else None,
                'username': getattr(user, 'loginid', str(user)),
                'model': model_name,
                'accessible_count': len(accessible_fields),
                'denied_count': len(denied_fields),
                'denied_fields': denied_fields,
                'correlation_id': correlation_id,
                'event_type': 'bulk_field_access'
            }
        )