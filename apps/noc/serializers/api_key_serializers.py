"""
NOC API Key Serializers.

Serializers for NOC API key management.
Follows .claude/rules.md Rule #7 (serializers <150 lines).

Ontology: data_contract=True, api_layer=True, validation_rules=True, security_critical=True
Category: serializers, api_keys, noc, monitoring
Domain: api_key_management, noc_security, key_rotation, access_control
Responsibility: API key CRUD; rotation scheduling; expiry validation; permission enforcement
Dependencies: noc.models (MonitoringAPIKey, MonitoringPermission), rest_framework
Security: API key hashing (never returns raw key after creation), IP whitelisting, permission scoping
Validation: NOC-specific permissions, IP format, expiry dates, rotation schedules
API: REST v1 /api/v1/noc/api-keys/*, admin-only endpoints
Key Rotation: Automatic rotation schedules (monthly, quarterly, biannually, annually, never)
Permissions: health, metrics, alerts, dashboard, admin (NOC-specific scopes)
"""

from rest_framework import serializers
from apps.core.models.monitoring_api_key import MonitoringAPIKey, MonitoringPermission

__all__ = [
    'NOCAPIKeySerializer',
    'NOCAPIKeyCreateSerializer',
    'APIKeyUsageSerializer',
]


class NOCAPIKeySerializer(serializers.ModelSerializer):
    """
    Display serializer for NOC API keys.

    Ontology: data_contract=True
    Purpose: Read-only API key details (NEVER returns raw key)
    Fields: 14 fields including computed is_expired, needs_rotation
    Read-Only: id, created_by_name, timestamps, usage_count, computed fields
    Computed Fields:
      - is_expired: Calls obj.is_expired() (checks expires_at < now)
      - needs_rotation: Calls obj.needs_rotation() (checks next_rotation_at < now)
    Security: Raw API key NEVER exposed (only on creation via NOCAPIKeyCreateSerializer)
    Use Case: List/detail API key info, rotation monitoring dashboard
    """

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

    def get_is_expired(self, obj) -> bool:
        """Check if key has expired."""
        return obj.is_expired()

    def get_needs_rotation(self, obj) -> bool:
        """Check if key needs rotation."""
        return obj.needs_rotation()


class NOCAPIKeyCreateSerializer(serializers.Serializer):
    """
    Serializer for creating NOC API keys.

    Ontology: data_contract=True, validation_rules=True, security_critical=True
    Purpose: Create new API key with permission scoping and rotation schedule
    Model: None (Serializer, not ModelSerializer - custom create logic)
    Fields: 7 fields (name, permissions, allowed_ips, expiry, rotation)
    Validation: NOC permission whitelist, IP format, expiry range (1-3650 days)
    Security: Returns raw API key ONLY on creation (stored as hash)
    Validation Rules:
      - permissions: Must be NOC-specific (health, metrics, alerts, dashboard) or admin
      - allowed_ips: Optional IP whitelist (null = allow all)
      - expires_days: 1-3650 days (null = never expires)
      - rotation_schedule: monthly, quarterly, biannually, annually, never
    Use Case: NOC admin creates API keys for external monitoring systems
    Create Flow: Calls MonitoringAPIKey.create_key() which returns (instance, raw_key)
    """

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
        """
        Validate NOC-specific permissions.

        Ontology: validation_rules=True, security_critical=True
        Validates: Permission whitelist for NOC operations
        Allowed Permissions:
          - health: /noc/health endpoint
          - metrics: /noc/metrics endpoint
          - alerts: /noc/alerts endpoint
          - dashboard: /noc/dashboard endpoint
          - admin: All NOC endpoints (superuser-equivalent)
        Security: Prevents granting non-NOC permissions via NOC API keys
        """
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
        """
        Create new NOC API key.

        Ontology: security_critical=True
        Returns: Instance with raw_api_key attribute (ONLY time raw key is exposed)
        Flow: MonitoringAPIKey.create_key() generates key, hashes it, returns (instance, raw_key)
        Security: Raw key stored in instance.raw_api_key for one-time display to user
        Storage: Only hash stored in database, raw key never retrievable
        """
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
    """
    Serializer for API key usage statistics.

    Ontology: data_contract=True
    Purpose: Read-only usage analytics for API key monitoring
    Model: None (output-only serializer)
    Fields: 9 fields (request counts, IPs, endpoints, response times)
    Read-Only: All fields (computed from logs)
    Use Case: NOC dashboard, API key rotation decisions, anomaly detection
    Data Source: Aggregated from API request logs (MonitoringAPIKey.usage_count)
    """

    api_key_id = serializers.IntegerField(read_only=True)
    api_key_name = serializers.CharField(read_only=True)
    total_requests = serializers.IntegerField(read_only=True)
    unique_ips = serializers.IntegerField(read_only=True)
    by_endpoint = serializers.ListField(read_only=True)
    by_status = serializers.ListField(read_only=True)
    avg_response_time = serializers.FloatField(read_only=True)
    error_count = serializers.IntegerField(read_only=True)
    period_days = serializers.IntegerField(read_only=True)
