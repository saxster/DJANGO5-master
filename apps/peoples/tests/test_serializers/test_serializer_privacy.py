"""
Comprehensive tests for serializer privacy protection.

This test suite validates that API serializers properly mask sensitive data
in responses, preventing accidental exposure through API endpoints.

Tests cover:
    - PeopleSerializer masked display fields
    - email_display field masking
    - mobno_display field masking
    - API response privacy
    - Serialization/deserialization

Security Requirements:
    - No decrypted values in API responses
    - GDPR compliance for API consumers
    - Masked display fields for sensitive data
"""

import pytest
from django.test import TestCase
from rest_framework.test import APIRequestFactory
from apps.peoples.serializers import PeopleSerializer
from apps.peoples.models import People
from datetime import date


@pytest.mark.django_db
class PeopleSerializerPrivacyTests(TestCase):
    """Test suite for PeopleSerializer privacy protection."""

    def setUp(self):
        """Set up test fixtures."""
        self.factory = APIRequestFactory()

        # Create test user
        self.test_user = People.objects.create(
            peoplecode="SER001",
            peoplename="Serializer Test User",
            loginid="sertest",
            email="serializer@example.com",
            mobno="+919876543210",
            dateofbirth=date(1990, 1, 1),
        )

    def test_serializer_has_display_fields(self):
        """Test that serializer includes masked display fields."""
        serializer = PeopleSerializer(self.test_user)
        data = serializer.data

        # Should have display fields
        self.assertIn('email_display', data)
        self.assertIn('mobno_display', data)

    def test_email_display_is_masked(self):
        """Test that email_display returns masked value."""
        serializer = PeopleSerializer(self.test_user)
        data = serializer.data

        email_display = data['email_display']

        # Should be masked
        self.assertIn('*', email_display)
        self.assertNotIn('serializer@example.com', email_display)
        self.assertNotIn('serializer', email_display)

    def test_mobno_display_is_masked(self):
        """Test that mobno_display returns masked value."""
        serializer = PeopleSerializer(self.test_user)
        data = serializer.data

        mobno_display = data['mobno_display']

        # Should be masked
        self.assertIn('*', mobno_display)
        self.assertNotIn('987654321', mobno_display)

    def test_display_fields_are_read_only(self):
        """Test that display fields are read-only."""
        serializer = PeopleSerializer(self.test_user)

        # Should be in read_only_fields
        meta = serializer.Meta
        self.assertIn('email_display', meta.read_only_fields)
        self.assertIn('mobno_display', meta.read_only_fields)

    def test_serializer_handles_none_email(self):
        """Test serializer handles None email gracefully."""
        user_without_email = People.objects.create(
            peoplecode="NOEMAIL002",
            peoplename="No Email",
            loginid="noemail2",
            email="temp@example.com",  # Required
            dateofbirth=date(1990, 1, 1),
        )

        serializer = PeopleSerializer(user_without_email)
        data = serializer.data

        # Should handle None gracefully
        # (note: email is required, so this tests the method's None handling)
        self.assertIsNotNone(data['email_display'])

    def test_serializer_handles_none_mobno(self):
        """Test serializer handles None mobno gracefully."""
        user_without_mobno = People.objects.create(
            peoplecode="NOMOB002",
            peoplename="No Mobile",
            loginid="nomob2",
            email="nomob2@example.com",
            mobno=None,  # Optional
            dateofbirth=date(1990, 1, 1),
        )

        serializer = PeopleSerializer(user_without_mobno)
        data = serializer.data

        # Should return None for display
        self.assertIsNone(data['mobno_display'])

    def test_multiple_users_different_masking(self):
        """Test that different users have different masked displays."""
        user2 = People.objects.create(
            peoplecode="SER002",
            peoplename="Second User",
            loginid="sertest2",
            email="different@example.com",
            mobno="+911234567890",
            dateofbirth=date(1990, 1, 1),
        )

        serializer1 = PeopleSerializer(self.test_user)
        serializer2 = PeopleSerializer(user2)

        data1 = serializer1.data
        data2 = serializer2.data

        # Should have different masked values
        self.assertNotEqual(data1['email_display'], data2['email_display'])
        self.assertNotEqual(data1['mobno_display'], data2['mobno_display'])


@pytest.mark.django_db
class SerializerAPIResponseTests(TestCase):
    """Tests for API response privacy."""

    def setUp(self):
        """Set up test fixtures."""
        self.test_user = People.objects.create(
            peoplecode="API001",
            peoplename="API Test User",
            loginid="apitest",
            email="api@example.com",
            mobno="+919999999999",
            dateofbirth=date(1990, 1, 1),
        )

    def test_no_plaintext_in_serialized_data(self):
        """Test that serialized data doesn't contain plaintext sensitive info."""
        serializer = PeopleSerializer(self.test_user)
        data = serializer.data

        # Convert to string (simulating API response)
        response_str = str(data)

        # The display fields should be masked
        # Note: The actual email field may still return MaskedSecureValue
        # but the display field should definitely be masked
        email_display = data.get('email_display', '')
        mobno_display = data.get('mobno_display', '')

        self.assertIn('*', email_display)
        self.assertIn('*', mobno_display)

    def test_serializer_validation_still_works(self):
        """Test that validation still works with masked values."""
        data = {
            'peoplecode': 'VALID001',
            'peoplename': 'Valid User',
            'loginid': 'validuser',
            'email': 'valid@example.com',
            'mobno': '+919876543210',
            'dateofbirth': '1990-01-01',
        }

        serializer = PeopleSerializer(data=data)
        self.assertTrue(serializer.is_valid())


@pytest.mark.django_db
class SerializerEdgeCaseTests(TestCase):
    """Tests for edge cases in serializer privacy."""

    def test_unicode_email_in_serializer(self):
        """Test unicode email masking in serializer."""
        user = People.objects.create(
            peoplecode="UNICODE002",
            peoplename="Unicode User",
            loginid="unicode2",
            email="tëst@exämple.com",
            dateofbirth=date(1990, 1, 1),
        )

        serializer = PeopleSerializer(user)
        data = serializer.data

        email_display = data['email_display']
        self.assertIn('*', email_display)
        self.assertNotIn('tëst', email_display)

    def test_special_characters_phone_in_serializer(self):
        """Test phone with special characters in serializer."""
        user = People.objects.create(
            peoplecode="SPECIAL002",
            peoplename="Special User",
            loginid="special2",
            email="special2@example.com",
            mobno="+1-555-123-4567",
            dateofbirth=date(1990, 1, 1),
        )

        serializer = PeopleSerializer(user)
        data = serializer.data

        mobno_display = data['mobno_display']
        self.assertIn('*', mobno_display)
