"""
Base Serializers with Comprehensive Validation

Provides secure base classes for REST Framework serializers that enforce
input validation, sanitization, and business rule compliance.

Compliance with Rule #13: Form Validation Requirements
- All serializers must have explicit field lists
- All serializers must have custom validation methods
- All serializers must implement business rule validation
"""

from rest_framework import serializers
from django.core.exceptions import ValidationError as DjangoValidationError
from apps.core.utils_new.form_security import InputSanitizer, FormValidators
from apps.core.utils_new.code_validators import (
    validate_peoplecode,
    validate_loginid,
    validate_mobile_number,
    validate_name,
)
import logging

logger = logging.getLogger(__name__)


class SecureSerializerMixin:
    """
    Mixin providing common validation patterns for all serializers.

    Features:
    - Automatic XSS protection for text fields
    - Code field sanitization
    - Email/phone validation
    - Business rule validation hooks
    """

    xss_protect_fields = []
    code_fields = []
    name_fields = []
    email_fields = []
    phone_fields = []

    def validate(self, attrs):
        """
        Cross-field validation with automatic sanitization.
        Override in subclasses for custom business rules.
        """
        attrs = super().validate(attrs)
        attrs = self._sanitize_inputs(attrs)
        attrs = self._validate_business_rules(attrs)
        return attrs

    def _sanitize_inputs(self, attrs):
        """Sanitize all input fields based on configuration."""
        for field_name in self.xss_protect_fields:
            if field_name in attrs and attrs[field_name]:
                attrs[field_name] = InputSanitizer.sanitize_text(attrs[field_name])

        for field_name in self.code_fields:
            if field_name in attrs and attrs[field_name]:
                attrs[field_name] = InputSanitizer.sanitize_code(attrs[field_name])

        for field_name in self.name_fields:
            if field_name in attrs and attrs[field_name]:
                attrs[field_name] = InputSanitizer.sanitize_name(attrs[field_name])

        for field_name in self.email_fields:
            if field_name in attrs and attrs[field_name]:
                attrs[field_name] = InputSanitizer.sanitize_email(attrs[field_name])

        for field_name in self.phone_fields:
            if field_name in attrs and attrs[field_name]:
                attrs[field_name] = InputSanitizer.sanitize_phone(attrs[field_name])

        return attrs

    def _validate_business_rules(self, attrs):
        """
        Hook for business rule validation.
        Override in subclasses to implement specific business rules.
        """
        return attrs

    def validate_code_uniqueness(self, value, model_class, field_name, exclude_id=None):
        """
        Validate that a code is unique within the model.

        Args:
            value: Code value to validate
            model_class: Model class to check against
            field_name: Name of the code field
            exclude_id: ID to exclude from uniqueness check (for updates)
        """
        from django.db.models import Q

        query = Q(**{field_name: value})
        if exclude_id:
            query &= ~Q(id=exclude_id)

        if hasattr(model_class, 'client_id'):
            client_id = self.context.get('client_id')
            if client_id:
                query &= Q(client_id=client_id)

        if model_class.objects.filter(query).exists():
            raise serializers.ValidationError(
                f"{field_name.title()} '{value}' already exists. Please choose a different code."
            )

        return value


class ValidatedModelSerializer(SecureSerializerMixin, serializers.ModelSerializer):
    """
    Base ModelSerializer with comprehensive validation.

    All model serializers should inherit from this class to ensure
    compliance with Rule #13 validation requirements.

    Usage:
        class MyModelSerializer(ValidatedModelSerializer):
            xss_protect_fields = ['description', 'comments']
            code_fields = ['mycode']
            name_fields = ['myname']

            class Meta:
                model = MyModel
                fields = ['id', 'mycode', 'myname', ...]  # Explicit fields required
                read_only_fields = ['id', 'created_at', 'updated_at']

            def validate_mycode(self, value):
                # Field-specific validation
                return value

            def validate(self, attrs):
                attrs = super().validate(attrs)
                # Cross-field validation
                return attrs
    """

    def validate(self, attrs):
        """Enforce validation rules."""
        attrs = super().validate(attrs)

        model_name = self.Meta.model.__name__

        if hasattr(self.Meta, 'fields') and self.Meta.fields == '__all__':
            raise serializers.ValidationError(
                f"{model_name}Serializer violates Rule #13: "
                f"Must use explicit field list instead of fields='__all__'"
            )

        return attrs


class TenantAwareSerializer(ValidatedModelSerializer):
    """
    Base serializer for tenant-aware models.

    Automatically validates tenant isolation and access control.
    """

    def validate(self, attrs):
        """Validate tenant isolation."""
        attrs = super().validate(attrs)

        request = self.context.get('request')
        if request and hasattr(request, 'user'):
            if hasattr(self.Meta.model, 'client_id'):
                attrs['client_id'] = request.user.client_id
            if hasattr(self.Meta.model, 'bu_id'):
                attrs['bu_id'] = request.user.bu_id

        return attrs

    def _validate_business_rules(self, attrs):
        """Validate tenant-specific business rules."""
        attrs = super()._validate_business_rules(attrs)

        if 'enable' in attrs and not attrs.get('enable'):
            logger.info(
                f"Disabling {self.Meta.model.__name__}",
                extra={
                    'model': self.Meta.model.__name__,
                    'instance_id': getattr(self.instance, 'id', None)
                }
            )

        return attrs