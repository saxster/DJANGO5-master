"""
Asset Management Service

Centralizes asset business logic extracted from views.

Following .claude/rules.md:
- Service layer pattern (Rule 8)
- Specific exception handling (Rule 11)
- Database query optimization (Rule 12)
- Business logic separation from views
"""

import logging
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from django.db import IntegrityError, transaction
from django.core.exceptions import ValidationError, PermissionDenied
from apps.core.services.base_service import BaseService
from apps.core.error_handling import ErrorHandler
from apps.core.exceptions import BusinessLogicException, DatabaseException
from apps.core.utils_new.db_utils import get_current_db_name
from apps.activity.models.asset_model import Asset
from apps.activity.models.location_model import Location
import apps.peoples.utils as putils
import apps.activity.utils as av_utils

logger = logging.getLogger(__name__)

__all__ = [
    'AssetManagementService',
    'AssetOperationResult',
]


@dataclass
class AssetOperationResult:
    """Result of asset operations."""
    success: bool
    asset: Optional[Asset] = None
    asset_id: Optional[int] = None
    message: Optional[str] = None
    error_message: Optional[str] = None
    correlation_id: Optional[str] = None


class AssetManagementService(BaseService):
    """
    Service for asset CRUD operations.

    Extracted from apps/activity/views/asset/crud_views.py to separate
    business logic from HTTP handling.
    """

    def get_service_name(self) -> str:
        return "AssetManagementService"

    @BaseService.monitor_performance("create_asset")
    def create_asset(
        self,
        asset_data: Dict[str, Any],
        extras_data: Dict[str, Any],
        user,
        session: Dict[str, Any]
    ) -> AssetOperationResult:
        """
        Create new asset with extras/metadata.

        Args:
            asset_data: Asset form cleaned data
            extras_data: Asset extras form cleaned data
            user: User creating the asset
            session: Request session data

        Returns:
            AssetOperationResult with created asset
        """
        try:
            with self.database_transaction():
                asset = Asset(**asset_data)
                asset.gpslocation = asset_data.get("gpslocation")
                asset.save()

                if av_utils.save_assetjsonform_data(extras_data, asset):
                    asset = putils.save_userinfo(
                        asset, user, session, create=True
                    )

                self._trigger_quality_assessment(asset, is_new=True)

                return AssetOperationResult(
                    success=True,
                    asset=asset,
                    asset_id=asset.id,
                    message="Asset created successfully"
                )

        except IntegrityError as e:
            logger.error(f"Asset creation integrity error: {e}")
            return AssetOperationResult(
                success=False,
                error_message="Asset with this code already exists"
            )
        except ValidationError as e:
            logger.warning(f"Asset creation validation error: {e}")
            return AssetOperationResult(
                success=False,
                error_message=str(e)
            )

    @BaseService.monitor_performance("update_asset")
    def update_asset(
        self,
        asset_id: int,
        asset_data: Dict[str, Any],
        extras_data: Dict[str, Any],
        user,
        session: Dict[str, Any]
    ) -> AssetOperationResult:
        """
        Update existing asset.

        Args:
            asset_id: ID of asset to update
            asset_data: Asset form cleaned data
            extras_data: Asset extras form cleaned data
            user: User updating the asset
            session: Request session data

        Returns:
            AssetOperationResult with updated asset
        """
        try:
            with self.database_transaction():
                asset = Asset.objects.select_for_update().get(pk=asset_id)

                for field, value in asset_data.items():
                    if field != 'pk':
                        setattr(asset, field, value)

                asset.gpslocation = asset_data.get("gpslocation")
                asset.save()

                if av_utils.save_assetjsonform_data(extras_data, asset):
                    asset = putils.save_userinfo(
                        asset, user, session, create=False
                    )

                self._trigger_quality_assessment(asset, is_new=False)

                return AssetOperationResult(
                    success=True,
                    asset=asset,
                    asset_id=asset.id,
                    message="Asset updated successfully"
                )

        except Asset.DoesNotExist as e:
            logger.error(f"Asset {asset_id} not found for update")
            return AssetOperationResult(
                success=False,
                error_message="Asset not found"
            )
        except IntegrityError as e:
            logger.error(f"Asset update integrity error: {e}")
            return AssetOperationResult(
                success=False,
                error_message="Asset code conflict"
            )

    @BaseService.monitor_performance("delete_asset")
    def delete_asset(self, asset_id: int) -> AssetOperationResult:
        """
        Delete asset with dependency checking.

        Args:
            asset_id: ID of asset to delete

        Returns:
            AssetOperationResult with deletion status
        """
        try:
            with self.database_transaction():
                asset = Asset.objects.optimized_get_with_relations(asset_id)
                asset_code = asset.assetcode
                asset.delete()

                logger.info(f"Asset deleted successfully: {asset_code}")

                return AssetOperationResult(
                    success=True,
                    message=f"Asset {asset_code} deleted successfully"
                )

        except Asset.DoesNotExist:
            logger.error(f"Asset {asset_id} not found for deletion")
            return AssetOperationResult(
                success=False,
                error_message="Asset not found"
            )
        except IntegrityError as e:
            logger.error(f"Cannot delete asset due to dependencies: {e}")
            return AssetOperationResult(
                success=False,
                error_message="Cannot delete asset - it is referenced by other records"
            )

    def _trigger_quality_assessment(self, asset: Asset, is_new: bool = False):
        """
        Trigger quality assessment for asset asynchronously.

        Args:
            asset: Asset instance
            is_new: Whether this is a new asset
        """
        try:
            from apps.quality_assurance.tasks import assess_entity_quality

            assess_entity_quality.delay(
                entity_type='ASSET',
                entity_id=asset.id,
                force_reassessment=not is_new
            )

        except ImportError:
            logger.debug("Quality assurance module not available")
        except (DatabaseError, IntegrityError, ObjectDoesNotExist, TypeError, ValidationError, ValueError) as e:
            logger.warning(
                f"Failed to trigger quality assessment for asset {asset.id}: {e}"
            )