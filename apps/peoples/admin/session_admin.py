"""
Session Management Admin Interface

Django admin interface for session oversight and security monitoring.

Features:
    - View all user sessions
    - Monitor suspicious sessions
    - Bulk session revocation
    - Session activity logs
    - Device tracking
"""

from django.contrib import admin
from django.utils.html import format_html
from django.utils import timezone
from django.urls import reverse
from django.utils.safestring import mark_safe

from apps.peoples.models import UserSession, SessionActivityLog


@admin.register(UserSession)
class UserSessionAdmin(admin.ModelAdmin):
    list_per_page = 50
    """
    Admin interface for user sessions.

    Features:
        - View all sessions with device info
        - Filter by status, device type, suspicious flag
        - Search by username, IP address
        - Bulk revoke action
        - Color-coded status indicators
    """

    list_display = [
        'user',
        'device_display',
        'ip_address_display',
        'location_display',
        'status_badge',
        'created_at',
        'last_activity',
        'actions_column'
    ]

    list_filter = [
        'revoked',
        'is_suspicious',
        'device_type',
        'is_current',
        ('created_at', admin.DateFieldListFilter),
        ('last_activity', admin.DateFieldListFilter),
    ]

    search_fields = [
        'user__loginid',
        'user__peoplename',
        'ip_address',
        'last_ip_address',
        'device_name',
        'device_fingerprint'
    ]

    readonly_fields = [
        'session',
        'user',
        'device_fingerprint',
        'device_name',
        'device_type',
        'user_agent',
        'browser',
        'browser_version',
        'os',
        'os_version',
        'ip_address',
        'last_ip_address',
        'country',
        'city',
        'created_at',
        'last_activity',
        'expires_at',
        'is_current',
        'is_suspicious',
        'suspicious_reason',
        'revoked',
        'revoked_at',
        'revoked_by',
        'revoke_reason',
        'is_expired_display',
        'activity_log_link'
    ]

    date_hierarchy = 'created_at'
    ordering = ['-last_activity']

    actions = ['revoke_selected_sessions', 'flag_as_suspicious']

    fieldsets = (
        ('User Information', {
            'fields': ('user', 'session')
        }),
        ('Device Information', {
            'fields': (
                'device_fingerprint',
                'device_name',
                'device_type',
                'user_agent',
                ('browser', 'browser_version'),
                ('os', 'os_version'),
            )
        }),
        ('Location Information', {
            'fields': (
                'ip_address',
                'last_ip_address',
                'country',
                'city',
            )
        }),
        ('Session Lifecycle', {
            'fields': (
                'created_at',
                'last_activity',
                'expires_at',
                'is_expired_display',
                'is_current',
            )
        }),
        ('Security', {
            'fields': (
                'is_suspicious',
                'suspicious_reason',
            )
        }),
        ('Revocation', {
            'fields': (
                'revoked',
                'revoked_at',
                'revoked_by',
                'revoke_reason',
            )
        }),
        ('Activity Logs', {
            'fields': ('activity_log_link',)
        }),
    )

    def has_add_permission(self, request):
        """Prevent manual creation of sessions."""
        return False

    def device_display(self, obj):
        """Display device information."""
        return obj.get_device_display()
    device_display.short_description = 'Device'

    def ip_address_display(self, obj):
        """Display current IP address."""
        return obj.last_ip_address or obj.ip_address
    ip_address_display.short_description = 'IP Address'

    def location_display(self, obj):
        """Display location."""
        return obj.get_location_display()
    location_display.short_description = 'Location'

    def status_badge(self, obj):
        """Display session status with color badge."""
        if obj.revoked:
            return format_html(
                '<span style="background-color: #6c757d; color: white; '
                'padding: 3px 10px; border-radius: 3px;">REVOKED</span>'
            )
        elif obj.is_expired():
            return format_html(
                '<span style="background-color: #ffc107; color: black; '
                'padding: 3px 10px; border-radius: 3px;">EXPIRED</span>'
            )
        elif obj.is_suspicious:
            return format_html(
                '<span style="background-color: #dc3545; color: white; '
                'padding: 3px 10px; border-radius: 3px;">SUSPICIOUS</span>'
            )
        elif obj.is_current:
            return format_html(
                '<span style="background-color: #28a745; color: white; '
                'padding: 3px 10px; border-radius: 3px;">ACTIVE (CURRENT)</span>'
            )
        else:
            return format_html(
                '<span style="background-color: #17a2b8; color: white; '
                'padding: 3px 10px; border-radius: 3px;">ACTIVE</span>'
            )
    status_badge.short_description = 'Status'

    def actions_column(self, obj):
        """Display action buttons."""
        if not obj.revoked and not obj.is_expired():
            return format_html(
                '<a class="button" href="#" onclick="return confirm('
                '\'Revoke this session?\');">Revoke</a>'
            )
        return '-'
    actions_column.short_description = 'Actions'

    def is_expired_display(self, obj):
        """Display whether session has expired."""
        return obj.is_expired()
    is_expired_display.short_description = 'Is Expired'
    is_expired_display.boolean = True

    def activity_log_link(self, obj):
        """Link to session activity logs."""
        url = reverse('admin:peoples_sessionactivitylog_changelist')
        return mark_safe(
            f'<a href="{url}?session__id__exact={obj.id}">View Activity Logs</a>'
        )
    activity_log_link.short_description = 'Activity Logs'

    def revoke_selected_sessions(self, request, queryset):
        """
        Admin action to revoke selected sessions.

        Security:
            - Records who revoked the sessions
            - Updates all relevant fields
            - Logs action for audit
        """
        count = 0
        for session in queryset.filter(revoked=False):
            session.revoke(revoked_by=request.user, reason='admin_action')
            count += 1

        self.message_user(
            request,
            f'Successfully revoked {count} session(s).'
        )
    revoke_selected_sessions.short_description = 'Revoke selected sessions'

    def flag_as_suspicious(self, request, queryset):
        """
        Admin action to flag sessions as suspicious.
        """
        count = queryset.filter(revoked=False).update(
            is_suspicious=True,
            suspicious_reason='Manually flagged by admin'
        )

        self.message_user(
            request,
            f'Flagged {count} session(s) as suspicious.'
        )
    flag_as_suspicious.short_description = 'Flag as suspicious'


@admin.register(SessionActivityLog)
class SessionActivityLogAdmin(admin.ModelAdmin):
    list_per_page = 50
    """
    Admin interface for session activity logs.

    Features:
        - View all session activities
        - Filter by activity type, suspicious flag
        - Search by user, IP address
        - Read-only audit log
    """

    list_display = [
        'timestamp',
        'session_user',
        'activity_type',
        'ip_address',
        'suspicious_badge',
        'description_short'
    ]

    list_filter = [
        'activity_type',
        'is_suspicious',
        ('timestamp', admin.DateFieldListFilter),
    ]

    search_fields = [
        'session__user__loginid',
        'session__user__peoplename',
        'ip_address',
        'description',
        'url'
    ]

    readonly_fields = [
        'session',
        'activity_type',
        'description',
        'ip_address',
        'url',
        'metadata',
        'is_suspicious',
        'timestamp'
    ]

    date_hierarchy = 'timestamp'
    ordering = ['-timestamp']

    # Disable add/edit/delete (audit logs are immutable)
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def session_user(self, obj):
        """Display user from session."""
        return obj.session.user.loginid
    session_user.short_description = 'User'
    session_user.admin_order_field = 'session__user__loginid'

    def description_short(self, obj):
        """Display truncated description."""
        if len(obj.description) > 50:
            return obj.description[:50] + '...'
        return obj.description
    description_short.short_description = 'Description'

    def suspicious_badge(self, obj):
        """Display suspicious flag with badge."""
        if obj.is_suspicious:
            return format_html(
                '<span style="background-color: #dc3545; color: white; '
                'padding: 3px 10px; border-radius: 3px;">SUSPICIOUS</span>'
            )
        return '-'
    suspicious_badge.short_description = 'Suspicious'
