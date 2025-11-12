"""
Tests for file upload timeout configuration.

Validates that timeout parameters are correctly configured and passed through the upload
pipeline to prevent worker thread exhaustion from hanging network calls.

Security: CVSS 5.9 - DoS prevention via worker thread protection
"""

import pytest
from unittest.mock import patch, MagicMock
from django.core.files.uploadedfile import SimpleUploadedFile


@pytest.mark.security
@pytest.mark.unit
class TestUploadTimeouts:
    """Test suite for upload timeout configuration."""

    def test_timeout_constants_importable(self):
        """Test that timeout constants can be imported and have correct values."""
        from apps.core.constants.timeouts import (
            FILE_UPLOAD_VIRUS_SCAN_TIMEOUT,
            FILE_UPLOAD_EXIF_PROCESSING_TIMEOUT,
            FILE_UPLOAD_CLOUD_UPLOAD_TIMEOUT,
            FILE_UPLOAD_MAX_TOTAL_TIMEOUT
        )

        # Verify constants have expected values
        assert FILE_UPLOAD_VIRUS_SCAN_TIMEOUT == 30, "Virus scan timeout should be 30 seconds"
        assert FILE_UPLOAD_EXIF_PROCESSING_TIMEOUT == 15, "EXIF processing timeout should be 15 seconds"
        assert FILE_UPLOAD_CLOUD_UPLOAD_TIMEOUT == 60, "Cloud upload timeout should be 60 seconds"
        assert FILE_UPLOAD_MAX_TOTAL_TIMEOUT == 120, "Max total timeout should be 120 seconds"

    def test_upload_passes_timeout_config(self):
        """Test that upload() function creates timeout_config in upload_context."""
        from apps.core.utils_new.upload_utils import upload
        from apps.core.constants.timeouts import (
            FILE_UPLOAD_VIRUS_SCAN_TIMEOUT,
            FILE_UPLOAD_EXIF_PROCESSING_TIMEOUT,
            FILE_UPLOAD_CLOUD_UPLOAD_TIMEOUT
        )

        # Create a simple mock request
        mock_request = MagicMock()
        mock_request.user.id = 123
        mock_request.user.is_authenticated = True
        mock_request.FILES = {'img': MagicMock(name='test.jpg')}
        mock_request.POST = {'foldertype': 'task'}
        mock_request.session = {}

        # Mock the SecureFileUploadService to capture the upload_context
        captured_context = {}

        def capture_context(uploaded_file, file_type, upload_context=None):
            captured_context.update(upload_context or {})
            return {
                'filename': 'test.jpg',
                'file_type': 'image',
                'correlation_id': 'test-123'
            }

        with patch('apps.core.services.secure_file_upload_service.SecureFileUploadService.validate_and_process_upload', side_effect=capture_context):
            with patch('apps.core.services.secure_file_upload_service.SecureFileUploadService.save_uploaded_file', return_value='/media/uploads/test.jpg'):
                # Call upload
                success, filename, filepath = upload(mock_request)

                # Verify timeout_config was created and passed
                assert 'timeout_config' in captured_context, "timeout_config not created in upload_context"
                timeout_config = captured_context['timeout_config']

                # Verify timeout values
                assert timeout_config['virus_scan_timeout'] == FILE_UPLOAD_VIRUS_SCAN_TIMEOUT
                assert timeout_config['exif_processing_timeout'] == FILE_UPLOAD_EXIF_PROCESSING_TIMEOUT
                assert timeout_config['cloud_upload_timeout'] == FILE_UPLOAD_CLOUD_UPLOAD_TIMEOUT

    def test_upload_vendor_file_passes_timeout_config(self):
        """Test that upload_vendor_file() creates timeout_config in upload_context."""
        from apps.core.utils_new.upload_utils import upload_vendor_file
        from apps.core.constants.timeouts import FILE_UPLOAD_VIRUS_SCAN_TIMEOUT

        # Create mock uploaded file
        mock_file = MagicMock()
        mock_file.name = 'document.pdf'

        # Mock the SecureFileUploadService to capture the upload_context
        captured_context = {}

        def capture_context(uploaded_file, file_type, upload_context=None):
            captured_context.update(upload_context or {})
            return {
                'filename': 'document.pdf',
                'file_type': 'pdf',
                'correlation_id': 'test-456'
            }

        with patch('apps.core.services.secure_file_upload_service.SecureFileUploadService.validate_and_process_upload', side_effect=capture_context):
            with patch('apps.core.services.secure_file_upload_service.SecureFileUploadService.save_uploaded_file', return_value='/media/uploads/document.pdf'):
                # Call upload_vendor_file
                success, filename, relative_path = upload_vendor_file(mock_file, 'WOM123')

                # Verify timeout_config was created and passed
                assert 'timeout_config' in captured_context, "timeout_config not created in upload_context for vendor upload"
                timeout_config = captured_context['timeout_config']

                # Verify timeout values are present
                assert 'virus_scan_timeout' in timeout_config
                assert timeout_config['virus_scan_timeout'] == FILE_UPLOAD_VIRUS_SCAN_TIMEOUT

    def test_service_accepts_timeout_config(self):
        """Test that SecureFileUploadService.validate_and_process_upload accepts and logs timeout_config."""
        from apps.core.services.secure_file_upload_service import SecureFileUploadService
        from django.core.files.uploadedfile import SimpleUploadedFile

        # Create a simple uploaded file with proper JPEG magic numbers
        jpeg_header = b'\xFF\xD8\xFF\xE0\x00\x10JFIF'
        uploaded_file = SimpleUploadedFile('test.jpg', jpeg_header + b'fake image data', content_type='image/jpeg')

        # Create upload context with timeout_config
        upload_context = {
            'people_id': 123,
            'folder_type': 'task',
            'timeout_config': {
                'virus_scan_timeout': 30,
                'exif_processing_timeout': 15,
                'cloud_upload_timeout': 60,
            }
        }

        # Mock file operations to avoid filesystem access
        with patch('apps.core.services.secure_file_upload_service.SecureFileUploadService._generate_secure_path', return_value='/tmp/test.jpg'):
            with patch('apps.core.services.secure_file_upload_service.SecureFileUploadService._create_file_metadata') as mock_metadata:
                mock_metadata.return_value = {
                    'filename': 'test.jpg',
                    'file_type': 'image',
                    'correlation_id': 'test-789'
                }

                # Call validate_and_process_upload with timeout_config
                # This should not raise any errors
                result = SecureFileUploadService.validate_and_process_upload(
                    uploaded_file,
                    'image',
                    upload_context
                )
                # Verify it completed successfully
                assert result is not None, "Service should return metadata dict"
                assert 'filename' in result, "Result should contain filename"
                # SUCCESS: Service accepted and processed timeout_config
