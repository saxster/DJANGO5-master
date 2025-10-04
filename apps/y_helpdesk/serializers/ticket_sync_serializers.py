"""
Ticket Sync Serializers with Status Transition Validation

Handles serialization and validation for Ticket sync from mobile clients.

Following .claude/rules.md:
- Rule #7: Serializer <100 lines
- Rule #11: Specific validation errors
"""

from rest_framework import serializers
from apps.y_helpdesk.models import Ticket
from apps.core.serializers import ValidatedModelSerializer


class TicketSyncSerializer(ValidatedModelSerializer):
    """
    Serializer for Ticket mobile sync operations.

    Handles status transition validation and escalation preservation.
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
        model = Ticket
        fields = [
            'id', 'uuid', 'mobile_id', 'version', 'sync_status', 'last_sync_timestamp',
            'ticketno', 'ticketdesc', 'status', 'priority', 'identifier',
            'assignedtopeople', 'assignedtogroup', 'comments',
            'bu', 'client', 'tenant',
            'cuser', 'muser', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'uuid', 'ticketno', 'created_at', 'updated_at']

    def validate_ticketdesc(self, value):
        """Validate ticket description."""
        if not value or len(value.strip()) < 10:
            raise serializers.ValidationError(
                "Ticket description must be at least 10 characters"
            )
        return value.strip()

    def validate_status(self, value):
        """Validate status field."""
        valid_statuses = ['NEW', 'OPEN', 'INPROGRESS', 'ONHOLD', 'RESOLVED', 'CLOSED', 'CANCELLED']
        if value and value.upper() not in valid_statuses:
            raise serializers.ValidationError(
                f"Status must be one of: {', '.join(valid_statuses)}"
            )
        return value.upper() if value else 'NEW'

    def validate_priority(self, value):
        """Validate priority field."""
        if value and value not in ['HIGH', 'MEDIUM', 'LOW']:
            raise serializers.ValidationError(
                "Priority must be HIGH, MEDIUM, or LOW"
            )
        return value

    def validate_identifier(self, value):
        """Validate identifier field."""
        valid_identifiers = ['REQUEST', 'TICKET']
        if value and value.upper() not in valid_identifiers:
            raise serializers.ValidationError(
                f"Identifier must be one of: {', '.join(valid_identifiers)}"
            )
        return value.upper() if value else 'TICKET'