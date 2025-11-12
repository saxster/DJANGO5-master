"""
Geofence tracking manager for PeopleEventlog.

Handles geofence-related queries and tracking views.
"""
from datetime import date, timedelta
from django.contrib.gis.db.models.functions import AsWKT
from apps.core import utils
import logging

logger = logging.getLogger("django")


class GeofenceManagerMixin:
    """
    Manager mixin for geofence tracking operations.

    Provides methods for:
    - Geofence tracking list views
    - Location validation utilities (deprecated - use GeospatialService)
    """

    def get_geofencetracking(self, request):
        """
        Optimized list view for geofence tracking with improved query performance
        """
        qobjs, dir, fields, length, start = utils.get_qobjs_dir_fields_start_length(
            request.GET
        )
        last8days = date.today() - timedelta(days=8)

        # Build base queryset with optimized order: select_related first, then filter, then annotate
        base_qset = (
            self.select_related("people", "peventtype", "geofence")
            .filter(
                peventtype__tacode="GEOFENCE",
                datefor__gte=last8days,
                bu_id=request.session["bu_id"],
            )
            .annotate(
                slocation=AsWKT("startlocation"),
                elocation=AsWKT("endlocation"),
            )
        )

        # Apply additional filters if they exist
        if qobjs:
            filtered_qset = base_qset.filter(qobjs)

            # Use separate count query to avoid expensive operations
            total = base_qset.count()
            fcount = filtered_qset.count()

            # Apply ordering and pagination to the final query
            result_qset = (
                filtered_qset
                .values(*fields)
                .order_by(dir)[start : start + length]
            )

            return total, fcount, result_qset
        else:
            # No additional filters
            total = base_qset.count()

            result_qset = (
                base_qset
                .values(*fields)
                .order_by(dir)[start : start + length]
            )

            return total, total, result_qset

    def get_lat_long(self, location):
        """
        Extract coordinates from geometry using centralized geospatial service.

        DEPRECATED: Use GeospatialService.extract_coordinates() directly.
        """
        try:
            from apps.attendance.services.geospatial_service import GeospatialService
            lon, lat = GeospatialService.extract_coordinates(location)
            return [lon, lat]
        except (ValueError, TypeError, AttributeError) as e:
            logger.error(f"Failed to extract coordinates from {location}: {str(e)}", exc_info=True)
            return [0.0, 0.0]  # Return default coordinates on failure

    def is_point_in_geofence(self, lat, lon, geofence):
        """
        Check if a point is within a geofence using centralized service.

        DEPRECATED: Use GeospatialService.is_point_in_geofence() directly.

        Args:
            lat (float): Latitude of the point to check.
            lon (float): Longitude of the point to check.
            geofence (Polygon or tuple): Polygon or (center_lat, center_lon, radius_km) tuple

        Returns:
            bool: True if the point is inside the geofence, False otherwise.
        """
        try:
            from apps.attendance.services.geospatial_service import GeospatialService
            return GeospatialService.is_point_in_geofence(
                lat, lon, geofence, use_hysteresis=True
            )
        except (ValueError, TypeError, AttributeError) as e:
            logger.error(f"Geofence validation failed for ({lat}, {lon}): {str(e)}", exc_info=True)
            return False
