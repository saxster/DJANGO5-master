"""
Tracking and Geometry Form Module
Handles GPS tracking records and geometry field validation.

Part of: apps/attendance/forms/
"""

from django import forms
from django.contrib.gis.geos import GEOSGeometry
from django.core.exceptions import ValidationError
import logging

from apps.attendance import models as atdm

logger = logging.getLogger(__name__)


def clean_geometry(val):
    """
    Enhanced geometry validation using centralized geospatial service
    """
    if not val or val.strip() == "":
        return None

    try:
        from apps.attendance.services.geospatial_service import GeospatialService

        val = val.strip()

        if val.startswith("Lat:") and "Lng:" in val:
            import re
            match = re.search(r"Lat:\s*([-\d.]+),\s*Lng:\s*([-\d.]+)", val)
            if match:
                lat, lon = float(match.group(1)), float(match.group(2))
                return GeospatialService.create_point(lat, lon)

        geom = GEOSGeometry(val, srid=4326)

        if geom.geom_type == 'Point':
            lon, lat = GeospatialService.extract_coordinates(geom)
            GeospatialService.validate_coordinates(lat, lon)

        return geom

    except (ValueError, TypeError, ValidationError) as e:
        raise forms.ValidationError(
            f"Invalid geometry format. Expected coordinates or WKT geometry. Error: {str(e)}"
        ) from e
    except (AttributeError, KeyError) as e:
        raise forms.ValidationError(
            f"Failed to process geometry data: {str(e)}"
        ) from e


class TrackingForm(forms.ModelForm):
    gpslocation = forms.CharField(max_length=200, required=True)

    class Meta:
        model = atdm.Tracking
        fields = ["deviceid", "gpslocation", "receiveddate", "people", "transportmode"]

    def clean_gpslocation(self):
        if val := self.cleaned_data.get("gpslocation"):
            val = clean_geometry(val)
        return val
