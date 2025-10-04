"""
NOC API Key Serializers.

Serializers for NOC API key management.
Follows .claude/rules.md Rule #7 (serializers <150 lines).
"""

from rest_framework import serializers
from apps.core.models.monitoring_api_key import MonitoringAPIKey, MonitoringPermission

__all__ = [
    'NOCAPIKeySerializer',
    'NOCAPIKeyCreateSerializer',
    'APIKeyUsageSerializer',
]


class NOCAPIKeySerializer(serializers.ModelSerializer):
    """Display serializer for NOC API keys."""

    created_by_name = serializers.CharField(
        source='created_by.peoplename',
        read_only=True,
        allow_null=True
    )

    is_expired = serializers.SerializerMethodField()
    needs_rotation = serializers.SerializerMethodField()

    class Meta:
        model = MonitoringAPIKey
        fields = [
            'id', 'name', 'description', 'monitoring_system',
            'permissions', 'allowed_ips', 'is_active',
            'created_by_name', 'created_at', 'expires_at',
            'last_used_at', 'usage_count', 'rotation_schedule',
            'next_rotation_at', 'is_expired', 'needs_rotation', 'metadata'
        ]
        read_only_fields = [
            'id', 'created_by_name', 'created_at', 'last_used_at',
            'usage_count', 'is_expired', 'needs_rotation'
        ]

    def get_is_expired(self, obj):
        """Check if key has expired."""
        return obj.is_expired()

    def get_needs_rotation(self, obj):
        """Check if key needs rotation."""
        return obj.needs_rotation()


class NOCAPIKeyCreateSerializer(serializers.Serializer):
    """Serializer for creating NOC API keys."""

    name = serializers.CharField(
        max_length=100,
        required=True,
        help_text="Descriptive name for the API key"
    )

    description = serializers.CharField(
        required=False,
        allow_blank=True,
        help_text="Purpose and usage notes"
    )

    monitoring_system = serializers.ChoiceField(
        choices=MonitoringAPIKey._meta.get_field('monitoring_system').choices,
        default='custom',
        help_text="Type of monitoring system using this key"
    )

    permissions = serializers.ListField(
        child=serializers.ChoiceField(choices=MonitoringPermission.choices),
        required=True,
        min_length=1,
        help_text="List of NOC permissions (health, metrics, alerts, etc.)"
    )

    allowed_ips = serializers.ListField(
        child=serializers.IPAddressField(),
        required=False,
        allow_null=True,
        allow_empty=True,
        help_text="Whitelisted IP addresses (null = all IPs allowed)"
    )

    expires_days = serializers.IntegerField(
        required=False,
        allow_null=True,
        min_value=1,
        max_value=3650,
        help_text="Days until expiration (null = never expires)"
    )

    rotation_schedule = serializers.ChoiceField(
        choices=MonitoringAPIKey._meta.get_field('rotation_schedule').choices,
        default='quarterly',
        help_text="Automatic rotation schedule"
    )

    def validate_permissions(self, value):
        """Validate NOC-specific permissions."""
        noc_permissions = [
            MonitoringPermission.HEALTH.value,
            MonitoringPermission.METRICS.value,
            MonitoringPermission.ALERTS.value,
            MonitoringPermission.DASHBOARD.value,
        ]

        for perm in value:
            if perm not in noc_permissions and perm != MonitoringPermission.ADMIN.value:
                raise serializers.ValidationError(
                    f"Invalid NOC permission: {perm}. "
                    f"Allowed: {noc_permissions} or admin"
                )

        return value

    def create(self, validated_data):
        """Create new NOC API key."""
        user = self.context['request'].user

        instance, api_key = MonitoringAPIKey.create_key(
            name=validated_data['name'],
            monitoring_system=validated_data.get('monitoring_system', 'custom'),
            permissions=validated_data['permissions'],
            allowed_ips=validated_data.get('allowed_ips'),
            expires_days=validated_data.get('expires_days'),
            created_by=user,
            description=validated_data.get('description', ''),
            rotation_schedule=validated_data.get('rotation_schedule', 'quarterly')
        )

        instance.raw_api_key = api_key
        return instance


class APIKeyUsageSerializer(serializers.Serializer):
    """Serializer for API key usage statistics."""

    api_key_id = serializers.IntegerField(read_only=True)
    api_key_name = serializers.CharField(read_only=True)
    total_requests = serializers.IntegerField(read_only=True)
    unique_ips = serializers.IntegerField(read_only=True)
    by_endpoint = serializers.ListField(read_only=True)
    by_status = serializers.ListField(read_only=True)
    avg_response_time = serializers.FloatField(read_only=True)
    error_count = serializers.IntegerField(read_only=True)
    period_days = serializers.IntegerField(read_only=True)