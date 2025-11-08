"""
Device Trust & Security admin interfaces (Sprint 1 - Oct 2025).

Provides:
    - DeviceRegistrationAdmin: Manage device trust registry
    - DeviceRiskEventAdmin: View and manage security events
    - Device trust scoring and blocking
"""

from django.contrib import admin
from django.utils import timezone

from apps.peoples.models import DeviceRegistration, DeviceRiskEvent


class DeviceRiskEventInline(admin.TabularInline):
    """Inline admin for device risk events."""

    model = DeviceRiskEvent
    extra = 0
    can_delete = False
    readonly_fields = (
        "event_type",
        "risk_score",
        "detected_at",
        "ip_address",
        "user_agent",
        "action_taken",
        "resolved",
        "resolved_at",
    )
    fields = ("event_type", "risk_score", "detected_at", "action_taken", "resolved")

    def has_add_permission(self, request, obj=None):
        """Risk events are created by system, not manually."""
        return False


@admin.register(DeviceRegistration)
class DeviceRegistrationAdmin(admin.ModelAdmin):
    list_per_page = 50
    """
    Admin interface for Device Trust Registry.

    Features:
    - View device trust scores and factors
    - Mark devices as trusted/blocked
    - View security events inline
    - Search by device ID, user, IP
    - Filter by trust status, blocked status

    Security:
    - Read-only device fingerprint (anti-tampering)
    - Audit trail for trust changes
    - No bulk device deletion (security preservation)
    """

    list_display = (
        "device_id_short",
        "user",
        "trust_score",
        "is_trusted",
        "is_blocked",
        "biometric_enrolled",
        "last_seen",
        "first_seen",
    )

    list_filter = (
        "is_trusted",
        "is_blocked",
        "biometric_enrolled",
        "last_seen",
    )

    search_fields = (
        "device_id",
        "user__peoplename",
        "user__email",
        "ip_address",
    )

    readonly_fields = (
        "device_id",
        "device_fingerprint",
        "first_seen",
        "last_seen",
        "enrollment_count",
        "trust_score",
        "trust_factors",
    )

    fieldsets = (
        (
            "Device Information",
            {
                "fields": (
                    "device_id",
                    "user",
                    "device_fingerprint",
                    "user_agent",
                    "ip_address",
                )
            },
        ),
        (
            "Trust & Security",
            {
                "fields": (
                    "trust_score",
                    "trust_factors",
                    "is_trusted",
                    "is_blocked",
                    "block_reason",
                )
            },
        ),
        (
            "Activity",
            {
                "fields": (
                    "first_seen",
                    "last_seen",
                    "last_location",
                    "biometric_enrolled",
                    "enrollment_count",
                )
            },
        ),
    )

    inlines = [DeviceRiskEventInline]
    actions = ["mark_as_trusted", "block_devices", "unblock_devices"]
    list_select_related = ("user",)

    def device_id_short(self, obj):
        """Show shortened device ID for readability."""
        return f"{obj.device_id[:16]}..."

    device_id_short.short_description = "Device ID"

    def mark_as_trusted(self, request, queryset):
        """Mark selected devices as trusted."""
        updated = queryset.filter(is_blocked=False).update(is_trusted=True)
        self.message_user(request, f"{updated} devices marked as trusted.")

    mark_as_trusted.short_description = "Mark as trusted"

    def block_devices(self, request, queryset):
        """Block selected devices."""
        updated = queryset.update(is_blocked=True, is_trusted=False)
        self.message_user(
            request, f"{updated} devices blocked.", level="warning"
        )

    block_devices.short_description = "Block devices"

    def unblock_devices(self, request, queryset):
        """Unblock selected devices."""
        updated = queryset.update(is_blocked=False, block_reason="")
        self.message_user(request, f"{updated} devices unblocked.")

    unblock_devices.short_description = "Unblock devices"

    def has_delete_permission(self, request, obj=None):
        """Prevent bulk device deletion (preserve security history)."""
        return False


@admin.register(DeviceRiskEvent)
class DeviceRiskEventAdmin(admin.ModelAdmin):
    list_per_page = 50
    """
    Admin interface for Device Security Events.

    Features:
    - View and filter security events
    - Mark events as resolved
    - Search by device, event type
    - View risk scores and details

    Security:
    - Read-only event data (audit integrity)
    - No manual event creation (system-only)
    - Preserve event history
    """

    list_display = (
        "event_id",
        "device_short",
        "event_type",
        "risk_score",
        "detected_at",
        "resolved",
        "action_taken",
    )

    list_filter = (
        "event_type",
        "resolved",
        "detected_at",
    )

    search_fields = (
        "device__device_id",
        "device__user__peoplename",
        "event_type",
    )

    readonly_fields = (
        "device",
        "event_type",
        "risk_score",
        "event_data",
        "detected_at",
        "ip_address",
        "user_agent",
        "action_taken",
    )

    fieldsets = (
        (
            "Event Information",
            {
                "fields": (
                    "event_id",
                    "device",
                    "event_type",
                    "risk_score",
                    "detected_at",
                )
            },
        ),
        (
            "Context",
            {
                "fields": ("ip_address", "user_agent", "event_data")
            },
        ),
        (
            "Response",
            {
                "fields": ("action_taken", "resolved", "resolved_at")
            },
        ),
    )

    actions = ["mark_as_resolved"]
    list_select_related = ("device", "device__user")
    date_hierarchy = "detected_at"

    def device_short(self, obj):
        """Show shortened device ID."""
        return f"{obj.device.device_id[:12]}..."

    device_short.short_description = "Device"

    def mark_as_resolved(self, request, queryset):
        """Mark selected events as resolved."""
        updated = queryset.filter(resolved=False).update(
            resolved=True, resolved_at=timezone.now()
        )
        self.message_user(request, f"{updated} events marked as resolved.")

    mark_as_resolved.short_description = "Mark as resolved"

    def has_add_permission(self, request):
        """Risk events are system-generated only."""
        return False

    def has_delete_permission(self, request, obj=None):
        """Preserve security event history."""
        return False
