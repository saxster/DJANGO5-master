"""
Integration tasks for MQTT and external APIs

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
# Face recognition import removed - not used in this file (Oct 2025 cleanup)
# from apps.face_recognition.services import get_face_recognition_service
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
# from apps.service.utils import execute_graphql_mutations  # Removed Oct 2025 - GraphQL deleted
from apps.service.utils import get_model_or_form
from apps.service.validators import clean_record
from apps.work_order_management.models import Vendor
from apps.work_order_management.models import Wom, WomDetails
from apps.work_order_management.utils import (
            approvers_email_and_name,
            get_peoplecode,
        )
from apps.work_order_management.utils import save_pdf_to_tmp_location
# SLA_View import removed - never used (dead code that caused circular import)
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


@shared_task(bind=True, name="insert_json_records_async")
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
