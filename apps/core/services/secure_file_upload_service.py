"""
Enhanced secure file upload service for all file types including PDFs.

This service extends the existing validation patterns to support PDFs and other
document types while maintaining comprehensive security validations.

Complies with Rule #14 from .claude/rules.md - File Upload Security
"""

import os
import logging
import hashlib
import mimetypes
from django.utils.text import get_valid_filename
from django.core.exceptions import ValidationError
from django.conf import settings
from django.contrib.gis.geos import Point
from apps.core.error_handling import ErrorHandler
from apps.core.exceptions import FileValidationException
from apps.core.services.exif_analysis_service import EXIFAnalysisService
from apps.core.models import (
    ImageMetadata, PhotoAuthenticityLog, CameraFingerprint, ImageQualityAssessment
)

logger = logging.getLogger(__name__)


class SecureFileUploadService:
    """
    Enhanced secure file upload service supporting multiple file types.

    Features:
    - Comprehensive filename sanitization and validation
    - Path traversal prevention with multiple layers
    - Content type validation with header verification
    - File size validation per file type
    - Secure random filename generation
    - Directory creation with proper permissions
    - Support for images, PDFs, and documents
    """

    # File type configurations
    FILE_TYPES = {
        'image': {
            'extensions': {'.jpg', '.jpeg', '.png', '.gif', '.webp'},
            'max_size': 5 * 1024 * 1024,  # 5MB
            'mime_types': {'image/jpeg', 'image/png', 'image/gif', 'image/webp'},
            'magic_numbers': {
                b'\xFF\xD8\xFF': 'jpeg',
                b'\x89PNG': 'png',
                b'GIF87a': 'gif',
                b'GIF89a': 'gif',
                b'RIFF': 'webp'
            }
        },
        'pdf': {
            'extensions': {'.pdf'},
            'max_size': 10 * 1024 * 1024,  # 10MB
            'mime_types': {'application/pdf'},
            'magic_numbers': {
                b'%PDF': 'pdf'
            }
        },
        'document': {
            'extensions': {'.doc', '.docx', '.txt', '.rtf'},
            'max_size': 10 * 1024 * 1024,  # 10MB
            'mime_types': {
                'application/msword',
                'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
                'text/plain',
                'application/rtf'
            },
            'magic_numbers': {
                b'PK\x03\x04': 'docx',
                b'\xD0\xCF\x11\xE0': 'doc',
                b'{\rtf': 'rtf'
            }
        }
    }

    # Dangerous file patterns that should be blocked
    DANGEROUS_PATTERNS = {
        'executable_extensions': {
            '.exe', '.bat', '.cmd', '.com', '.pif', '.scr', '.vbs', '.js',
            '.jar', '.sh', '.ps1', '.py', '.php', '.asp', '.aspx', '.jsp'
        },
        'dangerous_names': {
            'con', 'aux', 'prn', 'nul', 'com1', 'com2', 'com3', 'com4',
            'com5', 'com6', 'com7', 'com8', 'com9', 'lpt1', 'lpt2', 'lpt3',
            'lpt4', 'lpt5', 'lpt6', 'lpt7', 'lpt8', 'lpt9'
        },
        'path_traversal': {
            '..', '/', '\\', '\x00', '\r', '\n', ':', '*', '?', '"', '<',
            '>', '|', '\x7f'
        }
    }

    @classmethod
    def validate_and_process_upload(cls, uploaded_file, file_type, upload_context=None):
        """
        Main entry point for secure file upload processing.

        Args:
            uploaded_file: Django UploadedFile object
            file_type: Type of file ('image', 'pdf', 'document')
            upload_context: Dict with context info (user_id, folder_type, etc.)

        Returns:
            dict: Secure file information with path and metadata

        Raises:
            ValidationError: If any security validation fails
        """
        try:
            correlation_id = cls._generate_correlation_id()

            logger.info(
                "Starting secure file upload validation",
                extra={
                    'correlation_id': correlation_id,
                    'file_type': file_type,
                    'original_filename': uploaded_file.name if uploaded_file else 'None',
                    'upload_context': upload_context
                }
            )

            # Phase 1: Basic file validation
            cls._validate_file_exists(uploaded_file)

            # Phase 2: Security validation
            cls._validate_file_security(uploaded_file, file_type)

            # Phase 3: Content validation
            cls._validate_file_content(uploaded_file, file_type)

            # Phase 4: Generate secure path
            secure_path = cls._generate_secure_path(uploaded_file, file_type, upload_context)

            # Phase 5: Create secure metadata
            file_metadata = cls._create_file_metadata(uploaded_file, file_type, secure_path, correlation_id)

            logger.info(
                "File upload validation completed successfully",
                extra={
                    'correlation_id': correlation_id,
                    'secure_path': secure_path,
                    'file_size': uploaded_file.size
                }
            )

            return file_metadata

        except ValidationError:
            raise
        except (OSError, IOError, PermissionError) as e:
            correlation_id = ErrorHandler.handle_exception(
                e,
                context={
                    'service': 'SecureFileUploadService',
                    'method': 'validate_and_process_upload',
                    'file_type': file_type,
                    'error_type': 'filesystem'
                },
                level='error'
            )
            raise ValidationError(
                f"File system error during upload (ID: {correlation_id})"
            ) from e
        except (ValueError, TypeError, AttributeError) as e:
            correlation_id = ErrorHandler.handle_exception(
                e,
                context={
                    'service': 'SecureFileUploadService',
                    'method': 'validate_and_process_upload',
                    'file_type': file_type,
                    'error_type': 'data_validation'
                },
                level='warning'
            )
            raise ValidationError(
                f"Invalid file data (ID: {correlation_id})"
            ) from e
        except MemoryError as e:
            correlation_id = ErrorHandler.handle_exception(
                e,
                context={
                    'service': 'SecureFileUploadService',
                    'method': 'validate_and_process_upload',
                    'file_type': file_type,
                    'error_type': 'memory'
                },
                level='critical'
            )
            raise ValidationError(
                f"File upload processing failed (ID: {correlation_id})"
            ) from e

    @classmethod
    def _validate_file_exists(cls, uploaded_file):
        """Validate that file exists and is accessible."""
        if not uploaded_file:
            raise ValidationError("No file provided for upload")

        if not hasattr(uploaded_file, 'name') or not uploaded_file.name:
            raise ValidationError("File must have a valid name")

        if not hasattr(uploaded_file, 'size') or uploaded_file.size <= 0:
            raise ValidationError("File must have valid content")

    @classmethod
    def _validate_file_security(cls, uploaded_file, file_type):
        """Comprehensive security validation of uploaded file."""
        # Validate file type configuration
        if file_type not in cls.FILE_TYPES:
            raise ValidationError(f"Unsupported file type: {file_type}")

        config = cls.FILE_TYPES[file_type]

        # Validate file size
        if uploaded_file.size > config['max_size']:
            max_size_mb = config['max_size'] // (1024 * 1024)
            raise ValidationError(f"File too large. Maximum size for {file_type}: {max_size_mb}MB")

        # Sanitize and validate filename
        sanitized_name = cls._sanitize_filename(uploaded_file.name)

        # Validate file extension
        file_extension = cls._validate_file_extension(sanitized_name, config['extensions'])

        # Check for dangerous patterns
        cls._check_dangerous_patterns(sanitized_name)

        # Validate MIME type if available
        if hasattr(uploaded_file, 'content_type') and uploaded_file.content_type:
            cls._validate_mime_type(uploaded_file.content_type, config['mime_types'])

    @classmethod
    def _validate_file_content(cls, uploaded_file, file_type):
        """Validate actual file content using magic numbers."""
        config = cls.FILE_TYPES[file_type]

        # Read first few bytes to check magic numbers
        try:
            uploaded_file.seek(0)
            file_header = uploaded_file.read(8)
            uploaded_file.seek(0)  # Reset position

            # Check magic numbers
            valid_content = False
            for magic_bytes, content_type in config['magic_numbers'].items():
                if file_header.startswith(magic_bytes):
                    valid_content = True
                    break

            if not valid_content:
                raise ValidationError(f"File content does not match expected {file_type} format")

        except (OSError, IOError) as e:
            raise ValidationError("Unable to read file content for validation") from e

    @classmethod
    def _sanitize_filename(cls, filename):
        """Comprehensive filename sanitization."""
        if not filename or not isinstance(filename, str):
            raise ValidationError("Invalid filename provided")

        # Remove any path components
        filename = os.path.basename(filename)

        # Use Django's get_valid_filename for basic sanitization
        sanitized = get_valid_filename(filename)

        if not sanitized:
            raise ValidationError("Filename could not be sanitized")

        # Additional security checks
        if any(pattern in sanitized for pattern in cls.DANGEROUS_PATTERNS['path_traversal']):
            raise ValidationError("Filename contains dangerous path components")

        # Check filename length
        if len(sanitized) > 255:
            raise ValidationError("Filename too long (maximum 255 characters)")

        return sanitized

    @classmethod
    def _validate_file_extension(cls, filename, allowed_extensions):
        """Validate file extension against allowed list."""
        if not filename or '.' not in filename:
            raise ValidationError("File must have a valid extension")

        file_extension = os.path.splitext(filename)[1].lower()

        if not file_extension:
            raise ValidationError("File must have a valid extension")

        if file_extension not in allowed_extensions:
            allowed_list = ', '.join(sorted(allowed_extensions))
            raise ValidationError(f"File type not allowed. Allowed types: {allowed_list}")

        # Check against dangerous extensions
        if file_extension in cls.DANGEROUS_PATTERNS['executable_extensions']:
            raise ValidationError("Executable file types are not allowed")

        return file_extension

    @classmethod
    def _check_dangerous_patterns(cls, filename):
        """Check for dangerous filename patterns."""
        # Check against reserved Windows names
        name_without_ext = os.path.splitext(filename)[0].lower()
        if name_without_ext in cls.DANGEROUS_PATTERNS['dangerous_names']:
            raise ValidationError("Filename uses reserved system name")

        # Check for double extensions
        if filename.count('.') > 1:
            parts = filename.split('.')
            for part in parts[1:-1]:  # Check middle extensions
                if f".{part.lower()}" in cls.DANGEROUS_PATTERNS['executable_extensions']:
                    raise ValidationError("File contains dangerous double extension")

    @classmethod
    def _validate_mime_type(cls, content_type, allowed_mime_types):
        """Validate MIME type against allowed list."""
        if content_type not in allowed_mime_types:
            allowed_list = ', '.join(sorted(allowed_mime_types))
            raise ValidationError(f"MIME type not allowed. Allowed types: {allowed_list}")

    @classmethod
    def _generate_secure_path(cls, uploaded_file, file_type, upload_context):
        """Generate secure file path with proper directory structure."""
        if not upload_context:
            raise ValidationError("Upload context required for path generation")

        # Extract and validate context
        people_id = upload_context.get('people_id')
        folder_type = upload_context.get('folder_type', 'general')

        if not people_id:
            raise ValidationError("User ID required for file upload")

        # Sanitize folder type
        safe_folder_type = get_valid_filename(str(folder_type))
        if not safe_folder_type or '..' in safe_folder_type:
            raise ValidationError("Invalid folder type specified")

        # Generate secure filename
        file_extension = os.path.splitext(uploaded_file.name)[1].lower()
        secure_filename = cls._generate_unique_filename(people_id, file_extension)

        # Build secure path structure
        secure_path = os.path.join(
            settings.MEDIA_ROOT,
            'uploads',
            file_type,
            safe_folder_type,
            secure_filename
        )

        # Ensure path is within MEDIA_ROOT
        abs_secure_path = os.path.abspath(secure_path)
        abs_media_root = os.path.abspath(settings.MEDIA_ROOT)

        if not abs_secure_path.startswith(abs_media_root):
            raise ValidationError("Generated path is outside allowed directory")

        return secure_path

    @classmethod
    def _generate_unique_filename(cls, people_id, file_extension):
        """Generate unique filename to prevent conflicts."""
        import time
        import random

        # Sanitize people_id
        safe_people_id = get_valid_filename(str(people_id))

        # Create unique hash
        timestamp = str(int(time.time()))
        random_value = str(random.randint(10000, 99999))
        unique_data = f"{safe_people_id}_{timestamp}_{random_value}"
        unique_hash = hashlib.sha256(unique_data.encode()).hexdigest()[:12]

        return f"{safe_people_id}_{unique_hash}{file_extension}"

    @classmethod
    def _create_file_metadata(cls, uploaded_file, file_type, secure_path, correlation_id):
        """Create secure metadata for uploaded file."""
        return {
            'filename': os.path.basename(secure_path),
            'original_filename': os.path.basename(uploaded_file.name),
            'file_path': secure_path,
            'file_size': uploaded_file.size,
            'file_type': file_type,
            'content_type': getattr(uploaded_file, 'content_type', 'application/octet-stream'),
            'correlation_id': correlation_id,
            'upload_timestamp': cls._get_current_timestamp()
        }

    @classmethod
    def _generate_correlation_id(cls):
        """Generate unique correlation ID for tracking."""
        import uuid
        return str(uuid.uuid4())

    @classmethod
    def _get_current_timestamp(cls):
        """Get current timestamp in ISO format."""
        from datetime import datetime
        return datetime.now().isoformat()

    @classmethod
    def validate_reassembled_file(cls, file_path, file_type, mime_type):
        """
        Validate a reassembled file from chunked upload.

        This method extracts validation logic for use with resumable uploads.
        Applies same security checks as direct uploads.

        Args:
            file_path: Path to the reassembled file
            file_type: Type of file ('image', 'pdf', 'document')
            mime_type: Expected MIME type

        Raises:
            ValidationError: If any security validation fails
        """
        try:
            if file_type not in cls.FILE_TYPES:
                raise ValidationError(f"Unsupported file type: {file_type}")

            config = cls.FILE_TYPES[file_type]

            if not os.path.exists(file_path):
                raise ValidationError("File not found for validation")

            file_size = os.path.getsize(file_path)
            if file_size > config['max_size']:
                max_size_mb = config['max_size'] // (1024 * 1024)
                raise ValidationError(
                    f"File too large. Maximum size for {file_type}: {max_size_mb}MB"
                )

            filename = os.path.basename(file_path)
            cls._validate_file_extension(filename, config['extensions'])
            cls._check_dangerous_patterns(filename)

            if mime_type not in config['mime_types']:
                raise ValidationError(f"Invalid MIME type: {mime_type}")

            with open(file_path, 'rb') as f:
                file_header = f.read(8)

            valid_content = False
            for magic_bytes in config['magic_numbers'].keys():
                if file_header.startswith(magic_bytes):
                    valid_content = True
                    break

            if not valid_content:
                raise ValidationError(
                    f"File content does not match expected {file_type} format"
                )

            logger.info(
                "Reassembled file validation successful",
                extra={
                    'file_path': file_path,
                    'file_type': file_type,
                    'file_size': file_size
                }
            )

        except (OSError, IOError) as e:
            raise ValidationError("Unable to read file for validation") from e

    @classmethod
    def save_uploaded_file(cls, uploaded_file, file_metadata):
        """
        Securely save uploaded file to disk.

        Args:
            uploaded_file: Django UploadedFile object
            file_metadata: Metadata from validate_and_process_upload

        Returns:
            str: Final file path

        Raises:
            ValidationError: If file save fails
        """
        try:
            file_path = file_metadata['file_path']

            # Ensure directory exists with secure permissions
            directory = os.path.dirname(file_path)
            os.makedirs(directory, mode=0o755, exist_ok=True)

            # Save file securely
            with open(file_path, 'wb') as destination:
                for chunk in uploaded_file.chunks():
                    destination.write(chunk)

            # Set secure file permissions
            os.chmod(file_path, 0o644)

            logger.info(
                "File saved successfully",
                extra={
                    'correlation_id': file_metadata['correlation_id'],
                    'file_path': file_path,
                    'file_size': file_metadata['file_size']
                }
            )

            return file_path

        except (OSError, IOError) as e:
            correlation_id = ErrorHandler.handle_exception(
                e,
                context={
                    'service': 'SecureFileUploadService',
                    'method': 'save_uploaded_file',
                    'file_path': file_metadata.get('file_path'),
                    'correlation_id': file_metadata.get('correlation_id')
                }
            )
            raise ValidationError(
                f"Failed to save uploaded file (ID: {correlation_id})"
            ) from e

    @classmethod
    def validate_and_process_with_exif(
        cls,
        uploaded_file,
        file_type,
        upload_context=None,
        expected_location=None,
        enable_exif_processing=True
    ):
        """
        Enhanced file upload processing with comprehensive EXIF analysis.

        Args:
            uploaded_file: Django UploadedFile object
            file_type: Type of file ('image', 'pdf', 'document')
            upload_context: Dict with context info (user_id, folder_type, etc.)
            expected_location: Point object for GPS validation (optional)
            enable_exif_processing: Whether to perform EXIF analysis

        Returns:
            dict: Enhanced file information with EXIF analysis results

        Raises:
            ValidationError: If any security validation fails
        """
        try:
            correlation_id = cls._generate_correlation_id()

            logger.info(
                "Starting enhanced file upload with EXIF processing",
                extra={
                    'correlation_id': correlation_id,
                    'file_type': file_type,
                    'enable_exif': enable_exif_processing,
                    'upload_context': upload_context
                }
            )

            # Phase 1: Standard file validation
            file_metadata = cls.validate_and_process_upload(
                uploaded_file, file_type, upload_context
            )

            # Phase 2: Save file to disk first
            file_path = cls.save_uploaded_file(uploaded_file, file_metadata)
            file_metadata['final_file_path'] = file_path

            # Phase 3: EXIF processing (for images only)
            exif_results = {}
            if enable_exif_processing and file_type == 'image':
                try:
                    exif_results = cls._process_image_exif(
                        file_path,
                        upload_context,
                        expected_location,
                        correlation_id
                    )
                    file_metadata['exif_analysis'] = exif_results
                except (ValueError, TypeError) as exif_error:
                    logger.warning(
                        f"EXIF processing failed but file upload continues: {exif_error}",
                        extra={'correlation_id': correlation_id}
                    )
                    file_metadata['exif_analysis'] = {'error': str(exif_error)}

            # Phase 4: Security validation with EXIF context
            security_result = cls._perform_enhanced_security_validation(
                file_metadata, exif_results
            )
            file_metadata['security_validation'] = security_result

            # Phase 5: Final authenticity assessment
            if exif_results and not exif_results.get('error'):
                authenticity_assessment = cls._assess_upload_authenticity(
                    exif_results, expected_location, upload_context
                )
                file_metadata['authenticity_assessment'] = authenticity_assessment

                # Log high-risk uploads
                if authenticity_assessment.get('risk_level') == 'high':
                    logger.warning(
                        "High-risk file upload detected",
                        extra={
                            'correlation_id': correlation_id,
                            'authenticity_score': authenticity_assessment.get('authenticity_score'),
                            'fraud_indicators': authenticity_assessment.get('fraud_indicators', [])
                        }
                    )

            logger.info(
                "Enhanced file upload processing completed",
                extra={
                    'correlation_id': correlation_id,
                    'final_file_path': file_path,
                    'exif_processed': bool(exif_results and not exif_results.get('error')),
                    'authenticity_score': file_metadata.get('authenticity_assessment', {}).get('authenticity_score', 'N/A')
                }
            )

            return file_metadata

        except ValidationError:
            raise
        except (OSError, IOError, PermissionError) as e:
            correlation_id = ErrorHandler.handle_exception(
                e,
                context={
                    'service': 'SecureFileUploadService',
                    'method': 'validate_and_process_with_exif',
                    'file_type': file_type,
                    'error_type': 'filesystem'
                },
                level='error'
            )
            raise ValidationError(
                f"Enhanced file processing failed (ID: {correlation_id})"
            ) from e

    @classmethod
    def _process_image_exif(
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
                image_metadata = cls._create_image_metadata_record(
                    exif_metadata, upload_context, correlation_id
                )
                exif_metadata['database_id'] = image_metadata.id
            except Exception as db_error:
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
                    cls._log_authenticity_event(
                        image_metadata.id if 'database_id' in exif_metadata else None,
                        'location_check',
                        'failed',
                        location_validation,
                        people_id
                    )

            # Process camera fingerprint
            if exif_metadata.get('security_analysis', {}).get('camera_fingerprint'):
                cls._process_camera_fingerprint(
                    exif_metadata['security_analysis']['camera_fingerprint'],
                    exif_metadata,
                    people_id
                )

            return exif_metadata

        except (ValueError, TypeError, AttributeError) as e:
            logger.error(f"EXIF processing failed: {e}")
            return {'error': str(e), 'correlation_id': correlation_id}

    @classmethod
    def _create_image_metadata_record(
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
                cls._create_quality_assessment_record(image_metadata, quality_metrics)

            return image_metadata

        except Exception as e:
            logger.error(f"Failed to create ImageMetadata record: {e}")
            raise

    @classmethod
    def _create_quality_assessment_record(
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

        except Exception as e:
            logger.warning(f"Failed to create quality assessment record: {e}")

    @classmethod
    def _process_camera_fingerprint(
        cls,
        fingerprint_hash: str,
        exif_metadata: dict,
        people_id: int
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

        except Exception as e:
            logger.warning(f"Camera fingerprint processing failed: {e}")

    @classmethod
    def _log_authenticity_event(
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

        except Exception as e:
            logger.warning(f"Failed to log authenticity event: {e}")

    @classmethod
    def _perform_enhanced_security_validation(
        cls,
        file_metadata: dict,
        exif_results: dict
    ) -> dict:
        """
        Perform enhanced security validation using EXIF context.

        Args:
            file_metadata: Standard file validation results
            exif_results: EXIF analysis results

        Returns:
            dict: Enhanced security validation results
        """
        security_result = {
            'validation_passed': True,
            'security_score': 1.0,
            'security_warnings': [],
            'fraud_risk_level': 'low'
        }

        try:
            # Check authenticity score
            authenticity_score = exif_results.get('authenticity_score', 1.0)
            if authenticity_score < 0.3:
                security_result['validation_passed'] = False
                security_result['fraud_risk_level'] = 'high'
                security_result['security_warnings'].append(
                    'Photo authenticity score below acceptable threshold'
                )

            # Check for manipulation indicators
            fraud_indicators = exif_results.get('fraud_indicators', [])
            if len(fraud_indicators) > 2:
                security_result['fraud_risk_level'] = 'high'
                security_result['security_warnings'].append(
                    f'Multiple fraud indicators detected: {", ".join(fraud_indicators)}'
                )

            # Check GPS validation if available
            location_validation = exif_results.get('location_validation', {})
            if location_validation.get('authenticity_risk') == 'high':
                security_result['fraud_risk_level'] = 'high'
                security_result['security_warnings'].append(
                    'GPS location validation failed - possible spoofing detected'
                )

            # Calculate overall security score
            base_score = 1.0
            if authenticity_score < 0.5:
                base_score -= 0.4
            if len(fraud_indicators) > 1:
                base_score -= 0.3
            if location_validation.get('authenticity_risk') in ['high', 'medium']:
                base_score -= 0.2

            security_result['security_score'] = max(0.0, base_score)

            return security_result

        except Exception as e:
            logger.warning(f"Enhanced security validation failed: {e}")
            return {
                'validation_passed': True,
                'security_score': 0.5,
                'security_warnings': [f'Security validation error: {str(e)}'],
                'fraud_risk_level': 'unknown'
            }

    @classmethod
    def _assess_upload_authenticity(
        cls,
        exif_results: dict,
        expected_location: Point,
        upload_context: dict
    ) -> dict:
        """
        Assess overall upload authenticity combining multiple factors.

        Args:
            exif_results: EXIF analysis results
            expected_location: Expected GPS location
            upload_context: Upload context information

        Returns:
            dict: Comprehensive authenticity assessment
        """
        try:
            authenticity_score = exif_results.get('authenticity_score', 0.5)
            fraud_indicators = exif_results.get('fraud_indicators', [])

            # Base risk assessment
            if authenticity_score >= 0.8 and len(fraud_indicators) == 0:
                risk_level = 'low'
            elif authenticity_score >= 0.6 and len(fraud_indicators) <= 1:
                risk_level = 'medium'
            else:
                risk_level = 'high'

            # Location validation impact
            location_validation = exif_results.get('location_validation', {})
            if location_validation.get('authenticity_risk') == 'high':
                risk_level = 'high'

            # Security analysis impact
            security_analysis = exif_results.get('security_analysis', {})
            if security_analysis.get('manipulation_risk') == 'high':
                risk_level = 'high'

            return {
                'authenticity_score': authenticity_score,
                'risk_level': risk_level,
                'fraud_indicators': fraud_indicators,
                'location_validated': bool(location_validation),
                'recommendations': exif_results.get('recommendations', []),
                'requires_manual_review': (risk_level == 'high')
            }

        except Exception as e:
            logger.warning(f"Authenticity assessment failed: {e}")
            return {
                'authenticity_score': 0.5,
                'risk_level': 'unknown',
                'fraud_indicators': [],
                'location_validated': False,
                'recommendations': ['Manual review recommended due to assessment error'],
                'requires_manual_review': True
            }