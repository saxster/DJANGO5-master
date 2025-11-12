"""
Enhanced Attendance Views

Complete clock-in/out endpoints with all security and fraud detection integrations.

This file shows the COMPLETE implementation of clock-in/out with:
- Consent validation
- Photo capture and validation
- GPS spoofing detection
- Fraud detection and scoring
- Expense calculation
- Audit logging (automatic via middleware)

INTEGRATION INSTRUCTIONS:
1. Review this code
2. Merge these methods into apps/attendance/api/viewsets.py
3. Or use this as a new viewset and register it in URLs
"""

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.utils import timezone
from django.db import transaction
from typing import Optional

from apps.attendance.models import PeopleEventlog
from apps.attendance.models.attendance_photo import AttendancePhoto
from apps.attendance.models.fraud_alert import FraudAlert
from apps.attendance.api.serializers import AttendanceSerializer
from apps.core.permissions import TenantIsolationPermission

# Import all enhancement services
from apps.attendance.services.consent_service import ConsentValidationService
from apps.attendance.services.photo_quality_service import PhotoQualityService
from apps.attendance.services.fraud_detection_orchestrator import FraudDetectionOrchestrator
from apps.attendance.services.gps_spoofing_detector import GPSSpoofingDetector
from apps.attendance.services.geospatial_service import GeospatialService
from apps.attendance.services.expense_calculation_service import ExpenseCalculationService
from apps.attendance.services.clock_in_service import ClockInService
from apps.attendance.exceptions import (
    AttendancePermissionError,
    AttendanceValidationError,
)

import logging
from apps.core.exceptions.patterns import DATABASE_EXCEPTIONS


logger = logging.getLogger(__name__)


class EnhancedAttendanceViewSet(viewsets.ModelViewSet):
    """
    Enhanced Attendance ViewSet with complete security and fraud detection.

    This viewset includes ALL enhancements:
    - Consent validation (CA/LA compliance)
    - Photo capture with quality validation
    - GPS spoofing detection
    - Real-time fraud detection
    - Automatic expense calculation
    - Comprehensive audit logging (via middleware)
    """

    queryset = PeopleEventlog.objects.all()
    serializer_class = AttendanceSerializer
    permission_classes = [IsAuthenticated, TenantIsolationPermission]

    def get_queryset(self):
        """Filter by tenant and user permissions"""
        queryset = super().get_queryset()

        # Non-admin users see only their own records
        if not self.request.user.is_staff:
            queryset = queryset.filter(people=self.request.user)
        elif not self.request.user.is_superuser:
            # Admin users see their tenant's records
            queryset = queryset.filter(tenant=self.request.user.client_id)

        return queryset.select_related('people', 'client', 'bu', 'shift')

    @action(detail=False, methods=['post'])
    def clock_in(self, request):
        """Clock in with comprehensive validation"""
        try:
            # Parse request data
            lat = float(request.data.get('lat'))
            lng = float(request.data.get('lng'))
            accuracy = float(request.data.get('accuracy', 20.0))
            transport_mode = request.data.get('transport_mode', 'NONE')
            client_id = request.user.client_id if hasattr(request.user, 'client_id') else None
            using_biometric = 'photo' in request.FILES or request.data.get('use_face_recognition', False)
            photo_file = request.FILES.get('photo')
            photo_required = self._is_photo_required(client_id, photo_type='CLOCK_IN')
            
            # Validate consents
            ClockInService.validate_biometric_consent(request.user, using_biometric)
            
            # Validate GPS location
            ClockInService.validate_gps_location(lat, lng, accuracy, transport_mode, request.user)
            
            # Validate photo requirements
            ClockInService.validate_photo_requirements(photo_file, photo_required)
            
            # Perform clock-in
            attendance, photo_instance, fraud_result = ClockInService.perform_clock_in(
                user=request.user,
                lat=lat,
                lng=lng,
                accuracy=accuracy,
                device_id=request.data.get('device_id'),
                transport_mode=transport_mode,
                photo_file=photo_file,
                shift_id=request.data.get('shift_id'),
                notes=request.data.get('notes', ''),
                client_id=client_id,
                photo_required=photo_required
            )
            
            # Return success response
            return Response({
                'id': attendance.id,
                'status': 'success',
                'message': 'Clocked in successfully',
                'timestamp': attendance.punchintime.isoformat(),
                'location': {'lat': lat, 'lng': lng, 'accuracy': accuracy},
                'fraud_analysis': {
                    'score': round(fraud_result['analysis']['composite_score'], 3),
                    'risk_level': fraud_result['analysis']['risk_level'],
                    'anomaly_count': len(fraud_result['anomalies']),
                    'warnings': [a['description'] for a in fraud_result['anomalies']] if fraud_result['anomalies'] else []
                },
                'photo_captured': photo_instance is not None,
                'photo_quality': photo_instance.quality_rating if photo_instance else None,
            }, status=status.HTTP_201_CREATED)
            
        except AttendancePermissionError as e:
            logger.warning(f"Permission denied for clock-in: {e}")
            return Response({
                'error': 'PERMISSION_DENIED',
                'message': str(e),
                'context': e.context if hasattr(e, 'context') else {}
            }, status=status.HTTP_403_FORBIDDEN)
        except AttendanceValidationError as e:
            logger.warning(f"Validation failed for clock-in: {e}")
            return Response({
                'error': 'VALIDATION_FAILED',
                'message': str(e),
                'context': e.context if hasattr(e, 'context') else {}
            }, status=status.HTTP_400_BAD_REQUEST)
        except DATABASE_EXCEPTIONS as e:
            logger.error(f"Database error during clock-in for {request.user.username}: {e}", exc_info=True)
            return Response({
                'error': 'CLOCK_IN_FAILED',
                'message': 'Database error occurred. Please try again or contact support.',
                'support_id': getattr(request, 'correlation_id', 'N/A')
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        except (ValueError, TypeError, KeyError) as e:
            logger.error(f"Data validation error during clock-in for {request.user.username}: {e}", exc_info=True)
            return Response({
                'error': 'INVALID_DATA',
                'message': 'Invalid request data. Please check your inputs.',
                'support_id': getattr(request, 'correlation_id', 'N/A')
            }, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['post'])
    def clock_out(self, request):
        """
        Clock out with expense calculation.

        Request Body:
        {
            "lat": 37.7749,
            "lng": -122.4194,
            "accuracy": 15.0,
            "photo": "<base64_or_multipart_file>",  # Optional for clock-out
            "notes": "Completed shift"  # Optional
        }

        Response:
        {
            "id": 12345,
            "status": "success",
            "message": "Clocked out successfully",
            "timestamp": "2025-11-03T22:30:00Z",
            "work_duration": "8.0 hours",
            "distance": "45.2 km",
            "expense_calculated": 22.50,
            "photo_captured": false
        }
        """
        try:
            # Find today's open attendance record for this user
            today = timezone.now().date()

            attendance = PeopleEventlog.objects.filter(
                people=request.user,
                datefor=today,
                punchintime__isnull=False,
                punchouttime__isnull=True  # Not yet clocked out
            ).order_by('-punchintime').first()

            if not attendance:
                return Response({
                    'error': 'NO_OPEN_ATTENDANCE',
                    'message': 'No open clock-in found for today. Please clock in first.',
                }, status=status.HTTP_400_BAD_REQUEST)

            # ================================================================
            # STEP 1: VALIDATE GPS (same as clock-in)
            # ================================================================
            lat = float(request.data.get('lat'))
            lng = float(request.data.get('lng'))
            accuracy = float(request.data.get('accuracy', 20.0))

            # Validate GPS (check velocity from start location)
            is_valid_gps, gps_validation_results = GPSSpoofingDetector.validate_gps_location(
                latitude=lat,
                longitude=lng,
                accuracy=accuracy,
                previous_record=attendance,  # Check against clock-in location
                transport_mode=attendance.transportmodes[0] if attendance.transportmodes else 'NONE'
            )

            if not is_valid_gps and gps_validation_results['risk_score'] > 0.8:
                # Only block on high-confidence spoofing
                return Response({
                    'error': 'GPS_VALIDATION_FAILED',
                    'message': 'Location verification failed',
                    'details': gps_validation_results['spoofing_indicators'],
                }, status=status.HTTP_400_BAD_REQUEST)

            # ================================================================
            # STEP 2: PROCESS PHOTO (if provided)
            # ================================================================
            photo_instance = None
            if 'photo' in request.FILES:
                try:
                    photo_instance = PhotoQualityService.process_attendance_photo(
                        image_file=request.FILES['photo'],
                        attendance_record=attendance,
                        employee=request.user,
                        photo_type=AttendancePhoto.PhotoType.CLOCK_OUT,
                        client_id=client_id
                    )

                    attendance.checkout_photo = photo_instance

                except AttendanceValidationError as e:
                    # Log warning but don't block clock-out (photo less critical for clock-out)
                    logger.warning(f"Clock-out photo validation failed: {e}")

            # ================================================================
            # STEP 3: UPDATE ATTENDANCE RECORD
            # ================================================================
            with transaction.atomic():
                # Set clock-out data
                attendance.punchouttime = timezone.now()
                attendance.endlocation = GeospatialService.create_point(lng, lat)

                # Calculate work duration
                if attendance.punchintime:
                    time_delta = attendance.punchouttime - attendance.punchintime
                    attendance.duration = int(time_delta.total_seconds() / 60)  # Minutes

                # Calculate distance if both locations exist
                if attendance.startlocation and attendance.endlocation:
                    start_lon, start_lat = GeospatialService.extract_coordinates(attendance.startlocation)
                    end_lon, end_lat = GeospatialService.extract_coordinates(attendance.endlocation)

                    distance_km = GeospatialService.haversine_distance(
                        (start_lon, start_lat),
                        (end_lon, end_lat)
                    )
                    attendance.distance = distance_km

                attendance.save()

                # ================================================================
                # STEP 4: CALCULATE EXPENSE
                # ================================================================
                expense_amount = 0.0
                if attendance.distance and attendance.distance > 0:
                    try:
                        expense = ExpenseCalculationService.calculate_expense(attendance)
                        expense_amount = float(expense)
                        logger.info(
                            f"Calculated expense for attendance {attendance.id}: ${expense} "
                            f"({attendance.distance}km)"
                        )
                    except DATABASE_EXCEPTIONS as e:
                        logger.error(f"Expense calculation failed: {e}", exc_info=True)

                # ================================================================
                # STEP 5: RUN FRAUD DETECTION ON COMPLETE RECORD
                # ================================================================
                try:
                    orchestrator = FraudDetectionOrchestrator(request.user)
                    fraud_result = orchestrator.analyze_attendance(attendance)

                    # Update fraud scores
                    attendance.fraud_score = fraud_result['analysis']['composite_score']
                    attendance.fraud_risk_level = fraud_result['analysis']['risk_level']
                    attendance.fraud_anomalies = fraud_result['anomalies']
                    attendance.fraud_analyzed_at = timezone.now()
                    attendance.save(update_fields=[
                        'fraud_score', 'fraud_risk_level',
                        'fraud_anomalies', 'fraud_analyzed_at'
                    ])

                    # Create alert if suspicious (don't block clock-out, but flag)
                    if fraud_result['analysis']['composite_score'] >= 0.6:
                        FraudAlert.objects.create(
                            employee=request.user,
                            attendance_record=attendance,
                            alert_type=FraudAlert.AlertType.UNUSUAL_PATTERN,
                            severity=FraudAlert.Severity.HIGH if fraud_result['analysis']['composite_score'] >= 0.7 else FraudAlert.Severity.MEDIUM,
                            fraud_score=fraud_result['analysis']['composite_score'],
                            risk_score=int(fraud_result['analysis']['composite_score'] * 100),
                            evidence=fraud_result['detector_details'],
                            anomalies_detected=fraud_result['anomalies'],
                            auto_blocked=False,
                            tenant=client_id or 'default'
                        )

                except (ValueError, TypeError, KeyError, AttributeError) as e:
                    logger.error(f"Fraud detection failed for clock-out: {e}", exc_info=True)

            # ================================================================
            # STEP 6: RETURN SUCCESS RESPONSE
            # ================================================================
            return Response({
                'id': attendance.id,
                'status': 'success',
                'message': 'Clocked out successfully',
                'timestamp': attendance.punchouttime.isoformat(),
                'work_duration_hours': round(attendance.duration / 60, 1) if attendance.duration else 0,
                'distance_km': round(attendance.distance, 2) if attendance.distance else 0,
                'expense_calculated': expense_amount,
                'photo_captured': photo_instance is not None,
            }, status=status.HTTP_200_OK)

        except PeopleEventlog.DoesNotExist:
            return Response({
                'error': 'NO_OPEN_ATTENDANCE',
                'message': 'No open attendance found',
            }, status=status.HTTP_404_NOT_FOUND)

        except (IntegrityError, OperationalError, DatabaseError) as e:
            logger.error(f"Database error during clock-out: {e}", exc_info=True)
            return Response({
                'error': 'CLOCK_OUT_FAILED',
                'message': 'Database error occurred. Please try again.',
                'support_id': getattr(request, 'correlation_id', 'N/A')
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
        except (ValueError, TypeError, KeyError) as e:
            logger.error(f"Data validation error during clock-out: {e}", exc_info=True)
            return Response({
                'error': 'INVALID_DATA',
                'message': 'Invalid request data',
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def _is_photo_required(self, client_id: Optional[int], photo_type: str) -> bool:
        """
        Check if photo is required for this client.

        Args:
            client_id: Client ID
            photo_type: 'CLOCK_IN' or 'CLOCK_OUT'

        Returns:
            True if photo required
        """
        if not client_id:
            return False  # Default: not required

        try:
            from apps.attendance.models.attendance_photo import PhotoQualityThreshold

            threshold = PhotoQualityThreshold.objects.get(
                client_id=client_id,
                is_active=True
            )

            if photo_type == 'CLOCK_IN':
                return threshold.photo_required_clock_in
            elif photo_type == 'CLOCK_OUT':
                return threshold.photo_required_clock_out

        except PhotoQualityThreshold.DoesNotExist:
            pass

        return False  # Default if no configuration
