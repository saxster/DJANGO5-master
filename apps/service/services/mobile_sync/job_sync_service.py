"""Job mobile sync service functions."""

from __future__ import annotations

import json
import logging
from typing import Dict, Iterable

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import DatabaseError, IntegrityError
from pydantic import ValidationError as PydanticValidationError

from apps.activity.models.job_model import Jobneed, JobneedDetails
from apps.service.pydantic_schemas.job_schema import (
    ExternalTourModifiedAfterSchema,
    JobneedDetailsModifiedAfterSchema,
    JobneedModifiedAfterSchema,
)

from .base import SyncResult, build_select_output

log = logging.getLogger("mobile_service_log")


def _build_message(count: int) -> str:
    return f"Total {count} records fetched successfully!" if count else "No records"


def _materialise_records(queryset: Iterable[Dict[str, object]]) -> tuple[str, list[Dict[str, object]], int]:
    records_list = list(queryset)
    records_json = json.dumps(records_list, default=str)
    return records_json, records_list, len(records_list)


def fetch_jobneeds_modified_after(
    *, people_id: int, bu_id: int, client_id: int
) -> SyncResult:
    try:
        validated = JobneedModifiedAfterSchema(
            peopleid=people_id,
            buid=bu_id,
            clientid=client_id,
        )

        data = Jobneed.objects.get_job_needs(
            people_id=validated.peopleid,
            bu_id=validated.buid,
            client_id=validated.clientid,
        )

        records_json, records_list, count = _materialise_records(data)

        log.debug("fetch_jobneeds_modified_after -> %s rows", count)

        return build_select_output(
            records=records_list,
            record_type="jobneed",
            message=_build_message(count),
            records_json=records_json,
            typed_records=records_list,
        )
    except PydanticValidationError as exc:
        log.error("Jobneed sync validation error", exc_info=True)
        raise DjangoValidationError(exc.errors()) from exc
    except Jobneed.DoesNotExist as exc:
        log.warning("Jobneed data not found")
        raise DjangoValidationError("Job need not found") from exc
    except (DatabaseError, IntegrityError):
        log.error("Database error during jobneed sync", exc_info=True)
        raise


def fetch_jobneed_details_modified_after(*, jobneed_ids: str, ctz_offset: int) -> SyncResult:
    try:
        validated = JobneedDetailsModifiedAfterSchema(
            jobneedids=jobneed_ids,
            ctzoffset=ctz_offset,
        )

        data = JobneedDetails.objects.get_jndmodifiedafter(
            jobneedid=validated.jobneedids
        )

        records_json, records_list, count = _materialise_records(data)

        log.debug("fetch_jobneed_details_modified_after -> %s rows", count)

        return build_select_output(
            records=records_list,
            record_type="jobneeddetail",
            message=_build_message(count),
            records_json=records_json,
            typed_records=records_list,
        )
    except PydanticValidationError as exc:
        log.error("Jobneed detail validation error", exc_info=True)
        raise DjangoValidationError(exc.errors()) from exc
    except JobneedDetails.DoesNotExist as exc:
        log.warning("Jobneed details not found")
        raise DjangoValidationError("Job need details not found") from exc
    except (DatabaseError, IntegrityError):
        log.error("Database error during jobneed details sync", exc_info=True)
        raise


def fetch_external_tour_jobneeds(
    *, people_id: int, bu_id: int, client_id: int
) -> SyncResult:
    try:
        validated = ExternalTourModifiedAfterSchema(
            peopleid=people_id,
            buid=bu_id,
            clientid=client_id,
        )

        data = Jobneed.objects.get_external_tour_job_needs(
            people_id=validated.peopleid,
            bu_id=validated.buid,
            client_id=validated.clientid,
        )

        records_json, records_list, count = _materialise_records(data)

        log.debug("fetch_external_tour_jobneeds -> %s rows", count)

        return build_select_output(
            records=records_list,
            record_type="jobneed",
            message=_build_message(count),
            records_json=records_json,
            typed_records=records_list,
        )
    except PydanticValidationError as exc:
        log.error("External tour validation error", exc_info=True)
        raise DjangoValidationError(exc.errors()) from exc
    except Jobneed.DoesNotExist as exc:
        log.warning("External tour jobneeds not found")
        raise DjangoValidationError("External tour job needs not found") from exc
    except (DatabaseError, IntegrityError):
        log.error("Database error during external tour sync", exc_info=True)
        raise
