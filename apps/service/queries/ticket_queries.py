import graphene
from apps.y_helpdesk.models import Ticket
from apps.core import utils
from graphql import GraphQLError
from pydantic import ValidationError
from django.db import DatabaseError, IntegrityError
from django.core.exceptions import PermissionDenied
from apps.service.pydantic_schemas.ticket_schema import TicketSchema
from logging import getLogger
from apps.service.types import SelectOutputType
from apps.service.decorators import require_authentication, require_tenant_access

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
    @require_authentication
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
            log.error("Validation error in get_tickets", exc_info=True)
            raise GraphQLError(f"Invalid input parameters: {str(ve)}")
        except Ticket.DoesNotExist:
            log.warning("Tickets not found in get_tickets")
            raise GraphQLError("Tickets not found")
        except (DatabaseError, IntegrityError) as e:
            log.error("Database error in get_tickets", exc_info=True)
            raise GraphQLError("Database operation failed")
