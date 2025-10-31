"""
Maintenance and cleanup tasks

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
    IdempotentTask,
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
