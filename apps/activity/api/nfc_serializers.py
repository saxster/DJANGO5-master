"""
NFC REST API Serializers (Sprint 4.3)

DRF serializers for NFC tag management endpoints:
- Tag binding to assets
- Tag scanning
- Scan history
- Tag status management

All serializers follow OpenAPI 3.0 specification for mobile code generation.

Author: Development Team
Date: October 2025
"""

from rest_framework import serializers
from apps.activity.models import NFCTag, NFCDevice, NFCScanLog


class NFCTagBindSerializer(serializers.Serializer):
    """Serializer for binding NFC tag to asset."""

    tag_uid = serializers.CharField(
        max_length=50,
        required=True,
        help_text="NFC tag UID (8-32 hexadecimal characters)"
    )
    asset_id = serializers.IntegerField(
        required=True,
        help_text="Asset ID to bind tag to"
    )
    metadata = serializers.JSONField(
        required=False,
        default=dict,
        help_text="Optional tag metadata (type, manufacturer, etc.)"
    )

    def validate_tag_uid(self, value):
        """Validate tag UID format."""
        value = value.upper().strip()
        if not all(c in '0123456789ABCDEF' for c in value):
            raise serializers.ValidationError(
                "Tag UID must contain only hexadecimal characters (0-9, A-F)"
            )
        if len(value) < 8 or len(value) > 32:
            raise serializers.ValidationError(
                "Tag UID must be between 8 and 32 characters"
            )
        return value


class NFCTagBindResponseSerializer(serializers.Serializer):
    """Response serializer for tag binding."""

    success = serializers.BooleanField()
    tag_id = serializers.UUIDField(required=False)
    tag_uid = serializers.CharField(required=False)
    asset_name = serializers.CharField(required=False)
    message = serializers.CharField()


class NFCScanSerializer(serializers.Serializer):
    """Serializer for NFC tag scanning."""

    tag_uid = serializers.CharField(
        max_length=50,
        required=True,
        help_text="NFC tag UID scanned"
    )
    device_id = serializers.CharField(
        max_length=100,
        required=True,
        help_text="Device ID that performed the scan"
    )
    scan_type = serializers.ChoiceField(
        choices=['CHECKIN', 'CHECKOUT', 'INSPECTION', 'INVENTORY', 'MAINTENANCE'],
        required=False,
        default='INSPECTION',
        help_text="Type of scan being performed"
    )
    location_id = serializers.IntegerField(
        required=False,
        allow_null=True,
        help_text="Location ID where scan occurred"
    )
    metadata = serializers.JSONField(
        required=False,
        default=dict,
        help_text="Scan metadata (RSSI, response time, etc.)"
    )


class NFCScanResponseSerializer(serializers.Serializer):
    """Response serializer for NFC scanning."""

    success = serializers.BooleanField()
    scan_id = serializers.IntegerField(required=False)
    asset = serializers.DictField(required=False)
    scan_result = serializers.CharField()
    message = serializers.CharField()
    scan_time = serializers.DateTimeField(required=False)


class NFCScanHistorySerializer(serializers.Serializer):
    """Serializer for scan history query."""

    tag_uid = serializers.CharField(
        max_length=50,
        required=False,
        help_text="Filter by tag UID"
    )
    asset_id = serializers.IntegerField(
        required=False,
        help_text="Filter by asset ID"
    )
    days = serializers.IntegerField(
        required=False,
        default=30,
        min_value=1,
        max_value=365,
        help_text="Number of days to look back (default: 30)"
    )


class NFCScanHistoryResponseSerializer(serializers.Serializer):
    """Response serializer for scan history."""

    scans = serializers.ListField(
        child=serializers.DictField()
    )
    total_scans = serializers.IntegerField()
    date_range = serializers.DictField()


class NFCTagStatusUpdateSerializer(serializers.Serializer):
    """Serializer for updating tag status."""

    tag_uid = serializers.CharField(
        max_length=50,
        required=True,
        help_text="NFC tag UID"
    )
    status = serializers.ChoiceField(
        choices=['ACTIVE', 'INACTIVE', 'DAMAGED', 'LOST', 'DECOMMISSIONED'],
        required=True,
        help_text="New tag status"
    )


class NFCTagStatusUpdateResponseSerializer(serializers.Serializer):
    """Response serializer for tag status update."""

    success = serializers.BooleanField()
    old_status = serializers.CharField(required=False)
    new_status = serializers.CharField(required=False)
    message = serializers.CharField()
