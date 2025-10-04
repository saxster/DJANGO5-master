# Standard library imports
import base64
import json
import logging
import os
import time
import traceback as tb
from datetime import timedelta, datetime
from logging import getLogger
from pprint import pformat
from typing import Dict, Any, Optional, List, Union

# Third-party imports
from celery import shared_task

# Django imports
from django.apps import apps
from django.conf import settings
from django.core.mail import EmailMessage
from django.db import transaction
from django.db.models import Q
from django.templatetags.static import static
from django.utils import timezone
from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.db import DatabaseError, IntegrityError

# Local application imports
from intelliwiz_config.celery import app
from background_tasks import utils as butils
from apps.core import utils
from apps.core.queries import QueryRepository
from apps.core.utils_new.db_utils import get_current_db_name
from apps.core.exceptions import IntegrationException
from apps.reports.models import ScheduleReport
from apps.reports import utils as rutils
from apps.core.services.async_pdf_service import AsyncPDFGenerationService

# Import enhanced base classes and utilities
from apps.core.tasks.base import (
    BaseTask, EmailTask, ExternalServiceTask, MaintenanceTask, IdempotentTask, TaskMetrics, log_task_context
)
from apps.core.tasks.utils import task_retry_policy
from apps.core.constants.datetime_constants import SECONDS_IN_HOUR


mqlog = getLogger("message_q")
tlog = getLogger("tracking")
logger = logging.getLogger("django")

from .move_files_to_GCS import move_files_to_GCS, del_empty_dir, get_files
from .report_tasks import (
    get_scheduled_reports_fromdb,
    generate_scheduled_report,
    handle_error,
    walk_directory,
    get_report_record,
    check_time_of_report,
    remove_reportfile,
    save_report_to_tmp_folder,
)


@shared_task(name='cache_warming_scheduled')
def cache_warming_scheduled():
    """
    Scheduled task for automatic cache warming.

    Runs daily at 2 AM to warm critical caches during off-peak hours.
    """
    try:
        from apps.core.services.cache_warming_service import warm_critical_caches_task

        result = warm_critical_caches_task()

        logger.info(
            f"Scheduled cache warming completed: {result.get('total_keys_warmed', 0)} keys warmed",
            extra={'result': result}
        )

        return result

    except ImportError as e:
        logger.error(f"Cache warming service not found: {e}")
        return {'error': str(e)}
    except (DatabaseError, IntegrationException, ValueError) as e:
        logger.error(f"Cache warming task failed: {e}")
        return {'error': str(e)}
from io import BytesIO

from celery import shared_task
from scripts.utilities.mqtt_utils import publish_message


def validate_mqtt_topic(topic: str) -> str:
    """
    Validate MQTT topic for security and format compliance.

    Args:
        topic: MQTT topic string

    Returns:
        Validated topic string

    Raises:
        ValidationError: If topic validation fails
    """
    from django.core.exceptions import ValidationError
    import re

    if not topic or not isinstance(topic, str):
        raise ValidationError("MQTT topic must be a non-empty string")

    # MQTT topic length limit (MQTT spec allows up to 65535 bytes)
    if len(topic.encode('utf-8')) > 1000:  # Reasonable limit for our use case
        raise ValidationError("MQTT topic exceeds maximum length")

    # MQTT topic format validation
    # - Must not contain null characters
    # - Must not contain wildcards in publish topics
    # - Must follow MQTT topic conventions
    if '\x00' in topic:
        raise ValidationError("MQTT topic cannot contain null characters")

    if '#' in topic or '+' in topic:
        raise ValidationError("MQTT publish topics cannot contain wildcards (# or +)")

    # Check for malicious content
    dangerous_patterns = [
        r'[<>"\']',  # Potential injection characters
        r'javascript:',  # JavaScript injection
        r'<script',  # Script tags
    ]

    for pattern in dangerous_patterns:
        if re.search(pattern, topic, re.IGNORECASE):
            raise ValidationError("MQTT topic contains potentially malicious content")

    # Validate topic structure (should follow youtility conventions)
    topic_pattern = re.compile(r'^[a-zA-Z0-9/_\-\.]+$')
    if not topic_pattern.match(topic):
        raise ValidationError("MQTT topic contains invalid characters")

    return topic.strip()


def validate_mqtt_payload(payload: Union[str, Dict[str, Any], List[Any], int, float, bool]) -> Union[str, Dict[str, Any], List[Any], int, float, bool]:
    """
    Validate and sanitize MQTT payload for security.

    Args:
        payload: MQTT payload (can be string, dict, or other JSON-serializable type)

    Returns:
        Validated payload

    Raises:
        ValidationError: If payload validation fails
    """
    import json
    from django.core.exceptions import ValidationError
    from apps.core.validation import XSSPrevention

    if payload is None:
        return payload

    # Size limit (1MB for MQTT payload is generous)
    try:
        payload_str = json.dumps(payload) if not isinstance(payload, str) else payload
        if len(payload_str.encode('utf-8')) > 1024 * 1024:  # 1MB limit
            raise ValidationError("MQTT payload exceeds maximum size")
    except (TypeError, ValueError) as e:
        raise ValidationError(f"MQTT payload is not JSON serializable: {e}")

    # Sanitize payload if it's a string or contains strings
    if isinstance(payload, str):
        # Check for malicious content
        sanitized = XSSPrevention.sanitize_input(payload)
        return sanitized
    elif isinstance(payload, dict):
        # Recursively sanitize dictionary values
        sanitized_payload = {}
        for key, value in payload.items():
            # Sanitize key
            if not isinstance(key, str):
                key = str(key)
            sanitized_key = XSSPrevention.sanitize_input(key)

            # Sanitize value
            sanitized_value = XSSPrevention.sanitize_input(value)
            sanitized_payload[sanitized_key] = sanitized_value

        return sanitized_payload
    elif isinstance(payload, (list, tuple)):
        # Sanitize list items
        return [XSSPrevention.sanitize_input(item) for item in payload]
    else:
        # For other types (int, float, bool), return as-is
        return payload


@shared_task(
    base=ExternalServiceTask,
    bind=True,
    queue='external_api',
    priority=5,
    **task_retry_policy('external_api'),
    name="publish_mqtt"
)
def publish_mqtt(self, topic: str, payload: Union[str, Dict[str, Any], List[Any], int, float, bool]) -> Dict[str, Any]:
    """
    Securely publish MQTT message with comprehensive input validation.

    Args:
        topic: MQTT topic string
        payload: MQTT payload (JSON-serializable)

    Returns:
        Secure task response dictionary
    """
    from apps.core.error_handling import ErrorHandler
    from django.core.exceptions import ValidationError

    # Generate correlation ID for tracking
    import uuid
    correlation_id = str(uuid.uuid4())

    with self.task_context(topic=topic, payload_size=len(str(payload))):
        log_task_context('publish_mqtt', topic=topic, payload_size=len(str(payload)))

        # Record MQTT task metrics
        TaskMetrics.increment_counter('mqtt_publish_started', {
            'domain': 'external_api',
            'topic_prefix': topic.split('/')[0] if '/' in topic else topic
        })

    try:
        # Comprehensive input validation
        validated_topic = validate_mqtt_topic(topic)
        validated_payload = validate_mqtt_payload(payload)

        # Use circuit breaker for MQTT broker connection
        with self.external_service_call('mqtt_broker', timeout=10):
            publish_message(validated_topic, validated_payload)

        # Record success metrics
        TaskMetrics.increment_counter('mqtt_publish_success', {
            'topic_prefix': validated_topic.split('/')[0] if '/' in validated_topic else validated_topic
        })

        logger.info(
            f"[MQTT] Task completed successfully",
            extra={
                "correlation_id": correlation_id,
                "topic": validated_topic,
                "payload_type": type(validated_payload).__name__
            }
        )

        return ErrorHandler.create_secure_task_response(
            success=True,
            message="MQTT message published successfully",
            data={"topic": validated_topic, "correlation_id": correlation_id},
            correlation_id=correlation_id
        )

    except ValidationError as e:
        # Input validation failed - log and return secure error
        return ErrorHandler.handle_task_exception(
            e,
            task_name="publish_mqtt",
            task_params={"topic": topic, "payload_type": type(payload).__name__},
            correlation_id=correlation_id
        )

    except (DatabaseError, IntegrationException, TypeError, ValidationError, ValueError, json.JSONDecodeError) as e:
        # Other errors - log securely and retry if appropriate
        error_response = ErrorHandler.handle_task_exception(
            e,
            task_name="publish_mqtt",
            task_params={"topic": topic, "payload_type": type(payload).__name__},
            correlation_id=correlation_id
        )

        # For non-validation errors, attempt retry
        logger.error(f"[MQTT] Task failed, attempting retry", extra={"correlation_id": correlation_id})
        raise self.retry(exc=e)


@app.task(bind=True, default_retry_delay=300, max_retries=5, name="send_ticket_email")
def send_ticket_email(self, ticket=None, id=None):
    """
    Send ticket notification email with secure error handling.

    Args:
        ticket: Ticket object (optional)
        id: Ticket ID to look up (optional)

    Returns:
        Secure task response dictionary
    """
    from apps.y_helpdesk.models import Ticket
    from django.conf import settings
    from django.template.loader import render_to_string
    from apps.core.error_handling import ErrorHandler

    # Generate correlation ID for tracking
    import uuid
    correlation_id = str(uuid.uuid4())

    try:
        # Validate input parameters
        if not ticket and not id:
            return ErrorHandler.create_secure_task_response(
                success=False,
                message="Either ticket object or ticket ID must be provided",
                error_code="INVALID_PARAMETERS",
                correlation_id=correlation_id
            )

        # Get ticket if ID provided
        if not ticket and id:
            try:
                ticket = Ticket.objects.get(id=id)
            except Ticket.DoesNotExist:
                return ErrorHandler.create_secure_task_response(
                    success=False,
                    message="Ticket not found",
                    error_code="TICKET_NOT_FOUND",
                    correlation_id=correlation_id
                )

        if ticket:
            logger.info(f"Processing ticket email for ticket: {ticket.ticketno}",
                       extra={"correlation_id": correlation_id})

            emails = butils.get_email_recipents_for_ticket(ticket)
            logger.info(f"Email recipients found: {len(emails) if emails else 0}",
                       extra={"correlation_id": correlation_id})

            updated_or_created = "Created" if ticket.cdtz == ticket.mdtz else "Updated"

            # Handle potential null values securely
            site_name = ticket.bu.buname if ticket.bu else "Unknown Site"
            subject = f"Ticket with #{ticket.ticketno} is {updated_or_created}"
            if ticket.bu:
                subject += f" at site: {site_name}"

            context = {
                "subject": subject,
                "desc": ticket.ticketdesc or "",
                "template": ticket.ticketcategory.taname if ticket.ticketcategory else "General",
                "status": ticket.status or "Unknown",
                "createdon": ticket.cdtz.strftime("%Y-%m-%d %H:%M:%S") if ticket.cdtz else "Unknown",
                "modifiedon": ticket.mdtz.strftime("%Y-%m-%d %H:%M:%S") if ticket.mdtz else "Unknown",
                "modifiedby": ticket.muser.peoplename if ticket.muser else "System",
                "assignedto": (ticket.assignedtogroup.groupname if ticket.assignedtogroup else "Unassigned")
                if ticket.assignedtopeople_id in [None, 1]
                else (ticket.assignedtopeople.peoplename if ticket.assignedtopeople else "Unassigned"),
                "comments": ticket.comments or "",
                "priority": ticket.priority or "Normal",
                "level": ticket.level or "Standard",
            }

            # Only send email if there are valid recipients
            if emails:
                # Final safety validation to prevent SMTP failures
                from .utils import validate_email_list
                validated_emails = validate_email_list(emails)

                if validated_emails:
                    html_message = render_to_string("y_helpdesk/ticket_email.html", context)
                    msg = EmailMessage()
                    msg.body = html_message
                    msg.to = validated_emails
                    msg.subject = context["subject"]
                    msg.from_email = settings.DEFAULT_FROM_EMAIL
                    msg.content_subtype = "html"

                    msg.send()
                    logger.info("Ticket email sent successfully",
                               extra={"correlation_id": correlation_id, "recipient_count": len(validated_emails)})

                    return ErrorHandler.create_secure_task_response(
                        success=True,
                        message="Ticket email sent successfully",
                        data={"ticket_no": ticket.ticketno, "recipient_count": len(validated_emails)},
                        correlation_id=correlation_id
                    )
                else:
                    logger.warning(f"All email recipients failed validation for ticket {ticket.ticketno}",
                                  extra={"correlation_id": correlation_id})
                    return ErrorHandler.create_secure_task_response(
                        success=False,
                        message="No valid email recipients found",
                        error_code="NO_VALID_RECIPIENTS",
                        correlation_id=correlation_id
                    )
            else:
                logger.warning("No email recipients found for ticket",
                              extra={"correlation_id": correlation_id})
                return ErrorHandler.create_secure_task_response(
                    success=False,
                    message="No email recipients configured for ticket",
                    error_code="NO_RECIPIENTS",
                    correlation_id=correlation_id
                )
        else:
            return ErrorHandler.create_secure_task_response(
                success=False,
                message="Ticket not found",
                error_code="TICKET_NOT_FOUND",
                correlation_id=correlation_id
            )

    except (DatabaseError, IntegrationException, IntegrityError, ObjectDoesNotExist, TypeError, ValidationError, ValueError, json.JSONDecodeError) as e:
        # Use secure error handling - logs full details but returns sanitized response
        return ErrorHandler.handle_task_exception(
            e,
            task_name="send_ticket_email",
            task_params={"ticket_id": id, "has_ticket_object": ticket is not None},
            correlation_id=correlation_id
        )


@shared_task(
    base=IdempotentTask,
    name="auto_close_jobs",
    idempotency_ttl=SECONDS_IN_HOUR * 4,  # 4 hours (critical task category)
    bind=True
)
def autoclose_job(self, jobneedid=None):
    from django.template.loader import render_to_string
    from django.conf import settings

    context = {}
    try:
        # get all expired jobs
        Jobneed = apps.get_model("activity", "Jobneed")
        resp = {"story": "", "traceback": "", "id": []}
        expired = Jobneed.objects.get_expired_jobs(id=jobneedid)
        resp["story"] += f"total expired jobs = {len(expired)}\n"
        with transaction.atomic(using=get_current_db_name()):
            resp["story"] += f"using database: {get_current_db_name()}\n"
            for rec in expired:
                resp["story"] += f"processing record with id= {rec['id']}\n"
                resp["story"] += f"record category is {rec['ticketcategory__tacode']}\n"

                if rec["ticketcategory__tacode"] in [
                    "AUTOCLOSENOTIFY",
                    "RAISETICKETNOTIFY",
                ]:
                    logger.info("notifying through email...")
                    pdate = rec["plandatetime"] + timedelta(minutes=rec["ctzoffset"])
                    pdate = pdate.strftime("%d-%b-%Y %H:%M")
                    edate = rec["expirydatetime"] + timedelta(minutes=rec["ctzoffset"])
                    edate = edate.strftime("%d-%b-%Y %H:%M")

                    # Determine task type for better readability
                    task_type = "TOUR" if rec["identifier"] in ["INTERNALTOUR", "EXTERNALTOUR"] else rec["identifier"]
                    subject = f"AUTOCLOSE {task_type} planned on {pdate} not reported in time"
                    context = {
                        "subject": subject,
                        "buname": rec["bu__buname"],
                        "plan_dt": pdate,
                        "creatorname": rec["cuser__peoplename"],
                        "assignedto": rec["assignedto"],
                        "exp_dt": edate,
                        "show_ticket_body": False,
                        "identifier": rec["identifier"],
                        "jobdesc": rec["jobdesc"],
                    }

                    emails = butils.get_email_recipients(rec["bu_id"], rec["client_id"])
                    resp["story"] += f"email recipients: {len(emails) if emails else 0} users\n"
                    logger.info(f"Email recipients count: {len(emails) if emails else 0}")
                    msg = EmailMessage()
                    msg.subject = subject
                    msg.from_email = settings.DEFAULT_FROM_EMAIL
                    msg.to = emails
                    msg.content_subtype = "html"

                    if rec["ticketcategory__tacode"] == "RAISETICKETNOTIFY":
                        logger.info("ticket needs to be generated")
                        context["show_ticket_body"] = True
                        jobdesc = f'AUTOCLOSED {"TOUR" if rec["identifier"] in  ["INTERNALTOUR", "EXTERNALTOUR"] else rec["identifier"] } planned on {pdate} not reported in time'
                        # DB OPERATION
                        ticket_data = butils.create_ticket_for_autoclose(rec, jobdesc)
                        logger.info(f"{ticket_data}")
                        if (
                            esc := butils.get_escalation_of_ticket(ticket_data)
                            and esc["frequencyvalue"]
                            and esc["frequency"]
                        ):
                            context["escalation"] = True
                            context[
                                "next_escalation"
                            ] = f"{esc['frequencyvalue']} {esc['frequency']}"
                        created_at = ticket_data["cdtz"] + timedelta(
                            minutes=ticket_data["ctzoffset"]
                        )
                        created_at = created_at.strftime("%d-%b-%Y %H:%M")

                        context["ticketno"] = ticket_data["ticketno"]
                        context["tjobdesc"] = jobdesc
                        context["categoryname"] = rec["ticketcategory__taname"]
                        context["priority"] = rec["priority"]
                        context["status"] = "NEW"
                        context["tcreatedby"] = rec["cuser__peoplename"]
                        context["created_at"] = created_at
                        context["tkt_assignedto"] = rec["assignedto"]

                    html_message = render_to_string(
                        "activity/autoclose_mail.html", context=context
                    )
                    resp["story"] += f"context in email template is {context}\n"
                    msg.body = html_message
                    msg.send()
                    logger.info(f"mail sent, record_id:{rec['id']}")
                resp = butils.update_job_autoclose_status(rec, resp)

    except (DatabaseError, IntegrationException, IntegrityError, ObjectDoesNotExist, TypeError, ValidationError, ValueError, json.JSONDecodeError) as e:
        logger.critical(f"context in the template:{context}", exc_info=True)
        logger.error(
            "something went wrong while running autoclose_job()", exc_info=True
        )
        # Stack trace exposure security fix - log error securely without exposing details
        from apps.core.error_handling import ErrorHandler
        import uuid
        correlation_id = str(uuid.uuid4())
        ErrorHandler.handle_exception(e, context={"task": "autoclose_job"}, correlation_id=correlation_id)
        resp["error"] = {"code": "TASK_EXECUTION_ERROR", "correlation_id": correlation_id}
    return resp


@shared_task(
    base=IdempotentTask,
    name="ticket_escalation",
    idempotency_ttl=SECONDS_IN_HOUR * 4,  # 4 hours (critical task category)
    bind=True
)
def ticket_escalation(self):
    result = {"story": "", "traceback": "", "id": []}
    try:
        # get all records of tickets which can be escalated
        # Use new Django ORM implementation with atomic transaction for data consistency
        with transaction.atomic(using=get_current_db_name()):
            result["story"] += f"using database: {get_current_db_name()}\n"
            tickets = QueryRepository.get_ticketlist_for_escalation()
            result["story"] = f"Total tickets found for escalation are {len(tickets)}\n"
            # update ticket_history, assignments to people & groups, level, mdtz, modifiedon
            result = butils.update_ticket_data(tickets, result)
    except (DatabaseError, IntegrationException, IntegrityError, ObjectDoesNotExist, TypeError, ValidationError, ValueError, json.JSONDecodeError) as e:
        logger.critical("somwthing went wrong while ticket escalation", exc_info=True)
        # Stack trace exposure security fix - log error securely without exposing details
        from apps.core.error_handling import ErrorHandler
        import uuid
        correlation_id = str(uuid.uuid4())
        ErrorHandler.handle_exception(e, context={"task": "ticket_escalation"}, correlation_id=correlation_id)
        result["error"] = {"code": "TASK_EXECUTION_ERROR", "correlation_id": correlation_id}
    return result


@shared_task(
    base=IdempotentTask,
    name="send_reminder_email",
    idempotency_ttl=SECONDS_IN_HOUR * 2,  # 2 hours (email task category)
    bind=True
)
def send_reminder_email(self):
    from django.template.loader import render_to_string
    from django.conf import settings
    from apps.reminder.models import Reminder

    resp = {"story": "", "traceback": "", "id": []}
    try:
        # Use atomic transaction for reminder processing to ensure data consistency
        with transaction.atomic(using=get_current_db_name()):
            resp["story"] += f"using database: {get_current_db_name()}\n"
            # get all reminders which are not sent
            reminders = Reminder.objects.get_all_due_reminders()
            resp["story"] += f"total due reminders are: {len(reminders)}\n"
            logger.info(f"total due reminders are {len(reminders)}")

            for rem in reminders:
                resp["story"] += f"processing reminder with id: {rem['id']}"
                emails = utils.get_email_addresses(
                    [rem["people_id"], rem["cuser_id"], rem["muser_id"]], [rem["group_id"]]
                )
                resp["story"] += f"emails recipents are as follows {emails}\n"
                recipents = list(set(emails + rem["mailids"].split(",")))
                subject = f"Reminder For {rem['job__jobname']}"
                context = {
                    "job": rem["job__jobname"],
                    "plandatetime": rem["pdate"],
                    "jobdesc": rem["job__jobdesc"],
                    "sitename": rem["bu__buname"],
                    "creator": rem["cuser__peoplename"],
                    "modifier": rem["muser__peoplename"],
                    "subject": subject,
                }
                html_message = render_to_string(
                    "activity/reminder_mail.html", context=context
                )
                resp["story"] += f"context in email template is {context}\n"
                logger.info(f"Sending reminder mail with subject {subject}")

                msg = EmailMessage()
                msg.subject = subject
                msg.body = html_message
                msg.from_email = settings.DEFAULT_FROM_EMAIL
                msg.to = recipents
                msg.content_subtype = "html"
                # returns 1 if mail sent successfully else 0
                # Email sending and DB update wrapped in transaction for consistency
                if is_mail_sent := msg.send(fail_silently=True):
                    Reminder.objects.filter(id=rem["id"]).update(
                        status="SUCCESS", mdtz=timezone.now()
                    )
                else:
                    Reminder.objects.filter(id=rem["id"]).update(
                        status="FAILED", mdtz=timezone.now()
                    )
                resp["id"].append(rem["id"])
                logger.info(f"Reminder mail sent to {recipents} with subject {subject}")
    except (DatabaseError, IntegrationException, IntegrityError, ObjectDoesNotExist, TypeError, ValidationError, ValueError, json.JSONDecodeError) as e:
        logger.critical("Error while sending reminder email", exc_info=True)
        # Stack trace exposure security fix - log error securely without exposing details
        from apps.core.error_handling import ErrorHandler
        import uuid
        correlation_id = str(uuid.uuid4())
        ErrorHandler.handle_exception(e, context={"task": "send_reminder_email"}, correlation_id=correlation_id)
        resp["error"] = {"code": "TASK_EXECUTION_ERROR", "correlation_id": correlation_id}
    return resp


@shared_task(
    base=IdempotentTask,
    name="create_ppm_job",
    idempotency_ttl=SECONDS_IN_HOUR * 4,  # 4 hours (critical task category)
    bind=True
)
def create_ppm_job(self, jobid=None):
    F, d = {}, []
    # resp = {'story':"", 'traceback':""}
    startdtz = enddtz = msg = resp = None

    from apps.activity.models.job_model import Job
    from apps.activity.models.asset_model import Asset

    from apps.schedhuler.utils import (
        calculate_startdtz_enddtz_for_ppm,
        get_datetime_list,
        insert_into_jn_and_jnd,
        get_readable_dates,
        create_ppm_reminder,
    )

    result = {"story": "", "traceback": "", "id": []}

    try:
        # atomic transaction
        with transaction.atomic(using=get_current_db_name()):
            if jobid:
                jobs = Job.objects.filter(id=jobid).values(*utils.JobFields.fields)
            else:
                jobs = (
                    Job.objects.filter(
                        ~Q(jobname="NONE"),
                        ~Q(asset__runningstatus=Asset.RunningStatus.SCRAPPED),
                        identifier=Job.Identifier.PPM.value,
                        parent_id=1,
                    )
                    .select_related(
                        "asset", "pgroup", "cuser", "muser", "people", "qset"
                    )
                    .values(*utils.JobFields.fields)
                )

            if not jobs:
                msg = "No jobs found schedhuling terminated"
                result["story"] += f"{msg}\n"
                logger.warning(f"{msg}", exc_info=True)
            total_jobs = len(jobs)

            if total_jobs > 0 and jobs is not None:
                logger.info("processing jobs started found:= '%s' jobs", (len(jobs)))
                result["story"] += f"total jobs found {total_jobs}\n"
                for job in jobs:
                    result["story"] += f'\nprocessing job with id: {job["id"]}'
                    startdtz, enddtz = calculate_startdtz_enddtz_for_ppm(job)
                    logger.debug(
                        f"Jobs to be schedhuled from startdatetime {startdtz} to enddatetime {enddtz}"
                    )
                    DT, is_cron, resp = get_datetime_list(
                        job["cron"], startdtz, enddtz, resp
                    )
                    if not DT:
                        resp = {
                            "msg": "Please check your Valid From and Valid To dates"
                        }
                        continue
                    logger.debug(
                        "Jobneed will going to create for all this datetimes\n %s",
                        (pformat(get_readable_dates(DT))),
                    )
                    if not is_cron:
                        F[str(job["id"])] = {"cron": job["cron"]}
                    status, resp = insert_into_jn_and_jnd(job, DT, resp)
                    if status:
                        d.append(
                            {
                                "job": job["id"],
                                "jobname": job["jobname"],
                                "cron": job["cron"],
                                "iscron": is_cron,
                                "count": len(DT),
                                "status": status,
                            }
                        )
                create_ppm_reminder(d)
                if F:
                    result[
                        "story"
                    ] += f"create_ppm_job failed job schedule list {pformat(F)}\n"
                    logger.info(
                        f"create_ppm_job Failed job schedule list:={pformat(F)}"
                    )
                    for key, value in list(F.items()):
                        logger.info(f"create_ppm_job job_id: {key} | cron: {value}")
    except (DatabaseError, IntegrationException, IntegrityError, ObjectDoesNotExist, TypeError, ValidationError, ValueError, json.JSONDecodeError) as e:
        logger.critical("something went wrong create_ppm_job", exc_info=True)
        # Stack trace exposure security fix - log error securely without exposing details
        from apps.core.error_handling import ErrorHandler
        import uuid
        correlation_id = str(uuid.uuid4())
        ErrorHandler.handle_exception(e, context={"task": "create_ppm_job", "job_id": job.get("id")}, correlation_id=correlation_id)
        F[str(job["id"])] = {"error": "TASK_EXECUTION_ERROR", "correlation_id": correlation_id}

    return resp, F, d, result


@app.task(
    bind=True,
    default_retry_delay=300,
    max_retries=5,
    name="perform_facerecognition_bgt",
)
def perform_facerecognition_bgt(self, pel_uuid, peopleid, db="default"):
    result = {"story": "perform_facerecognition_bgt()\n", "traceback": ""}
    result["story"] += f"inputs are {pel_uuid = } {peopleid = }, {db = }\n"
    starttime = time.time()

    # Load distance threshold from FaceRecognitionModel (defaults to 0.3 if not found)
    FaceRecognitionModel = apps.get_model("face_recognition", "FaceRecognitionModel")
    try:
        face_model = FaceRecognitionModel.objects.filter(
            model_type='FACENET512',
            status='ACTIVE'
        ).first()
        distance_threshold = face_model.similarity_threshold if face_model else 0.3
    except (AttributeError, DatabaseError, IntegrationException, IntegrityError, ObjectDoesNotExist, TypeError, ValidationError, ValueError, json.JSONDecodeError):
        distance_threshold = 0.3  # Fallback to default

    logger.info(f"Using distance threshold: {distance_threshold}")
    result["story"] += f"Using distance threshold: {distance_threshold}\n"

    try:
        logger.info("perform_facerecognition ...start [+]")
        with transaction.atomic(using=get_current_db_name()):
            utils.set_db_for_router(db)
            if pel_uuid not in [None, "NONE", "", 1] and peopleid not in [
                None,
                "NONE",
                1,
                "",
            ]:
                # Retrieve the event picture
                Attachment = apps.get_model("activity", "Attachment")
                pel_att = Attachment.objects.get_people_pic(
                    pel_uuid, db
                )  # people event pic

                # Check if reference photo exists
                if not pel_att:
                    logger.info(f"No reference photo found for attendance UUID: {pel_uuid}")
                    result["story"] += f"No reference photo found for comparison. Face recognition skipped.\n"
                    return result

                # Retrieve the default profile picture of the person
                People = apps.get_model("peoples", "People")
                people_obj = People.objects.get(id=peopleid)
                # Handle both old /youtility4_media/ and current /media/ URL patterns
                img_url = people_obj.peopleimg.url
                img_path = img_url.replace("/youtility4_media/", "").replace("/media/", "")
                default_peopleimg = f'{settings.MEDIA_ROOT}/{img_path}'

                # Use a placeholder image if the default one is blank
                default_peopleimg = (
                    static("assets/media/images/blank.png")
                    if default_peopleimg.endswith("blank.png")
                    else default_peopleimg
                )

                if default_peopleimg and hasattr(pel_att, 'people_event_pic') and pel_att.people_event_pic:
                    images_info = f"default image path:{default_peopleimg} and uploaded file path:{pel_att.people_event_pic}"
                    logger.info(f"{images_info}")
                    result["story"] += f"{images_info}\n"

                    # Perform face verification using Unified Service
                    from apps.face_recognition.services import get_face_recognition_service
                    import uuid

                    correlation_id = str(uuid.uuid4())
                    face_service = get_face_recognition_service()

                    # Use the unified service for verification
                    verification_result = face_service.verify_face(
                        user_id=peopleid,
                        image_path=pel_att.people_event_pic,
                        correlation_id=correlation_id
                    )

                    logger.info(f"Face verification completed: {verification_result}")
                    result["story"] += f"Face verification completed via unified service\n"
                    result["story"] += f"Verified: {verification_result.verified}, "
                    result["story"] += f"Similarity: {verification_result.similarity_score:.4f}, "
                    result["story"] += f"Distance: {verification_result.distance:.4f}, "
                    result["story"] += f"Confidence: {verification_result.confidence_score:.4f}\n"

                    if verification_result.error_message:
                        result["story"] += f"Error: {verification_result.error_message}\n"

                    if verification_result.quality_issues:
                        result["story"] += f"Quality issues detected: {', '.join(verification_result.quality_issues)}\n"

                    # Update attendance record using unified service
                    updated = face_service.update_attendance_with_result(
                        pel_uuid=pel_uuid,
                        user_id=peopleid,
                        result=verification_result,
                        database=db
                    )

                    if updated:
                        logger.info("Face recognition results updated in attendance record")
                        result["story"] += "Attendance record updated successfully\n"
                    else:
                        logger.warning("Failed to update attendance record")
                        result["story"] += "Failed to update attendance record\n"
    except ValueError as v:
        logger.error(
            "face recognition image not found or face is not there...", exc_info=True
        )
        # Stack trace exposure security fix - log error securely without exposing details
        from apps.core.error_handling import ErrorHandler
        import uuid
        correlation_id = str(uuid.uuid4())
        ErrorHandler.handle_exception(v, context={"task": "face_recognition"}, correlation_id=correlation_id)
        result["error"] = {"code": "TASK_EXECUTION_ERROR", "correlation_id": correlation_id}
    except (AttributeError, DatabaseError, IntegrationException, IntegrityError, ObjectDoesNotExist, TypeError, ValidationError, ValueError, json.JSONDecodeError) as e:
        logger.critical(
            "something went wrong! while performing face-recognition in background",
            exc_info=True,
        )
        # Stack trace exposure security fix - log error securely without exposing details
        from apps.core.error_handling import ErrorHandler
        import uuid
        correlation_id = str(uuid.uuid4())
        ErrorHandler.handle_exception(e, context={"task": "face_recognition"}, correlation_id=correlation_id)
        result["error"] = {"code": "TASK_EXECUTION_ERROR", "correlation_id": correlation_id}
        self.retry(e)
        raise
    endtime = time.time()
    total_time = endtime - starttime
    logger.info(f"Total time take for this function is {total_time}")
    return result


@app.task(bind=True, name="alert_sendmail")
def alert_sendmail(self, id, event, atts=False):
    """
    takes uuid, ownername (which is the model name) and event (observation or deviation)
    gets the record from model if record has alerts set to true then send mail based on event
    """
    Jobneed = apps.get_model("activity", "Jobneed")
    from .utils import alert_deviation, alert_observation

    obj = Jobneed.objects.filter(id=id).first()
    if event == "observation" and obj:
        return alert_observation(obj, atts)
    if event == "deviation" and obj:
        return alert_deviation(obj, atts)


@shared_task(bind=True, name="task_every_min")
def task_every_min(self):
    from django.utils import timezone

    return f"task completed at {timezone.now()}"


@shared_task(bind=True, name="send_report_on_email")
def send_report_on_email(self, formdata, json_report):
    import mimetypes
    import json

    jsonresp = {"story": "", "traceback": ""}
    try:
        jsonresp["story"] += f"formdata: {formdata}"
        file_buffer = BytesIO()
        jsonrep = json.loads(json_report)
        report_content = base64.b64decode(jsonrep["report"])
        file_buffer.write(report_content)
        file_buffer.seek(0)
        mime_type, encoding = mimetypes.guess_type(f'.{formdata["format"]}')
        email = EmailMessage(
            subject=f"Per your request, please find the report attached from {settings.COMPANYNAME}",
            from_email=settings.EMAIL_HOST_USER,
            to=formdata["to_addr"],
            cc=formdata["cc"],
            body=formdata.get("email_body"),
        )
        email.attach(
            filename=f'{formdata["report_name"]}.{formdata["format"]}',
            content=file_buffer.getvalue(),
            mimetype=mime_type,
        )
        email.send()
        jsonresp["story"] += "email sent"
    except (AttributeError, DatabaseError, FileNotFoundError, IOError, IntegrationException, IntegrityError, OSError, ObjectDoesNotExist, PermissionError, TypeError, ValidationError, ValueError, json.JSONDecodeError) as e:
        logger.critical(
            "something went wrong while sending report on email", exc_info=True
        )
        # Stack trace exposure security fix - log error securely without exposing details
        from apps.core.error_handling import ErrorHandler
        import uuid
        correlation_id = str(uuid.uuid4())
        ErrorHandler.handle_exception(e, context={"task": "email_report"}, correlation_id=correlation_id)
        jsonresp["error"] = {"code": "TASK_EXECUTION_ERROR", "correlation_id": correlation_id}
    return jsonresp


@shared_task(bind=True, name="create_report_history")
def create_report_history(self, formdata, userid, buid, EI):
    jsonresp = {"story": "", "traceback": ""}
    try:
        # Use atomic transaction for report history creation to ensure data consistency
        with transaction.atomic(using=get_current_db_name()):
            jsonresp["story"] += f"using database: {get_current_db_name()}\n"
            ReportHistory = apps.get_model("reports", "ReportHistory")
            obj = ReportHistory.objects.create(
                traceback=EI[2] if EI[0] else None,
                user_id=userid,
                report_name=formdata["report_name"],
                params={"params": f"{formdata}"},
                export_type=formdata["export_type"],
                bu_id=buid,
                ctzoffset=formdata["ctzoffset"],
                cc_mails=formdata["cc"],
                to_mails=formdata["to_addr"],
                email_body=formdata["email_body"],
            )
            jsonresp["story"] += f"A Report history object created with pk: {obj.pk}"
    except (AttributeError, DatabaseError, FileNotFoundError, IOError, IntegrationException, IntegrityError, OSError, ObjectDoesNotExist, PermissionError, TypeError, ValidationError, ValueError, json.JSONDecodeError) as e:
        logger.critical(
            "something went wron while running create_report_history()", exc_info=True
        )
        # Stack trace exposure security fix - log error securely without exposing details
        from apps.core.error_handling import ErrorHandler
        import uuid
        correlation_id = str(uuid.uuid4())
        ErrorHandler.handle_exception(e, context={"task": "email_notification"}, correlation_id=correlation_id)
        jsonresp["error"] = {"code": "TASK_EXECUTION_ERROR", "correlation_id": correlation_id}
    return jsonresp


@shared_task(bind=True, name="send_email_notification_for_workpermit_approval")
def send_email_notification_for_workpermit_approval(
    self,
    womid,
    approvers,
    approvers_code,
    sitename,
    workpermit_status,
    permit_name,
    workpermit_attachment,
    vendor_name,
    client_id,
):
    jsonresp = {"story": "", "traceback": ""}
    try:
        from django.apps import apps
        from django.template.loader import render_to_string

        Wom = apps.get_model("work_order_management", "Wom")
        People = apps.get_model("peoples", "People")
        wp_details = Wom.objects.get_wp_answers(womid)
        wp_obj = Wom.objects.get(id=womid)
        # logger.info(f"wp_details: {wp_details}")
        logger.info(f"Approvers: {approvers}")
        jsonresp["story"] += f"\n{wp_details}"
        logger.info(f"WP Details{wp_details}")
        if wp_details:
            qset = People.objects.filter(peoplecode__in=approvers_code)
            logger.info(f"Qset {qset}")
            for p in qset.values("email", "id"):
                logger.info(f"Sending email to user", extra={'user_id': p['id']})
                logger.info(
                    f"{permit_name}-{wp_obj.other_data['wp_seqno']}-{sitename}-Approval Pending"
                )
                msg = EmailMessage()
                msg.subject = f"{permit_name}-{wp_obj.other_data['wp_seqno']}-{sitename}-Approval Pending"
                msg.to = [p["email"]]
                msg.from_email = settings.DEFAULT_FROM_EMAIL
                cxt = {
                    "peopleid": p["id"],
                    "HOST": settings.HOST,
                    "workpermitid": womid,
                    "sitename": sitename,
                    "status": workpermit_status,
                    "permit_no": wp_obj.other_data["wp_seqno"],
                    "permit_name": permit_name,
                    "vendor_name": vendor_name,
                    "client_id": client_id,
                }
                logger.info(f"Context: {cxt}")
                html = render_to_string(
                    "work_order_management/workpermit_approver_action.html", context=cxt
                )
                msg.body = html
                msg.content_subtype = "html"
                logger.info(f"Attachment {workpermit_attachment}")
                msg.attach_file(workpermit_attachment, mimetype="application/pdf")
                msg.send()
                logger.info(f"Email sent successfully", extra={'user_id': p['id']})
                jsonresp["story"] += f"Email sent to user {p['id']}"
        jsonresp["story"] += f"A {permit_name} email sent of pk: {womid}: "
    except (AttributeError, DatabaseError, FileNotFoundError, IOError, IntegrationException, IntegrityError, OSError, ObjectDoesNotExist, PermissionError, TypeError, ValidationError, ValueError, json.JSONDecodeError) as e:
        logger.critical(
            "Something went wrong while running send_email_notification_for_wp_verifier",
            exc_info=True,
        )
        # Stack trace exposure security fix - log error securely without exposing details
        from apps.core.error_handling import ErrorHandler
        import uuid
        correlation_id = str(uuid.uuid4())
        ErrorHandler.handle_exception(e, context={"task": "email_notification"}, correlation_id=correlation_id)
        jsonresp["error"] = {"code": "TASK_EXECUTION_ERROR", "correlation_id": correlation_id}
    return jsonresp


@shared_task(bind=True, name="send_email_notification_for_wp_verifier")
def send_email_notification_for_wp_verifier(
    self,
    womid,
    verifiers,
    sitename,
    workpermit_status,
    permit_name,
    vendor_name,
    client_id,
    workpermit_attachment=None,
):
    jsonresp = {"story": "", "traceback": ""}
    try:
        from django.apps import apps
        from django.template.loader import render_to_string

        Wom = apps.get_model("work_order_management", "Wom")
        People = apps.get_model("peoples", "People")
        wp_details = Wom.objects.get_wp_answers(womid)
        wp_obj = Wom.objects.get(id=womid)
        permit_no = wp_obj.other_data["wp_seqno"]
        jsonresp["story"] += f"\n{wp_details}"
        if wp_details:
            qset = People.objects.filter(peoplecode__in=verifiers)
            for p in qset.values("email", "id"):
                logger.info(f"Sending email to user", extra={'user_id': p['id']})
                msg = EmailMessage()
                msg.subject = f"{permit_name}-{wp_obj.other_data['wp_seqno']}-{sitename}-Verification Pending"
                msg.to = [p["email"]]
                msg.from_email = settings.DEFAULT_FROM_EMAIL
                cxt = {
                    "peopleid": p["id"],
                    "HOST": settings.HOST,
                    "workpermitid": womid,
                    "sitename": sitename,
                    "status": workpermit_status,
                    "permit_no": wp_obj.other_data["wp_seqno"],
                    "permit_name": permit_name,
                    "vendor_name": vendor_name,
                    "client_id": client_id,
                }
                html = render_to_string(
                    "work_order_management/workpermit_verifier_action.html", context=cxt
                )
                msg.body = html
                msg.content_subtype = "html"
                msg.attach_file(workpermit_attachment, mimetype="application/pdf")
                msg.send()
                logger.info(f"Email sent successfully", extra={'user_id': p['id']})
                jsonresp["story"] += f"Email sent to user {p['id']}"
        jsonresp["story"] += f"A {permit_name} email sent of pk: {womid}: "
    except (AttributeError, DatabaseError, FileNotFoundError, IOError, IntegrationException, IntegrityError, OSError, ObjectDoesNotExist, PermissionError, TypeError, ValidationError, ValueError, json.JSONDecodeError) as e:
        logger.critical(
            "Something went wrong while running send_email_notification_for_wp_verifier",
            exc_info=True,
        )
        # Stack trace exposure security fix - log error securely without exposing details
        from apps.core.error_handling import ErrorHandler
        import uuid
        correlation_id = str(uuid.uuid4())
        ErrorHandler.handle_exception(e, context={"task": "email_notification"}, correlation_id=correlation_id)
        jsonresp["error"] = {"code": "TASK_EXECUTION_ERROR", "correlation_id": correlation_id}
    return jsonresp


@shared_task(bind=True, name="send_email_notification_for_wp_from_mobile_for_verifier")
def send_email_notification_for_wp_from_mobile_for_verifier(
    self,
    womid,
    verifiers,
    sitename,
    workpermit_status,
    permit_name,
    vendor_name,
    client_id,
    workpermit_attachment=None,
):
    jsonresp = {"story": "", "traceback": ""}
    try:
        from django.apps import apps
        from django.template.loader import render_to_string

        Wom = apps.get_model("work_order_management", "Wom")
        People = apps.get_model("peoples", "People")
        wp_details = Wom.objects.get_wp_answers(womid)
        wp_obj = Wom.objects.get(id=womid)
        jsonresp["story"] += f"\n{wp_details}"
        logger.info(f"Vendor name: {vendor_name} , client_id: {client_id}")
        if wp_details:
            qset = People.objects.filter(peoplecode__in=verifiers)
            for p in qset.values("email", "id"):
                logger.info(f"Sending email to user", extra={'user_id': p['id']})
                msg = EmailMessage()
                msg.subject = f"{permit_name}-{wp_obj.other_data['wp_seqno']}-{sitename}-Verification Pending"
                msg.to = [p["email"]]
                msg.from_email = settings.DEFAULT_FROM_EMAIL
                cxt = {
                    "peopleid": p["id"],
                    "HOST": settings.HOST,
                    "workpermitid": womid,
                    "sitename": sitename,
                    "status": workpermit_status,
                    "permit_no": wp_obj.other_data["wp_seqno"],
                    "permit_name": permit_name,
                    "vendor_name": vendor_name,
                    "client_id": client_id,
                }
                html = render_to_string(
                    "work_order_management/workpermit_verifier_action.html", context=cxt
                )
                msg.body = html
                msg.content_subtype = "html"
                msg.attach_file(workpermit_attachment, mimetype="application/pdf")
                msg.send()
                logger.info(f"Email sent successfully", extra={'user_id': p['id']})
                jsonresp["story"] += f"Email sent to user {p['id']}"
        jsonresp["story"] += f"A {permit_name} email sent of pk: {womid}: "
    except (AttributeError, DatabaseError, FileNotFoundError, IOError, IntegrationException, IntegrityError, OSError, ObjectDoesNotExist, PermissionError, TypeError, ValidationError, ValueError, json.JSONDecodeError) as e:
        logger.critical(
            "Something went wrong while running send_email_notification_for_wp_verifier",
            exc_info=True,
        )
        # Stack trace exposure security fix - log error securely without exposing details
        from apps.core.error_handling import ErrorHandler
        import uuid
        correlation_id = str(uuid.uuid4())
        ErrorHandler.handle_exception(e, context={"task": "email_notification"}, correlation_id=correlation_id)
        jsonresp["error"] = {"code": "TASK_EXECUTION_ERROR", "correlation_id": correlation_id}
    return jsonresp


@shared_task(bind=True, name="send_email_notification_for_wp")
def send_email_notification_for_wp(
    self,
    womid,
    qsetid,
    approvers,
    client_id,
    bu_id,
    sitename,
    workpermit_status,
    vendor_name,
):
    jsonresp = {"story": "", "traceback": ""}
    try:
        from django.apps import apps
        from django.template.loader import render_to_string

        Wom = apps.get_model("work_order_management", "Wom")
        People = apps.get_model("peoples", "People")
        wp_details = Wom.objects.get_wp_answers(womid)
        wp_obj = Wom.objects.get(id=womid)
        jsonresp["story"] += f"\n{wp_details}"
        if wp_details:
            qset = People.objects.filter(peoplecode__in=approvers)
            logger.info("Qset: ", qset)
            for p in qset.values("email", "id"):
                logger.info("Sending email to user", extra={'user_id': p['id']})
                jsonresp["story"] += f"sending email to user {p['id']}"
                msg = EmailMessage()
                msg.subject = f"General Work Permit #{wp_obj.other_data['wp_seqno']} needs your approval"
                msg.to = [p["email"]]
                msg.from_email = settings.DEFAULT_FROM_EMAIL
                cxt = {
                    "peopleid": p["id"],
                    "HOST": settings.HOST,
                    "workpermitid": womid,
                    "sitename": sitename,
                    "status": workpermit_status,
                    "permit_no": wp_obj.other_data["wp_seqno"],
                    "permit_name": "General Work Permit",
                    "vendor_name": vendor_name,
                }
                html = render_to_string(
                    "work_order_management/workpermit_approver_action.html", context=cxt
                )
                msg.body = html
                # msg.attach_file(workpermit_attachment,mimetype='application/pdf')
                msg.content_subtype = "html"
                # msg.attach_file(workpermit_attachment, mimetype='application/pdf')
                msg.send()
                logger.info("Email sent successfully", extra={'user_id': p['id']})
                jsonresp["story"] += f"email sent to user {p['id']}"
        jsonresp["story"] += f"A Workpermit email sent of pk: {womid}"
    except (AttributeError, DatabaseError, FileNotFoundError, IOError, IntegrationException, IntegrityError, OSError, ObjectDoesNotExist, PermissionError, TypeError, ValidationError, ValueError, json.JSONDecodeError) as e:
        logger.critical(
            "something went wron while running send_email_notification_for_wp",
            exc_info=True,
        )
        # Stack trace exposure security fix - log error securely without exposing details
        from apps.core.error_handling import ErrorHandler
        import uuid
        correlation_id = str(uuid.uuid4())
        ErrorHandler.handle_exception(e, context={"task": "email_notification"}, correlation_id=correlation_id)
        jsonresp["error"] = {"code": "TASK_EXECUTION_ERROR", "correlation_id": correlation_id}
    return jsonresp


@shared_task(
    bind=True, name="send_email_notification_for_vendor_and_security_of_wp_cancellation"
)
def send_email_notification_for_vendor_and_security_of_wp_cancellation(
    self,
    wom_id,
    sitename,
    workpermit_status,
    vendor_name,
    permit_name,
    permit_no,
    submit_work_permit=False,
    submit_work_permit_from_mobile=False,
):
    jsonresp = {"story": "", "traceback": ""}
    try:
        from apps.work_order_management.models import Wom, WomDetails
        from apps.onboarding.models import Bt
        from django.template.loader import render_to_string
        from apps.work_order_management.models import Vendor
        from apps.peoples.models import People

        wom = Wom.objects.filter(parent_id=wom_id)
        site_id = wom[0].bu_id
        sitename = Bt.objects.get(id=site_id).buname

        logger.info(f"THe Site Name for vendor and security is {sitename}")
        # sitename = Bt.objects.get((Wom.objects.get(id=wom_id).client.id)).buname
        sections = [x for x in wom]
        if not submit_work_permit_from_mobile:
            if submit_work_permit:
                wom_detail = sections[-2].id
            else:
                wom_detail = sections[-1].id
        else:
            if submit_work_permit:
                wom_detail = sections[-2].id
        logger.info(f"sections: {sections}")
        logger.info(f"wom_detail: {wom_detail}")
        vendor_email = Vendor.objects.get(id=wom[0].vendor.id).email
        wom_detail_email_section = WomDetails.objects.filter(wom_id=wom_detail)
        logger.info(f"WOM Detail Answer Section: {wom_detail_email_section}")
        logger.info("Vendor email notification prepared")
        logger.info(f"WOM Detail Email Section: {wom_detail_email_section}")
        parent_wom = Wom.objects.get(id=wom_id).remarks
        cancelled_by = People.objects.get(
            peoplecode=parent_wom[0].get("people", "")
        ).peoplename
        remarks = parent_wom[0].get(
            "remarks",
        )
        for emailsection in wom_detail_email_section:
            logger.info("Email section processed")
            emails = emailsection.answer.split(",")
            for email in emails:
                msg = EmailMessage()
                msg.subject = (
                    f"{permit_name}-{permit_no}-{sitename}-{workpermit_status}"
                )
                msg.to = [email]
                msg.from_email = settings.DEFAULT_FROM_EMAIL
                cxt = {
                    "permit_name": permit_name,
                    "sitename": sitename,
                    "status": workpermit_status,
                    "vendor_name": vendor_name,
                    "permit_no": permit_no,
                    "cancelled_by": cancelled_by,
                    "remarks": remarks,
                }
                html = render_to_string(
                    "work_order_management/workpermit_cancellation.html", context=cxt
                )
                msg.body = html
                msg.content_subtype = "html"
                msg.send()
                logger.info("Email sent successfully")
    except (AttributeError, DatabaseError, FileNotFoundError, IOError, IntegrationException, IntegrityError, OSError, ObjectDoesNotExist, PermissionError, TypeError, ValidationError, ValueError, json.JSONDecodeError) as e:
        logger.critical(
            "something went wrong while sending email to vendor and security",
            exc_info=True,
        )
        # Stack trace exposure security fix - log error securely without exposing details
        from apps.core.error_handling import ErrorHandler
        import uuid
        correlation_id = str(uuid.uuid4())
        ErrorHandler.handle_exception(e, context={"task": "email_notification"}, correlation_id=correlation_id)
        jsonresp["error"] = {"code": "TASK_EXECUTION_ERROR", "correlation_id": correlation_id}
    return jsonresp


@shared_task(bind=True, name="send_email_notification_for_vendor_and_security_for_rwp")
def send_email_notification_for_vendor_and_security_for_rwp(
    self,
    wom_id,
    sitename,
    workpermit_status,
    vendor_name,
    pdf_path,
    permit_name,
    permit_no,
):
    jsonresp = {"story": "", "traceback": ""}
    try:
        from apps.work_order_management.models import Wom, WomDetails
        from apps.onboarding.models import Bt
        from django.template.loader import render_to_string
        from apps.work_order_management.models import Vendor

        wom = Wom.objects.filter(parent_id=wom_id).order_by("id")
        site_id = wom[0].bu_id
        sitename = Bt.objects.get(id=site_id).buname

        logger.info(f"THe Site Name for vendor and security is {sitename}")
        # sitename = Bt.objects.get((Wom.objects.get(id=wom_id).client.id)).buname
        sections = [x for x in wom]
        # if not submit_work_permit_from_mobile:
        #     wom_detail = sections[-2].id
        # else:
        #     wom_detail = sections[-2].id

        wom_detail = sections[-2].id
        logger.info(f"sections: {sections}")
        logger.info(f"wom_detail: {wom_detail}")
        vendor_email = Vendor.objects.get(id=wom[0].vendor.id).email
        wom_detail_email_section = WomDetails.objects.filter(wom_id=wom_detail)
        logger.info(f"WOM Detail Answer Section: {wom_detail_email_section}")
        logger.info("Vendor email notification prepared")
        logger.info(f"WOM Detail Email Section: {wom_detail_email_section}")
        for emailsection in wom_detail_email_section:
            logger.info("Email section processed")
            emails = emailsection.answer.split(",")
            for email in emails:
                msg = EmailMessage()
                msg.subject = (
                    f"{permit_name}-{permit_no}-{sitename}-{workpermit_status}"
                )
                msg.to = [email]
                msg.from_email = settings.DEFAULT_FROM_EMAIL
                cxt = {
                    "permit_name": permit_name,
                    "sitename": sitename,
                    "status": workpermit_status,
                    "vendor_name": vendor_name,
                    "permit_no": permit_no,
                }
                html = render_to_string(
                    "work_order_management/workpermit_vendor.html", context=cxt
                )
                msg.body = html
                msg.content_subtype = "html"
                msg.attach_file(pdf_path, mimetype="application/pdf")
                msg.send()
                logger.info("Email sent successfully")
    except (AttributeError, DatabaseError, FileNotFoundError, IOError, IntegrationException, IntegrityError, OSError, ObjectDoesNotExist, PermissionError, TypeError, ValidationError, ValueError, json.JSONDecodeError) as e:
        logger.critical(
            "something went wrong while sending email to vendor and security",
            exc_info=True,
        )
        # Stack trace exposure security fix - log error securely without exposing details
        from apps.core.error_handling import ErrorHandler
        import uuid
        correlation_id = str(uuid.uuid4())
        ErrorHandler.handle_exception(e, context={"task": "email_notification"}, correlation_id=correlation_id)
        jsonresp["error"] = {"code": "TASK_EXECUTION_ERROR", "correlation_id": correlation_id}
    return jsonresp


@shared_task(
    bind=True, name="send_email_notification_for_vendor_and_security_after_approval"
)
def send_email_notification_for_vendor_and_security_after_approval(
    self,
    wom_id,
    sitename,
    workpermit_status,
    vendor_name,
    pdf_path,
    permit_name,
    permit_no,
):
    jsonresp = {"story": "", "traceback": ""}
    try:
        from apps.work_order_management.models import Wom, WomDetails
        from apps.onboarding.models import Bt
        from django.template.loader import render_to_string
        from apps.work_order_management.models import Vendor

        wom = Wom.objects.filter(parent_id=wom_id).order_by("id")
        site_id = wom[0].bu_id
        sitename = Bt.objects.get(id=site_id).buname

        logger.info(f"THe Site Name for vendor and security is {sitename}")
        sections = [x for x in wom]
        wom_detail = sections[-1].id
        logger.info(f"sections: {sections}")
        logger.info(f"wom_detail: {wom_detail}")
        vendor_email = Vendor.objects.get(id=wom[0].vendor.id).email
        wom_detail_email_section = WomDetails.objects.filter(wom_id=wom_detail)
        logger.info(f"WOM Detail Answer Section: {wom_detail_email_section}")
        logger.info("Vendor email notification prepared")
        logger.info(f"WOM Detail Email Section: {wom_detail_email_section}")
        for emailsection in wom_detail_email_section:
            logger.info("Email section processed")
            emails = emailsection.answer.split(",")
            for email in emails:
                msg = EmailMessage()
                msg.subject = (
                    f"{permit_name}-{permit_no}-{sitename}-{workpermit_status}"
                )
                msg.to = [email]
                msg.from_email = settings.DEFAULT_FROM_EMAIL
                cxt = {
                    "permit_name": permit_name,
                    "sitename": sitename,
                    "status": workpermit_status,
                    "vendor_name": vendor_name,
                    "permit_no": permit_no,
                }
                html = render_to_string(
                    "work_order_management/workpermit_vendor.html", context=cxt
                )
                msg.body = html
                msg.content_subtype = "html"
                msg.attach_file(pdf_path, mimetype="application/pdf")
                msg.send()
                logger.info("Email sent successfully")
    except (AttributeError, DatabaseError, FileNotFoundError, IOError, IntegrationException, IntegrityError, OSError, ObjectDoesNotExist, PermissionError, TypeError, ValidationError, ValueError, json.JSONDecodeError) as e:
        logger.critical(
            "something went wrong while sending email to vendor and security",
            exc_info=True,
        )
        # Stack trace exposure security fix - log error securely without exposing details
        from apps.core.error_handling import ErrorHandler
        import uuid
        correlation_id = str(uuid.uuid4())
        ErrorHandler.handle_exception(e, context={"task": "email_notification"}, correlation_id=correlation_id)
        jsonresp["error"] = {"code": "TASK_EXECUTION_ERROR", "correlation_id": correlation_id}
    return jsonresp


@shared_task(bind=True, name="send_email_notification_for_sla_vendor")
def send_email_notification_for_sla_vendor(self, wom_id, report_attachment, sitename):
    jsonresp = {"story": "", "traceback": ""}
    try:
        from apps.work_order_management.models import Wom, WomDetails
        from apps.work_order_management.models import Vendor
        from django.template.loader import render_to_string
        from dateutil.relativedelta import relativedelta
        from apps.work_order_management.utils import (
            approvers_email_and_name,
            get_peoplecode,
        )
        from apps.work_order_management.views import SLA_View

        monthly_choices = SLA_View.MONTH_CHOICES
        wom = Wom.objects.get(uuid=wom_id)
        is_month_present = wom.other_data.get("month", None)
        if not is_month_present:
            month_no = wom.cdtz.month - 1
            if month_no == 0:
                month_no = 12
                year = wom.cdtz.year - 1
            else:
                year = wom.cdtz.year
            month_name = monthly_choices.get(f"{month_no}")
        else:
            month_name = is_month_present
            year = wom.cdtz.year
            if month_name == "December":
                year = wom.cdtz.year - 1
        vendor_details = Vendor.objects.filter(id=wom.vendor_id).values("name", "email")
        vendor_name = vendor_details[0].get("name")
        vendor_email = vendor_details[0].get("email")
        wp_approvers = wom.other_data["wp_approvers"]
        people_codes = get_peoplecode(wp_approvers)
        approver_emails, approver_name = approvers_email_and_name(people_codes)
        msg = EmailMessage()
        sla_seqno = wom.other_data["wp_seqno"]
        msg.subject = (
            f" {sitename}: Vendor Performance of {vendor_name} of {month_name}-{year}"
        )
        msg.to = [vendor_email]
        msg.cc = approver_emails
        msg.from_email = settings.DEFAULT_FROM_EMAIL
        approvedby = ""
        for name in approver_name:
            approvedby += name + " "

        cxt = {
            "sla_report_no": sla_seqno,
            "sitename": sitename,
            "report_name": "Vendor Performance Report",
            "approvedby": approvedby,
            "service_month": f"{month_name} {year}",
        }
        html = render_to_string("work_order_management/sla_vendor.html", context=cxt)
        msg.body = html
        msg.content_subtype = "html"

        msg.attach_file(report_attachment, mimetype="application/pdf")
        msg.send()
        logger.info(f"email sent to {vendor_email}")
    except (AttributeError, DatabaseError, FileNotFoundError, IOError, IntegrationException, IntegrityError, OSError, ObjectDoesNotExist, PermissionError, TypeError, ValidationError, ValueError, json.JSONDecodeError) as e:
        logger.critical(
            "something went wrong while sending email to vendor and security",
            exc_info=True,
        )
        # Stack trace exposure security fix - log error securely without exposing details
        from apps.core.error_handling import ErrorHandler
        import uuid
        correlation_id = str(uuid.uuid4())
        ErrorHandler.handle_exception(e, context={"task": "email_notification"}, correlation_id=correlation_id)
        jsonresp["error"] = {"code": "TASK_EXECUTION_ERROR", "correlation_id": correlation_id}
    return jsonresp


@shared_task(name="move_media_to_cloud_storage")
def move_media_to_cloud_storage():
    resp = {}
    try:
        logger.info("move_media_to_cloud_storage execution started [+]")
        directory_path = f"{settings.MEDIA_ROOT}/transactions/"
        path_list = get_files(directory_path)
        move_files_to_GCS(path_list, settings.BUCKET)
        del_empty_dir(directory_path)
        pass
    except (AttributeError, DatabaseError, FileNotFoundError, IOError, IntegrationException, IntegrityError, OSError, ObjectDoesNotExist, PermissionError, TypeError, ValidationError, ValueError, json.JSONDecodeError) as exc:
        logger.critical(
            "something went wron while running create_report_history()", exc_info=True
        )
        # Stack trace exposure security fix - log error securely without exposing details
        from apps.core.error_handling import ErrorHandler
        import uuid
        correlation_id = str(uuid.uuid4())
        ErrorHandler.handle_exception(e, context={"task": "send_reminder_email"}, correlation_id=correlation_id)
        resp["error"] = {"code": "TASK_EXECUTION_ERROR", "correlation_id": correlation_id}
    else:
        resp["msg"] = "Completed without any errors"
    return resp


@shared_task(
    base=IdempotentTask,
    name="create_scheduled_reports",
    idempotency_ttl=SECONDS_IN_HOUR * 24,  # 24 hours (report task category)
    bind=True
)
def create_scheduled_reports(self):
    state_map = {"not_generated": 0, "skipped": 0, "generated": 0, "processed": 0}

    resp = dict()
    try:
        data = get_scheduled_reports_fromdb()
        logger.info(f"Found {len(data)} for reports for generation in background")
        if data:
            for record in data:
                state_map = generate_scheduled_report(record, state_map)
        resp["msg"] = f"Total {len(data)} report/reports processed at {timezone.now()}"
    except (AttributeError, DatabaseError, FileNotFoundError, IOError, IntegrationException, IntegrityError, OSError, ObjectDoesNotExist, PermissionError, TypeError, ValidationError, ValueError, json.JSONDecodeError) as e:
        # Stack trace exposure security fix - log error securely without exposing details
        from apps.core.error_handling import ErrorHandler
        import uuid
        correlation_id = str(uuid.uuid4())
        ErrorHandler.handle_exception(e, context={"task": "send_reminder_email"}, correlation_id=correlation_id)
        resp["error"] = {"code": "TASK_EXECUTION_ERROR", "correlation_id": correlation_id}
        logger.critical("Error while creating report:", exc_info=True)
    state_map["processed"] = len(data)
    resp["state_map"] = state_map
    return resp


@shared_task(
    base=IdempotentTask,
    name="send_generated_report_on_mail",
    idempotency_ttl=SECONDS_IN_HOUR * 2,  # 2 hours (email task category)
    bind=True
)
def send_generated_report_on_mail(self):
    story = {
        "start_time": timezone.now(),
        "files_processed": 0,
        "emails_sent": 0,
        "errors": [],
        "end_time": timezone.now(),
    }

    try:
        for file in walk_directory(settings.TEMP_REPORTS_GENERATED):
            story["files_processed"] += 1
            sendmail, filename_without_extension = check_time_of_report(file)
            if sendmail:
                if record := get_report_record(filename_without_extension):
                    utils.send_email(
                        subject="Test Subject",
                        body="Test Body",
                        to=record.to_addr,
                        cc=record.cc,
                        atts=[file],
                    )
                    story["emails_sent"] += 1
                    # file deletion
                    story = remove_reportfile(file, story)
                else:
                    logger.info(f"No record found for file {os.path.basename(file)}")
            else:
                logger.info("No files to send at this moment")
    except (AttributeError, DatabaseError, FileNotFoundError, IOError, IntegrationException, IntegrityError, OSError, ObjectDoesNotExist, PermissionError, TypeError, ValidationError, ValueError, json.JSONDecodeError) as e:
        story["errors"].append(handle_error(e))
        logger.critical("something went wrong", exc_info=True)
    story["end_time"] = timezone.now()
    return story


@shared_task(bind=True, name="send_generated_report_onfly_email")
def send_generated_report_onfly_email(self, filepath, fromemail, to, cc, ctzoffset):
    story = {"msg": ["send_generated_report_onfly_email [started]"]}
    try:
        story["msg"].append(f"{filepath = } {fromemail = } {to = } {cc =}")
        currenttime = timezone.now() + timedelta(minutes=int(ctzoffset))
        msg = EmailMessage(
            f"Your Requested report! on {currenttime.strftime('%d-%b-%Y %H:%M:%S')}",
            from_email=fromemail,
            to=to,
            cc=cc,
        )
        msg.attach_file(filepath)
        msg.send()
        story["msg"].append("Email Sent")
        remove_reportfile(filepath, story)
        story["msg"].append("send_generated_report_onfly_email [ended]")
    except (AttributeError, DatabaseError, FileNotFoundError, IOError, IntegrationException, IntegrityError, OSError, ObjectDoesNotExist, PermissionError, TypeError, ValidationError, ValueError, json.JSONDecodeError) as e:
        logger.critical(
            "something went wrong in bg task send_generated_report_onfly_email",
            exc_info=True,
        )
    return story


@app.task(
    bind=True,
    default_retry_delay=300,
    max_retries=5,
    name="process_graphql_mutation_async",
)
def process_graphql_mutation_async(self, payload):
    """
    Process the incoming payload containing a GraphQL mutation and file data.

    Args:
        payload (str): The JSON-encoded payload containing the mutation query and variables.

    Returns:
        str: The JSON-encoded response containing the mutation result or errors.
    """
    from apps.service.utils import execute_graphql_mutations

    try:
        post_data = json.loads(payload)
        query = post_data.get("mutation")
        variables = post_data.get("variables", {})

        if query and variables:
            resp = execute_graphql_mutations(query, variables)
        else:
            mqlog.warning("Invalid records or query in the payload.")
            resp = json.dumps({"errors": ["No file data found"]})
    except (AttributeError, DatabaseError, FileNotFoundError, IOError, IntegrationException, IntegrityError, OSError, ObjectDoesNotExist, PermissionError, TypeError, ValidationError, ValueError, json.JSONDecodeError) as e:
        mqlog.error(f"Error processing payload: {e}", exc_info=True)
        resp = json.dumps({"errors": [str(e)]})
        raise e
    return resp


@app.task(bind=True, name="insert_json_records_async")
def insert_json_records_async(self, records, tablename):
    from apps.service.utils import get_model_or_form
    from apps.service.validators import clean_record

    if model := get_model_or_form(tablename):
        tlog.info("processing bulk json records for insert/update")
        for record in records:
            # Handle both string and dict inputs
            if isinstance(record, str):
                record = json.loads(record)
            record = clean_record(record)
            tlog.info(f"processing record {pformat(record)}")
            if model.objects.filter(uuid=record["uuid"]).exists():
                model.objects.filter(uuid=record["uuid"]).update(**record)
                tlog.info("record is already exist so updating it now..")
            else:
                tlog.info("record is not exist so creating new one..")
                model.objects.create(**record)
        return "Records inserted/updated successfully"


@app.task(bind=True, name="create_save_report_async")
def create_save_report_async(self, formdata, client_id, user_email, user_id):
    try:
        returnfile = formdata.get("export_type") == "SEND"
        report_essentials = rutils.ReportEssentials(report_name=formdata["report_name"])
        logger.info(f"report essentials: {report_essentials}")
        ReportFormat = report_essentials.get_report_export_object()
        report = ReportFormat(
            filename=formdata["report_name"],
            client_id=client_id,
            formdata=formdata,
            returnfile=True,
        )
        logger.info(f"Report Format initialized, {report}")

        if response := report.execute():
            if returnfile:
                rutils.process_sendingreport_on_email(response, formdata, user_email)
                return {
                    "status": 201,
                    "message": "Report generated successfully and email sent",
                    "alert": "alert-success",
                }
            filepath = save_report_to_tmp_folder(
                formdata["report_name"],
                ext=formdata["format"],
                report_output=response,
                dir=f"{settings.ONDEMAND_REPORTS_GENERATED}/{user_id}",
            )
            logger.info(f"Report saved at tmeporary location: {filepath}")
            return {
                "filepath": filepath,
                "filename": f'{formdata["report_name"]}.{formdata["format"]}',
                "status": 200,
                "message": "Report generated successfully",
                "alert": "alert-success",
            }
        else:
            return {
                "status": 404,
                "message": "No data found matching your report criteria.\
        Please check your entries and try generating the report again",
                "alert": "alert-warning",
            }
    except (AttributeError, DatabaseError, FileNotFoundError, IOError, IntegrationException, IntegrityError, OSError, ObjectDoesNotExist, PermissionError, TypeError, ValidationError, ValueError, json.JSONDecodeError) as e:
        logger.error(f"Error generating report: {e}")
        return {
            "status": 500,
            "message": "Internal Server Error",
            "alert": "alert-danger",
        }


@app.task(bind=True, name="cleanup_reports_which_are_12hrs_old")
def cleanup_reports_which_are_12hrs_old(self, dir_path, hours_old=12):
    for root, dirs, files in os.walk(dir_path):
        for filename in files:
            file_path = os.path.join(root, filename)
            threshold = datetime.now() - timedelta(hours=hours_old)
            try:
                if os.path.isfile(file_path):
                    file_stats = os.stat(file_path)
                    last_modified = datetime.fromtimestamp(file_stats.st_mtime)
                    if last_modified < threshold:
                        os.remove(file_path)
                        logger.info(
                            f"Deleted file: {file_path} as it was older than {hours_old} hours"
                        )
            except (ValueError, TypeError) as e:
                logger.error(f"Error deleting file {file_path}: {e}")


@app.task(
    bind=True,
    default_retry_delay=300,
    max_retries=5,
    name="process_graphql_download_async",
)
def process_graphql_download_async(self, payload):
    """
    Process the incoming payload containing a GraphQL download and file data.

    Args:
        payload (str): The JSON-encoded payload containing the mutation query and variables.

    Returns:
        str: The JSON-encoded response containing the mutation result or errors.
    """
    from apps.service.utils import execute_graphql_mutations

    try:
        post_data = json.loads(payload)
        query = post_data.get("query")

        if query:
            resp = execute_graphql_mutations(query, download=True)
        else:
            mqlog.warning("Invalid records or query in the payload.")
            resp = json.dumps({"errors": ["No file data found"]})
    except (AttributeError, DatabaseError, FileNotFoundError, IOError, IntegrationException, IntegrityError, OSError, ObjectDoesNotExist, PermissionError, TypeError, ValidationError, ValueError, json.JSONDecodeError) as e:
        mqlog.error(f"Error processing payload: {e}", exc_info=True)
        resp = json.dumps({"errors": [str(e)]})
        raise e
    return resp


@shared_task(bind=True, name="send_email_notification_for_sla_report")
def send_email_notification_for_sla_report(self, slaid, sitename):
    jsonresp = {"story": "", "traceback": ""}
    try:
        from django.apps import apps
        from django.template.loader import render_to_string
        from apps.reports.report_designs.service_level_agreement import (
            ServiceLevelAgreement,
        )
        from apps.work_order_management.models import Vendor
        from dateutil.relativedelta import relativedelta
        from datetime import datetime
        from apps.work_order_management.utils import save_pdf_to_tmp_location
        from apps.work_order_management.views import SLA_View

        monthly_choices = SLA_View.MONTH_CHOICES
        Wom = apps.get_model("work_order_management", "Wom")
        People = apps.get_model("peoples", "People")
        (
            sla_details,
            rounded_overall_score,
            question_ans,
            all_average_score,
            remarks,
        ) = Wom.objects.get_sla_answers(slaid)
        sla_record = Wom.objects.filter(id=slaid)[0]
        permit_no = sla_record.other_data["wp_seqno"]
        approvers = sla_record.approvers
        status = sla_record.workpermit
        jsonresp["story"] += f"\n{sla_details}"
        report_no = sla_record.other_data["wp_seqno"]
        uuid = sla_record.uuid
        wom = Wom.objects.get(id=slaid)
        is_month_present = wom.other_data.get("month", None)
        if not is_month_present:
            month_no = wom.cdtz.month - 1
            if month_no == 0:
                month_no = 12
                year = wom.cdtz.year - 1
            else:
                year = wom.cdtz.year
            month_name = monthly_choices.get(f"{month_no}")
        else:
            month_name = is_month_present
            year = wom.cdtz.year
            if month_name == "December":
                year = wom.cdtz.year - 1
        sla_report_obj = ServiceLevelAgreement(
            returnfile=True,
            filename="Service Level Agreement",
            formdata={
                "id": slaid,
                "bu__buname": sitename,
                "submit_button_flow": "true",
                "filename": "Service Level Agreement",
                "workpermit": sla_record.workpermit,
            },
        )
        attachment = sla_report_obj.execute()
        attachment_path = save_pdf_to_tmp_location(
            attachment, "Vendor performance report", permit_no
        )
        vendor_id = sla_record.vendor_id
        vendor_name = Vendor.objects.get(id=vendor_id).name
        if sla_details:
            qset = People.objects.filter(peoplecode__in=approvers)
            for p in qset.values("email", "id"):
                logger.info("Sending email to user", extra={'user_id': p['id']})
                jsonresp["story"] += f"sending email to user {p['id']}"
                msg = EmailMessage()
                msg.subject = f"{sitename} Vendor Performance {vendor_name} of {month_name}-{year}: Approval Pending"
                msg.to = [p["email"]]
                msg.from_email = settings.DEFAULT_FROM_EMAIL
                cxt = {
                    "sections": sla_details,
                    "peopleid": p["id"],
                    "HOST": settings.HOST,
                    "slaid": slaid,
                    "sitename": sitename,
                    "rounded_overall_score": rounded_overall_score,
                    "peopleid": p["id"],
                    "reportid": uuid,
                    "report_name": "Vendor Performance",
                    "report_no": report_no,
                    "status": status,
                    "vendorname": vendor_name,
                    "service_month": (
                        datetime.now() - relativedelta(months=1)
                    ).strftime("%B %Y"),
                }
                html = render_to_string(
                    "work_order_management/sla_report_approver_action.html", context=cxt
                )
                msg.body = html
                msg.content_subtype = "html"
                msg.attach_file(attachment_path, mimetype="application/pdf")
                msg.send()
                logger.info("Email sent successfully", extra={'user_id': p['id']})
                jsonresp["story"] += f"email sent to user {p['id']}"
            jsonresp["story"] += f"A Workpermit email sent of pk: {slaid}"
    except (AttributeError, DatabaseError, FileNotFoundError, IOError, IntegrationException, IntegrityError, OSError, ObjectDoesNotExist, PermissionError, TypeError, ValidationError, ValueError, json.JSONDecodeError) as e:
        logger.critical(
            "something went wrong while runing sending email to approvers",
            exc_info=True,
        )
        # Stack trace exposure security fix - log error securely without exposing details
        from apps.core.error_handling import ErrorHandler
        import uuid
        correlation_id = str(uuid.uuid4())
        ErrorHandler.handle_exception(e, context={"task": "email_notification"}, correlation_id=correlation_id)
        jsonresp["error"] = {"code": "TASK_EXECUTION_ERROR", "correlation_id": correlation_id}
    return jsonresp


@shared_task(name="send_mismatch_notification")
def send_mismatch_notification(mismatch_data):
    # This task sends mismatch data to the NOC dashboard
    logger.info(f"Mismatched detected: {mismatch_data}")
    # Add logic to send data to NOC dashboard


@shared_task(bind=True, max_retries=3, default_retry_delay=60, name="process_audio_transcript")
def process_audio_transcript(self, jobneed_detail_id):
    """
    Background task to process audio transcription for JobneedDetails

    Args:
        jobneed_detail_id: ID of the JobneedDetails instance with audio attachment

    Returns:
        dict: Task result with status and transcript data
    """
    result = {"story": "process_audio_transcript() started\n", "traceback": ""}

    try:
        from apps.activity.models.job_model import JobneedDetails
        from apps.core.services.speech_to_text_service import SpeechToTextService
        from django.utils import timezone

        result["story"] += f"Processing transcript for JobneedDetails ID: {jobneed_detail_id}\n"

        # Get JobneedDetails instance
        try:
            jobneed_detail = JobneedDetails.objects.get(id=jobneed_detail_id)
            result["story"] += f"Found JobneedDetails: {jobneed_detail.id}\n"
        except JobneedDetails.DoesNotExist:
            error_msg = f"JobneedDetails with ID {jobneed_detail_id} not found"
            logger.error(error_msg)
            result["story"] += f"ERROR: {error_msg}\n"
            return result

        # Update status to PROCESSING
        jobneed_detail.transcript_status = 'PROCESSING'
        jobneed_detail.save()
        result["story"] += "Status updated to PROCESSING\n"

        # Initialize speech service
        speech_service = SpeechToTextService()

        if not speech_service.is_service_available():
            error_msg = "Speech-to-Text service not available - check Google Cloud credentials"
            logger.error(error_msg)
            jobneed_detail.transcript_status = 'FAILED'
            jobneed_detail.save()
            result["story"] += f"ERROR: {error_msg}\n"
            return result

        # Process the transcription
        logger.info(f"Starting transcription for JobneedDetails {jobneed_detail_id}")
        transcript = speech_service.transcribe_audio(jobneed_detail)

        if transcript:
            # Success - update with transcript
            jobneed_detail.transcript = transcript
            jobneed_detail.transcript_status = 'COMPLETED'
            jobneed_detail.transcript_processed_at = timezone.now()

            # Set language if not already set
            if not jobneed_detail.transcript_language:
                jobneed_detail.transcript_language = speech_service.DEFAULT_LANGUAGE

            jobneed_detail.save()

            logger.info(f"Transcription completed for JobneedDetails {jobneed_detail_id}")
            result["story"] += f"SUCCESS: Transcription completed, length: {len(transcript)} characters\n"
            result["transcript_length"] = len(transcript)
            result["status"] = "COMPLETED"

        else:
            # Transcription failed
            jobneed_detail.transcript_status = 'FAILED'
            jobneed_detail.transcript_processed_at = timezone.now()
            jobneed_detail.save()

            logger.warning(f"Transcription failed for JobneedDetails {jobneed_detail_id}")
            result["story"] += "WARNING: Transcription failed - no transcript returned\n"
            result["status"] = "FAILED"

    except (AttributeError, DatabaseError, FileNotFoundError, IOError, IntegrationException, IntegrityError, OSError, ObjectDoesNotExist, PermissionError, TypeError, ValidationError, ValueError, json.JSONDecodeError) as e:
        # Handle unexpected errors
        logger.error(f"Error processing audio transcript for JobneedDetails {jobneed_detail_id}: {str(e)}", exc_info=True)
        # Stack trace exposure security fix - log error securely without exposing details
        from apps.core.error_handling import ErrorHandler
        import uuid
        correlation_id = str(uuid.uuid4())
        ErrorHandler.handle_exception(e, context={"task": "face_recognition"}, correlation_id=correlation_id)
        result["error"] = {"code": "TASK_EXECUTION_ERROR", "correlation_id": correlation_id}

        try:
            # Try to update status to FAILED
            jobneed_detail = JobneedDetails.objects.get(id=jobneed_detail_id)
            jobneed_detail.transcript_status = 'FAILED'
            jobneed_detail.transcript_processed_at = timezone.now()
            jobneed_detail.save()
        except (DatabaseError, IntegrityError, ObjectDoesNotExist) as save_error:
            logger.error(f"Could not update failed status: {save_error}")

        # Retry the task if we haven't exceeded max retries
        if self.request.retries < self.max_retries:
            logger.info(f"Retrying transcription task, attempt {self.request.retries + 1}")
            raise self.retry(exc=e)
        else:
            logger.error(f"Transcription task failed permanently after {self.max_retries} retries")
            result["status"] = "FAILED_PERMANENTLY"

    return result


# ============================================================================
# ASYNC PDF GENERATION TASKS
# ============================================================================

@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def generate_pdf_async(
    self,
    task_id: str,
    template_name: str,
    context_data: Dict[str, Any],
    user_id: int,
    filename: Optional[str] = None,
    css_files: Optional[List[str]] = None,
    output_format: str = 'pdf'
) -> Dict[str, Any]:
    """
    Generate PDF asynchronously using AsyncPDFGenerationService.

    This task moves heavy PDF generation operations out of the request cycle,
    providing better user experience and system performance.

    Args:
        task_id: Unique task identifier
        template_name: Django template path
        context_data: Template context data
        user_id: ID of requesting user
        filename: Optional custom filename
        css_files: Optional list of CSS file paths
        output_format: Output format (pdf, html)

    Returns:
        Dict containing generation results
    """
    pdf_service = AsyncPDFGenerationService()

    try:
        logger.info(f"Starting PDF generation task {task_id} for user {user_id}")

        # Update task status to processing
        pdf_service._update_task_status(task_id, 'processing', 'Starting PDF generation')

        # Generate PDF content
        result = pdf_service.generate_pdf_content(
            task_id=task_id,
            template_name=template_name,
            context_data=context_data,
            css_files=css_files,
            output_format=output_format
        )

        if result['status'] == 'completed':
            logger.info(f"PDF generation completed successfully: {task_id}")
            pdf_service._update_task_status(
                task_id,
                'completed',
                f"PDF generated successfully: {result.get('file_path', '')}"
            )
        else:
            logger.error(f"PDF generation failed: {task_id} - {result.get('error', 'Unknown error')}")

        return result

    except (AttributeError, DatabaseError, FileNotFoundError, IOError, IntegrationException, IntegrityError, OSError, ObjectDoesNotExist, PermissionError, TypeError, ValidationError, ValueError, json.JSONDecodeError) as e:
        error_msg = f"PDF generation task failed: {str(e)}"
        logger.error(f"Task {task_id} failed: {error_msg}", exc_info=True)

        pdf_service._update_task_status(task_id, 'failed', error_msg)

        # Retry logic
        if self.request.retries < self.max_retries:
            logger.info(f"Retrying PDF generation task {task_id}, attempt {self.request.retries + 1}")
            raise self.retry(exc=e, countdown=60 * (self.request.retries + 1))
        else:
            logger.error(f"PDF generation task {task_id} failed permanently after {self.max_retries} retries")
            return {
                'status': 'failed',
                'error': error_msg,
                'task_id': task_id
            }


@shared_task(bind=True, max_retries=2, default_retry_delay=30)
def external_api_call_async(
    self,
    url: str,
    method: str = 'GET',
    headers: Optional[Dict[str, str]] = None,
    data: Optional[Dict[str, Any]] = None,
    timeout: int = 30,
    user_id: Optional[int] = None
) -> Dict[str, Any]:
    """
    Make external API calls asynchronously to prevent blocking request cycle.

    Features:
    - Configurable timeout and retry logic
    - Secure header handling
    - Response validation
    - Error recovery

    Args:
        url: Target API URL
        method: HTTP method (GET, POST, PUT, DELETE)
        headers: Optional HTTP headers
        data: Optional request data
        timeout: Request timeout in seconds
        user_id: Optional user ID for logging

    Returns:
        Dict containing API response or error information
    """
    import requests
    from requests.adapters import HTTPAdapter
    from urllib3.util.retry import Retry

    try:
        logger.info(f"Starting external API call to {url} for user {user_id}")

        # Configure requests session with retry strategy
        session = requests.Session()
        retry_strategy = Retry(
            total=3,
            status_forcelist=[429, 500, 502, 503, 504],
            method_whitelist=["HEAD", "GET", "OPTIONS", "POST"],
            backoff_factor=1
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("http://", adapter)
        session.mount("https://", adapter)

        # Prepare request parameters
        request_params = {
            'timeout': timeout,
            'headers': headers or {}
        }

        # Add data for POST/PUT requests
        if method.upper() in ['POST', 'PUT', 'PATCH'] and data:
            request_params['json'] = data

        # Make the API call
        response = session.request(method.upper(), url, **request_params)

        # Validate response
        response.raise_for_status()

        # Parse response
        try:
            response_data = response.json()
        except ValueError:
            response_data = response.text

        result = {
            'status': 'success',
            'status_code': response.status_code,
            'data': response_data,
            'headers': dict(response.headers),
            'url': url,
            'method': method.upper()
        }

        logger.info(f"External API call completed successfully: {url}")
        return result

    except requests.exceptions.Timeout:
        error_msg = f"API call timeout after {timeout}s: {url}"
        logger.warning(error_msg)

        if self.request.retries < self.max_retries:
            logger.info(f"Retrying API call to {url}, attempt {self.request.retries + 1}")
            raise self.retry(exc=requests.exceptions.Timeout(error_msg))

        return {
            'status': 'error',
            'error': 'timeout',
            'message': error_msg,
            'url': url
        }

    except requests.exceptions.RequestException as e:
        error_msg = f"API call failed: {str(e)}"
        logger.error(f"External API call to {url} failed: {error_msg}", exc_info=True)

        if self.request.retries < self.max_retries:
            logger.info(f"Retrying API call to {url}, attempt {self.request.retries + 1}")
            raise self.retry(exc=e)

        return {
            'status': 'error',
            'error': 'request_failed',
            'message': error_msg,
            'url': url
        }

    except (AttributeError, DatabaseError, FileNotFoundError, IOError, IntegrationException, IntegrityError, OSError, ObjectDoesNotExist, PermissionError, TypeError, ValidationError, ValueError, json.JSONDecodeError, requests.ConnectionError, requests.RequestException, requests.Timeout) as e:
        error_msg = f"Unexpected error in API call: {str(e)}"
        logger.error(f"Unexpected error in external API call to {url}: {error_msg}", exc_info=True)

        return {
            'status': 'error',
            'error': 'unexpected_error',
            'message': error_msg,
            'url': url
        }


@shared_task(bind=True)
def cleanup_expired_pdf_tasks(self) -> Dict[str, Any]:
    """
    Clean up expired PDF generation tasks and temporary files.

    This task should be run periodically via Celery beat scheduler.

    Returns:
        Dict containing cleanup statistics
    """
    try:
        logger.info("Starting PDF task cleanup")

        pdf_service = AsyncPDFGenerationService()
        cleaned_count = pdf_service.cleanup_expired_tasks()

        result = {
            'status': 'success',
            'cleaned_tasks': cleaned_count,
            'timestamp': timezone.now().isoformat()
        }

        logger.info(f"PDF task cleanup completed: {cleaned_count} tasks cleaned")
        return result

    except (AttributeError, DatabaseError, FileNotFoundError, IOError, IntegrationException, IntegrityError, OSError, ObjectDoesNotExist, PermissionError, TypeError, ValidationError, ValueError, json.JSONDecodeError, requests.ConnectionError, requests.RequestException, requests.Timeout) as e:
        error_msg = f"PDF task cleanup failed: {str(e)}"
        logger.error(error_msg, exc_info=True)

        return {
            'status': 'error',
            'error': error_msg,
            'timestamp': timezone.now().isoformat()
        }
