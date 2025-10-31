"""People and attendance mobile sync service functions."""

from __future__ import annotations

import json
import logging
from typing import Dict, Iterable, List, Optional

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import DatabaseError, IntegrityError
from pydantic import ValidationError as PydanticValidationError

from apps.activity.models.attachment_model import Attachment
from apps.attendance.models import PeopleEventlog
from apps.peoples.models import People, Pgbelonging
from apps.service.pydantic_schemas.people_schema import (
    AttachmentSchema,
    PeopleEventLogHistorySchema,
    PeopleEventLogPunchInsSchema,
    PeopleModifiedAfterSchema,
    PgbelongingModifiedAfterSchema,
)

from .base import SyncResult, build_select_output

log = logging.getLogger("mobile_service_log")


def _materialise_records(queryset: Iterable[Dict[str, object]]) -> tuple[str, List[Dict[str, object]], int]:
    records_list = list(queryset)
    records_json = json.dumps(records_list, default=str)
    return records_json, records_list, len(records_list)


def _success_message(count: int) -> str:
    return f"Total {count} records fetched successfully!" if count else "No records"


def fetch_people_modified_after(*, mdtz: str, ctz_offset: int, bu_id: int) -> SyncResult:
    try:
        validated = PeopleModifiedAfterSchema(
            mdtz=mdtz,
            ctzoffset=ctz_offset,
            buid=bu_id,
        )

        data = People.objects.get_people_modified_after(
            mdtz=validated.mdtz,
            siteid=validated.buid,
        )

        records_json, records_list, count = _materialise_records(data)

        log.debug("fetch_people_modified_after -> %s rows", count)

        return build_select_output(
            records=records_list,
            record_type="people",
            message=_success_message(count),
            records_json=records_json,
            typed_records=records_list,
        )
    except PydanticValidationError as exc:
        log.error("People modified validation error", exc_info=True)
        raise DjangoValidationError(exc.errors()) from exc
    except People.DoesNotExist as exc:
        log.warning("People records not found")
        raise DjangoValidationError("People not found") from exc
    except (DatabaseError, IntegrityError):
        log.error("Database error during people sync", exc_info=True)
        raise


def fetch_people_event_log_punch_ins(*, date_for: str, bu_id: int, people_id: int) -> SyncResult:
    try:
        validated = PeopleEventLogPunchInsSchema(
            datefor=date_for,
            buid=bu_id,
            peopleid=people_id,
        )

        data = PeopleEventlog.objects.get_people_event_log_punch_ins(
            datefor=validated.datefor,
            buid=validated.buid,
            peopleid=validated.peopleid,
        )

        records_json, records_list, count = _materialise_records(data)

        log.debug("fetch_people_event_log_punch_ins -> %s rows", count)

        return build_select_output(
            records=records_list,
            record_type="peopleeventlog",
            message=_success_message(count),
            records_json=records_json,
            typed_records=records_list,
        )
    except PydanticValidationError as exc:
        log.error("People event log validation error", exc_info=True)
        raise DjangoValidationError(exc.errors()) from exc
    except PeopleEventlog.DoesNotExist as exc:
        log.warning("People event logs not found")
        raise DjangoValidationError("Event log not found") from exc
    except (DatabaseError, IntegrityError):
        log.error("Database error during people event log sync", exc_info=True)
        raise


def fetch_pgbelongings_modified_after(
    *, mdtz: str, ctz_offset: int, bu_id: int, people_id: int
) -> SyncResult:
    try:
        validated = PgbelongingModifiedAfterSchema(
            mdtz=mdtz,
            ctzoffset=ctz_offset,
            buid=bu_id,
            peopleid=people_id,
        )

        data = Pgbelonging.objects.get_modified_after(
            mdtz=validated.mdtz,
            peopleid=validated.peopleid,
            buid=validated.buid,
        )

        records_json, records_list, count = _materialise_records(data)

        log.debug("fetch_pgbelongings_modified_after -> %s rows", count)

        return build_select_output(
            records=records_list,
            record_type="pgbelonging",
            message=_success_message(count),
            records_json=records_json,
            typed_records=records_list,
        )
    except PydanticValidationError as exc:
        log.error("Pgbelonging validation error", exc_info=True)
        raise DjangoValidationError(exc.errors()) from exc
    except Pgbelonging.DoesNotExist as exc:
        log.warning("Pgbelonging records not found")
        raise DjangoValidationError("Business unit membership not found") from exc
    except (DatabaseError, IntegrityError):
        log.error("Database error during pgbelonging sync", exc_info=True)
        raise


def fetch_people_eventlog_history(
    *,
    mdtz: str,
    ctz_offset: int,
    people_id: int,
    bu_id: int,
    client_id: int,
    pevent_type_ids: List[int],
) -> SyncResult:
    try:
        validated = PeopleEventLogHistorySchema(
            mdtz=mdtz,
            ctzoffset=ctz_offset,
            peopleid=people_id,
            buid=bu_id,
            clientid=client_id,
            peventtypeid=pevent_type_ids,
        )

        data = PeopleEventlog.objects.get_peopleeventlog_history(
            mdtz=validated.mdtz,
            people_id=validated.peopleid,
            bu_id=validated.buid,
            client_id=validated.clientid,
            ctzoffset=validated.ctzoffset,
            peventtypeid=validated.peventtypeid,
        )

        records_json, records_list, count = _materialise_records(data)

        log.debug("fetch_people_eventlog_history -> %s rows", count)

        return build_select_output(
            records=records_list,
            record_type="peopleeventlog",
            message=_success_message(count),
            records_json=records_json,
            typed_records=records_list,
        )
    except PydanticValidationError as exc:
        log.error("People eventlog history validation error", exc_info=True)
        raise DjangoValidationError(exc.errors()) from exc
    except PeopleEventlog.DoesNotExist as exc:
        log.warning("People eventlog history not found")
        raise DjangoValidationError("Event log history not found") from exc
    except (DatabaseError, IntegrityError):
        log.error("Database error during people eventlog history sync", exc_info=True)
        raise


def fetch_attachments(*, owner: str) -> SyncResult:
    try:
        validated = AttachmentSchema(owner=owner)

        data = Attachment.objects.get_attachements_for_mob(
            ownerid=validated.owner
        )

        records_json, records_list, count = _materialise_records(data)

        log.debug("fetch_attachments -> %s rows", count)

        return build_select_output(
            records=records_list,
            record_type="attachment",
            message=_success_message(count),
            records_json=records_json,
            typed_records=records_list,
        )
    except PydanticValidationError as exc:
        log.error("Attachment validation error", exc_info=True)
        raise DjangoValidationError(exc.errors()) from exc
    except Attachment.DoesNotExist as exc:
        log.warning("Attachments not found")
        raise DjangoValidationError("Attachments not found") from exc
    except (DatabaseError, IntegrityError):
        log.error("Database error during attachment sync", exc_info=True)
        raise
