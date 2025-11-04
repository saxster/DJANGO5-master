"""
Enhanced Django Admin for Attendance Models

Provides admin interfaces for all new attendance enhancement models.

Models:
- AttendanceAccessLog (audit logging)
- ConsentPolicy (consent management)
- EmployeeConsentLog (consent tracking)
- ConsentRequirement (consent rules)
- AttendancePhoto (photo storage)
- PhotoQualityThreshold (photo settings)
- UserBehaviorProfile (fraud detection)
- FraudAlert (fraud alerts)
- SyncConflict (mobile sync)
"""

from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils import timezone
from apps.attendance.models.audit_log import AttendanceAccessLog, AuditLogRetentionPolicy
from apps.attendance.models.consent import ConsentPolicy, EmployeeConsentLog, ConsentRequirement
from apps.attendance.models.attendance_photo import AttendancePhoto, PhotoQualityThreshold
from apps.attendance.models.user_behavior_profile import UserBehaviorProfile
from apps.attendance.models.fraud_alert import FraudAlert
from apps.attendance.models.sync_conflict import SyncConflict


@admin.register(AttendanceAccessLog)
class AttendanceAccessLogAdmin(admin.ModelAdmin):
    """Admin for attendance access audit logs"""

    list_display = [
        'id', 'timestamp', 'user_link', 'action_badge', 'resource_type',
        'status_badge', 'duration_ms', 'suspicious_badge', 'risk_score'
    ]

    list_filter = [
        'action', 'resource_type', 'status_code', 'is_suspicious',
        ('timestamp', admin.DateFieldListFilter),
    ]

    search_fields = [
        'user__username', 'user__email', 'ip_address',
        'correlation_id', 'notes'
    ]

    readonly_fields = [
        'uuid', 'user', 'action', 'timestamp', 'duration_ms',
        'ip_address', 'user_agent', 'request_path', 'http_method',
        'status_code', 'correlation_id', 'old_values', 'new_values',
        'attendance_record', 'resource_type', 'resource_id',
        'impersonated_by'
    ]

    date_hierarchy = 'timestamp'
    ordering = ['-timestamp']

    fieldsets = (
        ('Basic Information', {
            'fields': ('uuid', 'timestamp', 'user', 'impersonated_by')
        }),
        ('Action Details', {
            'fields': ('action', 'resource_type', 'resource_id', 'attendance_record')
        }),
        ('Request Information', {
            'fields': ('http_method', 'request_path', 'status_code', 'duration_ms')
        }),
        ('Client Information', {
            'fields': ('ip_address', 'user_agent', 'correlation_id')
        }),
        ('Changes', {
            'fields': ('old_values', 'new_values'),
            'classes': ('collapse',)
        }),
        ('Security', {
            'fields': ('is_suspicious', 'risk_score', 'notes')
        }),
    )

    def user_link(self, obj):
        """Link to user"""
        if obj.user:
            url = reverse('admin:peoples_people_change', args=[obj.user.id])
            return format_html('<a href="{}">{}</a>', url, obj.user.username)
        return '-'
    user_link.short_description = 'User'

    def action_badge(self, obj):
        """Colored badge for action"""
        colors = {
            'VIEW': 'blue',
            'CREATE': 'green',
            'UPDATE': 'orange',
            'DELETE': 'red',
            'EXPORT': 'purple',
        }
        color = colors.get(obj.action, 'gray')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 10px; border-radius: 3px;">{}</span>',
            color, obj.get_action_display()
        )
    action_badge.short_description = 'Action'

    def status_badge(self, obj):
        """Colored badge for HTTP status"""
        if obj.status_code:
            if obj.status_code < 300:
                color = 'green'
            elif obj.status_code < 400:
                color = 'blue'
            elif obj.status_code < 500:
                color = 'orange'
            else:
                color = 'red'
            return format_html(
                '<span style="background-color: {}; color: white; padding: 3px 10px; border-radius: 3px;">{}</span>',
                color, obj.status_code
            )
        return '-'
    status_badge.short_description = 'Status'

    def suspicious_badge(self, obj):
        """Badge for suspicious activity"""
        if obj.is_suspicious:
            return format_html(
                '<span style="background-color: red; color: white; padding: 3px 10px; border-radius: 3px;">⚠ SUSPICIOUS</span>'
            )
        return '-'
    suspicious_badge.short_description = 'Suspicious'

    def has_add_permission(self, request):
        """Audit logs are created automatically, not manually"""
        return False

    def has_delete_permission(self, request, obj=None):
        """Audit logs should not be deleted (immutable)"""
        return request.user.is_superuser  # Only superusers can delete


@admin.register(ConsentPolicy)
class ConsentPolicyAdmin(admin.ModelAdmin):
    """Admin for consent policies"""

    list_display = [
        'id', 'title', 'policy_type', 'state', 'version',
        'effective_date', 'active_badge', 'requires_signature'
    ]

    list_filter = ['policy_type', 'state', 'is_active', 'requires_signature', 'requires_written_consent']
    search_fields = ['title', 'summary', 'policy_text']
    date_hierarchy = 'effective_date'

    fieldsets = (
        ('Policy Information', {
            'fields': ('uuid', 'policy_type', 'state', 'version', 'title')
        }),
        ('Policy Content', {
            'fields': ('summary', 'policy_text')
        }),
        ('Effective Dates', {
            'fields': ('effective_date', 'expiration_date')
        }),
        ('Requirements', {
            'fields': ('requires_signature', 'requires_written_consent', 'is_active')
        }),
    )

    readonly_fields = ['uuid']

    def active_badge(self, obj):
        """Badge for active status"""
        if obj.is_active:
            return format_html('<span style="color: green;">✓ Active</span>')
        return format_html('<span style="color: gray;">✗ Inactive</span>')
    active_badge.short_description = 'Status'


@admin.register(EmployeeConsentLog)
class EmployeeConsentLogAdmin(admin.ModelAdmin):
    """Admin for employee consent logs"""

    list_display = [
        'id', 'employee_link', 'policy_type', 'status_badge',
        'granted_at', 'expires_at', 'is_active_badge'
    ]

    list_filter = [
        'status', 'policy__policy_type', 'policy__state',
        ('granted_at', admin.DateFieldListFilter),
    ]

    search_fields = ['employee__username', 'employee__email', 'policy__title']

    readonly_fields = [
        'uuid', 'granted_at', 'granted_ip', 'granted_user_agent',
        'revoked_at', 'revoked_ip', 'notification_sent_at', 'reminder_sent_at'
    ]

    fieldsets = (
        ('Basic Information', {
            'fields': ('uuid', 'employee', 'policy', 'status')
        }),
        ('Grant Information', {
            'fields': ('granted_at', 'granted_ip', 'granted_user_agent', 'signature_type')
        }),
        ('Signature', {
            'fields': ('signature_data', 'written_consent_document'),
            'classes': ('collapse',)
        }),
        ('Revocation', {
            'fields': ('revoked_at', 'revoked_reason', 'revoked_ip'),
            'classes': ('collapse',)
        }),
        ('Expiration', {
            'fields': ('expires_at',)
        }),
        ('Notifications', {
            'fields': ('notification_sent_at', 'reminder_sent_at'),
            'classes': ('collapse',)
        }),
        ('Notes', {
            'fields': ('notes',)
        }),
    )

    def employee_link(self, obj):
        """Link to employee"""
        url = reverse('admin:peoples_people_change', args=[obj.employee.id])
        return format_html('<a href="{}">{}</a>', url, obj.employee.username)
    employee_link.short_description = 'Employee'

    def policy_type(self, obj):
        """Policy type"""
        return obj.policy.get_policy_type_display()
    policy_type.short_description = 'Policy Type'

    def status_badge(self, obj):
        """Colored status badge"""
        colors = {
            'PENDING': 'gray',
            'GRANTED': 'green',
            'REVOKED': 'red',
            'EXPIRED': 'orange',
            'DENIED': 'red',
        }
        color = colors.get(obj.status, 'gray')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 10px; border-radius: 3px;">{}</span>',
            color, obj.get_status_display()
        )
    status_badge.short_description = 'Status'

    def is_active_badge(self, obj):
        """Badge showing if consent is currently active"""
        if obj.is_active():
            return format_html('<span style="color: green;">✓ Active</span>')
        return format_html('<span style="color: red;">✗ Inactive</span>')
    is_active_badge.short_description = 'Active'


@admin.register(AttendancePhoto)
class AttendancePhotoAdmin(admin.ModelAdmin):
    """Admin for attendance photos"""

    list_display = [
        'id', 'employee_link', 'photo_type', 'captured_at',
        'quality_badge', 'face_badge', 'validation_badge', 'size_kb'
    ]

    list_filter = [
        'photo_type', 'quality_rating', 'validation_passed',
        'face_detected', 'is_deleted',
        ('captured_at', admin.DateFieldListFilter),
    ]

    search_fields = ['employee__username', 'attendance_record__id']

    readonly_fields = [
        'uuid', 'captured_at', 'file_size_bytes', 'width', 'height',
        'face_detected', 'face_count', 'face_confidence',
        'quality_score', 'quality_rating', 'is_blurry', 'is_dark',
        'brightness', 'matches_enrolled_template', 'match_confidence',
        'validation_passed', 'validation_errors', 'image_preview'
    ]

    fieldsets = (
        ('Basic Information', {
            'fields': ('uuid', 'employee', 'attendance_record', 'photo_type', 'captured_at')
        }),
        ('Photo', {
            'fields': ('image', 'image_preview', 'thumbnail')
        }),
        ('Quality Metrics', {
            'fields': ('quality_score', 'quality_rating', 'is_blurry', 'is_dark', 'brightness')
        }),
        ('Face Detection', {
            'fields': ('face_detected', 'face_count', 'face_confidence')
        }),
        ('Face Matching', {
            'fields': ('matches_enrolled_template', 'match_confidence', 'face_recognition_model')
        }),
        ('Technical', {
            'fields': ('width', 'height', 'file_size_bytes', 'device_info', 'gps_location'),
            'classes': ('collapse',)
        }),
        ('Validation', {
            'fields': ('validation_passed', 'validation_errors')
        }),
        ('Retention', {
            'fields': ('delete_after', 'is_deleted', 'deleted_at')
        }),
    )

    def employee_link(self, obj):
        """Link to employee"""
        url = reverse('admin:peoples_people_change', args=[obj.employee.id])
        return format_html('<a href="{}">{}</a>', url, obj.employee.username)
    employee_link.short_description = 'Employee'

    def quality_badge(self, obj):
        """Quality rating badge"""
        colors = {
            'EXCELLENT': 'green',
            'GOOD': 'blue',
            'ACCEPTABLE': 'orange',
            'POOR': 'red',
            'REJECTED': 'darkred',
        }
        color = colors.get(obj.quality_rating, 'gray')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 10px; border-radius: 3px;">{}</span>',
            color, obj.quality_rating or 'N/A'
        )
    quality_badge.short_description = 'Quality'

    def face_badge(self, obj):
        """Face detection badge"""
        if obj.face_detected:
            return format_html(
                '<span style="color: green;">✓ {} face(s)</span>', obj.face_count
            )
        return format_html('<span style="color: red;">✗ No face</span>')
    face_badge.short_description = 'Face'

    def validation_badge(self, obj):
        """Validation status badge"""
        if obj.validation_passed:
            return format_html('<span style="color: green;">✓ Passed</span>')
        return format_html('<span style="color: red;">✗ Failed</span>')
    validation_badge.short_description = 'Validation'

    def size_kb(self, obj):
        """File size in KB"""
        if obj.file_size_bytes:
            return f"{obj.file_size_bytes / 1024:.1f} KB"
        return '-'
    size_kb.short_description = 'Size'

    def image_preview(self, obj):
        """Show image preview"""
        if obj.image:
            return format_html(
                '<img src="{}" style="max-width: 300px; max-height: 300px;" />',
                obj.image.url
            )
        return '-'
    image_preview.short_description = 'Preview'


@admin.register(UserBehaviorProfile)
class UserBehaviorProfileAdmin(admin.ModelAdmin):
    """Admin for user behavior profiles (fraud detection)"""

    list_display = [
        'id', 'employee_link', 'is_baseline_sufficient', 'training_records_count',
        'typical_checkin_hour', 'total_checkins', 'anomalies_detected',
        'last_anomaly_at'
    ]

    list_filter = ['is_baseline_sufficient', ('baseline_updated_at', admin.DateFieldListFilter)]
    search_fields = ['employee__username', 'employee__email']

    readonly_fields = [
        'uuid', 'baseline_created_at', 'baseline_updated_at',
        'training_records_count', 'total_checkins', 'anomalies_detected',
        'false_positives', 'detection_accuracy', 'last_anomaly_at'
    ]

    fieldsets = (
        ('Employee', {
            'fields': ('uuid', 'employee', 'tenant')
        }),
        ('Baseline Status', {
            'fields': (
                'is_baseline_sufficient', 'training_records_count',
                'baseline_created_at', 'baseline_updated_at'
            )
        }),
        ('Temporal Patterns', {
            'fields': (
                'typical_checkin_hour', 'typical_checkin_minute',
                'checkin_time_variance_minutes', 'typical_checkout_hour',
                'typical_work_duration_minutes', 'work_duration_variance_minutes'
            )
        }),
        ('Location Patterns', {
            'fields': ('typical_locations', 'typical_geofences', 'location_radius_meters'),
            'classes': ('collapse',)
        }),
        ('Device Patterns', {
            'fields': ('typical_devices', 'device_change_tolerance'),
            'classes': ('collapse',)
        }),
        ('Work Patterns', {
            'fields': ('typical_work_days', 'typical_transport_modes'),
            'classes': ('collapse',)
        }),
        ('Detection Settings', {
            'fields': ('anomaly_score_threshold', 'auto_block_threshold')
        }),
        ('Statistics', {
            'fields': (
                'total_checkins', 'anomalies_detected',
                'false_positives', 'detection_accuracy', 'last_anomaly_at'
            )
        }),
    )

    def employee_link(self, obj):
        """Link to employee"""
        url = reverse('admin:peoples_people_change', args=[obj.employee.id])
        return format_html('<a href="{}">{}</a>', url, obj.employee.username)
    employee_link.short_description = 'Employee'

    actions = ['retrain_baseline']

    def retrain_baseline(self, request, queryset):
        """Action to retrain baselines for selected employees"""
        from apps.attendance.ml_models import BehavioralAnomalyDetector

        trained = 0
        for profile in queryset:
            detector = BehavioralAnomalyDetector(profile.employee)
            if detector.train_baseline(force_retrain=True):
                trained += 1

        self.message_user(request, f"Retrained {trained} behavior baselines")
    retrain_baseline.short_description = "Retrain fraud detection baseline"


@admin.register(FraudAlert)
class FraudAlertAdmin(admin.ModelAdmin):
    """Admin for fraud alerts"""

    list_display = [
        'id', 'employee_link', 'alert_type', 'severity_badge',
        'status_badge', 'fraud_score', 'detection_timestamp',
        'assigned_to', 'resolved_at'
    ]

    list_filter = [
        'alert_type', 'severity', 'status', 'auto_blocked',
        ('detection_timestamp', admin.DateFieldListFilter),
    ]

    search_fields = [
        'employee__username', 'assigned_to__username',
        'investigation_notes', 'resolution_notes'
    ]

    readonly_fields = [
        'uuid', 'detection_timestamp', 'fraud_score', 'risk_score',
        'evidence', 'anomalies_detected', 'auto_blocked'
    ]

    date_hierarchy = 'detection_timestamp'
    ordering = ['-detection_timestamp']

    fieldsets = (
        ('Alert Information', {
            'fields': ('uuid', 'employee', 'attendance_record', 'detection_timestamp')
        }),
        ('Classification', {
            'fields': ('alert_type', 'severity', 'status')
        }),
        ('Risk Assessment', {
            'fields': ('fraud_score', 'risk_score', 'auto_blocked')
        }),
        ('Evidence', {
            'fields': ('anomalies_detected', 'evidence'),
            'classes': ('collapse',)
        }),
        ('Investigation', {
            'fields': (
                'assigned_to', 'assigned_at',
                'investigation_notes'
            )
        }),
        ('Resolution', {
            'fields': (
                'resolved_by', 'resolved_at',
                'resolution_notes'
            )
        }),
        ('Escalation', {
            'fields': ('is_escalated', 'escalated_at', 'escalation_reason'),
            'classes': ('collapse',)
        }),
        ('Notifications', {
            'fields': ('manager_notified', 'employee_notified')
        }),
    )

    def employee_link(self, obj):
        """Link to employee"""
        url = reverse('admin:peoples_people_change', args=[obj.employee.id])
        return format_html('<a href="{}">{}</a>', url, obj.employee.username)
    employee_link.short_description = 'Employee'

    def severity_badge(self, obj):
        """Severity badge"""
        colors = {
            'LOW': 'blue',
            'MEDIUM': 'orange',
            'HIGH': 'darkorange',
            'CRITICAL': 'red',
        }
        color = colors.get(obj.severity, 'gray')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 10px; border-radius: 3px; font-weight: bold;">{}</span>',
            color, obj.get_severity_display()
        )
    severity_badge.short_description = 'Severity'

    def status_badge(self, obj):
        """Status badge"""
        colors = {
            'PENDING': 'gray',
            'INVESTIGATING': 'blue',
            'RESOLVED_LEGITIMATE': 'green',
            'RESOLVED_FRAUD': 'red',
            'FALSE_POSITIVE': 'orange',
            'ESCALATED': 'purple',
        }
        color = colors.get(obj.status, 'gray')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 10px; border-radius: 3px;">{}</span>',
            color, obj.get_status_display()
        )
    status_badge.short_description = 'Status'

    actions = ['assign_to_me', 'mark_as_investigating', 'mark_as_false_positive']

    def assign_to_me(self, request, queryset):
        """Assign selected alerts to current user"""
        updated = queryset.filter(status='PENDING').update(
            assigned_to=request.user,
            assigned_at=timezone.now(),
            status=FraudAlert.Status.INVESTIGATING
        )
        self.message_user(request, f"Assigned {updated} alerts to you")
    assign_to_me.short_description = "Assign to me and start investigating"

    def mark_as_investigating(self, request, queryset):
        """Mark as investigating"""
        updated = queryset.update(status=FraudAlert.Status.INVESTIGATING)
        self.message_user(request, f"Marked {updated} alerts as investigating")
    mark_as_investigating.short_description = "Mark as investigating"

    def mark_as_false_positive(self, request, queryset):
        """Mark as false positive"""
        updated = queryset.update(
            status=FraudAlert.Status.FALSE_POSITIVE,
            resolved_by=request.user,
            resolved_at=timezone.now()
        )

        # Update employee profiles to reduce false positives
        for alert in queryset:
            if hasattr(alert.employee, 'behavior_profile'):
                profile = alert.employee.behavior_profile
                profile.false_positives += 1
                profile.save()

        self.message_user(request, f"Marked {updated} alerts as false positive")
    mark_as_false_positive.short_description = "Mark as false positive"


@admin.register(SyncConflict)
class SyncConflictAdmin(admin.ModelAdmin):
    """Admin for mobile sync conflicts"""

    list_display = [
        'id', 'employee_link', 'conflict_type', 'resolution',
        'detected_at', 'user_notified', 'device_id'
    ]

    list_filter = ['conflict_type', 'resolution', 'user_notified']
    search_fields = ['employee__username', 'device_id']

    readonly_fields = [
        'uuid', 'detected_at', 'resolved_at',
        'client_version', 'server_version', 'device_id', 'app_version'
    ]

    def employee_link(self, obj):
        """Link to employee"""
        url = reverse('admin:peoples_people_change', args=[obj.employee.id])
        return format_html('<a href="{}">{}</a>', url, obj.employee.username)
    employee_link.short_description = 'Employee'


# Register remaining models
admin.site.register(AuditLogRetentionPolicy)
admin.site.register(ConsentRequirement)
admin.site.register(PhotoQualityThreshold)
