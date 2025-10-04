"""
Attendance Sync Serializers with GPS Validation

Handles serialization and validation for Tracking (Attendance) sync from mobile clients.

Following .claude/rules.md:
- Rule #7: Serializer <100 lines
- Rule #11: Specific validation errors
"""

from rest_framework import serializers
from apps.attendance.models import Tracking
from apps.core.serializers import ValidatedModelSerializer


class AttendanceSyncSerializer(ValidatedModelSerializer):
    """
    Serializer for Tracking (Attendance) mobile sync operations.

    Handles GPS location validation and device tracking.
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
        model = Tracking
        fields = [
            'id', 'uuid', 'mobile_id', 'version', 'sync_status', 'last_sync_timestamp',
            'deviceid', 'gpslocation', 'receiveddate',
            'people', 'transportmode', 'reference', 'identifier'
        ]
        read_only_fields = ['id', 'uuid']

    def validate_deviceid(self, value):
        """Validate device ID."""
        if not value or len(value.strip()) < 5:
            raise serializers.ValidationError(
                "Device ID must be at least 5 characters"
            )
        return value.strip()

    def validate_gpslocation(self, value):
        """
        Validate GPS location.

        Ensures location data is present for attendance tracking.
        """
        if not value:
            raise serializers.ValidationError(
                "GPS location is required for attendance tracking"
            )
        return value

    def validate_transportmode(self, value):
        """Validate transport mode."""
        valid_modes = ['WALK', 'BIKE', 'CAR', 'BUS', 'TRAIN', 'OTHER']
        if value and value.upper() not in valid_modes:
            raise serializers.ValidationError(
                f"Transport mode must be one of: {', '.join(valid_modes)}"
            )
        return value.upper() if value else 'WALK'

    def validate_identifier(self, value):
        """Validate identifier field."""
        valid_identifiers = ['NONE', 'CONVEYANCE', 'EXTERNALTOUR', 'INTERNALTOUR', 'SITEVISIT', 'TRACKING']
        if value and value.upper() not in valid_identifiers:
            raise serializers.ValidationError(
                f"Identifier must be one of: {', '.join(valid_identifiers)}"
            )
        return value.upper() if value else 'TRACKING'