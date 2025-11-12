"""
Ticket operations and escalation tasks

Migrated from god file refactoring
Date: 2025-09-30
Updated: 2025-10-31 - Removed unused GCS imports (optimization)
"""
from celery import shared_task
from django.core.exceptions import ObjectDoesNotExist
from django.db import DatabaseError, IntegrityError
from apps.core.exceptions import IntegrationException
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

# Initialize logger for ticket tasks
logger = logging.getLogger('background_tasks.ticket')


@shared_task(
    bind=True,
    default_retry_delay=300,
    max_retries=5,
    soft_time_limit=300,  # 5 minutes soft limit
    time_limit=600,        # 10 minutes hard limit
    name="send_ticket_email"
)
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
    bind=True,
    name="ticket_escalation",
    idempotency_scope='global',
    idempotency_ttl=14400,  # 4 hours
    soft_time_limit=300,     # 5 minutes soft limit
    time_limit=600,          # 10 minutes hard limit
    max_retries=3
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
    bind=True,
    name="alert_sendmail",
    soft_time_limit=180,  # 3 minutes - alert email
    time_limit=360         # 6 minutes hard limit
)
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
