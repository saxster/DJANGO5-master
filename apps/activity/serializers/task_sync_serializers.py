"""
Task Sync Serializers for Mobile Sync Operations

Handles serialization and validation for JobNeed (Task) sync from mobile clients.

Following .claude/rules.md:
- Rule #7: Serializer <100 lines
- Rule #11: Specific validation errors
"""

from rest_framework import serializers
from django.core.exceptions import ValidationError as DjangoValidationError
from apps.activity.models.job_model import Jobneed
from apps.core.serializers import ValidatedModelSerializer


class TaskSyncSerializer(ValidatedModelSerializer):
    """
    Serializer for Task (JobNeed) mobile sync operations.

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
        model = Jobneed
        fields = [
            'id', 'uuid', 'mobile_id', 'version', 'sync_status', 'last_sync_timestamp',
            'jobdesc', 'plandatetime', 'expirydatetime', 'gracetime',
            'starttime', 'endtime', 'gpslocation', 'remarks',
            'priority', 'identifier', 'jobstatus', 'jobtype', 'scantype',
            'job', 'location', 'asset', 'qset',
            'bu', 'client', 'tenant',
            'cuser', 'muser', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'uuid', 'created_at', 'updated_at']

    def validate_jobdesc(self, value):
        """Validate job description."""
        if not value or len(value.strip()) < 3:
            raise serializers.ValidationError(
                "Job description must be at least 3 characters"
            )
        if len(value) > 200:
            raise serializers.ValidationError(
                "Job description cannot exceed 200 characters"
            )
        return value.strip()

    def validate_gracetime(self, value):
        """Validate grace time."""
        if value is not None and value < 0:
            raise serializers.ValidationError(
                "Grace time cannot be negative"
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
        plandatetime = attrs.get('plandatetime')
        expirydatetime = attrs.get('expirydatetime')

        if plandatetime and expirydatetime:
            if expirydatetime < plandatetime:
                raise serializers.ValidationError(
                    "Expiry datetime must be after plan datetime"
                )

        starttime = attrs.get('starttime')
        endtime = attrs.get('endtime')

        if starttime and endtime:
            if endtime < starttime:
                raise serializers.ValidationError(
                    "End time must be after start time"
                )

        return attrs