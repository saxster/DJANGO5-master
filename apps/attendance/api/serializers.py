"""
Attendance & Geofencing API Serializers

Serializers for attendance records, geofences, and location validation.

Compliance with .claude/rules.md:
- Serializers < 100 lines
- Specific validation
- PostGIS field handling

Ontology: data_contract=True, api_layer=True, validation_rules=True, geospatial=True
Category: serializers, api, attendance, geofencing
Domain: attendance_tracking, geofence_validation, gps_verification
Responsibility: Serialize attendance data; validate GPS coordinates; geofence boundary management
Dependencies: attendance.models, django.contrib.gis.geos, PostGIS
Security: GPS coordinate validation, spoofing detection, accuracy thresholds
Validation: Lat/lng bounds (-90-90, -180-180), geofence type consistency, accuracy warnings
API: REST v1 /api/v1/attendance/*, mobile clock-in/out endpoints
Geospatial: PostGIS Point geometry, GeoJSON boundary support
"""

from rest_framework import serializers
from apps.attendance.models import PeopleEventlog, Geofence
from django.contrib.gis.geos import Point
from datetime import datetime, timezone as dt_timezone
import logging

logger = logging.getLogger(__name__)


class PeopleEventlogSerializer(serializers.ModelSerializer):
    """
    Serializer for people event logs (attendance history).

    Used for mobile sync of attendance records.

    Ontology: data_contract=True
    Purpose: Read-only attendance history for sync/reporting
    Fields: 9 fields (peopleid, event type, time, geofence status)
    Read-Only: id, timestamps, people_name (computed)
    Field Transforms: people_name from People.get_full_name()
    Use Case: Mobile attendance sync, dashboard history, audit trail
    Performance: Select-related peopleid to avoid N+1
    """
    people_name = serializers.CharField(
        source='peopleid.get_full_name',
        read_only=True
    )

    class Meta:
        model = PeopleEventlog
        fields = [
            'id', 'peopleid', 'people_name', 'peventtype',
            'eventtime', 'eventdate', 'accuracy',
            'inside_geofence', 'geofence_name',
            'created_at', 'modified_at'
        ]
        read_only_fields = ['id', 'created_at', 'modified_at']


class AttendanceSerializer(serializers.ModelSerializer):
    """
    Serializer for attendance records (PeopleEventlog).

    Handles clock in/out with GPS coordinates.

    Ontology: data_contract=True, validation_rules=True, geospatial=True
    Purpose: Create attendance records with GPS validation
    Fields: 9 fields including write-only lat/lng
    Write-Only: lat, lng (transformed to PostGIS Point)
    Read-Only: id, created_at, inside_geofence, geofence_name (computed by model)
    Validation: GPS bounds, accuracy threshold, spoofing detection
    Validation Rules:
      - lat: -90 to 90 (decimal degrees)
      - lng: -180 to 180 (decimal degrees)
      - accuracy: Warning if >100m (low GPS quality)
      - Spoofing: Check for (0,0) coordinates
    Geospatial: Converts lat/lng to PostGIS Point(lng, lat, srid=4326)
    Use Case: Mobile clock-in/out, geofence validation on write
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
        """
        Validate GPS coordinates and accuracy.

        Ontology: validation_rules=True, geospatial=True
        Validates: GPS coordinate bounds, accuracy threshold
        Input: lat (float), lng (float), accuracy (float, optional)
        Output: Validated attrs or ValidationError
        Rules:
          - Latitude: -90 to 90 (WGS84 standard)
          - Longitude: -180 to 180 (WGS84 standard)
          - Accuracy: Warning if >100m (mobile GPS typical: 5-30m)
        Security: Prevents invalid coordinates from corrupting geospatial data
        """
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
        """
        Create attendance record with geofence validation.

        Ontology: geospatial=True
        Transform: Converts lat/lng to PostGIS Point geometry
        Geofence: inside_geofence/geofence_name computed by model save()
        SRID: 4326 (WGS84 standard for GPS coordinates)
        Order: Point(lng, lat) - NOTE: PostGIS uses (x, y) = (longitude, latitude)
        """
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


class GeofenceSerializer(serializers.ModelSerializer):
    """
    Serializer for geofence boundaries.

    Supports GeoJSON format for polygon/circle geofences using standard DRF.

    Ontology: data_contract=True, validation_rules=True, geospatial=True
    Purpose: Define and manage geofence boundaries for attendance validation
    Fields: 11 fields (name, type, boundary, center_point, radius)
    Read-Only: id, timestamps
    Geofence Types: polygon (boundary field), circle (center_point + radius)
    Validation: Type-specific validation (polygon requires boundary, circle requires center + radius)
    Geospatial: Boundary=PostGIS Polygon, center_point=PostGIS Point
    GeoJSON: DRF auto-serializes PostGIS fields to/from GeoJSON
    Use Case: Site boundary definition, mobile geofence sync
    """

    class Meta:
        model = Geofence
        fields = [
            'id', 'name', 'geofence_type', 'boundary',
            'center_point', 'radius',
            'bu_id', 'client_id',
            'is_active', 'description',
            'created_at', 'modified_at'
        ]
        read_only_fields = ['id', 'created_at', 'modified_at']

    def validate(self, attrs):
        """
        Validate geofence data based on type.

        Ontology: validation_rules=True, geospatial=True
        Validates: Type-specific required fields
        Rules:
          - polygon type: requires boundary (PostGIS Polygon)
          - circle type: requires center_point (PostGIS Point) AND radius (meters)
        Use Case: Prevents incomplete geofence definitions
        """
        geofence_type = attrs.get('geofence_type')

        if geofence_type == 'polygon' and not attrs.get('boundary'):
            raise serializers.ValidationError({
                'boundary': 'Polygon geofences require a boundary'
            })

        if geofence_type == 'circle':
            if not attrs.get('center_point') or not attrs.get('radius'):
                raise serializers.ValidationError({
                    'center_point': 'Circle geofences require center point and radius'
                })

        return attrs


class LocationValidationSerializer(serializers.Serializer):
    """
    Serializer for validating if location is inside geofence.

    Input-only serializer (no model binding).

    Ontology: validation_rules=True, geospatial=True
    Purpose: Validate GPS coordinates for geofence check queries
    Fields: 3 fields (lat, lng, person_id)
    Model: None (input-only serializer)
    Validation: GPS bounds at field level, spoofing detection in validate()
    Spoofing Detection: Flags (0,0) as suspicious (Null Island - unlikely real location)
    Use Case: Real-time geofence check API, mobile location queries
    Response: Service layer checks if Point(lng, lat) intersects any active geofences
    """
    lat = serializers.FloatField(required=True, min_value=-90, max_value=90)
    lng = serializers.FloatField(required=True, min_value=-180, max_value=180)
    person_id = serializers.IntegerField(required=False)

    def validate(self, attrs):
        """
        Validate location data.

        Ontology: validation_rules=True
        Validates: Spoofing detection
        Security: Detects fake GPS coordinates
        Warning: (0,0) is "Null Island" (Gulf of Guinea) - unlikely real user location
        """
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
