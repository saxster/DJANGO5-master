"""
Database Service Module

Handles all database operations including record insertion, updates, and queries.
Extracted from apps/service/utils.py for improved organization and maintainability.

Migration Date: 2025-09-30
Original File: apps/service/utils.py (lines 69-1167)

Functions:
- insertrecord_json: Async bulk record insertion
- get_json_data: JSON data extraction from files
- get_model_or_form: Model resolution by table name
- get_object: Generic object retrieval by UUID
- insert_or_update_record: Upsert operations with nested details
- update_record: Update jobneed records with details
- update_jobneeddetails: Batch update jobneed details
- save_parent_childs: Save parent-child hierarchies for reports
- perform_insertrecord: Celery task for async insertion
- get_user_instance: Get People instance by ID
"""
import json
import traceback as tb
from logging import getLogger
from pprint import pformat

from django.apps import apps
from django.conf import settings
from django.db import transaction
from django.db.utils import IntegrityError, DatabaseError
from django.core.exceptions import ObjectDoesNotExist, ValidationError

from apps.activity.models.asset_model import Asset
from apps.activity.models.job_model import Jobneed, JobneedDetails
from apps.work_order_management.models import Wom
from apps.core import utils
from apps.core.utils_new.db_utils import get_current_db_name
from apps.core.utils_new.sentinel_resolvers import is_none_record
from apps.core.constants import JobConstants, DatabaseConstants
from apps.core import exceptions as excp
from apps.service import serializers as sz
from apps.y_helpdesk.models import Ticket
# Lazy imports to avoid circular dependency - imported where used
# from background_tasks.tasks import (
#     alert_sendmail,
#     send_email_notification_for_wp_from_mobile_for_verifier,
#     insert_json_records_async,
# )
from celery import shared_task
from apps.work_order_management.utils import (
    save_approvers_injson,
    save_verifiers_injson,
)
from apps.scheduler.utils import create_dynamic_job
from apps.service.validators import clean_record
from apps.service.rest_types import ServiceOutputType  # GraphQL types removed Oct 2025

# Import Messages class for consistency
from apps.service.auth import Messages as AM


log = getLogger("message_q")
tlog = getLogger("tracking")
error_logger = getLogger("error_logger")


class Messages(AM):
    """Database service messages"""
    INSERT_SUCCESS = "Inserted Successfully!"
    UPDATE_SUCCESS = "Updated Successfully!"
    IMPROPER_DATA = (
        "Failed to insert incorrect tablname or size of columns and rows doesn't match",
    )
    WRONG_OPERATION = "Wrong operation 'id' is passed during insertion!"
    DBERROR = "Integrity Error!"
    INSERT_FAILED = "Failed to insert something went wrong!"
    UPDATE_FAILED = "Failed to Update something went wrong!"
    NOT_INTIATED = "Insert cannot be initated not provided necessary data"
    UPLOAD_FAILED = "Upload Failed!"
    NOTFOUND = "Unable to find people with this pelogid"
    START = "Mutation start"
    END = "Mutation end"
    ADHOCFAILED = "Adhoc service failed"
    NODETAILS = " Unable to find any details record against site/incident report"
    REPORTSFAILED = "Failed to generate jasper reports"
    UPLOAD_SUCCESS = "Uploaded Successfully!"


def insertrecord_json(records, tablename):
    """
    Async bulk record insertion via Celery.

    Args:
        records: List of record dicts or JSON strings
        tablename: Target model table name

    Returns:
        list: UUIDs of records queued for insertion
    """
    uuids = []
    try:
        if model := get_model_or_form(tablename):
            for record in records:
                # Handle both string and dict inputs
                if isinstance(record, str):
                    record = json.loads(record)
                record = clean_record(record)
                uuids.append(record["uuid"])

            # Lazy import to avoid circular dependency
            from background_tasks.tasks import insert_json_records_async
            insert_json_records_async.delay(records, tablename)
    except IntegrityError as e:
        tlog.info(f"record already exist in {tablename}")
    except (DatabaseError, TypeError, ValueError, json.JSONDecodeError) as e:
        tlog.critical("something went wrong", exc_info=True)
        raise e
    return uuids


def get_json_data(file):
    """
    Extract JSON data from uploaded file.

    Handles special tracking record format with ? separator.

    Args:
        file: File object with read() method

    Returns:
        list: Parsed JSON data or empty list on error
    """
    jsonstring = None
    try:
        s = file.read().decode("utf-8")
        jsonstring = s.replace("'", "")
        if isTrackingRecord := jsonstring.startswith("{"):
            log.info("Tracking record found")
            arr = jsonstring.split("?")
            jsonstring = json.dumps(arr)
        return json.loads(jsonstring)
    except json.decoder.JSONDecodeError:
        log.warning("It is not valid Json String \n %s" % (pformat(jsonstring)))
    except (DatabaseError, FileNotFoundError, IOError, OSError, PermissionError, TypeError, ValueError, json.JSONDecodeError) as e:
        log.critical("File unzipping error", exc_info=True)
    return []


def get_model_or_form(tablename):
    """
    Resolve Django model class from table name string.

    Maps legacy table names to actual model classes for backward compatibility.

    Args:
        tablename: String identifier for the model

    Returns:
        Model class or None if not found
    """
    if tablename == "peopleeventlog":
        return apps.get_model("attendance", "PeopleEventlog")
    if tablename == "attachment":
        return apps.get_model("activity", "Attachment")
    if tablename == "assetlog":
        return apps.get_model("activity", "AssetLog")
    if tablename == "jobneed":
        return apps.get_model("activity", "Jobneed")
    if tablename == "jobneeddetails":
        return apps.get_model("activity", "JobneedDetails")
    if tablename == "deviceeventlog":
        return apps.get_model("activity", "DeviceEventlog")
    if tablename == "ticket":
        return apps.get_model("y_helpdesk", "Ticket")
    if tablename == "asset":
        return apps.get_model("activity", "Asset")
    if tablename == "tracking":
        return apps.get_model("attendance", "Tracking")
    if tablename == "typeassist":
        return apps.get_model("onboarding", "TypeAssist")
    if tablename == "wom":
        return apps.get_model("work_order_management", "Wom")
    if tablename == "womdetails":
        return apps.get_model("work_order_management", "WomDetails")
    if tablename == "business unit":
        return apps.get_model("onboarding", "Bt")


def get_object(uuid, model):
    """
    Retrieve object by UUID.

    Args:
        uuid: Object UUID
        model: Django model class

    Returns:
        Model instance

    Raises:
        Exception: If object not found
    """
    try:
        return model.objects.get(uuid=uuid)
    except model.DoesNotExist as e:
        raise Exception from e


def insert_or_update_record(record, tablename):
    """
    Upsert record with support for nested details.

    Handles special logic for:
    - Jobneed records with nested details
    - Attachment records with ownername_id correction
    - Foreign key field name corrections

    Args:
        record: Dict with record data
        tablename: Target model table name

    Returns:
        Model instance or None on IntegrityError
    """
    try:
        if model := get_model_or_form(tablename):
            # Clean the record first (this will handle field name mappings)
            record = clean_record(record)

            # Extract details if present (for jobneed records with nested details)
            # Do this AFTER cleaning so field names are already mapped
            details = None
            if tablename == "jobneed" and "details" in record:
                details = record.pop("details")
                log.info(f"Found {len(details)} detail records nested in jobneed record")

            log.info(f"record after cleaning\n {pformat(record)}")

            # Fix field names for foreign keys (remove _id suffix for model fields)
            if tablename == "attachment":
                # Fix incorrect ownername_id from mobile app
                if "ownername_id" in record:
                    from apps.onboarding.models import TypeAssist
                    # Check if the provided ownername_id exists
                    if not TypeAssist.objects.filter(id=record["ownername_id"]).exists():
                        log.warning(f"Invalid ownername_id {record['ownername_id']} provided")
                        # Try to find the correct ID based on the ownername
                        if "ownername" in record or record.get("ownername_id") == 487:
                            # Known issue: mobile app sends 487 for JOBNEEDDETAILS
                            ownername = record.get("ownername", "JOBNEEDDETAILS")
                            correct_ta = TypeAssist.objects.filter(tacode=ownername).first()
                            if correct_ta:
                                log.info(f"Correcting ownername_id from {record['ownername_id']} to {correct_ta.id} for {ownername}")
                                record["ownername_id"] = correct_ta.id
                            else:
                                log.error(f"Could not find TypeAssist for {ownername}")

                # Remove the ownername string field - Django expects ownername_id only
                if "ownername" in record:
                    record.pop("ownername")

                if "tenant_id" in record:
                    record["tenant_id"] = record.get("tenant_id")
                if "cuser_id" in record:
                    record["cuser_id"] = record.get("cuser_id")
                if "muser_id" in record:
                    record["muser_id"] = record.get("muser_id")
                if "bu_id" in record:
                    record["bu_id"] = record.get("bu_id")

            if model.objects.filter(uuid=record["uuid"]).exists():
                model.objects.filter(uuid=record["uuid"]).update(**record)
                log.info("record is already exist so updating it now..")
                obj = model.objects.filter(uuid=record["uuid"]).first()
            else:
                log.info("record does not exist so creating it now..")
                obj = model.objects.create(**record)

            # Process nested details for jobneed records
            if tablename == "jobneed" and details and obj:
                # JobneedDetails is already imported at the top of the file
                log.info(f"Processing {len(details)} nested detail records for jobneed {obj.id}")
                details_created = 0
                for detail in details:
                    # Update the jobneed_id to reference the parent
                    detail["jobneed_id"] = obj.id
                    detail_cleaned = clean_record(detail)

                    # Check if detail already exists
                    if JobneedDetails.objects.filter(uuid=detail_cleaned.get("uuid")).exists():
                        JobneedDetails.objects.filter(uuid=detail_cleaned["uuid"]).update(**detail_cleaned)
                        log.info(f"Detail record with UUID {detail_cleaned['uuid']} updated")
                    else:
                        JobneedDetails.objects.create(**detail_cleaned)
                        details_created += 1
                        log.info(f"Detail record with UUID {detail_cleaned.get('uuid')} created")

                log.info(f"Processed all {len(details)} detail records for jobneed {obj.id} ({details_created} created)")

            return obj
    except IntegrityError as e:
        log.error(f"IntegrityError in {tablename}: {str(e)}")
        log.error(f"Record data: {record}")
        return None
    except (DatabaseError, FileNotFoundError, IOError, OSError, ObjectDoesNotExist, PermissionError, TypeError, ValidationError, ValueError, json.JSONDecodeError) as e:
        log.critical(
            "something went wrong while inserting/updating record", exc_info=True
        )
        raise e


def update_record(details, jobneed_record, JnModel, JndModel):
    """
    Update jobneed and its details (or create if ADHOC).

    For ADHOC tours, creates the record if it doesn't exist.
    Updates dynamic job creation and geocoding.

    Args:
        details: List of jobneed detail dicts
        jobneed_record: Jobneed data dict
        JnModel: Jobneed model class
        JndModel: JobneedDetails model class

    Returns:
        bool: True if successful
    """
    # Check for ADHOC before cleaning the record (field mapping changes identifier)
    original_identifier = jobneed_record.get("identifier", "")
    original_jobtype = jobneed_record.get("jobtype", "")

    is_adhoc = (
        original_jobtype == "ADHOC" or
        original_identifier.startswith("ADHOC") or
        "ADHOC" in original_identifier or
        original_identifier in ["ADHOCINTERNALTOUR", "ADHOCEXTERNALTOUR"]
    )

    log.info(f"ADHOC detection - original_identifier: {original_identifier}, original_jobtype: {original_jobtype}, is_adhoc: {is_adhoc}")

    record = clean_record(jobneed_record)
    try:
        # Try to get existing instance, or create if ADHOC
        try:
            instance = JnModel.objects.get(uuid=record["uuid"])
            jn_parent_serializer = sz.JobneedSerializer(data=record, instance=instance)
        except JnModel.DoesNotExist:
            # For ADHOC tours/tasks, create the record if it doesn't exist
            if is_adhoc:
                log.info(f"ADHOC record with UUID {record['uuid']} not found, creating new record")
                log.info(f"Original identifier: {jobneed_record.get('identifier')}, jobtype: {jobneed_record.get('jobtype')}")
                log.info(f"Cleaned identifier: {record.get('identifier')}, jobtype: {record.get('jobtype')}")
                instance = None
                jn_parent_serializer = sz.JobneedSerializer(data=record)
            else:
                log.error(f"Jobneed with UUID {record['uuid']} does not exist and is not ADHOC type")
                log.error(f"identifier: {record.get('identifier')}, jobtype: {record.get('jobtype')}")
                raise
        if jn_parent_serializer.is_valid():
            jobneed = jn_parent_serializer.save()
            if instance is None:
                log.info(f"Successfully created new ADHOC record with ID {jobneed.id} and UUID {jobneed.uuid}")
            if (
                jobneed.jobstatus == "COMPLETED"
                and jobneed.other_info.get("isdynamic")
                and is_none_record(jobneed.parent_id)  # Top-level dynamic job
            ):
                create_dynamic_job([jobneed.job_id])
                log.info("Dynamic job created")
            if jobneed.gpslocation:
                # Import here to avoid circular dependency
                from apps.service.services.geospatial_service import get_readable_addr_from_point
                jobneed.geojson["gpslocation"] = get_readable_addr_from_point(
                    jobneed.gpslocation
                )
            jobneed.save()
            log.debug(
                f"after saving the record jobneed_id {jobneed.id} cdtz {jobneed.cdtz} mdtz = {jobneed.mdtz} starttime = {jobneed.starttime} endtime = {jobneed.endtime}"
            )
            log.info(f"parent jobneed is {'created' if instance is None else 'updated'} successfully")
            if jobneed.jobstatus == "AUTOCLOSED" and len(details) == 0:
                return True
            elif isJndUpdated := update_jobneeddetails(details, JndModel):
                log.info("parent jobneed and its details are updated successully")

                # Lazy import to avoid circular dependency
                from background_tasks.tasks import alert_sendmail
                alert_sendmail.delay(jobneed.id, "observation", atts=True)
                return True
        else:
            log.error(
                f"parent jobneed record has some errors\n{jn_parent_serializer.errors} ",
                exc_info=True,
            )
    except (DatabaseError, FileNotFoundError, IOError, OSError, ObjectDoesNotExist, PermissionError, TypeError, ValidationError, ValueError, json.JSONDecodeError):
        log.critical("update_record failed", exc_info=True)
        raise
    return False


def update_jobneeddetails(jobneeddetails, JndModel):
    """
    Batch update or create jobneed detail records.

    Args:
        jobneeddetails: List of detail record dicts
        JndModel: JobneedDetails model class

    Returns:
        bool: True if all records processed successfully
    """
    try:
        if jobneeddetails:
            updated = 0
            created_count = 0
            updated_count = 0
            log.info(f"total {len(jobneeddetails)} JND records found")
            for detail in jobneeddetails:
                record = clean_record(detail)
                log.info(f"JND record after cleaning\n {pformat(record)}")

                # Try to get existing instance, create if it doesn't exist
                try:
                    instance = JndModel.objects.get(uuid=record["uuid"])
                    jnd_ser = sz.JndSerializers(data=record, instance=instance)
                    operation = "updated"
                except JndModel.DoesNotExist:
                    # Create new detail record if it doesn't exist
                    log.info(f"JND record with UUID {record['uuid']} not found, creating new record")
                    jnd_ser = sz.JndSerializers(data=record)
                    operation = "created"

                if jnd_ser.is_valid():
                    jnd_ser.save()
                    updated += 1
                    if operation == "created":
                        created_count += 1
                    else:
                        updated_count += 1
                    log.info(f"JND record with UUID {record['uuid']} {operation} successfully")
                else:
                    log.error(
                        f'JND record with this uuid: {record["uuid"]} has some errors!\n {jnd_ser.errors}',
                        exc_info=True,
                    )
            if len(jobneeddetails) == updated:
                log.info(f"All {updated} JND records processed successfully ({created_count} created, {updated_count} updated)")
                return True
            else:
                log.warning(f"failed to update all {len(jobneeddetails)} JND records")
    except (DatabaseError, FileNotFoundError, IOError, OSError, ObjectDoesNotExist, PermissionError, TypeError, ValidationError, ValueError, json.JSONDecodeError) as e:
        log.critical("jobneed details record failed to save", exc_info=True)
        raise


def save_parent_childs(
    sz, jn_parent_serializer, child, M, tablename, is_return_wp, verifers
):
    """
    Save parent-child record hierarchies for reports and work permits.

    Handles complex workflows including:
    - Site/incident report creation with child tasks
    - Work permit generation and approval routing
    - Return work permit processing
    - PDF generation and email notifications

    Args:
        sz: Serializers module
        jn_parent_serializer: Parent record serializer
        child: List of child records
        M: Messages class
        tablename: Target table ('wom' or 'jobneed')
        is_return_wp: Boolean for return work permit
        verifers: List of verifier IDs

    Returns:
        tuple: (rc, traceback, msg) where rc=0 on success
    """
    from apps.onboarding.models import Bt
    from apps.activity.models.question_model import QuestionSet
    from apps.work_order_management.models import Vendor
    from apps.work_order_management.views import WorkPermit
    from apps.work_order_management.utils import save_pdf_to_tmp_location

    try:
        rc, traceback = 0, "NA"
        instance = None
        if jn_parent_serializer.is_valid():
            if not is_return_wp:
                parent = jn_parent_serializer.save()
                log.info(f"{verifers},{type(verifers)}")
                parent.verifiers = [verifers]
                log.info(f"Here I am because not jn_parent_serializer: {parent}")
            if is_return_wp:
                log.info("Return Work Permit")
                id = jn_parent_serializer.validated_data.get("parent_id")
                log.info(f"WOM Id: {id}")
                wom = Wom.objects.get(
                    id=jn_parent_serializer.validated_data.get("parent_id")
                )
                seqno = (
                    Wom.objects.filter(parent_id=wom.id)
                    .order_by("-seqno")
                    .first()
                    .seqno
                    + 1
                )
                wom.workstatus = Wom.Workstatus.COMPLETED
                wom.save()

            log.info("parent record for report mutation saved")
            allsaved = 0
            log.info(f"Total {len(child)} child records found for report mutation")
            for ch in child:
                details = ch.pop("details")
                log.info(
                    f'Total {len(details)} detail records found for the chid with this uuid:{ch["uuid"]}'
                )
                parent_id = (
                    jn_parent_serializer.validated_data.get("parent_id")
                    if is_return_wp
                    else parent.id
                )
                ch.update({"parent_id": parent_id})
                switchedSerializer = (
                    sz.WomSerializer if tablename == "wom" else sz.JobneedSerializer
                )
                log.info(f"switched serializer is {switchedSerializer}")
                child_serializer = switchedSerializer(data=clean_record(ch))
                if child_serializer.is_valid():
                    if is_return_wp:
                        child_serializer.validated_data["seqno"] = seqno
                        seqno += 1
                    child_instance = child_serializer.save()
                    log.info(
                        f"child record with this uuid: {child_instance.uuid} saved for report mutation"
                    )
                    for dtl in details:
                        dtl.update(
                            {"wom_id": child_instance.id}
                            if tablename == "wom"
                            else {"jobneed_id": child_instance.id}
                        )
                        switchedDetailSerializer = (
                            sz.WomDetailsSerializers
                            if tablename == "wom"
                            else sz.JndSerializers
                        )
                        log.info(f"switched serializer is {switchedDetailSerializer}")
                        ch_detail_serializer = switchedDetailSerializer(
                            data=clean_record(dtl)
                        )
                        if ch_detail_serializer.is_valid():
                            ch_detail_serializer.save()
                        else:
                            log.error(
                                f"detail record of this child uuid:{child_instance.uuid} has some errors: {ch_detail_serializer.errors}"
                            )
                            traceback, msg, rc = (
                                str(ch_detail_serializer.errors),
                                M.INSERT_FAILED,
                                1,
                            )
                    allsaved += 1
                else:
                    log.error(f"child record has some errors:{child_serializer.errors}")
                    traceback, msg, rc = (
                        str(child_serializer.errors),
                        M.INSERT_FAILED,
                        1,
                    )
                log.info(f"Child : {child}")
            if allsaved == len(child):
                msg = M.INSERT_SUCCESS
                log.info(
                    f"All {allsaved} child records saved successfully,{is_return_wp}"
                )
                if (
                    not is_return_wp
                    and hasattr(parent, "parent_id")
                    and tablename == "wom"
                    and parent.workpermit != "NOT_REQUIRED"
                    and is_none_record(parent.parent_id)  # Top-level WOM
                ):
                    parent = save_approvers_injson(parent)
                    parent = save_verifiers_injson(parent)
                    log.info(f"{parent.id = } {parent.uuid = } {parent.description}")
                    wom_id = parent.id
                    verifers = parent.verifiers
                    sitename = Bt.objects.get(id=parent.bu_id).buname
                    worpermit_status = parent.workpermit
                    permit_name = parent.qset.qsetname
                    vendor_name = Vendor.objects.get(id=parent.vendor_id).name
                    client_id = parent.client_id
                    latest_records = (
                        Wom.objects.filter(
                            client=parent.client_id,
                            bu=parent.bu_id,
                            parent_id=DatabaseConstants.ID_SYSTEM,  # NONE parent for work permits
                            identifier="WP",
                        )
                        .order_by("-other_data__wp_seqno")
                        .first()
                    )
                    if latest_records is None:
                        parent.other_data["wp_seqno"] = 1
                    elif (
                        parent.other_data["wp_seqno"]
                        != latest_records.other_data["wp_seqno"]
                    ):
                        parent.other_data["wp_seqno"] = (
                            latest_records.other_data["wp_seqno"] + 1
                        )
                    parent.other_data["wp_name"] = permit_name
                    parent.identifier = "WP"
                    parent.save()
                    report_object = WorkPermit.get_report_object(parent, permit_name)
                    report = report_object(
                        filename=permit_name,
                        client_id=parent.client_id,
                        returnfile=True,
                        formdata={"id": parent.id},
                        request=None,
                    )
                    report_pdf_object = report.execute()
                    pdf_path = save_pdf_to_tmp_location(
                        report_pdf_object,
                        report_name=permit_name,
                        report_number=parent.other_data["wp_seqno"],
                    )
                    log.info(f"PDF Path: {pdf_path}")

                    # Lazy import to avoid circular dependency
                    from background_tasks.tasks import send_email_notification_for_wp_from_mobile_for_verifier
                    send_email_notification_for_wp_from_mobile_for_verifier.delay(
                        wom_id,
                        verifers,
                        sitename,
                        worpermit_status,
                        permit_name,
                        vendor_name,
                        client_id,
                        workpermit_attachment=pdf_path,
                    )
        if is_return_wp:
            from background_tasks.tasks import send_email_notification_for_vendor_and_security_for_rwp
            wom = Wom.objects.get(
                id=jn_parent_serializer.validated_data.get("parent_id")
            )
            vendor_name = Vendor.objects.get(id=wom.vendor_id).name
            permit_name = QuestionSet.objects.get(id=wom.qset.id).qsetname
            report_object = WorkPermit.get_report_object(wom, permit_name)
            report = report_object(
                filename=permit_name,
                client_id=wom.client_id,
                returnfile=True,
                formdata={"id": wom.id},
                request=None,
            )
            report_pdf_object = report.execute()
            permit_no = wom.other_data["wp_seqno"]
            sitename = Bt.objects.get(id=wom.bu.id).buname
            pdf_path = save_pdf_to_tmp_location(
                report_pdf_object,
                report_name=permit_name,
                report_number=wom.other_data["wp_seqno"],
            )
            send_email_notification_for_vendor_and_security_for_rwp.delay(
                wom.id,
                sitename,
                wom.workstatus,
                vendor_name,
                pdf_path,
                permit_name,
                permit_no,
            )
        else:
            log.error(jn_parent_serializer.errors)
            traceback, msg, rc = str(jn_parent_serializer.errors), M.INSERT_FAILED, 1
        log.info("save_parent_childs ............end")
        return rc, traceback, msg
    except (DatabaseError, FileNotFoundError, IOError, OSError, ObjectDoesNotExist, PermissionError, TypeError, ValidationError, ValueError, json.JSONDecodeError):
        log.critical("something went wrong", exc_info=True)
        raise


@shared_task(
    bind=True, default_retry_delay=300, max_retries=5, name="perform_insertrecord"
)
def perform_insertrecord(
    self, records, db="default", filebased=True, bg=False, userid=None
):
    """
    Celery task for async bulk record insertion.

    Validates and processes records with comprehensive error handling.
    Triggers post-insertion workflows like ticket history and face recognition.

    Args:
        records: List of JSON record strings
        db: Database alias
        filebased: Whether data is from file
        bg: Background execution flag
        userid: User ID for audit

    Returns:
        ServiceOutputType or dict: Result with rc, recordcount, msg, traceback
    """
    rc, recordcount, traceback, msg = 1, 0, "NA", Messages.INSERT_FAILED

    instance = None
    log.info(
        f"""perform_insertrecord( records = {type(records)}, bg = {bg}, db = {db}, filebased = {filebased}  { userid = } runnning in {'background' if bg else "foreground"})"""
    )
    try:
        data = [json.loads(record) for record in records]
        log.info(f"data = {pformat(data)} and length of data {len(data)}")

        if len(data) == 0:
            raise excp.NoRecordsFound

        # Validate records before processing
        valid_records = []
        empty_records = 0
        invalid_records = 0

        for record in data:
            if not record:  # Empty dict, None, or falsy value
                empty_records += 1
                log.warning(f"Skipping empty record: {record}")
                continue
            elif not isinstance(record, dict):
                invalid_records += 1
                log.error(f"Skipping invalid record type {type(record)}: {record}")
                continue
            else:
                valid_records.append(record)

        # Handle case where all records are empty/invalid
        if not valid_records:
            if empty_records > 0:
                msg = f"All {empty_records} records are empty (no data to process)"
                log.warning(msg)
                raise ValueError(msg)
            elif invalid_records > 0:
                msg = f"All {invalid_records} records have invalid format"
                log.error(msg)
                raise ValueError(msg)
            else:
                raise excp.NoRecordsFound

        log.info(f"Processing {len(valid_records)} valid records (skipped {empty_records} empty, {invalid_records} invalid)")

        with transaction.atomic(using=db):
            for record in valid_records:
                    # Handle missing tablename gracefully
                    tablename = record.pop("tablename", None)
                    if not tablename:
                        # Infer table name from record structure
                        if 'details' in record and 'jobdesc' in record:
                            tablename = "jobneed"  # Jobneed record with details
                        elif 'answer' in record and 'question_id' in record:
                            tablename = "jobneed_details"  # JobneedDetails record
                        else:
                            log.error(f"Cannot determine table name for record: {record}")
                            continue
                    log.info(f"Table Name: {tablename}")
                    log.info("Record %s", record)
                    obj = insert_or_update_record(record, tablename)
                    if record.get("people_id") == None:
                        id = record.get("muser_id")
                    else:
                        id = record.get("people_id")
                    user = get_user_instance(id)

                    if tablename == "ticket" and isinstance(obj, Ticket):
                        utils.store_ticket_history(instance=obj, user=user)
                    if tablename == "wom":
                        from apps.work_order_management import utils as wutils
                        wutils.notify_wo_creation(id=obj.id)

                    # Import here to avoid circular dependency
                    from apps.service.services.geospatial_service import save_linestring_and_update_pelrecord
                    from apps.service.services.crisis_service import check_for_sitecrisis

                    allconditions = [
                        hasattr(obj, "peventtype"),
                        hasattr(obj, "endlocation"),
                        hasattr(obj, "punchintime"),
                        hasattr(obj, "punchouttime"),
                    ]

                    if all(allconditions) and all(
                        [
                            tablename == "peopleeventlog",
                            obj.peventtype.tacode in ("CONVEYANCE", "AUDIT"),
                            obj.endlocation,
                            obj.punchouttime,
                            obj.punchintime,
                        ]
                    ):
                        log.info("save line string is started")
                        save_linestring_and_update_pelrecord(obj)
                    check_for_sitecrisis(obj, tablename, user)
                    recordcount += 1
                    log.info(f"{recordcount} record inserted successfully")
        if len(valid_records) == recordcount:
            msg = Messages.INSERT_SUCCESS
            log.info(f"All {recordcount} records are inserted successfully")
            rc = 0
    except excp.NoRecordsFound as e:
        log.warning("No records found for insertrecord service", exc_info=True)
        rc, traceback, msg = 1, tb.format_exc(), Messages.INSERT_FAILED
    except ValueError as e:
        # Handle empty/invalid records with specific error message
        log.warning(f"Input validation error: {str(e)}")
        rc, traceback, msg = 1, "NA", str(e)
    except (DatabaseError, FileNotFoundError, IOError, OSError, ObjectDoesNotExist, PermissionError, TypeError, ValidationError, ValueError, json.JSONDecodeError) as e:
        log.error("something went wrong!", exc_info=True)
        traceback = tb.format_exc()
    results = ServiceOutputType(
        rc=rc, recordcount=recordcount, msg=msg, traceback=traceback
    )
    return results.__dict__ if bg else results


def get_user_instance(id):
    """
    Get People instance by ID.

    Args:
        id: People model ID (will be converted to int)

    Returns:
        People instance
    """
    log.info(f"people id: {id} type: {type(id)}")
    from apps.peoples.models import People

    return People.objects.get(id=int(id))
