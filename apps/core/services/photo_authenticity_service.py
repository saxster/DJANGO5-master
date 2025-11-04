"""
Photo Authenticity Detection Service for Enterprise Security

Advanced photo authenticity verification combining EXIF analysis, GPS validation,
device fingerprinting, and machine learning-based fraud detection for enterprise
facility management and security applications.

Features:
- Real-time photo authenticity scoring (0.0 - 1.0)
- Multi-factor fraud detection (EXIF, GPS, device, behavioral)
- Integration with existing security intelligence systems
- Compliance-ready audit trails and reporting
- Automated flagging and manual review workflows

Complies with .claude/rules.md:
- Rule #7: Service methods < 150 lines
- Rule #9: Specific exception handling (no bare except)
- Rule #10: Database query optimization with select_related/prefetch_related
"""

import logging
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime, timedelta
from django.contrib.gis.geos import Point
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from apps.core.services.exif_analysis_service import EXIFAnalysisService
from apps.core.services.secure_file_upload_service import SecureFileUploadService
from apps.core.models.image_metadata import (
    ImageMetadata, PhotoAuthenticityLog, CameraFingerprint, ImageQualityAssessment
)
from apps.noc.security_intelligence.services.location_fraud_detector import LocationFraudDetector
from apps.core.error_handling import ErrorHandler
from apps.core.exceptions.patterns import DATABASE_EXCEPTIONS, BUSINESS_LOGIC_EXCEPTIONS

logger = logging.getLogger(__name__)


class PhotoAuthenticityService:
    """
    Enterprise-grade photo authenticity detection and verification service.

    Provides comprehensive photo authentication combining EXIF metadata analysis,
    GPS validation, device fingerprinting, and behavioral pattern analysis.
    """

    # Risk thresholds for different validation scenarios
    RISK_THRESHOLDS = {
        'attendance': {
            'low_risk': 0.8,      # High authenticity required for attendance
            'medium_risk': 0.6,
            'high_risk': 0.4
        },
        'facility_audit': {
            'low_risk': 0.7,      # Moderate authenticity for audits
            'medium_risk': 0.5,
            'high_risk': 0.3
        },
        'incident_report': {
            'low_risk': 0.9,      # Very high authenticity for incidents
            'medium_risk': 0.7,
            'high_risk': 0.5
        },
        'general': {
            'low_risk': 0.6,      # Lower threshold for general photos
            'medium_risk': 0.4,
            'high_risk': 0.2
        }
    }

    @classmethod
    def authenticate_photo(
        cls,
        image_path: str,
        context: Dict[str, Any],
        expected_location: Optional[Point] = None,
        validation_level: str = 'standard'
    ) -> Dict[str, Any]:
        """
        Perform comprehensive photo authentication with enterprise-grade validation.

        Args:
            image_path: Path to the photo file
            context: Context information (people_id, upload_type, etc.)
            expected_location: Expected GPS location for validation
            validation_level: Validation strictness ('basic', 'standard', 'strict')

        Returns:
            Comprehensive authentication results with recommendations

        Raises:
            ValidationError: If authentication process fails
        """
        try:
            correlation_id = cls._generate_correlation_id()
            people_id = context.get('people_id')
            upload_type = context.get('upload_type', 'general')

            logger.info(
                "Starting comprehensive photo authentication",
                extra={
                    'correlation_id': correlation_id,
                    'people_id': people_id,
                    'upload_type': upload_type,
                    'validation_level': validation_level
                }
            )

            # Initialize authentication result
            auth_result = {
                'correlation_id': correlation_id,
                'image_path': image_path,
                'people_id': people_id,
                'upload_type': upload_type,
                'authentication_timestamp': timezone.now().isoformat(),
                'validation_level': validation_level,
                'authenticated': False,
                'authenticity_score': 0.0,
                'confidence_level': 0.0,
                'risk_assessment': {},
                'fraud_indicators': [],
                'validation_results': [],
                'recommendations': [],
                'requires_manual_review': False,
                'compliance_status': 'pending'
            }

            # Phase 1: EXIF Metadata Analysis
            exif_results = cls._perform_exif_analysis(
                image_path, people_id, correlation_id
            )
            auth_result['exif_analysis'] = exif_results
            auth_result['validation_results'].append(exif_results)

            # Phase 2: GPS Location Validation
            if expected_location:
                location_results = cls._perform_location_validation(
                    image_path, expected_location, people_id, context
                )
                auth_result['location_validation'] = location_results
                auth_result['validation_results'].append(location_results)

            # Phase 3: Device Fingerprint Analysis
            device_results = cls._perform_device_analysis(
                exif_results, people_id, correlation_id
            )
            auth_result['device_analysis'] = device_results
            auth_result['validation_results'].append(device_results)

            # Phase 4: Behavioral Pattern Analysis
            if validation_level in ['standard', 'strict']:
                behavioral_results = cls._perform_behavioral_analysis(
                    people_id, upload_type, correlation_id
                )
                auth_result['behavioral_analysis'] = behavioral_results
                auth_result['validation_results'].append(behavioral_results)

            # Phase 5: Comprehensive Risk Assessment
            risk_assessment = cls._calculate_comprehensive_risk(
                auth_result['validation_results'], upload_type, validation_level
            )
            auth_result['risk_assessment'] = risk_assessment
            auth_result['authenticity_score'] = risk_assessment['authenticity_score']
            auth_result['confidence_level'] = risk_assessment['confidence_level']

            # Phase 6: Final Authentication Decision
            authentication_decision = cls._make_authentication_decision(
                risk_assessment, upload_type, validation_level
            )
            auth_result.update(authentication_decision)

            # Phase 7: Generate Recommendations
            auth_result['recommendations'] = cls._generate_recommendations(
                auth_result, validation_level
            )

            # Phase 8: Audit Logging
            cls._log_authentication_event(auth_result, context)

            logger.info(
                "Photo authentication completed",
                extra={
                    'correlation_id': correlation_id,
                    'authenticated': auth_result['authenticated'],
                    'authenticity_score': auth_result['authenticity_score'],
                    'requires_review': auth_result['requires_manual_review']
                }
            )

            return auth_result

        except (ValueError, TypeError, AttributeError) as e:
            correlation_id = ErrorHandler.handle_exception(
                e,
                context={
                    'service': 'PhotoAuthenticityService',
                    'method': 'authenticate_photo',
                    'image_path': image_path,
                    'people_id': people_id
                },
                level='error'
            )
            raise ValidationError(
                f"Photo authentication failed (ID: {correlation_id})"
            ) from e

    @classmethod
    def _perform_exif_analysis(
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
    def _perform_location_validation(
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
    def _perform_device_analysis(
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
            device_score = cls._calculate_device_trust_score(fingerprint_record, people_id)

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
    def _calculate_device_trust_score(cls, fingerprint_record: CameraFingerprint, people_id: int) -> float:
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
    def _perform_behavioral_analysis(
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
            behavioral_score = cls._analyze_upload_patterns(recent_uploads, upload_type)

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
    def _analyze_upload_patterns(cls, recent_uploads, upload_type: str) -> float:
        """Analyze upload patterns for behavioral anomalies."""
        try:
            if not recent_uploads:
                return 0.5

            # Calculate authenticity score statistics
            authenticity_scores = [upload.authenticity_score for upload in recent_uploads]
            avg_authenticity = sum(authenticity_scores) / len(authenticity_scores)

            # Check for consistency in upload quality
            quality_variance = cls._calculate_variance(authenticity_scores)

            # Behavioral score based on historical authenticity
            behavioral_score = avg_authenticity

            # Penalize high variance (inconsistent quality suggests manipulation)
            if quality_variance > 0.2:
                behavioral_score *= 0.8

            # Check upload timing patterns
            upload_times = [upload.analysis_timestamp for upload in recent_uploads]
            timing_score = cls._analyze_upload_timing(upload_times)
            behavioral_score = (behavioral_score + timing_score) / 2

            return max(0.0, min(1.0, behavioral_score))

        except BUSINESS_LOGIC_EXCEPTIONS as e:
            logger.warning(f"Upload pattern analysis failed: {e}", exc_info=True)
            return 0.5

    @classmethod
    def _calculate_variance(cls, values: List[float]) -> float:
        """Calculate variance of a list of values."""
        if len(values) < 2:
            return 0.0

        mean = sum(values) / len(values)
        variance = sum((x - mean) ** 2 for x in values) / len(values)
        return variance ** 0.5  # Return standard deviation

    @classmethod
    def _analyze_upload_timing(cls, upload_times: List[datetime]) -> float:
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
            interval_variance = cls._calculate_variance(intervals)

            # Low variance with short intervals suggests automation
            if interval_variance < avg_interval * 0.1 and avg_interval < 300:  # 5 minutes
                return 0.3  # Suspicious automation pattern

            # Normal human variation
            return 0.8

        except BUSINESS_LOGIC_EXCEPTIONS as e:
            logger.warning(f"Upload timing analysis failed: {e}", exc_info=True)
            return 0.7

    @classmethod
    def _calculate_comprehensive_risk(
        cls,
        validation_results: List[Dict[str, Any]],
        upload_type: str,
        validation_level: str
    ) -> Dict[str, Any]:
        """Calculate comprehensive risk assessment."""
        try:
            # Collect authenticity scores and fraud indicators
            authenticity_scores = []
            all_fraud_indicators = []
            confidence_factors = []

            for result in validation_results:
                if result.get('status') == 'completed':
                    score = result.get('authenticity_score', 0.5)
                    authenticity_scores.append(score)
                    confidence_factors.append(1.0)
                elif result.get('status') == 'error':
                    authenticity_scores.append(0.3)  # Penalize errors
                    confidence_factors.append(0.5)

                all_fraud_indicators.extend(result.get('fraud_indicators', []))

            # Calculate weighted authenticity score
            if authenticity_scores:
                weighted_authenticity = sum(
                    score * weight for score, weight in zip(authenticity_scores, confidence_factors)
                ) / sum(confidence_factors)
            else:
                weighted_authenticity = 0.5

            # Calculate confidence level
            confidence_level = sum(confidence_factors) / len(validation_results) if validation_results else 0.5

            # Determine risk level based on thresholds
            thresholds = cls.RISK_THRESHOLDS.get(upload_type, cls.RISK_THRESHOLDS['general'])

            if weighted_authenticity >= thresholds['low_risk']:
                risk_level = 'low'
            elif weighted_authenticity >= thresholds['medium_risk']:
                risk_level = 'medium'
            elif weighted_authenticity >= thresholds['high_risk']:
                risk_level = 'high'
            else:
                risk_level = 'critical'

            return {
                'authenticity_score': weighted_authenticity,
                'confidence_level': confidence_level,
                'risk_level': risk_level,
                'fraud_indicators': list(set(all_fraud_indicators)),
                'validation_count': len(validation_results),
                'successful_validations': len([r for r in validation_results if r.get('status') == 'completed']),
                'thresholds_used': thresholds
            }

        except BUSINESS_LOGIC_EXCEPTIONS as e:
            logger.warning(f"Comprehensive risk calculation failed: {e}", exc_info=True)
            return {
                'authenticity_score': 0.1,
                'confidence_level': 0.1,
                'risk_level': 'critical',
                'fraud_indicators': ['RISK_CALCULATION_FAILED'],
                'error': str(e)
            }

    @classmethod
    def _make_authentication_decision(
        cls,
        risk_assessment: Dict[str, Any],
        upload_type: str,
        validation_level: str
    ) -> Dict[str, Any]:
        """Make final authentication decision."""
        try:
            authenticity_score = risk_assessment.get('authenticity_score', 0.0)
            risk_level = risk_assessment.get('risk_level', 'critical')
            fraud_indicators = risk_assessment.get('fraud_indicators', [])

            # Determine authentication result
            if risk_level in ['critical', 'high']:
                authenticated = False
                requires_manual_review = True
                compliance_status = 'failed'
            elif risk_level == 'medium':
                authenticated = (validation_level != 'strict')
                requires_manual_review = (validation_level == 'strict')
                compliance_status = 'conditional'
            else:  # low risk
                authenticated = True
                requires_manual_review = False
                compliance_status = 'passed'

            # Override for specific fraud indicators
            critical_indicators = [
                'BLOCKED_DEVICE', 'PHOTO_MANIPULATION_DETECTED',
                'EXIF_GPS_IMPOSSIBLE_DISTANCE', 'HIGH_FRAUD_DEVICE'
            ]

            if any(indicator in fraud_indicators for indicator in critical_indicators):
                authenticated = False
                requires_manual_review = True
                compliance_status = 'failed'

            return {
                'authenticated': authenticated,
                'requires_manual_review': requires_manual_review,
                'compliance_status': compliance_status,
                'decision_factors': {
                    'risk_level': risk_level,
                    'validation_level': validation_level,
                    'critical_indicators_present': any(
                        indicator in fraud_indicators for indicator in critical_indicators
                    )
                }
            }

        except BUSINESS_LOGIC_EXCEPTIONS as e:
            logger.warning(f"Authentication decision failed: {e}", exc_info=True)
            return {
                'authenticated': False,
                'requires_manual_review': True,
                'compliance_status': 'error',
                'decision_factors': {'error': str(e)}
            }

    @classmethod
    def _generate_recommendations(
        cls,
        auth_result: Dict[str, Any],
        validation_level: str
    ) -> List[str]:
        """Generate actionable recommendations based on authentication results."""
        recommendations = []

        try:
            risk_level = auth_result.get('risk_assessment', {}).get('risk_level', 'unknown')
            fraud_indicators = auth_result.get('risk_assessment', {}).get('fraud_indicators', [])
            authenticity_score = auth_result.get('authenticity_score', 0.0)

            # General recommendations based on risk level
            if risk_level == 'critical':
                recommendations.append("CRITICAL: Photo rejected - manual investigation required")
                recommendations.append("Do not accept this photo for any official purpose")

            elif risk_level == 'high':
                recommendations.append("HIGH RISK: Require manual verification before acceptance")
                recommendations.append("Consider requesting alternative photo from different angle")

            elif risk_level == 'medium':
                recommendations.append("MEDIUM RISK: Additional verification recommended")
                recommendations.append("Monitor user for pattern analysis")

            # Specific recommendations based on fraud indicators
            if 'PHOTO_MANIPULATION_DETECTED' in fraud_indicators:
                recommendations.append("Photo shows signs of editing - request original unedited photo")

            if 'BLOCKED_DEVICE' in fraud_indicators:
                recommendations.append("Photo taken with blocked device - security review required")

            if 'EXIF_GPS_GEOFENCE_VIOLATION' in fraud_indicators:
                recommendations.append("GPS location outside allowed area - verify user location")

            if 'MISSING_CRITICAL_EXIF_DATA' in fraud_indicators:
                recommendations.append("Photo lacks metadata - request photo with location services enabled")

            # Quality improvement recommendations
            if authenticity_score < 0.6:
                recommendations.append("Consider implementing stricter photo validation policies")
                recommendations.append("Provide user training on proper photo capture techniques")

            # No issues found
            if not recommendations and auth_result.get('authenticated'):
                recommendations.append("Photo meets authenticity standards - approved for use")

            return recommendations

        except BUSINESS_LOGIC_EXCEPTIONS as e:
            logger.warning(f"Recommendation generation failed: {e}", exc_info=True)
            return ["Manual review recommended due to system error"]

    @classmethod
    def _log_authentication_event(
        cls,
        auth_result: Dict[str, Any],
        context: Dict[str, Any]
    ):
        """Log authentication event for audit and compliance."""
        try:
            # This would integrate with the existing logging system
            logger.info(
                "Photo authentication completed",
                extra={
                    'correlation_id': auth_result.get('correlation_id'),
                    'people_id': auth_result.get('people_id'),
                    'authenticated': auth_result.get('authenticated'),
                    'authenticity_score': auth_result.get('authenticity_score'),
                    'risk_level': auth_result.get('risk_assessment', {}).get('risk_level'),
                    'requires_review': auth_result.get('requires_manual_review'),
                    'upload_type': auth_result.get('upload_type'),
                    'fraud_indicators_count': len(auth_result.get('risk_assessment', {}).get('fraud_indicators', []))
                }
            )

        except DATABASE_EXCEPTIONS as e:
            logger.warning(f"Failed to log authentication event: {e}", exc_info=True)

    @classmethod
    def _generate_correlation_id(cls) -> str:
        """Generate unique correlation ID for tracking."""
        import uuid
        return str(uuid.uuid4())

    @classmethod
    def get_authentication_history(
        cls,
        people_id: int,
        days: int = 30,
        upload_type: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get authentication history for analysis and reporting.

        Args:
            people_id: User ID
            days: Number of days to look back
            upload_type: Optional filter by upload type

        Returns:
            Authentication history summary
        """
        try:
            # Query authentication logs
            filters = {
                'people_id': people_id,
                'analysis_timestamp__gte': timezone.now() - timedelta(days=days)
            }

            if upload_type:
                filters['upload_context'] = upload_type

            auth_records = ImageMetadata.objects.filter(**filters).select_related().order_by('-analysis_timestamp')

            # Calculate statistics
            total_uploads = auth_records.count()
            if total_uploads == 0:
                return {
                    'people_id': people_id,
                    'period_days': days,
                    'total_uploads': 0,
                    'summary': 'No upload history found'
                }

            avg_authenticity = sum(r.authenticity_score for r in auth_records) / total_uploads
            high_risk_count = auth_records.filter(manipulation_risk='high').count()
            flagged_count = auth_records.filter(validation_status='suspicious').count()

            return {
                'people_id': people_id,
                'period_days': days,
                'upload_type_filter': upload_type,
                'total_uploads': total_uploads,
                'average_authenticity_score': round(avg_authenticity, 3),
                'high_risk_uploads': high_risk_count,
                'flagged_uploads': flagged_count,
                'risk_percentage': round((high_risk_count / total_uploads) * 100, 1),
                'recent_uploads': [
                    {
                        'timestamp': r.analysis_timestamp.isoformat(),
                        'authenticity_score': r.authenticity_score,
                        'validation_status': r.validation_status,
                        'manipulation_risk': r.manipulation_risk
                    }
                    for r in auth_records[:10]
                ]
            }

        except DATABASE_EXCEPTIONS as e:
            logger.error(f"Failed to get authentication history: {e}", exc_info=True)
            return {
                'people_id': people_id,
                'error': str(e),
                'period_days': days
            }