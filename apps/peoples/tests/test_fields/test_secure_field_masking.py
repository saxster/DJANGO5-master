"""
Comprehensive tests for MaskedSecureValue and secure field privacy protection.

This test suite validates that sensitive data is properly masked in all representations
to prevent accidental exposure in logs, admin interfaces, debugging, and API responses.

Tests cover:
    - MaskedSecureValue __str__ and __repr__ masking
    - Email masking patterns
    - Phone number masking patterns
    - Raw value access with audit logging
    - Integration with EnhancedSecureString field
    - Database save/load cycles with masking
    - Edge cases and special characters

Security Requirements:
    - GDPR compliance (privacy by design)
    - OWASP security best practices
    - Audit logging for all raw value access
    - Prevention of shoulder-surfing attacks
"""

import pytest
import logging
from django.test import TestCase
from apps.peoples.fields import MaskedSecureValue, EnhancedSecureString
from apps.peoples.models import People
from datetime import date


class MaskedSecureValueTests(TestCase):
    """Test suite for MaskedSecureValue wrapper class."""

    def test_email_masking_standard(self):
        """Test standard email masking pattern."""
        email = MaskedSecureValue("user@example.com")
        masked = str(email)

        # Should mask local part except first 2 chars
        self.assertIn("us", masked)
        self.assertNotIn("user", masked)
        self.assertIn("*", masked)
        self.assertIn("@", masked)

        # Should mask domain except TLD
        self.assertNotIn("example", masked)
        self.assertIn(".com", masked)

    def test_email_masking_short_local(self):
        """Test email masking with short local part."""
        email = MaskedSecureValue("ab@test.com")
        masked = str(email)

        # Short local should be fully masked
        self.assertIn("*", masked)
        self.assertIn("@", masked)
        self.assertIn(".com", masked)
        self.assertNotIn("ab", masked)

    def test_phone_masking_standard(self):
        """Test standard phone number masking."""
        phone = MaskedSecureValue("+919876543210")
        masked = str(phone)

        # Should show first 3 and last 2 digits
        self.assertIn("+91", masked[:3])
        self.assertIn("10", masked[-2:])
        self.assertIn("*", masked)
        self.assertNotIn("987654321", masked)

    def test_phone_masking_short(self):
        """Test phone masking with short number."""
        phone = MaskedSecureValue("12345")
        masked = str(phone)

        # Short numbers should be fully masked
        self.assertEqual(masked, "********")

    def test_repr_masking(self):
        """Test __repr__ returns masked value."""
        email = MaskedSecureValue("test@example.com")
        repr_str = repr(email)

        # repr should include <MaskedValue: ...>
        self.assertIn("<MaskedValue:", repr_str)
        self.assertIn("*", repr_str)
        self.assertNotIn("test", repr_str)

    def test_raw_value_property(self):
        """Test raw_value property returns unmasked value."""
        original = "sensitive@data.com"
        masked = MaskedSecureValue(original)

        # raw_value should return original
        self.assertEqual(masked.raw_value, original)

    def test_raw_value_audit_logging(self):
        """Test raw_value access triggers audit logging."""
        import logging
        from unittest.mock import patch

        with patch.object(logging.getLogger('security_audit'), 'warning') as mock_log:
            masked = MaskedSecureValue("secret@data.com")
            _ = masked.raw_value

            # Should have logged the access
            mock_log.assert_called_once()
            call_args = mock_log.call_args

            # Check log message
            self.assertIn("Unmasked secure field access", call_args[0][0])

            # Check extra context
            extra = call_args[1]['extra']
            self.assertIn('correlation_id', extra)
            self.assertIn('access_type', extra)
            self.assertIn('stack_trace', extra)

    def test_equality_comparison(self):
        """Test equality comparison works correctly."""
        value1 = MaskedSecureValue("test@example.com")
        value2 = MaskedSecureValue("test@example.com")
        value3 = MaskedSecureValue("other@example.com")

        # Same values should be equal
        self.assertEqual(value1, value2)

        # Different values should not be equal
        self.assertNotEqual(value1, value3)

        # Should work with string comparison
        self.assertEqual(value1, "test@example.com")

    def test_hash_works(self):
        """Test hashing works for use in dicts/sets."""
        value1 = MaskedSecureValue("test@example.com")
        value2 = MaskedSecureValue("test@example.com")

        # Same values should have same hash
        self.assertEqual(hash(value1), hash(value2))

        # Should be usable in sets
        value_set = {value1, value2}
        self.assertEqual(len(value_set), 1)

    def test_boolean_evaluation(self):
        """Test boolean evaluation."""
        # Non-empty value should be truthy
        self.assertTrue(MaskedSecureValue("test@example.com"))

        # Empty string should be falsy
        self.assertFalse(MaskedSecureValue(""))

        # None should be falsy
        self.assertFalse(MaskedSecureValue(None))

    def test_length_works(self):
        """Test length calculation."""
        value = MaskedSecureValue("test@example.com")
        self.assertEqual(len(value), len("test@example.com"))

    def test_empty_value_handling(self):
        """Test handling of empty values."""
        empty = MaskedSecureValue("")
        self.assertEqual(str(empty), "")

        none = MaskedSecureValue(None)
        self.assertEqual(str(none), "")


@pytest.mark.django_db
class EnhancedSecureStringMaskingTests(TestCase):
    """Integration tests for EnhancedSecureString with MaskedSecureValue."""

    def test_field_returns_masked_value(self):
        """Test field returns MaskedSecureValue on database read."""
        # Create user with encrypted email
        user = People.objects.create(
            peoplecode="TEST001",
            peoplename="Test User",
            loginid="testuser",
            email="test@example.com",
            dateofbirth=date(1990, 1, 1),
        )

        # Reload from database
        user_reloaded = People.objects.get(pk=user.pk)

        # Email should be MaskedSecureValue instance
        self.assertIsInstance(user_reloaded.email, MaskedSecureValue)

        # String representation should be masked
        email_str = str(user_reloaded.email)
        self.assertIn("*", email_str)
        self.assertNotIn("test", email_str)

    def test_masked_value_in_admin_display(self):
        """Test masked values appear in admin-like displays."""
        user = People.objects.create(
            peoplecode="TEST002",
            peoplename="Admin Test",
            loginid="admintest",
            email="admin@company.com",
            mobno="+919876543210",
            dateofbirth=date(1990, 1, 1),
        )

        user_reloaded = People.objects.get(pk=user.pk)

        # Email display should be masked
        email_display = str(user_reloaded.email)
        self.assertNotIn("admin", email_display)
        self.assertIn("*", email_display)

        # Mobile display should be masked
        mobno_display = str(user_reloaded.mobno)
        self.assertNotIn("987654321", mobno_display)
        self.assertIn("*", mobno_display)

    def test_raw_value_accessible_when_needed(self):
        """Test raw value can be accessed when legitimately needed."""
        user = People.objects.create(
            peoplecode="TEST003",
            peoplename="Raw Value Test",
            loginid="rawtest",
            email="raw@example.com",
            dateofbirth=date(1990, 1, 1),
        )

        user_reloaded = People.objects.get(pk=user.pk)

        # Should be able to access raw value explicitly
        raw_email = user_reloaded.email.raw_value
        self.assertEqual(raw_email, "raw@example.com")

    def test_save_with_masked_value(self):
        """Test saving model with MaskedSecureValue works correctly."""
        user = People.objects.create(
            peoplecode="TEST004",
            peoplename="Save Test",
            loginid="savetest",
            email="save@example.com",
            dateofbirth=date(1990, 1, 1),
        )

        # Reload and modify
        user_reloaded = People.objects.get(pk=user.pk)
        user_reloaded.peoplename = "Modified Name"
        user_reloaded.save()  # Email should still be MaskedSecureValue

        # Verify email is still correct after save
        user_final = People.objects.get(pk=user.pk)
        self.assertEqual(user_final.email.raw_value, "save@example.com")

    def test_unicode_email_masking(self):
        """Test masking works with unicode characters."""
        user = People.objects.create(
            peoplecode="TEST005",
            peoplename="Unicode Test",
            loginid="unicodetest",
            email="tëst@exämple.com",
            dateofbirth=date(1990, 1, 1),
        )

        user_reloaded = People.objects.get(pk=user.pk)
        email_str = str(user_reloaded.email)

        # Should be masked
        self.assertIn("*", email_str)
        self.assertNotIn("tëst", email_str)


@pytest.mark.django_db
class PrivacyComplianceTests(TestCase):
    """Tests for GDPR and privacy compliance."""

    def test_no_plaintext_in_logs(self):
        """Test that str() never exposes plaintext in logs."""
        user = People.objects.create(
            peoplecode="PRIVACY001",
            peoplename="Privacy Test",
            loginid="privacytest",
            email="privacy@sensitive.com",
            mobno="+919999999999",
            dateofbirth=date(1990, 1, 1),
        )

        user_reloaded = People.objects.get(pk=user.pk)

        # Simulate logging (what would appear in log files)
        log_message = f"User email: {user_reloaded.email}, mobile: {user_reloaded.mobno}"

        # Log message should not contain sensitive data
        self.assertNotIn("privacy@sensitive.com", log_message)
        self.assertNotIn("9999999999", log_message)
        self.assertIn("*", log_message)

    def test_repr_safe_for_debugging(self):
        """Test that repr() is safe for debugging output."""
        user = People.objects.create(
            peoplecode="DEBUG001",
            peoplename="Debug Test",
            loginid="debugtest",
            email="debug@test.com",
            dateofbirth=date(1990, 1, 1),
        )

        user_reloaded = People.objects.get(pk=user.pk)

        # repr() should not expose sensitive data
        repr_output = repr(user_reloaded.email)
        self.assertNotIn("debug", repr_output)
        self.assertIn("MaskedValue", repr_output)

    def test_comparison_works_without_exposure(self):
        """Test comparisons work without exposing values."""
        user1 = People.objects.create(
            peoplecode="COMP001",
            peoplename="Compare Test 1",
            loginid="compare1",
            email="same@test.com",
            dateofbirth=date(1990, 1, 1),
        )

        user2 = People.objects.create(
            peoplecode="COMP002",
            peoplename="Compare Test 2",
            loginid="compare2",
            email="same@test.com",
            dateofbirth=date(1990, 1, 1),
        )

        user1_reloaded = People.objects.get(pk=user1.pk)
        user2_reloaded = People.objects.get(pk=user2.pk)

        # Should be able to compare without exposing values
        self.assertEqual(user1_reloaded.email, user2_reloaded.email)


@pytest.mark.django_db
class EdgeCaseTests(TestCase):
    """Tests for edge cases and special scenarios."""

    def test_none_value_handling(self):
        """Test handling of None values."""
        user = People.objects.create(
            peoplecode="NONE001",
            peoplename="None Test",
            loginid="nonetest",
            email="test@example.com",
            mobno=None,  # Explicit None
            dateofbirth=date(1990, 1, 1),
        )

        user_reloaded = People.objects.get(pk=user.pk)

        # mobno should handle None gracefully
        self.assertIsNone(user_reloaded.mobno)

    def test_empty_string_handling(self):
        """Test handling of empty strings."""
        masked = MaskedSecureValue("")
        self.assertEqual(str(masked), "")
        self.assertFalse(masked)  # Should be falsy

    def test_very_long_email(self):
        """Test masking of very long email addresses."""
        long_email = "verylongemailaddress" * 10 + "@example.com"
        masked = MaskedSecureValue(long_email)
        masked_str = str(masked)

        # Should still be masked
        self.assertIn("*", masked_str)
        self.assertNotIn("verylongemailaddress" * 10, masked_str)

    def test_special_characters_in_email(self):
        """Test masking with special characters."""
        email = MaskedSecureValue("user+tag@example.com")
        masked_str = str(email)

        # Should mask the special characters too
        self.assertIn("*", masked_str)
        self.assertNotIn("+tag", masked_str)

    def test_international_phone_format(self):
        """Test various international phone formats."""
        phones = [
            "+1-555-123-4567",
            "+44 20 1234 5678",
            "+91 98765 43210",
        ]

        for phone in phones:
            masked = MaskedSecureValue(phone)
            masked_str = str(masked)

            # All should be masked
            self.assertIn("*", masked_str)
            # Original number should not be fully visible
            self.assertTrue(len(masked_str) < len(phone) or "*" in masked_str)
