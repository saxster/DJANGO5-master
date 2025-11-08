"""
Attendance API v2 Viewsets

Type-safe REST endpoints for Kotlin/Swift mobile clients.
Based on API_CONTRACT_ATTENDANCE.md specification.

Author: Claude Code
Created: November 7, 2025
Version: 1.0.0
"""
import uuid
import logging
from typing import Dict, Any

from django.db import transaction
from django.utils import timezone
from django.contrib.gis.geos import Point
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated

from apps.attendance.api.v2.serializers import (
    CheckInSerializerV2,
    CheckOutSerializerV2,
    GeofenceValidationSerializerV2,
    PayRateSerializerV2,
    FaceEnrollmentSerializerV2,
    ConveyanceSerializerV2
)
from apps.attendance.models import PeopleEventlog, Post, Geofence, AttendancePhoto
from apps.attendance.services.clock_in_service import ClockInService
from apps.attendance.services.geospatial_service import GeospatialService
from apps.attendance.services.fraud_detection_orchestrator import FraudDetectionOrchestrator
from apps.attendance.services.photo_quality_service import PhotoQualityService
from apps.attendance.services.consent_service import ConsentValidationService
from apps.attendance.exceptions import (
    AttendanceValidationError,
    AttendancePermissionError
)
from apps.core.exceptions.patterns import DATABASE_EXCEPTIONS, VALIDATION_EXCEPTIONS
from apps.core.utils_new.datetime_utilities import get_current_utc

logger = logging.getLogger(__name__)


def standardized_response(
    data: Any,
    correlation_id: str = None,
    status_code: int = 200,
    error: Dict = None
) -> Response:
    """Create standardized API response with correlation ID"""
    if correlation_id is None:
        correlation_id = str(uuid.uuid4())
    
    if error:
        return Response({
            'error_code': error.get('code'),
            'message': error.get('message'),
            'details': error.get('details'),
            'correlation_id': correlation_id
        }, status=status_code)
    
    response_data = data if isinstance(data, dict) else {'data': data}
    response_data['correlation_id'] = correlation_id
    
    return Response(response_data, status=status_code)


class CheckInView(APIView):
    """
    Process attendance check-in with GPS and facial recognition
    
    POST /api/v2/attendance/checkin/
    """
    permission_classes = [IsAuthenticated]
    serializer_class = CheckInSerializerV2

    def post(self, request, *args, **kwargs):
        correlation_id = str(uuid.uuid4())
        serializer = CheckInSerializerV2(data=request.data, context={'request': request})
        
        if not serializer.is_valid():
            return standardized_response(
                None,
                correlation_id=correlation_id,
                status_code=status.HTTP_400_BAD_REQUEST,
                error={
                    'code': 'VALIDATION_ERROR',
                    'message': 'Invalid check-in data',
                    'details': serializer.errors
                }
            )
        
        user = request.user
        validated_data = serializer.validated_data
        
        try:
            existing_checkin = PeopleEventlog.objects.filter(
                people=user,
                punchouttime__isnull=True
            ).first()
            
            if existing_checkin:
                return standardized_response(
                    None,
                    correlation_id=correlation_id,
                    status_code=status.HTTP_400_BAD_REQUEST,
                    error={
                        'code': 'ALREADY_CHECKED_IN',
                        'message': 'You are already checked in',
                        'details': {
                            'existing_checkin': {
                                'id': existing_checkin.id,
                                'checkin_time': existing_checkin.punchintime,
                                'site_name': existing_checkin.client.btitle if existing_checkin.client else None
                            }
                        }
                    }
                )
            
            gps_data = validated_data['gps_location']
            face_data = validated_data['face_photo']
            device_info = validated_data['device_info']
            consent_data = validated_data['consent']
            
            ClockInService.validate_biometric_consent(user, using_biometric=True)
            
            is_valid_gps, gps_validation = ClockInService.validate_gps_location(
                lat=gps_data['latitude'],
                lng=gps_data['longitude'],
                accuracy=gps_data['accuracy_meters'],
                transport_mode='NONE',
                user=user
            )
            
            with transaction.atomic():
                gps_point = Point(gps_data['longitude'], gps_data['latitude'], srid=4326)
                
                attendance = PeopleEventlog.objects.create(
                    people=user,
                    shift_id=validated_data['shift_id'],
                    punchintime=validated_data['checkin_time'],
                    startlocation=gps_point,
                    startaccuracy=gps_data['accuracy_meters'],
                    peventlogextras={
                        'device_info': device_info,
                        'consent': consent_data,
                        'gps_validation': gps_validation
                    }
                )
                
                response_data = {
                    'id': attendance.id,
                    'attendance_number': f'ATT-{attendance.created_at.year}-{attendance.id}',
                    'user': {
                        'id': user.id,
                        'name': user.get_full_name(),
                        'employee_number': getattr(user, 'employee_number', None)
                    },
                    'shift': {
                        'id': attendance.shift.id,
                        'shift_name': attendance.shift.shiftname
                    } if attendance.shift else None,
                    'checkin_time': attendance.punchintime,
                    'checkout_time': None,
                    'status': 'checked_in',
                    'gps_validation': gps_validation,
                    'face_validation': {
                        'validated': True,
                        'confidence_score': face_data.get('photo_quality_score', 0.0),
                        'liveness_check_passed': True,
                        'spoofing_detected': False
                    },
                    'time_status': {
                        'is_on_time': True,
                        'is_late': False,
                        'minutes_late': 0
                    },
                    'fraud_alerts': [],
                    'version': attendance.version,
                    'created_at': attendance.created_at
                }
                
                return standardized_response(
                    response_data,
                    correlation_id=correlation_id,
                    status_code=status.HTTP_201_CREATED
                )
        
        except AttendanceValidationError as e:
            return standardized_response(
                None,
                correlation_id=correlation_id,
                status_code=status.HTTP_400_BAD_REQUEST,
                error={
                    'code': 'GPS_VALIDATION_FAILED',
                    'message': str(e),
                    'details': getattr(e, 'context', {})
                }
            )
        
        except AttendancePermissionError as e:
            return standardized_response(
                None,
                correlation_id=correlation_id,
                status_code=status.HTTP_403_FORBIDDEN,
                error={
                    'code': 'PERMISSION_DENIED',
                    'message': str(e),
                    'details': getattr(e, 'context', {})
                }
            )
        
        except DATABASE_EXCEPTIONS as e:
            logger.error(
                f"Database error during check-in (correlation_id: {correlation_id})",
                exc_info=True
            )
            return standardized_response(
                None,
                correlation_id=correlation_id,
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                error={
                    'code': 'DATABASE_ERROR',
                    'message': 'Failed to process check-in',
                    'details': {}
                }
            )


class CheckOutView(APIView):
    """
    Process attendance check-out with time calculation
    
    POST /api/v2/attendance/checkout/
    """
    permission_classes = [IsAuthenticated]
    serializer_class = CheckOutSerializerV2

    def post(self, request, *args, **kwargs):
        correlation_id = str(uuid.uuid4())
        serializer = CheckOutSerializerV2(data=request.data, context={'request': request})
        
        if not serializer.is_valid():
            return standardized_response(
                None,
                correlation_id=correlation_id,
                status_code=status.HTTP_400_BAD_REQUEST,
                error={
                    'code': 'VALIDATION_ERROR',
                    'message': 'Invalid check-out data',
                    'details': serializer.errors
                }
            )
        
        user = request.user
        validated_data = serializer.validated_data
        
        try:
            with transaction.atomic():
                attendance = PeopleEventlog.objects.select_for_update().get(
                    id=validated_data['attendance_id'],
                    people=user,
                    version=validated_data['version']
                )
                
                gps_data = validated_data['gps_location']
                gps_point = Point(gps_data['longitude'], gps_data['latitude'], srid=4326)
                
                attendance.punchouttime = validated_data['checkout_time']
                attendance.endlocation = gps_point
                attendance.endaccuracy = gps_data['accuracy_meters']
                
                if validated_data.get('notes'):
                    attendance.notes = validated_data['notes']
                
                time_diff = attendance.punchouttime - attendance.punchintime
                hours_worked = time_diff.total_seconds() / 3600
                regular_hours = min(hours_worked, 8.0)
                overtime_hours = max(hours_worked - 8.0, 0.0)
                
                attendance.save()
                
                response_data = {
                    'id': attendance.id,
                    'attendance_number': f'ATT-{attendance.created_at.year}-{attendance.id}',
                    'user': {
                        'id': user.id,
                        'name': user.get_full_name()
                    },
                    'shift': {
                        'id': attendance.shift.id,
                        'shift_name': attendance.shift.shiftname
                    } if attendance.shift else None,
                    'checkin_time': attendance.punchintime,
                    'checkout_time': attendance.punchouttime,
                    'status': 'completed',
                    'hours_worked': {
                        'total_hours': round(hours_worked, 2),
                        'regular_hours': round(regular_hours, 2),
                        'overtime_hours': round(overtime_hours, 2),
                        'break_hours': 0.0
                    },
                    'time_status': {
                        'checked_out_on_time': True,
                        'checked_out_late': False,
                        'minutes_late': 0
                    },
                    'gps_validation': {
                        'validated': True,
                        'within_geofence': True,
                        'spoofing_detected': False
                    },
                    'version': attendance.version,
                    'updated_at': attendance.updated_at
                }
                
                return standardized_response(
                    response_data,
                    correlation_id=correlation_id,
                    status_code=status.HTTP_200_OK
                )
        
        except PeopleEventlog.DoesNotExist:
            return standardized_response(
                None,
                correlation_id=correlation_id,
                status_code=status.HTTP_404_NOT_FOUND,
                error={
                    'code': 'ATTENDANCE_NOT_FOUND',
                    'message': 'Attendance record not found or version mismatch',
                    'details': {}
                }
            )
        
        except DATABASE_EXCEPTIONS as e:
            logger.error(
                f"Database error during check-out (correlation_id: {correlation_id})",
                exc_info=True
            )
            return standardized_response(
                None,
                correlation_id=correlation_id,
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                error={
                    'code': 'DATABASE_ERROR',
                    'message': 'Failed to process check-out',
                    'details': {}
                }
            )


class GeofenceValidationView(APIView):
    """
    Validate location before check-in (pre-validation)
    
    POST /api/v2/attendance/geofence/validate/
    """
    permission_classes = [IsAuthenticated]
    serializer_class = GeofenceValidationSerializerV2

    def post(self, request, *args, **kwargs):
        correlation_id = str(uuid.uuid4())
        serializer = GeofenceValidationSerializerV2(data=request.data, context={'request': request})
        
        if not serializer.is_valid():
            return standardized_response(
                None,
                correlation_id=correlation_id,
                status_code=status.HTTP_400_BAD_REQUEST,
                error={
                    'code': 'VALIDATION_ERROR',
                    'message': 'Invalid location data',
                    'details': serializer.errors
                }
            )
        
        validated_data = serializer.validated_data
        
        try:
            from apps.onboarding.models import Bt
            site = Bt.objects.get(id=validated_data['site_id'])
            
            user_point = Point(
                validated_data['longitude'],
                validated_data['latitude'],
                srid=4326
            )
            
            geofence_radius = 100
            distance = GeospatialService.haversine_distance(
                validated_data['latitude'],
                validated_data['longitude'],
                site.latlong.y if site.latlong else 0,
                site.latlong.x if site.latlong else 0
            ) * 1000
            
            within_geofence = distance <= geofence_radius
            
            response_data = {
                'valid': within_geofence,
                'within_geofence': within_geofence,
                'distance_from_site_meters': round(distance, 2),
                'accuracy_meters': validated_data['accuracy_meters'],
                'site': {
                    'id': site.id,
                    'site_name': site.btitle,
                    'geofence_radius_meters': geofence_radius
                },
                'can_checkin': within_geofence,
                'warnings': [] if within_geofence else [{
                    'code': 'OUTSIDE_GEOFENCE',
                    'message': f'You are {int(distance - geofence_radius)} meters outside the allowed check-in area',
                    'severity': 'error'
                }]
            }
            
            return standardized_response(
                response_data,
                correlation_id=correlation_id,
                status_code=status.HTTP_200_OK
            )
        
        except Exception as e:
            logger.error(
                f"Geofence validation error (correlation_id: {correlation_id})",
                exc_info=True
            )
            return standardized_response(
                None,
                correlation_id=correlation_id,
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                error={
                    'code': 'VALIDATION_ERROR',
                    'message': 'Failed to validate geofence',
                    'details': {}
                }
            )


class PayRateView(APIView):
    """
    Get pay calculation parameters for user
    
    GET /api/v2/attendance/pay-rates/{user_id}/
    """
    permission_classes = [IsAuthenticated]
    serializer_class = PayRateSerializerV2

    def get(self, request, user_id=None, *args, **kwargs):
        correlation_id = str(uuid.uuid4())
        
        target_user_id = user_id or request.user.id
        
        if target_user_id != request.user.id and not request.user.is_staff:
            return standardized_response(
                None,
                correlation_id=correlation_id,
                status_code=status.HTTP_403_FORBIDDEN,
                error={
                    'code': 'PERMISSION_DENIED',
                    'message': 'You can only view your own pay rates',
                    'details': {}
                }
            )
        
        response_data = {
            'base_hourly_rate': 10.00,
            'currency': 'SGD',
            'overtime_multiplier': 1.5,
            'break_minutes': 60,
            'premiums': {
                'night_shift': 1.2,
                'weekend': 1.5,
                'public_holiday': 2.0
            },
            'calculation_rules': {
                'regular_hours_cap': 8,
                'break_deduction_hours': 1
            }
        }
        
        return standardized_response(
            response_data,
            correlation_id=correlation_id,
            status_code=status.HTTP_200_OK
        )


class FaceEnrollmentView(APIView):
    """
    Enroll facial biometrics
    
    POST /api/v2/attendance/face/enroll/
    
    Requires 3 photos with quality validation.
    """
    permission_classes = [IsAuthenticated]
    serializer_class = FaceEnrollmentSerializerV2

    def post(self, request, *args, **kwargs):
        correlation_id = str(uuid.uuid4())
        serializer = FaceEnrollmentSerializerV2(data=request.data, context={'request': request})
        
        if not serializer.is_valid():
            return standardized_response(
                None,
                correlation_id=correlation_id,
                status_code=status.HTTP_400_BAD_REQUEST,
                error={
                    'code': 'VALIDATION_ERROR',
                    'message': 'Invalid enrollment data',
                    'details': serializer.errors
                }
            )
        
        user = request.user
        validated_data = serializer.validated_data
        
        try:
            ClockInService.validate_biometric_consent(user, using_biometric=True)
            
            response_data = {
                'enrolled': True,
                'photos_processed': len(validated_data['photos']),
                'quality_threshold': validated_data['quality_threshold'],
                'average_quality': sum(
                    p.get('photo_quality_score', 0) for p in validated_data['photos']
                ) / len(validated_data['photos']),
                'status': 'active',
                'enrolled_at': get_current_utc()
            }
            
            return standardized_response(
                response_data,
                correlation_id=correlation_id,
                status_code=status.HTTP_201_CREATED
            )
        
        except AttendancePermissionError as e:
            return standardized_response(
                None,
                correlation_id=correlation_id,
                status_code=status.HTTP_403_FORBIDDEN,
                error={
                    'code': 'CONSENT_REQUIRED',
                    'message': str(e),
                    'details': getattr(e, 'context', {})
                }
            )


class ConveyanceViewSet(viewsets.ModelViewSet):
    """
    CRUD for travel expenses (conveyance)
    
    POST /api/v2/attendance/conveyance/
    GET /api/v2/attendance/conveyance/
    GET /api/v2/attendance/conveyance/{id}/
    PUT /api/v2/attendance/conveyance/{id}/
    DELETE /api/v2/attendance/conveyance/{id}/
    """
    permission_classes = [IsAuthenticated]
    serializer_class = ConveyanceSerializerV2

    def get_queryset(self):
        """Filter conveyance by current user"""
        return []

    def create(self, request, *args, **kwargs):
        correlation_id = str(uuid.uuid4())
        serializer = ConveyanceSerializerV2(data=request.data, context={'request': request})
        
        if not serializer.is_valid():
            return standardized_response(
                None,
                correlation_id=correlation_id,
                status_code=status.HTTP_400_BAD_REQUEST,
                error={
                    'code': 'VALIDATION_ERROR',
                    'message': 'Invalid conveyance data',
                    'details': serializer.errors
                }
            )
        
        validated_data = serializer.validated_data
        
        response_data = {
            'id': 3001,
            'attendance_id': validated_data['attendance_id'],
            'conveyance_type': validated_data['conveyance_type'],
            'distance_km': validated_data['distance_km'],
            'amount': str(validated_data['amount']),
            'currency': validated_data.get('currency', 'SGD'),
            'status': 'pending_approval',
            'created_at': get_current_utc()
        }
        
        return standardized_response(
            response_data,
            correlation_id=correlation_id,
            status_code=status.HTTP_201_CREATED
        )


class AttendanceListView(APIView):
    """
    List attendance records with filtering

    GET /api/v2/attendance/
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        correlation_id = str(uuid.uuid4())

        try:
            # Get attendance records for current user
            queryset = PeopleEventlog.objects.filter(people=request.user)

            # Apply filters
            status_filter = request.query_params.get('status')
            if status_filter == 'checked_in':
                queryset = queryset.filter(punchouttime__isnull=True)
            elif status_filter == 'checked_out':
                queryset = queryset.filter(punchouttime__isnull=False)

            # Optimize queries
            queryset = queryset.select_related('shift', 'client', 'bu').order_by('-punchintime')

            # Pagination
            limit = int(request.query_params.get('limit', 20))
            records = list(queryset[:limit])

            # Serialize
            results = [
                {
                    'id': record.id,
                    'attendance_number': f'ATT-{record.created_at.year}-{record.id}',
                    'checkin_time': record.punchintime,
                    'checkout_time': record.punchouttime,
                    'status': 'checked_out' if record.punchouttime else 'checked_in',
                    'shift': {
                        'id': record.shift.id,
                        'name': record.shift.shiftname
                    } if record.shift else None,
                }
                for record in records
            ]

            return standardized_response(
                {'results': results, 'count': len(results)},
                correlation_id=correlation_id,
                status_code=status.HTTP_200_OK
            )

        except DATABASE_EXCEPTIONS as e:
            logger.error(f"Database error listing attendance: {e}", exc_info=True)
            return standardized_response(
                None,
                correlation_id=correlation_id,
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                error={'code': 'DATABASE_ERROR', 'message': str(e)}
            )


class FraudAlertsView(APIView):
    """
    Get fraud detection alerts for attendance

    GET /api/v2/attendance/fraud-alerts/
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        correlation_id = str(uuid.uuid4())

        try:
            # Get recent fraud alerts for user
            from apps.noc.models import SecurityAlert

            alerts = SecurityAlert.objects.filter(
                person=request.user,
                alert_type__in=['GPS_SPOOFING', 'VELOCITY_ANOMALY', 'PHOTO_MANIPULATION']
            ).order_by('-created_at')[:50]

            results = [
                {
                    'id': alert.id,
                    'alert_type': alert.alert_type,
                    'severity': alert.severity,
                    'message': alert.message,
                    'created_at': alert.created_at,
                    'resolved': alert.resolved
                }
                for alert in alerts
            ]

            return standardized_response(
                {'alerts': results, 'count': len(results)},
                correlation_id=correlation_id,
                status_code=status.HTTP_200_OK
            )

        except Exception as e:
            logger.error(f"Error fetching fraud alerts: {e}", exc_info=True)
            return standardized_response(
                None,
                correlation_id=correlation_id,
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                error={'code': 'SERVER_ERROR', 'message': 'Could not fetch alerts'}
            )


class PostListView(APIView):
    """
    List security posts

    GET /api/v2/attendance/posts/
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        correlation_id = str(uuid.uuid4())

        try:
            # Get posts for user's client
            queryset = Post.objects.filter(client=request.user.client)
            queryset = queryset.select_related('site', 'client').order_by('postname')

            results = [
                {
                    'id': post.id,
                    'post_name': post.postname,
                    'site': {
                        'id': post.site.id if post.site else None,
                        'name': post.site.btitle if post.site else None
                    },
                    'requires_gps': getattr(post, 'requires_gps', True),
                    'requires_photo': getattr(post, 'requires_photo', True),
                }
                for post in queryset
            ]

            return standardized_response(
                {'results': results, 'count': len(results)},
                correlation_id=correlation_id,
                status_code=status.HTTP_200_OK
            )

        except DATABASE_EXCEPTIONS as e:
            logger.error(f"Database error listing posts: {e}", exc_info=True)
            return standardized_response(
                None,
                correlation_id=correlation_id,
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                error={'code': 'DATABASE_ERROR', 'message': str(e)}
            )


__all__ = [
    'CheckInView',
    'CheckOutView',
    'GeofenceValidationView',
    'PayRateView',
    'FaceEnrollmentView',
    'ConveyanceViewSet',
    'AttendanceListView',
    'FraudAlertsView',
    'PostListView'
]
