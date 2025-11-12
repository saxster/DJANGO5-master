import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import RequestFactory
from apps.core.middleware.input_sanitization_middleware import InputSanitizationMiddleware
from apps.core.exceptions import SecurityException


@pytest.mark.security
class TestFileContentValidation:

    def test_double_extension_blocked(self, rf):
        """Test double extension files are blocked."""
        middleware = InputSanitizationMiddleware(lambda r: r)

        # Malicious file with double extension
        malicious_file = SimpleUploadedFile(
            'resume.pdf.exe',
            b'MZ\x90\x00',  # PE executable header
            content_type='application/pdf'
        )

        request = rf.post('/upload/', {'file': malicious_file})

        # Should raise SecurityException
        with pytest.raises(SecurityException) as exc:
            middleware._sanitize_file_uploads(request)

        # Either blocked for dangerous extension or unsupported file type
        assert ('dangerous extension' in str(exc.value).lower() or
                'unsupported file type' in str(exc.value).lower())

    def test_executable_content_blocked(self, rf):
        """Test executable content detected by magic numbers."""
        middleware = InputSanitizationMiddleware(lambda r: r)

        # File with .jpg extension but EXE content
        spoofed_file = SimpleUploadedFile(
            'image.jpg',
            b'MZ\x90\x00\x03',  # Windows PE header
            content_type='image/jpeg'
        )

        request = rf.post('/upload/', {'file': spoofed_file})

        with pytest.raises(SecurityException) as exc:
            middleware._sanitize_file_uploads(request)

        # Should catch content validation failure
        assert ('validation failed' in str(exc.value).lower() or
                'content does not match' in str(exc.value).lower() or
                'invalid file type' in str(exc.value).lower())

    def test_valid_image_passes_validation(self, rf):
        """Test valid image file passes all validation."""
        middleware = InputSanitizationMiddleware(lambda r: r)

        # Valid JPEG file
        valid_image = SimpleUploadedFile(
            'photo.jpg',
            b'\xFF\xD8\xFF\xE0',  # JPEG magic number
            content_type='image/jpeg'
        )

        request = rf.post('/upload/', {'file': valid_image})

        # Should not raise exception
        try:
            middleware._sanitize_file_uploads(request)
        except SecurityException as e:
            pytest.fail(f"Valid file blocked: {e}")
