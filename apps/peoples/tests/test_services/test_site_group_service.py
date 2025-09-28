"""
Tests for SiteGroupManagementService.
"""

import pytest
from unittest.mock import Mock, patch
from django.test import TestCase

from apps.peoples.services.site_group_management_service import (
    SiteGroupManagementService,
    SiteGroupOperationResult
)
from apps.peoples.models import Pgroup


@pytest.mark.unit
@pytest.mark.django_db
class TestSiteGroupManagementService(TestCase):
    """Test SiteGroupManagementService functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.service = SiteGroupManagementService()
        self.mock_user = Mock()
        self.mock_user.id = 1
        self.session = {"bu_id": 1, "client_id": 1, "tenantid": 1}

    @patch('apps.peoples.services.site_group_management_service.Pgroup.objects')
    def test_get_site_group_list(self, mock_group_objects):
        """Test site group list retrieval."""
        mock_group_objects.list_view_sitegrp.return_value = (100, 100, [])

        result = self.service.get_site_group_list({}, self.session)

        assert result["recordsTotal"] == 100

    @patch.object(SiteGroupManagementService, '_save_assigned_sites')
    @patch('apps.peoples.services.site_group_management_service.Pgroup')
    @patch('apps.peoples.services.site_group_management_service.putils')
    def test_create_site_group_success(self, mock_putils, mock_group, mock_save):
        """Test successful site group creation."""
        mock_instance = Mock()
        mock_instance.id = 1
        mock_instance.pk = 1
        mock_instance.groupname = "Test Site Group"
        mock_instance.enable = True
        mock_group.return_value = mock_instance

        result = self.service.create_site_group(
            {"groupname": "Test Site Group"},
            [{"buid": 1}, {"buid": 2}],
            self.mock_user,
            self.session
        )

        assert result.success is True
        mock_save.assert_called_once()

    @patch('apps.peoples.services.site_group_management_service.Pgbelonging.objects')
    def test_get_assigned_sites(self, mock_belonging_objects):
        """Test retrieving assigned sites."""
        mock_belonging_objects.get_assigned_sitesto_sitegrp.return_value = [
            {"buid": 1, "buname": "Site 1"}
        ]

        sites = self.service.get_assigned_sites(1)

        assert len(sites) == 1