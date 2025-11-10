"""
Media processing tasks including face recognition and audio

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
from apps.core.error_handling import ErrorHandler
from apps.core.queries import QueryRepository
from apps.core.services.async_pdf_service import AsyncPDFGenerationService
from apps.core.services.cache_warming_service import warm_critical_caches_task
from apps.core.services.speech_to_text_service import SpeechToTextService
from apps.core.tasks.base import (
    IdempotentTask,
    BaseTask, EmailTask, ExternalServiceTask, MaintenanceTask, TaskMetrics, log_task_context
)
from apps.core.tasks.utils import task_retry_policy
from apps.tenants.constants import DEFAULT_DB_ALIAS
from apps.tenants.utils import tenant_context
from apps.core.validation import XSSPrevention
# from apps.face_recognition.services import get_face_recognition_service  # Imported locally where needed (line 169)
from apps.client_onboarding.models import Bt
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
    bind=True,
    default_retry_delay=300,
    max_retries=5,
    soft_time_limit=180,  # 3 minutes - face recognition processing
    time_limit=360,        # 6 minutes hard limit
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
        target_db = db or DEFAULT_DB_ALIAS

        with tenant_context(target_db):
            with transaction.atomic(using=target_db):
                invalid_tokens = {None, "NONE", "", 1}
                if pel_uuid in invalid_tokens or peopleid in invalid_tokens:
                    logger.info("Face recognition skipped due to missing identifiers")
                    result["story"] += "Missing pel_uuid or peopleid; skipping recognition.\n"
                    return result

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


@shared_task(
    name="move_media_to_cloud_storage",
    soft_time_limit=1800,  # 30 minutes - file operations
    time_limit=2400         # 40 minutes hard limit
)
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
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    soft_time_limit=600,   # 10 minutes - audio transcription
    time_limit=900,         # 15 minutes hard limit
    name="process_audio_transcript"
)
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
