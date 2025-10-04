"""
NOC Incident Serializers.

DRF serializers for incident management workflow.
Follows .claude/rules.md Rule #7 (<150 lines), Rule #11 (specific exceptions).
"""

from rest_framework import serializers
from apps.noc.models import NOCIncident
from apps.noc.services import NOCPrivacyService
from .alert_serializers import NOCAlertEventListSerializer

__all__ = [
    'NOCIncidentSerializer',
    'NOCIncidentListSerializer',
    'IncidentCreateSerializer',
    'IncidentAssignSerializer',
    'IncidentResolveSerializer',
]


class NOCIncidentListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for incident list views."""

    alert_count = serializers.IntegerField(source='alerts.count', read_only=True)
    severity_display = serializers.CharField(source='get_severity_display', read_only=True)
    state_display = serializers.CharField(source='get_state_display', read_only=True)
    assigned_to_name = serializers.SerializerMethodField()

    class Meta:
        model = NOCIncident
        fields = [
            'id', 'title', 'state', 'state_display', 'severity', 'severity_display',
            'alert_count', 'assigned_to_name', 'created_at', 'resolved_at'
        ]
        read_only_fields = fields

    def get_assigned_to_name(self, obj):
        if obj.assigned_to:
            return NOCPrivacyService.mask_pii(
                {'name': obj.assigned_to.peoplename},
                self.context.get('user', None)
            ).get('name')
        return None


class NOCIncidentSerializer(serializers.ModelSerializer):
    """Detailed serializer for incident detail views."""

    alerts = NOCAlertEventListSerializer(many=True, read_only=True)
    alert_ids = serializers.ListField(child=serializers.IntegerField(), write_only=True, required=False)
    assigned_to_name = serializers.SerializerMethodField()
    escalated_to_name = serializers.SerializerMethodField()
    resolved_by_name = serializers.SerializerMethodField()
    severity_display = serializers.CharField(source='get_severity_display', read_only=True)
    state_display = serializers.CharField(source='get_state_display', read_only=True)
    time_to_resolve_display = serializers.SerializerMethodField()

    class Meta:
        model = NOCIncident
        fields = [
            'id', 'title', 'description', 'state', 'state_display', 'severity', 'severity_display',
            'alerts', 'alert_ids', 'assigned_to_name', 'escalated_to_name', 'resolved_by_name',
            'assigned_at', 'escalated_at', 'resolved_at', 'resolution_notes',
            'time_to_resolve', 'time_to_resolve_display', 'created_at'
        ]
        read_only_fields = [
            'id', 'severity', 'state', 'alerts', 'assigned_at', 'escalated_at', 'resolved_at',
            'time_to_resolve', 'created_at'
        ]

    def get_assigned_to_name(self, obj):
        if obj.assigned_to:
            return NOCPrivacyService.mask_pii(
                {'name': obj.assigned_to.peoplename},
                self.context.get('user', None)
            ).get('name')
        return None

    def get_escalated_to_name(self, obj):
        if obj.escalated_to:
            return NOCPrivacyService.mask_pii(
                {'name': obj.escalated_to.peoplename},
                self.context.get('user', None)
            ).get('name')
        return None

    def get_resolved_by_name(self, obj):
        if obj.resolved_by:
            return NOCPrivacyService.mask_pii(
                {'name': obj.resolved_by.peoplename},
                self.context.get('user', None)
            ).get('name')
        return None

    def get_time_to_resolve_display(self, obj):
        if obj.time_to_resolve:
            return str(obj.time_to_resolve)
        return None


class IncidentCreateSerializer(serializers.Serializer):
    """Serializer for creating incidents from alerts."""

    alert_ids = serializers.ListField(
        child=serializers.IntegerField(),
        required=True,
        min_length=1,
        max_length=50
    )
    title = serializers.CharField(required=True, max_length=255)
    description = serializers.CharField(required=False, allow_blank=True, max_length=2000)


class IncidentAssignSerializer(serializers.Serializer):
    """Serializer for assigning an incident."""

    assigned_to_id = serializers.IntegerField(required=True)
    comment = serializers.CharField(required=False, allow_blank=True, max_length=500)


class IncidentResolveSerializer(serializers.Serializer):
    """Serializer for resolving an incident."""

    resolution_notes = serializers.CharField(required=True, max_length=2000)