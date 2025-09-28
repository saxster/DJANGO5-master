"""
Tests for PasswordManagementService.
"""

import pytest
from unittest.mock import Mock, patch
from django.test import TestCase

from apps.peoples.services.password_management_service import (
    PasswordManagementService,
    PasswordOperationResult
)
from apps.peoples.models import People


@pytest.mark.unit
@pytest.mark.django_db
class TestPasswordManagementService(TestCase):
    """Test PasswordManagementService functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.service = PasswordManagementService()

    @patch('apps.peoples.services.password_management_service.People.objects')
    @patch('apps.peoples.services.password_management_service.SetPasswordForm')
    def test_change_password_success(self, mock_form_class, mock_people_objects):
        """Test successful password change."""
        mock_user = Mock()
        mock_people_objects.get.return_value = mock_user

        mock_form = Mock()
        mock_form.is_valid.return_value = True
        mock_form_class.return_value = mock_form

        result = self.service.change_password(1, "newpass123", "newpass123")

        assert result.success is True
        mock_form.save.assert_called_once()

    @patch('apps.peoples.services.password_management_service.People.objects')
    @patch('apps.peoples.services.password_management_service.SetPasswordForm')
    def test_change_password_validation_failure(self, mock_form_class, mock_people_objects):
        """Test password change with validation errors."""
        mock_user = Mock()
        mock_people_objects.get.return_value = mock_user

        mock_form = Mock()
        mock_form.is_valid.return_value = False
        mock_form.errors = {"new_password2": ["Passwords don't match"]}
        mock_form_class.return_value = mock_form

        result = self.service.change_password(1, "pass1", "pass2")

        assert result.success is False
        assert result.errors is not None

    @patch('apps.peoples.services.password_management_service.People.objects')
    def test_change_password_user_not_found(self, mock_people_objects):
        """Test password change for non-existent user."""
        mock_people_objects.get.side_effect = People.DoesNotExist()

        result = self.service.change_password(999, "pass", "pass")

        assert result.success is False
        assert "not found" in result.error_message