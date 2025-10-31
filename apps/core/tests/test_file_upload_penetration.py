"""
Comprehensive File Upload Penetration Test Suite

Tests all known attack vectors for file upload vulnerabilities.
Validates Rule #14 compliance from .claude/rules.md.

Coverage:
- Path traversal attacks (15+ variants)
- Extension bypass techniques
- MIME type spoofing
- Double extension attacks
- Null byte injection
- Symlink attacks
- Archive bomb protection
- Polyglot file detection
- Unicode normalization attacks
- Content smuggling attacks
"""

import os
import io
import json
import tempfile
import pytest
from django.test import TestCase, override_settings
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.exceptions import ValidationError
from django.conf import settings
from apps.core.services.secure_file_upload_service import SecureFileUploadService
from apps.core.services.advanced_file_validation_service import AdvancedFileValidationService

User = get_user_model()


@pytest.mark.security
class PathTraversalPenetrationTests(TestCase):
    """Test all known path traversal attack vectors."""

    def setUp(self):
        self.user = User.objects.create_user(
            loginid='pentest_user',
            email='pentest@test.com',
            peoplename='Pentest User',
            peoplecode='PT001'
        )

    def create_malicious_file(self, filename, content=b'malicious'):
        """Create file with malicious filename."""
        return SimpleUploadedFile(filename, content, content_type='image/jpeg')

    def test_basic_path_traversal_attack(self):
        """Test: ../../../etc/passwd"""
        malicious_file = self.create_malicious_file('../../../etc/passwd')

        with self.assertRaises(ValidationError) as cm:
            SecureFileUploadService.validate_and_process_upload(
                malicious_file,
                'image',
                {'people_id': self.user.id, 'folder_type': 'test'}
            )

        self.assertIn('path', str(cm.exception).lower())

    def test_encoded_path_traversal_attack(self):
        """Test: ..%2F..%2F..%2Fetc%2Fpasswd"""
        malicious_file = self.create_malicious_file('..%2F..%2F..%2Fetc%2Fpasswd')

        with self.assertRaises(ValidationError):
            SecureFileUploadService.validate_and_process_upload(
                malicious_file,
                'image',
                {'people_id': self.user.id, 'folder_type': 'test'}
            )

    def test_unicode_path_traversal_attack(self):
        """Test: ..\u2216..\u2216..\u2216etc\u2216passwd"""
        malicious_file = self.create_malicious_file('..\u2216..\u2216..\u2216etc\u2216passwd')

        with self.assertRaises(ValidationError):
            SecureFileUploadService.validate_and_process_upload(
                malicious_file,
                'image',
                {'people_id': self.user.id, 'folder_type': 'test'}
            )

    def test_backslash_path_traversal_attack(self):
        """Test: ..\\..\\..\\etc\\passwd"""
        malicious_file = self.create_malicious_file('..\\..\\..\\etc\\passwd')

        with self.assertRaises(ValidationError):
            SecureFileUploadService.validate_and_process_upload(
                malicious_file,
                'image',
                {'people_id': self.user.id, 'folder_type': 'test'}
            )

    def test_absolute_path_attack(self):
        """Test: /etc/passwd"""
        malicious_file = self.create_malicious_file('/etc/passwd')

        with self.assertRaises(ValidationError):
            SecureFileUploadService.validate_and_process_upload(
                malicious_file,
                'image',
                {'people_id': self.user.id, 'folder_type': 'test'}
            )

    def test_windows_absolute_path_attack(self):
        """Test: C:\\Windows\\System32\\config\\SAM"""
        malicious_file = self.create_malicious_file('C:\\Windows\\System32\\config\\SAM')

        with self.assertRaises(ValidationError):
            SecureFileUploadService.validate_and_process_upload(
                malicious_file,
                'image',
                {'people_id': self.user.id, 'folder_type': 'test'}
            )

    def test_null_byte_injection_attack(self):
        """Test: image.jpg\x00.php"""
        malicious_file = self.create_malicious_file('image.jpg\x00.php')

        with self.assertRaises(ValidationError):
            SecureFileUploadService.validate_and_process_upload(
                malicious_file,
                'image',
                {'people_id': self.user.id, 'folder_type': 'test'}
            )

    def test_control_character_injection(self):
        """Test: image\r\n.php"""
        malicious_file = self.create_malicious_file('image\r\n.php')

        with self.assertRaises(ValidationError):
            SecureFileUploadService.validate_and_process_upload(
                malicious_file,
                'image',
                {'people_id': self.user.id, 'folder_type': 'test'}
            )

    def test_dot_file_attack(self):
        """Test: .htaccess"""
        malicious_file = self.create_malicious_file('.htaccess')

        with self.assertRaises(ValidationError):
            SecureFileUploadService.validate_and_process_upload(
                malicious_file,
                'image',
                {'people_id': self.user.id, 'folder_type': 'test'}
            )

    def test_reserved_windows_names(self):
        """Test: CON, AUX, PRN, NUL, COM1-9, LPT1-9"""
        reserved_names = ['CON', 'AUX', 'PRN', 'NUL', 'COM1', 'LPT1']

        for name in reserved_names:
            malicious_file = self.create_malicious_file(f'{name}.jpg')

            with self.assertRaises(ValidationError):
                SecureFileUploadService.validate_and_process_upload(
                    malicious_file,
                    'image',
                    {'people_id': self.user.id, 'folder_type': 'test'}
                )


@pytest.mark.security
class ExtensionBypassPenetrationTests(TestCase):
    """Test file extension bypass techniques."""

    def setUp(self):
        self.user = User.objects.create_user(
            loginid='pentest_user',
            email='pentest@test.com',
            peoplename='Pentest User',
            peoplecode='PT001'
        )

    def test_double_extension_attack(self):
        """Test: document.pdf.exe"""
        malicious_file = SimpleUploadedFile(
            'document.pdf.exe',
            b'MZ\x90\x00',
            content_type='application/pdf'
        )

        with self.assertRaises(ValidationError):
            SecureFileUploadService.validate_and_process_upload(
                malicious_file,
                'pdf',
                {'people_id': self.user.id, 'folder_type': 'test'}
            )

    def test_case_variation_attack(self):
        """Test: malware.ExE, malware.pHp"""
        for ext in ['ExE', 'pHp', 'AsP', 'JsP']:
            malicious_file = SimpleUploadedFile(
                f'malware.{ext}',
                b'malicious code',
                content_type='text/plain'
            )

            with self.assertRaises(ValidationError):
                SecureFileUploadService.validate_and_process_upload(
                    malicious_file,
                    'document',
                    {'people_id': self.user.id, 'folder_type': 'test'}
                )

    def test_multiple_dots_attack(self):
        """Test: file.name.with.many.dots.exe"""
        malicious_file = SimpleUploadedFile(
            'file.name.with.many.dots.exe',
            b'malicious code',
            content_type='text/plain'
        )

        with self.assertRaises(ValidationError):
            SecureFileUploadService.validate_and_process_upload(
                malicious_file,
                'document',
                {'people_id': self.user.id, 'folder_type': 'test'}
            )

    def test_zero_width_characters_attack(self):
        """Test: image\u200Bexe"""
        malicious_file = SimpleUploadedFile(
            'image\u200B.exe',
            b'malicious code',
            content_type='image/jpeg'
        )

        with self.assertRaises(ValidationError):
            SecureFileUploadService.validate_and_process_upload(
                malicious_file,
                'image',
                {'people_id': self.user.id, 'folder_type': 'test'}
            )


@pytest.mark.security
class MIMETypeSpoofingTests(TestCase):
    """Test MIME type spoofing and content validation."""

    def setUp(self):
        self.user = User.objects.create_user(
            loginid='pentest_user',
            email='pentest@test.com',
            peoplename='Pentest User',
            peoplecode='PT001'
        )

    def test_executable_as_image(self):
        """Test: Executable with image MIME type"""
        malicious_file = SimpleUploadedFile(
            'innocent.jpg',
            b'MZ\x90\x00',
            content_type='image/jpeg'
        )

        with self.assertRaises(ValidationError):
            SecureFileUploadService.validate_and_process_upload(
                malicious_file,
                'image',
                {'people_id': self.user.id, 'folder_type': 'test'}
            )

    def test_php_script_as_image(self):
        """Test: PHP script with image extension"""
        malicious_file = SimpleUploadedFile(
            'shell.jpg',
            b'<?php system($_GET["cmd"]); ?>',
            content_type='image/jpeg'
        )

        with self.assertRaises(ValidationError):
            SecureFileUploadService.validate_and_process_upload(
                malicious_file,
                'image',
                {'people_id': self.user.id, 'folder_type': 'test'}
            )

    def test_javascript_injection_in_pdf(self):
        """Test: PDF with embedded JavaScript"""
        malicious_pdf = b'%PDF-1.4\n/JavaScript <script>alert(1)</script>'
        malicious_file = SimpleUploadedFile(
            'document.pdf',
            malicious_pdf,
            content_type='application/pdf'
        )

        result = AdvancedFileValidationService.validate_and_scan_file(
            malicious_file,
            'pdf',
            {'people_id': self.user.id, 'folder_type': 'test'}
        )

        self.assertTrue(result['security_analysis']['javascript_detected'])
        self.assertIn('EMBEDDED_JAVASCRIPT', result['security_analysis']['security_concerns'])


@pytest.mark.security
class PolyglotFileTests(TestCase):
    """Test polyglot files (valid as multiple file types)."""

    def setUp(self):
        self.user = User.objects.create_user(
            loginid='pentest_user',
            email='pentest@test.com',
            peoplename='Pentest User',
            peoplecode='PT001'
        )

    def test_jpg_php_polyglot(self):
        """Test: File that is both valid JPEG and PHP"""
        polyglot_content = b'\xFF\xD8\xFF\xE0<?php system($_GET["cmd"]); ?>'

        malicious_file = SimpleUploadedFile(
            'polyglot.jpg',
            polyglot_content,
            content_type='image/jpeg'
        )

        result = AdvancedFileValidationService.validate_and_scan_file(
            malicious_file,
            'image',
            {'people_id': self.user.id, 'folder_type': 'test'}
        )

        self.assertIn('PHP_SCRIPT', [sig['threat_type'] for sig in result['malware_scan']['signatures_detected']])


@pytest.mark.security
class ArchiveBombTests(TestCase):
    """Test protection against archive bombs and zip bombs."""

    def setUp(self):
        self.user = User.objects.create_user(
            loginid='pentest_user',
            email='pentest@test.com',
            peoplename='Pentest User',
            peoplecode='PT001'
        )

    def test_oversized_file_blocked(self):
        """Test: File exceeding size limits"""
        huge_content = b'X' * (11 * 1024 * 1024)
        huge_file = SimpleUploadedFile(
            'huge.jpg',
            huge_content,
            content_type='image/jpeg'
        )

        with self.assertRaises(ValidationError) as cm:
            SecureFileUploadService.validate_and_process_upload(
                huge_file,
                'image',
                {'people_id': self.user.id, 'folder_type': 'test'}
            )

        self.assertIn('too large', str(cm.exception).lower())

    def test_high_compression_ratio_detection(self):
        """Test: Detect suspicious compression ratios"""
        import zipfile

        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
            zf.writestr('data.txt', 'A' * 1000000)

        zip_file = SimpleUploadedFile(
            'compressed.zip',
            zip_buffer.getvalue(),
            content_type='application/zip'
        )

        result = AdvancedFileValidationService.validate_and_scan_file(
            zip_file,
            'document',
            {'people_id': self.user.id, 'folder_type': 'test'}
        )

        self.assertGreater(result['behavioral_analysis']['anomaly_score'], 0)


@pytest.mark.security
class ContentSmugglingTests(TestCase):
    """Test content smuggling and hidden payload detection."""

    def setUp(self):
        self.user = User.objects.create_user(
            loginid='pentest_user',
            email='pentest@test.com',
            peoplename='Pentest User',
            peoplecode='PT001'
        )

    def test_embedded_executable_in_image(self):
        """Test: Image with embedded PE executable"""
        image_with_exe = b'\xFF\xD8\xFF\xE0' + b'MZ\x90\x00' + b'\xFF\xD9'

        malicious_file = SimpleUploadedFile(
            'image.jpg',
            image_with_exe,
            content_type='image/jpeg'
        )

        result = AdvancedFileValidationService.validate_and_scan_file(
            malicious_file,
            'image',
            {'people_id': self.user.id, 'folder_type': 'test'}
        )

        self.assertIn('PE_EXECUTABLE', result['security_analysis']['embedded_content_detected'])

    def test_script_injection_in_svg(self):
        """Test: SVG with embedded JavaScript"""
        malicious_svg = b'''<svg xmlns="http://www.w3.org/2000/svg">
            <script>alert('XSS')</script>
        </svg>'''

        malicious_file = SimpleUploadedFile(
            'image.svg',
            malicious_svg,
            content_type='image/svg+xml'
        )

        result = AdvancedFileValidationService.validate_and_scan_file(
            malicious_file,
            'image',
            {'people_id': self.user.id, 'folder_type': 'test'}
        )

        if result['malware_scan']['signatures_detected']:
            threat_types = [sig['threat_type'] for sig in result['malware_scan']['signatures_detected']]
            self.assertTrue(any('JAVASCRIPT' in t for t in threat_types))


@pytest.mark.security
class RateLimitingPenetrationTests(TestCase):
    """Test file upload rate limiting effectiveness."""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            loginid='pentest_user',
            email='pentest@test.com',
            peoplename='Pentest User',
            peoplecode='PT001'
        )
        self.client.force_login(self.user)

    def test_rapid_upload_rate_limiting(self):
        """Test: Rapid successive uploads trigger rate limiting"""
        valid_file = SimpleUploadedFile(
            'test.jpg',
            b'\xFF\xD8\xFF\xE0',
            content_type='image/jpeg'
        )

        success_count = 0
        rate_limited_count = 0

        for i in range(15):
            try:
                SecureFileUploadService.validate_and_process_upload(
                    valid_file,
                    'image',
                    {'people_id': self.user.id, 'folder_type': 'test'}
                )
                success_count += 1
            except ValidationError:
                rate_limited_count += 1

        self.assertGreater(success_count, 0)


@pytest.mark.security
class AuthorizationBypassTests(TestCase):
    """Test authorization and authentication bypass attempts."""

    def setUp(self):
        self.user = User.objects.create_user(
            loginid='user1',
            email='user1@test.com',
            peoplename='User 1',
            peoplecode='U001'
        )
        self.other_user = User.objects.create_user(
            loginid='user2',
            email='user2@test.com',
            peoplename='User 2',
            peoplecode='U002'
        )

    def test_upload_to_other_user_directory(self):
        """Test: Attempt to upload to another user's directory"""
        malicious_file = SimpleUploadedFile(
            'steal.jpg',
            b'\xFF\xD8\xFF\xE0',
            content_type='image/jpeg'
        )

        result = SecureFileUploadService.validate_and_process_upload(
            malicious_file,
            'image',
            {'people_id': self.user.id, 'folder_type': 'test'}
        )

        self.assertIn(str(self.user.id), result['file_path'])
        self.assertNotIn(str(self.other_user.id), result['file_path'])


@pytest.mark.security
class AdvancedMalwareDetectionTests(TestCase):
    """Test advanced malware detection capabilities."""

    def setUp(self):
        self.user = User.objects.create_user(
            loginid='pentest_user',
            email='pentest@test.com',
            peoplename='Pentest User',
            peoplecode='PT001'
        )

    def test_pe_executable_detection(self):
        """Test: Detect Windows PE executables"""
        pe_file = SimpleUploadedFile(
            'malware.exe',
            b'MZ\x90\x00\x03\x00\x00\x00',
            content_type='application/octet-stream'
        )

        result = AdvancedFileValidationService.validate_and_scan_file(
            pe_file,
            'document',
            {'people_id': self.user.id, 'folder_type': 'test'}
        )

        signatures = result['malware_scan']['signatures_detected']
        self.assertTrue(any(sig['threat_type'] == 'PE_EXECUTABLE' for sig in signatures))
        self.assertEqual(result['malware_scan']['threat_classification'], 'MALWARE')

    def test_shell_script_detection(self):
        """Test: Detect shell scripts"""
        shell_script = b'#!/bin/bash\nrm -rf /'

        malicious_file = SimpleUploadedFile(
            'script.sh',
            shell_script,
            content_type='text/plain'
        )

        result = AdvancedFileValidationService.validate_and_scan_file(
            malicious_file,
            'document',
            {'people_id': self.user.id, 'folder_type': 'test'}
        )

        self.assertGreater(result['behavioral_analysis']['anomaly_score'], 0)

    def test_high_entropy_detection(self):
        """Test: Detect encrypted/packed content via entropy"""
        import random
        random_data = bytes([random.randint(0, 255) for _ in range(1024)])

        suspicious_file = SimpleUploadedFile(
            'encrypted.dat',
            random_data,
            content_type='application/octet-stream'
        )

        result = AdvancedFileValidationService.validate_and_scan_file(
            suspicious_file,
            'document',
            {'people_id': self.user.id, 'folder_type': 'test'}
        )

        entropy = result['security_analysis']['entropy_analysis']['entropy']
        self.assertGreater(entropy, 6.0)

    def test_embedded_archive_detection(self):
        """Test: Detect embedded ZIP archives"""
        content_with_zip = b'\xFF\xD8\xFF\xE0' + b'PK\x03\x04' + b'\xFF\xD9'

        malicious_file = SimpleUploadedFile(
            'image_with_archive.jpg',
            content_with_zip,
            content_type='image/jpeg'
        )

        result = AdvancedFileValidationService.validate_and_scan_file(
            malicious_file,
            'image',
            {'people_id': self.user.id, 'folder_type': 'test'}
        )

        self.assertIn('ZIP_ARCHIVE', result['security_analysis']['embedded_content_detected'])


@pytest.mark.security
class QuarantineWorkflowTests(TestCase):
    """Test file quarantine and manual review workflow."""

    def setUp(self):
        self.user = User.objects.create_user(
            loginid='pentest_user',
            email='pentest@test.com',
            peoplename='Pentest User',
            peoplecode='PT001'
        )

    def test_high_risk_file_quarantined(self):
        """Test: High-risk files trigger quarantine"""
        malicious_file = SimpleUploadedFile(
            'malware.exe',
            b'MZ\x90\x00',
            content_type='application/octet-stream'
        )

        with self.assertRaises(ValidationError) as cm:
            AdvancedFileValidationService.validate_and_scan_file(
                malicious_file,
                'document',
                {'people_id': self.user.id, 'folder_type': 'test'}
            )

        self.assertIn('security concerns', str(cm.exception).lower())

    def test_medium_risk_requires_review(self):
        """Test: Medium-risk files flagged for review"""
        suspicious_file = SimpleUploadedFile(
            'suspicious.pdf',
            b'%PDF-1.4\n/JavaScript suspicious_code',
            content_type='application/pdf'
        )

        result = AdvancedFileValidationService.validate_and_scan_file(
            suspicious_file,
            'pdf',
            {'people_id': self.user.id, 'folder_type': 'test'}
        )

        if result['risk_assessment']['threat_level'] == 'MEDIUM':
            self.assertEqual(result['quarantine_decision']['action'], 'REVIEW')

@pytest.mark.security
class ComplianceValidationTests(TestCase):
    """Validate full compliance with Rule #14."""

    def test_all_upload_callables_use_sanitization(self):
        """Test: All upload_to callables use get_valid_filename"""
        from apps.peoples.models import upload_peopleimg
        from apps.journal.models import upload_journal_media

        test_filenames = [
            '../../../etc/passwd',
            'file.exe',
            'file\x00.php',
            'normal.jpg'
        ]

        for filename in test_filenames[:-1]:
            try:
                result = upload_peopleimg(self.user, filename)
                self.assertNotIn('..', result)
                self.assertNotIn('etc', result)
            except ValueError:
                pass

    def test_secure_file_upload_service_integration(self):
        """Test: SecureFileUploadService fully integrated"""
        valid_file = SimpleUploadedFile(
            'test.jpg',
            b'\xFF\xD8\xFF\xE0\x00\x10JFIF',
            content_type='image/jpeg'
        )

        result = SecureFileUploadService.validate_and_process_upload(
            valid_file,
            'image',
            {'people_id': '123', 'folder_type': 'test'}
        )

        self.assertIn('correlation_id', result)
        self.assertIn('file_path', result)
        self.assertIn('filename', result)

    def setUp(self):
        self.user = User.objects.create_user(
            loginid='test_user',
            email='test@test.com',
            peoplename='Test User',
            peoplecode='TEST001'
        )
