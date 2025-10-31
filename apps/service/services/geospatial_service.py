"""
Geospatial Service Module

Handles all geospatial operations including reverse geocoding and linestring processing.
Extracted from apps/service/utils.py for improved organization and maintainability.

Migration Date: 2025-09-30
Original File: apps/service/utils.py (lines 746-921)

Functions:
- save_linestring_and_update_pelrecord: Create linestring from tracking points
- get_readable_addr_from_point: Reverse geocoding for addresses
- save_addr_for_point: Save addresses for multiple point fields

Features:
- Google Maps API integration
- PostGIS linestring geometry
- Coordinate transformation (SRID 4326 <-> 3857)
- Centralized coordinate extraction via GeospatialService
"""
from logging import getLogger
from django.contrib.gis.geos import LineString
from django.db.utils import DatabaseError
from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.conf import settings
import googlemaps
import json

from apps.attendance.services.geospatial_service import GeospatialService, CoordinateParsingError

# Get Google Maps API key from settings with fallback
google_map_key = getattr(settings, 'GOOGLE_MAP_SECRET_KEY', '')

log = getLogger("message_q")
tlog = getLogger("tracking")


def save_linestring_and_update_pelrecord(obj):
    """
    Create linestring geometry from tracking points and update record.

    Retrieves all tracking points for the given reference UUID, creates a
    PostGIS LineString geometry, transforms to spherical mercator for
    distance calculation, then saves back to the object.

    Also geocodes start and end locations to human-readable addresses.

    Args:
        obj: PeopleEventlog instance with UUID reference

    Side Effects:
        - Updates obj.journeypath with LineString geometry
        - Updates obj.geojson with geocoded addresses
        - Saves obj to database
    """
    # sourcery skip: identity-comprehension
    from apps.attendance.models import Tracking

    try:
        bet_objs = Tracking.objects.filter(reference=obj.uuid).order_by("receiveddate")
        line = [[coord for coord in obj.gpslocation] for obj in bet_objs]
        if len(line) > 1:
            ls = LineString(line, srid=4326)
            # transform spherical mercator projection system
            ls.transform(3857)
            # d = round(ls.length / 1000)
            # obj.distance = d
            ls.transform(4326)
            obj.journeypath = ls
            obj.geojson["startlocation"] = get_readable_addr_from_point(
                obj.startlocation
            )
            obj.geojson["endlocation"] = get_readable_addr_from_point(obj.endlocation)
            obj.save()
            # bet_objs.delete()
            log.info("save linestring is saved..")

    except (DatabaseError, FileNotFoundError, IOError, OSError, ObjectDoesNotExist, PermissionError, TypeError, ValidationError, ValueError, json.JSONDecodeError) as e:
        log.critical("ERROR while saving line string", exc_info=True)
        raise


def get_readable_addr_from_point(point):
    """
    Get human-readable address from a Point geometry using reverse geocoding.

    Uses centralized GeospatialService for consistent coordinate extraction.

    Args:
        point: Point geometry object

    Returns:
        str: Formatted address or empty string if geocoding fails
    """
    try:
        # Use centralized coordinate extraction
        lon, lat = GeospatialService.extract_coordinates(point)

        # Validate coordinates (avoid 0,0 which indicates invalid/missing data)
        if lon not in [0.0, "0.0"] and lat not in [0.0, "0.0"]:
            gmaps = googlemaps.Client(key=google_map_key)
            # Google Maps API expects (lat, lon) tuple
            result = gmaps.reverse_geocode((lat, lon))
            log.info("reverse geocoding complete, results returned")
            return result[0]["formatted_address"]

        log.info("Not a valid point (coordinates are 0,0), returned empty string")
        return ""

    except CoordinateParsingError as e:
        log.warning(f"Failed to extract coordinates from point: {e}")
        return ""
    except (DatabaseError, FileNotFoundError, IOError, OSError, ObjectDoesNotExist, PermissionError, TypeError, ValidationError, ValueError, json.JSONDecodeError) as e:
        log.critical("something went wrong while reverse geocoding", exc_info=True)
        return ""


def save_addr_for_point(obj):
    """
    Geocode and save addresses for all point fields on an object.

    Checks for gpslocation, startlocation, and endlocation attributes and
    geocodes each to a human-readable address, storing in obj.geojson dict.

    Args:
        obj: Model instance with Point fields and geojson JSONField

    Side Effects:
        - Updates obj.geojson dict with geocoded addresses
        - Saves obj to database
    """
    if hasattr(obj, "gpslocation"):
        obj.geojson["gpslocation"] = get_readable_addr_from_point(obj.gpslocation)
    if hasattr(obj, "startlocation"):
        obj.geojson["startlocation"] = get_readable_addr_from_point(obj.startlocation)
    if hasattr(obj, "endlocation"):
        obj.geojson["endlocation"] = get_readable_addr_from_point(obj.endlocation)
    obj.save()
