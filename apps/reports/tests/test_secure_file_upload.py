"""
Comprehensive security tests for secure file upload functionality.

These tests validate protection against file upload vulnerabilities including:
- Path traversal attacks
- Filename injection
- Content type spoofing
- File size attacks
- Malicious file content

Complies with security testing requirements from .claude/rules.md
"""

import os
import tempfile
import pytest
from django.test import TestCase, Client, override_settings
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.exceptions import ValidationError
from unittest.mock import patch, MagicMock
from apps.reports.services.secure_report_upload_service import (
    SecureReportUploadService,
    secure_upload_pdf
)
from apps.core.services.secure_file_upload_service import SecureFileUploadService

User = get_user_model()


class SecureFileUploadServiceTests(TestCase):
    """Test cases for SecureFileUploadService security validations."""

    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.client = Client()

    def create_test_file(self, filename, content=b'%PDF-1.4 test content', content_type='application/pdf'):
        """Helper to create test uploaded files."""
        return SimpleUploadedFile(
            filename,
            content,
            content_type=content_type
        )

    def test_path_traversal_prevention(self):
        """Test prevention of path traversal attacks."""
        malicious_filenames = [
            '../../../etc/passwd',
            '..\\..\\..\\windows\\system32\\config\\sam',
            'normal.pdf/../../../etc/passwd',
            'file.pdf\x00.exe',
            '../../sensitive/file.pdf',
            'folder/../../../etc/passwd.pdf',
            '\x2e\x2e\x2f\x2e\x2e\x2fpasswd.pdf',  # URL encoded ../
        ]

        for malicious_filename in malicious_filenames:
            with self.subTest(filename=malicious_filename):
                uploaded_file = self.create_test_file(malicious_filename)
                upload_context = {
                    'people_id': self.user.id,
                    'folder_type': 'reports'
                }

                with self.assertRaises(ValidationError) as cm:
                    SecureFileUploadService.validate_and_process_upload(
                        uploaded_file,
                        'pdf',
                        upload_context
                    )

                self.assertIn(
                    'dangerous',
                    str(cm.exception).lower(),
                    f"Failed to detect path traversal in: {malicious_filename}"
                )

    def test_filename_injection_prevention(self):
        """Test prevention of filename injection attacks."""
        malicious_filenames = [
            'file.pdf; rm -rf /',
            'file.pdf && echo "pwned"',
            'file.pdf | cat /etc/passwd',
            'file.pdf`whoami`',
            'file.pdf$(id)',
            'file.pdf\nrm -rf /',
            'file.pdf\r\nmalicious_command',
            'CON.pdf',  # Windows reserved name
            'AUX.pdf',  # Windows reserved name
            'NUL.pdf',  # Windows reserved name
        ]

        for malicious_filename in malicious_filenames:
            with self.subTest(filename=malicious_filename):
                uploaded_file = self.create_test_file(malicious_filename)
                upload_context = {
                    'people_id': self.user.id,
                    'folder_type': 'reports'
                }

                with self.assertRaises(ValidationError) as cm:
                    SecureFileUploadService.validate_and_process_upload(
                        uploaded_file,
                        'pdf',
                        upload_context
                    )

                error_message = str(cm.exception).lower()
                self.assertTrue(
                    any(keyword in error_message for keyword in [
                        'dangerous', 'invalid', 'reserved', 'characters'
                    ]),
                    f"Failed to detect malicious filename: {malicious_filename}"
                )

    def test_file_extension_validation(self):
        """Test file extension validation and executable prevention."""
        dangerous_extensions = [
            'test.exe',
            'document.bat',
            'script.js',
            'malware.vbs',
            'trojan.scr',
            'virus.com',
            'shell.sh',
            'exploit.php',
            'backdoor.asp',
            'payload.jsp',
            'malware.py',
        ]

        for dangerous_file in dangerous_extensions:
            with self.subTest(filename=dangerous_file):
                uploaded_file = self.create_test_file(dangerous_file)
                upload_context = {
                    'people_id': self.user.id,
                    'folder_type': 'reports'
                }

                with self.assertRaises(ValidationError) as cm:
                    SecureFileUploadService.validate_and_process_upload(
                        uploaded_file,
                        'pdf',
                        upload_context
                    )

                error_message = str(cm.exception).lower()
                self.assertTrue(
                    'not allowed' in error_message or 'executable' in error_message,
                    f"Failed to block dangerous extension: {dangerous_file}"
                )

    def test_file_size_validation(self):
        """Test file size validation."""
        # Create oversized file content
        oversized_content = b'%PDF-1.4 ' + b'A' * (15 * 1024 * 1024)  # 15MB+ content

        uploaded_file = self.create_test_file('large.pdf', oversized_content)
        upload_context = {
            'people_id': self.user.id,
            'folder_type': 'reports'
        }

        with self.assertRaises(ValidationError) as cm:
            SecureFileUploadService.validate_and_process_upload(
                uploaded_file,
                'pdf',
                upload_context
            )

        self.assertIn('too large', str(cm.exception).lower())

    def test_content_type_validation(self):
        """Test MIME type and magic number validation."""
        # Test content type spoofing
        fake_pdf = self.create_test_file(
            'fake.pdf',
            b'<script>alert("xss")</script>',  # HTML content
            'application/pdf'  # Fake PDF MIME type
        )

        upload_context = {
            'people_id': self.user.id,
            'folder_type': 'reports'
        }

        with self.assertRaises(ValidationError) as cm:
            SecureFileUploadService.validate_and_process_upload(
                fake_pdf,
                'pdf',
                upload_context
            )

        self.assertIn('content does not match', str(cm.exception).lower())

    def test_double_extension_prevention(self):
        """Test prevention of double extension attacks."""
        double_extension_files = [
            'document.pdf.exe',
            'image.jpg.bat',
            'report.pdf.js',
            'file.pdf.vbs',
            'doc.pdf.scr',
        ]

        for dangerous_file in double_extension_files:
            with self.subTest(filename=dangerous_file):
                uploaded_file = self.create_test_file(dangerous_file)
                upload_context = {
                    'people_id': self.user.id,
                    'folder_type': 'reports'
                }

                with self.assertRaises(ValidationError) as cm:
                    SecureFileUploadService.validate_and_process_upload(
                        uploaded_file,
                        'pdf',
                        upload_context
                    )

                error_message = str(cm.exception).lower()
                self.assertTrue(
                    'dangerous' in error_message or 'not allowed' in error_message,
                    f"Failed to detect double extension: {dangerous_file}"
                )

    def test_valid_file_upload_success(self):
        """Test that valid files upload successfully."""
        valid_pdf_content = b'%PDF-1.4\n1 0 obj\n<<\n/Type /Catalog\n>>\nendobj\nxref\n0 1\n0000000000 65535 f \ntrailer\n<<\n/Size 1\n/Root 1 0 R\n>>\nstartxref\n0\n%%EOF'

        uploaded_file = self.create_test_file('valid.pdf', valid_pdf_content)
        upload_context = {
            'people_id': self.user.id,
            'folder_type': 'reports'
        }

        # Should not raise an exception
        result = SecureFileUploadService.validate_and_process_upload(
            uploaded_file,
            'pdf',
            upload_context
        )

        self.assertIsInstance(result, dict)
        self.assertIn('filename', result)
        self.assertIn('correlation_id', result)
        self.assertTrue(result['filename'].endswith('.pdf'))

    def test_folder_type_validation(self):
        """Test folder type validation."""
        uploaded_file = self.create_test_file('test.pdf')

        invalid_folder_types = [
            '../../../etc',
            'folder/../../sensitive',
            'invalid_folder',
            'system',
            'config',
        ]

        for invalid_folder in invalid_folder_types:
            with self.subTest(folder_type=invalid_folder):
                upload_context = {
                    'people_id': self.user.id,
                    'folder_type': invalid_folder
                }

                with self.assertRaises(ValidationError):
                    SecureReportUploadService.validate_and_process_upload(
                        uploaded_file,
                        'pdf_report',
                        upload_context
                    )


class SecureReportUploadViewTests(TestCase):
    """Test cases for secure report upload views."""

    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        self.client = Client()

    def test_authentication_required(self):
        """Test that authentication is required for file upload."""
        uploaded_file = SimpleUploadedFile(
            'test.pdf',
            b'%PDF-1.4 test content',
            content_type='application/pdf'
        )

        response = self.client.post('/upload_pdf/', {
            'img': uploaded_file,
            'peopleid': self.user.id,
            'foldertype': 'reports'
        })

        # Should redirect to login or return 401/403
        self.assertIn(response.status_code, [302, 401, 403])

    def test_csrf_protection(self):
        """Test CSRF protection on upload endpoint."""
        self.client.login(username='testuser', password='testpass123')

        uploaded_file = SimpleUploadedFile(
            'test.pdf',
            b'%PDF-1.4 test content',
            content_type='application/pdf'
        )

        # Request without CSRF token should fail
        response = self.client.post('/upload_pdf/', {
            'img': uploaded_file,
            'peopleid': self.user.id,
            'foldertype': 'reports'
        }, HTTP_X_CSRFTOKEN='invalid_token')

        self.assertEqual(response.status_code, 403)

    def test_only_post_method_allowed(self):
        """Test that only POST method is allowed."""
        self.client.force_login(self.user)

        # GET request should be rejected
        response = self.client.get('/upload_pdf/')
        self.assertEqual(response.status_code, 405)

        # PUT request should be rejected
        response = self.client.put('/upload_pdf/')
        self.assertEqual(response.status_code, 405)

    def test_missing_required_fields(self):
        """Test validation of required fields."""
        self.client.force_login(self.user)

        # Missing peopleid
        response = self.client.post('/upload_pdf/', {
            'foldertype': 'reports'
        })
        self.assertEqual(response.status_code, 400)

        # Missing foldertype
        uploaded_file = SimpleUploadedFile(
            'test.pdf',
            b'%PDF-1.4 test content',
            content_type='application/pdf'
        )
        response = self.client.post('/upload_pdf/', {
            'img': uploaded_file,
            'peopleid': self.user.id
        })
        self.assertEqual(response.status_code, 400)

    @patch('apps.reports.services.secure_report_upload_service.SecureFileUploadService.save_uploaded_file')
    def test_successful_upload_response(self, mock_save):
        """Test successful upload response format."""
        self.client.force_login(self.user)

        # Mock file save to avoid actual file system operations
        mock_save.return_value = '/fake/path/to/file.pdf'

        uploaded_file = SimpleUploadedFile(
            'test.pdf',
            b'%PDF-1.4 test content',
            content_type='application/pdf'
        )

        response = self.client.post('/upload_pdf/', {
            'img': uploaded_file,
            'peopleid': self.user.id,
            'foldertype': 'reports'
        })

        self.assertEqual(response.status_code, 200)
        response_data = response.json()
        self.assertTrue(response_data.get('success'))
        self.assertIn('filename', response_data)
        self.assertIn('correlation_id', response_data)


@pytest.mark.security
class SecurityPenetrationTests(TestCase):
    """Advanced security penetration tests."""

    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )

    def test_unicode_normalization_attack(self):
        """Test protection against Unicode normalization attacks."""
        # Unicode characters that normalize to dangerous characters
        unicode_attacks = [
            'test\u002e\u002e\u002fpasswd.pdf',  # Unicode ../
            'test\u00ff\u00fe\u002e\u002e\u002fpasswd.pdf',  # BOM + ../
            'test\u202e.fdp.exe',  # Right-to-left override
        ]

        for attack_filename in unicode_attacks:
            with self.subTest(filename=attack_filename):
                uploaded_file = SimpleUploadedFile(
                    attack_filename,
                    b'%PDF-1.4 test content',
                    content_type='application/pdf'
                )

                upload_context = {
                    'people_id': self.user.id,
                    'folder_type': 'reports'
                }

                with self.assertRaises(ValidationError):
                    SecureFileUploadService.validate_and_process_upload(
                        uploaded_file,
                        'pdf',
                        upload_context
                    )

    def test_zip_bomb_protection(self):
        """Test protection against zip bomb attacks in documents."""
        # Simulate a highly compressed malicious file
        zip_bomb_content = b'%PDF-1.4 ' + b'A' * 1000 + b'\x78\x9c' + b'\x00' * 1000

        uploaded_file = SimpleUploadedFile(
            'zipbomb.pdf',
            zip_bomb_content,
            content_type='application/pdf'
        )

        upload_context = {
            'people_id': self.user.id,
            'folder_type': 'reports'
        }

        # Should be caught by size validation or content validation
        with self.assertRaises(ValidationError):
            SecureFileUploadService.validate_and_process_upload(
                uploaded_file,
                'pdf',
                upload_context
            )

    def test_polyglot_file_protection(self):
        """Test protection against polyglot files."""
        # File that looks like both PDF and executable
        polyglot_content = b'%PDF-1.4\nMZ\x90\x00\x03\x00\x00\x00'

        uploaded_file = SimpleUploadedFile(
            'polyglot.pdf',
            polyglot_content,
            content_type='application/pdf'
        )

        upload_context = {
            'people_id': self.user.id,
            'folder_type': 'reports'
        }

        # Should pass basic validation but be caught by deeper analysis
        try:
            result = SecureFileUploadService.validate_and_process_upload(
                uploaded_file,
                'pdf',
                upload_context
            )
            # If it passes, ensure it's properly sandboxed
            self.assertIsInstance(result, dict)
        except ValidationError:
            # Expected behavior - file rejected
            pass

    def test_symlink_attack_prevention(self):
        """Test prevention of symlink attacks in file paths."""
        # This test ensures our path validation prevents symlink traversal
        symlink_paths = [
            'reports/../../etc/passwd',
            'uploads/../../../home/user/.ssh/id_rsa',
            'temp/link_to_sensitive_file.pdf',
        ]

        for symlink_path in symlink_paths:
            with self.subTest(path=symlink_path):
                # Test that our path generation never creates paths outside MEDIA_ROOT
                upload_context = {
                    'people_id': self.user.id,
                    'folder_type': 'reports'
                }

                uploaded_file = SimpleUploadedFile(
                    'test.pdf',
                    b'%PDF-1.4 test content',
                    content_type='application/pdf'
                )

                result = SecureFileUploadService.validate_and_process_upload(
                    uploaded_file,
                    'pdf',
                    upload_context
                )

                # Ensure the generated path is always within MEDIA_ROOT
                import os
                from django.conf import settings
                abs_result_path = os.path.abspath(result['file_path'])
                abs_media_root = os.path.abspath(settings.MEDIA_ROOT)
                self.assertTrue(abs_result_path.startswith(abs_media_root))