"""
Attendance managers module.

Consolidated manager for PeopleEventlog with specialized mixins for:
- Face recognition verification
- Face recognition result updates
- List views and reporting
- History and sync queries
- Event tracking (SOS, site crisis)
- Dashboard cards
- Geofence tracking
- Spatial analytics
- Compliance analytics
- Journey analytics
- Heatmap generation
- Outlier detection

Import PELManager from this module to get all functionality.
"""
from apps.attendance.managers.base import PELManager as BasePELManager
from apps.attendance.managers.face_recognition_manager import FaceRecognitionManagerMixin
from apps.attendance.managers.fr_update_manager import FRUpdateManagerMixin
from apps.attendance.managers.list_view_manager import ListViewManagerMixin
from apps.attendance.managers.history_manager import HistoryManagerMixin
from apps.attendance.managers.event_tracking_manager import EventTrackingManagerMixin
from apps.attendance.managers.dashboard_manager import DashboardManagerMixin
from apps.attendance.managers.geofence_manager import GeofenceManagerMixin
from apps.attendance.managers.spatial_analytics_manager import SpatialAnalyticsManagerMixin
from apps.attendance.managers.compliance_analytics_manager import ComplianceAnalyticsManagerMixin
from apps.attendance.managers.journey_analytics_manager import JourneyAnalyticsManagerMixin
from apps.attendance.managers.heatmap_outlier_manager import HeatmapOutlierManagerMixin


class PELManager(
    FaceRecognitionManagerMixin,
    FRUpdateManagerMixin,
    ListViewManagerMixin,
    HistoryManagerMixin,
    EventTrackingManagerMixin,
    DashboardManagerMixin,
    GeofenceManagerMixin,
    SpatialAnalyticsManagerMixin,
    ComplianceAnalyticsManagerMixin,
    JourneyAnalyticsManagerMixin,
    HeatmapOutlierManagerMixin,
    BasePELManager
):
    """
    Complete manager for PeopleEventlog with all functionality.

    Combines all specialized mixins:
    - FaceRecognitionManagerMixin: FR status and photo queries
    - FRUpdateManagerMixin: FR result updates with race condition protection
    - ListViewManagerMixin: Attendance list views and conveyance
    - HistoryManagerMixin: Attendance history and punch-in queries
    - EventTrackingManagerMixin: SOS, site crisis, and event tracking
    - DashboardManagerMixin: Dashboard card counts
    - GeofenceManagerMixin: Geofence tracking and validation
    - SpatialAnalyticsManagerMixin: PostGIS spatial queries
    - ComplianceAnalyticsManagerMixin: Geofence compliance analytics
    - JourneyAnalyticsManagerMixin: Journey pattern analysis
    - HeatmapOutlierManagerMixin: Heatmap generation and outlier detection
    - BasePELManager: Foundation manager with tenant-aware filtering

    Use this manager as:
        from apps.attendance.managers import PELManager

        class PeopleEventlog(models.Model):
            objects = PELManager()
    """
    pass


__all__ = [
    'PELManager',
    'BasePELManager',
    'FaceRecognitionManagerMixin',
    'FRUpdateManagerMixin',
    'ListViewManagerMixin',
    'HistoryManagerMixin',
    'EventTrackingManagerMixin',
    'DashboardManagerMixin',
    'GeofenceManagerMixin',
    'SpatialAnalyticsManagerMixin',
    'ComplianceAnalyticsManagerMixin',
    'JourneyAnalyticsManagerMixin',
    'HeatmapOutlierManagerMixin',
]
