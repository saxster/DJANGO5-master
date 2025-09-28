import graphene
from apps.activity.models.job_model import Jobneed, JobneedDetails
from apps.service.pydantic_schemas.job_schema import (
    JobneedModifiedAfterSchema,
    JobneedDetailsModifiedAfterSchema,
    ExternalTourModifiedAfterSchema,
)
from apps.service.types import SelectOutputType
from logging import getLogger
from apps.core import utils
from graphql import GraphQLError
from pydantic import ValidationError
from django.db import DatabaseError, IntegrityError
from django.core.exceptions import PermissionDenied
from apps.service.decorators import require_authentication, require_tenant_access

log = getLogger("mobile_service_log")


class JobQueries(graphene.ObjectType):
    get_jobneedmodifiedafter = graphene.Field(
        SelectOutputType, 
        peopleid=graphene.Int(required=True, description="People id"),
        buid=graphene.Int(required=True, description="Business unit id"),
        clientid=graphene.Int(required=True, description="Client id")
    )

    get_jndmodifiedafter = graphene.Field(
        SelectOutputType, 
        jobneedids=graphene.String(required=True, description="Job need ids"),
        ctzoffset=graphene.Int(required=True, description="Client timezone offset")
    )

    get_externaltourmodifiedafter = graphene.Field(
        SelectOutputType, 
        peopleid=graphene.Int(required=True, description="People id"),
        buid=graphene.Int(required=True, description="Business unit id"),
        clientid=graphene.Int(required=True, description="Client id")
    )

    @staticmethod
    @require_tenant_access
    def resolve_get_jobneedmodifiedafter(self, info, peopleid, buid, clientid):
        try:
            log.info("request for get_jobneedmodifiedafter")
            # Create filter dict for validation
            filter_data = {
                'peopleid': peopleid,
                'buid': buid,
                'clientid': clientid
            }
            validated = JobneedModifiedAfterSchema(**filter_data)
            data = Jobneed.objects.get_job_needs(
                people_id=validated.peopleid,
                bu_id=validated.buid,
                client_id=validated.clientid,
            )
            records, count, msg = utils.get_select_output(data)
            log.info(f"{count} objects returned...")
            return SelectOutputType(nrows=count, records=records, msg=msg)
        except ValidationError as ve:
            log.error("Validation error in get_jobneedmodifiedafter", exc_info=True)
            raise GraphQLError(f"Invalid input parameters: {str(ve)}")
        except Jobneed.DoesNotExist:
            log.warning("Job need not found in get_jobneedmodifiedafter")
            raise GraphQLError("Job need not found")
        except (DatabaseError, IntegrityError) as e:
            log.error("Database error in get_jobneedmodifiedafter", exc_info=True)
            raise GraphQLError("Database operation failed")

    @staticmethod
    @require_authentication
    def resolve_get_jndmodifiedafter(self, info, jobneedids, ctzoffset):
        try:
            log.info("request for get_jndmodifiedafter")
            # Create filter dict for validation
            filter_data = {
                'jobneedids': jobneedids,
                'ctzoffset': ctzoffset
            }
            validated = JobneedDetailsModifiedAfterSchema(**filter_data)
            data = JobneedDetails.objects.get_jndmodifiedafter(
                jobneedid=validated.jobneedids
            )
            records, count, msg = utils.get_select_output(data)
            log.info(f"{count} objects returned...")
            return SelectOutputType(nrows=count, records=records, msg=msg)
        except ValidationError as ve:
            log.error("Validation error in get_jndmodifiedafter", exc_info=True)
            raise GraphQLError(f"Invalid input parameters: {str(ve)}")
        except JobneedDetails.DoesNotExist:
            log.warning("Job need details not found")
            raise GraphQLError("Job need details not found")
        except (DatabaseError, IntegrityError) as e:
            log.error("Database error in get_jndmodifiedafter", exc_info=True)
            raise GraphQLError("Database operation failed")

    @staticmethod
    @require_tenant_access
    def resolve_get_externaltourmodifiedafter(self, info, peopleid, buid, clientid):
        try:
            log.info("request for get_externaltourmodifiedafter")
            # Create filter dict for validation
            filter_data = {
                'peopleid': peopleid,
                'buid': buid,
                'clientid': clientid
            }
            validated = ExternalTourModifiedAfterSchema(**filter_data)
            data = Jobneed.objects.get_external_tour_job_needs(
                people_id=validated.peopleid,
                bu_id=validated.buid,
                client_id=validated.clientid,
            )
            records, count, msg = utils.get_select_output(data)
            log.info(f"{count} objects returned...")
            return SelectOutputType(nrows=count, records=records, msg=msg)
        except ValidationError as ve:
            log.error("Validation error in get_externaltourmodifiedafter", exc_info=True)
            raise GraphQLError(f"Invalid input parameters: {str(ve)}")
        except Jobneed.DoesNotExist:
            log.warning("External tour not found")
            raise GraphQLError("External tour not found")
        except (DatabaseError, IntegrityError) as e:
            log.error("Database error in get_externaltourmodifiedafter", exc_info=True)
            raise GraphQLError("Database operation failed")
