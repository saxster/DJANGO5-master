"""
EXIF Analysis Service for YOUTILITY5 Enterprise Platform

Advanced EXIF metadata extraction and analysis for security, compliance, and quality control.
Integrates with existing security infrastructure for photo authenticity validation.

Features:
- Comprehensive EXIF data extraction (GPS, camera, timestamps, software)
- Photo authenticity detection and manipulation analysis
- GPS validation and spoofing detection
- Device fingerprinting and tracking
- Integration with existing security services

Complies with .claude/rules.md:
- Rule #7: Service methods < 150 lines
- Rule #9: Specific exception handling (no bare except)
- Rule #10: Database query optimization with select_related/prefetch_related
"""

import os
import logging
import hashlib
from datetime import datetime, timezone as dt_timezone
from typing import Dict, Any, Optional, List, Tuple
from PIL import Image, ExifTags
from PIL.ExifTags import TAGS, GPSTAGS

# Optional EXIF reading dependency
try:
    import exifread
    EXIF_AVAILABLE = True
except ImportError:
    EXIF_AVAILABLE = False
    exifread = None

from django.contrib.gis.geos import Point
from django.core.exceptions import ValidationError
from django.conf import settings
from django.utils import timezone

from apps.core.error_handling import ErrorHandler
from apps.core.constants.datetime_constants import SECONDS_IN_DAY
from apps.core.utils_new.datetime_utilities import get_current_utc

logger = logging.getLogger(__name__)


class EXIFAnalysisService:
    """
    Comprehensive EXIF analysis service for enterprise security and quality control.

    Extracts and analyzes photo metadata for authenticity validation, GPS verification,
    device fingerprinting, and compliance auditing.
    """

    # Critical EXIF tags for security analysis
    SECURITY_TAGS = {
        'GPS': ['GPSLatitude', 'GPSLongitude', 'GPSAltitude', 'GPSTimeStamp', 'GPSDateStamp'],
        'TIMESTAMP': ['DateTime', 'DateTimeOriginal', 'DateTimeDigitized'],
        'CAMERA': ['Make', 'Model', 'Software', 'SerialNumber', 'LensModel'],
        'TECHNICAL': ['ImageWidth', 'ImageLength', 'Flash', 'FocalLength', 'ISO']
    }

    # Software signatures indicating potential manipulation
    MANIPULATION_INDICATORS = {
        'editing_software': {
            'Adobe Photoshop', 'GIMP', 'Paint.NET', 'Canva', 'Pixlr', 'Lightroom',
            'Snapseed', 'Instagram', 'FaceTune', 'PhotoShop Express'
        },
        'suspicious_patterns': {
            'missing_timestamps', 'gps_mismatch', 'software_modification',
            'impossible_values', 'metadata_inconsistency'
        }
    }

    @classmethod
    def extract_comprehensive_metadata(
        cls,
        image_path: str,
        people_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Extract comprehensive EXIF metadata with security analysis.

        Args:
            image_path: Path to the image file
            people_id: Optional user ID for fraud tracking

        Returns:
            Comprehensive metadata dictionary with security indicators

        Raises:
            ValidationError: If image analysis fails
        """
        try:
            correlation_id = cls._generate_correlation_id()

            logger.info(
                "Starting comprehensive EXIF extraction",
                extra={
                    'correlation_id': correlation_id,
                    'image_path': image_path,
                    'people_id': people_id
                }
            )

            # Initialize result structure
            result = {
                'correlation_id': correlation_id,
                'image_path': image_path,
                'people_id': people_id,
                'extraction_timestamp': get_current_utc().isoformat(),
                'file_info': {},
                'exif_data': {},
                'gps_data': {},
                'security_analysis': {},
                'quality_metrics': {},
                'authenticity_score': 0.0,
                'fraud_indicators': [],
                'recommendations': []
            }

            # Phase 1: File analysis
            result['file_info'] = cls._analyze_file_properties(image_path)

            # Phase 2: EXIF extraction
            exif_data = cls._extract_raw_exif_data(image_path)
            result['exif_data'] = exif_data

            # Phase 3: GPS data processing
            if exif_data:
                result['gps_data'] = cls._extract_gps_coordinates(exif_data)

            # Phase 4: Security analysis
            result['security_analysis'] = cls._perform_security_analysis(
                exif_data, result['gps_data'], result['file_info']
            )

            # Phase 5: Quality assessment
            result['quality_metrics'] = cls._assess_metadata_quality(exif_data)

            # Phase 6: Authenticity scoring
            result['authenticity_score'] = cls._calculate_authenticity_score(result)

            # Phase 7: Fraud indicator analysis
            fraud_analysis = cls._analyze_fraud_indicators(result, people_id)
            result['fraud_indicators'] = fraud_analysis['indicators']
            result['recommendations'] = fraud_analysis['recommendations']

            logger.info(
                "EXIF extraction completed successfully",
                extra={
                    'correlation_id': correlation_id,
                    'authenticity_score': result['authenticity_score'],
                    'fraud_indicators_count': len(result['fraud_indicators'])
                }
            )

            return result

        except (OSError, IOError, PermissionError) as e:
            correlation_id = ErrorHandler.handle_exception(
                e,
                context={
                    'service': 'EXIFAnalysisService',
                    'method': 'extract_comprehensive_metadata',
                    'image_path': image_path,
                    'people_id': people_id
                },
                level='error'
            )
            raise ValidationError(
                f"Failed to access image file for EXIF extraction (ID: {correlation_id})"
            ) from e

        except (ValueError, TypeError, AttributeError) as e:
            correlation_id = ErrorHandler.handle_exception(
                e,
                context={
                    'service': 'EXIFAnalysisService',
                    'method': 'extract_comprehensive_metadata',
                    'image_path': image_path
                },
                level='warning'
            )
            raise ValidationError(
                f"Invalid image data for EXIF processing (ID: {correlation_id})"
            ) from e

    @classmethod
    def _analyze_file_properties(cls, image_path: str) -> Dict[str, Any]:
        """Analyze basic file properties and calculate hash."""
        try:
            stat_info = os.stat(image_path)
            file_hash = cls._calculate_file_hash(image_path)

            return {
                'file_size': stat_info.st_size,
                'created_timestamp': datetime.fromtimestamp(
                    stat_info.st_ctime, tz=dt_timezone.utc
                ).isoformat(),
                'modified_timestamp': datetime.fromtimestamp(
                    stat_info.st_mtime, tz=dt_timezone.utc
                ).isoformat(),
                'file_hash': file_hash,
                'file_extension': os.path.splitext(image_path)[1].lower()
            }
        except (OSError, IOError) as e:
            logger.warning(f"Failed to analyze file properties: {e}")
            return {'error': str(e)}

    @classmethod
    def _extract_raw_exif_data(cls, image_path: str) -> Dict[str, Any]:
        """Extract raw EXIF data using multiple methods for robustness."""
        exif_data = {}

        # Method 1: PIL/Pillow extraction
        try:
            with Image.open(image_path) as img:
                exif_dict = img._getexif()
                if exif_dict:
                    for tag_id, value in exif_dict.items():
                        tag_name = TAGS.get(tag_id, tag_id)
                        exif_data[f"PIL_{tag_name}"] = str(value)
        except (OSError, AttributeError, ValueError) as e:
            logger.debug(f"PIL EXIF extraction failed: {e}")

        # Method 2: ExifRead extraction (more comprehensive - optional dependency)
        if EXIF_AVAILABLE and exifread is not None:
            try:
                with open(image_path, 'rb') as f:
                    tags = exifread.process_file(f, details=True)
                    for tag_key, tag_value in tags.items():
                        if tag_key not in ['JPEGThumbnail', 'TIFFThumbnail']:
                            exif_data[f"EXIF_{tag_key}"] = str(tag_value)
            except (OSError, IOError, ValueError) as e:
                logger.debug(f"ExifRead extraction failed: {e}")
        else:
            logger.debug("ExifRead not available - using PIL only for EXIF extraction")

        return exif_data

    @classmethod
    def _extract_gps_coordinates(cls, exif_data: Dict[str, Any]) -> Dict[str, Any]:
        """Extract and validate GPS coordinates from EXIF data."""
        gps_data = {
            'latitude': None,
            'longitude': None,
            'altitude': None,
            'timestamp': None,
            'accuracy': None,
            'source': None,
            'validation_status': 'no_gps_data'
        }

        try:
            # Look for GPS data in different formats
            lat_keys = [k for k in exif_data.keys() if 'GPS' in k and 'Latitude' in k]
            lon_keys = [k for k in exif_data.keys() if 'GPS' in k and 'Longitude' in k]

            if lat_keys and lon_keys:
                # Extract coordinates (simplified - production would need more robust parsing)
                lat_raw = exif_data[lat_keys[0]]
                lon_raw = exif_data[lon_keys[0]]

                # Parse coordinate strings (format varies by camera)
                latitude = cls._parse_gps_coordinate(lat_raw)
                longitude = cls._parse_gps_coordinate(lon_raw)

                if latitude is not None and longitude is not None:
                    # Validate coordinate ranges
                    if -90 <= latitude <= 90 and -180 <= longitude <= 180:
                        gps_data.update({
                            'latitude': latitude,
                            'longitude': longitude,
                            'source': lat_keys[0],
                            'validation_status': 'valid',
                            'point_geometry': Point(longitude, latitude, srid=4326)
                        })
                    else:
                        gps_data['validation_status'] = 'invalid_range'

                # Extract additional GPS metadata
                for key, value in exif_data.items():
                    if 'GPS' in key:
                        if 'Altitude' in key:
                            gps_data['altitude'] = cls._parse_numeric_value(value)
                        elif 'TimeStamp' in key or 'DateStamp' in key:
                            gps_data['timestamp'] = str(value)

            return gps_data

        except (ValueError, TypeError, AttributeError) as e:
            logger.warning(f"GPS coordinate extraction failed: {e}")
            gps_data['validation_status'] = 'extraction_error'
            gps_data['error'] = str(e)
            return gps_data

    @classmethod
    def _parse_gps_coordinate(cls, coord_str: str) -> Optional[float]:
        """Parse GPS coordinate string to decimal degrees."""
        try:
            # Handle different GPS coordinate formats
            coord_str = str(coord_str).strip()

            # Format 1: [degrees, minutes, seconds] or degrees/1, minutes/1, seconds/1
            if '/' in coord_str and ',' in coord_str:
                parts = coord_str.replace('[', '').replace(']', '').split(',')
                if len(parts) >= 3:
                    degrees = float(parts[0].split('/')[0]) / float(parts[0].split('/')[1])
                    minutes = float(parts[1].split('/')[0]) / float(parts[1].split('/')[1])
                    seconds = float(parts[2].split('/')[0]) / float(parts[2].split('/')[1])
                    return degrees + (minutes / 60.0) + (seconds / 3600.0)

            # Format 2: Direct decimal
            try:
                return float(coord_str)
            except ValueError:
                pass

            return None

        except (ValueError, TypeError, IndexError, ZeroDivisionError) as e:
            logger.debug(f"GPS coordinate parsing failed: {e}")
            return None

    @classmethod
    def _parse_numeric_value(cls, value_str: str) -> Optional[float]:
        """Parse numeric EXIF values handling fractions."""
        try:
            value_str = str(value_str).strip()
            if '/' in value_str:
                numerator, denominator = value_str.split('/')
                return float(numerator) / float(denominator)
            return float(value_str)
        except (ValueError, TypeError, ZeroDivisionError):
            return None

    @classmethod
    def _perform_security_analysis(
        cls,
        exif_data: Dict[str, Any],
        gps_data: Dict[str, Any],
        file_info: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Perform comprehensive security analysis on EXIF data."""
        security_analysis = {
            'manipulation_risk': 'low',
            'software_signatures': [],
            'timestamp_consistency': True,
            'gps_authenticity': 'unknown',
            'camera_fingerprint': None,
            'suspicious_patterns': []
        }

        try:
            # Analyze software signatures
            for key, value in exif_data.items():
                if 'Software' in key or 'ProcessingSoftware' in key:
                    software_name = str(value).lower()
                    security_analysis['software_signatures'].append(value)

                    # Check for editing software
                    for editor in cls.MANIPULATION_INDICATORS['editing_software']:
                        if editor.lower() in software_name:
                            security_analysis['manipulation_risk'] = 'high'
                            security_analysis['suspicious_patterns'].append(
                                f'editing_software_detected:{editor}'
                            )

            # Camera fingerprint creation
            camera_info = []
            for key, value in exif_data.items():
                if any(tag in key for tag in ['Make', 'Model', 'SerialNumber']):
                    camera_info.append(f"{key}:{value}")

            if camera_info:
                security_analysis['camera_fingerprint'] = hashlib.sha256(
                    '|'.join(sorted(camera_info)).encode()
                ).hexdigest()[:16]

            # GPS authenticity assessment
            if gps_data.get('validation_status') == 'valid':
                # Check for round numbers (often indicates fake GPS)
                lat, lon = gps_data['latitude'], gps_data['longitude']
                if lat == round(lat) and lon == round(lon):
                    security_analysis['gps_authenticity'] = 'suspicious'
                    security_analysis['suspicious_patterns'].append('rounded_gps_coordinates')
                else:
                    security_analysis['gps_authenticity'] = 'likely_authentic'

            # Timestamp consistency analysis
            timestamps = []
            for key, value in exif_data.items():
                if 'DateTime' in key:
                    timestamps.append(str(value))

            if len(set(timestamps)) > 1:
                security_analysis['timestamp_consistency'] = False
                security_analysis['suspicious_patterns'].append('inconsistent_timestamps')

            return security_analysis

        except (ValueError, TypeError, AttributeError) as e:
            logger.warning(f"Security analysis failed: {e}")
            security_analysis['error'] = str(e)
            return security_analysis

    @classmethod
    def _assess_metadata_quality(cls, exif_data: Dict[str, Any]) -> Dict[str, Any]:
        """Assess the quality and completeness of EXIF metadata."""
        quality_metrics = {
            'completeness_score': 0.0,
            'critical_data_present': False,
            'metadata_richness': 'low',
            'missing_critical_fields': []
        }

        try:
            total_critical_fields = sum(len(tags) for tags in cls.SECURITY_TAGS.values())
            present_fields = 0

            for category, tags in cls.SECURITY_TAGS.items():
                for tag in tags:
                    found = any(tag in key for key in exif_data.keys())
                    if found:
                        present_fields += 1
                    else:
                        quality_metrics['missing_critical_fields'].append(tag)

            # Calculate completeness score
            quality_metrics['completeness_score'] = present_fields / total_critical_fields

            # Determine metadata richness
            if quality_metrics['completeness_score'] >= 0.8:
                quality_metrics['metadata_richness'] = 'high'
            elif quality_metrics['completeness_score'] >= 0.5:
                quality_metrics['metadata_richness'] = 'medium'
            else:
                quality_metrics['metadata_richness'] = 'low'

            # Check for critical data presence
            gps_present = any('GPS' in key for key in exif_data.keys())
            timestamp_present = any('DateTime' in key for key in exif_data.keys())
            camera_present = any(tag in str(exif_data) for tag in ['Make', 'Model'])

            quality_metrics['critical_data_present'] = (
                gps_present and timestamp_present and camera_present
            )

            return quality_metrics

        except (ValueError, TypeError) as e:
            logger.warning(f"Quality assessment failed: {e}")
            quality_metrics['error'] = str(e)
            return quality_metrics

    @classmethod
    def _calculate_authenticity_score(cls, analysis_result: Dict[str, Any]) -> float:
        """Calculate overall photo authenticity score (0.0 - 1.0)."""
        try:
            score = 1.0  # Start with perfect authenticity

            # Deduct for manipulation risk
            manipulation_risk = analysis_result['security_analysis'].get('manipulation_risk', 'low')
            if manipulation_risk == 'high':
                score -= 0.4
            elif manipulation_risk == 'medium':
                score -= 0.2

            # Deduct for suspicious patterns
            suspicious_count = len(
                analysis_result['security_analysis'].get('suspicious_patterns', [])
            )
            score -= min(0.3, suspicious_count * 0.1)

            # Deduct for poor metadata quality
            completeness = analysis_result['quality_metrics'].get('completeness_score', 0.0)
            if completeness < 0.3:
                score -= 0.2

            # Deduct for GPS issues
            gps_authenticity = analysis_result['security_analysis'].get('gps_authenticity', 'unknown')
            if gps_authenticity == 'suspicious':
                score -= 0.3

            # Bonus for high-quality metadata
            if completeness > 0.8:
                score += 0.1

            return max(0.0, min(1.0, score))

        except (ValueError, TypeError, AttributeError) as e:
            logger.warning(f"Authenticity score calculation failed: {e}")
            return 0.5  # Neutral score if calculation fails

    @classmethod
    def _analyze_fraud_indicators(
        cls,
        analysis_result: Dict[str, Any],
        people_id: Optional[int]
    ) -> Dict[str, Any]:
        """Analyze fraud indicators and generate recommendations."""
        fraud_analysis = {
            'indicators': [],
            'recommendations': [],
            'risk_level': 'low'
        }

        try:
            # Collect fraud indicators
            security_analysis = analysis_result.get('security_analysis', {})
            gps_data = analysis_result.get('gps_data', {})

            # Add suspicious patterns as fraud indicators
            fraud_analysis['indicators'].extend(
                security_analysis.get('suspicious_patterns', [])
            )

            # GPS-specific fraud indicators
            if gps_data.get('validation_status') == 'invalid_range':
                fraud_analysis['indicators'].append('invalid_gps_coordinates')

            if gps_data.get('validation_status') == 'no_gps_data':
                fraud_analysis['indicators'].append('missing_gps_data')

            # Authenticity score-based indicators
            authenticity_score = analysis_result.get('authenticity_score', 1.0)
            if authenticity_score < 0.3:
                fraud_analysis['indicators'].append('low_authenticity_score')
                fraud_analysis['risk_level'] = 'high'
            elif authenticity_score < 0.6:
                fraud_analysis['indicators'].append('medium_authenticity_score')
                fraud_analysis['risk_level'] = 'medium'

            # Generate recommendations
            if 'editing_software_detected' in str(fraud_analysis['indicators']):
                fraud_analysis['recommendations'].append(
                    'Photo shows signs of editing - verify with original source'
                )

            if 'missing_gps_data' in fraud_analysis['indicators']:
                fraud_analysis['recommendations'].append(
                    'Enable GPS location services for photo verification'
                )

            if 'rounded_gps_coordinates' in fraud_analysis['indicators']:
                fraud_analysis['recommendations'].append(
                    'GPS coordinates appear artificially precise - investigate location'
                )

            if fraud_analysis['risk_level'] == 'high':
                fraud_analysis['recommendations'].append(
                    'Photo requires manual verification due to high fraud risk'
                )

            return fraud_analysis

        except (ValueError, TypeError, AttributeError) as e:
            logger.warning(f"Fraud analysis failed: {e}")
            fraud_analysis['error'] = str(e)
            return fraud_analysis

    @classmethod
    def _calculate_file_hash(cls, file_path: str) -> str:
        """Calculate SHA256 hash of file for integrity verification."""
        try:
            hash_sha256 = hashlib.sha256()
            with open(file_path, 'rb') as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    hash_sha256.update(chunk)
            return hash_sha256.hexdigest()[:16]  # Truncate for storage
        except (OSError, IOError) as e:
            logger.warning(f"File hash calculation failed: {e}")
            return hashlib.sha256(str(file_path).encode()).hexdigest()[:16]

    @classmethod
    def _generate_correlation_id(cls) -> str:
        """Generate unique correlation ID for tracking."""
        import uuid
        return str(uuid.uuid4())

    @classmethod
    def validate_photo_location(
        cls,
        image_path: str,
        expected_location: Point,
        tolerance_meters: int = 100
    ) -> Dict[str, Any]:
        """
        Validate photo GPS against expected location for spoofing detection.

        Args:
            image_path: Path to photo
            expected_location: Expected GPS location as Point
            tolerance_meters: Maximum allowed distance in meters

        Returns:
            Validation result with distance and authenticity assessment
        """
        try:
            metadata = cls.extract_comprehensive_metadata(image_path)
            gps_data = metadata.get('gps_data', {})

            if gps_data.get('validation_status') != 'valid':
                return {
                    'validation_status': 'no_gps_data',
                    'authenticity_risk': 'high',
                    'reason': 'Photo contains no valid GPS coordinates'
                }

            photo_location = gps_data.get('point_geometry')
            if not photo_location:
                return {
                    'validation_status': 'invalid_coordinates',
                    'authenticity_risk': 'high',
                    'reason': 'Could not parse GPS coordinates'
                }

            # Calculate distance using PostGIS
            distance_meters = expected_location.distance(photo_location) * 111000  # Rough conversion

            validation_result = {
                'validation_status': 'validated',
                'distance_meters': round(distance_meters, 2),
                'tolerance_meters': tolerance_meters,
                'within_tolerance': distance_meters <= tolerance_meters,
                'photo_coordinates': {
                    'latitude': gps_data['latitude'],
                    'longitude': gps_data['longitude']
                },
                'expected_coordinates': {
                    'latitude': expected_location.y,
                    'longitude': expected_location.x
                }
            }

            # Determine authenticity risk
            if distance_meters <= tolerance_meters:
                validation_result['authenticity_risk'] = 'low'
                validation_result['reason'] = 'GPS coordinates match expected location'
            elif distance_meters <= tolerance_meters * 2:
                validation_result['authenticity_risk'] = 'medium'
                validation_result['reason'] = f'GPS coordinates {distance_meters:.0f}m from expected location'
            else:
                validation_result['authenticity_risk'] = 'high'
                validation_result['reason'] = f'GPS coordinates {distance_meters:.0f}m from expected - possible spoofing'

            return validation_result

        except (ValueError, TypeError, AttributeError) as e:
            correlation_id = ErrorHandler.handle_exception(
                e,
                context={
                    'service': 'EXIFAnalysisService',
                    'method': 'validate_photo_location',
                    'image_path': image_path
                },
                level='warning'
            )
            return {
                'validation_status': 'error',
                'authenticity_risk': 'unknown',
                'reason': f'Location validation failed (ID: {correlation_id})',
                'error': str(e)
            }