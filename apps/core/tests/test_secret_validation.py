"""
Comprehensive test suite for secret validation framework.

Tests the SecretValidator class and related functions to ensure
all critical secrets are properly validated at application startup.

Implements testing for Rule 4: Secure Secret Management
"""

import unittest
import base64

# Django imports
from django.test import TestCase

# Third-party imports
import pytest

# Local application imports
from apps.core.validation import (
    SecretValidator,
    SecretValidationError,
    validate_secret_key,
    validate_encryption_key,
    validate_admin_password
)


class SecretValidatorEntropyTest(TestCase):
    """Test entropy calculation functionality"""

    def test_empty_string_entropy(self):
        """Test entropy calculation for empty string"""
        entropy = SecretValidator.calculate_entropy("")
        self.assertEqual(entropy, 0.0)

    def test_single_character_entropy(self):
        """Test entropy for single repeated character"""
        entropy = SecretValidator.calculate_entropy("aaaaaaa")
        self.assertEqual(entropy, 0.0)

    def test_random_string_entropy(self):
        """Test entropy for random-looking string"""
        # A reasonably random string should have decent entropy
        random_string = "a9B#k2L@m5N$p8Q!r1S%t4U&w7Y*z0Z"
        entropy = SecretValidator.calculate_entropy(random_string)
        self.assertGreater(entropy, 4.0)

    def test_alphabet_entropy(self):
        """Test entropy for alphabetical sequence"""
        alphabet = "abcdefghijklmnopqrstuvwxyz"
        entropy = SecretValidator.calculate_entropy(alphabet)
        self.assertGreater(entropy, 4.5)  # Should have high entropy due to diversity

    def test_numeric_sequence_entropy(self):
        """Test entropy for numeric sequence"""
        numbers = "0123456789" * 5  # Repeat to get length
        entropy = SecretValidator.calculate_entropy(numbers)
        self.assertLess(entropy, 4.0)  # Lower entropy due to repetition


class SecretKeyValidationTest(TestCase):
    """Test SECRET_KEY validation functionality"""

    def test_empty_secret_key(self):
        """Test validation fails for empty SECRET_KEY"""
        with self.assertRaises(SecretValidationError) as context:
            validate_secret_key("SECRET_KEY", "")

        self.assertIn("empty or not provided", str(context.exception))
        self.assertIn("get_random_secret_key", context.exception.remediation)

    def test_none_secret_key(self):
        """Test validation fails for None SECRET_KEY"""
        with self.assertRaises(SecretValidationError) as context:
            validate_secret_key("SECRET_KEY", None)

        self.assertIn("empty or not provided", str(context.exception))

    def test_short_secret_key(self):
        """Test validation fails for short SECRET_KEY"""
        short_key = "abcd1234!@#$"  # Only 12 characters
        with self.assertRaises(SecretValidationError) as context:
            validate_secret_key("SECRET_KEY", short_key)

        self.assertIn("too short", str(context.exception))
        self.assertIn("12 chars", str(context.exception))
        self.assertIn("at least 50 characters", str(context.exception))

    def test_low_entropy_secret_key(self):
        """Test validation fails for low entropy SECRET_KEY"""
        # 50+ chars but very low entropy
        low_entropy_key = "a" * 60  # All same character
        with self.assertRaises(SecretValidationError) as context:
            validate_secret_key("SECRET_KEY", low_entropy_key)

        self.assertIn("insufficient entropy", str(context.exception))

    def test_weak_pattern_secret_key(self):
        """Test validation fails for keys with weak patterns"""
        weak_patterns = [
            "passwordpasswordpasswordpasswordpasswordpassword",  # Contains 'password'
            "secretsecretsecretsecretsecretsecretsecretsecret",  # Contains 'secret'
            "abcdefghijklmnopqrstuvwxyzabcdefghijklmnopqrstuvw",  # Contains alphabet
            "django" + "x" * 44,  # Contains 'django'
        ]

        for weak_key in weak_patterns:
            with self.assertRaises(SecretValidationError):
                validate_secret_key("SECRET_KEY", weak_key)

    def test_insufficient_character_diversity(self):
        """Test validation fails for insufficient character diversity"""
        # Only lowercase letters (missing uppercase, digits, specials)
        low_diversity = "abcdefghijklmnopqrstuvwxyzabcdefghijklmnopqrstu"
        with self.assertRaises(SecretValidationError) as context:
            validate_secret_key("SECRET_KEY", low_diversity)

        self.assertIn("character diversity", str(context.exception))

    def test_valid_secret_key(self):
        """Test validation passes for properly generated SECRET_KEY"""
        # Generate a proper Django secret key format
        valid_key = "a9B#k2L@m5N$p8Q!r1S%t4U&w7Y*z0Z3C^f6G)h9J+n2M?q5R(s8T"

        # Should not raise any exception
        result = validate_secret_key("SECRET_KEY", valid_key)
        self.assertEqual(result, valid_key)

    def test_django_generated_secret_key(self):
        """Test validation passes for Django-generated secret key"""
        # Simulate a Django-generated key
        from django.core.management.utils import get_random_secret_key
        django_key = get_random_secret_key()

        # Should pass validation
        result = validate_secret_key("SECRET_KEY", django_key)
        self.assertEqual(result, django_key)


class EncryptionKeyValidationTest(TestCase):
    """Test ENCRYPT_KEY validation functionality"""

    def test_empty_encryption_key(self):
        """Test validation fails for empty ENCRYPT_KEY"""
        with self.assertRaises(SecretValidationError) as context:
            validate_encryption_key("ENCRYPT_KEY", "")

        self.assertIn("empty or not provided", str(context.exception))
        self.assertIn("Fernet.generate_key", context.exception.remediation)

    def test_invalid_base64_encryption_key(self):
        """Test validation fails for invalid base64 ENCRYPT_KEY"""
        invalid_b64 = "this_is_not_valid_base64!"
        with self.assertRaises(SecretValidationError) as context:
            validate_encryption_key("ENCRYPT_KEY", invalid_b64)

        self.assertIn("not valid base64", str(context.exception))

    def test_wrong_length_encryption_key(self):
        """Test validation fails for wrong length ENCRYPT_KEY"""
        # Valid base64 but wrong length (16 bytes instead of 32)
        short_key = base64.b64encode(b"a" * 16).decode()
        with self.assertRaises(SecretValidationError) as context:
            validate_encryption_key("ENCRYPT_KEY", short_key)

        self.assertIn("16 bytes, must be exactly 32 bytes", str(context.exception))

    def test_low_entropy_encryption_key(self):
        """Test validation fails for low entropy ENCRYPT_KEY"""
        # 32 bytes of mostly zeros (low entropy)
        low_entropy_bytes = b"\x00" * 30 + b"\x01\x02"
        low_entropy_key = base64.b64encode(low_entropy_bytes).decode()

        with self.assertRaises(SecretValidationError) as context:
            validate_encryption_key("ENCRYPT_KEY", low_entropy_key)

        self.assertIn("insufficient entropy", str(context.exception))

    def test_zero_byte_encryption_key(self):
        """Test validation fails for keys with too many zero bytes"""
        # Key with many zero bytes (shows as 'A' in base64)
        zero_heavy_key = "A" * 40 + "BCD="  # Lots of A's indicate zero bytes

        with self.assertRaises(SecretValidationError) as context:
            validate_encryption_key("ENCRYPT_KEY", zero_heavy_key)

        self.assertIn("too many zero bytes", str(context.exception))

    def test_valid_encryption_key(self):
        """Test validation passes for properly generated ENCRYPT_KEY"""
        try:
            from cryptography.fernet import Fernet
            valid_key = Fernet.generate_key().decode()

            # Should not raise any exception
            result = validate_encryption_key("ENCRYPT_KEY", valid_key)
            self.assertEqual(result, valid_key)
        except ImportError:
            # Skip if cryptography not available
            self.skipTest("cryptography package not available")

    def test_fernet_compatibility(self):
        """Test that validated keys work with Fernet"""
        try:
            from cryptography.fernet import Fernet

            # Generate and validate a key
            fernet_key = Fernet.generate_key().decode()
            validated_key = validate_encryption_key("ENCRYPT_KEY", fernet_key)

            # Test that it actually works with Fernet
            f = Fernet(validated_key.encode())
            test_data = b"test message"
            encrypted = f.encrypt(test_data)
            decrypted = f.decrypt(encrypted)

            self.assertEqual(decrypted, test_data)
        except ImportError:
            self.skipTest("cryptography package not available")


class AdminPasswordValidationTest(TestCase):
    """Test SUPERADMIN_PASSWORD validation functionality"""

    def test_empty_admin_password(self):
        """Test validation fails for empty admin password"""
        with self.assertRaises(SecretValidationError) as context:
            validate_admin_password("SUPERADMIN_PASSWORD", "")

        self.assertIn("empty or not provided", str(context.exception))

    def test_short_admin_password(self):
        """Test validation fails for short admin password"""
        short_password = "Test123!"  # Only 8 characters
        with self.assertRaises(SecretValidationError) as context:
            validate_admin_password("SUPERADMIN_PASSWORD", short_password)

        self.assertIn("validation failed", str(context.exception))

    def test_common_admin_password(self):
        """Test validation fails for common passwords"""
        common_passwords = [
            "password123456",  # Too common
            "admin123456789",  # Predictable admin password
            "qwerty123456789",  # Common keyboard pattern
        ]

        for password in common_passwords:
            with self.assertRaises(SecretValidationError):
                validate_admin_password("SUPERADMIN_PASSWORD", password)

    def test_similar_to_user_info_password(self):
        """Test validation fails for passwords similar to user info"""
        # Password similar to 'superadmin' username
        similar_password = "superadmin12345!"
        with self.assertRaises(SecretValidationError) as context:
            validate_admin_password("SUPERADMIN_PASSWORD", similar_password)

        self.assertIn("validation failed", str(context.exception))

    def test_numeric_only_password(self):
        """Test validation fails for numeric-only passwords"""
        numeric_password = "123456789012"  # 12 digits
        with self.assertRaises(SecretValidationError):
            validate_admin_password("SUPERADMIN_PASSWORD", numeric_password)

    def test_low_entropy_admin_password(self):
        """Test validation fails for low entropy admin password"""
        # Meets length but very low entropy
        low_entropy = "aaaaaaaaaaaaaa"  # 14 characters, all same
        with self.assertRaises(SecretValidationError) as context:
            validate_admin_password("SUPERADMIN_PASSWORD", low_entropy)

        self.assertIn("insufficient entropy", str(context.exception))

    def test_valid_admin_password(self):
        """Test validation passes for strong admin password"""
        strong_password = "Admin@SecureP@ssw0rd2024!"

        # Should not raise any exception
        result = validate_admin_password("SUPERADMIN_PASSWORD", strong_password)
        self.assertEqual(result, strong_password)

    def test_django_password_validators_integration(self):
        """Test integration with Django's password validators"""
        # Ensure we're using Django's configured validators
        with self.assertRaises(SecretValidationError):
            # This should fail Django's configured validators
            validate_admin_password("SUPERADMIN_PASSWORD", "weak")


class SecretValidatorBatchTest(TestCase):
    """Test batch validation functionality"""

    def test_validate_all_secrets_success(self):
        """Test batch validation with all valid secrets"""
        try:
            from cryptography.fernet import Fernet
            from django.core.management.utils import get_random_secret_key

            secrets_config = {
                'SECRET_KEY': {
                    'value': get_random_secret_key(),
                    'type': 'secret_key'
                },
                'ENCRYPT_KEY': {
                    'value': Fernet.generate_key().decode(),
                    'type': 'encryption_key'
                },
                'SUPERADMIN_PASSWORD': {
                    'value': 'Admin@SecureP@ssw0rd2024!',
                    'type': 'admin_password'
                }
            }

            validated = SecretValidator.validate_all_secrets(secrets_config)

            # Should return all secrets validated
            self.assertEqual(len(validated), 3)
            self.assertIn('SECRET_KEY', validated)
            self.assertIn('ENCRYPT_KEY', validated)
            self.assertIn('SUPERADMIN_PASSWORD', validated)

        except ImportError:
            self.skipTest("cryptography package not available")

    def test_validate_all_secrets_failure(self):
        """Test batch validation with invalid secrets"""
        secrets_config = {
            'SECRET_KEY': {
                'value': 'weak',  # Too short
                'type': 'secret_key'
            },
            'ENCRYPT_KEY': {
                'value': 'invalid',  # Invalid base64
                'type': 'encryption_key'
            },
            'SUPERADMIN_PASSWORD': {
                'value': 'weak',  # Too weak
                'type': 'admin_password'
            }
        }

        with self.assertRaises(SecretValidationError) as context:
            SecretValidator.validate_all_secrets(secrets_config)

        # Should report all failures
        error_message = str(context.exception)
        self.assertIn("3 secret(s)", error_message)
        self.assertIn("SECRET_KEY", error_message)
        self.assertIn("ENCRYPT_KEY", error_message)
        self.assertIn("SUPERADMIN_PASSWORD", error_message)

    def test_unknown_secret_type(self):
        """Test batch validation with unknown secret type"""
        secrets_config = {
            'UNKNOWN_SECRET': {
                'value': 'some_value',
                'type': 'unknown_type'
            }
        }

        with self.assertRaises(ValueError) as context:
            SecretValidator.validate_all_secrets(secrets_config)

        self.assertIn("Unknown secret type: unknown_type", str(context.exception))


class ConvenienceFunctionTest(TestCase):
    """Test convenience functions"""

    def test_validate_secret_key_function(self):
        """Test standalone validate_secret_key function"""
        from django.core.management.utils import get_random_secret_key

        valid_key = get_random_secret_key()
        result = validate_secret_key("TEST_KEY", valid_key)
        self.assertEqual(result, valid_key)

    def test_validate_encryption_key_function(self):
        """Test standalone validate_encryption_key function"""
        try:
            from cryptography.fernet import Fernet

            valid_key = Fernet.generate_key().decode()
            result = validate_encryption_key("TEST_KEY", valid_key)
            self.assertEqual(result, valid_key)
        except ImportError:
            self.skipTest("cryptography package not available")

    def test_validate_admin_password_function(self):
        """Test standalone validate_admin_password function"""
        strong_password = "Admin@SecureP@ssw0rd2024!"
        result = validate_admin_password("TEST_PASSWORD", strong_password)
        self.assertEqual(result, strong_password)


class SecretValidationErrorTest(TestCase):
    """Test SecretValidationError exception"""

    def test_error_with_remediation(self):
        """Test error includes remediation information"""
        error = SecretValidationError(
            "TEST_SECRET",
            "Test error message",
            "Test remediation advice"
        )

        self.assertEqual(error.secret_name, "TEST_SECRET")
        self.assertEqual(error.remediation, "Test remediation advice")
        self.assertIn("Test error message", str(error))

    def test_error_without_remediation(self):
        """Test error works without remediation"""
        error = SecretValidationError("TEST_SECRET", "Test error message")

        self.assertEqual(error.secret_name, "TEST_SECRET")
        self.assertIsNone(error.remediation)


@pytest.mark.security
class SecurityIntegrationTest(TestCase):
    """Test security integration scenarios"""

    def test_settings_import_structure(self):
        """Test that validation functions can be imported in settings"""
        # This tests the import structure used in settings.py
        try:
            from apps.core.validation import (
                validate_secret_key,
                validate_encryption_key,
                validate_admin_password
            )

            # Functions should be callable
            self.assertTrue(callable(validate_secret_key))
            self.assertTrue(callable(validate_encryption_key))
            self.assertTrue(callable(validate_admin_password))
        except ImportError as e:
            self.fail(f"Could not import validation functions: {e}")

    def test_startup_failure_scenario(self):
        """Test that invalid secrets would cause startup failure"""
        # Simulate the settings.py validation block
        invalid_secrets = {
            "SECRET_KEY": "weak",
            "ENCRYPT_KEY": "invalid",
            "SUPERADMIN_PASSWORD": "weak"
        }

        with self.assertRaises((SecretValidationError, ValueError)):
            # This simulates what happens in settings.py
            validate_secret_key("SECRET_KEY", invalid_secrets["SECRET_KEY"])

    @patch('sys.exit')
    def test_settings_error_handling(self, mock_exit):
        """Test error handling in settings-like scenario"""
        try:
            validate_secret_key("SECRET_KEY", "")
        except SecretValidationError as e:
            # Verify error has proper attributes for settings.py handling
            self.assertTrue(hasattr(e, 'secret_name'))
            self.assertTrue(hasattr(e, 'remediation'))


if __name__ == "__main__":
    unittest.main()