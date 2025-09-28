"""
Comprehensive tests for the SecureEncryptionService.

These tests verify that the new cryptographically secure encryption
properly replaces the insecure zlib compression implementation.
"""
from django.test import TestCase, override_settings
from django.core.exceptions import ValidationError
from apps.core.services.secure_encryption_service import SecureEncryptionService
from apps.peoples.fields.secure_fields import EnhancedSecureString


class SecureEncryptionServiceTest(TestCase):
    """Test the SecureEncryptionService functionality."""

    def setUp(self):
        """Set up test environment."""
        # Reset singleton state for testing
        SecureEncryptionService._fernet_instance = None
        SecureEncryptionService._key_derivation_salt = None

    def test_encryption_decryption_basic(self):
        """Test basic encryption and decryption functionality."""
        plaintext = "sensitive_user_email@example.com"

        # Encrypt
        encrypted = SecureEncryptionService.encrypt(plaintext)

        # Should have version prefix
        self.assertTrue(encrypted.startswith("FERNET_V1:"))
        self.assertNotEqual(encrypted, plaintext)

        # Decrypt
        decrypted = SecureEncryptionService.decrypt(encrypted)
        self.assertEqual(decrypted, plaintext)

    def test_encryption_bytes_input(self):
        """Test encryption with bytes input."""
        plaintext_bytes = b"sensitive_data"

        encrypted = SecureEncryptionService.encrypt(plaintext_bytes)
        decrypted = SecureEncryptionService.decrypt(encrypted)

        self.assertEqual(decrypted, "sensitive_data")

    def test_encryption_empty_string(self):
        """Test encryption with empty string."""
        encrypted = SecureEncryptionService.encrypt("")
        decrypted = SecureEncryptionService.decrypt(encrypted)

        self.assertEqual(decrypted, "")

    def test_encryption_unicode(self):
        """Test encryption with unicode characters."""
        plaintext = "🔒 Sensitive Data with émojis and açcénts 中文"

        encrypted = SecureEncryptionService.encrypt(plaintext)
        decrypted = SecureEncryptionService.decrypt(encrypted)

        self.assertEqual(decrypted, plaintext)

    def test_encryption_large_data(self):
        """Test encryption with large amounts of data."""
        plaintext = "A" * 10000  # 10KB of data

        encrypted = SecureEncryptionService.encrypt(plaintext)
        decrypted = SecureEncryptionService.decrypt(encrypted)

        self.assertEqual(decrypted, plaintext)

    def test_legacy_migration_success(self):
        """Test successful migration of legacy zlib data."""
        # Create legacy zlib compressed data
        import zlib
        import base64

        original_data = "legacy_email@example.com"
        legacy_compressed = base64.urlsafe_b64encode(zlib.compress(original_data.encode('utf-8'), 9))

        # Test migration
        success, result = SecureEncryptionService.migrate_legacy_data(legacy_compressed.decode('ascii'))

        self.assertTrue(success)
        self.assertTrue(result.startswith("FERNET_V1:"))

        # Verify we can decrypt the result
        decrypted = SecureEncryptionService.decrypt(result)
        self.assertEqual(decrypted, original_data)

    def test_legacy_migration_failure(self):
        """Test migration failure with invalid legacy data."""
        invalid_data = "not_valid_legacy_data"

        success, result = SecureEncryptionService.migrate_legacy_data(invalid_data)

        self.assertFalse(success)
        self.assertEqual(result, invalid_data)

    def test_is_securely_encrypted(self):
        """Test secure encryption detection."""
        # Test secure format
        secure_data = "FERNET_V1:some_encrypted_data"
        self.assertTrue(SecureEncryptionService.is_securely_encrypted(secure_data))

        # Test non-secure formats
        self.assertFalse(SecureEncryptionService.is_securely_encrypted("ENC_V1:legacy_data"))
        self.assertFalse(SecureEncryptionService.is_securely_encrypted("plaintext_data"))
        self.assertFalse(SecureEncryptionService.is_securely_encrypted(""))
        self.assertFalse(SecureEncryptionService.is_securely_encrypted(None))

    def test_validation_setup(self):
        """Test encryption setup validation."""
        self.assertTrue(SecureEncryptionService.validate_encryption_setup())

    @override_settings(SECRET_KEY="")
    def test_invalid_secret_key(self):
        """Test behavior with invalid SECRET_KEY."""
        # Reset singleton to force re-initialization
        SecureEncryptionService._fernet_instance = None
        SecureEncryptionService._key_derivation_salt = None

        with self.assertRaises(ValueError):
            SecureEncryptionService.encrypt("test")

    def test_decryption_invalid_token(self):
        """Test decryption with invalid token."""
        invalid_encrypted = "FERNET_V1:invalid_token_data"

        with self.assertRaises(ValueError):
            SecureEncryptionService.decrypt(invalid_encrypted)

    def test_different_keys_different_results(self):
        """Test that different secret keys produce different encrypted results."""
        plaintext = "test_data"

        # Encrypt with current key
        encrypted1 = SecureEncryptionService.encrypt(plaintext)

        # Reset and change key (simulate different environment)
        SecureEncryptionService._fernet_instance = None
        SecureEncryptionService._key_derivation_salt = None

        with patch('django.conf.settings.SECRET_KEY', 'different_secret_key'):
            encrypted2 = SecureEncryptionService.encrypt(plaintext)

        # Should produce different results
        self.assertNotEqual(encrypted1, encrypted2)

    def test_consistency_across_calls(self):
        """Test that the same plaintext produces consistent encryption key derivation."""
        plaintext = "consistent_test"

        # Multiple encryptions should be decryptable (though ciphertext will differ due to IV)
        encrypted1 = SecureEncryptionService.encrypt(plaintext)
        encrypted2 = SecureEncryptionService.encrypt(plaintext)

        # Ciphertext should be different (due to random IV)
        self.assertNotEqual(encrypted1, encrypted2)

        # But both should decrypt to same plaintext
        self.assertEqual(SecureEncryptionService.decrypt(encrypted1), plaintext)
        self.assertEqual(SecureEncryptionService.decrypt(encrypted2), plaintext)


class EnhancedSecureStringFieldTest(TestCase):
    """Test the EnhancedSecureString field implementation."""

    def setUp(self):
        """Set up test field."""
        self.field = EnhancedSecureString()

    def test_field_initialization(self):
        """Test field initialization with proper defaults."""
        field = EnhancedSecureString()
        self.assertEqual(field.max_length, 500)
        self.assertIn("cryptographically secure", field.help_text)

    def test_get_prep_value_encryption(self):
        """Test value preparation (encryption) for database storage."""
        plaintext = "user@example.com"

        encrypted = self.field.get_prep_value(plaintext)

        self.assertNotEqual(encrypted, plaintext)
        self.assertTrue(encrypted.startswith("FERNET_V1:"))

    def test_get_prep_value_already_encrypted(self):
        """Test that already encrypted values are not double-encrypted."""
        already_encrypted = "FERNET_V1:some_encrypted_data"

        result = self.field.get_prep_value(already_encrypted)

        self.assertEqual(result, already_encrypted)

    def test_get_prep_value_invalid_type(self):
        """Test validation with invalid data types."""
        with self.assertRaises(ValidationError):
            self.field.get_prep_value(123)

        with self.assertRaises(ValidationError):
            self.field.get_prep_value(['list', 'data'])

    def test_from_db_value_decryption(self):
        """Test value retrieval (decryption) from database."""
        plaintext = "user@example.com"
        encrypted = SecureEncryptionService.encrypt(plaintext)

        decrypted = self.field.from_db_value(encrypted, None, None)

        self.assertEqual(decrypted, plaintext)

    def test_from_db_value_legacy_format(self):
        """Test handling of legacy encryption format."""
        # Create mock legacy data
        legacy_data = "ENC_V1:some_legacy_data"

        # Mock the migration to return success
        with patch.object(SecureEncryptionService, 'migrate_legacy_data') as mock_migrate:
            mock_migrate.return_value = (True, "FERNET_V1:migrated_data")

            with patch.object(SecureEncryptionService, 'decrypt') as mock_decrypt:
                mock_decrypt.return_value = "decrypted_data"

                result = self.field.from_db_value(legacy_data, None, None)

                self.assertEqual(result, "decrypted_data")
                mock_migrate.assert_called_once()

    def test_from_db_value_unversioned_data(self):
        """Test handling of unversioned (possibly plaintext) data."""
        unversioned_data = "plaintext_or_old_format"

        # Should attempt migration and fall back to plaintext
        result = self.field.from_db_value(unversioned_data, None, None)

        # Should return the original data as fallback
        self.assertEqual(result, unversioned_data)

    def test_from_db_value_error_handling(self):
        """Test error handling during decryption."""
        invalid_data = "FERNET_V1:invalid_encrypted_data"

        # Should return None instead of raising exception
        result = self.field.from_db_value(invalid_data, None, None)

        self.assertIsNone(result)

    def test_format_detection_methods(self):
        """Test internal format detection methods."""
        # Test secure format detection
        self.assertTrue(self.field._is_secure_format("FERNET_V1:encrypted_data"))
        self.assertFalse(self.field._is_secure_format("ENC_V1:legacy_data"))
        self.assertFalse(self.field._is_secure_format("plaintext"))

        # Test legacy format detection
        self.assertTrue(self.field._is_legacy_format("ENC_V1:legacy_data"))
        self.assertFalse(self.field._is_legacy_format("FERNET_V1:secure_data"))
        self.assertFalse(self.field._is_legacy_format("plaintext"))

    def test_contribute_to_class(self):
        """Test that field properly adds security properties to model class."""
        # Create a mock model class
        class MockModel:
            pass

        # Contribute field to class
        self.field.contribute_to_class(MockModel, 'secure_email')

        # Check that security properties were added
        self.assertTrue(hasattr(MockModel, 'is_secure_email_securely_encrypted'))
        self.assertTrue(hasattr(MockModel, 'secure_email_needs_migration'))

    def test_deconstruct_for_migrations(self):
        """Test field deconstruction for Django migrations."""
        name, path, args, kwargs = self.field.deconstruct()

        # Should remove default help_text to avoid migration noise
        self.assertNotIn('help_text', kwargs)


class SecurityIntegrationTest(TestCase):
    """Integration tests for security components."""

    def test_end_to_end_encryption(self):
        """Test complete encryption flow from field to service."""
        field = EnhancedSecureString()
        original_email = "test@example.com"

        # Prepare value (encrypt)
        encrypted = field.get_prep_value(original_email)

        # Store and retrieve (decrypt)
        decrypted = field.from_db_value(encrypted, None, None)

        self.assertEqual(decrypted, original_email)
        self.assertNotEqual(encrypted, original_email)
        self.assertTrue(SecureEncryptionService.is_securely_encrypted(encrypted))

    def test_performance_reasonable(self):
        """Test that encryption/decryption performance is reasonable."""
        import time

        data = "performance_test@example.com"
        iterations = 100

        # Test encryption performance
        start_time = time.time()
        for _ in range(iterations):
            encrypted = SecureEncryptionService.encrypt(data)
        encryption_time = time.time() - start_time

        # Test decryption performance
        start_time = time.time()
        for _ in range(iterations):
            SecureEncryptionService.decrypt(encrypted)
        decryption_time = time.time() - start_time

        # Should complete within reasonable time (adjust thresholds as needed)
        self.assertLess(encryption_time, 5.0)  # 5 seconds for 100 operations
        self.assertLess(decryption_time, 5.0)  # 5 seconds for 100 operations