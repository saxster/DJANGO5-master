"""
Asset queries with fallback support for gradual migration.
This version allows switching between PostgreSQL and Django ORM implementations.
"""

import graphene
from apps.core import utils
from apps.activity.models.asset_model import Asset
from apps.service.types import SelectOutputType
from apps.service.inputs.asset_input import AssetFilterInput
from graphql.error import GraphQLError
from logging import getLogger
from apps.service.pydantic_schemas.asset_schema import AssetFilterSchema
from pydantic import ValidationError
import json
import os

log = getLogger("mobile_service_log")


class AssetQueriesWithFallback(graphene.ObjectType):
    """Asset queries with fallback to PostgreSQL functions during migration."""

    get_assetdetails = graphene.Field(
        SelectOutputType,
        mdtz=graphene.String(required=True, description="Modification timestamp"),
        ctzoffset=graphene.Int(required=True, description="Client timezone offset"),
        buid=graphene.Int(required=True, description="Business unit id"),
        description="Query to fetch asset details based on modification timestamp and business unit.",
    )

    @staticmethod
    def resolve_get_assetdetails(self, info, mdtz, ctzoffset, buid):
        try:
            log.info("request for get_assetdetails")
            # Create filter dict for validation
            filter_data = {
                'mdtz': mdtz,
                'ctzoffset': ctzoffset,
                'buid': buid
            }
            validated = AssetFilterSchema(**filter_data)
            mdtzinput = utils.getawaredatetime(
                dt=validated.mdtz, offset=validated.ctzoffset
            )
            
            # Feature flag to control which implementation to use
            use_django_orm = os.environ.get('USE_DJANGO_ORM_FOR_ASSETS', 'false').lower() == 'true'
            
            if use_django_orm:
                log.info("Using Django ORM implementation for asset details")
                # Use Django ORM implementation
                from apps.activity.managers.asset_manager_orm import AssetManagerORM
                
                # Get asset details using Django ORM
                assets = AssetManagerORM.get_asset_details(mdtzinput, validated.buid)
                
                # Convert to JSON format matching the original response
                data_json = json.dumps(assets, default=str)
                count = len(assets)
                
                log.info(f"{count} assets returned from Django ORM")
                
                return SelectOutputType(
                    records=data_json,
                    msg=f"Total {count} records fetched successfully!",
                    nrows=count,
                )
            else:
                log.info("Using Django ORM for asset details (PostgreSQL functions deprecated)")
                # Always use Django ORM now - PostgreSQL functions have been migrated
                from apps.activity.managers.asset_manager_orm import AssetManagerORM
                results = AssetManagerORM.get_asset_details(mdtzinput, validated.buid)
                data_json = json.dumps(results, default=str)
                count = len(results)
                return SelectOutputType(
                    records=data_json,
                    msg=f"Total {count} asset records fetched successfully!",
                    nrows=count,
                )
                
        except ValidationError as ve:
            log.error("Validation error in get_assetdetails", exc_info=True)
            raise GraphQLError(f"get_assetdetails failed: {str(ve)}")
        except Exception as e:
            log.error("Unexpected error in get_assetdetails", exc_info=True)
            # Log which implementation was being used when error occurred
            implementation = "Django ORM" if use_django_orm else "PostgreSQL"
            log.error(f"Error occurred while using {implementation} implementation")
            raise GraphQLError(f"get_assetdetails failed: {str(e)}")