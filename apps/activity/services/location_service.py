"""
Location Management Service

Centralizes location business logic with GPS validation.

Following .claude/rules.md:
- Service layer pattern (Rule 8)
- Specific exception handling (Rule 11)
- Database query optimization (Rule 12)
"""

import logging
from typing import Dict, Any, Optional
from dataclasses import dataclass
from django.db import IntegrityError
from django.core.exceptions import ValidationError
from django.contrib.gis.geos import Point, Polygon, GEOSGeometry
from apps.core.services.base_service import BaseService
from apps.core.exceptions import BusinessLogicException
from apps.activity.models.location_model import Location
import apps.peoples.utils as putils

logger = logging.getLogger(__name__)

__all__ = [
    'LocationManagementService',
    'LocationOperationResult',
]


@dataclass
class LocationOperationResult:
    """Result of location operations."""
    success: bool
    location: Optional[Location] = None
    location_id: Optional[int] = None
    message: Optional[str] = None
    error_message: Optional[str] = None


class LocationManagementService(BaseService):
    """Service for location CRUD operations with GPS validation."""

    def get_service_name(self) -> str:
        return "LocationManagementService"

    @BaseService.monitor_performance("create_location")
    def create_location(
        self,
        location_data: Dict[str, Any],
        user,
        session: Dict[str, Any]
    ) -> LocationOperationResult:
        """
        Create new location with GPS validation.

        Args:
            location_data: Location form cleaned data
            user: User creating the location
            session: Request session data

        Returns:
            LocationOperationResult with created location
        """
        try:
            with self.database_transaction():
                gps_location = location_data.pop('gpslocation', None)
                location = Location(**location_data)

                if gps_location:
                    location.gpslocation = self._validate_gps_location(gps_location)

                location = putils.save_userinfo(location, user, session, create=True)

                return LocationOperationResult(
                    success=True,
                    location=location,
                    location_id=location.id,
                    message="Location created successfully"
                )

        except IntegrityError as e:
            logger.error(f"Location creation integrity error: {e}")
            return LocationOperationResult(
                success=False,
                error_message="Location with this code already exists"
            )
        except ValidationError as e:
            logger.warning(f"Location creation validation error: {e}")
            return LocationOperationResult(
                success=False,
                error_message=str(e)
            )

    @BaseService.monitor_performance("update_location")
    def update_location(
        self,
        location_id: int,
        location_data: Dict[str, Any],
        user,
        session: Dict[str, Any]
    ) -> LocationOperationResult:
        """Update existing location."""
        try:
            with self.database_transaction():
                location = Location.objects.select_for_update().get(pk=location_id)

                gps_location = location_data.pop('gpslocation', None)

                for field, value in location_data.items():
                    setattr(location, field, value)

                if gps_location:
                    location.gpslocation = self._validate_gps_location(gps_location)

                location = putils.save_userinfo(location, user, session, create=False)

                return LocationOperationResult(
                    success=True,
                    location=location,
                    location_id=location.id,
                    message="Location updated successfully"
                )

        except Location.DoesNotExist:
            return LocationOperationResult(
                success=False,
                error_message="Location not found"
            )
        except IntegrityError:
            return LocationOperationResult(
                success=False,
                error_message="Location code conflict"
            )

    @BaseService.monitor_performance("delete_location")
    def delete_location(self, location_id: int) -> LocationOperationResult:
        """Delete location with dependency checking."""
        try:
            with self.database_transaction():
                location = Location.objects.get(pk=location_id)
                location_code = location.loccode
                location.delete()

                return LocationOperationResult(
                    success=True,
                    message=f"Location {location_code} deleted"
                )

        except Location.DoesNotExist:
            return LocationOperationResult(
                success=False,
                error_message="Location not found"
            )
        except IntegrityError:
            return LocationOperationResult(
                success=False,
                error_message="Cannot delete - location is in use"
            )

    def _validate_gps_location(self, gps_data: Any) -> Optional[Point]:
        """
        Validate and convert GPS location data.

        Args:
            gps_data: GPS data (GEOSGeometry, dict, or string)

        Returns:
            Point object or None

        Raises:
            ValidationError: If GPS data is invalid
        """
        if not gps_data:
            return None

        if isinstance(gps_data, Point):
            return gps_data

        if isinstance(gps_data, GEOSGeometry):
            if gps_data.geom_type == 'Point':
                return gps_data
            raise ValidationError(f"GPS location must be Point, not {gps_data.geom_type}")

        if isinstance(gps_data, dict):
            lat = gps_data.get('latitude')
            lon = gps_data.get('longitude')
            if lat and lon:
                return Point(float(lon), float(lat), srid=4326)

        if isinstance(gps_data, str):
            try:
                return GEOSGeometry(gps_data)
            except (ValueError, TypeError) as e:
                raise ValidationError(f"Invalid GPS data format: {e}")

        raise ValidationError("Unsupported GPS location format")