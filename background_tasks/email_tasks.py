"""
Email notification tasks for work permits, approvals, and reminders

Migrated from god file refactoring
Date: 2025-09-30
"""
from celery import shared_task
from django.core.exceptions import ObjectDoesNotExist
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
    BaseTask, EmailTask, ExternalServiceTask, MaintenanceTask, TaskMetrics, log_task_context
)
from apps.core.tasks.utils import task_retry_policy
from apps.core.utils_new.db_utils import get_current_db_name
from apps.core.validation import XSSPrevention
# from apps.face_recognition.services import get_face_recognition_service  # Unused import - removed Oct 2025
from apps.onboarding.models import Bt
from apps.peoples.models import People
from apps.reminder.models import Reminder
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
# from apps.service.utils import execute_graphql_mutations  # GraphQL removed Oct 2025
from apps.service.utils import get_model_or_form
from apps.service.validators import clean_record
from apps.work_order_management.models import Vendor
from apps.work_order_management.models import Wom, WomDetails
from apps.work_order_management.utils import (
            approvers_email_and_name,
            get_peoplecode,
        )
from apps.work_order_management.utils import save_pdf_to_tmp_location
# SLA_View import moved to function scope to avoid circular dependency
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
        # Import constants instead of view class to avoid circular dependency
        from apps.work_order_management.constants import MONTH_CHOICES

        monthly_choices = MONTH_CHOICES
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
        # Import constants instead of view class to avoid circular dependency
        from apps.work_order_management.constants import MONTH_CHOICES

        monthly_choices = MONTH_CHOICES
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


@shared_task(
    base=EmailTask,
    bind=True,
    name="send_reminder_email"
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


@shared_task(name="send_mismatch_notification")
def send_mismatch_notification(mismatch_data):
    # This task sends mismatch data to the NOC dashboard
    logger.info(f"Mismatched detected: {mismatch_data}")

