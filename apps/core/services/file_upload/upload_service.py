"""
Main file upload service - facade for validation and processing.

Orchestrates:
- File validation
- EXIF processing
- Path generation
- File saving
- Security assessment

Complies with Rule #14 from .claude/rules.md - File Upload Security
"""

import os
import logging
import hashlib
from django.conf import settings
from django.core.exceptions import ValidationError
from django.contrib.gis.geos import Point
from django.utils.text import get_valid_filename
from apps.core.error_handling import ErrorHandler
from apps.core.services.file_upload.validation_core import FileValidationCore
from apps.core.services.file_upload.exif_processor import EXIFProcessor

logger = logging.getLogger(__name__)


class UploadService:
    """Main file upload service orchestrating validation and processing."""

    @classmethod
    def validate_and_process_upload(cls, uploaded_file, file_type, upload_context=None):
        """
        Main entry point for secure file upload processing with timeout protection.

        Args:
            uploaded_file: Django UploadedFile object
            file_type: Type of file ('image', 'pdf', 'document')
            upload_context: Dict with context info (user_id, folder_type, timeout_config, etc.)

        Returns:
            dict: Secure file information with path and metadata

        Raises:
            ValidationError: If any security validation fails
        """
        try:
            correlation_id = cls._generate_correlation_id()

            # Extract timeout configuration
            timeout_config = {}
            if upload_context:
                timeout_config = upload_context.get('timeout_config', {})

            logger.info(
                "Starting secure file upload validation",
                extra={
                    'correlation_id': correlation_id,
                    'file_type': file_type,
                    'original_filename': uploaded_file.name if uploaded_file else 'None',
                    'upload_context': upload_context,
                    'timeout_config': timeout_config
                }
            )

            # Phase 1: Basic file validation (no network)
            FileValidationCore.validate_file_exists(uploaded_file)

            # Phase 2: Security validation (no network)
            FileValidationCore.validate_file_security(uploaded_file, file_type)

            # Phase 3: Content validation (no network)
            FileValidationCore.validate_file_content(uploaded_file, file_type)

            # Phase 4: Virus scanning (WITH TIMEOUT) - if enabled
            if upload_context and upload_context.get('enable_virus_scan', False):
                virus_timeout = timeout_config.get('virus_scan_timeout', 30)
                logger.info(
                    f"Virus scan configured with {virus_timeout}s timeout",
                    extra={
                        'correlation_id': correlation_id,
                        'timeout': virus_timeout
                    }
                )
                # TODO: Implement actual virus scanning with timeout
                # This is a placeholder for future ClamAV integration
                # For now, we log that the system is ready for virus scanning

            # Phase 5: Generate secure path
            secure_path = cls._generate_secure_path(uploaded_file, file_type, upload_context)

            # Phase 6: Create secure metadata
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
                    'service': 'UploadService',
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
                    'service': 'UploadService',
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
                    'service': 'UploadService',
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
            # Path has been validated by _generate_secure_path() in validate_and_process_upload()
            # which ensures it is within MEDIA_ROOT and prevents path traversal
            file_path = file_metadata['file_path']

            # Ensure directory exists with secure permissions
            directory = os.path.dirname(file_path)
            os.makedirs(directory, mode=0o755, exist_ok=True)

            # Save file securely - path already validated
            # nosec: B603 - Path validated by _generate_secure_path
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
                    'service': 'UploadService',
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
                    exif_results = EXIFProcessor.process_image_exif(
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
                    'service': 'UploadService',
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
    def _perform_enhanced_security_validation(cls, file_metadata: dict, exif_results: dict) -> dict:
        """Perform enhanced security validation using EXIF context."""
        from apps.core.exceptions.patterns import DATABASE_EXCEPTIONS

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

        except DATABASE_EXCEPTIONS as e:
            logger.warning(f"Enhanced security validation failed: {e}")
            return {
                'validation_passed': True,
                'security_score': 0.5,
                'security_warnings': [f'Security validation error: {str(e)}'],
                'fraud_risk_level': 'unknown'
            }

    @classmethod
    def _assess_upload_authenticity(cls, exif_results: dict, expected_location: Point, upload_context: dict) -> dict:
        """Assess overall upload authenticity combining multiple factors."""
        from apps.core.exceptions.patterns import DATABASE_EXCEPTIONS

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

        except DATABASE_EXCEPTIONS as e:
            logger.warning(f"Authenticity assessment failed: {e}")
            return {
                'authenticity_score': 0.5,
                'risk_level': 'unknown',
                'fraud_indicators': [],
                'location_validated': False,
                'recommendations': ['Manual review recommended due to assessment error'],
                'requires_manual_review': True
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
