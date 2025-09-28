"""
Tests for CapabilityManagementService.
"""

import pytest
from unittest.mock import Mock, patch
from django.test import TestCase
from django.db import IntegrityError

from apps.peoples.services.capability_management_service import (
    CapabilityManagementService,
    CapabilityOperationResult
)
from apps.peoples.models import Capability


@pytest.mark.unit
@pytest.mark.django_db
class TestCapabilityManagementService(TestCase):
    """Test CapabilityManagementService functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.service = CapabilityManagementService()
        self.mock_user = Mock()
        self.mock_user.id = 1
        self.session = {"bu_id": 1, "client_id": 1}

    @patch('apps.peoples.services.capability_management_service.Capability.objects')
    def test_get_capability_list(self, mock_cap_objects):
        """Test capability list retrieval."""
        mock_queryset = Mock()
        mock_queryset.values.return_value = [
            {"id": 1, "capscode": "CAP001", "capsname": "Test Capability"}
        ]
        mock_cap_objects.select_related.return_value.filter.return_value = mock_queryset

        result = self.service.get_capability_list(self.session)

        assert len(result) == 1
        assert result[0]["capscode"] == "CAP001"

    @patch('apps.peoples.services.capability_management_service.Capability')
    @patch('apps.peoples.services.capability_management_service.putils')
    def test_create_capability_success(self, mock_putils, mock_capability):
        """Test successful capability creation."""
        mock_instance = Mock()
        mock_instance.id = 1
        mock_instance.capscode = "CAP001"
        mock_capability.return_value = mock_instance

        form_data = {"capscode": "CAP001", "capsname": "Test"}

        result = self.service.create_capability(
            form_data, self.mock_user, self.session
        )

        assert result.success is True
        assert result.capability == mock_instance

    @patch('apps.peoples.services.capability_management_service.Capability')
    def test_create_capability_integrity_error(self, mock_capability):
        """Test capability creation with duplicate."""
        mock_capability.side_effect = IntegrityError("Duplicate")

        result = self.service.create_capability(
            {}, self.mock_user, self.session
        )

        assert result.success is False
        assert "already exists" in result.error_message