"""
Job/Tour Service Module

Handles all job and tour operations including ADHOC tasks, updates, and linestring tracking.
Extracted from apps/service/utils.py for improved organization and maintainability.

Migration Date: 2025-09-30
Original File: apps/service/utils.py (lines 143-1188)

Functions:
- save_jobneeddetails: Placeholder for jobneed details processing
- update_adhoc_record: Update ADHOC task with race condition protection
- insert_adhoc_record: Create new ADHOC task record
- perform_tasktourupdate: Celery task for batch task/tour updates
- save_journeypath_field: Create linestring for tour journey
- check_for_tour_track: Check if tour tracking should be saved

Features:
- Distributed lock support for race condition prevention
- Celery task integration
- Dynamic job creation
- Journey path tracking with PostGIS LineString
"""
import json
import traceback as tb
from logging import getLogger
from pprint import pformat

from django.db import transaction
from django.db.utils import DatabaseError, IntegrityError
from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.contrib.gis.geos import LineString

from apps.activity.models.asset_model import Asset
from apps.activity.models.job_model import Jobneed, JobneedDetails
from apps.attendance.models import Tracking
from apps.core import exceptions as excp
from apps.core.constants import JobConstants, DatabaseConstants
from apps.core.utils_new.sentinel_resolvers import is_none_record
from apps.core.utils_new.distributed_locks import distributed_lock, LockAcquisitionError
from apps.core.error_handling import ErrorHandler
from apps.service import serializers as sz
from apps.service.validators import clean_record
from apps.service.rest_types import ServiceOutputType  # GraphQL types removed Oct 2025
from celery import shared_task
# Lazy import to avoid circular dependency - imported where used
# from background_tasks.tasks import alert_sendmail

# Import Messages from database_service
from apps.service.auth import Messages as AM


log = getLogger("message_q")
tlog = getLogger("tracking")


class Messages(AM):
    """Job service messages"""
    UPDATE_SUCCESS = "Updated Successfully!"
    UPDATE_FAILED = "Failed to Update something went wrong!"
    INSERT_SUCCESS = "Inserted Successfully!"
    INSERT_FAILED = "Failed to insert something went wrong!"
    UPLOAD_FAILED = "Upload Failed!"


def save_jobneeddetails(data):
    """
    Placeholder function for jobneed details processing.

    This function appears to be incomplete in the original utils.py.

    Args:
        data: Dict with jobneeddetails JSON string

    Note:
        Original implementation only parses JSON but doesn't process it.
        May need completion in future based on business requirements.
    """
    jobneeddetails_post_data = json.loads(data["jobneeddetails"])
    # Original function ends here - incomplete implementation


def update_adhoc_record(scheduletask, jobneedrecord, details):
    """
    Update adhoc task record with race condition protection.

    Uses distributed lock + transaction to prevent concurrent mobile
    sync operations from corrupting task state.

    Args:
        scheduletask: Dict with scheduled task data
        jobneedrecord: Dict with updated jobneed data
        details: List of question detail updates

    Returns:
        Tuple of (rc, recordcount, traceback, msg)
    """
    rc, recordcount, traceback, msg = 1, 0, "NA", ""
    log.info(f"jobneed record received: {pformat(jobneedrecord)}")

    lock_key = f"adhoc_update:{scheduletask['id']}"

    try:
        with distributed_lock(lock_key, timeout=10, blocking_timeout=5):
            with transaction.atomic():
                jobneed = Jobneed.objects.select_for_update().get(id=scheduletask["id"])

                jobneed.performedby_id = jobneedrecord["performedby_id"]
                jobneed.starttime = jobneedrecord["starttime"]
                jobneed.endtime = jobneedrecord["endtime"]
                jobneed.jobstatus = jobneedrecord["jobstatus"]
                jobneed.remarks = jobneedrecord["remarks"]
                jobneed.alerts = jobneedrecord["alerts"]
                jobneed.attachmentcount = jobneedrecord["attachmentcount"]
                jobneed.mdtz = jobneedrecord["mdtz"]
                jobneed.muser_id = jobneedrecord["muser_id"]

                jobneed.save(update_fields=[
                    'performedby_id', 'starttime', 'endtime', 'jobstatus',
                    'remarks', 'alerts', 'attachmentcount', 'mdtz', 'muser_id'
                ])

                log.info(f"Adhoc record {scheduletask['id']} updated successfully")
                recordcount += 1

    except LockAcquisitionError as e:
        log.warning(f"Failed to acquire lock for adhoc update: {scheduletask['id']}")
        rc, msg = 0, "System busy, please try again"
        return rc, recordcount, traceback, msg

    except ObjectDoesNotExist as e:
        log.error(f"Jobneed {scheduletask['id']} not found")
        rc, msg = 0, "Task not found"
        return rc, recordcount, traceback, msg

    except (DatabaseError, FileNotFoundError, IOError, IntegrityError, OSError, ObjectDoesNotExist, PermissionError, TypeError, ValidationError, ValueError, json.JSONDecodeError) as e:
        log.critical(f"Error updating adhoc record: {scheduletask['id']}", exc_info=True)
        rc, msg = 0, str(e)
        return rc, recordcount, str(e), msg

    log.info(f"Adhoc record updated successfully")

    JND = JobneedDetails.objects.filter(jobneed_id=scheduletask["id"]).values()
    for jnd in JND:
        for dtl in details:
            if jnd["question_id"] == dtl["question_id"]:
                obj = JobneedDetails.objects.get(id=jnd["id"])
                record = clean_record(dtl)
                jndsz = sz.JndSerializers(instance=obj, data=record)
                if jndsz.is_valid():
                    jndsz.save()
    recordcount += 1
    rc = 0

    # Lazy import to avoid circular dependency
    from background_tasks.tasks import alert_sendmail
    alert_sendmail.delay(scheduletask["id"], "observation", atts=True)
    msg = "Scheduled Record (ADHOC) updated successfully!"
    return rc, traceback, msg, recordcount


def insert_adhoc_record(jobneedrecord, details):
    """
    Create new ADHOC task record with details.

    Args:
        jobneedrecord: Dict with jobneed data
        details: List of detail record dicts

    Returns:
        Tuple of (rc, traceback, msg, recordcount)
    """
    rc, recordcount, traceback, msg = 1, 0, "NA", ""
    jnsz = sz.JobneedSerializer(data=jobneedrecord)
    if jnsz.is_valid():
        jn_instance = jnsz.save()
        log.info(f"Jobneed Instance: ------------> {jn_instance}")
        for dtl in details:
            dtl.update({"jobneed_id": jn_instance.id})
            record = clean_record(dtl)
            jndsz = sz.JndSerializers(data=record)
            if jndsz.is_valid():
                jndsz.save()
        msg = "Record (ADHOC) inserted successfully!"
        recordcount += 1
        rc = 0

        # Lazy import to avoid circular dependency
        from background_tasks.tasks import alert_sendmail
        alert_sendmail.delay(jn_instance.id, "observation", atts=True)
    else:
        rc, traceback = 1, jnsz.errors
    return rc, traceback, msg, recordcount


@shared_task(
    bind=True, default_retry_delay=300, max_retries=5, name="perform_tasktourupdate"
)
def perform_tasktourupdate(self, records, request=None, db="default", bg=False):
    """
    Celery task for batch task/tour updates.

    Updates jobneed records with their details, creates journey paths,
    and handles dynamic job creation.

    Args:
        records: List of JSON record strings
        request: HTTP request (optional)
        db: Database alias
        bg: Background execution flag

    Returns:
        ServiceOutputType or dict: Result with rc, recordcount, msg, traceback
    """
    # Import here to avoid circular dependency
    from apps.service.services.database_service import update_record

    rc, recordcount, traceback = 1, 0, "NA"
    instance, msg = None, Messages.UPDATE_FAILED

    try:
        log.info(
            f"""perform_tasktourupdate(type of file = {type(records) }bg = {bg}, db = {db} runnning in {'background' if bg else "foreground"})"""
        )
        data = [json.loads(record) for record in records]
        log.info(f"data: {pformat(data)}")
        if len(data) == 0:
            raise excp.NoRecordsFound
        log.info(f"total {len(data)} records found for task tour update")
        for rec in data:
            if rec:
                details = rec.pop("details")
                jobneed = rec
                with transaction.atomic(using=db):
                    if isupdated := update_record(
                        details, jobneed, Jobneed, JobneedDetails
                    ):
                        recordcount += 1
                        save_journeypath_field(jobneed)
                        log.info(f"{recordcount} task/tour updated successfully")
        if len(data) == recordcount:
            msg = Messages.UPDATE_SUCCESS
            log.info(f"All {recordcount} task/tour records are updated successfully")
            rc = 0
    except excp.NoRecordsFound as e:
        log.warning("No records found for task/tour update", exc_info=True)
        rc, traceback, msg = 1, tb.format_exc(), Messages.UPLOAD_FAILED
    except IntegrityError as e:
        log.error("Database Error", exc_info=True)
        rc, traceback, msg = 1, tb.format_exc(), Messages.UPLOAD_FAILED
    except (DatabaseError, FileNotFoundError, IOError, IntegrityError, OSError, ObjectDoesNotExist, PermissionError, TypeError, ValidationError, ValueError, json.JSONDecodeError) as e:
        log.error("Something went wrong", exc_info=True)
        rc, traceback, msg = 1, tb.format_exc(), Messages.UPLOAD_FAILED
    results = ServiceOutputType(
        rc=rc, msg=msg, recordcount=recordcount, traceback=traceback
    )
    return results.__dict__ if bg else results


def save_journeypath_field(jobneed):
    """
    Create LineString geometry for tour journey path.

    Processes tracking points to create a PostGIS LineString showing
    the route taken during a tour. Automatically triggered for
    completed external/internal tours.

    Args:
        jobneed: Dict with jobneed data (uuid, jobstatus, identifier, parent_id)

    Side Effects:
        - Updates Jobneed.journeypath with LineString geometry
        - Deletes intermediate tracking points after processing
    """
    log.info(
        f"{jobneed['jobstatus']=} {jobneed['identifier']=} {jobneed['parent_id']=}"
    )
    if (
        is_none_record(jobneed.get("parent_id"))  # Top-level tour jobneed
        and jobneed.get("jobstatus") in ("COMPLETED", "PARTIALLYCOMPLETED")
        and jobneed.get("identifier") in (JobConstants.Identifier.EXTERNALTOUR, JobConstants.Identifier.INTERNALTOUR)
    ):
        try:
            log.info(f"saving line string started all conditions met")
            sitetour = Jobneed.objects.get(uuid=jobneed.get("uuid"))
            between_latlngs = Tracking.objects.filter(
                reference=jobneed.get("uuid")
            ).order_by("receiveddate")
            line = [[coord for coord in obj.gpslocation] for obj in between_latlngs]
            if len(line) > 1:
                log.info(
                    "between lat lngs found for the tour with uuid %s"
                    % jobneed.get("uuid")
                )
                ls = LineString(line, srid=4326)
                ls.transform(4326)
                sitetour.journeypath = ls
                sitetour.save()
                info = between_latlngs.delete()
                log.info(
                    f"Between latlngs are deleted and their info is following\n {info}"
                )
                log.info("save linestring is saved..")
        except (DatabaseError, IntegrityError, ObjectDoesNotExist, TypeError, ValueError, json.JSONDecodeError) as e:
            log.critical("ERROR while saving line string", exc_info=True)
            raise
        else:
            sitetour = Jobneed.objects.get(uuid=jobneed.get("uuid"))
            log.info(
                f"line string saved printing it {pformat(sitetour.journeypath)} for the tour with uuid {jobneed.get('uuid')}"
            )
    else:
        log.info(f"saving line string ended because conditions not met")


def check_for_tour_track(obj, tablename):
    """
    Check if tour tracking linestring should be saved.

    Validates conditions for saving tracking data as a linestring geometry.
    Used by perform_insertrecord to trigger tracking for CONVEYANCE/AUDIT events.

    Args:
        obj: PeopleEventlog instance
        tablename: Table name ('peopleeventlog' expected)

    Side Effects:
        - Calls save_linestring_and_update_pelrecord if conditions met
    """
    # Import here to avoid circular dependency
    from apps.service.services.geospatial_service import save_linestring_and_update_pelrecord

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
