"""
Django Admin Configuration for Rate Limiting Models

Provides admin interface for managing:
- Blocked IPs
- Trusted IPs
- Violation logs
"""

from django.contrib import admin
from django.utils import timezone
from django.utils.html import format_html
from apps.core.models.rate_limiting import (
    RateLimitBlockedIP,
    RateLimitTrustedIP,
    RateLimitViolationLog
)


@admin.register(RateLimitBlockedIP)
class RateLimitBlockedIPAdmin(admin.ModelAdmin):
    """Admin interface for blocked IPs."""

    list_display = [
        'ip_address',
        'violation_count',
        'endpoint_type',
        'blocked_at',
        'blocked_until',
        'status_badge',
        'time_remaining'
    ]

    list_filter = [
        'is_active',
        'endpoint_type',
        'blocked_at',
        'blocked_until'
    ]

    search_fields = [
        'ip_address',
        'last_violation_path',
        'reason'
    ]

    readonly_fields = [
        'blocked_at',
        'violation_count',
        'endpoint_type',
        'last_violation_path',
        'time_remaining_display'
    ]

    fieldsets = [
        ('IP Information', {
            'fields': ['ip_address', 'is_active']
        }),
        ('Block Details', {
            'fields': [
                'blocked_at',
                'blocked_until',
                'time_remaining_display',
                'violation_count',
                'endpoint_type',
                'last_violation_path'
            ]
        }),
        ('Additional Information', {
            'fields': ['reason', 'notes']
        }),
    ]

    actions = ['unblock_ips', 'extend_block_24h']

    list_per_page = 50

    def status_badge(self, obj):
        """Display status as colored badge."""
        if obj.is_expired():
            return format_html(
                '<span style="color: green;">●</span> Expired'
            )
        elif obj.is_active:
            return format_html(
                '<span style="color: red;">●</span> Active'
            )
        else:
            return format_html(
                '<span style="color: gray;">●</span> Inactive'
            )
    status_badge.short_description = 'Status'

    def time_remaining(self, obj):
        """Display time remaining on block."""
        if obj.is_expired():
            return "Expired"

        delta = obj.blocked_until - timezone.now()
        hours = int(delta.total_seconds() // 3600)
        minutes = int((delta.total_seconds() % 3600) // 60)

        return f"{hours}h {minutes}m"
    time_remaining.short_description = 'Time Remaining'

    def time_remaining_display(self, obj):
        """Readonly field for time remaining."""
        return self.time_remaining(obj)
    time_remaining_display.short_description = 'Time Remaining'

    def unblock_ips(self, request, queryset):
        """Action to unblock selected IPs."""
        count = queryset.update(is_active=False)
        self.message_user(request, f'{count} IP(s) unblocked successfully.')
    unblock_ips.short_description = 'Unblock selected IPs'

    def extend_block_24h(self, request, queryset):
        """Action to extend block by 24 hours."""
        for obj in queryset:
            obj.extend_block(hours=24)
        self.message_user(request, f'{queryset.count()} block(s) extended by 24 hours.')
    extend_block_24h.short_description = 'Extend block by 24 hours'


@admin.register(RateLimitTrustedIP)
class RateLimitTrustedIPAdmin(admin.ModelAdmin):
    list_per_page = 50
    """Admin interface for trusted IPs."""

    list_display = [
        'ip_address',
        'description',
        'is_active',
        'added_at',
        'added_by',
        'expiry_status'
    ]

    list_filter = [
        'is_active',
        'added_at'
    ]

    search_fields = [
        'ip_address',
        'description',
        'notes'
    ]

    readonly_fields = [
        'added_at',
        'added_by'
    ]

    fieldsets = [
        ('IP Information', {
            'fields': ['ip_address', 'description', 'is_active']
        }),
        ('Trust Settings', {
            'fields': ['expires_at', 'notes']
        }),
        ('Audit Trail', {
            'fields': ['added_at', 'added_by']
        }),
    ]

    def expiry_status(self, obj):
        """Display expiry status."""
        if not obj.expires_at:
            return format_html(
                '<span style="color: green;">●</span> Permanent'
            )
        elif obj.is_expired():
            return format_html(
                '<span style="color: red;">●</span> Expired'
            )
        else:
            delta = obj.expires_at - timezone.now()
            days = delta.days
            return format_html(
                f'<span style="color: orange;">●</span> {days} days'
            )
    expiry_status.short_description = 'Expiry Status'


@admin.register(RateLimitViolationLog)
class RateLimitViolationLogAdmin(admin.ModelAdmin):
    list_per_page = 50
    """Admin interface for violation logs."""

    list_display = [
        'timestamp',
        'client_ip',
        'user',
        'endpoint_type',
        'violation_reason',
        'request_count',
        'rate_limit'
    ]

    list_filter = [
        'endpoint_type',
        'violation_reason',
        'timestamp'
    ]

    search_fields = [
        'client_ip',
        'endpoint_path',
        'correlation_id',
        'user__loginid'
    ]

    readonly_fields = [
        'timestamp',
        'client_ip',
        'user',
        'endpoint_path',
        'endpoint_type',
        'violation_reason',
        'request_count',
        'rate_limit',
        'correlation_id',
        'user_agent'
    ]

    fieldsets = [
        ('Violation Details', {
            'fields': [
                'timestamp',
                'client_ip',
                'user',
                'endpoint_path',
                'endpoint_type'
            ]
        }),
        ('Rate Limit Information', {
            'fields': [
                'violation_reason',
                'request_count',
                'rate_limit'
            ]
        }),
        ('Request Context', {
            'fields': [
                'correlation_id',
                'user_agent'
            ]
        }),
    ]

    def has_add_permission(self, request):
        """Disable manual creation of violation logs."""
        return False

    def has_change_permission(self, request, obj=None):
        """Make violation logs read-only."""
        return False