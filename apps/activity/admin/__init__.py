"""
Activity admin configuration.

Modular admin structure following CLAUDE.md architectural limits (max 200 lines per file).

Structure:
- asset_admin.py: Asset admin (existing)
- location_admin.py: Location admin (existing)
- meter_reading_admin.py: MeterReading admin
- meter_alert_admin.py: MeterReadingAlert admin
- vehicle_entry_admin.py: VehicleEntry admin
- vehicle_alert_admin.py: VehicleSecurityAlert admin
- question/: Question-related admins (existing)

All admins registered with Django's admin site automatically via @admin.register decorators.
"""

# Import all admin classes for backward compatibility
from apps.activity.admin.asset_admin import AssetResource, AssetResourceUpdate
from apps.activity.admin.location_admin import LocationResource, LocationResourceUpdate
from apps.activity.admin.meter_reading_admin import MeterReadingAdmin
from apps.activity.admin.meter_alert_admin import MeterReadingAlertAdmin
from apps.activity.admin.vehicle_entry_admin import VehicleEntryAdmin
from apps.activity.admin.vehicle_alert_admin import VehicleSecurityAlertAdmin

# Question admins are in question/ subdirectory and auto-registered

# Explicit __all__ to control namespace (Rule #16: Wildcard Import Prevention)
__all__ = [
    # From asset_admin.py
    'AssetResource',
    'AssetResourceUpdate',

    # From location_admin.py
    'LocationResource',
    'LocationResourceUpdate',

    # From meter_reading_admin.py
    'MeterReadingAdmin',

    # From meter_alert_admin.py
    'MeterReadingAlertAdmin',

    # From vehicle_entry_admin.py
    'VehicleEntryAdmin',

    # From vehicle_alert_admin.py
    'VehicleSecurityAlertAdmin',
]
