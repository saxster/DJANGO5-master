"""
Monitoring API Serializers

Serializers for monitoring models and API responses.
"""

from rest_framework import serializers
from apps.monitoring.models import (
    Alert, AlertRule, OperationalTicket, TicketCategory,
    MonitoringMetric, DeviceHealthSnapshot, AlertAcknowledgment
)


class AlertRuleSerializer(serializers.ModelSerializer):
    """Serializer for alert rules"""

    class Meta:
        model = AlertRule
        fields = [
            'rule_id', 'name', 'alert_type', 'severity', 'is_active',
            'conditions', 'cooldown_minutes', 'auto_resolve_minutes',
            'notification_channels', 'total_triggered', 'last_triggered'
        ]
        read_only_fields = ['rule_id', 'total_triggered', 'last_triggered']


class AlertSerializer(serializers.ModelSerializer):
    """Serializer for alerts"""

    user_name = serializers.CharField(source='user.peoplename', read_only=True)
    site_name = serializers.CharField(source='site.buname', read_only=True)
    alert_type = serializers.CharField(source='rule.alert_type', read_only=True)
    rule_name = serializers.CharField(source='rule.name', read_only=True)

    class Meta:
        model = Alert
        fields = [
            'alert_id', 'title', 'description', 'severity', 'status',
            'triggered_at', 'acknowledged_at', 'resolved_at',
            'escalation_level', 'response_time_seconds', 'resolution_time_seconds',
            'user_name', 'site_name', 'alert_type', 'rule_name',
            'device_id', 'alert_data', 'context_data'
        ]
        read_only_fields = [
            'alert_id', 'triggered_at', 'acknowledged_at', 'resolved_at',
            'response_time_seconds', 'resolution_time_seconds'
        ]


class AlertAcknowledgmentSerializer(serializers.ModelSerializer):
    """Serializer for alert acknowledgments"""

    acknowledged_by_name = serializers.CharField(source='acknowledged_by.peoplename', read_only=True)

    class Meta:
        model = AlertAcknowledgment
        fields = [
            'acknowledged_by_name', 'acknowledgment_method', 'notes',
            'acknowledged_at', 'response_time_seconds'
        ]


class TicketCategorySerializer(serializers.ModelSerializer):
    """Serializer for ticket categories"""

    class Meta:
        model = TicketCategory
        fields = [
            'category_id', 'name', 'description', 'default_priority',
            'response_time_minutes', 'resolution_time_hours',
            'auto_assign', 'auto_escalate', 'is_active'
        ]


class TicketSerializer(serializers.ModelSerializer):
    """Serializer for operational tickets"""

    user_name = serializers.CharField(source='user.peoplename', read_only=True)
    site_name = serializers.CharField(source='site.buname', read_only=True)
    category_name = serializers.CharField(source='category.name', read_only=True)
    assigned_to_name = serializers.CharField(source='assigned_to.peoplename', read_only=True)
    alert_type = serializers.CharField(source='alert.rule.alert_type', read_only=True)

    class Meta:
        model = OperationalTicket
        fields = [
            'ticket_id', 'ticket_number', 'title', 'description',
            'priority', 'status', 'created_at', 'assigned_at',
            'resolved_at', 'closed_at', 'response_due_at', 'resolution_due_at',
            'is_overdue', 'escalation_count', 'resolution_type',
            'resolution_notes', 'user_name', 'site_name', 'category_name',
            'assigned_to_name', 'alert_type', 'device_id'
        ]
        read_only_fields = [
            'ticket_id', 'ticket_number', 'created_at', 'assigned_at',
            'resolved_at', 'closed_at', 'is_overdue'
        ]


class MonitoringMetricSerializer(serializers.ModelSerializer):
    """Serializer for monitoring metrics"""

    user_name = serializers.CharField(source='user.peoplename', read_only=True)

    class Meta:
        model = MonitoringMetric
        fields = [
            'metric_id', 'metric_type', 'value', 'unit',
            'recorded_at', 'user_name', 'device_id',
            'context', 'accuracy', 'confidence'
        ]
        read_only_fields = ['metric_id', 'recorded_at']


class DeviceHealthSnapshotSerializer(serializers.ModelSerializer):
    """Serializer for device health snapshots"""

    user_name = serializers.CharField(source='user.peoplename', read_only=True)
    site_name = serializers.CharField(source='site.buname', read_only=True)

    class Meta:
        model = DeviceHealthSnapshot
        fields = [
            'snapshot_id', 'overall_health', 'health_score',
            'battery_level', 'battery_health', 'is_charging',
            'signal_strength', 'network_type', 'is_online',
            'memory_usage_percent', 'storage_usage_percent',
            'thermal_state', 'steps_last_hour', 'last_movement_at',
            'predicted_battery_hours', 'risk_score', 'anomaly_indicators',
            'snapshot_taken_at', 'user_name', 'site_name', 'device_id'
        ]
        read_only_fields = ['snapshot_id', 'snapshot_taken_at']


class SystemHealthSerializer(serializers.Serializer):
    """Serializer for system health data"""

    timestamp = serializers.DateTimeField()
    overall_health = serializers.CharField()
    alert_statistics = serializers.DictField()
    monitoring_statistics = serializers.DictField()
    system_performance = serializers.DictField()


class DashboardDataSerializer(serializers.Serializer):
    """Serializer for dashboard data"""

    system_health = SystemHealthSerializer()
    alert_summary = serializers.DictField()
    device_summary = serializers.DictField()
    recent_incidents = serializers.ListField()
    performance_metrics = serializers.DictField()
    timestamp = serializers.DateTimeField()


class MonitoringResultSerializer(serializers.Serializer):
    """Serializer for comprehensive monitoring results"""

    status = serializers.CharField()
    user_id = serializers.IntegerField()
    device_id = serializers.CharField()
    timestamp = serializers.DateTimeField()
    overall_status = serializers.CharField()
    monitoring_results = serializers.DictField()
    alerts = serializers.ListField()
    recommendations = serializers.ListField()
    risk_assessment = serializers.DictField(required=False)