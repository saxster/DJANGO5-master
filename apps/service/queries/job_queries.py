import graphene
from apps.activity.models.job_model import Jobneed, JobneedDetails
from apps.service.pydantic_schemas.job_schema import (
    JobneedModifiedAfterSchema,
    JobneedDetailsModifiedAfterSchema,
    ExternalTourModifiedAfterSchema,
)
from apps.service.inputs.job_input import (
    JobneedModifiedAfterInput,
    JobneedDetailsModifiedAfterInput,
    ExternalTourModifiedAfterInput,
)
from apps.service.types import SelectOutputType
from logging import getLogger
from apps.core import utils
from graphql import GraphQLError
from pydantic import ValidationError

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
            log.error("something went wrong", exc_info=True)
            raise GraphQLError(f"get_jobneedmodifiedafter failed: {str(ve)}")
        except Exception as e:
            log.error("something went wrong", exc_info=True)
            raise GraphQLError(f"get_jobneedmodifiedafter failed: {str(e)}")

    @staticmethod
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
            log.error("something went wrong", exc_info=True)
            raise GraphQLError(f"get_jndmodifiedafter failed: {str(ve)}")
        except Exception as e:
            log.error("something went wrong", exc_info=True)
            raise GraphQLError(f"get_jndmodifiedafter failed: {str(e)}")

    @staticmethod
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
            log.error("something went wrong", exc_info=True)
            raise GraphQLError(f"get_externaltourmodifiedafter failed: {str(ve)}")
        except Exception as e:
            log.error("something went wrong", exc_info=True)
            raise GraphQLError(f"get_externaltourmodifiedafter failed: {str(e)}")
