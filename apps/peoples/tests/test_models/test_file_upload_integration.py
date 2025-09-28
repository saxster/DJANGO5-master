"""
File Upload Integration Tests

Tests comprehensive integration between the backward-compatible upload_peopleimg()
function and the new SecureFileUploadService.

Verifies:
- Path traversal prevention
- Filename sanitization
- Extension validation
- Service delegation
- Error handling and fallback
- Security compliance with Rule #14
"""

import pytest
from django.core.exceptions import ValidationError
from unittest.mock import Mock, patch


class TestFileUploadIntegration:
    """Test integration of file upload with security service."""

    def test_upload_generates_secure_path(self, mock_people_with_client):
        """Verify secure path generation works end-to-end"""
        from apps.peoples.models import upload_peopleimg
        import warnings

        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            result = upload_peopleimg(mock_people_with_client, "profile.jpg")

        # Should generate secure path
        assert isinstance(result, str)
        assert ".." not in result  # No path traversal
        assert result.startswith("master/")  # Correct base path
        assert result.endswith(".jpg")  # Correct extension

    def test_dangerous_filenames_sanitized(self, mock_people_with_client):
        """Verify dangerous filenames are properly sanitized"""
        from apps.peoples.models import upload_peopleimg
        import warnings

        dangerous_names = [
            "../../../etc/passwd",
            "test/../../secret.jpg",
            "file\x00.jpg",
            "..\\..\\windows\\system32\\file.jpg"
        ]

        for dangerous_name in dangerous_names:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                result = upload_peopleimg(mock_people_with_client, dangerous_name)

            # Should either sanitize or return default
            assert ".." not in result
            assert "/" not in result.split("master/")[-1].split("/people/")[-1]  # No path separators in filename

    def test_invalid_extensions_rejected(self, mock_people_with_client):
        """Verify invalid file extensions are rejected or handled"""
        from apps.peoples.models import upload_peopleimg
        import warnings

        invalid_files = [
            "malware.exe",
            "script.php",
            "backdoor.sh",
            "virus.bat"
        ]

        for invalid_file in invalid_files:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                result = upload_peopleimg(mock_people_with_client, invalid_file)

            # Should return default/fallback or raise error
            assert result == "master/people/blank.png" or result.endswith(('.jpg', '.jpeg', '.png', '.gif', '.webp'))


@pytest.fixture
def mock_people_with_client():
    """Create mock People instance with client for upload tests"""
    mock_instance = Mock()
    mock_instance.id = 123
    mock_instance.peoplecode = "EMP001"
    mock_instance.peoplename = "John Doe"
    mock_instance.client_id = 1

    mock_client = Mock()
    mock_client.id = 1
    mock_client.bucode = "ACME"
    mock_instance.client = mock_client

    return mock_instance


class TestSecureFileUploadService:
    """Test SecureFileUploadService directly"""

    def test_service_rejects_path_traversal(self):
        """Verify service rejects path traversal attempts"""
        from apps.peoples.services.file_upload_service import SecureFileUploadService

        mock_instance = Mock()
        mock_instance.peoplecode = "TEST"
        mock_instance.peoplename = "Test"

        with pytest.raises(ValidationError):
            SecureFileUploadService._sanitize_filename("../../../etc/passwd")

    def test_service_validates_extensions(self):
        """Verify service validates file extensions"""
        from apps.peoples.services.file_upload_service import SecureFileUploadService

        # Valid extensions should pass
        for ext in ['.jpg', '.jpeg', '.png', '.gif', '.webp']:
            result = SecureFileUploadService._validate_file_extension(f"file{ext}")
            assert result == ext.lower()

        # Invalid extensions should fail
        with pytest.raises(ValidationError):
            SecureFileUploadService._validate_file_extension("malware.exe")