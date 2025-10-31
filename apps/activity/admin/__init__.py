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
from apps.activity.admin.asset_admin import *  # noqa: F401, F403
from apps.activity.admin.location_admin import *  # noqa: F401, F403
from apps.activity.admin.meter_reading_admin import MeterReadingAdmin  # noqa: F401
from apps.activity.admin.meter_alert_admin import MeterReadingAlertAdmin  # noqa: F401
from apps.activity.admin.vehicle_entry_admin import VehicleEntryAdmin  # noqa: F401
from apps.activity.admin.vehicle_alert_admin import VehicleSecurityAlertAdmin  # noqa: F401

# Question admins are in question/ subdirectory and auto-registered

__all__ = [
    'MeterReadingAdmin',
    'MeterReadingAlertAdmin',
    'VehicleEntryAdmin',
    'VehicleSecurityAlertAdmin',
]
