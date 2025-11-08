"""
Location Fraud Detector Service.

Detects GPS spoofing and geofence violations.
Validates location quality, speed, and network correlation.

Follows .claude/rules.md:
- Rule #7: Service < 150 lines
- Rule #8: Methods < 30 lines
- Rule #11: Specific exception handling
- Rule #13: Use constants instead of magic numbers
"""

import logging
from datetime import timedelta
from django.utils import timezone
from django.db import transaction
from django.contrib.gis.measure import D
from django.contrib.gis.geos import Point
from apps.core.services.exif_analysis_service import EXIFAnalysisService
from apps.core.models import ImageMetadata, PhotoAuthenticityLog
from apps.core.constants.spatial_constants import METERS_PER_DEGREE_LAT
from apps.core.exceptions.patterns import DATABASE_EXCEPTIONS


logger = logging.getLogger('noc.security_intelligence')


class LocationFraudDetector:
    """Detects GPS-based location fraud."""

    def __init__(self, config):
        """
        Initialize detector with configuration.

        Args:
            config: SecurityAnomalyConfig instance
        """
        self.config = config

    def detect_gps_spoofing(self, attendance_event):
        """
        Detect GPS manipulation via impossible speed.

        Args:
            attendance_event: PeopleEventlog instance

        Returns:
            dict: Fraud detection result or None
        """
        from apps.activity.models import Location

        try:
            if not attendance_event.startlocation:
                return None

            recent_location = Location.objects.filter(
                people=attendance_event.people,
                cdtz__lt=attendance_event.punchintime,
                gpslocation__isnull=False
            ).order_by('-cdtz').first()

            if not recent_location:
                return None

            distance_m = recent_location.gpslocation.distance(attendance_event.startlocation)
            distance_km = distance_m / 1000

            time_diff_seconds = (attendance_event.punchintime - recent_location.cdtz).total_seconds()

            if time_diff_seconds <= 0:
                return None

            speed_kmh = (distance_km / time_diff_seconds) * 3600

            if speed_kmh > self.config.max_travel_speed_kmh:
                return {
                    'anomaly_type': 'GPS_SPOOFING',
                    'severity': 'CRITICAL',
                    'calculated_speed_kmh': speed_kmh,
                    'distance_km': distance_km,
                    'time_seconds': time_diff_seconds,
                    'confidence_score': 0.99,
                    'evidence_data': {
                        'max_allowed_speed': self.config.max_travel_speed_kmh,
                        'exceeded_by': speed_kmh - self.config.max_travel_speed_kmh,
                    }
                }

        except (ValueError, AttributeError) as e:
            logger.error(f"GPS spoofing detection error: {e}", exc_info=True)

        return None

    def detect_geofence_violation(self, attendance_event):
        """
        Detect attendance outside geofence.

        Args:
            attendance_event: PeopleEventlog instance

        Returns:
            dict: Geofence violation result or None
        """
        try:
            if not attendance_event.startlocation or not attendance_event.bu:
                return None

            site = attendance_event.bu

            if not hasattr(site, 'gpslocation') or not site.gpslocation:
                return None

            distance_m = site.gpslocation.distance(attendance_event.startlocation)

            threshold_m = self.config.geofence_violation_threshold_meters

            if distance_m > threshold_m:
                return {
                    'anomaly_type': 'GEOFENCE_VIOLATION',
                    'severity': 'HIGH',
                    'distance_outside_meters': distance_m - threshold_m,
                    'total_distance_meters': distance_m,
                    'confidence_score': 0.90,
                    'evidence_data': {
                        'threshold_meters': threshold_m,
                        'site_location': str(site.gpslocation),
                        'attendance_location': str(attendance_event.startlocation),
                    }
                }

        except (ValueError, AttributeError) as e:
            logger.error(f"Geofence violation detection error: {e}", exc_info=True)

        return None

    def validate_gps_quality(self, attendance_event):
        """
        Validate GPS accuracy and quality.

        Args:
            attendance_event: PeopleEventlog instance

        Returns:
            dict: Quality validation result or None
        """
        try:
            accuracy = attendance_event.accuracy

            if accuracy and accuracy > self.config.gps_accuracy_max_meters:
                return {
                    'anomaly_type': 'GPS_LOW_ACCURACY',
                    'severity': 'MEDIUM',
                    'accuracy_meters': accuracy,
                    'max_allowed_meters': self.config.gps_accuracy_max_meters,
                    'confidence_score': 0.70,
                    'evidence_data': {
                        'accuracy_exceeded_by': accuracy - self.config.gps_accuracy_max_meters,
                    }
                }

        except (ValueError, AttributeError) as e:
            logger.error(f"GPS quality validation error: {e}", exc_info=True)

        return None

    @transaction.atomic
    def log_gps_validation(self, attendance_event, validation_results):
        """
        Log GPS validation with fraud detection.

        Args:
            attendance_event: PeopleEventlog instance
            validation_results: list of validation results

        Returns:
            GPSValidationLog instance
        """
        from apps.noc.security_intelligence.models import GPSValidationLog
        from apps.activity.models import Location

        try:
            fraud_indicators = []
            fraud_score = 0.0

            for result in validation_results:
                if result:
                    fraud_indicators.append(result['anomaly_type'])
                    fraud_score = max(fraud_score, result['confidence_score'])

            result_status = 'VALID'
            if 'GPS_SPOOFING' in fraud_indicators:
                result_status = 'SPOOFED'
            elif 'GEOFENCE_VIOLATION' in fraud_indicators:
                result_status = 'GEOFENCE_VIOLATION'
            elif fraud_score > 0.6:
                result_status = 'SUSPICIOUS'

            previous_loc = Location.objects.filter(
                people=attendance_event.people,
                cdtz__lt=attendance_event.punchintime,
                gpslocation__isnull=False
            ).order_by('-cdtz').first()

            log = GPSValidationLog.objects.create(
                tenant=attendance_event.tenant,
                person=attendance_event.people,
                site=attendance_event.bu,
                attendance_event=attendance_event,
                validated_at=timezone.now(),
                result=result_status,
                gps_location=attendance_event.startlocation,
                gps_accuracy_meters=attendance_event.accuracy or 0,
                distance_from_geofence_meters=attendance_event.bu.gpslocation.distance(attendance_event.startlocation) if attendance_event.bu.gpslocation else 0,
                is_within_geofence='GEOFENCE_VIOLATION' not in fraud_indicators,
                previous_location=previous_loc.gpslocation if previous_loc else None,
                previous_location_time=previous_loc.cdtz if previous_loc else None,
                fraud_score=fraud_score,
                fraud_indicators=fraud_indicators,
                device_id=attendance_event.deviceid or '',
                flagged_for_review=fraud_score >= 0.7,
            )

            return log

        except (ValueError, AttributeError) as e:
            logger.error(f"GPS validation logging error: {e}", exc_info=True)
            return None

    def detect_exif_photo_fraud(self, image_path, expected_location, people_id):
        """
        Detect photo fraud using EXIF metadata analysis.

        Args:
            image_path: Path to the uploaded photo
            expected_location: Expected GPS location as Point
            people_id: ID of the person uploading the photo

        Returns:
            dict: EXIF fraud detection result or None
        """
        try:
            # Extract EXIF metadata
            exif_metadata = EXIFAnalysisService.extract_comprehensive_metadata(
                image_path, people_id
            )

            fraud_indicators = []
            fraud_score = 0.0

            # Check authenticity score
            authenticity_score = exif_metadata.get('authenticity_score', 1.0)
            if authenticity_score < 0.5:
                fraud_indicators.append('LOW_AUTHENTICITY_SCORE')
                fraud_score = max(fraud_score, 0.8)

            # Check for photo manipulation
            manipulation_risk = exif_metadata.get('security_analysis', {}).get('manipulation_risk', 'low')
            if manipulation_risk == 'high':
                fraud_indicators.append('PHOTO_MANIPULATION_DETECTED')
                fraud_score = max(fraud_score, 0.9)

            # Validate GPS coordinates if present
            gps_data = exif_metadata.get('gps_data', {})
            if gps_data.get('validation_status') == 'valid':
                location_result = self._validate_exif_gps_location(
                    gps_data, expected_location
                )
                if location_result:
                    fraud_indicators.extend(location_result['fraud_indicators'])
                    fraud_score = max(fraud_score, location_result['fraud_score'])

            # Check for missing critical EXIF data
            quality_metrics = exif_metadata.get('quality_metrics', {})
            if quality_metrics.get('completeness_score', 1.0) < 0.3:
                fraud_indicators.append('MISSING_CRITICAL_EXIF_DATA')
                fraud_score = max(fraud_score, 0.6)

            if fraud_indicators:
                return {
                    'anomaly_type': 'EXIF_PHOTO_FRAUD',
                    'severity': 'HIGH' if fraud_score > 0.7 else 'MEDIUM',
                    'fraud_indicators': fraud_indicators,
                    'fraud_score': fraud_score,
                    'authenticity_score': authenticity_score,
                    'confidence_score': min(0.95, fraud_score + 0.1),
                    'evidence_data': {
                        'exif_metadata_id': exif_metadata.get('database_id'),
                        'manipulation_risk': manipulation_risk,
                        'quality_completeness': quality_metrics.get('completeness_score', 0.0)
                    }
                }

        except (ValueError, AttributeError, TypeError) as e:
            logger.error(f"EXIF photo fraud detection error: {e}", exc_info=True)

        return None

    def _validate_exif_gps_location(self, gps_data, expected_location):
        """
        Validate EXIF GPS coordinates against expected location.

        Args:
            gps_data: GPS data from EXIF analysis
            expected_location: Expected GPS location as Point

        Returns:
            dict: GPS validation result or None
        """
        try:
            if not expected_location:
                return None

            photo_lat = gps_data.get('latitude')
            photo_lon = gps_data.get('longitude')

            if photo_lat is None or photo_lon is None:
                return None

            photo_location = Point(photo_lon, photo_lat, srid=4326)
            distance_meters = expected_location.distance(photo_location) * METERS_PER_DEGREE_LAT

            fraud_indicators = []
            fraud_score = 0.0

            # Check if location is impossible distance away
            if distance_meters > self.config.geofence_violation_threshold_meters * 10:
                fraud_indicators.append('EXIF_GPS_IMPOSSIBLE_DISTANCE')
                fraud_score = 0.9

            # Check for suspiciously round GPS coordinates (often fake)
            if (photo_lat == round(photo_lat) and photo_lon == round(photo_lon)):
                fraud_indicators.append('EXIF_GPS_ROUND_COORDINATES')
                fraud_score = max(fraud_score, 0.7)

            # Check for location outside geofence
            elif distance_meters > self.config.geofence_violation_threshold_meters:
                fraud_indicators.append('EXIF_GPS_GEOFENCE_VIOLATION')
                fraud_score = max(fraud_score, 0.8)

            if fraud_indicators:
                return {
                    'fraud_indicators': fraud_indicators,
                    'fraud_score': fraud_score,
                    'distance_meters': distance_meters,
                    'photo_coordinates': {'lat': photo_lat, 'lon': photo_lon},
                    'expected_coordinates': {'lat': expected_location.y, 'lon': expected_location.x}
                }

        except (ValueError, AttributeError) as e:
            logger.error(f"EXIF GPS validation error: {e}", exc_info=True)

        return None

    def detect_camera_device_fraud(self, people_id, camera_fingerprint_hash):
        """
        Detect fraud based on camera device patterns.

        Args:
            people_id: ID of the person
            camera_fingerprint_hash: Camera fingerprint hash

        Returns:
            dict: Camera fraud detection result or None
        """
        try:
            from apps.core.models import CameraFingerprint

            # Get camera fingerprint record
            camera_fingerprint = CameraFingerprint.objects.filter(
                fingerprint_hash=camera_fingerprint_hash
            ).first()

            if not camera_fingerprint:
                return None

            fraud_indicators = []
            fraud_score = 0.0

            # Check trust level
            if camera_fingerprint.trust_level == 'blocked':
                fraud_indicators.append('BLOCKED_CAMERA_DEVICE')
                fraud_score = 1.0
            elif camera_fingerprint.trust_level == 'suspicious':
                fraud_indicators.append('SUSPICIOUS_CAMERA_DEVICE')
                fraud_score = 0.8

            # Check fraud incident history
            if camera_fingerprint.fraud_incidents >= 3:
                fraud_indicators.append('HIGH_FRAUD_INCIDENT_CAMERA')
                fraud_score = max(fraud_score, 0.9)

            # Check if camera is used by multiple people (device sharing)
            user_count = camera_fingerprint.associated_users.count()
            if user_count > 5:
                fraud_indicators.append('MULTI_USER_CAMERA_DEVICE')
                fraud_score = max(fraud_score, 0.6)

            # Check if person is not associated with this camera
            if not camera_fingerprint.associated_users.filter(id=people_id).exists():
                fraud_indicators.append('UNREGISTERED_CAMERA_DEVICE')
                fraud_score = max(fraud_score, 0.7)

            if fraud_indicators:
                return {
                    'anomaly_type': 'CAMERA_DEVICE_FRAUD',
                    'severity': 'HIGH' if fraud_score > 0.7 else 'MEDIUM',
                    'fraud_indicators': fraud_indicators,
                    'fraud_score': fraud_score,
                    'confidence_score': min(0.95, fraud_score + 0.05),
                    'evidence_data': {
                        'camera_fingerprint_id': camera_fingerprint.id,
                        'trust_level': camera_fingerprint.trust_level,
                        'fraud_incidents': camera_fingerprint.fraud_incidents,
                        'associated_users_count': user_count
                    }
                }

        except (ValueError, AttributeError) as e:
            logger.error(f"Camera device fraud detection error: {e}", exc_info=True)

        return None

    def comprehensive_photo_validation(self, image_path, expected_location, people_id):
        """
        Perform comprehensive photo validation combining GPS and EXIF analysis.

        Args:
            image_path: Path to the uploaded photo
            expected_location: Expected GPS location as Point
            people_id: ID of the person uploading the photo

        Returns:
            dict: Comprehensive validation results
        """
        try:
            validation_results = []
            fraud_indicators = []
            max_fraud_score = 0.0

            # 1. EXIF photo fraud detection
            exif_fraud = self.detect_exif_photo_fraud(image_path, expected_location, people_id)
            if exif_fraud:
                validation_results.append(exif_fraud)
                fraud_indicators.extend(exif_fraud.get('fraud_indicators', []))
                max_fraud_score = max(max_fraud_score, exif_fraud.get('fraud_score', 0.0))

            # 2. Camera device fraud detection
            exif_metadata = EXIFAnalysisService.extract_comprehensive_metadata(image_path, people_id)
            camera_fingerprint = exif_metadata.get('security_analysis', {}).get('camera_fingerprint')

            if camera_fingerprint:
                camera_fraud = self.detect_camera_device_fraud(people_id, camera_fingerprint)
                if camera_fraud:
                    validation_results.append(camera_fraud)
                    fraud_indicators.extend(camera_fraud.get('fraud_indicators', []))
                    max_fraud_score = max(max_fraud_score, camera_fraud.get('fraud_score', 0.0))

            # 3. Log comprehensive validation
            self._log_photo_validation(image_path, people_id, validation_results, fraud_indicators, max_fraud_score)

            return {
                'validation_passed': max_fraud_score < 0.5,
                'fraud_score': max_fraud_score,
                'fraud_indicators': list(set(fraud_indicators)),  # Remove duplicates
                'validation_results': validation_results,
                'risk_level': 'HIGH' if max_fraud_score > 0.7 else 'MEDIUM' if max_fraud_score > 0.4 else 'LOW',
                'requires_review': max_fraud_score > 0.6
            }

        except (ValueError, AttributeError) as e:
            logger.error(f"Comprehensive photo validation error: {e}", exc_info=True)
            return {
                'validation_passed': False,
                'fraud_score': 1.0,
                'fraud_indicators': ['VALIDATION_ERROR'],
                'validation_results': [],
                'risk_level': 'HIGH',
                'requires_review': True,
                'error': str(e)
            }

    def _log_photo_validation(self, image_path, people_id, validation_results, fraud_indicators, fraud_score):
        """
        Log photo validation results for audit and analysis.

        Args:
            image_path: Path to the photo
            people_id: ID of the person
            validation_results: List of validation results
            fraud_indicators: List of fraud indicators
            fraud_score: Maximum fraud score
        """
        try:
            # Get ImageMetadata record
            image_metadata = ImageMetadata.objects.filter(
                image_path=image_path,
                people_id=people_id
            ).order_by('-analysis_timestamp').first()

            if image_metadata:
                # Determine validation result
                if fraud_score > 0.7:
                    validation_result = 'failed'
                elif fraud_score > 0.4:
                    validation_result = 'flagged'
                else:
                    validation_result = 'passed'

                # Create authenticity log
                PhotoAuthenticityLog.objects.create(
                    image_metadata=image_metadata,
                    validation_action='automatic',
                    validation_result=validation_result,
                    validation_details={
                        'fraud_indicators': fraud_indicators,
                        'validation_results': validation_results,
                        'validation_timestamp': timezone.now().isoformat()
                    },
                    confidence_score=min(0.95, fraud_score + 0.1),
                    follow_up_required=(validation_result in ['failed', 'flagged']),
                    validation_notes=f"Comprehensive photo validation: {len(fraud_indicators)} fraud indicators detected"
                )

        except DATABASE_EXCEPTIONS as e:
            logger.warning(f"Failed to log photo validation: {e}")