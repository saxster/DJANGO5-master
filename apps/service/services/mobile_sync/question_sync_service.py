"""Question mobile sync service functions."""

from __future__ import annotations

import json
import logging
from typing import Dict, Iterable, Optional

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import DatabaseError, IntegrityError
from pydantic import ValidationError as PydanticValidationError
from apps.core.exceptions.patterns import DATABASE_EXCEPTIONS, PARSING_EXCEPTIONS

from apps.activity.models.question_model import (
    Question,
    QuestionSet,
    QuestionSetBelonging,
)
from apps.core import utils
from apps.service.pydantic_schemas.question_schema import (
    QuestionModifiedSchema,
    QuestionSetBelongingModifiedSchema,
    QuestionSetModifiedSchema,
)

from .base import SyncResult, build_select_output

log = logging.getLogger("mobile_service_log")


def _handle_pydantic_error(exc: PydanticValidationError) -> None:
    log.error("Question sync validation failure", exc_info=True)
    raise DjangoValidationError(exc.errors()) from exc


def fetch_questions_modified_after(
    *, mdtz: str, ctz_offset: int, client_id: int
) -> SyncResult:
    """Fetch question records modified after given timestamp."""

    try:
        validated = QuestionModifiedSchema(
            mdtz=mdtz,
            ctzoffset=ctz_offset,
            clientid=client_id,
        )

        data = Question.objects.get_questions_modified_after(
            mdtz=validated.mdtz, clientid=validated.clientid
        )

        records_json, typed_records, count, msg, record_type = utils.get_select_output_typed(
            data, "question"
        )

        log.debug("fetch_questions_modified_after -> %s rows", count)

        return build_select_output(
            records=typed_records,
            record_type=record_type,
            message=msg,
            records_json=records_json,
            typed_records=typed_records,
        )
    except PydanticValidationError as exc:
        _handle_pydantic_error(exc)
    except Question.DoesNotExist as exc:
        log.warning("Questions not found")
        raise DjangoValidationError("Questions not found") from exc
    except (DatabaseError, IntegrityError):
        log.error("Database error during question sync", exc_info=True)
        raise


def fetch_question_sets_modified_after(
    *, mdtz: str, ctz_offset: int, bu_id: int, client_id: int, people_id: int
) -> SyncResult:
    try:
        validated = QuestionSetModifiedSchema(
            mdtz=mdtz,
            ctzoffset=ctz_offset,
            buid=bu_id,
            clientid=client_id,
            peopleid=people_id,
        )

        data = QuestionSet.objects.get_qset_modified_after(
            mdtz=validated.mdtz,
            buid=validated.buid,
            clientid=validated.clientid,
            peopleid=validated.peopleid,
        )

        records_json, typed_records, count, msg, record_type = utils.get_select_output_typed(
            data, "questionset"
        )

        log.debug("fetch_question_sets_modified_after -> %s rows", count)

        return build_select_output(
            records=typed_records,
            record_type=record_type,
            message=msg,
            records_json=records_json,
            typed_records=typed_records,
        )
    except PydanticValidationError as exc:
        _handle_pydantic_error(exc)
    except QuestionSet.DoesNotExist as exc:
        log.warning("Question sets not found")
        raise DjangoValidationError("Question sets not found") from exc
    except (DatabaseError, IntegrityError):
        log.error("Database error during question set sync", exc_info=True)
        raise


def _enhance_with_dependency_logic(
    records: Iterable[Dict[str, object]],
) -> Iterable[Dict[str, object]]:
    """Enhance question records with dependency metadata."""

    data_list = list(records)
    log.info("Enhancing %s question records with dependency logic", len(data_list))

    qset_groups: Dict[int, list[Dict[str, object]]] = {}
    for record in data_list:
        qsb_id = record.get("qset_id")
        if qsb_id is None:
            continue
        qset_groups.setdefault(int(qsb_id), []).append(record)

    enhanced_records: list[Dict[str, object]] = []

    for group_qset_id, questions in qset_groups.items():
        try:
            logic_data = QuestionSetBelonging.objects.get_questions_with_logic(group_qset_id)
            dependency_map = logic_data.get("dependency_map", {})
            has_conditional_logic = logic_data.get("has_conditional_logic", False)

            clean_dependency_map = _make_json_safe_map(dependency_map)

            for question in questions:
                question["dependency_map"] = clean_dependency_map
                question["has_conditional_logic"] = bool(has_conditional_logic)
                enhanced_records.append(question)
        except (DATABASE_EXCEPTIONS, PARSING_EXCEPTIONS):
            log.warning(
                "Dependency processing failed for qset %s",
                group_qset_id,
                exc_info=True,
            )
            for question in questions:
                question["dependency_map"] = {}
                question["has_conditional_logic"] = False
                enhanced_records.append(question)

    return enhanced_records


def _make_json_safe_map(dependency_map: Dict[str, object]) -> Dict[str, object]:
    """Ensure dependency map is JSON serializable."""

    if not isinstance(dependency_map, dict):
        return {}

    clean_map: Dict[str, object] = {}
    for key, value in dependency_map.items():
        if isinstance(value, (dict, list, str, int, float, bool)) or value is None:
            clean_map[str(key)] = value
        elif isinstance(value, set):
            clean_map[str(key)] = list(value)
        else:
            clean_map[str(key)] = str(value)
    return clean_map


def fetch_question_set_belongings_modified_after(
    *,
    mdtz: str,
    ctz_offset: int,
    bu_id: int,
    client_id: int,
    people_id: int,
    include_dependency_logic: bool = False,
) -> SyncResult:
    try:
        validated = QuestionSetBelongingModifiedSchema(
            mdtz=mdtz,
            ctzoffset=ctz_offset,
            buid=bu_id,
            clientid=client_id,
            peopleid=people_id,
        )

        base_queryset = QuestionSetBelonging.objects.get_modified_after(
            mdtz=validated.mdtz,
            buid=validated.buid,
        )

        if include_dependency_logic:
            enhanced_records = _enhance_with_dependency_logic(base_queryset)
            records_json = json.dumps(enhanced_records, default=str)
            record_type = "questionset"
            msg = f"Total {len(enhanced_records)} records with conditional logic fetched successfully!"

            return build_select_output(
                records=enhanced_records,
                record_type=record_type,
                message=msg,
                records_json=records_json,
                typed_records=enhanced_records,
            )

        records_json, typed_records, count, msg, record_type = utils.get_select_output_typed(
            base_queryset, "questionset"
        )

        log.debug(
            "fetch_question_set_belongings_modified_after -> %s rows", count
        )

        return build_select_output(
            records=typed_records,
            record_type=record_type,
            message=msg,
            records_json=records_json,
            typed_records=typed_records,
        )

    except PydanticValidationError as exc:
        _handle_pydantic_error(exc)
    except QuestionSetBelonging.DoesNotExist as exc:
        log.warning("Question set belongings not found")
        raise DjangoValidationError("Question set belongings not found") from exc
    except (DatabaseError, IntegrityError):
        log.error("Database error during question belonging sync", exc_info=True)
        raise
    except (TypeError, KeyError, json.JSONDecodeError):
        log.error("Serialization error during question belonging sync", exc_info=True)
        raise


def fetch_question_set_with_logic(
    *, qset_id: int, client_id: int, bu_id: int
) -> SyncResult:
    try:
        logic_data = QuestionSetBelonging.objects.get_questions_with_logic(qset_id)

        record = {
            "questions": logic_data.get("questions", []),
            "dependency_map": logic_data.get("dependency_map", {}),
            "has_conditional_logic": logic_data.get("has_conditional_logic", False),
            "validation_warnings": logic_data.get("validation_warnings", []),
        }

        records = [record]
        records_json = json.dumps(records, default=str)
        msg = (
            f"Questionset {qset_id} with conditional logic retrieved successfully"
        )

        return build_select_output(
            records=records,
            record_type="questionset",
            message=msg,
            records_json=records_json,
            typed_records=records,
        )
    except QuestionSetBelonging.DoesNotExist as exc:
        log.warning("Questionset %s not found", qset_id)
        raise DjangoValidationError("Question set not found") from exc
    except (DatabaseError, IntegrityError):
        log.error("Database error during question logic fetch", exc_info=True)
        raise
    except (TypeError, KeyError, json.JSONDecodeError):
        log.error("Serialization error during question logic fetch", exc_info=True)
        raise
