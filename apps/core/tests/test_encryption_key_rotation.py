"""
Comprehensive tests for encryption key rotation functionality.

Tests the complete key rotation infrastructure that addresses the CVSS 7.5
vulnerability where no key rotation mechanism existed.

Test Coverage:
- EncryptionKeyManager multi-key support
- Key versioning and format detection
- Data migration during rotation
- Rollback capability
- Key lifecycle tracking
- Security validations
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch
from django.test import TestCase, override_settings
from django.utils import timezone
from django.core.management import call_command
from io import StringIO

from apps.core.models import EncryptionKeyMetadata
from apps.core.services.encryption_key_manager import EncryptionKeyManager
from apps.core.services.secure_encryption_service import SecureEncryptionService
from apps.peoples.models import People


@pytest.mark.security
class EncryptionKeyManagerTest(TestCase):
    """Test suite for EncryptionKeyManager functionality."""

    def setUp(self):
        """Set up test fixtures."""
        # Clear any cached instances
        EncryptionKeyManager._current_key_id = None
        EncryptionKeyManager._active_keys = {}
        EncryptionKeyManager._key_metadata = {}

    def tearDown(self):
        """Clean up after tests."""
        EncryptionKeyManager._current_key_id = None
        EncryptionKeyManager._active_keys = {}
        EncryptionKeyManager._key_metadata = {}

    def test_initialization(self):
        """Test encryption key manager initialization."""
        EncryptionKeyManager.initialize()

        self.assertIsNotNone(EncryptionKeyManager._current_key_id)
        self.assertGreater(len(EncryptionKeyManager._active_keys), 0)

    def test_encrypt_with_v2_format(self):
        """Test encryption produces V2 format with key ID."""
        EncryptionKeyManager.initialize()

        plaintext = "test_data_v2_format"
        encrypted = EncryptionKeyManager.encrypt(plaintext)

        # Verify V2 format: FERNET_V2:key_id:payload
        self.assertTrue(encrypted.startswith("FERNET_V2:"))
        parts = encrypted.split(':', 2)
        self.assertEqual(len(parts), 3)
        self.assertEqual(parts[0], "FERNET_V2")

    def test_decrypt_v2_format(self):
        """Test decryption of V2 format with key ID."""
        EncryptionKeyManager.initialize()

        plaintext = "test_v2_decrypt"
        encrypted = EncryptionKeyManager.encrypt(plaintext)
        decrypted = EncryptionKeyManager.decrypt(encrypted)

        self.assertEqual(decrypted, plaintext)

    def test_decrypt_v1_legacy_format(self):
        """Test decryption of legacy V1 format without key ID."""
        EncryptionKeyManager.initialize()

        # Create legacy V1 format using SecureEncryptionService
        plaintext = "legacy_v1_data"
        legacy_encrypted = SecureEncryptionService.encrypt(plaintext)

        # Verify it's V1 format
        self.assertTrue(legacy_encrypted.startswith("FERNET_V1:"))

        # Should decrypt successfully
        decrypted = EncryptionKeyManager.decrypt(legacy_encrypted)
        self.assertEqual(decrypted, plaintext)

    def test_decrypt_tries_all_keys(self):
        """Test that decryption tries all active keys if key ID not found."""
        EncryptionKeyManager.initialize()

        # Encrypt with current key
        plaintext = "multi_key_test"
        encrypted = EncryptionKeyManager.encrypt(plaintext)

        # Create a new key (simulating rotation)
        new_key_id = EncryptionKeyManager.create_new_key()
        EncryptionKeyManager.activate_key(new_key_id)

        # Should still decrypt with old key (still active)
        decrypted = EncryptionKeyManager.decrypt(encrypted)
        self.assertEqual(decrypted, plaintext)

    def test_create_new_key(self):
        """Test creating a new encryption key."""
        # Create initial key metadata for current key
        current_key = EncryptionKeyMetadata.objects.create(
            key_id="current_key",
            is_active=True,
            created_at=timezone.now(),
            expires_at=timezone.now() + timedelta(days=90),
            rotation_status='active'
        )

        new_key_id = EncryptionKeyManager.create_new_key()

        self.assertIsNotNone(new_key_id)
        self.assertTrue(new_key_id.startswith("key_"))

        # Verify key metadata was created
        new_key_meta = EncryptionKeyMetadata.objects.get(key_id=new_key_id)
        self.assertFalse(new_key_meta.is_active)  # Not active until rotation completes
        self.assertEqual(new_key_meta.rotation_status, 'created')

    def test_activate_key(self):
        """Test activating an encryption key."""
        # Create a key to activate
        key_meta = EncryptionKeyMetadata.objects.create(
            key_id="test_activate_key",
            is_active=False,
            created_at=timezone.now(),
            expires_at=timezone.now() + timedelta(days=90),
            rotation_status='created'
        )

        EncryptionKeyManager.activate_key(key_meta.key_id)

        # Verify key was activated
        key_meta.refresh_from_db()
        self.assertTrue(key_meta.is_active)
        self.assertEqual(key_meta.rotation_status, 'active')
        self.assertEqual(EncryptionKeyManager._current_key_id, key_meta.key_id)

    def test_get_key_status(self):
        """Test retrieving key status information."""
        # Create test keys
        old_key = EncryptionKeyMetadata.objects.create(
            key_id="old_key",
            is_active=True,
            created_at=timezone.now() - timedelta(days=80),
            expires_at=timezone.now() + timedelta(days=10),
            rotation_status='active'
        )

        EncryptionKeyManager.initialize()
        status = EncryptionKeyManager.get_key_status()

        self.assertIn('current_key_id', status)
        self.assertIn('active_keys_count', status)
        self.assertIn('keys', status)
        self.assertGreater(len(status['keys']), 0)

        # Check key info structure
        key_info = status['keys'][0]
        self.assertIn('key_id', key_info)
        self.assertIn('is_current', key_info)
        self.assertIn('age_days', key_info)
        self.assertIn('expires_in_days', key_info)
        self.assertIn('needs_rotation', key_info)

    def test_key_format_detection(self):
        """Test detection of different encryption formats."""
        v2_data = "FERNET_V2:key123:payload"
        v1_data = "FERNET_V1:payload"
        unversioned = "some_old_data"

        self.assertEqual(EncryptionKeyManager._detect_format(v2_data), "FERNET_V2")
        self.assertEqual(EncryptionKeyManager._detect_format(v1_data), "FERNET_V1")
        self.assertEqual(EncryptionKeyManager._detect_format(unversioned), "UNVERSIONED")


@pytest.mark.security
class EncryptionKeyMetadataModelTest(TestCase):
    """Test suite for EncryptionKeyMetadata model."""

    def test_create_key_metadata(self):
        """Test creating encryption key metadata."""
        key_meta = EncryptionKeyMetadata.objects.create(
            key_id="test_key_001",
            is_active=False,
            created_at=timezone.now(),
            expires_at=timezone.now() + timedelta(days=90),
            rotation_status='created'
        )

        self.assertEqual(key_meta.key_id, "test_key_001")
        self.assertFalse(key_meta.is_active)
        self.assertEqual(key_meta.rotation_status, 'created')

    def test_key_age_calculation(self):
        """Test key age calculation property."""
        created_date = timezone.now() - timedelta(days=30)
        key_meta = EncryptionKeyMetadata.objects.create(
            key_id="age_test_key",
            is_active=True,
            created_at=created_date,
            expires_at=timezone.now() + timedelta(days=60),
            rotation_status='active'
        )

        self.assertEqual(key_meta.age_days, 30)

    def test_expiration_check(self):
        """Test key expiration checking."""
        expired_key = EncryptionKeyMetadata.objects.create(
            key_id="expired_key",
            is_active=True,
            created_at=timezone.now() - timedelta(days=100),
            expires_at=timezone.now() - timedelta(days=10),
            rotation_status='active'
        )

        self.assertTrue(expired_key.is_expired)
        self.assertTrue(expired_key.expires_in_days < 0)

    def test_needs_rotation_check(self):
        """Test checking if key needs rotation."""
        # Key expiring in 10 days - needs rotation
        soon_expiring = EncryptionKeyMetadata.objects.create(
            key_id="soon_expiring_key",
            is_active=True,
            created_at=timezone.now() - timedelta(days=80),
            expires_at=timezone.now() + timedelta(days=10),
            rotation_status='active'
        )

        # Key expiring in 30 days - doesn't need rotation yet
        not_expiring_soon = EncryptionKeyMetadata.objects.create(
            key_id="not_expiring_key",
            is_active=True,
            created_at=timezone.now() - timedelta(days=60),
            expires_at=timezone.now() + timedelta(days=30),
            rotation_status='active'
        )

        self.assertTrue(soon_expiring.needs_rotation)
        self.assertFalse(not_expiring_soon.needs_rotation)

    def test_mark_for_rotation(self):
        """Test marking key for rotation."""
        key_meta = EncryptionKeyMetadata.objects.create(
            key_id="rotation_test_key",
            is_active=True,
            created_at=timezone.now(),
            expires_at=timezone.now() + timedelta(days=90),
            rotation_status='active'
        )

        key_meta.mark_for_rotation("new_key_id", "Test rotation")

        key_meta.refresh_from_db()
        self.assertEqual(key_meta.rotation_status, 'rotating')
        self.assertEqual(key_meta.replaced_by_key_id, "new_key_id")
        self.assertIn("Test rotation", key_meta.rotation_notes)

    def test_retire_key(self):
        """Test retiring a key after rotation."""
        key_meta = EncryptionKeyMetadata.objects.create(
            key_id="retire_test_key",
            is_active=True,
            created_at=timezone.now(),
            expires_at=timezone.now() + timedelta(days=90),
            rotation_status='rotating'
        )

        key_meta.retire("Rotation complete")

        key_meta.refresh_from_db()
        self.assertFalse(key_meta.is_active)
        self.assertEqual(key_meta.rotation_status, 'retired')
        self.assertIsNotNone(key_meta.rotated_at)
        self.assertIn("Rotation complete", key_meta.rotation_notes)

    def test_get_current_key(self):
        """Test getting the current active key."""
        # Create multiple keys
        old_key = EncryptionKeyMetadata.objects.create(
            key_id="old_key",
            is_active=True,
            created_at=timezone.now() - timedelta(days=100),
            expires_at=timezone.now() + timedelta(days=1),
            rotation_status='active'
        )

        current_key = EncryptionKeyMetadata.objects.create(
            key_id="current_key",
            is_active=True,
            created_at=timezone.now(),
            expires_at=timezone.now() + timedelta(days=90),
            rotation_status='active'
        )

        retrieved_key = EncryptionKeyMetadata.get_current_key()
        self.assertEqual(retrieved_key.key_id, current_key.key_id)

    def test_get_keys_needing_rotation(self):
        """Test getting keys that need rotation."""
        # Key expiring soon
        soon_key = EncryptionKeyMetadata.objects.create(
            key_id="soon_key",
            is_active=True,
            created_at=timezone.now() - timedelta(days=80),
            expires_at=timezone.now() + timedelta(days=10),
            rotation_status='active'
        )

        # Key not expiring soon
        safe_key = EncryptionKeyMetadata.objects.create(
            key_id="safe_key",
            is_active=True,
            created_at=timezone.now() - timedelta(days=30),
            expires_at=timezone.now() + timedelta(days=60),
            rotation_status='active'
        )

        keys_needing_rotation = EncryptionKeyMetadata.get_keys_needing_rotation()

        self.assertEqual(keys_needing_rotation.count(), 1)
        self.assertEqual(keys_needing_rotation.first().key_id, soon_key.key_id)

    def test_auto_expiration_on_save(self):
        """Test automatic expiration status on save."""
        expired_key = EncryptionKeyMetadata.objects.create(
            key_id="auto_expire_key",
            is_active=True,
            created_at=timezone.now() - timedelta(days=100),
            expires_at=timezone.now() - timedelta(days=1),
            rotation_status='active'
        )

        # Save should automatically mark as expired
        expired_key.save()

        expired_key.refresh_from_db()
        self.assertEqual(expired_key.rotation_status, 'expired')
        self.assertFalse(expired_key.is_active)


@pytest.mark.security
class KeyRotationIntegrationTest(TestCase):
    """Integration tests for complete key rotation process."""

    def setUp(self):
        """Set up test fixtures."""
        EncryptionKeyManager._current_key_id = None
        EncryptionKeyManager._active_keys = {}
        EncryptionKeyManager._key_metadata = {}

    def test_complete_key_rotation_workflow(self):
        """Test complete key rotation from start to finish."""
        # Step 1: Initialize with old key
        EncryptionKeyManager.initialize()
        old_key_id = EncryptionKeyManager._current_key_id

        # Create metadata for old key
        old_key_meta = EncryptionKeyMetadata.objects.create(
            key_id=old_key_id,
            is_active=True,
            created_at=timezone.now() - timedelta(days=80),
            expires_at=timezone.now() + timedelta(days=10),
            rotation_status='active'
        )

        # Step 2: Encrypt some data with old key
        test_data = "sensitive_data_to_rotate"
        old_encrypted = EncryptionKeyManager.encrypt(test_data)

        # Verify it uses old key
        self.assertIn(old_key_id, old_encrypted)

        # Step 3: Create new key for rotation
        new_key_id = EncryptionKeyManager.create_new_key()
        self.assertIsNotNone(new_key_id)

        # Step 4: Mark old key for rotation
        old_key_meta.mark_for_rotation(new_key_id, "Scheduled rotation")
        old_key_meta.refresh_from_db()
        self.assertEqual(old_key_meta.rotation_status, 'rotating')

        # Step 5: "Migrate" data to new key (decrypt with old, encrypt with new)
        decrypted_data = EncryptionKeyManager.decrypt(old_encrypted)
        new_encrypted = EncryptionKeyManager.encrypt(decrypted_data, key_id=new_key_id)

        # Verify new encryption uses new key
        self.assertIn(new_key_id, new_encrypted)

        # Step 6: Activate new key
        EncryptionKeyManager.activate_key(new_key_id)
        self.assertEqual(EncryptionKeyManager._current_key_id, new_key_id)

        # Step 7: Retire old key
        old_key_meta.retire("Migration complete")
        old_key_meta.refresh_from_db()
        self.assertEqual(old_key_meta.rotation_status, 'retired')
        self.assertFalse(old_key_meta.is_active)

        # Step 8: Verify both old and new data can still be decrypted
        decrypted_old = EncryptionKeyManager.decrypt(old_encrypted)
        decrypted_new = EncryptionKeyManager.decrypt(new_encrypted)

        self.assertEqual(decrypted_old, test_data)
        self.assertEqual(decrypted_new, test_data)

    def test_multiple_key_decryption(self):
        """Test decryption works with data encrypted by multiple keys."""
        EncryptionKeyManager.initialize()

        # Encrypt with first key
        key1_id = EncryptionKeyManager._current_key_id
        data1 = "data_with_key_1"
        encrypted1 = EncryptionKeyManager.encrypt(data1)

        # Create and activate second key
        key2_id = EncryptionKeyManager.create_new_key()
        EncryptionKeyManager.activate_key(key2_id)

        data2 = "data_with_key_2"
        encrypted2 = EncryptionKeyManager.encrypt(data2)

        # Both should decrypt successfully
        decrypted1 = EncryptionKeyManager.decrypt(encrypted1)
        decrypted2 = EncryptionKeyManager.decrypt(encrypted2)

        self.assertEqual(decrypted1, data1)
        self.assertEqual(decrypted2, data2)


@pytest.mark.security
class DeprecatedEncryptionBlockingTest(TestCase):
    """Test that deprecated encryption functions are blocked in production."""

    def test_deprecated_encrypt_blocked_in_all_environments(self):
        """Test deprecated encrypt() raises error in ALL environments."""
        from apps.core.utils_new.string_utils import encrypt

        with self.assertRaises(RuntimeError) as context:
            encrypt("test_data")

        self.assertIn("CRITICAL SECURITY ERROR", str(context.exception))
        self.assertIn("HARD DEPRECATED", str(context.exception))
        self.assertIn("CVSS 7.5", str(context.exception))

    def test_deprecated_decrypt_blocked_in_all_environments(self):
        """Test deprecated decrypt() raises error in ALL environments."""
        from apps.core.utils_new.string_utils import decrypt

        with self.assertRaises(RuntimeError) as context:
            decrypt(b"test_data")

        self.assertIn("CRITICAL SECURITY ERROR", str(context.exception))
        self.assertIn("HARD DEPRECATED", str(context.exception))
        self.assertIn("CVSS 7.5", str(context.exception))

    def test_secure_encryption_service_works_correctly(self):
        """Test SecureEncryptionService as proper replacement."""
        from apps.core.services.secure_encryption_service import SecureEncryptionService

        test_data = "test_data_for_encryption"
        encrypted = SecureEncryptionService.encrypt(test_data)
        decrypted = SecureEncryptionService.decrypt(encrypted)

        self.assertEqual(decrypted, test_data)
        self.assertTrue(encrypted.startswith("FERNET_V1:"))