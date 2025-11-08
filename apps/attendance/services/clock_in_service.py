"""
Clock-In Service

Extracted business logic from clock_in view method for ADR 003 compliance.
Reduces view method from 216 lines to <30 lines.
"""
from typing import Dict, Optional, Tuple
from django.db import transaction
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.attendance.models import PeopleEventlog
from apps.attendance.models.attendance_photo import AttendancePhoto
from apps.attendance.models.fraud_alert import FraudAlert
from apps.attendance.exceptions import (
    AttendancePermissionError,
    AttendanceValidationError,
)
from apps.attendance.services.consent_service import ConsentValidationService
from apps.attendance.services.photo_quality_service import PhotoQualityService
from apps.attendance.services.fraud_detection_orchestrator import FraudDetectionOrchestrator
from apps.attendance.services.gps_spoofing_detector import GPSSpoofingDetector
from apps.attendance.services.geospatial_service import GeospatialService
from apps.core.exceptions.patterns import DATABASE_EXCEPTIONS

import logging

logger = logging.getLogger(__name__)


class ClockInService:
    """Service for clock-in business logic orchestration"""
    
    @staticmethod
    def validate_biometric_consent(user, using_biometric: bool) -> None:
        """Validate biometric consent if biometric features are used"""
        if not using_biometric:
            return
        
        can_use_biometric, missing_consents = ConsentValidationService.can_user_use_biometric_features(user)
        
        if not can_use_biometric:
            logger.warning(
                f"Biometric features blocked for {user.username}: missing biometric consents",
                extra={'missing_consents': missing_consents}
            )
            raise AttendancePermissionError(
                'Biometric consent required for face recognition and photo capture',
                context={
                    'missing_consents': missing_consents,
                    'action_required': 'Accept biometric consent policy at /attendance/consent/',
                    'note': 'GPS tracking is core app functionality and does not require consent'
                }
            )
    
    @staticmethod
    def validate_gps_location(
        lat: float,
        lng: float,
        accuracy: float,
        transport_mode: str,
        user
    ) -> Tuple[bool, Dict]:
        """Validate GPS location with spoofing detection"""
        # Get previous attendance for velocity check
        previous_attendance = PeopleEventlog.objects.filter(
            people=user,
            punchouttime__isnull=False
        ).order_by('-punchouttime').first()
        
        # Validate GPS with spoofing detection
        is_valid_gps, gps_validation_results = GPSSpoofingDetector.validate_gps_location(
            latitude=lat,
            longitude=lng,
            accuracy=accuracy,
            previous_record=previous_attendance,
            transport_mode=transport_mode
        )
        
        if not is_valid_gps:
            logger.warning(
                f"GPS validation failed for {user.username}",
                extra=gps_validation_results
            )
            raise AttendanceValidationError(
                'Your location could not be verified',
                context={
                    'details': gps_validation_results['spoofing_indicators'],
                    'suggestions': [
                        'Ensure GPS is enabled on your device',
                        'Move to an area with better GPS signal',
                        'Disable any location spoofing apps',
                        'Contact your manager if this persists'
                    ]
                }
            )
        
        return is_valid_gps, gps_validation_results
    
    @staticmethod
    def validate_photo_requirements(photo_file, photo_required: bool) -> None:
        """Validate photo meets requirements"""
        if photo_required and not photo_file:
            raise AttendanceValidationError(
                'Photo is required for clock-in at your location'
            )
        
        if photo_file:
            # Quick validation (detailed validation after record creation)
            if photo_file.size > 5 * 1024 * 1024:  # 5MB max
                raise AttendanceValidationError(
                    'Photo must be smaller than 5MB'
                )
    
    @staticmethod
    def create_attendance_record(
        user,
        lat: float,
        lng: float,
        accuracy: float,
        device_id: str,
        transport_mode: str,
        client_id: str,
        shift_id: Optional[int],
        notes: str,
        has_photo: bool
    ) -> PeopleEventlog:
        """Create attendance record"""
        # Create GPS point
        gps_point = GeospatialService.create_point(lng, lat)
        
        # Create attendance record
        attendance = PeopleEventlog.objects.create(
            people=user,
            punchintime=timezone.now(),
            datefor=timezone.now().date(),
            startlocation=gps_point,
            accuracy=accuracy,
            deviceid=device_id,
            transportmodes=[transport_mode] if transport_mode and transport_mode != 'NONE' else [],
            tenant=client_id or 'default',
            client_id=client_id,
            shift_id=shift_id,
            remarks=notes,
            facerecognitionin=has_photo,
        )
        
        logger.info(f"Created attendance record {attendance.id} for {user.username}")
        return attendance
    
    @staticmethod
    def process_photo(
        photo_file,
        attendance: PeopleEventlog,
        user,
        client_id: str,
        photo_required: bool
    ) -> Optional[AttendancePhoto]:
        """Process and validate attendance photo"""
        if not photo_file:
            return None
        
        try:
            photo_instance = PhotoQualityService.process_attendance_photo(
                image_file=photo_file,
                attendance_record=attendance,
                employee=user,
                photo_type=AttendancePhoto.PhotoType.CLOCK_IN,
                client_id=client_id
            )
            
            # Link photo to attendance
            attendance.checkin_photo = photo_instance
            attendance.save(update_fields=['checkin_photo'])
            
            logger.info(f"Processed clock-in photo for attendance {attendance.id}")
            return photo_instance
            
        except AttendanceValidationError as e:
            # Photo failed validation
            logger.error(f"Photo validation failed: {e}")
            
            # If photo is required, fail the clock-in
            if photo_required:
                attendance.delete()  # Rollback
                raise
            
            # Otherwise, log warning and continue
            logger.warning(f"Photo validation failed but not required: {e}")
            return None
    
    @staticmethod
    def analyze_fraud(
        attendance: PeopleEventlog,
        user,
        client_id: str
    ) -> Dict:
        """Perform fraud detection analysis and handle results"""
        try:
            orchestrator = FraudDetectionOrchestrator(user)
            fraud_result = orchestrator.analyze_attendance(attendance)
            
            # Save fraud detection results
            attendance.fraud_score = fraud_result['analysis']['composite_score']
            attendance.fraud_risk_level = fraud_result['analysis']['risk_level']
            attendance.fraud_anomalies = fraud_result['anomalies']
            attendance.fraud_analyzed_at = timezone.now()
            attendance.save(update_fields=[
                'fraud_score',
                'fraud_risk_level',
                'fraud_anomalies',
                'fraud_analyzed_at'
            ])
            
            logger.info(
                f"Fraud analysis complete for attendance {attendance.id}: "
                f"score={fraud_result['analysis']['composite_score']:.3f}, "
                f"risk={fraud_result['analysis']['risk_level']}"
            )
            
            # Handle high-risk fraud
            if fraud_result['analysis']['should_block']:
                ClockInService._handle_fraud_alert(
                    fraud_result, user, attendance, client_id, auto_blocked=True
                )
                raise AttendancePermissionError(
                    'Your check-in has been flagged for manager review due to unusual activity',
                    context={
                        'fraud_score': fraud_result['analysis']['composite_score'],
                        'risk_level': fraud_result['analysis']['risk_level'],
                        'anomalies': [a['description'] for a in fraud_result['anomalies']],
                        'action_required': 'Please contact your manager for manual verification'
                    }
                )
            
            # Check for MEDIUM/HIGH risk (flag but don't block)
            elif fraud_result['analysis']['composite_score'] >= 0.5:
                ClockInService._handle_fraud_alert(
                    fraud_result, user, attendance, client_id, auto_blocked=False
                )
            
            return fraud_result
            
        except DATABASE_EXCEPTIONS as e:
            # Don't fail clock-in if fraud detection fails
            logger.error(f"Fraud detection failed for attendance {attendance.id}: {e}", exc_info=True)
            return {
                'analysis': {
                    'composite_score': 0.0,
                    'risk_level': 'UNKNOWN',
                    'should_block': False
                },
                'anomalies': []
            }
    
    @staticmethod
    def _handle_fraud_alert(
        fraud_result: Dict,
        user,
        attendance: PeopleEventlog,
        client_id: str,
        auto_blocked: bool
    ) -> FraudAlert:
        """Create fraud alert based on analysis results"""
        alert = FraudAlert.objects.create(
            employee=user,
            attendance_record=attendance,
            alert_type=FraudAlert.AlertType.HIGH_RISK_BEHAVIOR if auto_blocked else FraudAlert.AlertType.UNUSUAL_PATTERN,
            severity=FraudAlert.Severity.CRITICAL if auto_blocked else (
                FraudAlert.Severity.HIGH if fraud_result['analysis']['composite_score'] >= 0.6 
                else FraudAlert.Severity.MEDIUM
            ),
            fraud_score=fraud_result['analysis']['composite_score'],
            risk_score=int(fraud_result['analysis']['composite_score'] * 100),
            evidence=fraud_result['detector_details'],
            anomalies_detected=fraud_result['anomalies'],
            auto_blocked=auto_blocked,
            tenant=client_id or 'default'
        )
        
        if auto_blocked:
            logger.critical(
                f"FRAUD DETECTED: Auto-blocked clock-in for {user.username}, "
                f"alert_id={alert.id}, score={fraud_result['analysis']['composite_score']:.3f}"
            )
        else:
            logger.warning(
                f"Suspicious activity detected for {user.username}: "
                f"score={fraud_result['analysis']['composite_score']:.3f}, alert_id={alert.id}"
            )
        
        return alert
    
    @staticmethod
    def perform_clock_in(
        user,
        lat: float,
        lng: float,
        accuracy: float,
        device_id: str,
        transport_mode: str,
        photo_file,
        shift_id: Optional[int],
        notes: str,
        client_id: str,
        photo_required: bool
    ) -> Tuple[PeopleEventlog, Optional[AttendancePhoto], Dict]:
        """
        Main orchestration method for clock-in process.
        
        Returns:
            Tuple of (attendance_record, photo_instance, fraud_result)
        """
        with transaction.atomic():
            # Create attendance record
            attendance = ClockInService.create_attendance_record(
                user=user,
                lat=lat,
                lng=lng,
                accuracy=accuracy,
                device_id=device_id,
                transport_mode=transport_mode,
                client_id=client_id,
                shift_id=shift_id,
                notes=notes,
                has_photo=photo_file is not None
            )
            
            # Process photo if provided
            photo_instance = ClockInService.process_photo(
                photo_file=photo_file,
                attendance=attendance,
                user=user,
                client_id=client_id,
                photo_required=photo_required
            )
            
            # Fraud detection analysis
            fraud_result = ClockInService.analyze_fraud(
                attendance=attendance,
                user=user,
                client_id=client_id
            )
            
            return attendance, photo_instance, fraud_result
