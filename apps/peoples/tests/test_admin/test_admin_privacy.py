"""
Comprehensive tests for admin interface privacy protection.

This test suite validates that the Django admin interface properly masks
sensitive data in list displays, preventing accidental exposure during
administrative tasks.

Tests cover:
    - PeopleAdmin list_display masking
    - Email masking in admin interface
    - Mobile number masking in admin interface
    - Password masking (always hidden)
    - Callable method behavior
    - Admin ordering and filtering

Security Requirements:
    - No decrypted values in admin list display
    - GDPR compliance for admin users
    - Shoulder-surfing protection
    - Screenshot leak prevention
"""

import pytest
from django.test import TestCase, RequestFactory
from django.contrib.admin.sites import AdminSite
from django.contrib.auth import get_user_model
from apps.peoples.admin import PeopleAdmin
from apps.peoples.models import People
from datetime import date


@pytest.mark.django_db
class PeopleAdminPrivacyTests(TestCase):
    """Test suite for PeopleAdmin privacy protection."""

    def setUp(self):
        """Set up test fixtures."""
        self.site = AdminSite()
        self.admin = PeopleAdmin(People, self.site)
        self.factory = RequestFactory()

        # Create test users
        self.test_user = People.objects.create(
            peoplecode="ADMIN001",
            peoplename="Admin Test User",
            loginid="admintest",
            email="admin@example.com",
            mobno="+919876543210",
            dateofbirth=date(1990, 1, 1),
            is_staff=True,
            is_superuser=True,
        )
        self.test_user.set_password("testpassword123")
        self.test_user.save()

    def test_email_masked_method_exists(self):
        """Test that email_masked method exists."""
        self.assertTrue(hasattr(self.admin, 'email_masked'))

    def test_mobno_masked_method_exists(self):
        """Test that mobno_masked method exists."""
        self.assertTrue(hasattr(self.admin, 'mobno_masked'))

    def test_password_masked_method_exists(self):
        """Test that password_masked method exists."""
        self.assertTrue(hasattr(self.admin, 'password_masked'))

    def test_email_masked_returns_masked_value(self):
        """Test email_masked returns properly masked email."""
        masked_email = self.admin.email_masked(self.test_user)

        # Should contain asterisks
        self.assertIn("*", masked_email)

        # Should NOT contain full email
        self.assertNotIn("admin@example.com", masked_email)
        self.assertNotIn("admin", masked_email)

        # Should show partial information
        self.assertIn("ad", masked_email[:2])  # First 2 chars
        self.assertIn(".com", masked_email)  # TLD

    def test_mobno_masked_returns_masked_value(self):
        """Test mobno_masked returns properly masked mobile number."""
        masked_mobno = self.admin.mobno_masked(self.test_user)

        # Should contain asterisks
        self.assertIn("*", masked_mobno)

        # Should NOT contain full number
        self.assertNotIn("9876543210", masked_mobno)

        # Should show partial information (first 3 and last 2)
        self.assertTrue(masked_mobno.startswith("+91"))  # Country code
        self.assertTrue(masked_mobno.endswith("10"))    # Last 2 digits

    def test_password_masked_never_shows_password(self):
        """Test password_masked NEVER shows actual password."""
        masked_password = self.admin.password_masked(self.test_user)

        # Should only show bullets
        self.assertEqual(masked_password, "••••••••")

        # Should NOT contain any part of actual password
        self.assertNotIn("test", masked_password)
        self.assertNotIn("password", masked_password)

    def test_list_display_uses_masked_fields(self):
        """Test that list_display uses masked field methods."""
        list_display = self.admin.list_display

        # Should use masked versions
        self.assertIn("email_masked", list_display)
        self.assertIn("mobno_masked", list_display)
        self.assertIn("password_masked", list_display)

        # Should NOT use raw fields
        self.assertNotIn("email", list_display)
        self.assertNotIn("mobno", list_display)
        self.assertNotIn("password", list_display)

    def test_email_masked_handles_none(self):
        """Test email_masked handles None values gracefully."""
        user_without_email = People.objects.create(
            peoplecode="NOEMAIL001",
            peoplename="No Email User",
            loginid="noemail",
            email="placeholder@example.com",  # Required field
            dateofbirth=date(1990, 1, 1),
        )
        user_without_email.email = None
        user_without_email.save()

        result = self.admin.email_masked(user_without_email)
        self.assertEqual(result, "-")

    def test_mobno_masked_handles_none(self):
        """Test mobno_masked handles None values gracefully."""
        user_without_mobno = People.objects.create(
            peoplecode="NOMOB001",
            peoplename="No Mobile User",
            loginid="nomobile",
            email="nomobile@example.com",
            mobno=None,  # Optional field
            dateofbirth=date(1990, 1, 1),
        )

        result = self.admin.mobno_masked(user_without_mobno)
        self.assertEqual(result, "-")

    def test_password_masked_handles_empty(self):
        """Test password_masked handles empty password."""
        user_no_password = People.objects.create(
            peoplecode="NOPASS001",
            peoplename="No Password User",
            loginid="nopassword",
            email="nopass@example.com",
            dateofbirth=date(1990, 1, 1),
        )
        # Don't set password

        result = self.admin.password_masked(user_no_password)
        self.assertEqual(result, "-")

    def test_admin_ordering_preserved(self):
        """Test that admin ordering works with masked fields."""
        # email_masked should have admin_order_field set
        self.assertTrue(hasattr(self.admin.email_masked, 'admin_order_field'))
        self.assertEqual(self.admin.email_masked.admin_order_field, 'email')

        # mobno_masked should have admin_order_field set
        self.assertTrue(hasattr(self.admin.mobno_masked, 'admin_order_field'))
        self.assertEqual(self.admin.mobno_masked.admin_order_field, 'mobno')

    def test_short_descriptions_set(self):
        """Test that short descriptions are properly set."""
        self.assertEqual(self.admin.email_masked.short_description, "Email")
        self.assertEqual(self.admin.mobno_masked.short_description, "Mobile")
        self.assertEqual(self.admin.password_masked.short_description, "Password")

    def test_multiple_users_different_masking(self):
        """Test that different users have different masked values."""
        user2 = People.objects.create(
            peoplecode="ADMIN002",
            peoplename="Second Admin",
            loginid="admin2",
            email="different@example.com",
            mobno="+911234567890",
            dateofbirth=date(1990, 1, 1),
        )

        masked1_email = self.admin.email_masked(self.test_user)
        masked2_email = self.admin.email_masked(user2)

        # Should be different
        self.assertNotEqual(masked1_email, masked2_email)

        masked1_mobno = self.admin.mobno_masked(self.test_user)
        masked2_mobno = self.admin.mobno_masked(user2)

        # Should be different
        self.assertNotEqual(masked1_mobno, masked2_mobno)


@pytest.mark.django_db
class AdminSecurityComplianceTests(TestCase):
    """Tests for security compliance in admin interface."""

    def setUp(self):
        """Set up test fixtures."""
        self.site = AdminSite()
        self.admin = PeopleAdmin(People, self.site)

    def test_no_plaintext_in_changelist(self):
        """Test that changelist never shows plaintext sensitive data."""
        # Create test user
        user = People.objects.create(
            peoplecode="SECRET001",
            peoplename="Secret User",
            loginid="secretuser",
            email="secret@company.com",
            mobno="+919999999999",
            dateofbirth=date(1990, 1, 1),
        )

        # Get masked displays
        email_display = self.admin.email_masked(user)
        mobno_display = self.admin.mobno_masked(user)

        # Verify no plaintext
        self.assertNotIn("secret@company.com", email_display)
        self.assertNotIn("9999999999", mobno_display)

        # Verify masking present
        self.assertIn("*", email_display)
        self.assertIn("*", mobno_display)

    def test_admin_documentation_present(self):
        """Test that admin class has proper documentation."""
        self.assertIsNotNone(self.admin.__doc__)
        self.assertIn("privacy", self.admin.__doc__.lower())

    def test_list_select_related_optimization(self):
        """Test that list_select_related includes necessary relations."""
        # Should have select_related for performance
        self.assertTrue(hasattr(self.admin, 'list_select_related'))
        self.assertIsInstance(self.admin.list_select_related, tuple)


@pytest.mark.django_db
class AdminEdgeCaseTests(TestCase):
    """Tests for edge cases in admin interface."""

    def setUp(self):
        """Set up test fixtures."""
        self.site = AdminSite()
        self.admin = PeopleAdmin(People, self.site)

    def test_unicode_email_masking_in_admin(self):
        """Test unicode email masking in admin."""
        user = People.objects.create(
            peoplecode="UNICODE001",
            peoplename="Unicode User",
            loginid="unicode",
            email="tëst@exämple.com",
            dateofbirth=date(1990, 1, 1),
        )

        masked = self.admin.email_masked(user)
        self.assertIn("*", masked)
        self.assertNotIn("tëst", masked)

    def test_very_long_email_in_admin(self):
        """Test very long email masking in admin."""
        long_email = "verylongemailaddress" * 5 + "@company.com"
        user = People.objects.create(
            peoplecode="LONG001",
            peoplename="Long Email User",
            loginid="longuser",
            email=long_email,
            dateofbirth=date(1990, 1, 1),
        )

        masked = self.admin.email_masked(user)
        self.assertIn("*", masked)
        # Should not contain the full long string
        self.assertNotIn("verylongemailaddress" * 5, masked)

    def test_special_characters_in_phone(self):
        """Test phone numbers with special characters."""
        user = People.objects.create(
            peoplecode="SPECIAL001",
            peoplename="Special Phone User",
            loginid="special",
            email="special@example.com",
            mobno="+1-555-123-4567",
            dateofbirth=date(1990, 1, 1),
        )

        masked = self.admin.mobno_masked(user)
        self.assertIn("*", masked)
        # Should not show full number with dashes
        self.assertNotIn("555-123-4567", masked)


@pytest.mark.django_db
class AdminResourceClassTests(TestCase):
    """Tests for import/export resource classes."""

    def setUp(self):
        """Set up test fixtures."""
        self.site = AdminSite()
        self.admin = PeopleAdmin(People, self.site)

    def test_resource_class_set(self):
        """Test that resource class is properly configured."""
        from apps.peoples.admin import PeopleResource

        self.assertEqual(self.admin.resource_class, PeopleResource)

    def test_list_display_links_preserved(self):
        """Test that list display links are preserved."""
        self.assertEqual(
            self.admin.list_display_links,
            ["peoplecode", "peoplename"]
        )
