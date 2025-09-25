import graphene
from apps.peoples.models import People, Pgbelonging, Pgroup
from apps.attendance.models import PeopleEventlog
from apps.activity.models.attachment_model import Attachment
from apps.service.pydantic_schemas.people_schema import (
    PeopleModifiedAfterSchema,
    PeopleEventLogPunchInsSchema,
    PgbelongingModifiedAfterSchema,
    PeopleEventLogHistorySchema,
    AttachmentSchema,
)
from graphql import GraphQLError
from apps.service.inputs.people_input import (
    PeopleModifiedAfterFilterInput,
    PeopleEventLogPunchInsFilterInput,
    PgbelongingModifiedAfterFilterInput,
    PeopleEventLogHistoryFilterInput,
    AttachmentFilterInput,
)
from apps.service.types import SelectOutputType
from apps.core import utils
from logging import getLogger
from pydantic import ValidationError

log = getLogger("mobile_service_log")


class PeopleQueries(graphene.ObjectType):
    get_peoplemodifiedafter = graphene.Field(
        SelectOutputType,
        mdtz=graphene.String(required=True, description="Modification timestamp"),
        ctzoffset=graphene.Int(required=True, description="Client timezone offset"),
        buid=graphene.Int(required=True, description="Business unit id"),
    )

    get_people_event_log_punch_ins = graphene.Field(
        SelectOutputType,
        datefor=graphene.String(required=True, description="Date for"),
        buid=graphene.Int(required=True, description="Business unit id"),
        peopleid=graphene.Int(required=True, description="People id"),
    )

    get_pgbelongingmodifiedafter = graphene.Field(
        SelectOutputType,
        mdtz=graphene.String(required=True, description="Modification timestamp"),
        ctzoffset=graphene.Int(required=True, description="Client timezone offset"),
        buid=graphene.Int(required=True, description="Business unit id"),
        peopleid=graphene.Int(required=True, description="People id"),
    )

    get_peopleeventlog_history = graphene.Field(
        SelectOutputType,
        mdtz=graphene.String(required=True, description="Modification timestamp"),
        ctzoffset=graphene.Int(required=True, description="Client timezone offset"),
        peopleid=graphene.Int(required=True, description="People id"),
        buid=graphene.Int(required=True, description="Business unit id"),
        clientid=graphene.Int(required=True, description="Client id"),
        peventtypeid=graphene.List(graphene.Int, required=True, description="Pevent type ids"),
    )

    get_attachments = graphene.Field(
        SelectOutputType, 
        owner=graphene.String(required=True, description="Owner")
    )

    @staticmethod
    def resolve_get_peoplemodifiedafter(self, info, mdtz, ctzoffset, buid):
        try:
            log.info("request for get_peoplemodifiedafter")
            # Create filter dict for validation
            filter_data = {
                'mdtz': mdtz,
                'ctzoffset': ctzoffset,
                'buid': buid
            }
            validated = PeopleModifiedAfterSchema(**filter_data)
            mdtzinput = utils.getawaredatetime(
                dt=validated.mdtz, offset=validated.ctzoffset
            )
            data = People.objects.get_people_modified_after(
                mdtz=mdtzinput, siteid=validated.buid
            )
            records, count, msg = utils.get_select_output(data)
            log.info(f"{count} objects returned...")
            return SelectOutputType(nrows=count, records=records, msg=msg)
        except ValidationError as ve:
            log.error("something went wrong", exc_info=True)
            raise GraphQLError(f"get_peoplemodifiedafter failed: {str(ve)}")
        except Exception as e:
            log.error("something went wrong", exc_info=True)
            raise GraphQLError(f"get_peoplemodifiedafter failed: {str(e)}")

    @staticmethod
    def resolve_get_people_event_log_punch_ins(self, info, datefor, buid, peopleid):
        try:
            log.info("request for get_people_event_log_punch_ins")
            # Create filter dict for validation
            filter_data = {
                'datefor': datefor,
                'buid': buid,
                'peopleid': peopleid
            }
            validated = PeopleEventLogPunchInsSchema(**filter_data)
            data = PeopleEventlog.objects.get_people_event_log_punch_ins(
                datefor=validated.datefor,
                buid=validated.buid,
                peopleid=validated.peopleid,
            )
            records, count, msg = utils.get_select_output(data)
            log.info(f"{count} objects returned...")
            return SelectOutputType(nrows=count, records=records, msg=msg)
        except ValidationError as ve:
            log.error("something went wrong", exc_info=True)
            raise GraphQLError(f"get_people_event_log_punch_ins failed: {str(ve)}")
        except Exception as e:
            log.error("something went wrong", exc_info=True)
            raise GraphQLError(f"get_people_event_log_punch_ins failed: {str(e)}")

    @staticmethod
    def resolve_get_pgbelongingmodifiedafter(self, info, mdtz, ctzoffset, buid, peopleid):
        try:
            log.info("request for get_pgbelongingmodifiedafter")
            # Create filter dict for validation
            filter_data = {
                'mdtz': mdtz,
                'ctzoffset': ctzoffset,
                'buid': buid,
                'peopleid': peopleid
            }
            validated = PgbelongingModifiedAfterSchema(**filter_data)
            mdtzinput = utils.getawaredatetime(
                dt=validated.mdtz, offset=validated.ctzoffset
            )
            data = Pgbelonging.objects.get_modified_after(
                mdtz=mdtzinput, peopleid=validated.peopleid, buid=validated.buid
            )
            records, count, msg = utils.get_select_output(data)
            log.info(f"{count} objects returned...")
            return SelectOutputType(nrows=count, records=records, msg=msg)
        except ValidationError as ve:
            log.error("something went wrong", exc_info=True)
            raise GraphQLError(f"get_pgbelongingmodifiedafter failed: {str(ve)}")
        except Exception as e:
            log.error("something went wrong", exc_info=True)
            raise GraphQLError(f"get_pgbelongingmodifiedafter failed: {str(e)}")

    @staticmethod
    def resolve_get_peopleeventlog_history(self, info, mdtz, ctzoffset, peopleid, buid, clientid, peventtypeid):
        try:
            log.info("request for get_peopleeventlog_history")
            # Create filter dict for validation
            filter_data = {
                'mdtz': mdtz,
                'ctzoffset': ctzoffset,
                'peopleid': peopleid,
                'buid': buid,
                'clientid': clientid,
                'peventtypeid': peventtypeid
            }
            validated = PeopleEventLogHistorySchema(**filter_data)
            mdtzinput = utils.getawaredatetime(
                dt=validated.mdtz, offset=validated.ctzoffset
            )
            data = PeopleEventlog.objects.get_peopleeventlog_history(
                mdtz=mdtzinput,
                people_id=validated.peopleid,
                bu_id=validated.buid,
                client_id=validated.clientid,
                ctzoffset=validated.ctzoffset,
                peventtypeid=validated.peventtypeid,
            )
            records, count, msg = utils.get_select_output(data)
            log.info(f"{count} objects returned...")
            return SelectOutputType(nrows=count, records=records, msg=msg)
        except ValidationError as ve:
            log.error("something went wrong", exc_info=True)
            raise GraphQLError(f"get_peopleeventlog_history failed: {str(ve)}")
        except Exception as e:
            log.error("something went wrong", exc_info=True)
            raise GraphQLError(f"get_peopleeventlog_history failed: {str(e)}")

    @staticmethod
    def resolve_get_attachments(self, info, owner):
        try:
            log.info("request for get_attachments")
            # Create filter dict for validation
            filter_data = {
                'owner': owner
            }
            validated = AttachmentSchema(**filter_data)
            data = Attachment.objects.get_attachements_for_mob(ownerid=validated.owner)
            records, count, msg = utils.get_select_output(data)
            log.info(f"{count} objects returned...")
            return SelectOutputType(nrows=count, records=records, msg=msg)
        except ValidationError as ve:
            log.error("something went wrong", exc_info=True)
            raise GraphQLError(f"get_attachments failed: {str(ve)}")
        except Exception as e:
            log.error("something went wrong", exc_info=True)
            raise GraphQLError(f"get_attachments failed: {str(e)}")
