import graphene
from apps.y_helpdesk.models import Ticket
from apps.core import utils
from graphql import GraphQLError
from apps.service.inputs.ticket_input import TicketFilterInput
from pydantic import ValidationError
from apps.service.pydantic_schemas.ticket_schema import TicketSchema
from logging import getLogger
from apps.service.types import SelectOutputType

log = getLogger("mobile_service_log")


class TicketQueries(graphene.ObjectType):
    get_tickets = graphene.Field(
        SelectOutputType, 
        peopleid=graphene.Int(required=True, description="People id"),
        buid=graphene.Int(description="Bu id"),
        clientid=graphene.Int(description="Client id"),
        mdtz=graphene.String(required=True, description="Modification timestamp"),
        ctzoffset=graphene.Int(required=True, description="Client timezone offset")
    )

    @staticmethod
    def resolve_get_tickets(self, info, peopleid, mdtz, ctzoffset, buid=None, clientid=None):
        log.info("request for get_tickets")
        try:
            # Create filter dict for validation
            filter_data = {
                'peopleid': peopleid,
                'buid': buid,
                'clientid': clientid,
                'mdtz': mdtz,
                'ctzoffset': ctzoffset
            }
            validated = TicketSchema(**filter_data)
            data = Ticket.objects.get_tickets_for_mob(
                peopleid=validated.peopleid,
                buid=validated.buid,
                clientid=validated.clientid,
                mdtz=validated.mdtz,
                ctzoffset=validated.ctzoffset,
            )
            records, count, msg = utils.get_select_output(data)
            log.info(f"{count} objects returned...")
            return SelectOutputType(nrows=count, records=records, msg=msg)
        except ValidationError as ve:
            log.error("something went wrong", exc_info=True)
            raise GraphQLError(f"get_tickets failed: {str(ve)}")
        except Exception as e:
            log.error("something went wrong", exc_info=True)
            raise GraphQLError("something went wrong")
