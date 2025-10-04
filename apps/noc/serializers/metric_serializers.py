"""
NOC Metric Serializers.

DRF serializers for metrics and dashboard data.
Follows .claude/rules.md Rule #7 (<150 lines).
"""

from rest_framework import serializers
from apps.noc.models import NOCMetricSnapshot

__all__ = [
    'NOCMetricSnapshotSerializer',
    'MetricOverviewSerializer',
]


class NOCMetricSnapshotSerializer(serializers.ModelSerializer):
    """Serializer for detailed metric snapshots."""

    client_name = serializers.CharField(source='client.buname', read_only=True)
    bu_name = serializers.CharField(source='bu.buname', read_only=True, allow_null=True)
    oic_name = serializers.CharField(source='oic.peoplename', read_only=True, allow_null=True)

    class Meta:
        model = NOCMetricSnapshot
        fields = [
            'id', 'client_name', 'bu_name', 'city', 'state', 'oic_name',
            'window_start', 'window_end',
            'tickets_open', 'tickets_overdue', 'tickets_resolved',
            'work_orders_pending', 'work_orders_completed', 'work_orders_overdue',
            'attendance_present', 'attendance_expected',
            'device_health_online', 'device_health_offline',
            'sync_health_score', 'cdtz'
        ]
        read_only_fields = fields


class MetricOverviewSerializer(serializers.Serializer):
    """Serializer for aggregated dashboard overview metrics."""

    tickets_open = serializers.IntegerField()
    tickets_overdue = serializers.IntegerField()
    work_orders_pending = serializers.IntegerField()
    attendance_present = serializers.IntegerField()
    attendance_expected = serializers.IntegerField()
    attendance_ratio = serializers.FloatField()
    device_offline = serializers.IntegerField()
    active_alerts = serializers.IntegerField()
    active_incidents = serializers.IntegerField()
    critical_alerts = serializers.IntegerField()
    clients_count = serializers.IntegerField()
    sites_count = serializers.IntegerField()
    time_range_hours = serializers.IntegerField()
    last_updated = serializers.DateTimeField()