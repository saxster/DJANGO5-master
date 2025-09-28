"""
Tests for EmailVerificationService.
"""

import pytest
from unittest.mock import Mock, patch
from django.test import TestCase

from apps.peoples.services.email_verification_service import (
    EmailVerificationService,
    EmailVerificationResult
)
from apps.peoples.models import People
from apps.core.exceptions import EmailServiceException


@pytest.mark.unit
@pytest.mark.django_db
class TestEmailVerificationService(TestCase):
    """Test EmailVerificationService functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.service = EmailVerificationService()

    @patch('apps.peoples.services.email_verification_service.People.objects')
    @patch('apps.peoples.services.email_verification_service.send_email')
    def test_send_verification_email_success(self, mock_send_email, mock_people_objects):
        """Test successful email verification send."""
        mock_user = Mock()
        mock_user.id = 1
        mock_user.email = "test@example.com"
        mock_people_objects.get.return_value = mock_user

        result = self.service.send_verification_email(1)

        assert result.success is True
        mock_send_email.assert_called_once_with(mock_user)

    @patch('apps.peoples.services.email_verification_service.People.objects')
    def test_send_verification_email_user_not_found(self, mock_people_objects):
        """Test email verification for non-existent user."""
        mock_people_objects.get.side_effect = People.DoesNotExist()

        result = self.service.send_verification_email(999)

        assert result.success is False
        assert "not found" in result.error_message

    @patch('apps.peoples.services.email_verification_service.People.objects')
    @patch('apps.peoples.services.email_verification_service.send_email')
    def test_send_verification_email_service_error(self, mock_send_email, mock_people_objects):
        """Test email verification with service error."""
        mock_user = Mock()
        mock_people_objects.get.return_value = mock_user
        mock_send_email.side_effect = EmailServiceException("SMTP error")

        result = self.service.send_verification_email(1)

        assert result.success is False
        assert "temporarily unavailable" in result.error_message