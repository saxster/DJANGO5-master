"""
NOC Maintenance Window Serializers.

DRF serializers for maintenance window management.
Follows .claude/rules.md Rule #7 (<150 lines).
"""

from rest_framework import serializers
from django.utils import timezone
from apps.noc.models import MaintenanceWindow
from apps.noc.services import NOCPrivacyService

__all__ = [
    'MaintenanceWindowSerializer',
    'MaintenanceWindowCreateSerializer',
]


class MaintenanceWindowSerializer(serializers.ModelSerializer):
    """Serializer for maintenance windows."""

    client_name = serializers.CharField(source='client.buname', read_only=True, allow_null=True)
    bu_name = serializers.CharField(source='bu.buname', read_only=True, allow_null=True)
    created_by_name = serializers.SerializerMethodField()
    is_active = serializers.SerializerMethodField()

    class Meta:
        model = MaintenanceWindow
        fields = [
            'id', 'client_name', 'bu_name', 'start_time', 'end_time',
            'suppress_alerts', 'reason', 'created_by_name', 'is_active', 'cdtz'
        ]
        read_only_fields = ['id', 'created_by_name', 'is_active', 'cdtz']

    def get_created_by_name(self, obj):
        if obj.created_by:
            return NOCPrivacyService.mask_pii(
                {'name': obj.created_by.peoplename},
                self.context.get('user', None)
            ).get('name')
        return None

    def get_is_active(self, obj):
        now = timezone.now()
        return obj.start_time <= now <= obj.end_time


class MaintenanceWindowCreateSerializer(serializers.Serializer):
    """Serializer for creating maintenance windows."""

    client_id = serializers.IntegerField(required=False, allow_null=True)
    bu_id = serializers.IntegerField(required=False, allow_null=True)
    start_time = serializers.DateTimeField(required=True)
    end_time = serializers.DateTimeField(required=True)
    suppress_alerts = serializers.ListField(
        child=serializers.CharField(),
        required=False,
        default=list
    )
    reason = serializers.CharField(required=True, max_length=1000)

    def validate(self, data):
        if data['end_time'] <= data['start_time']:
            raise serializers.ValidationError("end_time must be after start_time")

        if data['start_time'] < timezone.now():
            raise serializers.ValidationError("start_time cannot be in the past")

        if not data.get('client_id') and not data.get('bu_id'):
            raise serializers.ValidationError("Either client_id or bu_id must be provided")

        return data