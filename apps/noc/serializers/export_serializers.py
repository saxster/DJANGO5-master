"""
NOC Export Serializers.

Serializers for export templates, history, and export requests.
Follows .claude/rules.md Rule #7 (serializers <150 lines).
"""

from rest_framework import serializers
from apps.noc.models import NOCExportTemplate, NOCExportHistory

__all__ = [
    'NOCExportTemplateSerializer',
    'NOCExportTemplateListSerializer',
    'NOCExportHistorySerializer',
    'ExportRequestSerializer',
]


class NOCExportTemplateSerializer(serializers.ModelSerializer):
    """Full export template serializer for CRUD operations."""

    user_name = serializers.CharField(
        source='user.peoplename',
        read_only=True
    )

    class Meta:
        model = NOCExportTemplate
        fields = [
            'id', 'user', 'user_name', 'name', 'description',
            'entity_type', 'format', 'filters', 'columns',
            'is_public', 'usage_count', 'cdtz', 'mdtz'
        ]
        read_only_fields = ['id', 'user_name', 'usage_count', 'cdtz', 'mdtz']

    def validate_filters(self, value):
        """Validate filter structure."""
        if not isinstance(value, dict):
            raise serializers.ValidationError("Filters must be a dictionary")

        valid_keys = {
            'client_ids', 'severities', 'statuses',
            'days', 'status', 'severity'
        }

        if not set(value.keys()).issubset(valid_keys):
            raise serializers.ValidationError(
                f"Invalid filter keys. Allowed: {valid_keys}"
            )

        return value

    def validate_columns(self, value):
        """Validate columns list."""
        if value is not None and not isinstance(value, list):
            raise serializers.ValidationError("Columns must be a list or null")

        return value


class NOCExportTemplateListSerializer(serializers.ModelSerializer):
    """Lightweight export template serializer for list views."""

    user_name = serializers.CharField(
        source='user.peoplename',
        read_only=True
    )

    class Meta:
        model = NOCExportTemplate
        fields = [
            'id', 'name', 'entity_type', 'format',
            'is_public', 'usage_count', 'user_name'
        ]


class NOCExportHistorySerializer(serializers.ModelSerializer):
    """Export history serializer for audit display."""

    user_name = serializers.CharField(
        source='user.peoplename',
        read_only=True
    )

    template_name = serializers.CharField(
        source='template.name',
        read_only=True,
        allow_null=True
    )

    file_size_mb = serializers.SerializerMethodField()

    class Meta:
        model = NOCExportHistory
        fields = [
            'id', 'user_name', 'template_name', 'entity_type',
            'format', 'record_count', 'file_size_bytes', 'file_size_mb',
            'filters_used', 'ip_address', 'cdtz', 'expires_at'
        ]
        read_only_fields = '__all__'

    def get_file_size_mb(self, obj):
        """Calculate file size in MB."""
        if obj.file_size_bytes:
            return round(obj.file_size_bytes / (1024 * 1024), 2)
        return None


class ExportRequestSerializer(serializers.Serializer):
    """Validate export request parameters."""

    entity_type = serializers.ChoiceField(
        choices=['alerts', 'incidents', 'snapshots', 'audit'],
        required=True
    )

    format = serializers.ChoiceField(
        choices=['csv', 'json'],
        default='csv'
    )

    template_id = serializers.IntegerField(
        required=False,
        allow_null=True,
        help_text="Optional export template to use"
    )

    days = serializers.IntegerField(
        default=30,
        min_value=1,
        max_value=365,
        help_text="Number of days to include in export"
    )

    client_ids = serializers.ListField(
        child=serializers.IntegerField(),
        required=False,
        allow_empty=True,
        help_text="Filter by specific client IDs"
    )

    severity = serializers.ChoiceField(
        choices=['INFO', 'LOW', 'MEDIUM', 'HIGH', 'CRITICAL'],
        required=False,
        allow_null=True,
        help_text="Filter by severity (alerts only)"
    )

    status = serializers.ChoiceField(
        choices=['NEW', 'ACKNOWLEDGED', 'ASSIGNED', 'ESCALATED', 'RESOLVED', 'SUPPRESSED'],
        required=False,
        allow_null=True,
        help_text="Filter by status (alerts only)"
    )

    def validate(self, data):
        """Cross-field validation."""
        if data.get('template_id'):
            try:
                template = NOCExportTemplate.objects.get(
                    id=data['template_id']
                )
                data['entity_type'] = template.entity_type
                data['format'] = template.format
                data.update(template.filters)
            except NOCExportTemplate.DoesNotExist:
                raise serializers.ValidationError(
                    {"template_id": "Template not found"}
                )

        return data