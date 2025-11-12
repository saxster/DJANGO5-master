"""
TestGeo model - Test model for geospatial functionality.

Used for testing PostGIS features with various geometry types.
"""
from django.db import models
from django.contrib.gis.db.models import LineStringField, PointField, PolygonField


class TestGeo(models.Model):
    """
    Test model for geospatial functionality.

    Contains various geometry types for testing PostGIS operations:
    - Polygon: Area boundaries
    - Point: Single location coordinates
    - LineString: Path/route definitions
    """

    code = models.CharField(max_length=15)
    poly = PolygonField(geography=True, null=True)
    point = PointField(geography=True, blank=True, null=True)
    line = LineStringField(geography=True, null=True, blank=True)


__all__ = ['TestGeo']
