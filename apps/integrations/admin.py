"""
Django Admin for Webhook Management (Nov 2025).

Provides UI for managing webhook configurations, event subscriptions,
and delivery monitoring.
"""

from django.contrib import admin
from django.utils.html import format_html
from django.db.models import Count, Q
from django.utils import timezone
from datetime import timedelta

from apps.integrations.models import (
    WebhookConfiguration,
    WebhookEvent,
    WebhookDeliveryLog
)


class WebhookEventInline(admin.TabularInline):
    """Inline editor for webhook events."""
    model = WebhookEvent
    extra = 1
    fields = ['event_type']


@admin.register(WebhookConfiguration)
class WebhookConfigurationAdmin(admin.ModelAdmin):
    """Admin interface for webhook configuration."""

    list_display = [
        'name',
        'webhook_type',
        'status_indicator',
        'event_count',
        'success_rate_24h',
        'last_delivery',
        'created_at'
    ]

    list_filter = [
        'webhook_type',
        'enabled',
        'tenant',
        'created_at'
    ]

    search_fields = [
        'name',
        'url',
        'description',
        'webhook_id'
    ]

    readonly_fields = [
        'webhook_id',
        'created_at',
        'updated_at',
        'success_rate_24h',
        'last_delivery',
        'total_deliveries'
    ]

    fieldsets = (
        ('Identity', {
            'fields': ('webhook_id', 'name', 'description')
        }),
        ('Configuration', {
            'fields': ('webhook_type', 'url', 'secret')
        }),
        ('Behavior', {
            'fields': ('enabled', 'retry_count', 'timeout_seconds')
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at', 'tenant'),
            'classes': ('collapse',)
        }),
        ('Statistics', {
            'fields': ('success_rate_24h', 'last_delivery', 'total_deliveries'),
            'classes': ('collapse',)
        }),
    )

    inlines = [WebhookEventInline]

    def status_indicator(self, obj):
        """Visual indicator of webhook status."""
        if obj.enabled:
            return format_html('<span style="color: green;">● Active</span>')
        return format_html('<span style="color: red;">○ Disabled</span>')
    status_indicator.short_description = 'Status'

    def event_count(self, obj):
        """Count of subscribed events."""
        return obj.webhook_events.count()
    event_count.short_description = 'Events'

    def success_rate_24h(self, obj):
        """Success rate in last 24 hours."""
        last_24h = timezone.now() - timedelta(hours=24)

        logs = obj.delivery_logs.filter(delivered_at__gte=last_24h)
        total = logs.count()

        if total == 0:
            return "No deliveries"

        successful = logs.filter(success=True).count()
        rate = (successful / total * 100)

        color = 'green' if rate > 90 else 'orange' if rate > 70 else 'red'

        return format_html(
            f'<span style="color: {color};">{rate:.1f}% ({successful}/{total})</span>'
        )
    success_rate_24h.short_description = 'Success Rate (24h)'

    def last_delivery(self, obj):
        """Timestamp of last delivery attempt."""
        last_log = obj.delivery_logs.first()  # Already ordered by -delivered_at
        if last_log:
            return last_log.delivered_at
        return "Never"
    last_delivery.short_description = 'Last Delivery'

    def total_deliveries(self, obj):
        """Total delivery attempts."""
        return obj.delivery_logs.count()
    total_deliveries.short_description = 'Total Deliveries'

    actions = ['enable_webhooks', 'disable_webhooks', 'test_webhook']

    def enable_webhooks(self, request, queryset):
        """Bulk enable webhooks."""
        updated = queryset.update(enabled=True)
        self.message_user(request, f"Enabled {updated} webhook(s)")
    enable_webhooks.short_description = "Enable selected webhooks"

    def disable_webhooks(self, request, queryset):
        """Bulk disable webhooks."""
        updated = queryset.update(enabled=False)
        self.message_user(request, f"Disabled {updated} webhook(s)")
    disable_webhooks.short_description = "Disable selected webhooks"

    def test_webhook(self, request, queryset):
        """Send test delivery to selected webhooks."""
        for webhook in queryset:
            # Queue test delivery
            from apps.integrations.services.webhook_delivery_service import WebhookDeliveryService
            service = WebhookDeliveryService()
            service.deliver_test(webhook)

        self.message_user(
            request,
            f"Queued test deliveries for {queryset.count()} webhook(s)"
        )
    test_webhook.short_description = "Send test delivery"


@admin.register(WebhookEvent)
class WebhookEventAdmin(admin.ModelAdmin):
    """Admin interface for webhook events."""

    list_display = [
        'webhook',
        'event_type',
        'webhook_status',
        'created_at'
    ]

    list_filter = [
        'event_type',
        'webhook__webhook_type',
        'webhook__enabled'
    ]

    search_fields = [
        'event_type',
        'webhook__name'
    ]

    def webhook_status(self, obj):
        """Show webhook enabled status."""
        if obj.webhook.enabled:
            return "✅ Enabled"
        return "❌ Disabled"
    webhook_status.short_description = 'Webhook Status'


@admin.register(WebhookDeliveryLog)
class WebhookDeliveryLogAdmin(admin.ModelAdmin):
    """Admin interface for webhook delivery logs."""

    list_display = [
        'webhook',
        'event_type',
        'status_icon',
        'http_status_code',
        'response_time_ms',
        'attempt_number',
        'delivered_at'
    ]

    list_filter = [
        'success',
        'webhook__webhook_type',
        'event_type',
        'delivered_at',
        'tenant'
    ]

    search_fields = [
        'webhook__name',
        'event_type',
        'error_message'
    ]

    readonly_fields = [
        'webhook',
        'event_type',
        'delivered_at',
        'http_status_code',
        'response_time_ms',
        'success',
        'error_message',
        'attempt_number',
        'retry_after_seconds'
    ]

    date_hierarchy = 'delivered_at'

    def status_icon(self, obj):
        """Visual success/failure indicator."""
        if obj.success:
            return format_html('<span style="color: green; font-size: 16px;">✅</span>')
        return format_html('<span style="color: red; font-size: 16px;">❌</span>')
    status_icon.short_description = 'Status'

    def has_add_permission(self, request):
        """Delivery logs are created automatically - no manual adds."""
        return False

    def has_change_permission(self, request, obj=None):
        """Delivery logs are immutable - no edits."""
        return False
