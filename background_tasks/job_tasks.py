"""
Job lifecycle management tasks

Migrated from god file refactoring
Date: 2025-09-30
Updated: 2025-10-31 - Removed unused GCS imports (optimization)
"""
from celery import shared_task
from django.core.exceptions import ObjectDoesNotExist
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
from .utils import alert_deviation, alert_observation
from .utils import validate_email_list
from apps.activity.models.asset_model import Asset
from apps.activity.models.job_model import Job
from apps.activity.models.job_model import JobneedDetails
from apps.core import utils
from apps.core.error_handling import ErrorHandler
from apps.core.queries import QueryRepository
from apps.core.services.async_pdf_service import AsyncPDFGenerationService
from apps.core.services.cache_warming_service import warm_critical_caches_task
from apps.core.services.speech_to_text_service import SpeechToTextService
from apps.core.tasks.base import (
    BaseTask, EmailTask, ExternalServiceTask, MaintenanceTask, IdempotentTask, TaskMetrics, log_task_context
)
from apps.core.tasks.utils import task_retry_policy
from apps.core.utils_new.db_utils import get_current_db_name
from apps.core.validation import XSSPrevention
# from apps.face_recognition.services import get_face_recognition_service  # Unused import - removed Oct 2025
from apps.client_onboarding.models import Bt
from apps.peoples.models import People
from apps.scheduler.models.reminder import Reminder
from apps.reports import utils as rutils
from apps.reports.models import ScheduleReport
from apps.reports.report_designs.service_level_agreement import (
            ServiceLevelAgreement,
        )
from apps.scheduler.utils import (
        calculate_startdtz_enddtz_for_ppm,
        get_datetime_list,
        insert_into_jn_and_jnd,
        get_readable_dates,
        create_ppm_reminder,
    )
from apps.service.services.database_service import get_model_or_form
from apps.service.validators import clean_record
from apps.work_order_management.models import Vendor
from apps.work_order_management.models import Wom, WomDetails
from apps.work_order_management.utils import (
            approvers_email_and_name,
            get_peoplecode,
        )
from apps.work_order_management.utils import save_pdf_to_tmp_location
# SLA_View import removed - use constants.MONTH_CHOICES instead
# from apps.work_order_management.views import SLA_View
from apps.y_helpdesk.models import Ticket
from background_tasks import utils as butils
from celery import shared_task
from datetime import datetime
from datetime import timedelta, datetime
from dateutil.relativedelta import relativedelta
from django.apps import apps
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.mail import EmailMessage
from django.db import transaction
from django.db.models import Q
from django.template.loader import render_to_string
from django.templatetags.static import static
from django.utils import timezone
from intelliwiz_config.celery import app
from io import BytesIO
from logging import getLogger
from pprint import pformat
from requests.adapters import HTTPAdapter
from scripts.utilities.mqtt_utils import publish_message
from typing import Dict, Any, Optional, List, Union
from urllib3.util.retry import Retry
import base64
import json
import logging
import mimetypes
import os
import re
import requests
import time
import traceback as tb
import uuid


@shared_task(
    base=IdempotentTask,
    bind=True,
    name="auto_close_jobs",
    idempotency_scope='global',
    idempotency_ttl=14400,  # 4 hours (from SECONDS_IN_HOUR * 4)
    soft_time_limit=600,     # 10 minutes - batch job closing
    time_limit=900            # 15 minutes hard limit
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
    name="create_ppm_job",
    soft_time_limit=1800,  # 30 minutes soft limit (processes multiple jobs)
    time_limit=2400,        # 40 minutes hard limit
    max_retries=2
)
def create_ppm_job(jobid=None):
    F, d = {}, []
    # resp = {'story':"", 'traceback':""}
    startdtz = enddtz = msg = resp = None

    from apps.activity.models.job_model import Job
    from apps.activity.models.asset_model import Asset

    from apps.scheduler.utils import (
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


@shared_task(
    bind=True,
    name="task_every_min",
    soft_time_limit=30,  # 30 seconds - health check
    time_limit=60         # 1 minute hard limit
)
def task_every_min(self):
    from django.utils import timezone

    return f"task completed at {timezone.now()}"
