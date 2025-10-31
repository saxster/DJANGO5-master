"""Ticket mobile sync service functions."""

from __future__ import annotations

import logging
from typing import Optional

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import DatabaseError, IntegrityError
from pydantic import ValidationError as PydanticValidationError

from apps.core import utils
from apps.service.pydantic_schemas.ticket_schema import TicketSchema
from apps.y_helpdesk.models import Ticket

from .base import SyncResult, build_select_output

log = logging.getLogger("mobile_service_log")


def fetch_modified_tickets(
    *,
    people_id: int,
    mdtz: str,
    ctz_offset: int,
    bu_id: Optional[int] = None,
    client_id: Optional[int] = None,
) -> SyncResult:
    """Return modified tickets for mobile sync consumers."""

    try:
        filter_data = {
            "peopleid": people_id,
            "mdtz": mdtz,
            "ctzoffset": ctz_offset,
        }
        if bu_id is not None:
            filter_data["buid"] = bu_id
        if client_id is not None:
            filter_data["clientid"] = client_id
        validated = TicketSchema(**filter_data)

        data = Ticket.objects.get_tickets_for_mob(
            peopleid=validated.peopleid,
            buid=validated.buid,
            clientid=validated.clientid,
            mdtz=validated.mdtz,
            ctzoffset=validated.ctzoffset,
        )

        records_json, typed_records, count, msg, record_type = utils.get_select_output_typed(
            data, "ticket"
        )

        log.debug("fetch_modified_tickets -> %s rows", count)

        return build_select_output(
            records=typed_records,
            record_type=record_type,
            message=msg,
            records_json=records_json,
            typed_records=typed_records,
        )

    except PydanticValidationError as exc:
        log.error("Ticket sync validation error", exc_info=True)
        raise DjangoValidationError(exc.errors()) from exc
    except Ticket.DoesNotExist as exc:
        log.warning("Ticket sync returned no data")
        raise DjangoValidationError("Tickets not found") from exc
    except (DatabaseError, IntegrityError) as exc:
        log.error("Database error during ticket sync", exc_info=True)
        raise
