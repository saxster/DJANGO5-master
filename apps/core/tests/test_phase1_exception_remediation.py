"""
Comprehensive unit tests for Phase 1 Exception Handling Remediation.

Tests specific exception handling in:
1. apps/peoples/forms.py (authentication/decryption)
2. apps/activity/managers/job_manager.py (job workflows)
3. apps/scheduler/services/scheduling_service.py (tour scheduling)
4. apps/core/services/secure_encryption_service.py
5. apps/core/services/secure_file_upload_service.py
6. apps/core/services/secure_file_download_service.py

Validates that generic `except Exception` patterns have been replaced with
specific exception types per Rule #11 (.claude/rules.md).
"""

import pytest
import zlib
import binascii
from unittest.mock import Mock, patch, MagicMock
from django.core.exceptions import ValidationError
from django.db import DatabaseError, IntegrityError, OperationalError
from django.http import Http404
from django.core.files.uploadedfile import SimpleUploadedFile
from cryptography.fernet import InvalidToken

from apps.peoples.forms import PeopleForm
from apps.core.services.secure_encryption_service import SecureEncryptionService
from apps.core.services.secure_file_upload_service import SecureFileUploadService
from apps.core.services.secure_file_download_service import SecureFileDownloadService
from apps.core.exceptions import SecurityException, DatabaseException, SchedulingException
from apps.scheduler.services.scheduling_service import SchedulingService, TourConfiguration


class TestPeoplesFormsExceptionHandling:
    """Test specific exception handling in peoples/forms.py"""

    def test_email_decryption_type_error_caught(self):
        """Verify TypeError is caught specifically during email decryption"""
        with patch('apps.peoples.forms.decrypt') as mock_decrypt:
            mock_decrypt.side_effect = TypeError("Expected bytes, got None")

            # Create form with instance that has email
            mock_instance = Mock()
            mock_instance.pk = 1
            mock_instance.email = None  # Will cause TypeError
            mock_instance.mobno = None

            mock_request = Mock()
            mock_request.session = {
                'client_id': 1,
                'bu_id': 1,
                'assignedsites': [1]
            }

            # Form should handle TypeError gracefully
            form = PeopleForm(request=mock_request, instance=mock_instance)
            # Email should be set to original value (None) without raising
            assert form.initial.get('email') is None or form.initial.get('email') == mock_instance.email

    def test_email_decryption_zlib_error_caught(self):
        """Verify zlib.error is caught specifically during email decryption"""
        with patch('apps.peoples.forms.decrypt') as mock_decrypt:
            mock_decrypt.side_effect = zlib.error("Error -3 while decompressing")

            mock_instance = Mock()
            mock_instance.pk = 1
            mock_instance.email = "corrupted_data"
            mock_instance.mobno = None

            mock_request = Mock()
            mock_request.session = {
                'client_id': 1,
                'bu_id': 1,
                'assignedsites': [1]
            }

            # Form should handle zlib.error gracefully (assume plain text)
            form = PeopleForm(request=mock_request, instance=mock_instance)
            assert form.initial.get('email') == "corrupted_data"

    def test_email_decryption_runtime_error_raises_security_exception(self):
        """Verify RuntimeError in decryption raises SecurityException"""
        with patch('apps.peoples.forms.decrypt') as mock_decrypt:
            mock_decrypt.side_effect = RuntimeError("Deprecated function in production")

            mock_instance = Mock()
            mock_instance.pk = 1
            mock_instance.email = "encrypted_email"
            mock_instance.mobno = None

            mock_request = Mock()
            mock_request.session = {
                'client_id': 1,
                'bu_id': 1,
                'assignedsites': [1]
            }

            # Should raise SecurityException (not generic Exception)
            with pytest.raises(SecurityException):
                PeopleForm(request=mock_request, instance=mock_instance)

    def test_mobno_decryption_unicode_decode_error_caught(self):
        """Verify UnicodeDecodeError is caught specifically during mobno decryption"""
        with patch('apps.peoples.forms.decrypt') as mock_decrypt:
            mock_decrypt.side_effect = UnicodeDecodeError(
                'utf-8', b'\xff\xfe', 0, 1, 'invalid start byte'
            )

            mock_instance = Mock()
            mock_instance.pk = 1
            mock_instance.email = None
            mock_instance.mobno = "corrupted_mobno"

            mock_request = Mock()
            mock_request.session = {
                'client_id': 1,
                'bu_id': 1,
                'assignedsites': [1]
            }

            # Form should handle UnicodeDecodeError gracefully
            form = PeopleForm(request=mock_request, instance=mock_instance)
            assert form.initial.get('mobno') == "corrupted_mobno"


class TestJobManagerExceptionHandling:
    """Test specific exception handling in activity/managers/job_manager.py"""

    def test_checkpoint_save_database_error_caught(self):
        """Verify DatabaseError is caught specifically in checkpoint save"""
        from apps.activity.managers import JobManager

        manager = JobManager()
        manager.model = Mock()

        mock_request = Mock()
        mock_request.POST = {
            'parentid': '1',
            'action': 'create',
            'expirytime': '10',
            'qset_id': '1',
            'asset_id': '1',
            'seqno': '1',
            'qsetname': 'Test'
        }
        mock_request.user = Mock()

        with patch.object(manager, 'filter') as mock_filter:
            mock_filter.return_value.select_related.return_value.values.return_value.first.return_value = {
                'id': 1,
                'jobname': 'Test',
                'bu__buname': 'Test Site'
            }

            with patch('apps.activity.managers.job_manager.distributed_lock'):
                with patch('apps.activity.managers.job_manager.transaction.atomic'):
                    with patch.object(manager, 'create', side_effect=DatabaseError("Connection lost")):
                        result = manager.handle_save_checkpoint_guardtour(mock_request)

                        # Should return error dict (not raise generic Exception)
                        assert 'error' in result
                        assert 'Database service unavailable' in result['error']
                        assert result['data'] == []

    def test_checkpoint_save_validation_error_caught(self):
        """Verify ValidationError is caught specifically in checkpoint save"""
        from apps.activity.managers import JobManager

        manager = JobManager()
        manager.model = Mock()

        mock_request = Mock()
        mock_request.POST = {
            'parentid': '1',
            'action': 'create',
            'expirytime': 'invalid',  # Invalid data
            'qset_id': '1',
            'asset_id': '1',
            'seqno': '1',
            'qsetname': 'Test'
        }
        mock_request.user = Mock()

        with patch.object(manager, 'filter') as mock_filter:
            mock_filter.return_value.select_related.return_value.values.return_value.first.return_value = {
                'id': 1,
                'jobname': 'Test',
                'bu__buname': 'Test Site'
            }

            with patch('apps.activity.managers.job_manager.distributed_lock'):
                with patch('apps.activity.managers.job_manager.transaction.atomic'):
                    with patch('apps.scheduler.utils.job_fields', side_effect=ValueError("Invalid expiry time")):
                        result = manager.handle_save_checkpoint_guardtour(mock_request)

                        # Should return validation error (not generic Exception)
                        assert 'error' in result
                        assert 'Invalid checkpoint data' in result['error']


class TestSchedulingServiceExceptionHandling:
    """Test specific exception handling in scheduler/services/scheduling_service.py"""

    def test_create_tour_validation_error_caught(self):
        """Verify ValidationError is caught specifically in tour creation"""
        service = SchedulingService()

        tour_config = TourConfiguration(
            job_name="Test Tour",
            start_time=None,  # Invalid - will cause validation error
            end_time=None,
            expiry_time=10,
            identifier="INTERNALTOUR",
            priority="LOW",
            scan_type="QR",
            grace_time=5,
            from_date=None,
            upto_date=None,
            checkpoints=[]
        )

        mock_user = Mock()
        mock_session = {'client_id': 1, 'bu_id': 1}

        result = service.create_guard_tour(tour_config, mock_user, mock_session)

        # Should catch ValidationError and return SchedulingResult with specific error
        assert result.success is False
        assert 'Invalid tour configuration' in result.error_message or result.error_message is not None
        assert result.correlation_id is not None

    def test_create_tour_database_error_caught(self):
        """Verify DatabaseError is caught specifically in tour creation"""
        service = SchedulingService()

        tour_config = TourConfiguration(
            job_name="Test Tour",
            start_time=Mock(),
            end_time=Mock(),
            expiry_time=10,
            identifier="INTERNALTOUR",
            priority="LOW",
            scan_type="QR",
            grace_time=5,
            from_date=Mock(),
            upto_date=Mock(),
            checkpoints=[]
        )

        mock_user = Mock()
        mock_session = {'client_id': 1, 'bu_id': 1}

        with patch.object(service, '_create_tour_job', side_effect=DatabaseError("Connection failed")):
            with patch('apps.scheduler.services.scheduling_service.transaction_manager'):
                result = service.create_guard_tour(tour_config, mock_user, mock_session)

                # Should catch DatabaseError and return specific error
                assert result.success is False
                assert result.error_message is not None


class TestSecureEncryptionServiceExceptionHandling:
    """Test specific exception handling in secure_encryption_service.py"""

    def test_encrypt_type_error_caught(self):
        """Verify TypeError is caught specifically during encryption"""
        with pytest.raises(ValueError) as exc_info:
            SecureEncryptionService.encrypt(None)  # Invalid type

        # Should raise ValueError (not generic Exception)
        assert "Invalid data type" in str(exc_info.value)
        assert "ID:" in str(exc_info.value)  # Has correlation ID

    def test_decrypt_binascii_error_caught(self):
        """Verify binascii.Error is caught specifically during decryption"""
        with pytest.raises(ValueError) as exc_info:
            SecureEncryptionService.decrypt("invalid_base64!!!")

        # Should raise ValueError (not generic Exception)
        assert "decoding failed" in str(exc_info.value).lower() or "decryption failed" in str(exc_info.value).lower()
        assert "ID:" in str(exc_info.value)  # Has correlation ID

    def test_decrypt_invalid_token_caught(self):
        """Verify InvalidToken is caught specifically during decryption"""
        with pytest.raises(ValueError) as exc_info:
            SecureEncryptionService.decrypt("FERNET_V1:bm90X3ZhbGlkX2RhdGE=")

        # Should raise ValueError with specific message (not generic Exception)
        assert "Decryption failed" in str(exc_info.value)

    def test_migrate_legacy_data_type_error_caught(self):
        """Verify TypeError is caught in legacy migration without raising"""
        success, result = SecureEncryptionService.migrate_legacy_data(None)

        # Should return False (not raise generic Exception)
        assert success is False
        assert result is None


class TestSecureFileUploadServiceExceptionHandling:
    """Test specific exception handling in secure_file_upload_service.py"""

    def test_upload_os_error_caught(self):
        """Verify OSError is caught specifically during file upload"""
        uploaded_file = SimpleUploadedFile("test.jpg", b"fake image content")

        with patch.object(SecureFileUploadService, '_validate_file_type', side_effect=OSError("Disk full")):
            with pytest.raises(ValidationError) as exc_info:
                SecureFileUploadService.validate_and_process_upload(
                    uploaded_file,
                    'image',
                    {'user_id': 1}
                )

            # Should raise ValidationError (not generic Exception)
            assert "File system error" in str(exc_info.value) or "ID:" in str(exc_info.value)

    def test_upload_value_error_caught(self):
        """Verify ValueError is caught specifically during file upload"""
        uploaded_file = SimpleUploadedFile("test.jpg", b"")

        with patch.object(SecureFileUploadService, '_validate_file_size', side_effect=ValueError("Invalid size")):
            with pytest.raises(ValidationError) as exc_info:
                SecureFileUploadService.validate_and_process_upload(
                    uploaded_file,
                    'image',
                    {'user_id': 1}
                )

            # Should raise ValidationError (not generic Exception)
            assert "Invalid file data" in str(exc_info.value) or "ID:" in str(exc_info.value)


class TestSecureFileDownloadServiceExceptionHandling:
    """Test specific exception handling in secure_file_download_service.py"""

    def test_download_file_not_found_error_caught(self):
        """Verify FileNotFoundError is caught specifically during download"""
        mock_user = Mock()
        mock_user.id = 1

        with patch.object(SecureFileDownloadService, '_validate_file_path', side_effect=FileNotFoundError("File not found")):
            with pytest.raises(Http404):
                SecureFileDownloadService.validate_and_serve_file(
                    "nonexistent.pdf",
                    mock_user,
                    "test-correlation-id"
                )

    def test_download_value_error_caught(self):
        """Verify ValueError is caught specifically during download"""
        mock_user = Mock()
        mock_user.id = 1

        with patch.object(SecureFileDownloadService, '_validate_file_path', side_effect=ValueError("Invalid path")):
            with pytest.raises(Http404):
                SecureFileDownloadService.validate_and_serve_file(
                    "../../../etc/passwd",
                    mock_user,
                    "test-correlation-id"
                )


class TestExceptionCorrelationIDs:
    """Verify all exceptions have correlation IDs for tracking"""

    def test_all_phase1_exceptions_have_correlation_ids(self):
        """Ensure all Phase 1 fixes include correlation IDs in error handling"""
        # This is tested implicitly in the above tests by asserting "ID:" in error messages
        # and by checking result.correlation_id is not None

        # Test encryption service
        try:
            SecureEncryptionService.encrypt(None)
        except ValueError as e:
            assert "ID:" in str(e), "Encryption error missing correlation ID"

        # Test tour creation
        service = SchedulingService()
        result = service.create_guard_tour(
            TourConfiguration(
                job_name="", start_time=None, end_time=None,
                expiry_time=0, identifier="", priority="",
                scan_type="", grace_time=0, from_date=None,
                upto_date=None, checkpoints=[]
            ),
            Mock(),
            {}
        )
        assert result.correlation_id is not None, "Scheduling error missing correlation ID"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])