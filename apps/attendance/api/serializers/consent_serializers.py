"""
Consent Management Serializers

Serializers for consent management API endpoints.
"""

from rest_framework import serializers
from apps.attendance.models.consent import (
    ConsentPolicy,
    EmployeeConsentLog,
    ConsentRequirement
)
from django.contrib.auth import get_user_model

User = get_user_model()


class ConsentPolicySerializer(serializers.ModelSerializer):
    """
    Serializer for consent policies.

    Read-only for employees, writable for admins.
    """

    policy_type_display = serializers.CharField(source='get_policy_type_display', read_only=True)
    state_display = serializers.CharField(source='get_state_display', read_only=True)

    # Computed fields
    is_expired = serializers.SerializerMethodField()
    days_until_expiration = serializers.SerializerMethodField()

    class Meta:
        model = ConsentPolicy
        fields = [
            'id',
            'uuid',
            'policy_type',
            'policy_type_display',
            'state',
            'state_display',
            'version',
            'title',
            'policy_text',
            'summary',
            'effective_date',
            'expiration_date',
            'is_active',
            'requires_signature',
            'requires_written_consent',
            'is_expired',
            'days_until_expiration',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['uuid', 'created_at', 'updated_at']

    def get_is_expired(self, obj):
        """Check if policy is expired"""
        from django.utils import timezone
        if not obj.expiration_date:
            return False
        return obj.expiration_date < timezone.now().date()

    def get_days_until_expiration(self, obj):
        """Get days until policy expires"""
        from django.utils import timezone
        if not obj.expiration_date:
            return None
        delta = obj.expiration_date - timezone.now().date()
        return delta.days if delta.days > 0 else 0


class EmployeeConsentLogSerializer(serializers.ModelSerializer):
    """
    Serializer for employee consent logs.
    """

    employee_name = serializers.CharField(source='employee.username', read_only=True)
    employee_email = serializers.CharField(source='employee.email', read_only=True)
    policy = ConsentPolicySerializer(read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)

    # Computed fields
    is_active = serializers.SerializerMethodField()
    is_expired = serializers.BooleanField(read_only=True)
    days_until_expiration = serializers.IntegerField(read_only=True)

    class Meta:
        model = EmployeeConsentLog
        fields = [
            'id',
            'uuid',
            'employee',
            'employee_name',
            'employee_email',
            'policy',
            'status',
            'status_display',
            'granted_at',
            'granted_ip',
            'signature_type',
            'revoked_at',
            'revoked_reason',
            'expires_at',
            'is_active',
            'is_expired',
            'days_until_expiration',
            'notification_sent_at',
            'reminder_sent_at',
            'notes',
            'created_at',
            'updated_at',
        ]
        read_only_fields = [
            'uuid',
            'granted_at',
            'granted_ip',
            'revoked_at',
            'notification_sent_at',
            'reminder_sent_at',
            'created_at',
            'updated_at',
        ]

    def get_is_active(self, obj):
        """Check if consent is currently active"""
        return obj.is_active()


class ConsentGrantSerializer(serializers.Serializer):
    """
    Serializer for granting consent.

    Used when employee accepts a consent policy.
    """

    policy_id = serializers.IntegerField(
        required=True,
        help_text="ID of the consent policy to accept"
    )

    signature_data = serializers.CharField(
        required=False,
        allow_blank=True,
        help_text="Digital signature data (base64 image or typed name)"
    )

    signature_type = serializers.ChoiceField(
        choices=['TYPED', 'DRAWN', 'ELECTRONIC'],
        default='ELECTRONIC',
        help_text="Type of signature provided"
    )

    def validate_policy_id(self, value):
        """Validate policy exists and is active"""
        try:
            policy = ConsentPolicy.objects.get(id=value, is_active=True)
            return value
        except ConsentPolicy.DoesNotExist:
            raise serializers.ValidationError("Policy not found or not active")


class ConsentRevokeSerializer(serializers.Serializer):
    """
    Serializer for revoking consent.
    """

    consent_id = serializers.IntegerField(
        required=True,
        help_text="ID of the consent log to revoke"
    )

    reason = serializers.CharField(
        required=True,
        max_length=500,
        help_text="Reason for revoking consent"
    )

    def validate_reason(self, value):
        """Validate reason is not empty"""
        if not value or len(value.strip()) < 10:
            raise serializers.ValidationError("Please provide a detailed reason (minimum 10 characters)")
        return value


class ConsentRequestSerializer(serializers.Serializer):
    """
    Serializer for admin requesting consent from employee.
    """

    employee_id = serializers.IntegerField(
        required=True,
        help_text="ID of employee to request consent from"
    )

    policy_id = serializers.IntegerField(
        required=True,
        help_text="ID of consent policy"
    )

    send_notification = serializers.BooleanField(
        default=True,
        help_text="Whether to send email notification"
    )

    def validate_employee_id(self, value):
        """Validate employee exists"""
        try:
            User.objects.get(id=value)
            return value
        except User.DoesNotExist:
            raise serializers.ValidationError("Employee not found")

    def validate_policy_id(self, value):
        """Validate policy exists"""
        try:
            ConsentPolicy.objects.get(id=value, is_active=True)
            return value
        except ConsentPolicy.DoesNotExist:
            raise serializers.ValidationError("Policy not found or not active")


class ConsentStatusSerializer(serializers.Serializer):
    """
    Serializer for consent status check response.
    """

    can_clock_in = serializers.BooleanField()
    has_all_required_consents = serializers.BooleanField()
    missing_consents = serializers.ListField(
        child=serializers.DictField(),
        help_text="List of missing consent policies"
    )


class ConsentRequirementSerializer(serializers.ModelSerializer):
    """
    Serializer for consent requirements.
    """

    policy = ConsentPolicySerializer(read_only=True)
    client_name = serializers.CharField(source='client.name', read_only=True)
    bu_name = serializers.CharField(source='bu.name', read_only=True)

    class Meta:
        model = ConsentRequirement
        fields = [
            'id',
            'policy',
            'client',
            'client_name',
            'bu',
            'bu_name',
            'role',
            'state',
            'is_mandatory',
            'blocks_clock_in',
            'grace_period_days',
            'reminder_days_before_expiration',
            'is_active',
        ]
        read_only_fields = ['id']
