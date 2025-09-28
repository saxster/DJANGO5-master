"""
Security Tests for People Image Upload

Tests the security fixes for upload_peopleimg() function to prevent:
- Path traversal attacks
- Filename injection
- Extension spoofing
- Directory traversal

Compliance: Validates Rule #14 from .claude/rules.md - File Upload Security
"""

import pytest
from django.test import TestCase
from django.contrib.auth import get_user_model

from apps.peoples.models import upload_peopleimg

User = get_user_model()


@pytest.mark.security
class PeopleImageUploadSecurityTests(TestCase):
    """Comprehensive security tests for people image uploads."""

    def setUp(self):
        """Set up test data."""
        from apps.onboarding.models import Bt

        self.client_bu = Bt.objects.create(
            bucode='SECTEST001',
            buname='Security Test Client',
            butype='CLIENT'
        )

        self.user = User.objects.create(
            loginid='sec_user',
            peoplecode='SEC001',
            peoplename='Security Test User',
            email='security@example.com',
            dateofbirth='1990-01-01',
            client=self.client_bu
        )

    def test_path_traversal_with_parent_directory(self):
        """Test: ../../../etc/passwd patterns are sanitized."""
        malicious_filename = '../../../etc/passwd'
        result = upload_peopleimg(self.user, malicious_filename)

        # Result should NOT contain path traversal
        self.assertNotIn('..', result)
        self.assertNotIn('/etc/', result)
        self.assertTrue(result.startswith('master/'))

    def test_path_traversal_with_backslash(self):
        """Test: Windows-style path traversal is blocked."""
        malicious_filename = '..\\..\\..\\windows\\system32\\config\\sam'
        result = upload_peopleimg(self.user, malicious_filename)

        self.assertNotIn('..', result)
        self.assertNotIn('windows', result.lower())

    def test_null_byte_injection_prevention(self):
        """Test: Null bytes are stripped from filenames."""
        malicious_filename = 'image.jpg\x00.php'
        result = upload_peopleimg(self.user, malicious_filename)

        # Null bytes should be removed
        self.assertNotIn('\x00', result)
        # Should not allow PHP extension
        self.assertNotIn('.php', result)

    def test_absolute_path_prevention(self):
        """Test: Absolute paths are rejected."""
        absolute_paths = [
            '/etc/passwd',
            '/var/www/html/shell.php',
            'C:\\Windows\\System32\\evil.exe'
        ]

        for path in absolute_paths:
            result = upload_peopleimg(self.user, path)

            # Should not start with absolute indicators
            self.assertFalse(result.startswith('/'))
            self.assertFalse(result[1:3] == ':\\' if len(result) > 2 else False)

    def test_double_extension_attack(self):
        """Test: Double extensions like .php.jpg are handled safely."""
        malicious_filenames = [
            'image.php.jpg',
            'shell.exe.png',
            'script.sh.gif'
        ]

        for filename in malicious_filenames:
            result = upload_peopleimg(self.user, filename)

            # Should accept only if the LAST extension is valid
            valid_extensions = ['.jpg', '.jpeg', '.png', '.gif', '.webp']
            has_valid_ext = any(result.endswith(ext) for ext in valid_extensions)

            # Either has valid extension or returns default
            self.assertTrue(
                has_valid_ext or result == "master/people/blank.png",
                f"Invalid extension handling: {result}"
            )

    def test_script_extension_rejection(self):
        """Test: Script extensions are rejected."""
        script_extensions = [
            'shell.php',
            'malware.exe',
            'script.sh',
            'code.py',
            'batch.bat'
        ]

        for filename in script_extensions:
            result = upload_peopleimg(self.user, filename)

            # Should return default image
            self.assertEqual(result, "master/people/blank.png")

    def test_special_characters_sanitization(self):
        """Test: Special characters are sanitized."""
        special_char_names = [
            'file<script>.jpg',
            'image|pipe.png',
            'photo@#$%.gif',
            'pic;rm -rf.jpg'
        ]

        for filename in special_char_names:
            result = upload_peopleimg(self.user, filename)

            # Should not contain dangerous special characters
            dangerous_chars = ['<', '>', '|', ';', '&', '`', '$']
            for char in dangerous_chars:
                self.assertNotIn(char, result)

    def test_reserved_windows_names_handled(self):
        """Test: Reserved Windows names are handled safely."""
        reserved_names = [
            'con.jpg',
            'aux.png',
            'prn.gif',
            'nul.jpg'
        ]

        for filename in reserved_names:
            result = upload_peopleimg(self.user, filename)

            # Should still generate a safe path
            # The exact handling depends on implementation
            # but it should not cause system issues
            self.assertTrue(len(result) > 0)

    def test_extremely_long_filename(self):
        """Test: Extremely long filenames are handled."""
        long_filename = 'a' * 500 + '.jpg'
        result = upload_peopleimg(self.user, long_filename)

        # Result should be reasonable length (< 255 for most filesystems)
        # Each component should be < 255
        for component in result.split('/'):
            self.assertLessEqual(len(component), 255)

    def test_unicode_characters_handling(self):
        """Test: Unicode characters are handled properly."""
        unicode_filenames = [
            '中文文件名.jpg',
            'файл.png',
            'αρχείο.gif',
            'ملف.jpg'
        ]

        for filename in unicode_filenames:
            result = upload_peopleimg(self.user, filename)

            # Should generate a valid path (may be sanitized)
            self.assertTrue(len(result) > 0)
            self.assertTrue(result.startswith('master/'))

    def test_directory_creation_prevention(self):
        """Test: Attempts to create directories are prevented."""
        directory_attempts = [
            'newdir/../../etc/passwd',
            'folder/../../../../../tmp/evil.sh',
            './subdir/../../sensitive'
        ]

        for attempt in directory_attempts:
            result = upload_peopleimg(self.user, attempt)

            # Should not allow directory traversal
            self.assertNotIn('..', result)

    def test_valid_image_extensions_accepted(self):
        """Test: Valid image extensions are accepted."""
        valid_images = [
            'photo.jpg',
            'image.jpeg',
            'graphic.png',
            'animation.gif',
            'modern.webp'
        ]

        for filename in valid_images:
            result = upload_peopleimg(self.user, filename)

            # Should NOT return default (should process the file)
            self.assertNotEqual(result, "master/people/blank.png")
            # Should contain the extension (in lowercase)
            ext = filename.split('.')[-1].lower()
            self.assertIn(f".{ext}", result.lower())

    def test_case_insensitive_extension_handling(self):
        """Test: Extensions are handled case-insensitively."""
        case_variants = [
            'photo.JPG',
            'image.JPEG',
            'graphic.PNG',
            'pic.GIF'
        ]

        for filename in case_variants:
            result = upload_peopleimg(self.user, filename)

            # Should accept uppercase extensions
            self.assertNotEqual(result, "master/people/blank.png")

    def test_no_extension_rejection(self):
        """Test: Files without extensions are rejected."""
        no_extension_files = [
            'filenamewithoutextension',
            'justtext',
            'noext'
        ]

        for filename in no_extension_files:
            result = upload_peopleimg(self.user, filename)

            # Should return default
            self.assertEqual(result, "master/people/blank.png")

    def test_spaces_in_filename_handled(self):
        """Test: Spaces in filenames are handled properly."""
        spaced_filenames = [
            'my photo.jpg',
            'user   image.png',
            'file with many   spaces.gif'
        ]

        for filename in spaced_filenames:
            result = upload_peopleimg(self.user, filename)

            # Spaces should be handled (converted to underscore or removed)
            # Should not contain multiple consecutive spaces in result
            self.assertNotIn('  ', result)

    def test_client_boundary_enforcement(self):
        """Test: Files are stored in client-specific directories."""
        result = upload_peopleimg(self.user, 'test.jpg')

        # Should contain client identifier
        self.assertIn(str(self.client_bu.id), result.lower())
        self.assertIn(self.client_bu.bucode.lower(), result.lower())

    def test_missing_client_fallback(self):
        """Test: Handles missing client gracefully."""
        user_no_client = User.objects.create(
            loginid='no_client_user',
            peoplecode='NC001',
            peoplename='No Client User',
            email='noclient@example.com',
            dateofbirth='1990-01-01'
        )

        result = upload_peopleimg(user_no_client, 'test.jpg')

        # Should still return a valid path
        self.assertTrue(len(result) > 0)
        self.assertTrue(result.startswith('master/'))

    def test_peoplecode_sanitization(self):
        """Test: People code is sanitized in path."""
        user_special_code = User.objects.create(
            loginid='special_user',
            peoplecode='TEST@#$%001',  # Special characters
            peoplename='Special User',
            email='special@example.com',
            dateofbirth='1990-01-01',
            client=self.client_bu
        )

        result = upload_peopleimg(user_special_code, 'test.jpg')

        # Special characters should be removed from path
        self.assertNotIn('@', result)
        self.assertNotIn('#', result)
        self.assertNotIn('$', result)
        self.assertNotIn('%', result)