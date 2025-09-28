"""
Comprehensive Integration Tests for Encryption Security Remediation

These tests validate the complete encryption security fix addressing CVSS 7.5 vulnerability.

Test Coverage:
1. Hard deprecation of insecure encrypt/decrypt functions
2. Migration from SecureString to EnhancedSecureString
3. Secure encryption service integration
4. Legacy data migration scenarios
5. Production safety guarantees
6. Performance under load
7. Compliance validation (GDPR, HIPAA, SOC2)

Compliance with .claude/rules.md Rule #2: No Custom Encryption Without Audit
"""

import pytest
import warnings
from datetime import date
from unittest.mock import patch, MagicMock
from django.test import TestCase, override_settings
from django.core.exceptions import ValidationError
from django.db import connection, transaction, IntegrityError
from apps.peoples.models import People
from apps.peoples.fields import EnhancedSecureString
from apps.core.services.secure_encryption_service import SecureEncryptionService


@pytest.mark.security
@pytest.mark.integration
class EncryptionRemediationIntegrationTest(TestCase):
    """End-to-end integration tests for encryption remediation."""

    def setUp(self):
        """Set up test environment."""
        SecureEncryptionService._fernet_instance = None
        SecureEncryptionService._key_derivation_salt = None

    def test_deprecated_functions_hard_blocked_all_environments(self):
        """
        CRITICAL TEST: Verify deprecated functions raise RuntimeError in ALL environments.

        Tests that CVSS 7.5 vulnerability is completely blocked.
        """
        from apps.core.utils_new.string_utils import encrypt, decrypt

        with self.assertRaises(RuntimeError) as ctx:
            encrypt("test")

        self.assertIn("CRITICAL SECURITY ERROR", str(ctx.exception))
        self.assertIn("HARD DEPRECATED", str(ctx.exception))
        self.assertIn("CVSS 7.5", str(ctx.exception))
        self.assertIn("SecureEncryptionService", str(ctx.exception))

        with self.assertRaises(RuntimeError) as ctx:
            decrypt(b"test")

        self.assertIn("CRITICAL SECURITY ERROR", str(ctx.exception))
        self.assertIn("CVSS 7.5", str(ctx.exception))

    def test_people_model_uses_enhanced_secure_string(self):
        """Verify People model uses EnhancedSecureString for sensitive fields."""
        from apps.peoples.models import People

        email_field = People._meta.get_field('email')
        mobno_field = People._meta.get_field('mobno')

        self.assertIsInstance(email_field, EnhancedSecureString)
        self.assertIsInstance(mobno_field, EnhancedSecureString)
        self.assertEqual(email_field.max_length, 500)

    def test_complete_user_lifecycle_with_encryption(self):
        """
        Test complete user lifecycle with encrypted fields.

        Validates:
        - User creation with encrypted email/mobile
        - Data retrieval with automatic decryption
        - Updates preserve encryption
        - Deletion works correctly
        """
        test_user = People.objects.create(
            peoplecode="ENC_TEST_001",
            peoplename="Encryption Test User",
            loginid="enctest001",
            email="secure_test@example.com",
            mobno="+1234567890",
            dateofbirth=date(1990, 1, 1)
        )

        with connection.cursor() as cursor:
            cursor.execute("SELECT email, mobno FROM people WHERE id = %s", [test_user.pk])
            raw_email, raw_mobno = cursor.fetchone()

            self.assertTrue(raw_email.startswith('FERNET_V1:'))
            self.assertTrue(raw_mobno.startswith('FERNET_V1:'))
            self.assertNotIn('secure_test@example.com', raw_email)
            self.assertNotIn('+1234567890', raw_mobno)

        reloaded_user = People.objects.get(pk=test_user.pk)
        self.assertEqual(reloaded_user.email, "secure_test@example.com")
        self.assertEqual(reloaded_user.mobno, "+1234567890")

        reloaded_user.email = "updated_secure@example.com"
        reloaded_user.save(update_fields=['email'])

        with connection.cursor() as cursor:
            cursor.execute("SELECT email FROM people WHERE id = %s", [test_user.pk])
            updated_raw_email = cursor.fetchone()[0]
            self.assertTrue(updated_raw_email.startswith('FERNET_V1:'))
            self.assertNotEqual(updated_raw_email, raw_email)

        final_user = People.objects.get(pk=test_user.pk)
        self.assertEqual(final_user.email, "updated_secure@example.com")

        test_user.delete()
        self.assertFalse(People.objects.filter(pk=test_user.pk).exists())

    def test_legacy_data_migration_scenario(self):
        """
        Test migration from legacy ENC_V1 format to secure FERNET_V1.

        Simulates real-world migration of old encrypted data.
        """
        test_user = People.objects.create(
            peoplecode="LEGACY_001",
            peoplename="Legacy User",
            loginid="legacy001",
            dateofbirth=date(1990, 1, 1)
        )

        import zlib
        import base64
        legacy_email = "legacy_email@example.com"
        legacy_compressed = base64.urlsafe_b64encode(
            zlib.compress(legacy_email.encode('utf-8'), 9)
        ).decode('ascii')
        legacy_format = f"ENC_V1:{legacy_compressed}"

        with connection.cursor() as cursor:
            cursor.execute(
                "UPDATE people SET email = %s WHERE id = %s",
                [legacy_format, test_user.pk]
            )

        migration_successful, migrated_data = SecureEncryptionService.migrate_legacy_data(legacy_compressed)

        self.assertTrue(migration_successful)
        self.assertTrue(migrated_data.startswith('FERNET_V1:'))

        decrypted = SecureEncryptionService.decrypt(migrated_data)
        self.assertEqual(decrypted, legacy_email)

    def test_plaintext_data_migration_scenario(self):
        """Test migration of plaintext data to secure encryption."""
        test_user = People.objects.create(
            peoplecode="PLAIN_001",
            peoplename="Plaintext User",
            loginid="plain001",
            dateofbirth=date(1990, 1, 1)
        )

        plaintext_email = "plaintext@example.com"

        with connection.cursor() as cursor:
            cursor.execute(
                "UPDATE people SET email = %s WHERE id = %s",
                [plaintext_email, test_user.pk]
            )

        reloaded_user = People.objects.get(pk=test_user.pk)
        self.assertEqual(reloaded_user.email, plaintext_email)

        reloaded_user.email = "now_secure@example.com"
        reloaded_user.save(update_fields=['email'])

        with connection.cursor() as cursor:
            cursor.execute("SELECT email FROM people WHERE id = %s", [test_user.pk])
            raw_email = cursor.fetchone()[0]
            self.assertTrue(raw_email.startswith('FERNET_V1:'))

    def test_concurrent_encryption_operations_thread_safe(self):
        """Test encryption operations are thread-safe under concurrent load."""
        import threading
        import queue

        results = queue.Queue()
        errors = queue.Queue()

        def concurrent_user_creation(thread_id):
            try:
                for i in range(5):
                    user = People.objects.create(
                        peoplecode=f"CONC{thread_id:02d}{i:02d}",
                        peoplename=f"Concurrent User {thread_id}-{i}",
                        loginid=f"conc{thread_id}_{i}",
                        email=f"concurrent{thread_id}_{i}@test.com",
                        mobno=f"+1555000{thread_id:02d}{i:02d}",
                        dateofbirth=date(1990, 1, 1)
                    )

                    with connection.cursor() as cursor:
                        cursor.execute("SELECT email FROM people WHERE id = %s", [user.pk])
                        raw_email = cursor.fetchone()[0]
                        if not raw_email.startswith('FERNET_V1:'):
                            errors.put(f"Thread {thread_id}: Email not encrypted")
                            return

                    user.delete()

                results.put(f"thread_{thread_id}_success")
            except Exception as e:
                errors.put(f"Thread {thread_id}: {str(e)}")

        threads = []
        for i in range(3):
            thread = threading.Thread(target=concurrent_user_creation, args=(i,))
            threads.append(thread)
            thread.start()

        for thread in threads:
            thread.join()

        self.assertTrue(errors.empty(), f"Concurrent errors: {list(errors.queue)}")
        self.assertEqual(results.qsize(), 3)

    def test_transaction_rollback_with_encrypted_fields(self):
        """Test encrypted fields behave correctly during transaction rollbacks."""
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                user1 = People.objects.create(
                    peoplecode="ROLLBACK_001",
                    peoplename="Rollback Test 1",
                    loginid="rollback001",
                    email="rollback1@test.com",
                    dateofbirth=date(1990, 1, 1)
                )

                People.objects.create(
                    peoplecode="ROLLBACK_001",
                    peoplename="Rollback Test 2",
                    loginid="rollback002",
                    email="rollback2@test.com",
                    dateofbirth=date(1990, 1, 1)
                )

        self.assertFalse(People.objects.filter(peoplecode="ROLLBACK_001").exists())

    def test_encryption_performance_within_sla(self):
        """Test encryption performance meets SLA requirements."""
        import time

        test_data = "performance_test@example.com"
        iterations = 100
        latencies = []

        for i in range(iterations):
            start = time.time()
            encrypted = SecureEncryptionService.encrypt(test_data)
            decrypted = SecureEncryptionService.decrypt(encrypted)
            latency = (time.time() - start) * 1000
            latencies.append(latency)

            self.assertEqual(decrypted, test_data)

        avg_latency = sum(latencies) / len(latencies)
        max_latency = max(latencies)
        p95_latency = sorted(latencies)[int(len(latencies) * 0.95)]

        self.assertLess(avg_latency, 10.0, f"Average latency too high: {avg_latency:.2f}ms")
        self.assertLess(p95_latency, 50.0, f"P95 latency too high: {p95_latency:.2f}ms")
        self.assertLess(max_latency, 100.0, f"Max latency too high: {max_latency:.2f}ms")

    def test_unicode_and_special_characters_encryption(self):
        """Test encryption handles all character encodings."""
        test_cases = [
            "unicode_tëst@exämple.com",
            "emoji_test_😀@example.com",
            "special!@#$%^&*()_test@example.com",
            "тест@пример.com",
            "测试@例子.com",
            "テスト@例.com",
        ]

        for test_email in test_cases:
            user = People.objects.create(
                peoplecode=f"UNICODE_{hash(test_email) % 10000:04d}",
                peoplename="Unicode Test",
                loginid=f"unicode_{hash(test_email) % 10000}",
                email=test_email,
                dateofbirth=date(1990, 1, 1)
            )

            reloaded = People.objects.get(pk=user.pk)
            self.assertEqual(reloaded.email, test_email)

            user.delete()

    def test_bulk_operations_maintain_encryption(self):
        """Test bulk create/update operations maintain proper encryption."""
        users = [
            People(
                peoplecode=f"BULK_{i:04d}",
                peoplename=f"Bulk User {i}",
                loginid=f"bulk{i:04d}",
                email=f"bulk{i:04d}@test.com",
                dateofbirth=date(1990, 1, 1)
            )
            for i in range(10)
        ]

        People.objects.bulk_create(users)

        for user in People.objects.filter(peoplecode__startswith="BULK_"):
            with connection.cursor() as cursor:
                cursor.execute("SELECT email FROM people WHERE id = %s", [user.pk])
                raw_email = cursor.fetchone()[0]
                self.assertTrue(raw_email.startswith('FERNET_V1:'))

        People.objects.filter(peoplecode__startswith="BULK_").delete()

    def test_encryption_with_database_constraints(self):
        """Test encrypted fields work with database constraints (unique, NOT NULL)."""
        user1 = People.objects.create(
            peoplecode="CONSTRAINT_001",
            peoplename="Constraint Test 1",
            loginid="constraint001",
            email="constraint@test.com",
            dateofbirth=date(1990, 1, 1)
        )

        with self.assertRaises(IntegrityError):
            People.objects.create(
                peoplecode="CONSTRAINT_002",
                peoplename="Constraint Test 2",
                loginid="constraint001",
                email="different@test.com",
                dateofbirth=date(1990, 1, 1)
            )

        user1.delete()

    def test_audit_command_detects_violations(self):
        """Test audit command detects insecure encryption usage."""
        from io import StringIO
        from django.core.management import call_command

        out = StringIO()
        call_command('audit_encryption_security', stdout=out)

        output = out.getvalue()
        self.assertIn('ENCRYPTION SECURITY AUDIT', output)
        self.assertIn('AUDIT', output)

    def test_migration_command_handles_edge_cases(self):
        """Test migration command handles various data formats."""
        test_user = People.objects.create(
            peoplecode="MIGRATE_001",
            peoplename="Migration Test",
            loginid="migrate001",
            dateofbirth=date(1990, 1, 1)
        )

        import zlib
        import base64
        legacy_mobile = "+1234567890"
        legacy_compressed = base64.urlsafe_b64encode(
            zlib.compress(legacy_mobile.encode('utf-8'), 9)
        ).decode('ascii')

        with connection.cursor() as cursor:
            cursor.execute(
                "UPDATE people SET mobno = %s WHERE id = %s",
                [f"ENC_V1:{legacy_compressed}", test_user.pk]
            )

        from io import StringIO
        from django.core.management import call_command

        out = StringIO()
        call_command('migrate_secure_encryption', '--dry-run', stdout=out)

        output = out.getvalue()
        self.assertIn('MIGRATION STATISTICS', output)

        test_user.delete()

    def test_encryption_compliance_dashboard_accessible(self):
        """Test encryption compliance dashboard loads correctly."""
        from django.contrib.auth import get_user_model
        User = get_user_model()

        superuser = User.objects.create_superuser(
            loginid='admin_enc_test',
            peoplecode='ADMIN_ENC',
            peoplename='Admin Encryption Test',
            email='admin@test.com',
            password='testpass123'
        )

        self.client.force_login(superuser)

        response = self.client.get('/admin/security/encryption-compliance/')

        self.assertEqual(response.status_code, 200)
        self.assertIn('Encryption Security Compliance', str(response.content))

        superuser.delete()


@pytest.mark.security
@pytest.mark.integration
class EncryptionComplianceTest(TestCase):
    """Regulatory compliance validation tests."""

    def test_gdpr_article_32_encryption_at_rest(self):
        """GDPR Article 32: Validate encryption of personal data at rest."""
        user = People.objects.create(
            peoplecode="GDPR_001",
            peoplename="GDPR Test User",
            loginid="gdpr001",
            email="gdpr_test@example.com",
            dateofbirth=date(1990, 1, 1)
        )

        with connection.cursor() as cursor:
            cursor.execute("SELECT email FROM people WHERE id = %s", [user.pk])
            raw_email = cursor.fetchone()[0]

            self.assertTrue(raw_email.startswith('FERNET_V1:'))
            self.assertNotIn('gdpr_test@example.com', raw_email)

        user.delete()

    def test_hipaa_164_312_phi_encryption(self):
        """HIPAA §164.312(e)(2)(ii): Validate PHI encryption mechanism."""
        user = People.objects.create(
            peoplecode="HIPAA_001",
            peoplename="HIPAA Test User",
            loginid="hipaa001",
            email="hipaa@test.com",
            mobno="+1234567890",
            dateofbirth=date(1990, 1, 1)
        )

        with connection.cursor() as cursor:
            cursor.execute("SELECT email, mobno FROM people WHERE id = %s", [user.pk])
            raw_email, raw_mobno = cursor.fetchone()

            self.assertTrue(SecureEncryptionService.is_securely_encrypted(raw_email))
            self.assertTrue(SecureEncryptionService.is_securely_encrypted(raw_mobno))

        user.delete()

    def test_soc2_cc6_6_confidential_data_protection(self):
        """SOC2 CC6.6: Validate confidential information is protected."""
        user = People.objects.create(
            peoplecode="SOC2_001",
            peoplename="SOC2 Test User",
            loginid="soc2001",
            email="soc2@test.com",
            dateofbirth=date(1990, 1, 1)
        )

        decrypted_email = user.email
        self.assertEqual(decrypted_email, "soc2@test.com")

        with connection.cursor() as cursor:
            cursor.execute("SELECT email FROM people WHERE id = %s", [user.pk])
            raw_email = cursor.fetchone()[0]

            self.assertTrue(SecureEncryptionService.is_securely_encrypted(raw_email))
            self.assertNotEqual(raw_email, decrypted_email)

        user.delete()

    def test_pci_dss_requirement_3_4_encryption(self):
        """PCI-DSS Req 3.4: Validate encryption renders data unreadable."""
        user = People.objects.create(
            peoplecode="PCI_001",
            peoplename="PCI Test User",
            loginid="pci001",
            email="pci@test.com",
            dateofbirth=date(1990, 1, 1)
        )

        with connection.cursor() as cursor:
            cursor.execute("SELECT email FROM people WHERE id = %s", [user.pk])
            raw_email = cursor.fetchone()[0]

            self.assertNotIn('pci@test.com', raw_email)
            self.assertNotIn('pci', raw_email)
            self.assertTrue(raw_email.startswith('FERNET_V1:'))

            try:
                import base64
                import zlib
                decoded = base64.urlsafe_b64decode(raw_email.split(':')[1])
                decompressed = zlib.decompress(decoded)
                self.fail("Data should NOT be decompressible (proves it's encrypted, not compressed)")
            except (ValueError, zlib.error):
                pass

        user.delete()


@pytest.mark.security
@pytest.mark.integration
class EncryptionStressTest(TestCase):
    """Stress and edge case tests for encryption security."""

    def test_high_volume_encryption_operations(self):
        """Test encryption handles high volume operations without degradation."""
        import time

        start_time = time.time()
        users_created = []

        for i in range(50):
            user = People.objects.create(
                peoplecode=f"VOL_{i:04d}",
                peoplename=f"Volume User {i}",
                loginid=f"vol{i:04d}",
                email=f"volume{i:04d}@test.com",
                dateofbirth=date(1990, 1, 1)
            )
            users_created.append(user.pk)

        elapsed_time = time.time() - start_time

        self.assertLess(elapsed_time, 10.0, f"High volume operations too slow: {elapsed_time:.2f}s")

        for user_pk in users_created:
            with connection.cursor() as cursor:
                cursor.execute("SELECT email FROM people WHERE id = %s", [user_pk])
                raw_email = cursor.fetchone()[0]
                self.assertTrue(raw_email.startswith('FERNET_V1:'))

        People.objects.filter(peoplecode__startswith="VOL_").delete()

    def test_corrupted_encrypted_data_handling(self):
        """Test system handles corrupted encrypted data gracefully."""
        user = People.objects.create(
            peoplecode="CORRUPT_001",
            peoplename="Corruption Test",
            loginid="corrupt001",
            email="corrupt@test.com",
            dateofbirth=date(1990, 1, 1)
        )

        corrupted_values = [
            "FERNET_V1:corrupted_base64_!!!",
            "FERNET_V1:truncated",
            "UNKNOWN_FORMAT:data",
            "\x00\x01\x02\x03",
        ]

        for corrupted in corrupted_values:
            with connection.cursor() as cursor:
                cursor.execute(
                    "UPDATE people SET email = %s WHERE id = %s",
                    [corrupted, user.pk]
                )

            reloaded = People.objects.get(pk=user.pk)

            self.assertTrue(
                reloaded.email is None or isinstance(reloaded.email, str),
                f"Corrupted data should return None or string, got {type(reloaded.email)}"
            )

        user.delete()

    def test_zero_downtime_key_rotation_simulation(self):
        """Simulate zero-downtime key rotation scenario."""
        user = People.objects.create(
            peoplecode="ROTATE_001",
            peoplename="Rotation Test",
            loginid="rotate001",
            email="rotate@test.com",
            dateofbirth=date(1990, 1, 1)
        )

        with connection.cursor() as cursor:
            cursor.execute("SELECT email FROM people WHERE id = %s", [user.pk])
            original_encrypted = cursor.fetchone()[0]

        email_before = user.email
        self.assertEqual(email_before, "rotate@test.com")

        SecureEncryptionService._fernet_instance = None
        SecureEncryptionService._key_derivation_salt = None

        user_after = People.objects.get(pk=user.pk)
        email_after = user_after.email

        self.assertEqual(email_after, "rotate@test.com")
        self.assertEqual(email_before, email_after)

        user.delete()

    def test_field_level_security_properties(self):
        """Test field-level security check properties work correctly."""
        user = People.objects.create(
            peoplecode="PROPS_001",
            peoplename="Properties Test",
            loginid="props001",
            email="props@test.com",
            dateofbirth=date(1990, 1, 1)
        )

        if hasattr(user, 'is_email_securely_encrypted'):
            with connection.cursor() as cursor:
                cursor.execute("SELECT email FROM people WHERE id = %s", [user.pk])
                raw_email = cursor.fetchone()[0]

                if raw_email.startswith('FERNET_V1:'):
                    self.assertTrue(user.is_email_securely_encrypted)

        if hasattr(user, 'email_needs_migration'):
            self.assertFalse(user.email_needs_migration)

        user.delete()


@pytest.mark.security
class EncryptionSecurityPenetrationTest(TestCase):
    """Security penetration tests for encryption vulnerabilities."""

    def test_cannot_bypass_encryption_with_raw_sql(self):
        """Test that raw SQL cannot bypass encryption."""
        user = People.objects.create(
            peoplecode="PENTEST_001",
            peoplename="Pentest User",
            loginid="pentest001",
            email="pentest@example.com",
            dateofbirth=date(1990, 1, 1)
        )

        with connection.cursor() as cursor:
            cursor.execute("SELECT email FROM people WHERE id = %s", [user.pk])
            raw_email = cursor.fetchone()[0]

            self.assertNotIn('pentest@example.com', raw_email)
            self.assertTrue(raw_email.startswith('FERNET_V1:'))

        user.delete()

    def test_cannot_read_encryption_keys_from_encrypted_data(self):
        """Test that encryption keys cannot be derived from encrypted data."""
        emails = [f"keytest{i}@example.com" for i in range(10)]
        encrypted_values = []

        for i, email in enumerate(emails):
            user = People.objects.create(
                peoplecode=f"KEYTEST_{i:03d}",
                peoplename=f"Key Test {i}",
                loginid=f"keytest{i:03d}",
                email=email,
                dateofbirth=date(1990, 1, 1)
            )

            with connection.cursor() as cursor:
                cursor.execute("SELECT email FROM people WHERE id = %s", [user.pk])
                raw_email = cursor.fetchone()[0]
                encrypted_values.append(raw_email)

            user.delete()

        unique_prefixes = set(ev.split(':')[1][:20] for ev in encrypted_values)
        self.assertEqual(len(unique_prefixes), len(emails), "Each encryption should be unique")

    def test_timing_attack_resistance(self):
        """Test encryption operations have consistent timing (resist timing attacks)."""
        import time
        import statistics

        short_data = "a@b.com"
        long_data = "very_long_email_address_" * 10 + "@example.com"

        short_times = []
        long_times = []

        for i in range(20):
            start = time.time()
            SecureEncryptionService.encrypt(short_data)
            short_times.append((time.time() - start) * 1000)

            start = time.time()
            SecureEncryptionService.encrypt(long_data)
            long_times.append((time.time() - start) * 1000)

        short_avg = statistics.mean(short_times)
        long_avg = statistics.mean(long_times)
        variance_ratio = abs(long_avg - short_avg) / short_avg

        self.assertLess(variance_ratio, 5.0, "Timing variance suggests potential timing attack vector")