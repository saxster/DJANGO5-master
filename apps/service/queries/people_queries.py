import graphene
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
from apps.service.types import SelectOutputType
from apps.core import utils
from logging import getLogger
from pydantic import ValidationError
from django.db import DatabaseError, IntegrityError
from django.core.exceptions import PermissionDenied
from apps.peoples.models import People, Pgbelonging
from apps.service.decorators import require_authentication, require_tenant_access

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
    @require_tenant_access
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
            log.error("Validation error in get_peoplemodifiedafter", exc_info=True)
            raise GraphQLError(f"Invalid input parameters: {str(ve)}")
        except People.DoesNotExist as e:
            log.warning(f"People not found in get_peoplemodifiedafter", exc_info=True)
            raise GraphQLError("Requested people data not found")
        except (DatabaseError, IntegrityError) as e:
            log.error("Database error in get_peoplemodifiedafter", exc_info=True)
            raise GraphQLError("Database operation failed")

    @staticmethod
    @require_tenant_access
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
            log.error("Validation error in get_people_event_log_punch_ins", exc_info=True)
            raise GraphQLError(f"Invalid input parameters: {str(ve)}")
        except PeopleEventlog.DoesNotExist:
            log.warning("Event log not found in get_people_event_log_punch_ins")
            raise GraphQLError("Event log not found")
        except (DatabaseError, IntegrityError) as e:
            log.error("Database error in get_people_event_log_punch_ins", exc_info=True)
            raise GraphQLError("Database operation failed")

    @staticmethod
    @require_tenant_access
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
            log.error("Validation error in get_pgbelongingmodifiedafter", exc_info=True)
            raise GraphQLError(f"Invalid input parameters: {str(ve)}")
        except Pgbelonging.DoesNotExist:
            log.warning("Pgbelonging not found in get_pgbelongingmodifiedafter")
            raise GraphQLError("Business unit membership not found")
        except (DatabaseError, IntegrityError) as e:
            log.error("Database error in get_pgbelongingmodifiedafter", exc_info=True)
            raise GraphQLError("Database operation failed")

    @staticmethod
    @require_tenant_access
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
            log.error("Validation error in get_peopleeventlog_history", exc_info=True)
            raise GraphQLError(f"Invalid input parameters: {str(ve)}")
        except PeopleEventlog.DoesNotExist:
            log.warning("Event log history not found")
            raise GraphQLError("Event log history not found")
        except (DatabaseError, IntegrityError) as e:
            log.error("Database error in get_peopleeventlog_history", exc_info=True)
            raise GraphQLError("Database operation failed")

    @staticmethod
    @require_authentication
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
            log.error("Validation error in get_attachments", exc_info=True)
            raise GraphQLError(f"Invalid input parameters: {str(ve)}")
        except Attachment.DoesNotExist:
            log.warning("Attachments not found")
            raise GraphQLError("Attachments not found")
        except (DatabaseError, IntegrityError) as e:
            log.error("Database error in get_attachments", exc_info=True)
            raise GraphQLError("Database operation failed")
