"""
Photo Authentication Service using EXIF Metadata (Sprint 5.3)

Integrates EXIF metadata analysis with biometric verification to detect:
- Photo manipulation (editing software detection)
- GPS spoofing (round numbers, inconsistencies)
- Camera fingerprinting (device tracking)
- Timestamp validation
- Photo authenticity scoring

Leverages existing EXIFAnalysisService from apps.core.services.

Author: Development Team
Date: October 2025
Status: Production-ready integration
"""

import logging
from typing import Dict, Any
from pathlib import Path

logger = logging.getLogger(__name__)

# Import existing EXIF service
try:
    from apps.core.services.exif_analysis_service import EXIFAnalysisService
    from apps.core.services.photo_authenticity_service import PhotoAuthenticityService
    EXIF_SERVICE_AVAILABLE = True
    logger.info("EXIF services available for photo authentication")
except ImportError:
    EXIF_SERVICE_AVAILABLE = False
    logger.warning("EXIF services not available - photo authentication limited")


class BiometricPhotoAuthenticationService:
    """
    Service for authenticating biometric photos using EXIF metadata.

    Integrates EXIF analysis into biometric verification workflow to
    detect manipulated or fraudulent photos.
    """

    def __init__(self):
        """Initialize photo authentication service."""
        if EXIF_SERVICE_AVAILABLE:
            self.exif_service = EXIFAnalysisService()
            self.authenticity_service = PhotoAuthenticityService()
        else:
            self.exif_service = None
            self.authenticity_service = None

        # Authentication thresholds
        self.min_authenticity_score = 0.7  # Attendance context (strict)
        self.fraud_risk_threshold = 0.6

    def authenticate_biometric_photo(
        self,
        image_path: str,
        context: str = 'biometric_verification'
    ) -> Dict[str, Any]:
        """
        Authenticate a biometric photo using EXIF metadata.

        Args:
            image_path: Path to the image file
            context: Verification context (biometric_verification, enrollment, etc.)

        Returns:
            Dictionary containing:
                - authenticated: Boolean indicating if photo is authentic
                - authenticity_score: Score 0.0-1.0 (higher is better)
                - fraud_risk: Risk score 0.0-1.0 (higher is worse)
                - fraud_indicators: List of fraud indicators found
                - gps_data: Extracted GPS coordinates (if available)
                - camera_fingerprint: Camera device identifier
                - manipulation_detected: Boolean
                - recommendations: List of recommendations
        """
        try:
            if not EXIF_SERVICE_AVAILABLE:
                # Fallback when services unavailable
                return self._authenticate_fallback(image_path)

            if not Path(image_path).exists():
                return {
                    'authenticated': False,
                    'authenticity_score': 0.0,
                    'fraud_risk': 1.0,
                    'fraud_indicators': ['FILE_NOT_FOUND']
                }

            # Extract EXIF metadata
            exif_data = self.exif_service.extract_comprehensive_exif(image_path)

            # Analyze authenticity
            authenticity_result = self.authenticity_service.assess_photo_authenticity(
                image_path=image_path,
                exif_data=exif_data,
                context=context
            )

            # Extract key information
            gps_data = exif_data.get('gps_data', {})
            camera_info = exif_data.get('camera_info', {})
            manipulation_analysis = exif_data.get('manipulation_analysis', {})

            # Generate camera fingerprint
            camera_fingerprint = self._generate_camera_fingerprint(camera_info)

            # Check for fraud indicators
            fraud_indicators = []

            if manipulation_analysis.get('editing_software_detected'):
                fraud_indicators.append('PHOTO_EDITED')

            if manipulation_analysis.get('timestamp_inconsistency'):
                fraud_indicators.append('TIMESTAMP_INCONSISTENCY')

            if gps_data.get('spoofing_indicators'):
                fraud_indicators.extend(gps_data['spoofing_indicators'])

            # Calculate fraud risk
            authenticity_score = authenticity_result.get('authenticity_score', 0.5)
            fraud_risk = 1.0 - authenticity_score

            # Authentication decision
            authenticated = (
                authenticity_score >= self.min_authenticity_score and
                fraud_risk < self.fraud_risk_threshold and
                len(fraud_indicators) == 0
            )

            # Generate recommendations
            recommendations = []
            if not authenticated:
                if authenticity_score < self.min_authenticity_score:
                    recommendations.append(f"Authenticity score too low: {authenticity_score:.2f}")
                if fraud_indicators:
                    recommendations.append(f"Fraud indicators found: {', '.join(fraud_indicators)}")
                recommendations.append("Use original unedited photo from camera")

            return {
                'authenticated': authenticated,
                'authenticity_score': float(authenticity_score),
                'fraud_risk': float(fraud_risk),
                'fraud_indicators': fraud_indicators,
                'gps_data': gps_data,
                'camera_fingerprint': camera_fingerprint,
                'manipulation_detected': manipulation_analysis.get('editing_software_detected', False),
                'recommendations': recommendations,
                'exif_completeness': exif_data.get('completeness_score', 0.0)
            }

        except Exception as e:
            logger.error(f"Error authenticating biometric photo: {e}")
            return {
                'authenticated': False,
                'authenticity_score': 0.0,
                'fraud_risk': 1.0,
                'error': str(e),
                'fraud_indicators': ['AUTHENTICATION_ERROR']
            }

    def _generate_camera_fingerprint(self, camera_info: Dict[str, Any]) -> str:
        """
        Generate camera device fingerprint from EXIF data.

        Args:
            camera_info: Camera information from EXIF

        Returns:
            Camera fingerprint (hash)
        """
        try:
            import hashlib

            # Combine camera make, model, and serial
            fingerprint_data = (
                f"{camera_info.get('make', '')}"
                f"{camera_info.get('model', '')}"
                f"{camera_info.get('serial_number', '')}"
            )

            if fingerprint_data:
                return hashlib.sha256(fingerprint_data.encode()).hexdigest()[:16]
            else:
                return "UNKNOWN"

        except Exception as e:
            logger.warning(f"Error generating camera fingerprint: {e}")
            return "ERROR"

    def _authenticate_fallback(self, image_path: str) -> Dict[str, Any]:
        """
        Fallback authentication when EXIF services unavailable.

        Args:
            image_path: Path to the image file

        Returns:
            Safe default authentication result
        """
        logger.warning("Using fallback photo authentication (EXIF services unavailable)")
        return {
            'authenticated': True,  # Fail open
            'authenticity_score': 0.5,
            'fraud_risk': 0.5,
            'fraud_indicators': [],
            'fallback': True,
            'note': 'EXIF authentication unavailable'
        }

    def validate_gps_coordinates(
        self,
        image_path: str,
        expected_location: Dict[str, float] = None,
        max_distance_km: float = 1.0
    ) -> Dict[str, Any]:
        """
        Validate GPS coordinates from EXIF against expected location.

        Args:
            image_path: Path to the image file
            expected_location: Expected GPS coordinates {'latitude': x, 'longitude': y}
            max_distance_km: Maximum allowed distance in kilometers

        Returns:
            Dictionary with GPS validation result
        """
        try:
            if not EXIF_SERVICE_AVAILABLE:
                return {'valid': True, 'fallback': True}

            # Extract EXIF
            exif_data = self.exif_service.extract_comprehensive_exif(image_path)
            gps_data = exif_data.get('gps_data', {})

            if not gps_data.get('latitude') or not gps_data.get('longitude'):
                return {
                    'valid': False,
                    'reason': 'No GPS coordinates in EXIF'
                }

            # Check for spoofing
            if gps_data.get('spoofing_indicators'):
                return {
                    'valid': False,
                    'reason': 'GPS spoofing detected',
                    'indicators': gps_data['spoofing_indicators']
                }

            # Validate against expected location if provided
            if expected_location:
                from apps.attendance.services.geospatial_service import GeospatialService
                geo_service = GeospatialService()

                distance = geo_service.haversine_distance(
                    gps_data['latitude'],
                    gps_data['longitude'],
                    expected_location['latitude'],
                    expected_location['longitude']
                )

                if distance > max_distance_km:
                    return {
                        'valid': False,
                        'reason': f'GPS distance too far: {distance:.2f} km',
                        'distance_km': distance
                    }

            return {
                'valid': True,
                'gps': {
                    'latitude': gps_data['latitude'],
                    'longitude': gps_data['longitude']
                },
                'authenticity_score': gps_data.get('authenticity_score', 1.0)
            }

        except Exception as e:
            logger.error(f"Error validating GPS coordinates: {e}")
            return {
                'valid': False,
                'error': str(e)
            }
