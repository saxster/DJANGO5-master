"""
Unit tests for AssetManagementService

Tests asset CRUD business logic extracted from views.

Following .claude/rules.md:
- Validates service layer separation (Rule 8)
- Tests specific exception handling (Rule 11)
- Verifies transaction management
"""

import pytest
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.contrib.gis.geos import Point
from unittest.mock import Mock, patch, MagicMock

from apps.activity.services import AssetManagementService, AssetOperationResult
from apps.activity.models.asset_model import Asset

User = get_user_model()


@pytest.mark.unit
class AssetManagementServiceTestCase(TestCase):
    """Test suite for AssetManagementService."""

    def setUp(self):
        """Set up test fixtures."""
        self.service = AssetManagementService()
        self.user = User.objects.create_user(
            loginid="testuser",
            peoplecode="TEST001",
            password="testpass123"
        )
        self.session = {
            'client_id': 1,
            'bu_id': 1,
            'sitecode': 'SITE001',
        }

    @patch('apps.activity.services.asset_service.putils.save_userinfo')
    @patch('apps.activity.services.asset_service.av_utils.save_assetjsonform_data')
    def test_create_asset_success(self, mock_save_json, mock_save_user):
        """Test successful asset creation."""
        asset_data = {
            'assetcode': 'ASSET001',
            'assetname': 'Test Asset',
            'gpslocation': Point(0, 0, srid=4326),
        }
        extras_data = {'custom_field': 'value'}

        mock_asset = Mock(spec=Asset)
        mock_asset.id = 1
        mock_save_json.return_value = True
        mock_save_user.return_value = mock_asset

        with patch.object(Asset, 'save'):
            with patch.object(self.service, '_trigger_quality_assessment'):
                result = self.service.create_asset(
                    asset_data, extras_data, self.user, self.session
                )

        self.assertTrue(result.success)
        self.assertEqual(result.asset_id, 1)

    @patch('apps.activity.services.asset_service.Asset')
    def test_create_asset_integrity_error(self, mock_asset_class):
        """Test asset creation with duplicate code."""
        from django.db import IntegrityError

        asset_data = {'assetcode': 'DUPLICATE'}
        extras_data = {}

        mock_instance = Mock()
        mock_instance.save.side_effect = IntegrityError("Duplicate key")
        mock_asset_class.return_value = mock_instance

        result = self.service.create_asset(
            asset_data, extras_data, self.user, self.session
        )

        self.assertFalse(result.success)
        self.assertIn("already exists", result.error_message)

    @patch('apps.activity.services.asset_service.Asset.objects.select_for_update')
    @patch('apps.activity.services.asset_service.putils.save_userinfo')
    def test_update_asset_success(self, mock_save_user, mock_select):
        """Test successful asset update."""
        asset_data = {
            'assetname': 'Updated Asset Name',
            'gpslocation': Point(1, 1, srid=4326),
        }
        extras_data = {}

        mock_asset = Mock(spec=Asset)
        mock_asset.id = 1
        mock_select.return_value.get.return_value = mock_asset
        mock_save_user.return_value = mock_asset

        with patch.object(self.service, '_trigger_quality_assessment'):
            result = self.service.update_asset(
                1, asset_data, extras_data, self.user, self.session
            )

        self.assertTrue(result.success)
        self.assertEqual(result.asset_id, 1)

    @patch('apps.activity.services.asset_service.Asset.objects.select_for_update')
    def test_update_asset_not_found(self, mock_select):
        """Test updating non-existent asset."""
        mock_select.return_value.get.side_effect = Asset.DoesNotExist()

        result = self.service.update_asset(
            999, {}, {}, self.user, self.session
        )

        self.assertFalse(result.success)
        self.assertEqual(result.error_message, "Asset not found")

    @patch('apps.activity.services.asset_service.Asset.objects.optimized_get_with_relations')
    def test_delete_asset_success(self, mock_get):
        """Test successful asset deletion."""
        mock_asset = Mock(spec=Asset)
        mock_asset.assetcode = 'ASSET001'
        mock_get.return_value = mock_asset

        result = self.service.delete_asset(1)

        self.assertTrue(result.success)
        mock_asset.delete.assert_called_once()

    @patch('apps.activity.services.asset_service.Asset.objects.optimized_get_with_relations')
    def test_delete_asset_not_found(self, mock_get):
        """Test deleting non-existent asset."""
        mock_get.side_effect = Asset.DoesNotExist()

        result = self.service.delete_asset(999)

        self.assertFalse(result.success)
        self.assertEqual(result.error_message, "Asset not found")

    @patch('apps.activity.services.asset_service.Asset.objects.optimized_get_with_relations')
    def test_delete_asset_with_dependencies(self, mock_get):
        """Test deleting asset with foreign key dependencies."""
        from django.db import IntegrityError

        mock_asset = Mock(spec=Asset)
        mock_asset.delete.side_effect = IntegrityError("Foreign key constraint")
        mock_get.return_value = mock_asset

        result = self.service.delete_asset(1)

        self.assertFalse(result.success)
        self.assertIn("referenced by other records", result.error_message)

    def test_trigger_quality_assessment_handles_import_error(self):
        """Test quality assessment gracefully handles missing module."""
        mock_asset = Mock()
        mock_asset.id = 1

        with patch('apps.activity.services.asset_service.assess_entity_quality', None):
            self.service._trigger_quality_assessment(mock_asset, is_new=True)

    def test_trigger_quality_assessment_handles_exception(self):
        """Test quality assessment handles task queue errors."""
        mock_asset = Mock()
        mock_asset.id = 1

        with patch('apps.activity.services.asset_service.assess_entity_quality') as mock_task:
            mock_task.delay.side_effect = Exception("Queue error")

            self.service._trigger_quality_assessment(mock_asset, is_new=True)


@pytest.mark.performance
class AssetManagementServicePerformanceTestCase(TestCase):
    """Performance tests for AssetManagementService."""

    def setUp(self):
        """Set up test fixtures."""
        self.service = AssetManagementService()

    def test_service_metrics_initialization(self):
        """Test service initializes metrics correctly."""
        self.assertEqual(self.service.service_name, "AssetManagementService")
        self.assertIsNotNone(self.service.metrics)
        self.assertEqual(self.service.metrics.call_count, 0)

    @pytest.mark.skip("Requires database setup")
    def test_create_asset_performance_monitoring(self):
        """Test that create_asset monitors performance."""
        pass