"""
PII Redaction Serializer Mixin

Provides automatic PII redaction capabilities to Django REST Framework serializers.
Enables field-level, role-based conditional redaction.

Features:
- Configurable field redaction per serializer
- Role-based permissions (owner, admin, third-party)
- Preserves data structure
- Performance optimized
- Audit logging for redacted field access

Usage:
    class JournalEntrySerializer(PIIRedactionMixin, serializers.ModelSerializer):
        PII_FIELDS = ['content', 'gratitude_items', 'affirmations']
        PII_ADMIN_FIELDS = ['title', 'subtitle']

        class Meta:
            model = JournalEntry
            fields = '__all__'

Author: Claude Code
Date: 2025-10-01
"""

from typing import Dict, List, Optional, Any, Set
from rest_framework import serializers
from apps.core.security.pii_redaction import PIIRedactionService
from apps.journal.logging import get_journal_logger
from django.core.cache import cache

logger = get_journal_logger(__name__)


class PIIRedactionMixin:
    """
    Mixin for serializers to enable automatic PII redaction.

    Attributes to set in serializer:
        PII_FIELDS: List of fields to ALWAYS redact for non-owners
        PII_ADMIN_FIELDS: List of fields visible to admins (redacted form)
        PII_SAFE_FIELDS: List of fields never redacted (defaults to metadata)
        PII_AUDIT_ACCESS: Boolean - whether to log field access (default: True)
    """

    # Default safe fields (never redacted)
    DEFAULT_SAFE_FIELDS: Set[str] = {
        'id', 'created_at', 'updated_at', 'timestamp',
        'entry_type', 'privacy_scope', 'sync_status',
        'version', 'is_bookmarked', 'is_draft',
        # Numeric metrics (safe for analytics)
        'mood_rating', 'stress_level', 'energy_level',
        'completion_rate', 'efficiency_score', 'quality_score',
    }

    def __init__(self, *args, **kwargs):
        """Initialize mixin and set up redaction service."""
        super().__init__(*args, **kwargs)
        self.pii_service = PIIRedactionService()
        self._redaction_cache = {}  # Cache redaction decisions for performance
        self._policy_cache = {}  # Cache tenant policies

    def _get_redaction_policy(self, instance):
        """
        Get the redaction policy for the instance's tenant.

        Args:
            instance: Model instance

        Returns:
            RedactionPolicy or None
        """
        # Get tenant from instance
        tenant = getattr(instance, 'tenant', None)
        if not tenant:
            return None

        # Check cache
        cache_key = f'redaction_policy:{tenant.id}'
        if cache_key in self._policy_cache:
            return self._policy_cache[cache_key]

        # Try Django cache first
        policy = cache.get(cache_key)
        if policy:
            self._policy_cache[cache_key] = policy
            return policy

        # Load from database
        try:
            from apps.journal.models.redaction_policy import RedactionPolicy
            policy = RedactionPolicy.get_policy_for_tenant(tenant)

            # Cache for 5 minutes
            cache.set(cache_key, policy, timeout=300)
            self._policy_cache[cache_key] = policy
            return policy
        except Exception as e:
            logger.warning(f"Failed to load redaction policy for tenant {tenant.id}: {e}")
            return None

    def _should_redact_field_by_policy(self, field_name: str, user, instance) -> tuple:
        """
        Check if field should be redacted based on tenant policy.

        Args:
            field_name: Field name to check
            user: User accessing the data
            instance: Model instance

        Returns:
            tuple: (should_redact: bool, redaction_type: str or None)
        """
        policy = self._get_redaction_policy(instance)
        if not policy:
            # No policy - use default behavior
            return self._should_redact_field_default(field_name, user)

        # Determine user role
        is_owner = self._check_ownership(instance, user)
        is_admin = self._check_admin(user)

        if is_owner:
            user_role = 'owner'
        elif is_admin:
            user_role = 'admin'
        elif user and user.is_authenticated:
            user_role = 'user'
        else:
            user_role = 'anonymous'

        return policy.should_redact_field(field_name, user_role)

    def _should_redact_field_default(self, field_name: str, user) -> tuple:
        """
        Default redaction logic when no policy is configured.

        Args:
            field_name: Field name
            user: User

        Returns:
            tuple: (should_redact: bool, redaction_type: str or None)
        """
        # Get configured fields from serializer
        pii_fields = getattr(self, 'PII_FIELDS', [])
        admin_fields = getattr(self, 'PII_ADMIN_FIELDS', [])

        is_admin = self._check_admin(user)

        if field_name in pii_fields:
            return (True, 'full')
        elif field_name in admin_fields:
            if is_admin:
                return (True, 'partial')
            else:
                return (True, 'full')

        return (False, None)

    def to_representation(self, instance):
        """
        Override to_representation to apply PII redaction.

        Args:
            instance: Model instance to serialize

        Returns:
            dict: Serialized data with PII redacted based on permissions
        """
        # Get base representation
        representation = super().to_representation(instance)

        # Get request context
        request = self.context.get('request')
        if not request:
            # No request context - apply strict redaction
            return self._apply_strict_redaction(representation)

        # Determine user permissions
        user = request.user if hasattr(request, 'user') else None
        is_owner = self._check_ownership(instance, user)
        is_admin = self._check_admin(user)

        # Owner sees all their data
        if is_owner:
            return representation

        # Apply conditional redaction
        return self._apply_conditional_redaction(
            representation,
            instance,
            user,
            is_admin
        )

    def _check_ownership(self, instance, user) -> bool:
        """
        Check if user owns this instance.

        Args:
            instance: Model instance
            user: Requesting user

        Returns:
            bool: True if user owns this instance
        """
        if not user or not user.is_authenticated:
            return False

        # Check if instance has a 'user' field
        if hasattr(instance, 'user'):
            return instance.user == user

        # Check if instance has a 'user_id' field
        if hasattr(instance, 'user_id'):
            return instance.user_id == user.id

        return False

    def _check_admin(self, user) -> bool:
        """Check if user has admin privileges."""
        if not user or not user.is_authenticated:
            return False
        return user.is_superuser or user.is_staff

    def _apply_conditional_redaction(
        self,
        representation: Dict[str, Any],
        instance,
        user,
        is_admin: bool
    ) -> Dict[str, Any]:
        """
        Apply conditional PII redaction based on user role.

        Args:
            representation: Serialized data
            instance: Model instance
            user: Requesting user
            is_admin: Whether user is admin

        Returns:
            dict: Redacted representation
        """
        # Get redaction configuration from serializer
        pii_fields = getattr(self, 'PII_FIELDS', [])
        pii_admin_fields = getattr(self, 'PII_ADMIN_FIELDS', [])
        safe_fields = getattr(self, 'PII_SAFE_FIELDS', self.DEFAULT_SAFE_FIELDS)
        audit_access = getattr(self, 'PII_AUDIT_ACCESS', True)

        redacted = {}

        for key, value in representation.items():
            # Always safe fields - never redact
            if key in safe_fields:
                redacted[key] = value

            # Always redact for non-owners
            elif key in pii_fields:
                redacted[key] = self._get_redacted_value(key, value)

                # Audit log if enabled
                if audit_access:
                    self._audit_redacted_access(instance, user, key)

            # Admin-visible fields (show redacted marker)
            elif key in pii_admin_fields:
                if is_admin:
                    redacted[key] = f"[{key.upper()}]"
                else:
                    redacted[key] = '[REDACTED]'

                if audit_access and is_admin:
                    self._audit_admin_access(instance, user, key)

            # User name fields - special handling
            elif key in ['user_name', 'peoplename', 'created_by_name']:
                if is_admin:
                    redacted[key] = self._partially_redact_name(value)
                else:
                    redacted[key] = '[USER]'

            # Default: pass through
            else:
                redacted[key] = value

        return redacted

    def _apply_strict_redaction(self, representation: Dict[str, Any]) -> Dict[str, Any]:
        """
        Apply strict redaction when no user context available.

        Args:
            representation: Serialized data

        Returns:
            dict: Strictly redacted representation
        """
        pii_fields = getattr(self, 'PII_FIELDS', [])
        pii_admin_fields = getattr(self, 'PII_ADMIN_FIELDS', [])
        safe_fields = getattr(self, 'PII_SAFE_FIELDS', self.DEFAULT_SAFE_FIELDS)

        redacted = {}

        for key, value in representation.items():
            if key in safe_fields:
                redacted[key] = value
            elif key in pii_fields or key in pii_admin_fields:
                redacted[key] = '[REDACTED]'
            elif key in ['user_name', 'peoplename', 'created_by_name']:
                redacted[key] = '[USER]'
            else:
                redacted[key] = value

        return redacted

    def _get_redacted_value(self, field_name: str, value: Any) -> Any:
        """
        Get appropriate redacted value based on field type and value.

        Args:
            field_name: Name of the field
            value: Original value

        Returns:
            Any: Redacted value
        """
        if value is None:
            return None

        # String fields
        if isinstance(value, str):
            return '[REDACTED]'

        # List fields (preserve structure)
        elif isinstance(value, list):
            if value:
                return ['[REDACTED]'] * len(value)
            return []

        # Dict fields
        elif isinstance(value, dict):
            return {'redacted': True}

        # Numeric fields (shouldn't be in PII_FIELDS, but handle gracefully)
        elif isinstance(value, (int, float)):
            logger.warning(f"Numeric field '{field_name}' in PII_FIELDS - should be in safe fields")
            return value

        # Default
        else:
            return '[REDACTED]'

    def _partially_redact_name(self, name: str) -> str:
        """
        Partially redact name for admin visibility.

        Args:
            name: Full name

        Returns:
            str: Partially redacted name

        Example:
            "John Doe" -> "J*** D***"
            "Alice" -> "A***"
        """
        if not name or not isinstance(name, str):
            return '[USER]'

        parts = name.split()
        if len(parts) == 0:
            return '[USER]'

        redacted_parts = [
            f"{part[0]}***" if len(part) > 1 else part
            for part in parts
        ]

        return ' '.join(redacted_parts)

    def _audit_redacted_access(self, instance, user, field_name: str):
        """
        Audit log access to redacted field.

        Args:
            instance: Model instance
            user: Requesting user
            field_name: Field that was redacted
        """
        # Log redacted field access for compliance
        logger.info(
            f"PII field '{field_name}' redacted for non-owner",
            extra={
                'instance_id': str(getattr(instance, 'id', 'unknown')),
                'instance_type': instance.__class__.__name__,
                'requesting_user_id': str(user.id) if user else 'anonymous',
                'redacted_field': field_name,
                'action': 'field_redacted'
            }
        )

    def _audit_admin_access(self, instance, user, field_name: str):
        """
        Audit log admin access to sensitive field.

        Args:
            instance: Model instance
            user: Admin user
            field_name: Field accessed by admin
        """
        # Log admin access for compliance
        logger.warning(
            f"Admin accessed sensitive field '{field_name}'",
            extra={
                'instance_id': str(getattr(instance, 'id', 'unknown')),
                'instance_type': instance.__class__.__name__,
                'admin_user_id': str(user.id) if user else 'unknown',
                'accessed_field': field_name,
                'action': 'admin_field_access'
            }
        )


class WellnessPIIRedactionMixin(PIIRedactionMixin):
    """
    Wellness-specific PII redaction mixin.

    Extends PIIRedactionMixin with wellness-specific defaults.
    """

    # Wellness-specific safe fields
    DEFAULT_SAFE_FIELDS = PIIRedactionMixin.DEFAULT_SAFE_FIELDS | {
        'interaction_type',
        'completion_percentage',
        'time_spent_seconds',
        'user_rating',
        'action_taken',
        'delivery_context',
        'current_streak',
        'longest_streak',
        'total_content_viewed',
        'total_content_completed',
        'total_score',
    }
