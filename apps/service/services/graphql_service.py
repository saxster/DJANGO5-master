"""
GraphQL Service Module

Handles GraphQL mutation operations for reports, ADHOC tasks, and file-based workflows.
Extracted from apps/service/utils.py for improved organization and maintainability.

Migration Date: 2025-09-30
Original File: apps/service/utils.py (lines 924-1683)

Functions:
- call_service_based_on_filename: Route file uploads to appropriate handlers
- perform_reportmutation: Celery task for report (site/incident) processing
- perform_adhocmutation: Celery task for ADHOC task reconciliation
- execute_graphql_mutations: Execute GraphQL mutations with error handling

Features:
- File-based routing (insertRecord.gz, updateTaskTour.gz, uploadReport.gz, adhocRecord.gz)
- Complex parent-child hierarchies for reports
- Work permit PDF generation and approval workflows
- Asset lookup and correction for ADHOC tasks
"""
import json
import traceback as tb
from logging import getLogger
from pprint import pformat

from django.db import transaction
from django.db.utils import DatabaseError, IntegrityError
from django.core.exceptions import ObjectDoesNotExist, ValidationError

from apps.activity.models.asset_model import Asset
from apps.activity.models.job_model import Jobneed, JobneedDetails
from apps.core import exceptions as excp
from apps.core.constants import DatabaseConstants
from apps.service import serializers as sz
from apps.service.validators import clean_record
from apps.service.types import ServiceOutputType
from intelliwiz_config.celery import app

# Import Messages from database_service
from apps.service.auth import Messages as AM


log = getLogger("message_q")


class Messages(AM):
    """GraphQL service messages"""
    INSERT_SUCCESS = "Inserted Successfully!"
    UPDATE_SUCCESS = "Updated Successfully!"
    INSERT_FAILED = "Failed to insert something went wrong!"
    UPLOAD_FAILED = "Upload Failed!"
    NODETAILS = " Unable to find any details record against site/incident report"


def call_service_based_on_filename(
    data, filename, db="default", request=None, user=None
):
    """
    Route file uploads to appropriate Celery task handlers.

    Maps compressed file names to their corresponding service functions:
    - insertRecord.gz -> perform_insertrecord
    - updateTaskTour.gz -> perform_tasktourupdate
    - uploadReport.gz -> perform_reportmutation
    - adhocRecord.gz -> perform_adhocmutation

    Args:
        data: File data
        filename: Name of uploaded file
        db: Database alias
        request: HTTP request (optional)
        user: User ID for audit

    Returns:
        Celery AsyncResult: Task handle for monitoring
    """
    log.info(f"filename before calling {filename}")
    if filename == "insertRecord.gz":
        log.info("calling insertrecord. service..")
        from apps.service.services.database_service import perform_insertrecord
        return perform_insertrecord.delay(file=data, db=db, bg=True, userid=user)
    if filename == "updateTaskTour.gz":
        log.info("calling updateTaskTour service..")
        from apps.service.services.job_service import perform_tasktourupdate
        return perform_tasktourupdate.delay(file=data, db=db, bg=True)
    if filename == "uploadReport.gz":
        log.info("calling uploadReport service..")
        return perform_reportmutation.delay(file=data, db=db, bg=True)
    if filename == "adhocRecord.gz":
        log.info("calling adhocRecord service..")
        return perform_adhocmutation.delay(file=data, db=db, bg=True)


@app.task(
    bind=True, default_retry_delay=300, max_retries=5, name="perform_reportmutation"
)
def perform_reportmutation(self, records, db="default", bg=False):
    """
    Celery task for processing site/incident reports with child tasks.

    Handles complex hierarchies:
    - Parent record (site/incident report wrapper)
    - Multiple child records (actual report instances)
    - Detail records for each child (question answers)

    Also processes work permits:
    - PDF generation
    - Approval routing
    - Email notifications to verifiers
    - Return work permit handling

    Args:
        records: List of JSON record strings
        db: Database alias
        bg: Background execution flag

    Returns:
        ServiceOutputType or dict: Result with rc, recordcount, msg, traceback
    """
    # Import here to avoid circular dependency
    from apps.service.services.database_service import save_parent_childs

    rc, recordcount, traceback, msg = 1, 0, "NA", Messages.INSERT_FAILED
    instance = None
    try:
        log.info(
            f"""perform_reportmutation(records = {type(records)}, bg = {bg}, db = {db}, runnning in {'background' if bg else "foreground"})"""
        )
        data = [json.loads(record) for record in records]
        log.info(f"data: {pformat(data)}")
        if len(data) == 0:
            raise excp.NoRecordsFound
        log.info(
            f"'data = {pformat(data)} {len(data)} Number of records found in the file"
        )
        for record in data:
            if record:
                tablename = record.pop("tablename", None)
                is_return_workpermit = record.pop("isreturnwp", None)
                child = record.pop("child", None)
                parent = record

                log.info(f"Parent: ------------> {parent}")
                log.info(f"Child: ------------> {child}")
                verifers = record.pop("verifier", None)
                log.info(f"Verifier: ------------> {verifers}")
                try:
                    switchedSerializer = (
                        sz.WomSerializer if tablename == "wom" else sz.JobneedSerializer
                    )
                    log.info(f"Switched Serializer: ------------> {switchedSerializer}")
                    with transaction.atomic(using=db):
                        if child and len(child) > 0 and parent:
                            jobneed_parent_post_data = parent
                            jn_parent_serializer = switchedSerializer(
                                data=clean_record(jobneed_parent_post_data)
                            )
                            log.info(f"switched serializer is {switchedSerializer}")
                            rc, traceback, msg = save_parent_childs(
                                sz,
                                jn_parent_serializer,
                                child,
                                Messages,
                                tablename,
                                is_return_workpermit,
                                verifers,
                            )
                            if rc == 0:
                                recordcount += 1
                        else:
                            log.error(Messages.NODETAILS)
                            msg, rc = Messages.NODETAILS, 1
                except (TypeError, ValueError, json.JSONDecodeError) as e:
                    log.error(
                        "something went wrong while saving \
                            parent and child for report mutations",
                        exc_info=True,
                    )
                    raise
        if len(data) == recordcount:
            msg = Messages.UPDATE_SUCCESS
            log.info(f"All {recordcount} report records are updated successfully")
            rc = 0
        log.info(f"Data, {data}")
    except excp.NoRecordsFound as e:
        log.warning("No records found for report mutation", exc_info=True)
        rc, traceback, msg = 1, tb.format_exc(), Messages.UPLOAD_FAILED
    except (DatabaseError, FileNotFoundError, IOError, IntegrityError, OSError, ObjectDoesNotExist, PermissionError, TypeError, ValidationError, ValueError, json.JSONDecodeError) as e:
        msg, traceback, rc = Messages.INSERT_FAILED, tb.format_exc(), 1
        log.error("something went wrong", exc_info=True)
    results = ServiceOutputType(
        rc=rc, recordcount=recordcount, msg=msg, traceback=traceback
    )
    return results.__dict__ if bg else results


@app.task(
    bind=True, default_retry_delay=300, max_retries=5, name="perform_adhocmutation"
)
def perform_adhocmutation(
    self, records, db="default", bg=False
):  # sourcery skip: remove-empty-nested-block, remove-redundant-if, remove-redundant-pass
    """
    Celery task for ADHOC task reconciliation.

    Handles mobile-created ADHOC tasks by:
    - Looking up scheduled tasks by parameters (qset, people, asset, bu, time window)
    - Updating scheduled task if found (reconciliation)
    - Creating new ADHOC task if not found

    Also performs asset lookup correction:
    - Converts NEA (non-existent asset) placeholder to actual asset ID
    - Searches by site and asset code from remarks field

    Args:
        records: List of JSON record strings
        db: Database alias
        bg: Background execution flag

    Returns:
        ServiceOutputType or dict: Result with rc, recordcount, msg, traceback
    """
    # Import here to avoid circular dependency
    from apps.service.services.job_service import update_adhoc_record, insert_adhoc_record

    rc, recordcount, traceback, msg = 1, 0, "NA", Messages.INSERT_FAILED
    try:
        log.info(
            f"""perform_adhocmutation(records = {records}, bg = {bg}, db = {db}, runnning in {'background' if bg else "foreground"})"""
        )
        data = [json.loads(record) for record in records]
        for record in data:
            if record:
                details = record.pop("details")
                jobneedrecord = record

                with transaction.atomic(using=db):
                    if jobneedrecord["asset_id"] == DatabaseConstants.ID_SYSTEM:  # NONE asset
                        # then it should be NEA
                        assetobjs = Asset.objects.filter(
                            bu_id=jobneedrecord["bu_id"],
                            assetcode=jobneedrecord["remarks"],
                        )
                        jobneedrecord["asset_id"] = (
                            1 if assetobjs.count() != 1 else assetobjs[0].id
                        )

                    jobneedrecord = clean_record(jobneedrecord)
                    scheduletask = Jobneed.objects.get_schedule_for_adhoc(
                        jobneedrecord["qset_id"],
                        jobneedrecord["people_id"],
                        jobneedrecord["asset_id"],
                        jobneedrecord["bu_id"],
                        jobneedrecord["starttime"],
                        jobneedrecord["endtime"],
                    )

                    log.info(f"schedule task: {pformat(scheduletask)}")
                    log.info(f"jobneed record: {pformat(jobneedrecord)}")
                    # have to update to scheduled task/reconsilation
                    if (len(scheduletask) > 0) and scheduletask["identifier"] == "TASK":
                        log.info("schedule task found, updating it now")
                        rc, traceback, msg, recordcount = update_adhoc_record(
                            scheduletask, jobneedrecord, details
                        )
                    # have to insert/create to adhoc task
                    else:
                        log.info("schedule task not found, creating a new one")
                        rc, traceback, msg, recordcount = insert_adhoc_record(
                            jobneedrecord, details
                        )
    except excp.NoDataInTheFileError as e:
        rc, traceback = 1, tb.format_exc()
        log.error("No data in the file error", exc_info=True)
        raise
    except (DatabaseError, FileNotFoundError, IOError, IntegrityError, OSError, ObjectDoesNotExist, PermissionError, TypeError, ValidationError, ValueError, json.JSONDecodeError) as e:
        rc, traceback = 1, tb.format_exc()
        log.error("something went wrong", exc_info=True)
    results = ServiceOutputType(
        rc=rc, recordcount=recordcount, msg=msg, traceback=traceback
    )
    return results.__dict__ if bg else results


def execute_graphql_mutations(mutation_query, variables=dict(), download=False):
    """
    Execute GraphQL mutation with comprehensive error handling.

    Executes mutation against the GraphQL schema and formats response.
    Used by GraphQL endpoint views for mutation operations.

    Args:
        mutation_query: GraphQL mutation string
        variables: Dict of mutation variables
        download: If True, return dict; if False, return JSON string

    Returns:
        dict or str: Mutation result data

    Raises:
        Exception: If mutation has errors
    """
    from apps.service.schema import schema

    # Execute the GraphQL mutation with the file object
    result = schema.execute(mutation_query, variable_values=variables)

    log.info(f"Mutation query: {mutation_query}")
    if result.errors:
        # Handle errors
        error_messages = [error.message for error in result.errors]
        log.error(f"Mutation errors: {pformat(error_messages)}", exc_info=True)
        resp = json.dumps({"errors": error_messages})
        raise Exception(f"GraphQL mutation failed with errors {resp}")
    else:
        if download:
            resp = {"data": result.data}
        else:
            resp = json.dumps({"data": result.data})
    log.info(f"Response Data: ,{resp}")
    return resp
