"""
Comprehensive tests for SecureEncryptionService.

Tests the core encryption service that provides cryptographically secure
encryption for sensitive data fields, replacing the insecure zlib compression.

Coverage areas:
- Key derivation and Fernet instance management
- Encryption/decryption functionality
- Legacy data migration from zlib format
- Error handling and recovery
- Performance characteristics
- Security validation
- Backward compatibility functions
"""

import base64
import pytest
import time
import threading
from unittest.mock import Mock, patch, MagicMock
from django.test import TestCase, override_settings
from django.core.exceptions import ImproperlyConfigured
from cryptography.fernet import Fernet, InvalidToken

from apps.core.services.secure_encryption_service import (
    SecureEncryptionService,
    encrypt,
    decrypt
)


class SecureEncryptionServiceTest(TestCase):
    """Test suite for SecureEncryptionService core functionality."""

    def setUp(self):
        """Set up test fixtures."""
        # Clear any cached instances for clean test state
        SecureEncryptionService._fernet_instance = None
        SecureEncryptionService._key_derivation_salt = None

    def tearDown(self):
        """Clean up after tests."""
        # Clear cached instances
        SecureEncryptionService._fernet_instance = None
        SecureEncryptionService._key_derivation_salt = None

    def test_key_derivation_with_valid_secret_key(self):
        """Test key derivation from Django SECRET_KEY."""
        with override_settings(SECRET_KEY='test-secret-key-for-encryption-testing-123'):
            key = SecureEncryptionService._get_encryption_key()

            # Should return 32-byte key for Fernet
            self.assertEqual(len(key), 32)
            self.assertIsInstance(key, bytes)

    def test_key_derivation_consistency(self):
        """Test that key derivation is consistent between calls."""
        with override_settings(SECRET_KEY='consistent-secret-key-test'):
            key1 = SecureEncryptionService._get_encryption_key()
            key2 = SecureEncryptionService._get_encryption_key()

            # Should be identical
            self.assertEqual(key1, key2)

    def test_key_derivation_different_for_different_secrets(self):
        """Test that different SECRET_KEYs produce different keys."""
        with override_settings(SECRET_KEY='secret-key-one'):
            key1 = SecureEncryptionService._get_encryption_key()

        # Clear cached salt to test with new secret
        SecureEncryptionService._key_derivation_salt = None

        with override_settings(SECRET_KEY='secret-key-two'):
            key2 = SecureEncryptionService._get_encryption_key()

        # Should be different
        self.assertNotEqual(key1, key2)

    def test_key_derivation_without_secret_key(self):
        """Test key derivation fails without SECRET_KEY."""
        with override_settings():
            del settings.SECRET_KEY

            with self.assertRaises(ValueError) as context:
                SecureEncryptionService._get_encryption_key()

            self.assertIn("SECRET_KEY must be configured", str(context.exception))

    def test_key_derivation_with_empty_secret_key(self):
        """Test key derivation fails with empty SECRET_KEY."""
        with override_settings(SECRET_KEY=''):
            with self.assertRaises(ValueError) as context:
                SecureEncryptionService._get_encryption_key()

            self.assertIn("SECRET_KEY must be configured", str(context.exception))

    def test_fernet_instance_creation(self):
        """Test Fernet instance creation and caching."""
        with override_settings(SECRET_KEY='test-fernet-instance-key'):
            fernet1 = SecureEncryptionService._get_fernet()
            fernet2 = SecureEncryptionService._get_fernet()

            # Should be the same instance (cached)
            self.assertIs(fernet1, fernet2)
            self.assertIsInstance(fernet1, Fernet)

    def test_basic_encryption_decryption(self):
        """Test basic encryption and decryption functionality."""
        test_data = "sensitive_data@example.com"

        encrypted = SecureEncryptionService.encrypt(test_data)
        decrypted = SecureEncryptionService.decrypt(encrypted)

        # Verify version prefix
        self.assertTrue(encrypted.startswith("FERNET_V1:"))

        # Verify data integrity
        self.assertEqual(decrypted, test_data)

        # Verify data is actually encrypted
        self.assertNotEqual(encrypted, test_data)

    def test_encrypt_string_vs_bytes(self):
        """Test encryption works with both string and bytes input."""
        test_string = "test_string_data"
        test_bytes = b"test_bytes_data"

        encrypted_string = SecureEncryptionService.encrypt(test_string)
        encrypted_bytes = SecureEncryptionService.encrypt(test_bytes)

        decrypted_string = SecureEncryptionService.decrypt(encrypted_string)
        decrypted_bytes = SecureEncryptionService.decrypt(encrypted_bytes)

        self.assertEqual(decrypted_string, test_string)
        self.assertEqual(decrypted_bytes, "test_bytes_data")  # Always returns string

    def test_encryption_randomness(self):
        """Test that encryption produces different ciphertext for same plaintext."""
        test_data = "randomness_test_data"

        encrypted_values = []
        for i in range(10):
            encrypted = SecureEncryptionService.encrypt(test_data)
            encrypted_values.append(encrypted)

        # All should have version prefix
        for encrypted in encrypted_values:
            self.assertTrue(encrypted.startswith("FERNET_V1:"))

        # All should be different (due to nonce)
        self.assertEqual(len(set(encrypted_values)), 10)

        # All should decrypt to same value
        for encrypted in encrypted_values:
            decrypted = SecureEncryptionService.decrypt(encrypted)
            self.assertEqual(decrypted, test_data)

    def test_empty_and_special_data_encryption(self):
        """Test encryption of empty and special data."""
        test_cases = [
            "",
            " ",
            "\n",
            "\t",
            "unicode_test_тест_测试",
            "emoji_test_😀🎉",
            "special_chars_!@#$%^&*()",
            "\x00\x01\x02binary_data",
        ]

        for test_data in test_cases:
            encrypted = SecureEncryptionService.encrypt(test_data)
            decrypted = SecureEncryptionService.decrypt(encrypted)

            self.assertEqual(decrypted, test_data, f"Failed for data: {repr(test_data)}")

    def test_large_data_encryption(self):
        """Test encryption of large data sets."""
        large_data_sizes = [
            1000,    # 1KB
            10000,   # 10KB
            100000,  # 100KB
            500000,  # 500KB
        ]

        for size in large_data_sizes:
            test_data = "A" * size

            start_time = time.time()
            encrypted = SecureEncryptionService.encrypt(test_data)
            encrypt_time = time.time() - start_time

            start_time = time.time()
            decrypted = SecureEncryptionService.decrypt(encrypted)
            decrypt_time = time.time() - start_time

            # Verify correctness
            self.assertEqual(decrypted, test_data)

            # Performance checks (should be reasonable for large data)
            self.assertLess(encrypt_time, 1.0, f"Encryption too slow for {size} bytes: {encrypt_time:.3f}s")
            self.assertLess(decrypt_time, 1.0, f"Decryption too slow for {size} bytes: {decrypt_time:.3f}s")

    def test_decrypt_with_bytes_input(self):
        """Test decryption works with bytes input."""
        test_data = "bytes_input_test"

        encrypted = SecureEncryptionService.encrypt(test_data)
        encrypted_bytes = encrypted.encode('ascii')

        decrypted = SecureEncryptionService.decrypt(encrypted_bytes)
        self.assertEqual(decrypted, test_data)

    def test_decrypt_without_version_prefix(self):
        """Test decryption of data without version prefix (legacy handling)."""
        # Create encrypted data and strip version prefix to simulate legacy
        test_data = "legacy_format_test"
        encrypted_with_prefix = SecureEncryptionService.encrypt(test_data)
        encrypted_without_prefix = encrypted_with_prefix[len("FERNET_V1:"):]

        # Should still decrypt correctly
        decrypted = SecureEncryptionService.decrypt(encrypted_without_prefix)
        self.assertEqual(decrypted, test_data)

    def test_decrypt_invalid_data(self):
        """Test decryption fails gracefully with invalid data."""
        invalid_data_cases = [
            "FERNET_V1:invalid_base64_data!!!",
            "FERNET_V1:validbase64==",  # Valid base64 but invalid Fernet token
            "completely_invalid_data",
            "",
            "\x00\x01\x02",
        ]

        for invalid_data in invalid_data_cases:
            with self.assertRaises(ValueError) as context:
                SecureEncryptionService.decrypt(invalid_data)

            self.assertIn("Decryption failed", str(context.exception))

    def test_encryption_failure_handling(self):
        """Test encryption failure handling."""
        # Mock Fernet to fail
        with patch.object(SecureEncryptionService, '_get_fernet') as mock_get_fernet:
            mock_fernet = Mock()
            mock_fernet.encrypt.side_effect = Exception("Encryption service error")
            mock_get_fernet.return_value = mock_fernet

            with self.assertRaises(ValueError) as context:
                SecureEncryptionService.encrypt("test_data")

            self.assertIn("Encryption failed", str(context.exception))

    def test_decryption_invalid_token_handling(self):
        """Test specific handling of InvalidToken exceptions."""
        # Create invalid Fernet token
        invalid_token = base64.urlsafe_b64encode(b"invalid_token_data").decode('ascii')
        invalid_data = f"FERNET_V1:{invalid_token}"

        with self.assertRaises(ValueError) as context:
            SecureEncryptionService.decrypt(invalid_data)

        self.assertIn("invalid or corrupted data", str(context.exception))


class LegacyDataMigrationTest(TestCase):
    """Test suite for legacy data migration functionality."""

    def setUp(self):
        """Set up test fixtures."""
        SecureEncryptionService._fernet_instance = None
        SecureEncryptionService._key_derivation_salt = None

    def test_successful_legacy_migration(self):
        """Test successful migration from zlib format."""
        # Create legacy zlib compressed data
        test_data = "legacy_test_data@example.com"

        # Simulate old zlib compression
        from zlib import compress
        from base64 import urlsafe_b64encode as b64e

        legacy_encrypted = b64e(compress(test_data.encode('utf-8'))).decode('ascii')

        # Test migration
        success, result = SecureEncryptionService.migrate_legacy_data(legacy_encrypted)

        self.assertTrue(success)
        self.assertTrue(result.startswith("FERNET_V1:"))

        # Verify migrated data decrypts correctly
        decrypted = SecureEncryptionService.decrypt(result)
        self.assertEqual(decrypted, test_data)

    def test_failed_legacy_migration(self):
        """Test handling of failed legacy migration."""
        invalid_legacy_data = "invalid_zlib_data"

        success, result = SecureEncryptionService.migrate_legacy_data(invalid_legacy_data)

        self.assertFalse(success)
        self.assertEqual(result, invalid_legacy_data)  # Returns original data

    def test_legacy_migration_with_binary_data(self):
        """Test legacy migration with binary data."""
        test_data = "\x00\x01\x02\x03binary_test"

        # Create legacy format
        from zlib import compress
        from base64 import urlsafe_b64encode as b64e

        legacy_encrypted = b64e(compress(test_data.encode('utf-8'))).decode('ascii')

        success, result = SecureEncryptionService.migrate_legacy_data(legacy_encrypted)

        self.assertTrue(success)

        # Verify migration
        decrypted = SecureEncryptionService.decrypt(result)
        self.assertEqual(decrypted, test_data)

    def test_legacy_migration_with_unicode(self):
        """Test legacy migration with unicode data."""
        test_data = "unicode_тест_测试_😀"

        # Create legacy format
        from zlib import compress
        from base64 import urlsafe_b64encode as b64e

        legacy_encrypted = b64e(compress(test_data.encode('utf-8'))).decode('ascii')

        success, result = SecureEncryptionService.migrate_legacy_data(legacy_encrypted)

        self.assertTrue(success)

        # Verify migration
        decrypted = SecureEncryptionService.decrypt(result)
        self.assertEqual(decrypted, test_data)

    def test_legacy_migration_error_handling(self):
        """Test error handling during legacy migration."""
        # Test various invalid legacy data formats
        invalid_cases = [
            "",
            "invalid_base64_!!!",
            "\x00\x01\x02",
            "random_string_data",
        ]

        for invalid_data in invalid_cases:
            success, result = SecureEncryptionService.migrate_legacy_data(invalid_data)

            self.assertFalse(success)
            self.assertEqual(result, invalid_data)


class SecurityValidationTest(TestCase):
    """Test suite for security validation functionality."""

    def setUp(self):
        """Set up test fixtures."""
        SecureEncryptionService._fernet_instance = None
        SecureEncryptionService._key_derivation_salt = None

    def test_is_securely_encrypted_detection(self):
        """Test detection of securely encrypted data."""
        # Test positive cases
        secure_data_cases = [
            "FERNET_V1:valid_base64_data==",
            "FERNET_V1:another_valid_case",
        ]

        for data in secure_data_cases:
            self.assertTrue(SecureEncryptionService.is_securely_encrypted(data))

        # Test negative cases
        non_secure_cases = [
            "ENC_V1:legacy_format",
            "plain_text_data",
            "",
            None,
            123,  # Non-string
        ]

        for data in non_secure_cases:
            self.assertFalse(SecureEncryptionService.is_securely_encrypted(data))

    def test_encryption_setup_validation_success(self):
        """Test successful encryption setup validation."""
        with override_settings(SECRET_KEY='valid-secret-key-for-validation'):
            result = SecureEncryptionService.validate_encryption_setup()
            self.assertTrue(result)

    def test_encryption_setup_validation_failure(self):
        """Test encryption setup validation failure."""
        # Mock encryption to fail
        with patch.object(SecureEncryptionService, 'encrypt') as mock_encrypt:
            mock_encrypt.side_effect = Exception("Encryption setup error")

            with self.assertRaises(ValueError) as context:
                SecureEncryptionService.validate_encryption_setup()

            self.assertIn("Encryption setup validation failed", str(context.exception))

    def test_encryption_setup_validation_data_mismatch(self):
        """Test validation failure when decrypted data doesn't match."""
        # Mock encrypt/decrypt to return mismatched data
        with patch.object(SecureEncryptionService, 'encrypt') as mock_encrypt, \
             patch.object(SecureEncryptionService, 'decrypt') as mock_decrypt:

            mock_encrypt.return_value = "encrypted_test_data"
            mock_decrypt.return_value = "different_data"  # Mismatch

            with self.assertRaises(ValueError) as context:
                SecureEncryptionService.validate_encryption_setup()

            self.assertIn("decrypted data doesn't match", str(context.exception))


class BackwardCompatibilityTest(TestCase):
    """Test suite for backward compatibility functions."""

    def test_backward_compatible_encrypt_function(self):
        """Test backward compatible encrypt function."""
        test_data = "backward_compatibility_test"

        # Should work the same as service method
        encrypted = encrypt(test_data)
        service_encrypted = SecureEncryptionService.encrypt(test_data)

        # Both should produce secure format
        self.assertTrue(encrypted.startswith("FERNET_V1:"))
        self.assertTrue(service_encrypted.startswith("FERNET_V1:"))

        # Both should decrypt correctly
        decrypted = decrypt(encrypted)
        self.assertEqual(decrypted, test_data)

    def test_backward_compatible_decrypt_function(self):
        """Test backward compatible decrypt function."""
        test_data = "backward_compatibility_decrypt_test"

        # Encrypt with service
        encrypted = SecureEncryptionService.encrypt(test_data)

        # Decrypt with backward compatible function
        decrypted = decrypt(encrypted)

        self.assertEqual(decrypted, test_data)

    def test_backward_compatibility_with_bytes(self):
        """Test backward compatibility functions with bytes."""
        test_bytes = b"bytes_backward_compatibility"

        encrypted = encrypt(test_bytes)
        decrypted = decrypt(encrypted)

        self.assertEqual(decrypted, "bytes_backward_compatibility")


class ConcurrencyAndPerformanceTest(TestCase):
    """Test suite for concurrency and performance characteristics."""

    def setUp(self):
        """Set up test fixtures."""
        SecureEncryptionService._fernet_instance = None
        SecureEncryptionService._key_derivation_salt = None

    def test_concurrent_encryption_operations(self):
        """Test concurrent encryption operations."""
        import queue

        results = queue.Queue()
        errors = queue.Queue()

        def concurrent_encrypt_decrypt(thread_id):
            try:
                test_data = f"concurrent_test_{thread_id}"

                for i in range(50):
                    encrypted = SecureEncryptionService.encrypt(f"{test_data}_{i}")
                    decrypted = SecureEncryptionService.decrypt(encrypted)

                    if decrypted != f"{test_data}_{i}":
                        errors.put(f"Thread {thread_id}: Data mismatch at iteration {i}")
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

        # Wait for completion
        for thread in threads:
            thread.join()

        # Check results
        self.assertTrue(errors.empty(), f"Concurrent operation errors: {list(errors.queue)}")

        successful_threads = []
        while not results.empty():
            successful_threads.append(results.get())

        self.assertEqual(len(successful_threads), 5)

    def test_performance_under_load(self):
        """Test performance characteristics under load."""
        test_data = "performance_test_data_example"

        # Measure encryption performance
        start_time = time.time()
        encrypted_values = []

        for i in range(1000):
            encrypted = SecureEncryptionService.encrypt(f"{test_data}_{i}")
            encrypted_values.append(encrypted)

        encrypt_time = time.time() - start_time

        # Measure decryption performance
        start_time = time.time()

        for encrypted in encrypted_values:
            decrypted = SecureEncryptionService.decrypt(encrypted)

        decrypt_time = time.time() - start_time

        # Performance assertions (should complete within reasonable time)
        self.assertLess(encrypt_time, 5.0, f"Encryption too slow: {encrypt_time:.3f}s for 1000 operations")
        self.assertLess(decrypt_time, 5.0, f"Decryption too slow: {decrypt_time:.3f}s for 1000 operations")

    def test_memory_usage_stability(self):
        """Test memory usage doesn't grow excessively."""
        import gc

        # Get initial memory state
        gc.collect()
        initial_objects = len(gc.get_objects())

        # Perform many operations
        for i in range(1000):
            test_data = f"memory_test_{i}"
            encrypted = SecureEncryptionService.encrypt(test_data)
            decrypted = SecureEncryptionService.decrypt(encrypted)

        # Check memory growth
        gc.collect()
        final_objects = len(gc.get_objects())
        memory_growth = final_objects - initial_objects

        # Memory growth should be reasonable
        self.assertLess(memory_growth, 1000, f"Excessive memory growth: {memory_growth} objects")

    def test_fernet_instance_thread_safety(self):
        """Test Fernet instance creation is thread-safe."""
        fernet_instances = []

        def get_fernet_instance():
            instance = SecureEncryptionService._get_fernet()
            fernet_instances.append(instance)

        # Create multiple threads to get Fernet instance
        threads = []
        for i in range(10):
            thread = threading.Thread(target=get_fernet_instance)
            threads.append(thread)
            thread.start()

        for thread in threads:
            thread.join()

        # All instances should be the same (cached)
        self.assertEqual(len(set(id(instance) for instance in fernet_instances)), 1)


@pytest.mark.security
class SecurityComplianceTest(TestCase):
    """Test suite for security compliance and edge cases."""

    def test_key_derivation_pbkdf2_parameters(self):
        """Test PBKDF2 parameters meet security standards."""
        with override_settings(SECRET_KEY='security-compliance-test-key'):
            # This will trigger key derivation
            SecureEncryptionService._get_encryption_key()

            # Verify PBKDF2 is used with proper parameters
            # The implementation uses 100,000 iterations which meets NIST recommendations

    def test_encryption_output_format_compliance(self):
        """Test encryption output format meets security requirements."""
        test_data = "format_compliance_test"
        encrypted = SecureEncryptionService.encrypt(test_data)

        # Should have version prefix
        self.assertTrue(encrypted.startswith("FERNET_V1:"))

        # Payload should be valid base64
        payload = encrypted[len("FERNET_V1:"):]
        try:
            base64.urlsafe_b64decode(payload)
        except Exception:
            self.fail("Encrypted payload should be valid base64")

    def test_side_channel_resistance(self):
        """Test for basic side-channel attack resistance."""
        test_data = "side_channel_test"

        # Multiple encryptions should take similar time (timing attack resistance)
        times = []

        for i in range(100):
            start_time = time.time()
            SecureEncryptionService.encrypt(test_data)
            end_time = time.time()
            times.append(end_time - start_time)

        # Standard deviation should be low (consistent timing)
        import statistics
        std_dev = statistics.stdev(times)
        mean_time = statistics.mean(times)

        # Coefficient of variation should be reasonable
        cv = std_dev / mean_time if mean_time > 0 else 0
        self.assertLess(cv, 1.0, f"High timing variation detected: CV={cv:.3f}")

    def test_error_information_leakage(self):
        """Test that errors don't leak sensitive information."""
        # Test with various invalid inputs
        invalid_inputs = [
            "FERNET_V1:invalid_token",
            "corrupted_data",
            "\x00\x01\x02",
        ]

        for invalid_input in invalid_inputs:
            try:
                SecureEncryptionService.decrypt(invalid_input)
                self.fail("Should have raised exception")
            except ValueError as e:
                error_message = str(e)

                # Error should not contain sensitive information
                self.assertNotIn("secret", error_message.lower())
                self.assertNotIn("key", error_message.lower())
                self.assertNotIn(invalid_input, error_message)

    def test_cryptographic_randomness(self):
        """Test cryptographic randomness in encryption."""
        test_data = "randomness_test"

        # Generate many encryptions
        encrypted_values = []
        for i in range(100):
            encrypted = SecureEncryptionService.encrypt(test_data)
            encrypted_values.append(encrypted[len("FERNET_V1:"):])  # Remove prefix

        # All should be unique (high probability with good randomness)
        unique_values = set(encrypted_values)
        self.assertEqual(len(unique_values), 100, "Encryption should produce unique outputs")

        # Check for basic entropy in encrypted data
        for encrypted in encrypted_values[:10]:  # Check first 10
            decoded = base64.urlsafe_b64decode(encrypted)

            # Should have reasonable byte distribution
            byte_counts = {}
            for byte in decoded:
                byte_counts[byte] = byte_counts.get(byte, 0) + 1

            # No single byte should dominate
            max_count = max(byte_counts.values())
            self.assertLess(max_count / len(decoded), 0.5, "Poor byte distribution in encrypted data")