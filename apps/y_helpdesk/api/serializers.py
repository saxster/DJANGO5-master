"""
Help Desk API Serializers

Serializers for tickets, escalation policies, and SLA policies.

Compliance with .claude/rules.md:
- Serializers < 100 lines each
- Specific validation
"""

from rest_framework import serializers
from apps.y_helpdesk.models import Ticket, TicketHistory
from datetime import datetime, timezone as dt_timezone
import logging

logger = logging.getLogger(__name__)


class TicketListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for ticket list views."""

    assigned_to_name = serializers.CharField(
        source='assigned_to.get_full_name',
        read_only=True,
        allow_null=True
    )
    reporter_name = serializers.CharField(
        source='reporter.get_full_name',
        read_only=True
    )

    class Meta:
        model = Ticket
        fields = [
            'id', 'ticket_number', 'title', 'status', 'priority',
            'category', 'assigned_to', 'assigned_to_name',
            'reporter', 'reporter_name',
            'created_at', 'updated_at', 'due_date'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class TicketDetailSerializer(serializers.ModelSerializer):
    """Comprehensive serializer for ticket detail views."""

    assigned_to_name = serializers.CharField(
        source='assigned_to.get_full_name',
        read_only=True,
        allow_null=True
    )
    reporter_name = serializers.CharField(
        source='reporter.get_full_name',
        read_only=True
    )
    is_overdue = serializers.SerializerMethodField()

    class Meta:
        model = Ticket
        fields = [
            'id', 'ticket_number', 'title', 'description',
            'status', 'priority', 'category',
            'assigned_to', 'assigned_to_name',
            'reporter', 'reporter_name',
            'created_at', 'updated_at', 'resolved_at',
            'due_date', 'is_overdue',
            'attachments', 'tags'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'resolved_at']

    def get_is_overdue(self, obj):
        """Check if ticket is overdue."""
        if obj.status in ['resolved', 'closed']:
            return False

        if obj.due_date:
            return datetime.now(dt_timezone.utc) > obj.due_date

        return False


class TicketTransitionSerializer(serializers.Serializer):
    """Serializer for ticket state transitions."""

    to_status = serializers.ChoiceField(
        choices=['open', 'assigned', 'in_progress', 'resolved', 'closed'],
        required=True
    )
    comment = serializers.CharField(max_length=500, required=False, allow_blank=True)

    def validate_to_status(self, value):
        """Validate state transition is allowed."""
        ticket = self.context.get('ticket')
        current_status = ticket.status

        # Define allowed transitions
        allowed_transitions = {
            'open': ['assigned', 'closed'],
            'assigned': ['in_progress', 'closed'],
            'in_progress': ['resolved', 'assigned'],
            'resolved': ['closed', 'in_progress'],
            'closed': []  # Cannot transition from closed
        }

        if current_status == 'closed':
            raise serializers.ValidationError('Cannot transition from closed status')

        if value not in allowed_transitions.get(current_status, []):
            raise serializers.ValidationError(
                f'Cannot transition from {current_status} to {value}'
            )

        return value


__all__ = [
    'TicketListSerializer',
    'TicketDetailSerializer',
    'TicketTransitionSerializer',
]
