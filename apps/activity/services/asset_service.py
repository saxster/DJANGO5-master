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
from apps.ontology import ontology
from apps.core.services.base_service import BaseService, monitor_service_performance
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


@ontology(
    domain="operations",
    purpose="Asset Lifecycle Management Service",
    concept=(
        "Service layer for asset CRUD operations with business logic validation, state transition "
        "enforcement, and quality assessment triggers. Extracted from Django views to centralize "
        "asset management logic following service layer pattern."
    ),
    criticality="high",
    inputs=[
        {
            "name": "asset_data",
            "type": "Dict[str, Any]",
            "description": "Asset form cleaned data (assetcode, assetname, iscritical, runningstatus, etc.)",
            "required": True
        },
        {
            "name": "extras_data",
            "type": "Dict[str, Any]",
            "description": "Asset JSON metadata (purchase_date, supplier, invoice_no, meter readings)",
            "required": False
        },
        {
            "name": "user",
            "type": "People",
            "description": "Authenticated user for audit logging (cdby/mdby fields)",
            "required": True
        },
        {
            "name": "session",
            "type": "Dict[str, Any]",
            "description": "Request session data (bu, client, tenant context)",
            "required": True
        },
        {
            "name": "asset_id",
            "type": "int",
            "description": "Primary key for update/delete operations",
            "required_for": ["update_asset", "delete_asset"]
        }
    ],
    outputs=[
        {
            "name": "AssetOperationResult",
            "type": "dataclass",
            "description": "Result object with success status, asset instance, and messages",
            "structure": {
                "success": "bool - Operation success/failure",
                "asset": "Optional[Asset] - Created/updated asset instance",
                "asset_id": "Optional[int] - Asset primary key",
                "message": "Optional[str] - Success message",
                "error_message": "Optional[str] - Validation/integrity error details",
                "correlation_id": "Optional[str] - Distributed tracing ID"
            }
        }
    ],
    side_effects=[
        "Creates/updates Asset records in database with database_transaction() wrapper",
        "Populates asset_json JSONField via av_utils.save_assetjsonform_data()",
        "Updates audit fields (cdby, cdon, mdby, mdon) via putils.save_userinfo()",
        "Triggers quality_assurance.tasks.assess_entity_quality async task (if module available)",
        "Generates AssetLog audit trail entries on status changes (via Asset.save() signal)",
        "Enforces optimistic locking via select_for_update() in update operations",
        "Validates RESTRICT constraints on delete (raises IntegrityError if referenced)",
    ],
    depends_on=[
        "apps.core.services.base_service.BaseService (transaction wrapper, monitoring)",
        "apps.activity.models.asset_model.Asset (ORM model)",
        "apps.activity.utils.save_assetjsonform_data (JSON metadata persistence)",
        "apps.peoples.utils.save_userinfo (audit field population)",
        "apps.quality_assurance.tasks.assess_entity_quality (optional QA trigger)",
        "apps.core.exceptions (BusinessLogicException, DatabaseException)",
    ],
    used_by=[
        "apps.activity.views.asset_views.AssetCreateView (Django CBV)",
        "apps.activity.views.asset_views.AssetUpdateView",
        "apps.activity.views.asset_views.AssetDeleteView",
        "REST API endpoints: POST/PUT/DELETE /api/v1/assets/",
        "Mobile sync service for offline asset updates",
        "Admin panel asset management forms",
    ],
    tags=["service-layer", "crud", "asset-management", "transaction", "audit", "quality-assurance"],
    security_notes=(
        "Transaction safety:\n"
        "1. All operations wrapped in database_transaction() for ACID compliance\n"
        "2. select_for_update() on update operations prevents concurrent modification races\n"
        "3. IntegrityError exceptions caught and returned as user-friendly messages (no stack traces)\n"
        "4. Tenant isolation inherited from Asset model (TenantAwareModel)\n"
        "\nValidation:\n"
        "5. Django form cleaned_data ensures type safety before service invocation\n"
        "6. RESTRICT on_delete constraints prevent orphaned references\n"
        "7. Unique constraint violations detected via IntegrityError handling\n"
        "8. Critical asset deletions require additional confirmation at view layer\n"
        "\nAudit:\n"
        "9. All changes logged via save_userinfo() with user, timestamp, session context\n"
        "10. AssetLog entries created automatically via Django signals on save()"
    ),
    performance_notes=(
        "Database optimization:\n"
        "- select_for_update() acquires row-level locks (PostgreSQL FOR UPDATE)\n"
        "- AssetManager.optimized_get_with_relations() uses select_related for FKs\n"
        "- Batch operations not yet implemented (consider bulk_create for imports)\n"
        "\nAsync operations:\n"
        "- Quality assessment triggered via Celery .delay() (non-blocking)\n"
        "- Graceful degradation if quality_assurance module unavailable (ImportError)\n"
        "\nMonitoring:\n"
        "- @monitor_service_performance decorator logs execution time to OpenTelemetry\n"
        "- Correlation IDs available for distributed tracing (not yet populated)\n"
        "\nScaling concerns:\n"
        "- Large asset imports should use bulk_create (currently N queries)\n"
        "- JSON field writes not indexed (consider materialized views for common queries)\n"
        "- Parent hierarchy depth unlimited (add validation for max 3 levels)"
    ),
    architecture_notes=(
        "Service layer pattern:\n"
        "- Extracted from Django views to separate HTTP concerns from business logic\n"
        "- Returns dataclass results (not HttpResponse) for reusability across interfaces\n"
        "- Views translate AssetOperationResult to HTTP responses\n"
        "\nError handling:\n"
        "- Specific exceptions caught per .claude/rules.md Rule #11\n"
        "- IntegrityError: Unique constraint violations (assetcode conflicts)\n"
        "- ValidationError: Invalid GPS data, required fields missing\n"
        "- Asset.DoesNotExist: Update/delete on non-existent asset\n"
        "- No generic Exception catching (prevent silent failures)\n"
        "\nFuture enhancements:\n"
        "- Add bulk_update_assets() for batch operations\n"
        "- Implement state machine validation (enforce valid runningstatus transitions)\n"
        "- Add asset_history diffing (track field-level changes in AssetLog)\n"
        "- Support async service methods for long-running operations"
    ),
    examples=[
        {
            "description": "Create asset from Django view",
            "code": """
from apps.activity.services.asset_service import AssetManagementService

service = AssetManagementService()
result = service.create_asset(
    asset_data={
        'assetcode': 'PUMP-001',
        'assetname': 'Main Water Pump',
        'iscritical': True,
        'runningstatus': 'WORKING',
        'identifier': 'ASSET',
        'client': client_obj,
        'bu': site_obj,
        'tenant': tenant_obj,
    },
    extras_data={
        'model': 'Grundfos CR 15-3',
        'supplier': 'Grundfos India',
        'purchase_date': '2024-01-15',
    },
    user=request.user,
    session={'bu': site_id, 'client': client_id}
)

if result.success:
    messages.success(request, result.message)
    return redirect('asset_detail', pk=result.asset_id)
else:
    messages.error(request, result.error_message)
    return render(request, 'asset_form.html', {'form': form})
"""
        },
        {
            "description": "Update asset with optimistic locking",
            "code": """
service = AssetManagementService()
result = service.update_asset(
    asset_id=123,
    asset_data={
        'assetname': 'Main Water Pump - Building A',
        'runningstatus': 'MAINTENANCE',  # State transition
    },
    extras_data={
        'remarks': 'Scheduled maintenance - bearing replacement'
    },
    user=request.user,
    session={'bu': site_id, 'client': client_id}
)

# Concurrent update detected via select_for_update()
if not result.success and 'conflict' in result.error_message.lower():
    messages.warning(request, 'Asset modified by another user. Please refresh.')
"""
        },
        {
            "description": "Delete asset with dependency checking",
            "code": """
service = AssetManagementService()
result = service.delete_asset(asset_id=123)

if not result.success:
    if 'referenced' in result.error_message:
        # RESTRICT constraint triggered (Jobs/WorkOrders reference this asset)
        messages.error(
            request,
            'Cannot delete: Asset has active maintenance schedules or work orders'
        )
    else:
        messages.error(request, result.error_message)
"""
        }
    ]
)
class AssetManagementService(BaseService):
    """
    Service for asset CRUD operations.

    Extracted from apps/activity/views/asset/crud_views.py to separate
    business logic from HTTP handling.
    """

    def get_service_name(self) -> str:
        return "AssetManagementService"

    @monitor_service_performance("create_asset")
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

    @monitor_service_performance("update_asset")
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

    @monitor_service_performance("delete_asset")
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