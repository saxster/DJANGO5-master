"""
Base Serializers for Mobile Sync Operations

Provides common serializers for sync requests/responses across all domains.
Relocated from apps/api/v1/serializers/ to apps/core/serializers/ as part of V1→V2 migration.

These are generic, domain-agnostic serializers used by legacy sync endpoints.
For new V2 API endpoints, use type-safe serializers from apps/api/v2/serializers/.

Following .claude/rules.md:
- Rule #7: Serializers < 100 lines (well under limit)
- Rule #10: Comprehensive validation
- Rule #11: Specific exception handling
- Rule #13: Required validation patterns

Migration Note (Nov 2025):
- Originally in apps/api/v1/serializers/sync_base_serializers.py
- Moved to core for shared use by legacy sync views
- V2 APIs use enhanced type-safe serializers with Pydantic validation
"""

from rest_framework import serializers
from django.utils import timezone


class SyncItemResponseSerializer(serializers.Serializer):
    """
    Serializer for individual sync item response.

    Returned for each item in the sync batch.
    Used by: Attendance, Tasks, Tickets, Work Orders sync endpoints.
    """
    mobile_id = serializers.UUIDField(
        help_text='Client-generated unique identifier'
    )
    status = serializers.ChoiceField(
        choices=[
            ('created', 'Created'),
            ('updated', 'Updated'),
            ('conflict', 'Conflict'),
            ('error', 'Error')
        ],
        help_text='Sync status for this item'
    )
    server_version = serializers.IntegerField(
        required=False,
        help_text='Current server version after sync'
    )
    client_version = serializers.IntegerField(
        required=False,
        help_text='Client version that caused conflict'
    )
    error_message = serializers.CharField(
        required=False,
        help_text='Error details if status is error or conflict'
    )


class SyncRequestSerializer(serializers.Serializer):
    """
    Base serializer for sync request payload.

    Validates incoming sync batches from mobile clients.
    Generic serializer used across multiple domains.
    """
    entries = serializers.ListField(
        child=serializers.DictField(),
        min_length=1,
        max_length=1000,
        help_text='Array of items to sync (max 1000 per batch)'
    )
    last_sync_timestamp = serializers.DateTimeField(
        required=False,
        allow_null=True,
        help_text='Last successful sync timestamp (for delta sync)'
    )
    client_id = serializers.CharField(
        max_length=100,
        help_text='Unique device/client identifier'
    )

    def validate_entries(self, value):
        """Validate that entries list is not empty and has required fields."""
        if not value:
            raise serializers.ValidationError("entries cannot be empty")

        for entry in value:
            if 'mobile_id' not in entry:
                raise serializers.ValidationError(
                    "Each entry must have a mobile_id field"
                )

        return value

    def validate_client_id(self, value):
        """Validate client_id format."""
        if not value or len(value) < 5:
            raise serializers.ValidationError(
                "client_id must be at least 5 characters"
            )
        return value


class SyncResponseSerializer(serializers.Serializer):
    """
    Serializer for bulk sync response.

    Returns aggregated results for the entire sync batch.
    """
    synced_items = SyncItemResponseSerializer(many=True)
    conflicts = SyncItemResponseSerializer(many=True)
    errors = SyncItemResponseSerializer(many=True)
    timestamp = serializers.DateTimeField(
        default=timezone.now,
        help_text='Server timestamp when sync was processed'
    )


class DeltaSyncRequestSerializer(serializers.Serializer):
    """
    Serializer for delta sync (changes since timestamp) requests.

    Used by GET endpoints that return incremental changes.
    """
    since = serializers.DateTimeField(
        required=False,
        allow_null=True,
        help_text='Return changes since this timestamp'
    )
    limit = serializers.IntegerField(
        default=100,
        min_value=1,
        max_value=1000,
        help_text='Maximum number of items to return'
    )

    def validate_since(self, value):
        """Validate that since timestamp is not in the future."""
        if value and value > timezone.now():
            raise serializers.ValidationError(
                "since timestamp cannot be in the future"
            )
        return value


class DeltaSyncResponseSerializer(serializers.Serializer):
    """
    Serializer for delta sync response.

    Returns paginated list of changes with pagination metadata.
    """
    items = serializers.ListField(
        child=serializers.DictField(),
        help_text='List of changed items'
    )
    has_more = serializers.BooleanField(
        help_text='Whether more results are available'
    )
    next_timestamp = serializers.DateTimeField(
        required=False,
        allow_null=True,
        help_text='Timestamp to use for next delta sync request'
    )


__all__ = [
    'SyncItemResponseSerializer',
    'SyncRequestSerializer',
    'SyncResponseSerializer',
    'DeltaSyncRequestSerializer',
    'DeltaSyncResponseSerializer',
]
