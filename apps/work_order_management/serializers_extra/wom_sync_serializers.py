"""
Work Order Sync Serializers for Mobile Sync Operations

Handles serialization and validation for WOM (Work Order) sync from mobile clients.

Following .claude/rules.md:
- Rule #7: Serializer <100 lines
- Rule #11: Specific validation errors
"""

from rest_framework import serializers
from apps.work_order_management.models import Wom
from apps.core.serializers import ValidatedModelSerializer


class WOMSyncSerializer(ValidatedModelSerializer):
    """
    Serializer for Work Order (WOM) mobile sync operations.

    Handles sync-specific fields like mobile_id, version, sync_status.
    """

    mobile_id = serializers.UUIDField(
        required=False,
        help_text='Client-generated unique identifier'
    )
    version = serializers.IntegerField(
        required=False,
        help_text='Version for conflict detection'
    )
    sync_status = serializers.ChoiceField(
        choices=[
            ('synced', 'Synced'),
            ('pending_sync', 'Pending Sync'),
            ('sync_error', 'Sync Error'),
            ('pending_delete', 'Pending Delete'),
        ],
        required=False,
        help_text='Sync status'
    )
    last_sync_timestamp = serializers.DateTimeField(
        required=False,
        help_text='Last sync timestamp'
    )

    class Meta:
        model = Wom
        fields = [
            'id', 'uuid', 'mobile_id', 'version', 'sync_status', 'last_sync_timestamp',
            'wo_number', 'description', 'status', 'priority',
            'assigned_to', 'location', 'asset',
            'scheduled_start', 'scheduled_end', 'actual_start', 'actual_end',
            'estimated_hours', 'actual_hours',
            'bu', 'client', 'tenant',
            'cuser', 'muser', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'uuid', 'wo_number', 'created_at', 'updated_at']

    def validate_description(self, value):
        """Validate work order description."""
        if not value or len(value.strip()) < 5:
            raise serializers.ValidationError(
                "Description must be at least 5 characters"
            )
        return value.strip()

    def validate_status(self, value):
        """Validate status field."""
        valid_statuses = ['draft', 'in_progress', 'paused', 'completed', 'closed', 'cancelled']
        if value and value.lower() not in valid_statuses:
            raise serializers.ValidationError(
                f"Status must be one of: {', '.join(valid_statuses)}"
            )
        return value

    def validate_priority(self, value):
        """Validate priority field."""
        if value and value not in ['HIGH', 'MEDIUM', 'LOW']:
            raise serializers.ValidationError(
                "Priority must be HIGH, MEDIUM, or LOW"
            )
        return value

    def validate(self, attrs):
        """Cross-field validation."""
        scheduled_start = attrs.get('scheduled_start')
        scheduled_end = attrs.get('scheduled_end')

        if scheduled_start and scheduled_end:
            if scheduled_end < scheduled_start:
                raise serializers.ValidationError(
                    "Scheduled end must be after scheduled start"
                )

        actual_start = attrs.get('actual_start')
        actual_end = attrs.get('actual_end')

        if actual_start and actual_end:
            if actual_end < actual_start:
                raise serializers.ValidationError(
                    "Actual end must be after actual start"
                )

        return attrs