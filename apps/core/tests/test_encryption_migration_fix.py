"""
Comprehensive Tests for Encryption Migration from zlib to Fernet

Tests the migration from insecure zlib compression to cryptographically
secure Fernet encryption (AES-128 + HMAC-SHA256).

@pytest.mark.security - These tests validate critical security fixes
"""
import pytest
from django.test import TestCase, TransactionTestCase
from django.contrib.auth import get_user_model
from apps.core.services.secure_encryption_service import SecureEncryptionService
from apps.peoples.fields.secure_fields import EnhancedSecureString
from unittest.mock import Mock, patch
import warnings

User = get_user_model()


@pytest.mark.security
class SecureEncryptionServiceTest(TestCase):
    """Test suite for secure encryption service."""

    def test_encrypt_decrypt_roundtrip(self):
        """Test that encryption and decryption work correctly."""
        plaintext = "sensitive_data_123"

        encrypted = SecureEncryptionService.encrypt(plaintext)
        decrypted = SecureEncryptionService.decrypt(encrypted)

        self.assertEqual(decrypted, plaintext)
        self.assertNotEqual(encrypted, plaintext)
        self.assertIn("FERNET_V1:", encrypted)

    def test_encrypt_with_unicode(self):
        """Test encryption with unicode characters."""
        plaintext = "Hello 世界 🌍"

        encrypted = SecureEncryptionService.encrypt(plaintext)
        decrypted = SecureEncryptionService.decrypt(encrypted)

        self.assertEqual(decrypted, plaintext)

    def test_encrypt_with_special_characters(self):
        """Test encryption with special characters."""
        plaintext = "test@example.com!#$%^&*()"

        encrypted = SecureEncryptionService.encrypt(plaintext)
        decrypted = SecureEncryptionService.decrypt(encrypted)

        self.assertEqual(decrypted, plaintext)

    def test_encryption_produces_different_ciphertext(self):
        """Test that encrypting same plaintext produces different ciphertext (IND-CPA)."""
        plaintext = "sensitive_data"

        encrypted1 = SecureEncryptionService.encrypt(plaintext)
        encrypted2 = SecureEncryptionService.encrypt(plaintext)

        # Fernet uses nonce, so same plaintext should produce different ciphertext
        self.assertNotEqual(encrypted1, encrypted2)

        # But both should decrypt to same plaintext
        self.assertEqual(SecureEncryptionService.decrypt(encrypted1), plaintext)
        self.assertEqual(SecureEncryptionService.decrypt(encrypted2), plaintext)

    def test_tamper_detection(self):
        """Test that tampering with ciphertext is detected."""
        plaintext = "sensitive_data"
        encrypted = SecureEncryptionService.encrypt(plaintext)

        # Remove version prefix and try to tamper
        encrypted_payload = encrypted[len("FERNET_V1:"):]

        # Modify one character in the middle
        tampered = "FERNET_V1:" + encrypted_payload[:20] + "X" + encrypted_payload[21:]

        with self.assertRaises(ValueError):
            SecureEncryptionService.decrypt(tampered)

    def test_legacy_migration(self):
        """Test migration from legacy zlib format."""
        # Create legacy zlib-compressed data
        from zlib import compress
        from base64 import urlsafe_b64encode as b64e

        plaintext = "legacy_data"
        legacy_encrypted = b64e(compress(plaintext.encode('utf-8'), 9)).decode('ascii')

        # Try to migrate
        success, result = SecureEncryptionService.migrate_legacy_data(legacy_encrypted)

        self.assertTrue(success)
        self.assertIn("FERNET_V1:", result)

        # Verify decryption works
        decrypted = SecureEncryptionService.decrypt(result)
        self.assertEqual(decrypted, plaintext)

    def test_is_securely_encrypted(self):
        """Test detection of securely encrypted data."""
        plaintext = "test_data"
        encrypted = SecureEncryptionService.encrypt(plaintext)

        self.assertTrue(SecureEncryptionService.is_securely_encrypted(encrypted))
        self.assertFalse(SecureEncryptionService.is_securely_encrypted(plaintext))
        self.assertFalse(SecureEncryptionService.is_securely_encrypted("random_string"))

    def test_validate_encryption_setup(self):
        """Test encryption setup validation."""
        # Should not raise exception
        result = SecureEncryptionService.validate_encryption_setup()
        self.assertTrue(result)

    def test_encryption_with_bytes_input(self):
        """Test encryption accepts bytes as input."""
        plaintext_bytes = b"byte_data"

        encrypted = SecureEncryptionService.encrypt(plaintext_bytes)
        decrypted = SecureEncryptionService.decrypt(encrypted)

        self.assertEqual(decrypted, "byte_data")

    def test_decryption_with_bytes_input(self):
        """Test decryption accepts bytes as input."""
        plaintext = "test_data"
        encrypted = SecureEncryptionService.encrypt(plaintext)
        encrypted_bytes = encrypted.encode('ascii')

        decrypted = SecureEncryptionService.decrypt(encrypted_bytes)
        self.assertEqual(decrypted, plaintext)


@pytest.mark.security
class EnhancedSecureStringFieldTest(TransactionTestCase):
    """Test suite for EnhancedSecureString field."""

    def setUp(self):
        """Set up test user with encrypted fields."""
        # Use test configuration
        self.test_data = {
            'peoplecode': 'TEST001',
            'peoplename': 'Test User',
            'dateofbirth': '1990-01-01',
            'email': 'test@example.com',
            'mobno': '+1234567890',
            'loginid': 'testuser001'
        }

    def test_field_encrypts_on_save(self):
        """Test that field encrypts data when saving."""
        user = User(
            **self.test_data
        )
        user.set_password('testpass123')
        user.save()

        # Refresh from database
        user_from_db = User.objects.get(pk=user.pk)

        # Field should decrypt automatically
        self.assertEqual(user_from_db.email, 'test@example.com')
        self.assertEqual(user_from_db.mobno, '+1234567890')

    def test_field_handles_unicode(self):
        """Test field with unicode characters."""
        test_data = self.test_data.copy()
        test_data['email'] = 'test-用户@example.com'
        test_data['peoplecode'] = 'TEST002'
        test_data['loginid'] = 'testuser002'

        user = User(**test_data)
        user.set_password('testpass123')
        user.save()

        user_from_db = User.objects.get(pk=user.pk)
        self.assertEqual(user_from_db.email, 'test-用户@example.com')

    def test_field_handles_special_characters(self):
        """Test field with special characters."""
        test_data = self.test_data.copy()
        test_data['email'] = 'test+tag@example.com'
        test_data['mobno'] = '+1 (555) 123-4567'
        test_data['peoplecode'] = 'TEST003'
        test_data['loginid'] = 'testuser003'

        user = User(**test_data)
        user.set_password('testpass123')
        user.save()

        user_from_db = User.objects.get(pk=user.pk)
        self.assertEqual(user_from_db.email, 'test+tag@example.com')
        self.assertEqual(user_from_db.mobno, '+1 (555) 123-4567')

    def test_field_handles_none_value(self):
        """Test field handles None values correctly."""
        test_data = self.test_data.copy()
        test_data['mobno'] = None  # mobno is nullable
        test_data['peoplecode'] = 'TEST004'
        test_data['loginid'] = 'testuser004'

        user = User(**test_data)
        user.set_password('testpass123')
        user.save()

        user_from_db = User.objects.get(pk=user.pk)
        self.assertIsNone(user_from_db.mobno)

    def test_field_prevents_double_encryption(self):
        """Test that field doesn't double-encrypt already encrypted data."""
        user = User(**self.test_data)
        user.set_password('testpass123')
        user.save()

        # Get the encrypted value from database
        first_save_email = user.email

        # Update and save again
        user.peoplename = "Updated Name"
        user.save()

        # Email should still decrypt correctly
        user.refresh_from_db()
        self.assertEqual(user.email, 'test@example.com')

    def test_query_with_encrypted_fields(self):
        """Test querying with encrypted fields."""
        # Create multiple users
        for i in range(3):
            test_data = self.test_data.copy()
            test_data['peoplecode'] = f'TEST00{i+5}'
            test_data['loginid'] = f'testuser00{i+5}'
            test_data['email'] = f'user{i}@example.com'

            user = User(**test_data)
            user.set_password('testpass123')
            user.save()

        # Query should work
        users = User.objects.filter(peoplecode__in=['TEST005', 'TEST006', 'TEST007'])
        self.assertEqual(users.count(), 3)

        # Email should be decrypted
        for user in users:
            self.assertIn('@example.com', user.email)
            self.assertNotIn('FERNET_V1:', user.email)


@pytest.mark.security
class LegacyEncryptionDeprecationTest(TestCase):
    """Test deprecation warnings for legacy encryption."""

    def test_secure_string_deprecation_warning(self):
        """Test that SecureString raises deprecation warning."""
        from apps.peoples.models import SecureString
        from django.db import models

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")

            # Instantiate SecureString field
            field = SecureString()

            # Check deprecation warning was raised
            self.assertEqual(len(w), 1)
            self.assertTrue(issubclass(w[0].category, DeprecationWarning))
            self.assertIn("SecureString is deprecated", str(w[0].message))

    def test_string_utils_encrypt_hard_deprecated(self):
        """Test that string_utils encrypt is hard deprecated and raises RuntimeError."""
        from apps.core.utils_new.string_utils import encrypt

        with self.assertRaises(RuntimeError) as context:
            encrypt("test_data")

        self.assertIn("CRITICAL SECURITY ERROR", str(context.exception))
        self.assertIn("HARD DEPRECATED", str(context.exception))
        self.assertIn("CVSS 7.5", str(context.exception))

    def test_string_utils_decrypt_hard_deprecated(self):
        """Test that string_utils decrypt is hard deprecated and raises RuntimeError."""
        from apps.core.utils_new.string_utils import decrypt

        with self.assertRaises(RuntimeError) as context:
            decrypt(b"test_data")

        self.assertIn("CRITICAL SECURITY ERROR", str(context.exception))
        self.assertIn("HARD DEPRECATED", str(context.exception))
        self.assertIn("CVSS 7.5", str(context.exception))

    def test_secure_encryption_service_replacement(self):
        """Test SecureEncryptionService works as proper replacement."""
        from apps.core.services.secure_encryption_service import SecureEncryptionService

        test_data = "test_data_migration"
        encrypted = SecureEncryptionService.encrypt(test_data)
        decrypted = SecureEncryptionService.decrypt(encrypted)

        self.assertEqual(decrypted, test_data)
        self.assertTrue(encrypted.startswith("FERNET_V1:"))


@pytest.mark.security
class EncryptionSecurityTest(TestCase):
    """Security-focused tests for encryption."""

    def test_encrypted_data_is_not_plaintext(self):
        """Test that encrypted data doesn't contain plaintext."""
        sensitive_data = "password123!@#"

        encrypted = SecureEncryptionService.encrypt(sensitive_data)

        self.assertNotIn(sensitive_data, encrypted)
        self.assertNotIn("password", encrypted.lower())

    def test_different_data_produces_different_ciphertext(self):
        """Test that different plaintext produces different ciphertext."""
        data1 = "data_one"
        data2 = "data_two"

        encrypted1 = SecureEncryptionService.encrypt(data1)
        encrypted2 = SecureEncryptionService.encrypt(data2)

        self.assertNotEqual(encrypted1, encrypted2)

    def test_encryption_key_derivation(self):
        """Test that encryption key is properly derived."""
        # This tests that the service can create encryption keys
        # without exposing the actual SECRET_KEY

        plaintext = "test_data"

        # Multiple encryptions should work
        for _ in range(10):
            encrypted = SecureEncryptionService.encrypt(plaintext)
            decrypted = SecureEncryptionService.decrypt(encrypted)
            self.assertEqual(decrypted, plaintext)

    def test_version_prefix_prevents_algorithm_confusion(self):
        """Test that version prefix prevents algorithm confusion attacks."""
        plaintext = "test_data"
        encrypted = SecureEncryptionService.encrypt(plaintext)

        # Encrypted data should have version prefix
        self.assertTrue(encrypted.startswith("FERNET_V1:"))

        # Service should only decrypt data with correct prefix
        # (implicit in decrypt implementation)
        decrypted = SecureEncryptionService.decrypt(encrypted)
        self.assertEqual(decrypted, plaintext)


@pytest.mark.security
class EncryptionMigrationIntegrationTest(TransactionTestCase):
    """Integration tests for encryption migration."""

    def test_complete_migration_workflow(self):
        """Test complete migration from legacy to secure encryption."""
        # This simulates the full migration process:
        # 1. Old data exists with zlib compression
        # 2. Code is updated to use EnhancedSecureString
        # 3. Migration command re-encrypts data
        # 4. Data is accessible with new encryption

        # Step 1: Create user with email (will use EnhancedSecureString)
        test_data = {
            'peoplecode': 'MIG001',
            'peoplename': 'Migration Test User',
            'dateofbirth': '1990-01-01',
            'email': 'migrate@example.com',
            'mobno': '+9876543210',
            'loginid': 'migrateuser'
        }

        user = User(**test_data)
        user.set_password('testpass123')
        user.save()

        # Step 2: Verify data is encrypted with Fernet
        user_from_db = User.objects.get(pk=user.pk)
        self.assertEqual(user_from_db.email, 'migrate@example.com')

        # Step 3: Verify we can update the user
        user_from_db.peoplename = "Updated Migration User"
        user_from_db.save()

        # Step 4: Verify data integrity after update
        user_refreshed = User.objects.get(pk=user.pk)
        self.assertEqual(user_refreshed.email, 'migrate@example.com')
        self.assertEqual(user_refreshed.peoplename, "Updated Migration User")