"""
Attendance Forms Package
Provides form classes for attendance tracking, conveyance, and GPS tracking.

Module structure:
- attendance.py: AttendanceForm
- conveyance.py: ConveyanceForm
- tracking.py: TrackingForm, clean_geometry()

Refactored: November 2025 (Phase 3 god file elimination)
"""

from .attendance import AttendanceForm
from .conveyance import ConveyanceForm
from .tracking import TrackingForm, clean_geometry

__all__ = [
    "AttendanceForm",
    "ConveyanceForm",
    "TrackingForm",
    "clean_geometry",
]
