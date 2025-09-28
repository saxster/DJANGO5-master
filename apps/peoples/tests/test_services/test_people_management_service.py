"""
Comprehensive tests for PeopleManagementService.

Tests CRUD operations, encryption/decryption, error handling,
and transaction management.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from django.test import TestCase
from django.core.exceptions import ValidationError
from django.db import IntegrityError

from apps.peoples.services.people_management_service import (
    PeopleManagementService,
    PeopleListResult,
    PeopleOperationResult
)
from apps.peoples.models import People
from apps.core.exceptions import UserManagementException, SecurityException


@pytest.mark.unit
@pytest.mark.django_db
class TestPeopleManagementService(TestCase):
    """Test PeopleManagementService functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.service = PeopleManagementService()
        self.mock_user = Mock()
        self.mock_user.id = 1
        self.mock_user.peoplecode = "ADMIN001"
        self.session = {
            "bu_id": 1,
            "client_id": 1,
            "tenantid": 1
        }

    @patch('apps.peoples.services.people_management_service.People.objects')
    def test_get_people_list_success(self, mock_people_objects):
        """Test successful people list retrieval with pagination."""
        mock_queryset = Mock()
        mock_queryset.count.return_value = 100
        mock_queryset.__getitem__.return_value = [
            {"id": 1, "peoplename": "Test User", "email": "encrypted_email"}
        ]
        mock_people_objects.people_list_view.return_value = mock_queryset

        request_params = {
            "draw": "1",
            "start": "0",
            "length": "10"
        }

        result = self.service.get_people_list(request_params, self.session)

        assert isinstance(result, PeopleListResult)
        assert result.total == 100
        assert result.draw == 1

    @patch('apps.peoples.services.people_management_service.People.objects')
    def test_get_people_list_with_search(self, mock_people_objects):
        """Test people list with search filter."""
        mock_queryset = Mock()
        mock_queryset.filter.return_value = mock_queryset
        mock_queryset.count.return_value = 5
        mock_queryset.__getitem__.return_value = []
        mock_people_objects.people_list_view.return_value = mock_queryset

        request_params = {
            "draw": "1",
            "start": "0",
            "length": "10",
            "search[value]": "John"
        }

        result = self.service.get_people_list(request_params, self.session)

        assert result.total == 5
        mock_queryset.filter.assert_called_once()

    @patch('apps.peoples.services.people_management_service.People')
    @patch('apps.peoples.services.people_management_service.putils')
    def test_create_people_success(self, mock_putils, mock_people):
        """Test successful people creation."""
        mock_instance = Mock()
        mock_instance.id = 1
        mock_instance.peoplecode = "TEST001"
        mock_instance.bu = None
        mock_people.return_value = mock_instance
        mock_putils.save_jsonform.return_value = True

        form_data = {
            "peoplecode": "TEST001",
            "peoplename": "Test User"
        }
        json_form_data = {"userfor": "Web"}

        result = self.service.create_people(
            form_data, json_form_data, self.mock_user, self.session
        )

        assert result.success is True
        assert result.people == mock_instance
        assert result.data["pk"] == 1

    @patch('apps.peoples.services.people_management_service.People')
    def test_create_people_integrity_error(self, mock_people):
        """Test people creation with integrity error."""
        mock_people.side_effect = IntegrityError("Duplicate entry")

        form_data = {"peoplecode": "DUP001"}
        json_form_data = {}

        result = self.service.create_people(
            form_data, json_form_data, self.mock_user, self.session
        )

        assert result.success is False
        assert "already exists" in result.error_message

    @patch('apps.peoples.services.people_management_service.People.objects')
    @patch('apps.peoples.services.people_management_service.putils')
    def test_update_people_success(self, mock_putils, mock_people_objects):
        """Test successful people update."""
        mock_instance = Mock()
        mock_instance.id = 1
        mock_instance.peoplecode = "TEST001"
        mock_instance.bu = None
        mock_people_objects.get.return_value = mock_instance
        mock_putils.save_jsonform.return_value = True

        form_data = {"peoplename": "Updated Name"}
        json_form_data = {}

        result = self.service.update_people(
            1, form_data, json_form_data, self.mock_user, self.session
        )

        assert result.success is True
        assert result.data["pk"] == 1

    @patch('apps.peoples.services.people_management_service.People.objects')
    def test_update_people_not_found(self, mock_people_objects):
        """Test update with non-existent people."""
        mock_people_objects.get.side_effect = People.DoesNotExist()

        result = self.service.update_people(
            999, {}, {}, self.mock_user, self.session
        )

        assert result.success is False
        assert "not found" in result.error_message

    @patch('apps.peoples.services.people_management_service.People.objects')
    def test_get_people_success(self, mock_people_objects):
        """Test retrieving people by ID."""
        mock_instance = Mock()
        mock_queryset = Mock()
        mock_queryset.get.return_value = mock_instance
        mock_people_objects.select_related.return_value = mock_queryset

        people = self.service.get_people(1, self.session)

        assert people == mock_instance

    @patch('apps.peoples.services.people_management_service.People.objects')
    def test_get_people_not_found(self, mock_people_objects):
        """Test retrieving non-existent people."""
        mock_queryset = Mock()
        mock_queryset.get.side_effect = People.DoesNotExist()
        mock_people_objects.select_related.return_value = mock_queryset

        people = self.service.get_people(999, self.session)

        assert people is None

    @patch('apps.peoples.services.people_management_service.People.objects')
    def test_delete_people_soft_delete(self, mock_people_objects):
        """Test soft delete of people."""
        mock_instance = Mock()
        mock_instance.peoplecode = "TEST001"
        mock_people_objects.get.return_value = mock_instance

        result = self.service.delete_people(1, self.mock_user, self.session)

        assert result.success is True
        assert mock_instance.enable is False
        mock_instance.save.assert_called_once()

    @patch('apps.peoples.services.people_management_service.decrypt')
    def test_decrypt_field_value_success(self, mock_decrypt):
        """Test successful field decryption."""
        mock_decrypt.return_value = "decrypted_value"

        result = self.service._decrypt_field_value("encrypted_value", "email")

        assert result == "decrypted_value"
        mock_decrypt.assert_called_once_with("encrypted_value")

    @patch('apps.peoples.services.people_management_service.decrypt')
    def test_decrypt_field_value_failure(self, mock_decrypt):
        """Test field decryption failure handling."""
        mock_decrypt.side_effect = ValueError("Decryption failed")

        result = self.service._decrypt_field_value("invalid_value", "email")

        assert result == "invalid_value"

    @patch('apps.peoples.services.people_management_service.decrypt')
    def test_decrypt_field_security_exception(self, mock_decrypt):
        """Test field decryption with security exception."""
        mock_decrypt.side_effect = SecurityException("Security violation")

        result = self.service._decrypt_field_value("suspicious_value", "email")

        assert result == "[ENCRYPTED]"

    def test_apply_search_filter(self):
        """Test search filter application."""
        mock_queryset = Mock()
        mock_queryset.filter.return_value = mock_queryset

        result = self.service._apply_search_filter(mock_queryset, "test")

        mock_queryset.filter.assert_called_once()

    def test_apply_ordering_with_column(self):
        """Test ordering application with column name."""
        mock_queryset = Mock()
        mock_queryset.order_by.return_value = mock_queryset

        request_params = {
            "order[0][column]": "1",
            "order[0][dir]": "asc",
            "columns[1][data]": "peoplename"
        }

        result = self.service._apply_ordering(mock_queryset, request_params)

        mock_queryset.order_by.assert_called_once_with("peoplename")

    def test_apply_ordering_descending(self):
        """Test descending ordering."""
        mock_queryset = Mock()
        mock_queryset.order_by.return_value = mock_queryset

        request_params = {
            "order[0][column]": "0",
            "order[0][dir]": "desc",
            "columns[0][data]": "id"
        }

        result = self.service._apply_ordering(mock_queryset, request_params)

        mock_queryset.order_by.assert_called_once_with("-id")

    def test_serialize_people_list(self):
        """Test people list serialization with encrypted fields."""
        data = [
            {"id": 1, "email": "encrypted_email", "mobno": "encrypted_mobno"}
        ]

        with patch.object(self.service, '_decrypt_field_value') as mock_decrypt:
            mock_decrypt.return_value = "decrypted"
            result = self.service._serialize_people_list(data)

            assert result[0]["email"] == "decrypted"
            assert result[0]["mobno"] == "decrypted"
            assert mock_decrypt.call_count == 2


@pytest.mark.integration
@pytest.mark.django_db
class TestPeopleManagementServiceIntegration(TestCase):
    """Integration tests with real database operations."""

    def setUp(self):
        """Set up test fixtures with real database."""
        from apps.onboarding.models import Bt, Typeassist
        from apps.tenants.models import Tenant

        self.service = PeopleManagementService()

        self.tenant = Tenant.objects.create(
            tenant_name="Test Tenant",
            tenant_code="TEST"
        )

        self.bu = Bt.objects.create(
            buname="Test BU",
            bucode="TESTBU",
            tenant=self.tenant
        )

        self.peopletype = Typeassist.objects.create(
            taname="Employee",
            tacode="EMP",
            tafor="PEOPLE"
        )

        self.user = People.objects.create_user(
            loginid="admin",
            peoplecode="ADMIN001",
            peoplename="Admin User",
            bu=self.bu,
            peopletype=self.peopletype
        )

        self.session = {
            "bu_id": self.bu.id,
            "client_id": self.bu.id,
            "tenantid": self.tenant.id
        }

    def test_create_people_integration(self):
        """Test creating people with real database."""
        form_data = {
            "peoplecode": "TEST002",
            "peoplename": "Test User 2",
            "loginid": "testuser2",
            "bu": self.bu,
            "peopletype": self.peopletype
        }
        json_form_data = {"userfor": "Web"}

        result = self.service.create_people(
            form_data, json_form_data, self.user, self.session
        )

        assert result.success is True
        assert People.objects.filter(peoplecode="TEST002").exists()

    def test_update_people_integration(self):
        """Test updating people with real database."""
        person = People.objects.create(
            peoplecode="TEST003",
            peoplename="Original Name",
            loginid="testuser3",
            bu=self.bu,
            peopletype=self.peopletype
        )

        form_data = {"peoplename": "Updated Name"}
        json_form_data = {}

        result = self.service.update_people(
            person.id, form_data, json_form_data, self.user, self.session
        )

        assert result.success is True
        person.refresh_from_db()
        assert person.peoplename == "Updated Name"

    def test_delete_people_integration(self):
        """Test soft delete with real database."""
        person = People.objects.create(
            peoplecode="TEST004",
            peoplename="To Delete",
            loginid="testuser4",
            bu=self.bu,
            peopletype=self.peopletype,
            enable=True
        )

        result = self.service.delete_people(person.id, self.user, self.session)

        assert result.success is True
        person.refresh_from_db()
        assert person.enable is False