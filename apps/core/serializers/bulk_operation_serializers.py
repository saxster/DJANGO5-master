"""
Bulk Operation Serializers

Generic serializers for bulk operations with comprehensive validation.

Compliance with .claude/rules.md:
- Rule #9: Input validation
- Rule #11: Specific exception handling
"""

from rest_framework import serializers
from typing import List


class BulkTransitionSerializer(serializers.Serializer):
    """
    Serializer for bulk state transition requests.

    Validates:
    - IDs list (not empty, valid format)
    - Target state (required)
    - Comments (optional but recommended)
    - Dry run flag
    - Rollback behavior
    """

    ids = serializers.ListField(
        child=serializers.CharField(max_length=100),
        min_length=1,
        max_length=100,  # Max 100 items per bulk operation
        help_text='List of entity IDs to transition'
    )

    target_state = serializers.CharField(
        max_length=50,
        required=True,
        help_text='Target state to transition to'
    )

    comments = serializers.CharField(
        max_length=1000,
        required=False,
        allow_blank=True,
        help_text='Comments for the transition'
    )

    metadata = serializers.JSONField(
        required=False,
        default=dict,
        help_text='Additional metadata for the transition'
    )

    dry_run = serializers.BooleanField(
        default=False,
        help_text='If true, validate without executing'
    )

    rollback_on_error = serializers.BooleanField(
        default=True,
        help_text='If true, rollback all on any failure'
    )

    def validate_ids(self, value: List[str]) -> List[str]:
        """Validate IDs list"""
        if len(value) > 1000:
            raise serializers.ValidationError(
                "Maximum 1000 items allowed per bulk operation"
            )

        # Remove duplicates
        unique_ids = list(set(value))
        if len(unique_ids) < len(value):
            raise serializers.ValidationError(
                f"Duplicate IDs found. {len(value) - len(unique_ids)} duplicates removed."
            )

        return unique_ids

    def validate_target_state(self, value: str) -> str:
        """Validate target state"""
        return value.upper()


class BulkUpdateSerializer(serializers.Serializer):
    """
    Serializer for bulk update requests.

    Validates:
    - IDs list
    - Update data dictionary
    - Dry run flag
    """

    ids = serializers.ListField(
        child=serializers.CharField(max_length=100),
        min_length=1,
        max_length=1000,
        help_text='List of entity IDs to update'
    )

    update_data = serializers.JSONField(
        help_text='Dictionary of fields to update'
    )

    dry_run = serializers.BooleanField(
        default=False,
        help_text='If true, validate without executing'
    )

    rollback_on_error = serializers.BooleanField(
        default=True,
        help_text='If true, rollback all on any failure'
    )

    def validate_update_data(self, value: dict) -> dict:
        """Validate update data"""
        if not value:
            raise serializers.ValidationError("Update data cannot be empty")

        # Prevent updating sensitive fields
        forbidden_fields = ['id', 'uuid', 'created_on', 'created_by', 'tenant']
        for field in forbidden_fields:
            if field in value:
                raise serializers.ValidationError(
                    f"Cannot update protected field: {field}"
                )

        return value


class BulkAssignSerializer(serializers.Serializer):
    """
    Serializer for bulk assignment requests.

    Common for assigning work orders, tasks, tickets to users/teams.
    """

    ids = serializers.ListField(
        child=serializers.CharField(max_length=100),
        min_length=1,
        max_length=1000
    )

    assigned_to_user = serializers.CharField(
        max_length=100,
        required=False,
        allow_null=True,
        help_text='User ID to assign to'
    )

    assigned_to_team = serializers.CharField(
        max_length=100,
        required=False,
        allow_null=True,
        help_text='Team/Group ID to assign to'
    )

    comments = serializers.CharField(
        max_length=1000,
        required=False,
        allow_blank=True
    )

    dry_run = serializers.BooleanField(default=False)
    rollback_on_error = serializers.BooleanField(default=True)

    def validate(self, attrs):
        """Validate that at least one assignment target is provided"""
        if not attrs.get('assigned_to_user') and not attrs.get('assigned_to_team'):
            raise serializers.ValidationError(
                "Either assigned_to_user or assigned_to_team must be provided"
            )
        return attrs


class BulkOperationResponseSerializer(serializers.Serializer):
    """
    Serializer for bulk operation responses.

    Returns comprehensive results with success/failure tracking.
    """

    operation_type = serializers.CharField()
    total_items = serializers.IntegerField()
    successful_items = serializers.IntegerField()
    failed_items = serializers.IntegerField()
    success_rate = serializers.FloatField()
    successful_ids = serializers.ListField(child=serializers.CharField())
    failed_ids = serializers.ListField(child=serializers.CharField())
    failure_details = serializers.DictField()
    warnings = serializers.ListField(child=serializers.CharField())
    was_rolled_back = serializers.BooleanField()
    rollback_reason = serializers.CharField(allow_null=True)
