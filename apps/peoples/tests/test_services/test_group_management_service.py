"""
Tests for GroupManagementService.
"""

import pytest
from unittest.mock import Mock, patch
from django.test import TestCase
from django.db import IntegrityError

from apps.peoples.services.group_management_service import (
    GroupManagementService,
    GroupOperationResult
)
from apps.peoples.models import Pgroup, Pgbelonging


@pytest.mark.unit
@pytest.mark.django_db
class TestGroupManagementService(TestCase):
    """Test GroupManagementService functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.service = GroupManagementService()
        self.mock_user = Mock()
        self.mock_user.id = 1
        self.session = {"bu_id": 1, "client_id": 1, "tenantid": 1}

    @patch('apps.peoples.services.group_management_service.Pgroup.objects')
    def test_get_group_list(self, mock_group_objects):
        """Test group list retrieval."""
        mock_queryset = Mock()
        mock_queryset.values.return_value.order_by.return_value = [
            {"id": 1, "groupname": "Test Group"}
        ]
        mock_group_objects.select_related.return_value.filter.return_value = mock_queryset

        result = self.service.get_group_list(self.session)

        assert len(result) == 1

    @patch('apps.peoples.services.group_management_service.Pgroup')
    @patch('apps.peoples.services.group_management_service.putils')
    @patch.object(GroupManagementService, '_save_group_memberships')
    def test_create_group_success(self, mock_save_members, mock_putils, mock_group):
        """Test successful group creation."""
        mock_instance = Mock()
        mock_instance.id = 1
        mock_instance.groupname = "Test Group"
        mock_group.return_value = mock_instance

        result = self.service.create_group(
            {"groupname": "Test Group"},
            [1, 2, 3],
            self.mock_user,
            self.session
        )

        assert result.success is True
        mock_save_members.assert_called_once()

    @patch('apps.peoples.services.group_management_service.Pgbelonging.objects')
    def test_get_group_members(self, mock_belonging_objects):
        """Test retrieving group members."""
        mock_belonging_objects.filter.return_value.values_list.return_value = [1, 2, 3]

        members = self.service.get_group_members(1)

        assert members == [1, 2, 3]