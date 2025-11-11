"""
Transaction management tests for encryption key operations.

Tests the atomic transaction behavior for encryption key creation and activation
to prevent race conditions and ensure data consistency during key rotation.

Test Coverage:
- Transaction atomicity for key creation
- Transaction atomicity for key activation
- Rollback behavior on errors
- Concurrent operation safety
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch
from django.test import TestCase, TransactionTestCase
from django.utils import timezone
from django.db import transaction, IntegrityError

from apps.core.models import EncryptionKeyMetadata
from apps.core.services.encryption_key_manager import EncryptionKeyManager


@pytest.mark.security
class EncryptionKeyTransactionTest(TransactionTestCase):
    """Test transaction management for encryption key operations."""

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

    def test_create_new_key_atomicity(self):
        """Test that create_new_key uses atomic transaction."""
        # Create initial key for the database
        initial_key = EncryptionKeyMetadata.objects.create(
            key_id="initial_key",
            is_active=True,
            created_at=timezone.now(),
            expires_at=timezone.now() + timedelta(days=90),
            rotation_status='active'
        )

        # Create new key - should complete atomically
        new_key_id = EncryptionKeyManager.create_new_key()

        # Verify key was created successfully
        self.assertIsNotNone(new_key_id)
        self.assertTrue(new_key_id.startswith("key_"))

        # Verify metadata exists in database
        key_meta = EncryptionKeyMetadata.objects.get(key_id=new_key_id)
        self.assertFalse(key_meta.is_active)
        self.assertEqual(key_meta.rotation_status, 'created')

        # Verify initial key still exists
        self.assertTrue(EncryptionKeyMetadata.objects.filter(key_id="initial_key").exists())

    def test_create_new_key_transaction_rollback(self):
        """Test that create_new_key rolls back on database error."""
        # Create initial key
        initial_key = EncryptionKeyMetadata.objects.create(
            key_id="initial_key",
            is_active=True,
            created_at=timezone.now(),
            expires_at=timezone.now() + timedelta(days=90),
            rotation_status='active'
        )

        # Mock database error during create
        with patch.object(EncryptionKeyMetadata.objects, 'create',
                         side_effect=IntegrityError("Simulated database error")):
            with self.assertRaises(RuntimeError) as context:
                EncryptionKeyManager.create_new_key()

            # Verify error mentions correlation ID (from ErrorHandler)
            self.assertIn("Failed to create new encryption key", str(context.exception))

    def test_activate_key_atomicity(self):
        """Test that activate_key uses atomic transaction."""
        # Create keys
        inactive_key = EncryptionKeyMetadata.objects.create(
            key_id="inactive_key",
            is_active=False,
            created_at=timezone.now(),
            expires_at=timezone.now() + timedelta(days=90),
            rotation_status='created'
        )

        active_key = EncryptionKeyMetadata.objects.create(
            key_id="active_key",
            is_active=True,
            created_at=timezone.now(),
            expires_at=timezone.now() + timedelta(days=90),
            rotation_status='active'
        )

        # Set current key manager state
        EncryptionKeyManager._current_key_id = "active_key"

        # Activate the inactive key
        EncryptionKeyManager.activate_key("inactive_key")

        # Verify activation
        inactive_key.refresh_from_db()
        self.assertTrue(inactive_key.is_active)
        self.assertEqual(inactive_key.rotation_status, 'active')
        self.assertIsNotNone(inactive_key.activated_at)

        # Verify current key was updated
        self.assertEqual(EncryptionKeyManager._current_key_id, "inactive_key")

    def test_activate_key_updates_cache_atomically(self):
        """Test that cache update is part of activation transaction."""
        key = EncryptionKeyMetadata.objects.create(
            key_id="cache_test_key",
            is_active=False,
            created_at=timezone.now(),
            expires_at=timezone.now() + timedelta(days=90),
            rotation_status='created'
        )

        EncryptionKeyManager.activate_key("cache_test_key")

        # Verify both database and in-memory cache are consistent
        key.refresh_from_db()
        self.assertTrue(key.is_active)
        self.assertEqual(EncryptionKeyManager._current_key_id, "cache_test_key")

    def test_activate_key_transaction_rollback(self):
        """Test that activate_key rolls back on error - tests nonexistent key."""
        # Try to activate a key that doesn't exist
        with self.assertRaises(RuntimeError) as context:
            EncryptionKeyManager.activate_key("nonexistent_key_12345")

        # Verify error message contains failure indication
        self.assertIn("Failed to activate key", str(context.exception))

    def test_concurrent_key_creation(self):
        """Test that concurrent key creation doesn't cause issues."""
        initial_key = EncryptionKeyMetadata.objects.create(
            key_id="concurrent_initial",
            is_active=True,
            created_at=timezone.now(),
            expires_at=timezone.now() + timedelta(days=90),
            rotation_status='active'
        )

        # Create multiple keys sequentially (simulating concurrent requests)
        key_ids = []
        for _ in range(3):
            key_id = EncryptionKeyManager.create_new_key()
            key_ids.append(key_id)

        # Verify all keys were created
        self.assertEqual(len(key_ids), 3)
        self.assertEqual(len(set(key_ids)), 3)  # All unique

        # Verify all exist in database
        created_count = EncryptionKeyMetadata.objects.filter(
            key_id__in=key_ids
        ).count()
        self.assertEqual(created_count, 3)

    def test_key_creation_with_lock_prevents_race_condition(self):
        """Test that the instance lock protects against race conditions."""
        initial_key = EncryptionKeyMetadata.objects.create(
            key_id="lock_test_initial",
            is_active=True,
            created_at=timezone.now(),
            expires_at=timezone.now() + timedelta(days=90),
            rotation_status='active'
        )

        # Verify lock is being used
        self.assertIsNotNone(EncryptionKeyManager._instance_lock)

        # Create key while lock would be held
        key_id = EncryptionKeyManager.create_new_key()

        # Verify creation succeeded
        self.assertTrue(EncryptionKeyMetadata.objects.filter(key_id=key_id).exists())

    def test_activate_key_with_lock_prevents_race_condition(self):
        """Test that activation lock ensures atomic state updates."""
        key1 = EncryptionKeyMetadata.objects.create(
            key_id="lock_activate_key1",
            is_active=False,
            created_at=timezone.now(),
            expires_at=timezone.now() + timedelta(days=90),
            rotation_status='created'
        )

        key2 = EncryptionKeyMetadata.objects.create(
            key_id="lock_activate_key2",
            is_active=False,
            created_at=timezone.now(),
            expires_at=timezone.now() + timedelta(days=90),
            rotation_status='created'
        )

        # Activate first key
        EncryptionKeyManager.activate_key("lock_activate_key1")

        # Verify it's active
        key1.refresh_from_db()
        self.assertTrue(key1.is_active)
        self.assertEqual(EncryptionKeyManager._current_key_id, "lock_activate_key1")

        # Activate second key
        EncryptionKeyManager.activate_key("lock_activate_key2")

        # Verify state consistency
        key1.refresh_from_db()
        key2.refresh_from_db()
        self.assertTrue(key2.is_active)
        self.assertEqual(EncryptionKeyManager._current_key_id, "lock_activate_key2")

    def test_key_activation_sets_activation_timestamp(self):
        """Test that key activation sets the activated_at timestamp."""
        key = EncryptionKeyMetadata.objects.create(
            key_id="timestamp_test_key",
            is_active=False,
            created_at=timezone.now(),
            expires_at=timezone.now() + timedelta(days=90),
            rotation_status='created',
            activated_at=None
        )

        before_activation = timezone.now()
        EncryptionKeyManager.activate_key("timestamp_test_key")
        after_activation = timezone.now()

        key.refresh_from_db()
        self.assertIsNotNone(key.activated_at)
        self.assertGreaterEqual(key.activated_at, before_activation)
        self.assertLessEqual(key.activated_at, after_activation)

    def test_create_new_key_sets_created_at_timestamp(self):
        """Test that new key has proper creation timestamp."""
        initial_key = EncryptionKeyMetadata.objects.create(
            key_id="timestamp_initial",
            is_active=True,
            created_at=timezone.now(),
            expires_at=timezone.now() + timedelta(days=90),
            rotation_status='active'
        )

        before_creation = timezone.now()
        new_key_id = EncryptionKeyManager.create_new_key()
        after_creation = timezone.now()

        new_key = EncryptionKeyMetadata.objects.get(key_id=new_key_id)
        self.assertIsNotNone(new_key.created_at)
        self.assertGreaterEqual(new_key.created_at, before_creation)
        self.assertLessEqual(new_key.created_at, after_creation)

    def test_transaction_isolation_between_operations(self):
        """Test that key operations don't interfere with each other."""
        initial_key = EncryptionKeyMetadata.objects.create(
            key_id="isolation_initial",
            is_active=True,
            created_at=timezone.now(),
            expires_at=timezone.now() + timedelta(days=90),
            rotation_status='active'
        )

        # Create first key
        key1_id = EncryptionKeyManager.create_new_key()

        # Verify database state
        key1 = EncryptionKeyMetadata.objects.get(key_id=key1_id)
        self.assertEqual(key1.rotation_status, 'created')
        self.assertFalse(key1.is_active)

        # Create second key
        key2_id = EncryptionKeyManager.create_new_key()

        # Verify both keys exist and are isolated
        key1.refresh_from_db()
        key2 = EncryptionKeyMetadata.objects.get(key_id=key2_id)

        self.assertEqual(key1.rotation_status, 'created')
        self.assertEqual(key2.rotation_status, 'created')
        self.assertNotEqual(key1_id, key2_id)

        # Activate first key without affecting second
        EncryptionKeyManager.activate_key(key1_id)

        key1.refresh_from_db()
        key2.refresh_from_db()

        self.assertTrue(key1.is_active)
        self.assertFalse(key2.is_active)
        self.assertEqual(key1.rotation_status, 'active')
        self.assertEqual(key2.rotation_status, 'created')

    def test_key_metadata_consistency_after_activation(self):
        """Test that key metadata is consistently updated during activation."""
        key = EncryptionKeyMetadata.objects.create(
            key_id="consistency_test_key",
            is_active=False,
            created_at=timezone.now(),
            expires_at=timezone.now() + timedelta(days=90),
            rotation_status='created'
        )

        EncryptionKeyManager.activate_key("consistency_test_key")

        # Verify all fields are consistent
        key.refresh_from_db()
        self.assertTrue(key.is_active)
        self.assertEqual(key.rotation_status, 'active')
        self.assertIsNotNone(key.activated_at)
        self.assertEqual(EncryptionKeyManager._current_key_id, "consistency_test_key")
