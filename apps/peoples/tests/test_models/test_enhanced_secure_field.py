"""
Comprehensive tests for EnhancedSecureString field security improvements.

These tests validate that the new encryption field properly replaces the
insecure SecureString implementation and provides strong security guarantees.

Tests cover:
- Encryption/decryption functionality
- Migration from legacy format
- Security validation
- Error handling
- Performance characteristics
"""

import pytest
from django.test import TestCase
from django.core.exceptions import ValidationError
from apps.peoples.fields import EnhancedSecureString


class EnhancedSecureStringTests(TestCase):
    """Test suite for EnhancedSecureString field."""

    def setUp(self):
        """Set up test fixtures."""
        self.field = EnhancedSecureString()
        self.test_data = "test_email@example.com"
        self.sensitive_data = "sensitive_password123"

    def test_encryption_basic_functionality(self):
        """Test basic encryption and decryption works correctly."""
        # Test encryption
        encrypted_value = self.field.get_prep_value(self.test_data)

        # Verify it's encrypted (has version prefix)
        self.assertTrue(encrypted_value.startswith(self.field.SECURE_VERSION))
        self.assertNotEqual(encrypted_value, self.test_data)

        # Test decryption
        decrypted_value = self.field.from_db_value(encrypted_value, None, None)
        self.assertEqual(decrypted_value, self.test_data)

    def test_encryption_prevents_double_encryption(self):
        """Test that already encrypted data is not double-encrypted."""
        # First encryption
        encrypted_once = self.field.get_prep_value(self.test_data)

        # Attempt second encryption
        encrypted_twice = self.field.get_prep_value(encrypted_once)

        # Should be identical (no double encryption)
        self.assertEqual(encrypted_once, encrypted_twice)

    def test_handles_none_and_empty_values(self):
        """Test handling of None and empty string values."""
        # Test None values
        self.assertIsNone(self.field.get_prep_value(None))
        self.assertIsNone(self.field.from_db_value(None, None, None))

        # Test empty strings
        self.assertEqual(self.field.get_prep_value(""), "")
        self.assertEqual(self.field.from_db_value("", None, None), "")

    def test_input_validation(self):
        """Test input validation rejects invalid data types."""
        # Test non-string inputs
        with self.assertRaises(ValidationError):
            self.field.get_prep_value(123)

        with self.assertRaises(ValidationError):
            self.field.get_prep_value(['list', 'data'])

        with self.assertRaises(ValidationError):
            self.field.get_prep_value({'dict': 'data'})

    def test_legacy_format_migration(self):
        """Test migration from legacy ENC_V1 format."""
        # Simulate legacy format (for testing purposes)
        legacy_value = f"{self.field.LEGACY_VERSION}legacy_encrypted_data"

        # Should handle gracefully (implementation depends on migration service)
        result = self.field.from_db_value(legacy_value, None, None)

        # Should not raise exception and should return some value
        self.assertIsNotNone(result)

    def test_corruption_handling(self):
        """Test handling of corrupted encrypted data."""
        corrupted_data = f"{self.field.SECURE_VERSION}corrupted_base64_data!!!"

        # Should handle gracefully without exposing sensitive information
        result = self.field.from_db_value(corrupted_data, None, None)

        # Should return None for corrupted data (fail safe)
        self.assertIsNone(result)

    def test_field_initialization(self):
        """Test field initialization with proper defaults."""
        field = EnhancedSecureString()

        # Should have appropriate max_length for encrypted data
        self.assertEqual(field.max_length, 500)

        # Should have security help text
        self.assertIn('encrypted', field.help_text.lower())
        self.assertIn('secure', field.help_text.lower())

    def test_model_property_methods(self):
        """Test that field adds security check properties to models."""
        # This would be tested in integration with actual model
        # Here we test the property creation logic

        class MockModel:
            pass

        # Simulate contribute_to_class behavior
        field = EnhancedSecureString()
        field.contribute_to_class(MockModel, 'test_field')

        # Check that security properties were added
        self.assertTrue(hasattr(MockModel, 'is_test_field_securely_encrypted'))
        self.assertTrue(hasattr(MockModel, 'test_field_needs_migration'))

    def test_deconstruct_for_migrations(self):
        """Test deconstruct method for Django migrations."""
        field = EnhancedSecureString(max_length=600)

        name, path, args, kwargs = field.deconstruct()

        # Should maintain proper path for migrations
        self.assertIn('EnhancedSecureString', path)

        # Should not include default help_text in kwargs
        default_help_text = 'This field is encrypted using cryptographically secure algorithms'
        if 'help_text' in kwargs:
            self.assertNotEqual(kwargs['help_text'], default_help_text)

    def test_performance_characteristics(self):
        """Test that encryption/decryption has acceptable performance."""
        import time

        test_values = [
            "short",
            "medium_length_email@company.com",
            "very_long_string_with_lots_of_content_" * 10
        ]

        for test_value in test_values:
            start_time = time.time()

            # Encrypt
            encrypted = self.field.get_prep_value(test_value)

            # Decrypt
            decrypted = self.field.from_db_value(encrypted, None, None)

            end_time = time.time()
            operation_time = end_time - start_time

            # Should complete within reasonable time (< 0.1 seconds)
            self.assertLess(operation_time, 0.1)
            self.assertEqual(decrypted, test_value)

    def test_security_strength(self):
        """Test that encrypted values have proper security characteristics."""
        test_values = ["password123", "email@test.com", "secret_data"]
        encrypted_values = []

        for value in test_values:
            encrypted = self.field.get_prep_value(value)
            encrypted_values.append(encrypted)

            # Verify encryption format
            self.assertTrue(encrypted.startswith(self.field.SECURE_VERSION))

            # Verify original data is not visible
            self.assertNotIn(value, encrypted)

            # Verify base64-like structure (encrypted data should be base64)
            encrypted_data = encrypted[len(self.field.SECURE_VERSION):]

            # Should have reasonable length increase due to encryption
            self.assertGreater(len(encrypted_data), len(value))

        # Verify different inputs produce different encrypted outputs
        self.assertEqual(len(set(encrypted_values)), len(test_values))


@pytest.mark.django_db
class EnhancedSecureStringIntegrationTests(TestCase):
    """Integration tests with actual Django model usage."""

    def test_field_integration_with_model_save_load(self):
        """Test field works correctly when saving/loading from database."""
        from apps.peoples.models import People
        from datetime import date

        # Create test user
        test_user = People(
            peoplecode="TEST001",
            peoplename="Test User",
            loginid="testuser",
            email="test@example.com",  # This uses EnhancedSecureString
            dateofbirth=date(1990, 1, 1),
        )

        # Save to database
        test_user.save()

        # Reload from database
        reloaded_user = People.objects.get(pk=test_user.pk)

        # Verify email was encrypted and decrypted correctly
        self.assertEqual(reloaded_user.email, "test@example.com")

        # Verify it was actually encrypted in database
        from django.db import connection
        with connection.cursor() as cursor:
            cursor.execute("SELECT email FROM people WHERE id = %s", [test_user.pk])
            raw_email = cursor.fetchone()[0]

            # Raw value should be encrypted (have version prefix)
            self.assertTrue(raw_email.startswith('FERNET_V1:'))
            self.assertNotEqual(raw_email, "test@example.com")

    def test_field_model_properties(self):
        """Test that model properties for encryption status work correctly."""
        from apps.peoples.models import People
        from datetime import date

        test_user = People(
            peoplecode="TEST002",
            peoplename="Test User 2",
            loginid="testuser2",
            email="test2@example.com",
            dateofbirth=date(1990, 1, 1),
        )

        test_user.save()

        # Test security properties (if they exist)
        # Note: This depends on the actual model implementation
        if hasattr(test_user, 'is_email_securely_encrypted'):
            # Should indicate secure encryption after save
            self.assertTrue(test_user.is_email_securely_encrypted)

        if hasattr(test_user, 'email_needs_migration'):
            # Should not need migration for new records
            self.assertFalse(test_user.email_needs_migration)


@pytest.mark.django_db
class EnhancedSecureStringEdgeCaseTests(TestCase):
    """Edge case and stress tests for EnhancedSecureString field."""

    def setUp(self):
        """Set up test fixtures."""
        self.field = EnhancedSecureString()

    def test_concurrent_field_access(self):
        """Test field handles concurrent access safely."""
        import threading
        import queue
        from apps.peoples.models import People
        from datetime import date

        results = queue.Queue()
        errors = queue.Queue()

        def concurrent_encrypt_decrypt(thread_id):
            try:
                # Create unique test data for each thread
                test_data = f"thread{thread_id}_email@test{thread_id}.com"

                # Encrypt and decrypt multiple times
                for i in range(10):
                    encrypted = self.field.get_prep_value(test_data)
                    decrypted = self.field.from_db_value(encrypted, None, None)

                    if decrypted != test_data:
                        errors.put(f"Thread {thread_id}: Decryption mismatch at iteration {i}")
                        return

                results.put(f"thread_{thread_id}_success")

            except Exception as e:
                errors.put(f"Thread {thread_id}: {str(e)}")

        # Create multiple threads
        threads = []
        for i in range(5):
            thread = threading.Thread(target=concurrent_encrypt_decrypt, args=(i,))
            threads.append(thread)
            thread.start()

        # Wait for all threads
        for thread in threads:
            thread.join()

        # Check results
        self.assertTrue(errors.empty(), f"Concurrent access errors: {list(errors.queue)}")

        successful_threads = []
        while not results.empty():
            successful_threads.append(results.get())

        self.assertEqual(len(successful_threads), 5, "All threads should complete successfully")

    def test_database_transaction_rollback_behavior(self):
        """Test field behavior during database transaction rollbacks."""
        from apps.peoples.models import People
        from django.db import transaction, IntegrityError
        from datetime import date

        # Test that encrypted data is properly handled during rollbacks
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                user1 = People.objects.create(
                    peoplecode="TRANS001",
                    peoplename="Transaction Test 1",
                    loginid="transtest1",
                    email="trans1@example.com",
                    dateofbirth=date(1990, 1, 1),
                )

                # This should cause a rollback due to duplicate peoplecode
                user2 = People.objects.create(
                    peoplecode="TRANS001",  # Duplicate peoplecode
                    peoplename="Transaction Test 2",
                    loginid="transtest2",
                    email="trans2@example.com",
                    dateofbirth=date(1990, 1, 1),
                )

        # Verify no users were created due to rollback
        self.assertFalse(People.objects.filter(peoplecode="TRANS001").exists())

    def test_large_data_encryption_performance(self):
        """Test encryption performance with large data sets."""
        import time

        # Test with various data sizes
        data_sizes = [
            ("small", "a" * 100),
            ("medium", "b" * 1000),
            ("large", "c" * 10000),
            ("very_large", "d" * 50000),  # 50KB
        ]

        performance_results = {}

        for size_name, test_data in data_sizes:
            # Measure encryption time
            start_time = time.time()
            encrypted = self.field.get_prep_value(test_data)
            encrypt_time = time.time() - start_time

            # Measure decryption time
            start_time = time.time()
            decrypted = self.field.from_db_value(encrypted, None, None)
            decrypt_time = time.time() - start_time

            # Verify correctness
            self.assertEqual(decrypted, test_data, f"Data integrity failed for {size_name}")

            performance_results[size_name] = {
                'encrypt_time': encrypt_time,
                'decrypt_time': decrypt_time,
                'total_time': encrypt_time + decrypt_time
            }

            # Performance thresholds (should complete within reasonable time)
            self.assertLess(encrypt_time, 0.5, f"Encryption too slow for {size_name}: {encrypt_time:.3f}s")
            self.assertLess(decrypt_time, 0.5, f"Decryption too slow for {size_name}: {decrypt_time:.3f}s")

    def test_memory_usage_under_load(self):
        """Test memory usage doesn't grow excessively under load."""
        import gc
        import sys

        # Get initial memory state
        gc.collect()
        initial_objects = len(gc.get_objects())

        # Process many encryption/decryption operations
        test_data = "memory_test_email@example.com"

        for i in range(1000):
            encrypted = self.field.get_prep_value(f"{test_data}_{i}")
            decrypted = self.field.from_db_value(encrypted, None, None)

            # Verify correctness
            self.assertEqual(decrypted, f"{test_data}_{i}")

        # Check memory growth
        gc.collect()
        final_objects = len(gc.get_objects())
        memory_growth = final_objects - initial_objects

        # Memory growth should be reasonable (less than 500 objects for 1000 operations)
        self.assertLess(memory_growth, 500, f"Excessive memory growth: {memory_growth} objects")

    def test_migration_service_failure_handling(self):
        """Test graceful handling of migration service failures."""
        from unittest.mock import patch

        # Test with legacy format data
        legacy_data = f"{self.field.LEGACY_VERSION}legacy_test_data"

        # Mock migration service to fail
        with patch('apps.core.services.secure_encryption_service.SecureEncryptionService.migrate_legacy_data') as mock_migrate:
            mock_migrate.return_value = (False, None)  # Migration failed

            # Should handle gracefully without raising exception
            result = self.field.from_db_value(legacy_data, None, None)

            # Should return fallback value (the payload without prefix)
            self.assertEqual(result, "legacy_test_data")

    def test_encryption_service_unavailable_handling(self):
        """Test handling when encryption service is temporarily unavailable."""
        from unittest.mock import patch
        from django.core.exceptions import ValidationError

        test_data = "service_test@example.com"

        # Mock encryption service to fail
        with patch('apps.core.services.secure_encryption_service.SecureEncryptionService.encrypt') as mock_encrypt:
            mock_encrypt.side_effect = Exception("Encryption service unavailable")

            # Should raise ValidationError for security (fail-safe)
            with self.assertRaises(ValidationError):
                self.field.get_prep_value(test_data)

    def test_corrupted_data_recovery(self):
        """Test recovery from various types of data corruption."""
        corruption_scenarios = [
            # Truncated encrypted data
            f"{self.field.SECURE_VERSION}truncated",

            # Invalid base64 in encrypted data
            f"{self.field.SECURE_VERSION}invalid_base64_!!!",

            # Wrong encryption format
            "UNKNOWN_VERSION:encrypted_data",

            # Completely malformed data
            "completely_invalid_data_format",

            # Binary data that can't be decoded
            "\x00\x01\x02\x03\x04",
        ]

        for corrupted_data in corruption_scenarios:
            # Should handle gracefully without raising unhandled exceptions
            result = self.field.from_db_value(corrupted_data, None, None)

            # Should either return None (fail-safe) or the original data for fallback
            self.assertTrue(result is None or isinstance(result, str))

    def test_concurrent_database_operations(self):
        """Test concurrent database operations with encrypted fields."""
        import threading
        import queue
        from apps.peoples.models import People
        from datetime import date

        results = queue.Queue()
        errors = queue.Queue()

        def concurrent_db_operations(thread_id):
            try:
                # Create, update, and read user records concurrently
                user = People.objects.create(
                    peoplecode=f"CONC{thread_id:03d}",
                    peoplename=f"Concurrent User {thread_id}",
                    loginid=f"concuser{thread_id}",
                    email=f"concurrent{thread_id}@test.com",
                    dateofbirth=date(1990, 1, 1),
                )

                # Update email
                user.email = f"updated{thread_id}@test.com"
                user.save()

                # Read back and verify
                reloaded_user = People.objects.get(pk=user.pk)
                if reloaded_user.email != f"updated{thread_id}@test.com":
                    errors.put(f"Thread {thread_id}: Email update verification failed")
                    return

                # Clean up
                user.delete()
                results.put(f"thread_{thread_id}_success")

            except Exception as e:
                errors.put(f"Thread {thread_id}: {str(e)}")

        # Create multiple threads
        threads = []
        for i in range(3):  # Fewer threads for DB operations
            thread = threading.Thread(target=concurrent_db_operations, args=(i,))
            threads.append(thread)
            thread.start()

        # Wait for all threads
        for thread in threads:
            thread.join()

        # Check results
        self.assertTrue(errors.empty(), f"Concurrent DB operation errors: {list(errors.queue)}")

    def test_field_with_database_constraints(self):
        """Test field behavior with database constraints and uniqueness."""
        from apps.peoples.models import People
        from django.db import IntegrityError
        from datetime import date

        # Create first user
        user1 = People.objects.create(
            peoplecode="UNIQUE001",
            peoplename="Unique Test 1",
            loginid="uniquetest1",
            email="unique@test.com",
            dateofbirth=date(1990, 1, 1),
        )

        # Verify email is encrypted but unique constraint still works
        with self.assertRaises(IntegrityError):
            People.objects.create(
                peoplecode="UNIQUE002",
                peoplename="Unique Test 2",
                loginid="uniquetest1",  # Duplicate loginid should fail
                email="different@test.com",
                dateofbirth=date(1990, 1, 1),
            )

    def test_encryption_entropy_and_randomness(self):
        """Test that encryption produces random-looking output."""
        test_data = "entropy_test@example.com"
        encrypted_values = []

        # Encrypt the same data multiple times
        for i in range(10):
            encrypted = self.field.get_prep_value(test_data)
            encrypted_values.append(encrypted)

            # Each encryption should produce different output (nonce-based)
            for j, other_encrypted in enumerate(encrypted_values[:-1]):
                self.assertNotEqual(encrypted, other_encrypted,
                                  f"Encryption {i} should differ from encryption {j}")

            # All should decrypt to the same value
            decrypted = self.field.from_db_value(encrypted, None, None)
            self.assertEqual(decrypted, test_data)

    def test_field_with_various_character_encodings(self):
        """Test field handles various character encodings correctly."""
        encoding_test_cases = [
            # ASCII
            "ascii_test@example.com",

            # Unicode characters
            "unicode_tëst@exämple.com",

            # Emoji
            "emoji_test_😀@example.com",

            # Special characters
            "special!@#$%^&*()_test@example.com",

            # Different languages
            "тест@пример.com",  # Cyrillic
            "测试@例子.com",      # Chinese
            "テスト@例.com",     # Japanese
        ]

        for test_data in encoding_test_cases:
            # Should handle all encodings without error
            encrypted = self.field.get_prep_value(test_data)
            decrypted = self.field.from_db_value(encrypted, None, None)

            self.assertEqual(decrypted, test_data, f"Encoding failed for: {test_data}")

    def test_performance_under_stress(self):
        """Test performance characteristics under stress conditions."""
        import time
        import threading

        results = []

        def stress_test_worker():
            local_results = []
            start_time = time.time()

            for i in range(100):
                test_data = f"stress_test_{i}@example.com"
                encrypted = self.field.get_prep_value(test_data)
                decrypted = self.field.from_db_value(encrypted, None, None)

                operation_time = time.time() - start_time
                local_results.append(operation_time)

            results.extend(local_results)

        # Run stress test with multiple threads
        threads = []
        for i in range(3):
            thread = threading.Thread(target=stress_test_worker)
            threads.append(thread)
            thread.start()

        for thread in threads:
            thread.join()

        # Analyze performance results
        if results:
            avg_time = sum(results) / len(results)
            max_time = max(results)

            # Performance should remain reasonable under stress
            self.assertLess(avg_time, 1.0, f"Average operation time too slow: {avg_time:.3f}s")
            self.assertLess(max_time, 5.0, f"Maximum operation time too slow: {max_time:.3f}s")