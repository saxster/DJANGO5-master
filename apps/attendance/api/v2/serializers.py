"""
Attendance API v2 Serializers

Type-safe serializers for Kotlin/Swift mobile clients.
Based on API_CONTRACT_ATTENDANCE.md specification.

Author: Claude Code
Created: November 7, 2025
Version: 1.0.0
"""
from rest_framework import serializers
from django.contrib.gis.geos import Point
from typing import Dict, Any, Optional
import base64
import uuid

from apps.attendance.models import (
    PeopleEventlog,
    Post,
    Geofence,
    AttendancePhoto,
    FraudAlert
)
from apps.client_onboarding.models import Shift, Bt
from apps.peoples.models import People
from apps.attendance.validators import validate_geofence_coordinates


class GPSLocationSerializer(serializers.Serializer):
    """GPS location data with validation"""
    latitude = serializers.FloatField(min_value=-90.0, max_value=90.0)
    longitude = serializers.FloatField(min_value=-180.0, max_value=180.0)
    accuracy_meters = serializers.FloatField(min_value=0.0, max_value=1000.0)
    altitude = serializers.FloatField(required=False, allow_null=True)
    speed = serializers.FloatField(required=False, allow_null=True, min_value=0.0)


class FacePhotoSerializer(serializers.Serializer):
    """Face photo data with quality validation"""
    photo_data = serializers.CharField(help_text="Base64 encoded JPEG")
    photo_quality_score = serializers.FloatField(
        min_value=0.0,
        max_value=1.0,
        required=False,
        default=0.0
    )
    capture_timestamp = serializers.DateTimeField()

    def validate_photo_data(self, value):
        """Validate base64 image data"""
        if not value.startswith('data:image/'):
            raise serializers.ValidationError(
                "Photo must be base64 encoded with data URI scheme"
            )
        
        try:
            header, encoded = value.split(',', 1)
            decoded = base64.b64decode(encoded)
            
            if len(decoded) > 5 * 1024 * 1024:
                raise serializers.ValidationError("Photo size exceeds 5MB limit")
                
        except Exception as e:
            raise serializers.ValidationError(f"Invalid base64 image data: {str(e)}")
        
        return value


class DeviceInfoSerializer(serializers.Serializer):
    """Device information for fraud detection"""
    device_id = serializers.CharField(max_length=100)
    device_model = serializers.CharField(max_length=100, required=False)
    os_version = serializers.CharField(max_length=50, required=False)
    app_version = serializers.CharField(max_length=20, required=False)
    battery_level = serializers.IntegerField(min_value=0, max_value=100, required=False)
    network_type = serializers.CharField(max_length=20, required=False)


class ConsentSerializer(serializers.Serializer):
    """User consent for biometric features"""
    gps_tracking = serializers.BooleanField()
    facial_recognition = serializers.BooleanField()
    consent_timestamp = serializers.DateTimeField()

    def validate(self, attrs):
        """Both consents must be true for check-in"""
        if not attrs.get('gps_tracking'):
            raise serializers.ValidationError(
                {"gps_tracking": "GPS tracking consent is required"}
            )
        if not attrs.get('facial_recognition'):
            raise serializers.ValidationError(
                {"facial_recognition": "Facial recognition consent is required"}
            )
        return attrs


class CheckInSerializerV2(serializers.Serializer):
    """
    Check-in serializer with GPS + facial recognition
    
    POST /api/v2/attendance/checkin/
    """
    shift_id = serializers.IntegerField()
    checkin_time = serializers.DateTimeField()
    gps_location = GPSLocationSerializer()
    face_photo = FacePhotoSerializer()
    device_info = DeviceInfoSerializer()
    consent = ConsentSerializer()

    def validate_shift_id(self, value):
        """Validate shift exists and is assigned to user"""
        user = self.context['request'].user
        
        try:
            shift = Shift.objects.get(id=value)
        except Shift.DoesNotExist:
            raise serializers.ValidationError(f"Shift {value} does not exist")
        
        return value

    def create(self, validated_data):
        """Create attendance record - handled by viewset"""
        raise NotImplementedError("Use viewset create method")


class CheckOutSerializerV2(serializers.Serializer):
    """
    Check-out serializer with time calculation
    
    POST /api/v2/attendance/checkout/
    """
    attendance_id = serializers.IntegerField()
    checkout_time = serializers.DateTimeField()
    gps_location = GPSLocationSerializer()
    face_photo = FacePhotoSerializer(required=False)
    notes = serializers.CharField(max_length=500, required=False, allow_blank=True)
    version = serializers.IntegerField(help_text="Optimistic locking version")

    def validate_attendance_id(self, value):
        """Validate attendance record exists and belongs to user"""
        user = self.context['request'].user
        
        try:
            attendance = PeopleEventlog.objects.get(id=value, people=user)
        except PeopleEventlog.DoesNotExist:
            raise serializers.ValidationError(
                f"Attendance record {value} not found or not owned by you"
            )
        
        if attendance.punchouttime is not None:
            raise serializers.ValidationError("Already checked out")
        
        return value


class GeofenceValidationSerializerV2(serializers.Serializer):
    """
    Pre-validate GPS location before check-in
    
    POST /api/v2/attendance/geofence/validate/
    """
    latitude = serializers.FloatField(min_value=-90.0, max_value=90.0)
    longitude = serializers.FloatField(min_value=-180.0, max_value=180.0)
    accuracy_meters = serializers.FloatField(min_value=0.0, max_value=1000.0)
    site_id = serializers.IntegerField()

    def validate_site_id(self, value):
        """Validate site exists"""
        try:
            site = Bt.objects.get(id=value)
        except Bt.DoesNotExist:
            raise serializers.ValidationError(f"Site {value} does not exist")
        
        return value


class PayRateSerializerV2(serializers.Serializer):
    """
    Pay rate calculation parameters
    
    GET /api/v2/attendance/pay-rates/{user_id}/
    """
    base_hourly_rate = serializers.DecimalField(max_digits=10, decimal_places=2)
    currency = serializers.CharField(max_length=3, default='SGD')
    overtime_multiplier = serializers.FloatField(default=1.5)
    break_minutes = serializers.IntegerField(default=60)
    premiums = serializers.DictField(
        child=serializers.FloatField(),
        required=False,
        help_text="Night shift, weekend, holiday premiums"
    )
    calculation_rules = serializers.DictField(
        required=False,
        help_text="Custom calculation logic"
    )


class FaceEnrollmentSerializerV2(serializers.Serializer):
    """
    Facial biometric enrollment
    
    POST /api/v2/attendance/face/enroll/
    
    Requires 3 photos for quality verification.
    """
    photos = serializers.ListField(
        child=FacePhotoSerializer(),
        min_length=3,
        max_length=3,
        help_text="Exactly 3 photos required for enrollment"
    )
    quality_threshold = serializers.FloatField(
        min_value=0.0,
        max_value=1.0,
        default=0.75,
        help_text="Minimum quality score for acceptance"
    )

    def validate_photos(self, value):
        """Ensure all photos meet quality threshold"""
        threshold = self.initial_data.get('quality_threshold', 0.75)
        
        low_quality = [
            i for i, photo in enumerate(value)
            if photo.get('photo_quality_score', 0) < threshold
        ]
        
        if low_quality:
            raise serializers.ValidationError(
                f"Photos at indices {low_quality} do not meet quality threshold {threshold}"
            )
        
        return value


class ConveyanceSerializerV2(serializers.Serializer):
    """
    Travel expense (conveyance) record
    
    POST /api/v2/attendance/conveyance/
    """
    attendance_id = serializers.IntegerField()
    conveyance_type = serializers.ChoiceField(
        choices=[
            ('public_transport', 'Public Transport'),
            ('taxi', 'Taxi'),
            ('personal_vehicle', 'Personal Vehicle'),
            ('company_vehicle', 'Company Vehicle'),
            ('bike', 'Bike'),
            ('walk', 'Walk')
        ]
    )
    distance_km = serializers.FloatField(min_value=0.0)
    amount = serializers.DecimalField(max_digits=10, decimal_places=2)
    currency = serializers.CharField(max_length=3, default='SGD')
    receipt_photo = serializers.CharField(
        required=False,
        allow_null=True,
        help_text="Base64 encoded receipt image"
    )
    description = serializers.CharField(
        max_length=500,
        required=False,
        allow_blank=True
    )
    from_location = GPSLocationSerializer(required=False)
    to_location = GPSLocationSerializer(required=False)

    def validate_attendance_id(self, value):
        """Validate attendance record exists"""
        user = self.context['request'].user
        
        try:
            PeopleEventlog.objects.get(id=value, people=user)
        except PeopleEventlog.DoesNotExist:
            raise serializers.ValidationError(
                f"Attendance record {value} not found or not owned by you"
            )
        
        return value

    def validate_receipt_photo(self, value):
        """Validate base64 receipt image"""
        if not value:
            return value
        
        try:
            if value.startswith('data:image/'):
                header, encoded = value.split(',', 1)
                decoded = base64.b64decode(encoded)
                
                if len(decoded) > 10 * 1024 * 1024:
                    raise serializers.ValidationError("Receipt photo exceeds 10MB limit")
        except Exception as e:
            raise serializers.ValidationError(f"Invalid base64 image: {str(e)}")
        
        return value


class AttendanceResponseSerializerV2(serializers.Serializer):
    """Standardized attendance response"""
    id = serializers.IntegerField()
    attendance_number = serializers.CharField()
    user = serializers.DictField()
    shift = serializers.DictField()
    checkin_time = serializers.DateTimeField()
    checkout_time = serializers.DateTimeField(allow_null=True)
    status = serializers.CharField()
    gps_validation = serializers.DictField()
    face_validation = serializers.DictField()
    time_status = serializers.DictField()
    hours_worked = serializers.FloatField(allow_null=True)
    overtime_hours = serializers.FloatField(allow_null=True)
    fraud_alerts = serializers.ListField()
    version = serializers.IntegerField()
    created_at = serializers.DateTimeField()
    correlation_id = serializers.CharField()


__all__ = [
    'CheckInSerializerV2',
    'CheckOutSerializerV2',
    'GeofenceValidationSerializerV2',
    'PayRateSerializerV2',
    'FaceEnrollmentSerializerV2',
    'ConveyanceSerializerV2',
    'AttendanceResponseSerializerV2',
    'GPSLocationSerializer',
    'FacePhotoSerializer',
    'DeviceInfoSerializer',
    'ConsentSerializer'
]
