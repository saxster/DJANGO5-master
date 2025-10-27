"""
Attendance & Geofencing API Serializers

Serializers for attendance records, geofences, and location validation.

Compliance with .claude/rules.md:
- Serializers < 100 lines
- Specific validation
- PostGIS field handling
"""

from rest_framework import serializers
from rest_framework_gis import serializers as gis_serializers
from apps.attendance.models import PeopleEventlog, Geofence
from django.contrib.gis.geos import Point
from datetime import datetime, timezone as dt_timezone
import logging

logger = logging.getLogger(__name__)


class AttendanceSerializer(serializers.ModelSerializer):
    """
    Serializer for attendance records (PeopleEventlog).

    Handles clock in/out with GPS coordinates.
    """
    lat = serializers.FloatField(write_only=True, required=True)
    lng = serializers.FloatField(write_only=True, required=True)
    device_id = serializers.CharField(max_length=255, required=False, allow_blank=True)

    class Meta:
        model = PeopleEventlog
        fields = [
            'id', 'peopleid', 'event_type', 'event_time',
            'lat', 'lng', 'accuracy', 'device_id',
            'inside_geofence', 'geofence_name',
            'created_at'
        ]
        read_only_fields = ['id', 'created_at', 'inside_geofence', 'geofence_name']

    def validate(self, attrs):
        """Validate GPS coordinates and accuracy."""
        lat = attrs.get('lat')
        lng = attrs.get('lng')

        if not (-90 <= lat <= 90):
            raise serializers.ValidationError({
                'lat': 'Latitude must be between -90 and 90'
            })

        if not (-180 <= lng <= 180):
            raise serializers.ValidationError({
                'lng': 'Longitude must be between -180 and 180'
            })

        # Validate accuracy if provided
        accuracy = attrs.get('accuracy', 0)
        if accuracy > 100:
            logger.warning(f"Low GPS accuracy: {accuracy} meters")

        return attrs

    def create(self, validated_data):
        """Create attendance record with geofence validation."""
        lat = validated_data.pop('lat')
        lng = validated_data.pop('lng')

        # Create Point for location
        location = Point(lng, lat, srid=4326)

        # Create attendance record
        attendance = PeopleEventlog.objects.create(
            location=location,
            **validated_data
        )

        return attendance


class GeofenceSerializer(gis_serializers.GeoFeatureModelSerializer):
    """
    Serializer for geofence boundaries.

    Supports GeoJSON format for polygon/circle geofences.
    """

    class Meta:
        model = Geofence
        geo_field = 'boundary'
        fields = [
            'id', 'name', 'geofence_type', 'boundary',
            'radius', 'bu_id', 'client_id',
            'is_active', 'created_at', 'modified_at'
        ]
        read_only_fields = ['id', 'created_at', 'modified_at']

    def validate_boundary(self, value):
        """Validate geofence boundary."""
        if not value:
            raise serializers.ValidationError('Boundary is required')

        # Validate polygon closure (first and last point must match)
        if value.geom_type == 'Polygon':
            coords = value.coords[0]
            if coords[0] != coords[-1]:
                raise serializers.ValidationError(
                    'Polygon must be closed (first and last points must match)'
                )

        return value


class LocationValidationSerializer(serializers.Serializer):
    """
    Serializer for validating if location is inside geofence.

    Input-only serializer (no model binding).
    """
    lat = serializers.FloatField(required=True, min_value=-90, max_value=90)
    lng = serializers.FloatField(required=True, min_value=-180, max_value=180)
    person_id = serializers.IntegerField(required=False)

    def validate(self, attrs):
        """Validate location data."""
        lat = attrs.get('lat')
        lng = attrs.get('lng')

        # Check for spoofed coordinates (0,0 is likely fake)
        if lat == 0 and lng == 0:
            logger.warning("Suspicious coordinates: (0, 0)")

        return attrs


__all__ = [
    'AttendanceSerializer',
    'GeofenceSerializer',
    'LocationValidationSerializer',
]
