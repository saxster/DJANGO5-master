"""
Django Admin Configuration for MQTT Telemetry Models

Provides monitoring and management interfaces for MQTT telemetry data:
- Device telemetry (battery, signal, temperature)
- Guard GPS locations with geofence monitoring
- Sensor readings (motion, door, smoke)
- Critical alerts with acknowledgment workflow

Compliance: .claude/rules.md Rule #7 (< 200 lines per file)
"""

from django.contrib import admin
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from django.urls import reverse
from django.utils import timezone

from .models import DeviceTelemetry, GuardLocation, SensorReading, DeviceAlert


@admin.register(DeviceTelemetry)
class DeviceTelemetryAdmin(admin.ModelAdmin):
    """Admin interface for device telemetry data."""

    list_display = [
        'device_id',
        'battery_badge',
        'signal_badge',
        'temperature_display',
        'connectivity_status',
        'timestamp',
        'received_at',
    ]

    list_filter = [
        'connectivity_status',
        'timestamp',
        'received_at',
    ]

    search_fields = [
        'device_id',
    ]

    readonly_fields = [
        'device_id',
        'battery_level',
        'signal_strength',
        'temperature',
        'connectivity_status',
        'timestamp',
        'received_at',
        'raw_data',
    ]

    date_hierarchy = 'timestamp'

    list_per_page = 50

    def has_add_permission(self, request):
        """Telemetry is auto-generated from MQTT, not manually added."""
        return False

    def has_delete_permission(self, request, obj=None):
        """Allow deletion for cleanup only."""
        return request.user.is_superuser

    def battery_badge(self, obj):
        """Display battery level with color coding."""
        if obj.battery_level is None:
            return mark_safe('<span class="badge badge-secondary">N/A</span>')

        if obj.battery_level >= 80:
            color = "success"
            icon = "🔋"
        elif obj.battery_level >= 50:
            color = "warning"
            icon = "🔋"
        elif obj.battery_level >= 20:
            color = "warning"
            icon = "⚠️"
        else:
            color = "danger"
            icon = "🪫"

        return format_html(
            '<span class="badge badge-{}">{} {}%</span>',
            color,
            icon,
            obj.battery_level
        )
    battery_badge.short_description = "Battery"
    battery_badge.admin_order_field = "battery_level"

    def signal_badge(self, obj):
        """Display signal strength with color coding."""
        if obj.signal_strength is None:
            return mark_safe('<span class="badge badge-secondary">N/A</span>')

        # dBm scale: -50 = excellent, -70 = good, -90 = poor, -120 = very poor
        if obj.signal_strength >= -60:
            color = "success"
            icon = "📶"
        elif obj.signal_strength >= -80:
            color = "warning"
            icon = "📶"
        else:
            color = "danger"
            icon = "📵"

        return format_html(
            '<span class="badge badge-{}">{} {} dBm</span>',
            color,
            icon,
            obj.signal_strength
        )
    signal_badge.short_description = "Signal"
    signal_badge.admin_order_field = "signal_strength"

    def temperature_display(self, obj):
        """Display temperature with unit."""
        if obj.temperature is None:
            return "-"
        return f"{obj.temperature:.1f}°C"
    temperature_display.short_description = "Temperature"


@admin.register(GuardLocation)
class GuardLocationAdmin(admin.ModelAdmin):
    """Admin interface for guard GPS tracking."""

    list_display = [
        'guard_link',
        'location_display',
        'geofence_badge',
        'accuracy',
        'timestamp',
        'received_at',
    ]

    list_filter = [
        'in_geofence',
        'geofence_violation',
        'timestamp',
        'received_at',
    ]

    search_fields = [
        'guard__peoplename',
        'guard__peoplecode',
    ]

    readonly_fields = [
        'guard',
        'location',
        'accuracy',
        'in_geofence',
        'geofence_violation',
        'timestamp',
        'received_at',
        'raw_data',
        'map_display',
    ]

    date_hierarchy = 'timestamp'

    list_per_page = 50

    def has_add_permission(self, request):
        """GPS data is auto-generated from MQTT, not manually added."""
        return False

    def guard_link(self, obj):
        """Display guard name with link to People record."""
        url = reverse('admin:peoples_people_change', args=[obj.guard.pk])
        return format_html('<a href="{}">{}</a>', url, obj.guard.peoplename)
    guard_link.short_description = "Guard"
    guard_link.admin_order_field = "guard__peoplename"

    def location_display(self, obj):
        """Display GPS coordinates."""
        if obj.location:
            return f"{obj.location.y:.6f}°N, {obj.location.x:.6f}°E"
        return "-"
    location_display.short_description = "Coordinates"

    def geofence_badge(self, obj):
        """Display geofence status with color coding."""
        if obj.geofence_violation:
            return format_html(
                '<span class="badge badge-danger">⚠️ VIOLATION</span>'
            )
        elif obj.in_geofence:
            return format_html(
                '<span class="badge badge-success">✅ IN BOUNDS</span>'
            )
        else:
            return format_html(
                '<span class="badge badge-secondary">? UNKNOWN</span>'
            )
    geofence_badge.short_description = "Geofence Status"

    def map_display(self, obj):
        """Display location on map (if PostGIS admin available)."""
        if obj.location:
            lat, lon = obj.location.y, obj.location.x
            # OpenStreetMap link
            map_url = f"https://www.openstreetmap.org/?mlat={lat}&mlon={lon}&zoom=15"
            return format_html(
                '<a href="{}" target="_blank">View on Map 🗺️</a>',
                map_url
            )
        return "-"
    map_display.short_description = "Map"


@admin.register(SensorReading)
class SensorReadingAdmin(admin.ModelAdmin):
    """Admin interface for facility sensor data."""

    list_display = [
        'sensor_id',
        'sensor_type',
        'value_display',
        'state_badge',
        'timestamp',
        'received_at',
    ]

    list_filter = [
        'sensor_type',
        'state',
        'timestamp',
        'received_at',
    ]

    search_fields = [
        'sensor_id',
    ]

    readonly_fields = [
        'sensor_id',
        'sensor_type',
        'value',
        'state',
        'timestamp',
        'received_at',
        'raw_data',
    ]

    date_hierarchy = 'timestamp'

    list_per_page = 50

    def has_add_permission(self, request):
        """Sensor data is auto-generated from MQTT, not manually added."""
        return False

    def value_display(self, obj):
        """Display sensor value with unit if applicable."""
        if obj.value is None:
            return "-"

        # Add units based on sensor type
        if obj.sensor_type == 'TEMPERATURE':
            return f"{obj.value:.1f}°C"
        elif obj.sensor_type == 'HUMIDITY':
            return f"{obj.value:.1f}%"
        elif obj.sensor_type == 'SMOKE':
            return f"{obj.value:.0f} ppm"
        else:
            return f"{obj.value}"
    value_display.short_description = "Value"

    def state_badge(self, obj):
        """Display sensor state with color coding."""
        if not obj.state:
            return "-"

        color_map = {
            'ALARM': 'danger',
            'DETECTED': 'warning',
            'OPEN': 'warning',
            'NORMAL': 'success',
            'CLEAR': 'success',
            'CLOSED': 'success',
        }
        color = color_map.get(obj.state, 'secondary')

        return format_html(
            '<span class="badge badge-{}">{}</span>',
            color,
            obj.get_state_display() if hasattr(obj, 'get_state_display') else obj.state
        )
    state_badge.short_description = "State"


@admin.register(DeviceAlert)
class DeviceAlertAdmin(admin.ModelAdmin):
    """Admin interface for critical device alerts."""

    list_display = [
        'alert_type_badge',
        'source_id',
        'severity_badge',
        'status_badge',
        'message_short',
        'acknowledged_by',
        'timestamp',
    ]

    list_filter = [
        'alert_type',
        'severity',
        'status',
        'sms_sent',
        'email_sent',
        'push_sent',
        'timestamp',
    ]

    search_fields = [
        'source_id',
        'message',
        'acknowledged_by__peoplename',
    ]

    readonly_fields = [
        'alert_uuid',
        'source_id',
        'alert_type',
        'severity',
        'message',
        'location',
        'timestamp',
        'received_at',
        'sms_sent',
        'email_sent',
        'push_sent',
        'raw_data',
        'map_display',
    ]

    fieldsets = (
        ('Alert Details', {
            'fields': (
                'alert_uuid',
                'source_id',
                'alert_type',
                'severity',
                'message',
                'location',
                'map_display',
                'timestamp',
                'received_at',
            )
        }),
        ('Acknowledgment', {
            'fields': (
                'status',
                'acknowledged_by',
                'acknowledged_at',
                'resolved_at',
            )
        }),
        ('Notifications', {
            'fields': (
                'sms_sent',
                'email_sent',
                'push_sent',
            ),
            'classes': ('collapse',)
        }),
        ('Raw Data', {
            'fields': (
                'raw_data',
            ),
            'classes': ('collapse',)
        })
    )

    actions = [
        'acknowledge_alerts',
        'mark_as_resolved',
        'mark_as_false_alarm',
    ]

    date_hierarchy = 'timestamp'

    list_per_page = 50

    def alert_type_badge(self, obj):
        """Display alert type with icon."""
        icon_map = {
            'PANIC': '🚨',
            'SOS': '🆘',
            'INTRUSION': '🚪',
            'FIRE': '🔥',
            'MEDICAL': '🏥',
            'EQUIPMENT_FAILURE': '⚙️',
            'GEOFENCE_VIOLATION': '📍',
            'LOW_BATTERY': '🪫',
            'OFFLINE': '📵',
        }
        icon = icon_map.get(obj.alert_type, '⚠️')

        return format_html(
            '<span>{} {}</span>',
            icon,
            obj.get_alert_type_display()
        )
    alert_type_badge.short_description = "Alert Type"
    alert_type_badge.admin_order_field = "alert_type"

    def severity_badge(self, obj):
        """Display severity with color coding."""
        color_map = {
            'CRITICAL': 'danger',
            'HIGH': 'warning',
            'MEDIUM': 'info',
            'LOW': 'secondary',
        }
        color = color_map.get(obj.severity, 'secondary')

        return format_html(
            '<span class="badge badge-{}">{}</span>',
            color,
            obj.severity
        )
    severity_badge.short_description = "Severity"
    severity_badge.admin_order_field = "severity"

    def status_badge(self, obj):
        """Display status with color coding."""
        color_map = {
            'NEW': 'danger',
            'ACKNOWLEDGED': 'warning',
            'IN_PROGRESS': 'info',
            'RESOLVED': 'success',
            'FALSE_ALARM': 'secondary',
        }
        color = color_map.get(obj.status, 'secondary')

        return format_html(
            '<span class="badge badge-{}">{}</span>',
            color,
            obj.get_status_display()
        )
    status_badge.short_description = "Status"
    status_badge.admin_order_field = "status"

    def message_short(self, obj):
        """Display truncated message."""
        if len(obj.message) > 50:
            return obj.message[:50] + "..."
        return obj.message
    message_short.short_description = "Message"

    def map_display(self, obj):
        """Display alert location on map."""
        if obj.location:
            lat, lon = obj.location.y, obj.location.x
            map_url = f"https://www.openstreetmap.org/?mlat={lat}&mlon={lon}&zoom=18"
            return format_html(
                '<a href="{}" target="_blank">View Location 📍</a>',
                map_url
            )
        return "-"
    map_display.short_description = "Location"

    def acknowledge_alerts(self, request, queryset):
        """Acknowledge selected alerts."""
        for alert in queryset.filter(status='NEW'):
            alert.acknowledge(request.user)
        count = queryset.filter(status='NEW').count()
        self.message_user(request, f'{count} alerts acknowledged.')
    acknowledge_alerts.short_description = "Acknowledge selected alerts"

    def mark_as_resolved(self, request, queryset):
        """Mark selected alerts as resolved."""
        for alert in queryset:
            alert.resolve()
        self.message_user(request, f'{queryset.count()} alerts marked as resolved.')
    mark_as_resolved.short_description = "Mark as resolved"

    def mark_as_false_alarm(self, request, queryset):
        """Mark selected alerts as false alarms."""
        updated = queryset.update(status='FALSE_ALARM', resolved_at=timezone.now())
        self.message_user(request, f'{updated} alerts marked as false alarms.')
    mark_as_false_alarm.short_description = "Mark as false alarm"
