"""
NOC Alert Event Serializers.

DRF serializers for alert management with PII masking and RBAC support.
Follows .claude/rules.md Rule #7 (<150 lines), Rule #11 (specific exceptions).
"""

from rest_framework import serializers
from apps.noc.models import NOCAlertEvent
from apps.noc.services import NOCPrivacyService

__all__ = [
    'NOCAlertEventSerializer',
    'NOCAlertEventListSerializer',
    'AlertAcknowledgeSerializer',
    'AlertAssignSerializer',
    'AlertEscalateSerializer',
    'AlertResolveSerializer',
    'BulkAlertActionSerializer',
]


class NOCAlertEventListSerializer(serializers.ModelSerializer):
    """
    Lightweight serializer for alert list views.
    
    N+1 Query Optimization: ViewSets should use optimized queryset:
        NOCAlertEvent.objects.select_related('client', 'bu')
    """

    client_name = serializers.CharField(source='client.buname', read_only=True)
    site_name = serializers.CharField(source='bu.buname', read_only=True, allow_null=True)
    severity_display = serializers.CharField(source='get_severity_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = NOCAlertEvent
        fields = [
            'id', 'alert_type', 'severity', 'severity_display', 'status', 'status_display',
            'message', 'client_name', 'site_name', 'entity_type', 'entity_id',
            'suppressed_count', 'first_seen', 'last_seen', 'cdtz'
        ]
        read_only_fields = fields


class NOCAlertEventSerializer(serializers.ModelSerializer):
    """
    Detailed serializer for alert detail views with PII masking.
    
    N+1 Query Optimization: ViewSets should use optimized queryset:
        NOCAlertEvent.objects.select_related('client', 'bu', 'acknowledged_by', 
                                             'assigned_to', 'escalated_to', 
                                             'resolved_by', 'parent_alert')
    """

    client_name = serializers.CharField(source='client.buname', read_only=True)
    site_name = serializers.CharField(source='bu.buname', read_only=True, allow_null=True)
    acknowledged_by_name = serializers.SerializerMethodField()
    assigned_to_name = serializers.SerializerMethodField()
    escalated_to_name = serializers.SerializerMethodField()
    resolved_by_name = serializers.SerializerMethodField()
    severity_display = serializers.CharField(source='get_severity_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    time_to_ack_display = serializers.CharField(source='time_to_ack', read_only=True, allow_null=True)
    time_to_resolve_display = serializers.CharField(source='time_to_resolve', read_only=True, allow_null=True)

    class Meta:
        model = NOCAlertEvent
        fields = [
            'id', 'alert_type', 'severity', 'severity_display', 'status', 'status_display',
            'dedup_key', 'correlation_id', 'parent_alert', 'suppressed_count',
            'message', 'entity_type', 'entity_id', 'metadata',
            'client_name', 'site_name', 'acknowledged_at', 'acknowledged_by_name',
            'assigned_at', 'assigned_to_name', 'escalated_at', 'escalated_to_name',
            'resolved_at', 'resolved_by_name', 'time_to_ack_display', 'time_to_resolve_display',
            'first_seen', 'last_seen', 'cdtz'
        ]
        read_only_fields = fields

    def get_acknowledged_by_name(self, obj):
        """
        Get acknowledged_by name with PII masking.
        
        Performance: No additional query if select_related('acknowledged_by') used in queryset.
        """
        if obj.acknowledged_by:
            return NOCPrivacyService.mask_pii({'name': obj.acknowledged_by.peoplename}, self.context.get('user', None)).get('name')
        return None

    def get_assigned_to_name(self, obj):
        """
        Get assigned_to name with PII masking.
        
        Performance: No additional query if select_related('assigned_to') used in queryset.
        """
        if obj.assigned_to:
            return NOCPrivacyService.mask_pii({'name': obj.assigned_to.peoplename}, self.context.get('user', None)).get('name')
        return None

    def get_escalated_to_name(self, obj):
        """
        Get escalated_to name with PII masking.
        
        Performance: No additional query if select_related('escalated_to') used in queryset.
        """
        if obj.escalated_to:
            return NOCPrivacyService.mask_pii({'name': obj.escalated_to.peoplename}, self.context.get('user', None)).get('name')
        return None

    def get_resolved_by_name(self, obj):
        """
        Get resolved_by name with PII masking.
        
        Performance: No additional query if select_related('resolved_by') used in queryset.
        """
        if obj.resolved_by:
            return NOCPrivacyService.mask_pii({'name': obj.resolved_by.peoplename}, self.context.get('user', None)).get('name')
        return None


class AlertAcknowledgeSerializer(serializers.Serializer):
    """Serializer for acknowledging an alert."""

    comment = serializers.CharField(required=False, allow_blank=True, max_length=500)


class AlertAssignSerializer(serializers.Serializer):
    """Serializer for assigning an alert to a user."""

    assigned_to_id = serializers.IntegerField(required=True)
    comment = serializers.CharField(required=False, allow_blank=True, max_length=500)


class AlertEscalateSerializer(serializers.Serializer):
    """Serializer for escalating an alert."""

    escalated_to_id = serializers.IntegerField(required=True)
    reason = serializers.CharField(required=True, max_length=500)


class AlertResolveSerializer(serializers.Serializer):
    """Serializer for resolving an alert."""

    resolution_notes = serializers.CharField(required=True, max_length=1000)


class BulkAlertActionSerializer(serializers.Serializer):
    """Serializer for bulk alert operations."""

    alert_ids = serializers.ListField(
        child=serializers.IntegerField(),
        required=True,
        min_length=1,
        max_length=100
    )
    action = serializers.ChoiceField(
        choices=['acknowledge', 'assign', 'resolve'],
        required=True
    )
    assigned_to_id = serializers.IntegerField(required=False)
    resolution_notes = serializers.CharField(required=False, max_length=1000)
    comment = serializers.CharField(required=False, max_length=500)