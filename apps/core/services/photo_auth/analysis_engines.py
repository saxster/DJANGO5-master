"""
Photo authenticity analysis engines.

Handles:
- EXIF metadata analysis
- GPS location validation
- Device fingerprint analysis
- Behavioral pattern analysis
- Upload timing analysis

Complies with .claude/rules.md:
- Rule #7: Service methods < 150 lines
- Rule #9: Specific exception handling
- Rule #10: Database query optimization
"""

import logging
from typing import Dict, Any, List
from datetime import datetime, timedelta
from django.contrib.gis.geos import Point
from django.utils import timezone
from apps.core.services.exif_analysis_service import EXIFAnalysisService
from apps.core.models import ImageMetadata, CameraFingerprint
from apps.core.exceptions.patterns import DATABASE_EXCEPTIONS, BUSINESS_LOGIC_EXCEPTIONS

logger = logging.getLogger(__name__)


class AnalysisEngines:
    """Collection of analysis engines for photo authenticity."""

    @classmethod
    def perform_exif_analysis(
        cls,
        image_path: str,
        people_id: int,
        correlation_id: str
    ) -> Dict[str, Any]:
        """Perform comprehensive EXIF metadata analysis."""
        try:
            # Extract EXIF metadata
            exif_metadata = EXIFAnalysisService.extract_comprehensive_metadata(
                image_path, people_id
            )

            # Assess EXIF-based authenticity
            exif_score = exif_metadata.get('authenticity_score', 0.5)
            fraud_indicators = exif_metadata.get('fraud_indicators', [])

            return {
                'validation_type': 'exif_analysis',
                'status': 'completed',
                'authenticity_score': exif_score,
                'fraud_indicators': fraud_indicators,
                'quality_score': exif_metadata.get('quality_metrics', {}).get('completeness_score', 0.5),
                'gps_data_present': bool(exif_metadata.get('gps_data', {}).get('validation_status') == 'valid'),
                'manipulation_risk': exif_metadata.get('security_analysis', {}).get('manipulation_risk', 'low'),
                'evidence': {
                    'exif_metadata_id': exif_metadata.get('database_id'),
                    'camera_make': exif_metadata.get('security_analysis', {}).get('camera_make'),
                    'camera_model': exif_metadata.get('security_analysis', {}).get('camera_model'),
                    'software_signatures': exif_metadata.get('security_analysis', {}).get('software_signatures', [])
                }
            }

        except BUSINESS_LOGIC_EXCEPTIONS as e:
            logger.warning(f"EXIF analysis failed: {e}", exc_info=True)
            return {
                'validation_type': 'exif_analysis',
                'status': 'error',
                'authenticity_score': 0.1,  # Low score for failed analysis
                'fraud_indicators': ['EXIF_ANALYSIS_FAILED'],
                'error': str(e)
            }

    @classmethod
    def perform_location_validation(
        cls,
        image_path: str,
        expected_location: Point,
        people_id: int,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Perform GPS location validation."""
        try:
            # Use LocationFraudDetector for comprehensive validation
            from apps.noc.security_intelligence.models import SecurityAnomalyConfig

            # Get default config or create mock for validation
            config = SecurityAnomalyConfig.objects.filter(is_active=True).first()
            if not config:
                # Create mock config for validation
                class MockConfig:
                    def __init__(self):
                        self.geofence_violation_threshold_meters = 100
                        self.max_travel_speed_kmh = 200
                        self.gps_accuracy_max_meters = 50

                config = MockConfig()

            from apps.noc.security_intelligence.services.location_fraud_detector import LocationFraudDetector
            fraud_detector = LocationFraudDetector(config)
            validation_result = fraud_detector.comprehensive_photo_validation(
                image_path, expected_location, people_id
            )

            return {
                'validation_type': 'location_validation',
                'status': 'completed',
                'validation_passed': validation_result.get('validation_passed', False),
                'authenticity_score': 1.0 - validation_result.get('fraud_score', 0.5),
                'fraud_indicators': validation_result.get('fraud_indicators', []),
                'distance_accuracy': validation_result.get('distance_meters'),
                'risk_level': validation_result.get('risk_level', 'unknown'),
                'evidence': {
                    'validation_results': validation_result.get('validation_results', []),
                    'requires_review': validation_result.get('requires_review', False)
                }
            }

        except (DATABASE_EXCEPTIONS, BUSINESS_LOGIC_EXCEPTIONS) as e:
            logger.warning(f"Location validation failed: {e}", exc_info=True)
            return {
                'validation_type': 'location_validation',
                'status': 'error',
                'authenticity_score': 0.5,  # Neutral score for failed validation
                'fraud_indicators': ['LOCATION_VALIDATION_FAILED'],
                'error': str(e)
            }

    @classmethod
    def perform_device_analysis(
        cls,
        exif_results: Dict[str, Any],
        people_id: int,
        correlation_id: str
    ) -> Dict[str, Any]:
        """Perform camera device fingerprint analysis."""
        try:
            camera_fingerprint = exif_results.get('evidence', {}).get('camera_fingerprint')
            if not camera_fingerprint:
                return {
                    'validation_type': 'device_analysis',
                    'status': 'skipped',
                    'authenticity_score': 0.7,  # Neutral score when no device data
                    'fraud_indicators': ['NO_CAMERA_FINGERPRINT'],
                    'reason': 'No camera fingerprint data available'
                }

            # Check camera fingerprint against database
            fingerprint_record = CameraFingerprint.objects.filter(
                fingerprint_hash=camera_fingerprint
            ).select_related().prefetch_related('associated_users').first()

            if not fingerprint_record:
                return {
                    'validation_type': 'device_analysis',
                    'status': 'new_device',
                    'authenticity_score': 0.6,  # Lower score for unknown devices
                    'fraud_indicators': ['UNKNOWN_CAMERA_DEVICE'],
                    'device_risk_level': 'medium'
                }

            # Analyze device trustworthiness
            device_score = cls.calculate_device_trust_score(fingerprint_record, people_id)

            fraud_indicators = []
            if fingerprint_record.trust_level == 'blocked':
                fraud_indicators.append('BLOCKED_DEVICE')
            elif fingerprint_record.trust_level == 'suspicious':
                fraud_indicators.append('SUSPICIOUS_DEVICE')

            if fingerprint_record.fraud_incidents > 2:
                fraud_indicators.append('HIGH_FRAUD_DEVICE')

            return {
                'validation_type': 'device_analysis',
                'status': 'completed',
                'authenticity_score': device_score,
                'fraud_indicators': fraud_indicators,
                'device_trust_level': fingerprint_record.trust_level,
                'fraud_incident_count': fingerprint_record.fraud_incidents,
                'evidence': {
                    'camera_fingerprint_id': fingerprint_record.id,
                    'first_seen': fingerprint_record.first_seen.isoformat(),
                    'usage_count': fingerprint_record.usage_count,
                    'associated_users_count': fingerprint_record.associated_users.count()
                }
            }

        except DATABASE_EXCEPTIONS as e:
            logger.warning(f"Device analysis failed: {e}", exc_info=True)
            return {
                'validation_type': 'device_analysis',
                'status': 'error',
                'authenticity_score': 0.5,
                'fraud_indicators': ['DEVICE_ANALYSIS_FAILED'],
                'error': str(e)
            }

    @classmethod
    def calculate_device_trust_score(cls, fingerprint_record: CameraFingerprint, people_id: int) -> float:
        """Calculate device trust score based on historical data."""
        try:
            base_score = 1.0

            # Trust level impact
            trust_multipliers = {
                'trusted': 1.0,
                'neutral': 0.8,
                'suspicious': 0.4,
                'blocked': 0.1
            }
            base_score *= trust_multipliers.get(fingerprint_record.trust_level, 0.5)

            # Fraud incident impact
            if fingerprint_record.fraud_incidents > 0:
                fraud_penalty = min(0.5, fingerprint_record.fraud_incidents * 0.15)
                base_score -= fraud_penalty

            # User association impact
            if fingerprint_record.associated_users.filter(id=people_id).exists():
                base_score += 0.1  # Bonus for registered user
            else:
                base_score -= 0.2  # Penalty for unregistered user

            # Usage pattern impact
            usage_bonus = min(0.1, fingerprint_record.usage_count * 0.001)
            base_score += usage_bonus

            return max(0.0, min(1.0, base_score))

        except (DATABASE_EXCEPTIONS, BUSINESS_LOGIC_EXCEPTIONS) as e:
            logger.warning(f"Device trust score calculation failed: {e}", exc_info=True)
            return 0.5

    @classmethod
    def perform_behavioral_analysis(
        cls,
        people_id: int,
        upload_type: str,
        correlation_id: str
    ) -> Dict[str, Any]:
        """Perform behavioral pattern analysis."""
        try:
            # Analyze recent photo upload patterns
            recent_uploads = ImageMetadata.objects.filter(
                people_id=people_id,
                analysis_timestamp__gte=timezone.now() - timedelta(days=30)
            ).select_related().order_by('-analysis_timestamp')[:50]

            if recent_uploads.count() < 5:
                return {
                    'validation_type': 'behavioral_analysis',
                    'status': 'insufficient_data',
                    'authenticity_score': 0.7,
                    'fraud_indicators': ['INSUFFICIENT_BEHAVIORAL_DATA'],
                    'reason': 'Not enough historical data for behavioral analysis'
                }

            # Analyze patterns
            behavioral_score = cls.analyze_upload_patterns(recent_uploads, upload_type)

            fraud_indicators = []
            if behavioral_score < 0.4:
                fraud_indicators.append('ANOMALOUS_UPLOAD_PATTERN')

            # Check for rapid successive uploads (potential bulk fake uploads)
            rapid_uploads = recent_uploads.filter(
                analysis_timestamp__gte=timezone.now() - timedelta(hours=1)
            ).count()

            if rapid_uploads > 10:
                fraud_indicators.append('RAPID_BULK_UPLOADS')
                behavioral_score *= 0.7

            return {
                'validation_type': 'behavioral_analysis',
                'status': 'completed',
                'authenticity_score': behavioral_score,
                'fraud_indicators': fraud_indicators,
                'upload_frequency_score': behavioral_score,
                'evidence': {
                    'recent_uploads_count': recent_uploads.count(),
                    'rapid_uploads_count': rapid_uploads,
                    'analysis_period_days': 30
                }
            }

        except DATABASE_EXCEPTIONS as e:
            logger.warning(f"Behavioral analysis failed: {e}", exc_info=True)
            return {
                'validation_type': 'behavioral_analysis',
                'status': 'error',
                'authenticity_score': 0.5,
                'fraud_indicators': ['BEHAVIORAL_ANALYSIS_FAILED'],
                'error': str(e)
            }

    @classmethod
    def analyze_upload_patterns(cls, recent_uploads, upload_type: str) -> float:
        """Analyze upload patterns for behavioral anomalies."""
        try:
            if not recent_uploads:
                return 0.5

            # Calculate authenticity score statistics
            authenticity_scores = [upload.authenticity_score for upload in recent_uploads]
            avg_authenticity = sum(authenticity_scores) / len(authenticity_scores)

            # Check for consistency in upload quality
            quality_variance = cls.calculate_variance(authenticity_scores)

            # Behavioral score based on historical authenticity
            behavioral_score = avg_authenticity

            # Penalize high variance (inconsistent quality suggests manipulation)
            if quality_variance > 0.2:
                behavioral_score *= 0.8

            # Check upload timing patterns
            upload_times = [upload.analysis_timestamp for upload in recent_uploads]
            timing_score = cls.analyze_upload_timing(upload_times)
            behavioral_score = (behavioral_score + timing_score) / 2

            return max(0.0, min(1.0, behavioral_score))

        except BUSINESS_LOGIC_EXCEPTIONS as e:
            logger.warning(f"Upload pattern analysis failed: {e}", exc_info=True)
            return 0.5

    @classmethod
    def calculate_variance(cls, values: List[float]) -> float:
        """Calculate variance of a list of values."""
        if len(values) < 2:
            return 0.0

        mean = sum(values) / len(values)
        variance = sum((x - mean) ** 2 for x in values) / len(values)
        return variance ** 0.5  # Return standard deviation

    @classmethod
    def analyze_upload_timing(cls, upload_times: List[datetime]) -> float:
        """Analyze upload timing patterns for anomalies."""
        try:
            if len(upload_times) < 2:
                return 0.8

            # Check for suspiciously regular intervals
            intervals = []
            for i in range(1, len(upload_times)):
                interval = (upload_times[i-1] - upload_times[i]).total_seconds()
                intervals.append(abs(interval))

            if not intervals:
                return 0.8

            # Check for overly regular patterns (potential automation)
            avg_interval = sum(intervals) / len(intervals)
            interval_variance = cls.calculate_variance(intervals)

            # Low variance with short intervals suggests automation
            if interval_variance < avg_interval * 0.1 and avg_interval < 300:  # 5 minutes
                return 0.3  # Suspicious automation pattern

            # Normal human variation
            return 0.8

        except BUSINESS_LOGIC_EXCEPTIONS as e:
            logger.warning(f"Upload timing analysis failed: {e}", exc_info=True)
            return 0.7
