"""
Security Audit Admin Interface

Provides Django admin interface for security event monitoring.
"""

from django.contrib import admin
from django.utils.html import format_html
from django.utils import timezone
from apps.peoples.models.security_models import LoginAttemptLog, AccountLockout


@admin.register(LoginAttemptLog)
class LoginAttemptLogAdmin(admin.ModelAdmin):
    """
    Admin interface for login attempt logs.

    Features:
        - Read-only view (no editing of audit logs)
        - Search by username, IP address
        - Filter by success, failure reason, date
        - Color-coded success/failure display
    """

    list_display = [
        'created_at',
        'username',
        'ip_address',
        'success_badge',
        'failure_reason',
        'access_type'
    ]

    list_filter = [
        'success',
        'failure_reason',
        'access_type',
        ('created_at', admin.DateFieldListFilter),
    ]

    search_fields = [
        'username',
        'ip_address',
        'correlation_id'
    ]

    readonly_fields = [
        'username',
        'ip_address',
        'success',
        'failure_reason',
        'user_agent',
        'access_type',
        'correlation_id',
        'created_at'
    ]

    date_hierarchy = 'created_at'
    ordering = ['-created_at']

    # Disable add/edit/delete (audit logs are immutable)
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def success_badge(self, obj):
        """Display success status with color badge."""
        if obj.success:
            return format_html(
                '<span style="background-color: #28a745; color: white; '
                'padding: 3px 10px; border-radius: 3px;">SUCCESS</span>'
            )
        else:
            return format_html(
                '<span style="background-color: #dc3545; color: white; '
                'padding: 3px 10px; border-radius: 3px;">FAILED</span>'
            )
    success_badge.short_description = 'Status'


@admin.register(AccountLockout)
class AccountLockoutAdmin(admin.ModelAdmin):
    """
    Admin interface for account lockouts.

    Features:
        - View active and expired lockouts
        - Manual unlock capability
        - Search by username, IP
        - Filter by lockout type, status
        - Bulk unlock action
    """

    list_display = [
        'username',
        'lockout_type',
        'status_badge',
        'locked_at',
        'locked_until',
        'attempt_count',
        'unlocked_by'
    ]

    list_filter = [
        'is_active',
        'lockout_type',
        ('locked_at', admin.DateFieldListFilter),
    ]

    search_fields = [
        'username',
        'ip_address'
    ]

    readonly_fields = [
        'username',
        'ip_address',
        'lockout_type',
        'reason',
        'locked_at',
        'locked_until',
        'attempt_count',
        'is_expired_display',
        'unlocked_at',
        'unlocked_by'
    ]

    date_hierarchy = 'locked_at'
    ordering = ['-locked_at']

    actions = ['unlock_selected_accounts']

    def has_add_permission(self, request):
        """Prevent manual creation of lockouts."""
        return False

    def status_badge(self, obj):
        """Display lockout status with color badge."""
        if not obj.is_active:
            return format_html(
                '<span style="background-color: #6c757d; color: white; '
                'padding: 3px 10px; border-radius: 3px;">UNLOCKED</span>'
            )
        elif obj.is_expired():
            return format_html(
                '<span style="background-color: #ffc107; color: black; '
                'padding: 3px 10px; border-radius: 3px;">EXPIRED</span>'
            )
        else:
            return format_html(
                '<span style="background-color: #dc3545; color: white; '
                'padding: 3px 10px; border-radius: 3px;">ACTIVE</span>'
            )
    status_badge.short_description = 'Status'

    def is_expired_display(self, obj):
        """Display whether lockout has expired."""
        return obj.is_expired()
    is_expired_display.short_description = 'Is Expired'
    is_expired_display.boolean = True

    def unlock_selected_accounts(self, request, queryset):
        """
        Admin action to manually unlock selected accounts.

        Security:
            - Records who unlocked the account
            - Updates all relevant fields
            - Logs action for audit
        """
        count = 0
        for lockout in queryset.filter(is_active=True):
            lockout.unlock(unlocked_by=request.user)
            count += 1

        self.message_user(
            request,
            f'Successfully unlocked {count} account(s).'
        )
    unlock_selected_accounts.short_description = 'Unlock selected accounts'
