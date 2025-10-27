"""
Reports API Serializers

Serializers for report generation, scheduling, and templates.

Compliance with .claude/rules.md:
- Serializers < 100 lines
- Specific validation
"""

from rest_framework import serializers
from datetime import datetime, timezone as dt_timezone
from croniter import croniter
import logging

logger = logging.getLogger(__name__)


class ReportGenerateSerializer(serializers.Serializer):
    """
    Serializer for report generation requests.

    Input-only serializer (no model binding).
    """
    report_type = serializers.ChoiceField(
        choices=[
            'site_visit', 'attendance_summary', 'task_completion',
            'asset_inventory', 'ticket_report'
        ],
        required=True
    )
    format = serializers.ChoiceField(
        choices=['pdf', 'excel', 'csv', 'json'],
        default='pdf'
    )
    filters = serializers.JSONField(required=False, default=dict)
    date_from = serializers.DateTimeField(required=False)
    date_to = serializers.DateTimeField(required=False)

    def validate(self, attrs):
        """Validate date range if provided."""
        date_from = attrs.get('date_from')
        date_to = attrs.get('date_to')

        if date_from and date_to:
            if date_from > date_to:
                raise serializers.ValidationError({
                    'date_to': 'End date must be after start date'
                })

        return attrs


class ReportScheduleSerializer(serializers.Serializer):
    """
    Serializer for scheduled report configuration.

    Input serializer for creating report schedules.
    """
    report_type = serializers.ChoiceField(
        choices=[
            'site_visit', 'attendance_summary', 'task_completion',
            'asset_inventory', 'ticket_report'
        ],
        required=True
    )
    schedule_cron = serializers.CharField(max_length=100, required=True)
    recipients = serializers.ListField(
        child=serializers.EmailField(),
        min_length=1,
        max_length=10
    )
    format = serializers.ChoiceField(
        choices=['pdf', 'excel', 'csv'],
        default='pdf'
    )
    filters = serializers.JSONField(required=False, default=dict)

    def validate_schedule_cron(self, value):
        """Validate cron expression."""
        try:
            croniter(value, datetime.now())
        except (ValueError, KeyError) as e:
            raise serializers.ValidationError(
                f'Invalid cron expression: {str(e)}'
            )
        return value

    def validate_recipients(self, value):
        """Validate email recipients."""
        if not value:
            raise serializers.ValidationError('At least one recipient required')

        # Check for duplicates
        if len(value) != len(set(value)):
            raise serializers.ValidationError('Duplicate email addresses found')

        return value


class ReportStatusSerializer(serializers.Serializer):
    """
    Serializer for report generation status.

    Output-only serializer.
    """
    report_id = serializers.CharField()
    status = serializers.ChoiceField(
        choices=['pending', 'generating', 'completed', 'failed']
    )
    progress = serializers.IntegerField(min_value=0, max_value=100)
    download_url = serializers.URLField(allow_null=True)
    error_message = serializers.CharField(allow_null=True)
    created_at = serializers.DateTimeField()


__all__ = [
    'ReportGenerateSerializer',
    'ReportScheduleSerializer',
    'ReportStatusSerializer',
]
