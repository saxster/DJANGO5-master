"""
Audit Log Serializers

Serializers for audit log API endpoints.

Features:
- Read-only serialization (audit logs should not be modifiable)
- Nested serialization for related objects
- Custom fields for computed values
"""

from rest_framework import serializers
from apps.attendance.models.audit_log import AttendanceAccessLog
from django.contrib.auth import get_user_model
from datetime import datetime

User = get_user_model()


class UserSummarySerializer(serializers.ModelSerializer):
    """Minimal user information for audit logs"""

    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name']
        read_only_fields = fields


class AttendanceAccessLogSerializer(serializers.ModelSerializer):
    """
    Serializer for attendance access log entries.

    Includes nested user information and computed fields.
    """

    user = UserSummarySerializer(read_only=True)
    impersonated_by = UserSummarySerializer(read_only=True)
    action_display = serializers.CharField(source='get_action_display', read_only=True)
    resource_type_display = serializers.CharField(source='get_resource_type_display', read_only=True)

    # Computed fields
    is_failed = serializers.BooleanField(source='is_failed_access', read_only=True)
    is_unauthorized = serializers.BooleanField(read_only=True)
    is_slow = serializers.BooleanField(source='is_slow_operation', read_only=True)

    # Attendance record details (if present)
    attendance_record_details = serializers.SerializerMethodField()

    class Meta:
        model = AttendanceAccessLog
        fields = [
            'id',
            'uuid',
            'timestamp',
            'user',
            'impersonated_by',
            'action',
            'action_display',
            'resource_type',
            'resource_type_display',
            'resource_id',
            'attendance_record',
            'attendance_record_details',
            'duration_ms',
            'ip_address',
            'user_agent',
            'request_path',
            'http_method',
            'status_code',
            'correlation_id',
            'old_values',
            'new_values',
            'notes',
            'is_suspicious',
            'risk_score',
            'is_failed',
            'is_unauthorized',
            'is_slow',
        ]
        read_only_fields = fields

    def get_attendance_record_details(self, obj):
        """Get minimal details about the attendance record"""
        if obj.attendance_record:
            return {
                'id': obj.attendance_record.id,
                'employee': obj.attendance_record.people.username if obj.attendance_record.people else None,
                'date': obj.attendance_record.datefor,
                'punch_in': obj.attendance_record.punchintime,
                'punch_out': obj.attendance_record.punchouttime,
            }
        return None


class AuditLogFilterSerializer(serializers.Serializer):
    """Serializer for audit log filter parameters"""

    user_id = serializers.IntegerField(required=False, help_text="Filter by user ID")
    action = serializers.ChoiceField(
        choices=AttendanceAccessLog.Action.choices,
        required=False,
        help_text="Filter by action type"
    )
    start_date = serializers.DateTimeField(required=False, help_text="Start of date range")
    end_date = serializers.DateTimeField(required=False, help_text="End of date range")
    ip_address = serializers.IPAddressField(required=False, help_text="Filter by IP address")
    status_code = serializers.IntegerField(required=False, help_text="Filter by HTTP status code")
    is_suspicious = serializers.BooleanField(required=False, help_text="Filter suspicious activity")
    tenant = serializers.CharField(required=False, max_length=100, help_text="Filter by tenant")


class ComplianceReportRequestSerializer(serializers.Serializer):
    """Serializer for compliance report request"""

    start_date = serializers.DateField(
        required=True,
        help_text="Report start date (YYYY-MM-DD)"
    )
    end_date = serializers.DateField(
        required=True,
        help_text="Report end date (YYYY-MM-DD)"
    )
    tenant = serializers.CharField(
        required=False,
        max_length=100,
        help_text="Optional tenant filter"
    )

    def validate(self, data):
        """Validate date range"""
        if data['end_date'] < data['start_date']:
            raise serializers.ValidationError("end_date must be after start_date")

        # Convert to datetime for service compatibility
        data['start_date'] = datetime.combine(data['start_date'], datetime.min.time())
        data['end_date'] = datetime.combine(data['end_date'], datetime.max.time())

        return data


class InvestigationRequestSerializer(serializers.Serializer):
    """Serializer for investigation request"""

    user_id = serializers.IntegerField(
        required=True,
        help_text="User ID to investigate"
    )
    days = serializers.IntegerField(
        required=False,
        default=90,
        min_value=1,
        max_value=365,
        help_text="Number of days to investigate (1-365)"
    )


class AuditStatisticsSerializer(serializers.Serializer):
    """Serializer for audit statistics response"""

    total_accesses = serializers.IntegerField()
    unique_users = serializers.IntegerField()
    by_action = serializers.DictField()
    failed_accesses = serializers.IntegerField()
    suspicious_accesses = serializers.IntegerField()
    avg_duration_ms = serializers.FloatField(allow_null=True)
    peak_access_time = serializers.IntegerField(allow_null=True)


class ComplianceReportSerializer(serializers.Serializer):
    """Serializer for compliance report response"""

    report_period = serializers.DictField()
    access_summary = serializers.DictField()
    by_action = serializers.DictField()
    by_resource_type = serializers.DictField()
    security_events = serializers.DictField()
    performance_metrics = serializers.DictField()
    audit_coverage = serializers.DictField()
