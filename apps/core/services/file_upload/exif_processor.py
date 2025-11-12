"""
EXIF processing and metadata management for image uploads.

Handles:
- EXIF metadata extraction and analysis
- ImageMetadata database record creation
- Camera fingerprint processing
- Quality assessment
- Authenticity logging

Complies with Rule #14 from .claude/rules.md - File Upload Security
"""

import logging
from django.contrib.gis.geos import Point
from django.core.exceptions import ValidationError
from apps.core.services.exif_analysis_service import EXIFAnalysisService
from apps.core.models import (
    ImageMetadata,
    PhotoAuthenticityLog,
    CameraFingerprint,
    ImageQualityAssessment,
)
from apps.core.exceptions.patterns import DATABASE_EXCEPTIONS, FILE_EXCEPTIONS

logger = logging.getLogger(__name__)


class EXIFProcessor:
    """EXIF processing and metadata management for image uploads."""

    @classmethod
    def process_image_exif(
        cls,
        file_path: str,
        upload_context: dict,
        expected_location: Point,
        correlation_id: str
    ) -> dict:
        """
        Process EXIF data and create database records for comprehensive analysis.

        Args:
            file_path: Path to the uploaded image
            upload_context: Upload context information
            expected_location: Expected GPS location for validation
            correlation_id: Unique tracking ID

        Returns:
            dict: Comprehensive EXIF analysis results
        """
        try:
            # Extract comprehensive EXIF metadata
            people_id = upload_context.get('people_id') if upload_context else None
            exif_metadata = EXIFAnalysisService.extract_comprehensive_metadata(
                file_path, people_id
            )

            # Create ImageMetadata database record
            try:
                image_metadata = cls.create_image_metadata_record(
                    exif_metadata, upload_context, correlation_id
                )
                exif_metadata['database_id'] = image_metadata.id
            except FILE_EXCEPTIONS as db_error:
                logger.warning(f"Failed to create ImageMetadata record: {db_error}")
                exif_metadata['database_error'] = str(db_error)

            # Validate GPS location if expected location provided
            if expected_location and exif_metadata.get('gps_data', {}).get('validation_status') == 'valid':
                location_validation = EXIFAnalysisService.validate_photo_location(
                    file_path, expected_location
                )
                exif_metadata['location_validation'] = location_validation

                # Log location validation
                if location_validation.get('authenticity_risk') == 'high':
                    cls.log_authenticity_event(
                        image_metadata.id if 'database_id' in exif_metadata else None,
                        'location_check',
                        'failed',
                        location_validation,
                        people_id
                    )

            # Process camera fingerprint
            if exif_metadata.get('security_analysis', {}).get('camera_fingerprint'):
                cls.process_camera_fingerprint(
                    exif_metadata['security_analysis']['camera_fingerprint'],
                    exif_metadata,
                    people_id,
                )

            return exif_metadata

        except (ValueError, TypeError, AttributeError) as e:
            logger.error(f"EXIF processing failed: {e}")
            return {'error': str(e), 'correlation_id': correlation_id}

    @classmethod
    def create_image_metadata_record(
        cls,
        exif_metadata: dict,
        upload_context: dict,
        correlation_id: str
    ) -> ImageMetadata:
        """Create ImageMetadata database record from EXIF analysis."""
        try:
            gps_data = exif_metadata.get('gps_data', {})
            security_analysis = exif_metadata.get('security_analysis', {})
            quality_metrics = exif_metadata.get('quality_metrics', {})

            # Create GPS Point if coordinates are valid
            gps_point = None
            if gps_data.get('validation_status') == 'valid':
                gps_point = Point(
                    gps_data['longitude'],
                    gps_data['latitude'],
                    srid=4326
                )

            # Create ImageMetadata record
            image_metadata = ImageMetadata.objects.create(
                correlation_id=correlation_id,
                image_path=exif_metadata.get('image_path', ''),
                file_hash=exif_metadata.get('file_info', {}).get('file_hash', ''),
                file_size=exif_metadata.get('file_info', {}).get('file_size', 0),
                file_extension=exif_metadata.get('file_info', {}).get('file_extension', ''),
                people_id=upload_context.get('people_id') if upload_context else None,
                upload_context=upload_context.get('folder_type', 'general') if upload_context else None,
                gps_coordinates=gps_point,
                gps_altitude=gps_data.get('altitude'),
                gps_accuracy=gps_data.get('accuracy'),
                camera_make=security_analysis.get('camera_make'),
                camera_model=security_analysis.get('camera_model'),
                camera_serial=security_analysis.get('camera_fingerprint'),
                software_signature=','.join(security_analysis.get('software_signatures', [])),
                timestamp_consistency=security_analysis.get('timestamp_consistency', True),
                authenticity_score=exif_metadata.get('authenticity_score', 0.5),
                manipulation_risk=security_analysis.get('manipulation_risk', 'low'),
                validation_status='valid' if exif_metadata.get('authenticity_score', 0) > 0.7 else 'suspicious',
                raw_exif_data=exif_metadata.get('exif_data', {}),
                security_analysis=security_analysis,
                quality_metrics=quality_metrics
            )

            # Create quality assessment record if we have quality data
            if quality_metrics:
                cls.create_quality_assessment_record(image_metadata, quality_metrics)

            return image_metadata

        except DATABASE_EXCEPTIONS as e:
            logger.error(f"Failed to create ImageMetadata record: {e}")
            raise

    @classmethod
    def create_quality_assessment_record(
        cls,
        image_metadata: ImageMetadata,
        quality_metrics: dict
    ):
        """Create ImageQualityAssessment record."""
        try:
            completeness = quality_metrics.get('completeness_score', 0.5)

            # Determine quality level
            if completeness >= 0.9:
                quality_level = 'excellent'
            elif completeness >= 0.7:
                quality_level = 'good'
            elif completeness >= 0.5:
                quality_level = 'fair'
            elif completeness >= 0.3:
                quality_level = 'poor'
            else:
                quality_level = 'unacceptable'

            ImageQualityAssessment.objects.create(
                image_metadata=image_metadata,
                overall_quality_score=completeness,
                quality_level=quality_level,
                metadata_completeness=completeness,
                gps_data_quality=1.0 if image_metadata.gps_coordinates else 0.0,
                timestamp_reliability=1.0 if image_metadata.timestamp_consistency else 0.5,
                quality_issues=quality_metrics.get('missing_critical_fields', []),
                recommendations=[]  # Could be enhanced with specific recommendations
            )

        except DATABASE_EXCEPTIONS as e:
            logger.warning(f"Failed to create quality assessment record: {e}")

    @classmethod
    def process_camera_fingerprint(
        cls,
        fingerprint_hash: str,
        exif_metadata: dict,
        people_id: int,
    ):
        """Process and update camera fingerprint tracking."""
        try:
            security_analysis = exif_metadata.get('security_analysis', {})
            camera_make = security_analysis.get('camera_make', 'Unknown')
            camera_model = security_analysis.get('camera_model', 'Unknown')

            # Get or create camera fingerprint
            fingerprint, created = CameraFingerprint.objects.get_or_create(
                fingerprint_hash=fingerprint_hash,
                defaults={
                    'camera_make': camera_make,
                    'camera_model': camera_model,
                    'trust_level': 'neutral'
                }
            )

            # Update usage statistics
            if people_id:
                from apps.peoples.models import People
                people_instance = People.objects.get(id=people_id)
                fingerprint.update_usage(people_instance)

            # Check for fraud indicators
            fraud_indicators = exif_metadata.get('fraud_indicators', [])
            if fraud_indicators:
                fingerprint.fraud_incidents += 1
                if fingerprint.fraud_incidents >= 3:
                    fingerprint.trust_level = 'suspicious'
                fingerprint.save()

        except DATABASE_EXCEPTIONS as e:
            logger.warning(f"Camera fingerprint processing failed: {e}")

    @classmethod
    def log_authenticity_event(
        cls,
        image_metadata_id: int,
        validation_action: str,
        validation_result: str,
        validation_details: dict,
        people_id: int = None
    ):
        """Log authenticity validation event."""
        try:
            if not image_metadata_id:
                return

            PhotoAuthenticityLog.objects.create(
                image_metadata_id=image_metadata_id,
                validation_action=validation_action,
                validation_result=validation_result,
                reviewed_by_id=people_id,
                validation_details=validation_details,
                confidence_score=validation_details.get('confidence', 0.5),
                follow_up_required=(validation_result in ['failed', 'flagged'])
            )

        except DATABASE_EXCEPTIONS as e:
            logger.warning(f"Failed to log authenticity event: {e}")
