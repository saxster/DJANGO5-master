import graphene
from apps.onboarding.models import TypeAssist
from apps.service.types import SelectOutputType
from apps.core import utils
from logging import getLogger
from pydantic import ValidationError
from django.db import DatabaseError, IntegrityError
from django.core.exceptions import PermissionDenied
from apps.service.pydantic_schemas.typeassist_schema import (
    TypeAssistModifiedFilterSchema,
)
from graphql import GraphQLError
from apps.service.decorators import require_authentication, require_tenant_access

log = getLogger("mobile_service_log")


class TypeAssistQueries(graphene.ObjectType):
    get_typeassistmodifiedafter = graphene.Field(
        SelectOutputType, 
        mdtz=graphene.String(required=True, description="Modification timestamp"),
        ctzoffset=graphene.Int(required=True, description="Client timezone offset"),
        clientid=graphene.Int(required=True, description="Client id")
    )

    @staticmethod
    @require_tenant_access
    def resolve_get_typeassistmodifiedafter(self, info, mdtz, ctzoffset, clientid):
        try:
            log.info("request for get_typeassistmodifiedafter")
            # Create filter dict for validation
            filter_data = {
                'mdtz': mdtz,
                'ctzoffset': ctzoffset,
                'clientid': clientid
            }
            validated = TypeAssistModifiedFilterSchema(**filter_data)
            mdtzinput = utils.getawaredatetime(
                dt=validated.mdtz, offset=validated.ctzoffset
            )
            data = TypeAssist.objects.get_typeassist_modified_after(
                mdtz=mdtzinput, clientid=validated.clientid
            )
            records, count, msg = utils.get_select_output(data)
            log.info(f"{count} objects returned...")
            return SelectOutputType(nrows=count, records=records, msg=msg)
        except ValidationError as ve:
            log.error("Validation error in get_typeassistmodifiedafter", exc_info=True)
            raise GraphQLError(f"Invalid input parameters: {str(ve)}")
        except TypeAssist.DoesNotExist:
            log.warning("TypeAssist records not found")
            raise GraphQLError("TypeAssist records not found")
        except (DatabaseError, IntegrityError) as e:
            log.error("Database error in get_typeassistmodifiedafter", exc_info=True)
            raise GraphQLError("Database operation failed")
