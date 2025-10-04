from rest_framework import serializers
from django.utils import timezone
from .models import People
from apps.core.serializers import (
    ValidatedModelSerializer,
    validate_code_field,
    validate_name_field,
    validate_email_field,
    validate_phone_field,
)
import logging

logger = logging.getLogger(__name__)


class PeopleSerializer(ValidatedModelSerializer):
    """
    Secure People serializer with comprehensive validation and privacy protection.

    Privacy Features:
        - Sensitive fields (email, mobno) have masked display variants
        - Password is write-only and never serialized for output
        - Masked display fields for API responses
        - Raw values only accessible through explicit field access

    Compliance with Rule #13: Form Validation Requirements
    - Explicit field list (no __all__)
    - Field-level validation (validate_fieldname methods)
    - Cross-field validation (validate method)
    - Business rule validation

    Security:
        - GDPR compliant data exposure
        - Prevents accidental sensitive data leaks in API responses
        - Audit logging via MaskedSecureValue
    """

    xss_protect_fields = ['peoplename']
    code_fields = ['peoplecode', 'loginid']
    name_fields = ['peoplename']
    email_fields = ['email']
    phone_fields = ['mobno']

    # Add read-only masked display fields
    email_display = serializers.SerializerMethodField()
    mobno_display = serializers.SerializerMethodField()

    class Meta:
        model = People
        fields = [
            'id',
            'uuid',
            'peoplecode',
            'peoplename',
            'loginid',
            'email',
            'email_display',    # Privacy-safe display
            'mobno',
            'mobno_display',    # Privacy-safe display
            'peopleimg',
            'gender',
            'dateofbirth',
            'dateofjoin',
            'dateofreport',
            'enable',
            'isverified',
            'isadmin',
            'peopletype',
            'department',
            'designation',
            'worktype',
            'reportto',
            'location',
            'bu',
            'client',
            'deviceid',
            'ctzoffset',
            'people_extras',
            'created_at',
            'updated_at',
        ]
        read_only_fields = [
            'id',
            'uuid',
            'created_at',
            'updated_at',
            'last_login',
            'email_display',
            'mobno_display',
        ]

    def validate_peoplecode(self, value):
        """Validate people code format and uniqueness."""
        if not value:
            raise serializers.ValidationError("People code is required")

        value = validate_code_field(value)

        instance_id = self.instance.id if self.instance else None
        self.validate_code_uniqueness(
            value, People, 'peoplecode', exclude_id=instance_id
        )

        return value

    def validate_loginid(self, value):
        """Validate login ID format and uniqueness."""
        if not value:
            raise serializers.ValidationError("Login ID is required")

        value = value.strip()

        if ' ' in value:
            raise serializers.ValidationError("Spaces not allowed in login ID")

        if len(value) < 4:
            raise serializers.ValidationError("Login ID must be at least 4 characters")

        instance_id = self.instance.id if self.instance else None
        from django.db.models import Q
        query = Q(loginid=value)
        if instance_id:
            query &= ~Q(id=instance_id)

        if People.objects.filter(query).exists():
            raise serializers.ValidationError("Login ID already exists")

        return value

    def validate_email(self, value):
        """Validate email format and uniqueness."""
        if not value:
            return value

        value = validate_email_field(value)

        instance_id = self.instance.id if self.instance else None
        from django.db.models import Q
        query = Q(email=value)
        if instance_id:
            query &= ~Q(id=instance_id)

        if People.objects.filter(query).exists():
            raise serializers.ValidationError("Email already registered")

        return value

    def validate_mobno(self, value):
        """Validate mobile number format."""
        if not value:
            return value

        value = validate_phone_field(value)
        return value

    def validate_dateofbirth(self, value):
        """Validate date of birth is in the past."""
        if value and value >= timezone.now().date():
            raise serializers.ValidationError("Date of birth must be in the past")
        return value

    def validate_dateofjoin(self, value):
        """Validate date of joining."""
        if value and value > timezone.now().date():
            raise serializers.ValidationError("Date of joining cannot be in the future")
        return value

    def validate(self, attrs):
        """Cross-field validation and business rules."""
        attrs = super().validate(attrs)

        dob = attrs.get('dateofbirth') or (self.instance.dateofbirth if self.instance else None)
        doj = attrs.get('dateofjoin') or (self.instance.dateofjoin if self.instance else None)
        dor = attrs.get('dateofreport') or (self.instance.dateofreport if self.instance else None)

        if dob and doj:
            if dob == doj:
                raise serializers.ValidationError(
                    "Date of birth and date of joining cannot be equal"
                )
            if dob >= doj:
                raise serializers.ValidationError(
                    "Date of birth must be before date of joining"
                )

        if dob and dor:
            if dob >= dor:
                raise serializers.ValidationError(
                    "Date of birth must be before date of release"
                )

        if not self.instance and not attrs.get('enable', True):
            logger.warning("Creating disabled user account")

        return attrs

    def get_email_display(self, obj):
        """
        Return masked email for safe display in API responses.

        Security:
            - Shows only first 2 characters and domain TLD
            - Prevents accidental PII exposure in API logs
            - GDPR compliant

        Returns:
            str: Masked email (e.g., "us****@***.com") or None
        """
        if not obj.email:
            return None

        # The email field returns MaskedSecureValue, str() uses __str__() masking
        email_str = str(obj.email)

        # If already masked, return it
        if '*' in email_str:
            return email_str

        # Fallback: manual masking (should not be reached due to MaskedSecureValue)
        if '@' in email_str:
            local, domain = email_str.split('@', 1)
            masked_local = f"{local[:2]}****" if len(local) > 2 else "****"

            domain_parts = domain.split('.')
            masked_domain = f"***.{domain_parts[-1]}" if len(domain_parts) > 1 else "***"

            return f"{masked_local}@{masked_domain}"

        return "****@***"

    def get_mobno_display(self, obj):
        """
        Return masked mobile number for safe display in API responses.

        Security:
            - Shows only first 3 and last 2 digits
            - Prevents accidental PII exposure in API logs
            - GDPR compliant

        Returns:
            str: Masked mobile (e.g., "+91****12") or None
        """
        if not obj.mobno:
            return None

        # The mobno field returns MaskedSecureValue, str() uses __str__() masking
        mobno_str = str(obj.mobno)

        # If already masked, return it
        if '*' in mobno_str:
            return mobno_str

        # Fallback: manual masking (should not be reached due to MaskedSecureValue)
        if len(mobno_str) > 5:
            return f"{mobno_str[:3]}****{mobno_str[-2:]}"

        return "********"
